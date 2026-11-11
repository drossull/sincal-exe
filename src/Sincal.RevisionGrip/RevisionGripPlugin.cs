using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows.Forms;
using Sincal.DwgProps;
#if ZWCAD
using ZwSoft.ZwCAD.ApplicationServices;
using ZwSoft.ZwCAD.DatabaseServices;
using ZwSoft.ZwCAD.EditorInput;
using ZwSoft.ZwCAD.Geometry;
using ZwSoft.ZwCAD.Runtime;
using CadApplication = ZwSoft.ZwCAD.ApplicationServices.Application;
#else
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using CadApplication = Autodesk.AutoCAD.ApplicationServices.Application;
#endif

namespace Sincal.RevisionGrip;

public sealed class RevisionGripPlugin : IExtensionApplication
{
    private static readonly RevisionGrips Grips = new RevisionGrips();
    private static readonly Dictionary<Document, ObjectId> Pending = new Dictionary<Document, ObjectId>();
    private static bool registered;

    public void Initialize()
    {
        if (registered) return;
        Grips.SetCustomFilter();
        Overrule.AddOverrule(RXObject.GetClass(typeof(BlockReference)), Grips, false);
        Overrule.Overruling = true;
        registered = true;
    }

    public void Terminate()
    {
        if (registered) Overrule.RemoveOverrule(RXObject.GetClass(typeof(BlockReference)), Grips);
        registered = false;
        Pending.Clear();
    }

    internal static ObjectId Definition(BlockReference reference) =>
        reference.IsDynamicBlock ? reference.DynamicBlockTableRecord : reference.BlockTableRecord;

    internal static bool IsVignette(BlockTableRecord block) => !block.IsFromExternalReference
        && (block.Name.StartsWith("VIÑETA", StringComparison.OrdinalIgnoreCase)
            || block.Name.StartsWith("VINETA", StringComparison.OrdinalIgnoreCase));

#if REVISION_GRIP_TESTS
    internal static void TestSelect(ObjectId id) => Pending[CadApplication.DocumentManager.MdiActiveDocument] = id;
#endif

    internal static void Queue(ObjectId id)
    {
        var document = CadApplication.DocumentManager.MdiActiveDocument;
        if (document == null || id.IsNull || id.Database != document.Database || Pending.ContainsKey(document)) return;
        Pending[document] = id;
        try { document.SendStringToExecute("SINCAL_REV_EDIT ", true, false, false); }
        catch { Pending.Remove(document); throw; }
    }

    private sealed class Destination
    {
        internal Document Document = null!;
        internal TargetChoice Choice = null!;
        internal RevisionEditor.Snapshot? Snapshot;
        internal ObjectId? Definition;
        internal TargetChoice PropertyChoice = null!;
        internal Dictionary<string, string>? Properties;
    }

    [CommandMethod("SINCAL_REV_EDIT", CommandFlags.Session)]
    public static void Edit() => Open(false);

    [CommandMethod("SINCAL_PROPS_EDIT", CommandFlags.Session)]
    public static void EditProperties() => Open(true);

    private static void Open(bool propertiesFirst)
    {
        var current = CadApplication.DocumentManager.MdiActiveDocument;
        if (current == null) return;
        try
        {
            ObjectId? definition = null;
            RevisionEditor.Snapshot? sourceSnapshot = null;
            if (!propertiesFirst)
            {
                ObjectId selected;
                if (Pending.TryGetValue(current, out selected)) Pending.Remove(current);
                else
                {
                    var options = new PromptEntityOptions("\nSelecciona la viñeta cuyo cuadro quieres editar: ");
                    options.SetRejectMessage("\nSelecciona una inserción de viñeta.");
                    options.AddAllowedClass(typeof(BlockReference), true);
                    var selection = current.Editor.GetEntity(options);
                    if (selection.Status != PromptStatus.OK) return;
                    selected = selection.ObjectId;
                }
                using (current.LockDocument())
                using (var transaction = current.Database.TransactionManager.StartTransaction())
                {
                    var reference = (BlockReference)transaction.GetObject(selected, OpenMode.ForRead);
                    definition = Definition(reference);
                    if (!IsVignette((BlockTableRecord)transaction.GetObject(definition.Value, OpenMode.ForRead)))
                        throw new InvalidOperationException("Selecciona un bloque VIÑETA o VINETA del dibujo, no una referencia externa.");
                    sourceSnapshot = RevisionEditor.Read(current.Database, definition);
                    transaction.Commit();
                }
                if (sourceSnapshot.tables.Length != 1)
                    throw new InvalidOperationException("La viñeta debe contener un único cuadro de revisiones compatible.");
            }
            var source = sourceSnapshot?.tables[0];
            var values = source?.cells.Select(row => row.Select(cell => cell.text).ToArray()).ToArray();
            Dictionary<string, string> properties;
            using (current.LockDocument()) properties = CustomPropertyTransfer.Read(current.Database);
            var destinations = new List<Destination>();
            foreach (Document document in CadApplication.DocumentManager)
            {
                var target = new Destination { Document = document,
                    Choice = new TargetChoice { Name = document.Name, Selected = document == current },
                    PropertyChoice = new TargetChoice { Name = document.Name, Selected = document == current },
                    Definition = document == current ? definition : null };
                try
                {
                    if (document.IsReadOnly) throw new InvalidOperationException("Dibujo de solo lectura.");
                    using (document.LockDocument()) target.Properties = CustomPropertyTransfer.Read(document.Database);
                    target.PropertyChoice.Available = true;
                    target.PropertyChoice.Detail = document == current ? "Dibujo actual · valores de origen" : "Propiedades del dibujo";
                }
                catch (System.Exception error)
                {
                    target.PropertyChoice.Selected = false;
                    target.PropertyChoice.Detail = error.Message;
                }
                try
                {
                    if (source == null) throw new InvalidOperationException("Selecciona una viñeta con REV-EDIT para editar revisiones.");
                    if (document.IsReadOnly) throw new InvalidOperationException("Dibujo de solo lectura.");
                    using (document.LockDocument()) target.Snapshot = document == current
                        ? sourceSnapshot : RevisionEditor.Read(document.Database);
                    RevisionTransfer.Plan(source, values!, target.Snapshot!);
                    target.Choice.Available = true;
                    target.Choice.Detail = document == current ? "Viñeta seleccionada" : string.Join(", ", target.Snapshot!.tables.Select(t => t.block).Distinct());
                }
                catch (System.Exception error)
                {
                    target.Choice.Available = false;
                    target.Choice.Selected = false;
                    target.Choice.Detail = error.Message;
                }
                destinations.Add(target);
            }
            using (var dialog = new RevisionDialog(source, destinations.Select(d => d.Choice).ToList(),
                properties, destinations.Select(d => d.PropertyChoice).ToList(), propertiesFirst))
            {
                if (CadApplication.ShowModalDialog(dialog) != DialogResult.OK) return;
                if (dialog.ApplyProperties)
                {
                    var propertyPlans = destinations.Where(d => d.PropertyChoice.Selected).Select(d => new
                    {
                        Target = d, Changes = CustomPropertyTransfer.Plan(d.Properties!, dialog.PropertyValues)
                    }).ToArray();
                    var propertyResults = new List<string>();
                    foreach (var plan in propertyPlans)
                    {
                        var target = plan.Target;
                        try
                        {
                            if (!CadApplication.DocumentManager.Cast<Document>().Contains(target.Document))
                                throw new InvalidOperationException("El dibujo se cerró.");
                            var notice = CustomPropertyTransfer.Apply(target.Document, target.Properties!, plan.Changes);
                            propertyResults.Add($"{System.IO.Path.GetFileName(target.Document.Name)}: {(notice ?? (plan.Changes.Count == 0 ? "sin cambios" : "propiedades actualizadas"))}");
                        }
                        catch (System.Exception error) { propertyResults.Add($"{System.IO.Path.GetFileName(target.PropertyChoice.Name)}: no aplicado · {error.Message}"); }
                    }
                    CadApplication.ShowAlertDialog(string.Join("\n", propertyResults) + "\n\nLos dibujos no se guardaron automáticamente.");
                    return;
                }
                var selectedTargets = destinations.Where(d => d.Choice.Selected).ToArray();
                // Validate every destination before applying the first drawing.
                var plans = selectedTargets.Select(d => new { Target = d,
                    Changes = RevisionTransfer.Plan(source!, dialog.Values, d.Snapshot!) }).ToArray();
                var results = new List<string>();
                foreach (var plan in plans)
                {
                    var target = plan.Target;
                    try
                    {
                        if (!CadApplication.DocumentManager.Cast<Document>().Contains(target.Document))
                            throw new InvalidOperationException("El dibujo se cerró.");
                        var notice = RevisionTransfer.Apply(target.Document, target.Snapshot!, plan.Changes, target.Definition);
                        results.Add($"{System.IO.Path.GetFileName(target.Document.Name)}: {(notice ?? (plan.Changes.Length == 0 ? "sin cambios" : "actualizado"))}");
                    }
                    catch (System.Exception error) { results.Add($"{System.IO.Path.GetFileName(target.Choice.Name)}: no aplicado · {error.Message}"); }
                }
                CadApplication.ShowAlertDialog(string.Join("\n", results) + "\n\nLos dibujos no se guardaron automáticamente.");
            }
        }
        catch (System.Exception error)
        {
            string command = propertiesFirst ? "PROPS-EDIT" : "REV-EDIT";
            current.Editor.WriteMessage("\n" + command + ": " + error.Message);
            CadApplication.ShowAlertDialog(command + ": " + error.Message);
        }
    }
}

internal sealed class RevisionGrips : GripOverrule
{
    private static DBObject OpenForRead(ObjectId id)
    {
        // Grip callbacks can run during UNDO/REDO. A regular transaction here
        // can invalidate CAD's undo filer; pair these direct reads with using.
#pragma warning disable CS0618
        return id.Open(OpenMode.ForRead);
#pragma warning restore CS0618
    }

    public override bool IsApplicable(RXObject subject)
    {
        if (subject is not BlockReference reference || reference.Database == null) return false;
        try
        {
            using var block = (BlockTableRecord)OpenForRead(RevisionGripPlugin.Definition(reference));
            return RevisionGripPlugin.IsVignette(block);
        }
        catch { return false; }
    }

    public override void GetGripPoints(Entity entity, GripDataCollection grips, double viewSize,
        int gripSize, Vector3d viewDirection, GetGripPointsFlags flags)
    {
        base.GetGripPoints(entity, grips, viewSize, gripSize, viewDirection, flags);
        if (entity is not BlockReference reference) return;
        try
        {
            using (var block = (BlockTableRecord)OpenForRead(RevisionGripPlugin.Definition(reference)))
            {
                if (!RevisionGripPlugin.IsVignette(block)) return;
                foreach (ObjectId id in block)
                {
                    using var candidate = OpenForRead(id);
                    if (candidate is not Table table || table.Columns.Count != 6 || table.Rows.Count < 1) continue;
                    if (table.Cells[0, 0].Contents.Count != 1) continue;
                    var fieldId = table.Cells[0, 0].Contents[0].FieldId;
                    if (fieldId.IsNull) continue;
                    using var field = (Field)OpenForRead(fieldId);
                    var code = field.GetFieldCode();
                    if (!System.Text.RegularExpressions.Regex.IsMatch(code, @"^\\AcVar CustomDP\.Revision(?:\s|$)", System.Text.RegularExpressions.RegexOptions.IgnoreCase)) continue;
                    var extents = table.GeometricExtents;
                    var gap = Math.Max(table.Rows[0].Height, 2);
                    var point = new Point3d(extents.MinPoint.X - gap, extents.MaxPoint.Y - gap * .5, extents.MinPoint.Z);
                    grips.Add(new RevisionButton { GripPoint = point.TransformBy(reference.BlockTransform), TriggerGrip = true });
                    return;
                }
            }
        }
        // A grip must not interrupt drawing or selection if a proxy is unsupported.
        catch { }
    }
}

internal sealed class RevisionButton : GripData
{
    public override string GetTooltip() => "Editar revisiones";
    public override ReturnValue OnHotGrip(ObjectId entityId, Context context)
    {
        RevisionGripPlugin.Queue(entityId);
        return ReturnValue.GripHotToWarm;
    }
}
