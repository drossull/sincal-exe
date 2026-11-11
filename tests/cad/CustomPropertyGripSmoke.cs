using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using Timer = System.Windows.Forms.Timer;
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

// Included only in TEST builds. All drawings belong to the hidden runner process.
public static class CustomPropertyGripSmoke
{
    private static readonly string[] Names = { "source", "target", "omitted", "fault", "readonly" };
    private static readonly Dictionary<Document, State> BeforeDialog = new Dictionary<Document, State>();
    private static Timer? timer;
    private static string root = "";
    private static bool inspected;

    private sealed class State
    {
        internal Dictionary<string, string> Properties = null!;
        internal string[] Standard = null!;
        internal string[] Codes = null!;
        internal string[] Evaluated = null!;
        internal string[] Displayed = null!;
    }

    private static string Root()
    {
        var folder = Path.GetDirectoryName(CadApplication.DocumentManager.MdiActiveDocument.Name)!;
        if (!Path.GetFileName(folder).StartsWith("sincal-revision-grip-native-", StringComparison.Ordinal))
            throw new InvalidOperationException("Only the runner's disposable fixtures are accepted.");
        return folder;
    }

    private static void Log(string text) => File.AppendAllText(Path.Combine(root, "native-result.txt"), text + Environment.NewLine);
    private static void Assert(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
    private static void Rejected(Action action, string message, bool logError = false)
    {
        try { action(); }
        catch (InvalidOperationException error)
        {
            if (logError) Log("FAULT_EXCEPTION " + error);
            return;
        }
        throw new InvalidOperationException(message);
    }
    private static Dictionary<string, string> Values() => new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
    {
        ["proyecto"] = "NUEVO", ["Vaciar"] = "", ["Nueva"] = "creada"
    };
    private static Dictionary<string, Document> Documents() => CadApplication.DocumentManager.Cast<Document>()
        .Where(d => Path.GetDirectoryName(d.Name) == root && Names.Contains(Path.GetFileNameWithoutExtension(d.Name)))
        .ToDictionary(d => Path.GetFileNameWithoutExtension(d.Name));

    private static State Read(Document document)
    {
        using (document.LockDocument())
        using (var transaction = document.Database.TransactionManager.StartTransaction())
        {
            var db = document.Database;
            var summary = db.SummaryInfo;
            var result = new State
            {
                Properties = CustomPropertyTransfer.Read(db),
                Standard = new[] { summary.Author, summary.Comments, summary.HyperlinkBase, summary.Keywords,
                    summary.RevisionNumber, summary.Subject, summary.Title }
            };
            var codes = new List<string>();
            var evaluated = new List<string>();
            var displayed = new List<string>();
            void ReadField(Entity entity, string text)
            {
                var field = (Field)transaction.GetObject(entity.GetField("Text"), OpenMode.ForRead);
                codes.Add(field.GetFieldCode());
                evaluated.Add(field.GetFieldCode(FieldCodeFlags.EvaluatedText));
                displayed.Add(text);
            }
            var blocks = (BlockTable)transaction.GetObject(db.BlockTableId, OpenMode.ForRead);
            var model = (BlockTableRecord)transaction.GetObject(blocks[BlockTableRecord.ModelSpace], OpenMode.ForRead);
            foreach (ObjectId id in model)
            {
                var entity = transaction.GetObject(id, OpenMode.ForRead);
                if (entity is MText text) ReadField(text, text.Text);
                if (entity is BlockReference reference)
                    foreach (ObjectId attributeId in reference.AttributeCollection)
                    {
                        var attribute = (AttributeReference)transaction.GetObject(attributeId, OpenMode.ForRead);
                        ReadField(attribute, attribute.TextString);
                    }
            }
            result.Codes = codes.ToArray(); result.Evaluated = evaluated.ToArray(); result.Displayed = displayed.ToArray();
            transaction.Commit();
            return result;
        }
    }

    private static bool SameProperties(IReadOnlyDictionary<string, string> left, IReadOnlyDictionary<string, string> right) =>
        left.Count == right.Count && left.All(pair => right.TryGetValue(pair.Key, out var value) && pair.Value == value);
    private static bool Same(State left, State right) => SameProperties(left.Properties, right.Properties)
        && left.Standard.SequenceEqual(right.Standard) && left.Codes.SequenceEqual(right.Codes)
        && left.Evaluated.SequenceEqual(right.Evaluated) && left.Displayed.SequenceEqual(right.Displayed);

    private static void AddField(Database db, Transaction transaction, Entity entity, string key)
    {
        var field = new Field("%<\\AcVar CustomDP." + key + ">%", true)
        {
            EvaluationOption = FieldEvaluationOptions.Automatic
        };
        entity.SetField("Text", field);
        transaction.AddNewlyCreatedDBObject(field, true);
        foreach (var child in field.GetChildrenIds())
            ((Field)transaction.GetObject(child, OpenMode.ForWrite)).Evaluate((int)FieldEvaluationContext.Demand, db);
        field.Evaluate((int)FieldEvaluationContext.Demand, db);
    }

    [CommandMethod("SINCAL_PROPS_FIXTURES", CommandFlags.Session)]
    public static void Fixtures()
    {
        root = Root();
        Log("FIXTURES_STARTED");
        var previousWorking = HostApplicationServices.WorkingDatabase;
        try
        {
            Assert(Path.GetFileName(CadApplication.DocumentManager.MdiActiveDocument.Name) == "seed.dwg", "Wrong fixture source");
            foreach (var name in Names)
            {
                using var db = new Database(true, true);
                HostApplicationServices.WorkingDatabase = db;
                var key = name == "target" ? "PROYECTO" : "PrOyEcTo";
                var info = new DatabaseSummaryInfoBuilder { Author = "AUTOR", Title = "TITULO", Subject = "ASUNTO",
                    Comments = "COMENTARIOS", Keywords = "CLAVES", HyperlinkBase = "https://example.invalid/", RevisionNumber = "7" };
                info.CustomPropertyTable[key] = name.ToUpperInvariant();
                info.CustomPropertyTable["Vaciar"] = "BORRAR";
                info.CustomPropertyTable["Preservar"] = name;
                db.SummaryInfo = info.ToDatabaseSummaryInfo();
                using (var transaction = db.TransactionManager.StartTransaction())
                {
                    var blocks = (BlockTable)transaction.GetObject(db.BlockTableId, OpenMode.ForRead);
                    var model = (BlockTableRecord)transaction.GetObject(blocks[BlockTableRecord.ModelSpace], OpenMode.ForWrite);
                    var text = new MText { Contents = "INITIAL", TextHeight = 1, Location = Point3d.Origin };
                    model.AppendEntity(text); transaction.AddNewlyCreatedDBObject(text, true);
                    AddField(db, transaction, text, key);
                    blocks.UpgradeOpen();
                    var definition = new BlockTableRecord { Name = "SMOKE_FIELDS" };
                    blocks.Add(definition); transaction.AddNewlyCreatedDBObject(definition, true);
                    var attributeDefinition = new AttributeDefinition { Tag = "PROYECTO", TextString = "INITIAL", Height = 1 };
                    definition.AppendEntity(attributeDefinition); transaction.AddNewlyCreatedDBObject(attributeDefinition, true);
                    var reference = new BlockReference(new Point3d(0, 3, 0), definition.ObjectId);
                    model.AppendEntity(reference); transaction.AddNewlyCreatedDBObject(reference, true);
                    var attribute = new AttributeReference();
                    attribute.SetAttributeFromBlock(attributeDefinition, reference.BlockTransform);
                    reference.AttributeCollection.AppendAttribute(attribute); transaction.AddNewlyCreatedDBObject(attribute, true);
                    AddField(db, transaction, attribute, key);
                    transaction.Commit();
                }
                db.SaveAs(Path.Combine(root, name + ".dwg"), DwgVersion.Current);
                HostApplicationServices.WorkingDatabase = previousWorking;
            }
            Log("FIXTURES_READY");
        }
        catch (System.Exception error) { Log("FAIL PROPS_FIXTURES " + error); }
        finally { HostApplicationServices.WorkingDatabase = previousWorking; }
    }

    [CommandMethod("SINCAL_PROPS_SMOKE", CommandFlags.Session)]
    public static void Run()
    {
        root = Root();
        try
        {
            var documents = Documents();
            Assert(documents.Count == Names.Length && documents["readonly"].IsReadOnly, "Readonly fixture is missing");
            var before = documents.ToDictionary(pair => pair.Key, pair => Read(pair.Value));
            foreach (var pair in before)
                Assert(pair.Value.Codes.Length == 2 && pair.Value.Evaluated.All(v => v == pair.Key.ToUpperInvariant())
                    && pair.Value.Displayed.All(v => v == pair.Key.ToUpperInvariant()), "Fixture Fields are not evaluated: " + pair.Key);
            Log("PASS fixtures have evaluated MText and attribute Fields outside any table");

            var sourcePlan = CustomPropertyTransfer.Plan(before["source"].Properties, Values());
            Assert(sourcePlan.Keys.Contains("PrOyEcTo") && sourcePlan.Count == 3, "Plan did not preserve spelling/create missing/explicit blank");
            Assert(CustomPropertyTransfer.Plan(before["source"].Properties,
                new Dictionary<string, string> { ["preservar"] = "source" }).Count == 0, "Unchanged value became an edit");
            Assert(CustomPropertyTransfer.Plan(before["source"].Properties,
                new Dictionary<string, string> { ["Ruta"] = @"C:\Obra\{Plano}/é" }).Count == 1, "Normal path rejected");
            Rejected(() => CustomPropertyTransfer.Plan(before["source"].Properties,
                new Dictionary<string, string> { ["Ruta"] = "%<injection>%" }), "Field injection accepted");
            Log("PASS case-insensitive plans retain spelling, explicit blanks and ordinary paths");

            foreach (var name in new[] { "source", "target" })
            {
                var document = documents[name];
                var changes = CustomPropertyTransfer.Plan(before[name].Properties, Values());
                var notice = CustomPropertyTransfer.Apply(document, before[name].Properties, changes);
                if (notice != null) Log("NOTICE " + name + ": " + notice);
                var actual = Read(document);
                // Installed startup may add its catalog on document open. Preserve
                // the entire observed baseline, not only the three fixture keys.
                var expected = new Dictionary<string, string>(before[name].Properties, StringComparer.OrdinalIgnoreCase);
                foreach (var change in changes) expected[change.Key] = change.Value;
                Assert(SameProperties(expected, actual.Properties), "Selected properties differ: " + name
                    + "; expected=" + string.Join("; ", expected.Select(p => p.Key + "=" + p.Value))
                    + "; actual=" + string.Join("; ", actual.Properties.Select(p => p.Key + "=" + p.Value)));
                Assert(actual.Properties.Keys.Single(k => k.Equals("proyecto", StringComparison.OrdinalIgnoreCase))
                    == (name == "target" ? "PROYECTO" : "PrOyEcTo"), "Property spelling changed or duplicate key added");
                Assert(actual.Standard.SequenceEqual(before[name].Standard) && actual.Codes.SequenceEqual(before[name].Codes), "Standard metadata or Field expressions changed");
                Assert(actual.Evaluated.All(v => v == "NUEVO") && actual.Displayed.All(v => v == "NUEVO"), "General Fields remain stale: " + name);
            }
            Assert(Same(before["omitted"], Read(documents["omitted"])), "Omitted drawing changed");
            Rejected(() => CustomPropertyTransfer.Apply(documents["source"], before["source"].Properties, sourcePlan), "Stale snapshot accepted");
            Rejected(() => CustomPropertyTransfer.Apply(documents["readonly"], before["readonly"].Properties,
                CustomPropertyTransfer.Plan(before["readonly"].Properties, Values())), "Readonly drawing accepted");
            Assert(Same(before["readonly"], Read(documents["readonly"])), "Readonly drawing changed");
            Log("PASS selected destinations, missing keys, explicit blank, preserved metadata/expressions, omitted/stale/readonly protection");

            var fault = documents["fault"];
            var injected = false;
            CustomPropertyTransfer.TestAfterApply = () =>
            {
                var changed = Read(fault);
                Assert(changed.Properties["Proyecto"] == "NUEVO" && changed.Evaluated.All(v => v == "NUEVO"), "Failure was injected before actual mutations");
                injected = true;
                throw new InvalidOperationException("Injected failure after custom properties and Field refresh");
            };
            try
            {
                Rejected(() => CustomPropertyTransfer.Apply(fault, before["fault"].Properties,
                    CustomPropertyTransfer.Plan(before["fault"].Properties, Values())), "Injected failure was swallowed", true);
            }
            finally { CustomPropertyTransfer.TestAfterApply = null; }
            var restored = Read(fault);
            Assert(injected && Same(before["fault"], restored), "Failure did not roll back metadata and evaluated Fields"
                + "; hook=" + injected
                + "; properties=" + SameProperties(before["fault"].Properties, restored.Properties)
                + "; standard=" + before["fault"].Standard.SequenceEqual(restored.Standard)
                + "; expressions=" + before["fault"].Codes.SequenceEqual(restored.Codes)
                + "; evaluated expected=" + string.Join("|", before["fault"].Evaluated)
                + " actual=" + string.Join("|", restored.Evaluated)
                + "; displayed expected=" + string.Join("|", before["fault"].Displayed)
                + " actual=" + string.Join("|", restored.Displayed));
            Log("PASS rollback restores DWGPROPS, standard metadata and cached Field values");
            Log("PROPS_SMOKE_DONE");
        }
        catch (System.Exception error) { Log("FAIL PROPS " + error); }
        finally { CustomPropertyTransfer.TestAfterApply = null; }
    }

    private static IEnumerable<Control> Descendants(Control parent)
    {
        foreach (Control child in parent.Controls)
        {
            yield return child;
            foreach (var descendant in Descendants(child)) yield return descendant;
        }
    }

    [CommandMethod("SINCAL_PROPS_DIALOG_SMOKE", CommandFlags.Session)]
    public static void Dialog()
    {
        root = Root();
        var source = CadApplication.DocumentManager.MdiActiveDocument;
        try
        {
            Assert(Path.GetFileName(source.Name) == "source.dwg", "Wrong dialog source");
            BeforeDialog.Clear();
            foreach (var document in Documents().Values) BeforeDialog.Add(document, Read(document));
            inspected = false;
            timer?.Dispose();
            timer = new Timer { Interval = 100 };
            var started = DateTime.UtcNow;
            timer.Tick += (_, _) =>
            {
                var dialog = System.Windows.Forms.Application.OpenForms.Cast<Form>().OfType<RevisionDialog>().FirstOrDefault();
                if (dialog == null)
                {
                    if ((DateTime.UtcNow - started).TotalSeconds > 30) { timer!.Stop(); Log("FAIL PROPS_DIALOG did not open"); }
                    return;
                }
                timer!.Stop();
                try
                {
                    var controls = Descendants(dialog).ToArray();
                    var tabs = controls.OfType<TabControl>().Single(t => t.AccessibleName == "Secciones del editor");
                    Assert(tabs.SelectedIndex == 1 && !tabs.TabPages[0].Enabled, "PROPS-EDIT did not select properties without a vignette");
                    var properties = controls.OfType<DataGridView>().Single(g => g.AccessibleName == "Propiedades personalizadas");
                    var drawings = controls.OfType<DataGridView>().Single(g => g.AccessibleName == "Dibujos abiertos donde aplicar propiedades");
                    Assert(properties.Rows.Cast<DataGridViewRow>().All(r => !Equals(r.Cells[0].Value, true)), "Properties were selected implicitly");
                    foreach (var pair in BeforeDialog[source].Properties)
                    {
                        var row = properties.Rows.Cast<DataGridViewRow>().Single(r => Convert.ToString(r.Cells[1].Value) == pair.Key);
                        Assert(Convert.ToString(row.Cells[2].Value) == pair.Value && row.Cells[1].ReadOnly, "Property grid differs from DWGPROPS");
                    }
                    Assert(drawings.Rows.Count == CadApplication.DocumentManager.Count, "Open properties destination list is incomplete");
                    foreach (DataGridViewRow row in drawings.Rows)
                        Assert(Equals(row.Cells[0].Value, true) == (Convert.ToString(row.Cells[1].Value) == source.Name), "Unexpected selected properties destination");
                    var blank = properties.Rows.Cast<DataGridViewRow>().Single(r => Convert.ToString(r.Cells[1].Value) == "Vaciar");
                    blank.Cells[2].Value = "CANCELAR";
                    Assert(!Equals(blank.Cells[0].Value, true), "Editing a value implicitly selected it");
                    blank.Cells[0].Value = true;
                    var target = drawings.Rows.Cast<DataGridViewRow>().Single(r => Path.GetFileName(Convert.ToString(r.Cells[1].Value)) == "target.dwg");
                    target.Cells[0].Value = true;
                    var readOnly = drawings.Rows.Cast<DataGridViewRow>().Single(r => Path.GetFileName(Convert.ToString(r.Cells[1].Value)) == "readonly.dwg");
                    Assert(readOnly.ReadOnly && !Equals(readOnly.Cells[0].Value, true), "Readonly target was selectable");
                    inspected = true;
                    Log("PASS PROPS-EDIT wrapper opens properties without vignette; tabs, values and explicit selection inspected");
                }
                catch (System.Exception error) { Log("FAIL PROPS_DIALOG " + error); }
                finally
                {
                    dialog.DialogResult = DialogResult.Cancel;
                    dialog.Close();
                    source.SendStringToExecute("SINCAL_PROPS_DIALOG_CHECK ", true, false, false);
                }
            };
            timer.Start();
            source.SendStringToExecute("PROPS-EDIT\n", true, false, false);
        }
        catch (System.Exception error) { timer?.Stop(); Log("FAIL PROPS_DIALOG " + error); }
    }

    [CommandMethod("SINCAL_PROPS_DIALOG_CHECK", CommandFlags.Session)]
    public static void CheckDialog()
    {
        try
        {
            Assert(inspected, "Properties dialog was not inspected");
            foreach (var pair in BeforeDialog) Assert(Same(pair.Value, Read(pair.Key)), "Cancel changed drawing " + pair.Key.Name);
            Log("PASS properties dialog Cancel preserved every drawing and Field");
            Log("PROPS_DIALOG_DONE");
        }
        catch (System.Exception error) { Log("FAIL PROPS_DIALOG " + error); }
        finally { timer?.Dispose(); timer = null; BeforeDialog.Clear(); }
    }
}
