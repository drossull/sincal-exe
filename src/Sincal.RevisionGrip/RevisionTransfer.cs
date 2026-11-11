using System;
using System.Collections.Generic;
using System.Linq;
using Sincal.DwgProps;
#if ZWCAD
using ZwSoft.ZwCAD.ApplicationServices;
using ZwSoft.ZwCAD.DatabaseServices;
#else
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
#endif

namespace Sincal.RevisionGrip;

internal static class RevisionTransfer
{
#if REVISION_GRIP_TESTS
    internal static Action? TestAfterApply;
#endif
    internal static bool IsHeader(RevisionEditor.Cell[] row) => row.Length == 6
        && new[] { "VER", "REV", "REVISIÓN", "REVISION" }.Contains(row[0].text.Trim().ToUpperInvariant())
        && row[1].text.Trim().Equals("FECHA", StringComparison.OrdinalIgnoreCase);

    internal static RevisionEditor.Change[] Plan(RevisionEditor.Sheet source, string[][] values,
        RevisionEditor.Snapshot target)
    {
        if (values.Length != source.cells.Length || values.Any(r => r.Length != 6))
            throw new InvalidOperationException("La tabla editada tiene otro tamaño.");
        var changes = new List<RevisionEditor.Change>();
        foreach (var sheet in target.tables)
        {
            if (sheet.cells.Length != values.Length || sheet.cells.Any(r => r.Length != 6))
                throw new InvalidOperationException("El cuadro de destino tiene otra cantidad de filas o columnas.");
            for (int r = 0; r < values.Length; r++)
            {
                if (IsHeader(source.cells[r]) != IsHeader(sheet.cells[r]))
                    throw new InvalidOperationException("Los encabezados del cuadro de destino no coinciden.");
                for (int c = 0; c < 6; c++)
                {
                    var cell = sheet.cells[r][c];
                    if (IsHeader(source.cells[r])) continue;
                    var value = values[r][c];
                    if (value == cell.text) continue;
                    if (!cell.editable)
                        throw new InvalidOperationException($"Fila {r + 1}, columna {c + 1}: FIELD protegido en {sheet.block}.");
                    changes.Add(new RevisionEditor.Change(sheet.id, r, c, value));
                }
            }
        }
        if (changes.Count != 0) RevisionEditor.DesiredProperties(target, changes.ToArray());
        return changes.ToArray();
    }

    internal static bool Matches(RevisionEditor.Snapshot left, RevisionEditor.Snapshot right) =>
        left.integrity == right.integrity && left.tables.Length == right.tables.Length
        && left.tables.Zip(right.tables, (a, b) => a.id == b.id
            && a.cells.SelectMany(r => r).SequenceEqual(b.cells.SelectMany(r => r))).All(v => v);

    internal static string? Apply(Document document, RevisionEditor.Snapshot expected,
        RevisionEditor.Change[] changes, ObjectId? definition = null)
    {
        using (document.LockDocument())
        {
            var db = document.Database;
            var previousWorking = HostApplicationServices.WorkingDatabase;
            var previousSummary = db.SummaryInfo;
            try
            {
                HostApplicationServices.WorkingDatabase = db;
                if (!Matches(expected, RevisionEditor.Read(db, definition)))
                    throw new InvalidOperationException("El cuadro cambió desde que se abrió el editor. Vuelve a leerlo.");
                if (changes.Length == 0) return null;
                #if ZWCAD
                dynamic automation = document.ZcadDocument;
                #else
                dynamic automation = document.GetAcadDocument();
                #endif
                automation.StartUndoMark();
                try
                {
                    using (var transaction = db.TransactionManager.StartTransaction())
                    {
                        try
                        {
                            RevisionEditor.Apply(db, expected, changes, definition);
#if REVISION_GRIP_TESTS
                            TestAfterApply?.Invoke();
#endif
                            RevisionEditor.Verify(db, expected, changes, definition);
                            transaction.Commit();
                        }
                        catch
                        {
                            transaction.Abort();
                            // SummaryInfo is outside the entity transaction on both CAD engines.
                            db.SummaryInfo = previousSummary;
                            throw;
                        }
                    }
                }
                finally { automation.EndUndoMark(); }
                // Session commands can update inactive drawings; regenerate in their
                // document command context once this command releases its locks.
                try { document.SendStringToExecute("_.REGEN ", false, false, false); }
                catch (System.Exception error) { return "Datos actualizados; ejecuta REGEN para refrescar la vista: " + error.Message; }
                return null;
            }
            finally { HostApplicationServices.WorkingDatabase = previousWorking; }
        }
    }
}
