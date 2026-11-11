using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Sincal.DwgProps;
#if ZWCAD
using ZwSoft.ZwCAD.ApplicationServices;
using ZwSoft.ZwCAD.DatabaseServices;
using ZwSoft.ZwCAD.Geometry;
using ZwSoft.ZwCAD.Runtime;
using CadApplication = ZwSoft.ZwCAD.ApplicationServices.Application;
#else
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using CadApplication = Autodesk.AutoCAD.ApplicationServices.Application;
#endif

namespace Sincal.RevisionGrip;

// Compiled only when RevisionGripTests=true. Runs against disposable owned drawings.
public static class RevisionGripSmoke
{
    private const string BlockName = "VIÑETA G130";
    private sealed class Baseline
    {
        internal ObjectId Definition;
        internal RevisionEditor.Snapshot Snapshot = null!;
        internal string[] Cached = null!;
    }
    private static readonly Dictionary<Document, Baseline> Before = new Dictionary<Document, Baseline>();
    private static readonly List<GripDataCollection> GripResults = new List<GripDataCollection>();
    internal static RevisionButton Button = null!;
    internal static ObjectId ButtonEntity;

    private static string Root()
    {
        var root = Path.GetDirectoryName(CadApplication.DocumentManager.MdiActiveDocument.Name)!;
        if (!Path.GetFileName(root).StartsWith("sincal-revision-grip-native-", StringComparison.Ordinal))
            throw new InvalidOperationException("Smoke commands only accept the runner's temporary fixtures.");
        return root;
    }
    private static void Log(string root, string message) => File.AppendAllText(Path.Combine(root, "native-result.txt"), message + Environment.NewLine);
    private static void Assert(bool value, string label)
    {
        if (!value) throw new InvalidOperationException(label);
    }
    private static ObjectId Definition(Database db)
    {
        using var tr = db.TransactionManager.StartTransaction();
        return ((BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead))[BlockName];
    }
    private static RevisionEditor.Snapshot Read(Document doc, ObjectId definition)
    {
        using (doc.LockDocument()) return RevisionEditor.Read(doc.Database, definition);
    }
    private static string[] Cached(Document doc,ObjectId definition)
    {
        using(doc.LockDocument())
        using(var tr=doc.Database.TransactionManager.StartTransaction())
        {
            var block=(BlockTableRecord)tr.GetObject(definition,OpenMode.ForRead);
            var table=block.Cast<ObjectId>().Select(id=>tr.GetObject(id,OpenMode.ForRead)).OfType<Table>()
                .Single(t=>t.Columns.Count==6 && !t.Cells[0,0].Contents[0].FieldId.IsNull);
            var result=Enumerable.Range(0,table.Columns.Count).Select(c=>
            {
                var id=table.Cells[0,c].Contents[0].FieldId;
                return table.Cells[0,c].TextString+"\n"+(id.IsNull?"":((Field)tr.GetObject(id,OpenMode.ForRead)).GetFieldCode(FieldCodeFlags.EvaluatedText));
            }).ToArray();
            tr.Commit();
            return result;
        }
    }
    private static void Rejected(Action action, string label)
    {
        try { action(); }
        catch (InvalidOperationException) { return; }
        throw new InvalidOperationException(label);
    }

    [CommandMethod("SINCAL_REV_FIXTURES", CommandFlags.Session)]
    public static void Fixtures()
    {
        var root = Root();
        try
        {
            Log(root, "FIXTURES_STARTED");
            var doc = CadApplication.DocumentManager.MdiActiveDocument;
            Assert(Path.GetFileName(doc.Name) == "seed.dwg", "Fixture source is not seed.dwg");
            using (doc.LockDocument())
            {
                var source = doc.Database;
                var definition = Definition(source);
                var previous = HostApplicationServices.WorkingDatabase;
                try
                {
                    foreach (var name in new[] { "source", "target", "omitted", "fault" })
                    {
                        Log(root, "FIXTURE_CLONE " + name);
                        HostApplicationServices.WorkingDatabase = source;
                        using var db = new Database(true, true);
                        source.WblockCloneObjects(new ObjectIdCollection { definition }, db.BlockTableId,
                            new IdMapping(), DuplicateRecordCloning.Ignore, false);
                        Log(root, "FIXTURE_CLONED " + name);
                        HostApplicationServices.WorkingDatabase = db;
                        db.SummaryInfo = source.SummaryInfo;
                        db.Insunits = source.Insunits;
                        using (var tr = db.TransactionManager.StartTransaction())
                        {
                            var bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                            var ms = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);
                            var block = (BlockTableRecord)tr.GetObject(bt[BlockName], OpenMode.ForRead);
                            var reference = new BlockReference(Point3d.Origin, block.ObjectId);
                            ms.AppendEntity(reference); tr.AddNewlyCreatedDBObject(reference, true);
                            foreach (ObjectId id in block)
                            {
                                if (tr.GetObject(id, OpenMode.ForRead) is not AttributeDefinition a || a.Constant) continue;
                                var attribute = new AttributeReference();
                                attribute.SetAttributeFromBlock(a, reference.BlockTransform);
                                reference.AttributeCollection.AppendAttribute(attribute);
                                tr.AddNewlyCreatedDBObject(attribute, true);
                            }
                            tr.Commit();
                        }
                        db.SaveAs(Path.Combine(root, name + ".dwg"), DwgVersion.Current);
                        HostApplicationServices.WorkingDatabase = source;
                    }
                }
                finally { HostApplicationServices.WorkingDatabase = previous; }
            }
            Log(root, "FIXTURES_READY");
        }
        catch (System.Exception error) { Log(root, "FAIL FIXTURES " + error); }
    }

    [CommandMethod("SINCAL_REV_SMOKE", CommandFlags.Session)]
    public static void Run()
    {
        var root = Root();
        try
        {
            var documents = CadApplication.DocumentManager.Cast<Document>()
                .Where(d => Path.GetDirectoryName(d.Name) == root).ToDictionary(d => Path.GetFileName(d.Name));
            var source = documents["source.dwg"];
            var target = documents["target.dwg"];
            var omitted = documents["omitted.dwg"];
            var fault = documents["fault.dwg"];
            Assert(CadApplication.DocumentManager.MdiActiveDocument == source, "Source must initially be active");
            foreach(var document in new[]{source,target})
                document.CommandEnded+=(sender,args)=>
                {
                    if(args.GlobalCommandName=="REGEN") Log(root,"REGEN_DONE "+Path.GetFileName(document.Name));
                };
            Log(root, "SMOKE_BASELINES");
            Before.Clear();
            foreach (var document in new[] { source, target, omitted })
            {
                Log(root, "SMOKE_READ " + Path.GetFileName(document.Name));
                var id = Definition(document.Database);
                Before.Add(document, new Baseline { Definition = id, Snapshot = Read(document, id), Cached=Cached(document,id) });
                Assert(Before[document].Snapshot.tables.Length == 1, "Fixture must have exactly one revision table");
            }
            var original = Before[source].Snapshot;
            var sheet = original.tables[0];
            Assert(sheet.cells[0][0].property != null, "Revision property is not available");

            var values = sheet.cells.Select(row => row.Select(cell => cell.text).ToArray()).ToArray();
            values[0][0] = "Z";
            var historyRow = Enumerable.Range(1, sheet.cells.Length - 1)
                .First(r => !RevisionTransfer.IsHeader(sheet.cells[r]) && sheet.cells[r][5].editable);
            values[historyRow][5] = "PRUEBA";
            var invalidValues = values.Select(row => (string[])row.Clone()).ToArray();
            invalidValues[0][0] = "INVALID\nVALUE";
            Rejected(() => RevisionTransfer.Plan(sheet, invalidValues, original), "Control characters were accepted");
            var shortSheet = sheet with { cells = sheet.cells.Take(sheet.cells.Length - 1).ToArray() };
            Rejected(() => RevisionTransfer.Plan(sheet, values, original with { tables = new[] { shortSheet } }),
                "Mismatched table dimensions were accepted");
            Log(root, "PASS invalid values and incompatible tables rejected");

            foreach (var document in new[] { source, target })
            {
                Log(root, "SMOKE_APPLY " + Path.GetFileName(document.Name));
                var baseline = Before[document];
                var changes = RevisionTransfer.Plan(sheet, values, baseline.Snapshot);
                RevisionTransfer.Apply(document, baseline.Snapshot, changes, baseline.Definition);
                using(document.LockDocument())
                    RevisionEditor.Verify(document.Database,baseline.Snapshot,changes,baseline.Definition);
                var current = Read(document, baseline.Definition);
                if(current.integrity!=baseline.Snapshot.integrity)
                {
                    File.WriteAllText(document.Name+".before.json",baseline.Snapshot.integrity);
                    File.WriteAllText(document.Name+".after.json",current.integrity);
                }
                Assert(current.integrity == baseline.Snapshot.integrity, "Fields, geometry or style changed");
                Assert(current.tables[0].cells[0][0].text == "Z", "Revision property did not change");
                Assert(current.tables[0].cells[historyRow][5].text == values[historyRow][5], "History did not change");
                Rejected(() => RevisionTransfer.Apply(document, baseline.Snapshot, changes, baseline.Definition),
                    "A stale editor snapshot was accepted");
                Log(root, "SMOKE_APPLIED " + Path.GetFileName(document.Name));
            }
            Assert(CadApplication.DocumentManager.MdiActiveDocument == source, "Applying to an inactive drawing changed the active document");
            Assert(RevisionTransfer.Matches(Before[omitted].Snapshot, Read(omitted, Before[omitted].Definition)),
                "Unselected drawing changed");
            Log(root, "PASS selected drawings, DWGPROPS, history, Fields, stale snapshots and omitted drawing");

            var faultDefinition = Definition(fault.Database);
            var faultBefore = Read(fault, faultDefinition);
            var cachedBefore=Cached(fault,faultDefinition);
            var faultChanges = RevisionTransfer.Plan(sheet, values, faultBefore);
            var reachedHook=false;
            RevisionTransfer.TestAfterApply=()=>
            {
                var changed=Read(fault,faultDefinition).tables[0];
                Assert(changed.cells[0][0].text=="Z" && changed.cells[historyRow][5].text=="PRUEBA"
                    && Cached(fault,faultDefinition)[0]=="Z\nZ","Fault must happen after table, DWGPROPS and FIELD results changed");
                reachedHook=true;
                throw new InvalidOperationException("Injected failure after Apply");
            };
            try { Rejected(() => RevisionTransfer.Apply(fault, faultBefore, faultChanges, faultDefinition),"Injected failure did not reject Apply"); }
            finally { RevisionTransfer.TestAfterApply=null; }
            Assert(reachedHook,"Rollback hook was not reached");
            Assert(RevisionTransfer.Matches(faultBefore, Read(fault, faultDefinition)), "Rollback did not restore the table and DWGPROPS");
            Assert(Cached(fault,faultDefinition).SequenceEqual(cachedBefore),"Rollback did not restore visible FIELD results");
            Log(root, "PASS rollback after failure following table, DWGPROPS and FIELD mutations");
            Log(root, "SMOKE_GRIP");
            using (source.LockDocument())
            using (var tr = source.Database.TransactionManager.StartTransaction())
            {
                var bt = (BlockTable)tr.GetObject(source.Database.BlockTableId, OpenMode.ForRead);
                var ms = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForRead);
                var reference = ms.Cast<ObjectId>().Select(id => tr.GetObject(id, OpenMode.ForRead)).OfType<BlockReference>().Single();
                var grips = new GripDataCollection();
                GripResults.Add(grips);
                reference.GetGripPoints(grips, 1, 6, Vector3d.ZAxis, GetGripPointsFlags.GripPointsOnly);
                Assert(grips.Cast<GripData>().Any(g => g is RevisionButton && g.GetTooltip() == "Editar revisiones" && g.TriggerGrip),
                    "Custom editor grip was not created");
                Button=grips.Cast<GripData>().OfType<RevisionButton>().Single();
                ButtonEntity=reference.ObjectId;
                tr.Commit();
            }
            Log(root, "PASS custom grip and tooltip");
            Log(root, "SMOKE_DONE");
        }
        catch (System.Exception error) { Log(root, "FAIL SMOKE " + error); }
    }

    [CommandMethod("SINCAL_REV_CHECK_UNDO", CommandFlags.Session)]
    public static void CheckUndo()
    {
        var root = Root();
        try
        {
            var document = CadApplication.DocumentManager.MdiActiveDocument;
            var baseline = Before[document];
            var current=Read(document,baseline.Definition);
            Assert(current.integrity==baseline.Snapshot.integrity,"Undo changed FIELD links, styles or geometry");
            var cached=Cached(document,baseline.Definition);
            for(int c=0;c<6;c++)
            {
                var cell=current.tables[0].cells[0][c];
                if(cell.property is not null)
                    Assert(cached[c]==cell.text+"\n"+cell.text,"Visible FIELD result differs from DWGPROPS after Undo/REGEN");
            }
            Log(root,"UNDO_OBSERVED "+Path.GetFileName(document.Name)+" complete_restore="+RevisionTransfer.Matches(baseline.Snapshot,current));
            Log(root, "UNDO_DONE " + Path.GetFileName(document.Name));
        }
        catch (System.Exception error) { Log(root, "FAIL UNDO " + error); }
    }
}
