using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
#if ZWCAD
using ZwSoft.ZwCAD.ApplicationServices;
using ZwSoft.ZwCAD.DatabaseServices;
#else
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
#endif

namespace Sincal.RevisionGrip;

internal static class CustomPropertyTransfer
{
    internal const int MaxValueLength = 1000;
#if REVISION_GRIP_TESTS
    internal static Action? TestAfterApply;
#endif

    internal static Dictionary<string, string> Read(Database database)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (DictionaryEntry item in new DatabaseSummaryInfoBuilder(database.SummaryInfo).CustomPropertyTable)
        {
            var key = (string)item.Key;
            if (result.ContainsKey(key))
                throw new InvalidOperationException("Hay propiedades personalizadas repetidas con distintas mayúsculas: " + key + ". Repara sus nombres antes de editar.");
            result.Add(key, (string?)item.Value ?? "");
        }
        return result;
    }

    internal static Dictionary<string, string> Plan(IReadOnlyDictionary<string, string> expected,
        IReadOnlyDictionary<string, string> values)
    {
        var originals = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pair in expected)
        {
            if (originals.ContainsKey(pair.Key))
                throw new InvalidOperationException("La lectura contiene nombres de propiedades repetidos: " + pair.Key);
            originals.Add(pair.Key, pair.Value);
        }
        var changes = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pair in values)
        {
            if (!seen.Add(pair.Key))
                throw new InvalidOperationException("La selección contiene nombres de propiedades repetidos: " + pair.Key);
            bool exists = originals.TryGetValue(pair.Key, out var previous);
            // Existing values that are not changed may predate the editor's input limits.
            if (exists && previous == pair.Value) continue;
            if (string.IsNullOrWhiteSpace(pair.Key) || pair.Key.Length > 255 || pair.Key != pair.Key.Trim()
                || pair.Key.Any(char.IsControl))
                throw new InvalidOperationException("El nombre de la propiedad no es válido.");
            if (pair.Value == null || pair.Value.Length > MaxValueLength || pair.Value.Any(char.IsControl)
                || pair.Value.Contains("%<"))
                throw new InvalidOperationException("Propiedad " + pair.Key + ": usa texto de hasta " + MaxValueLength + " caracteres, sin controles ni códigos de Field.");
            string key = exists ? originals.Keys.First(name => name.Equals(pair.Key, StringComparison.OrdinalIgnoreCase)) : pair.Key;
            changes.Add(key, pair.Value);
        }
        return changes;
    }

    private static bool Matches(IReadOnlyDictionary<string, string> left, IReadOnlyDictionary<string, string> right) =>
        left.Count == right.Count && left.OrderBy(pair => pair.Key, StringComparer.Ordinal)
            .SequenceEqual(right.OrderBy(pair => pair.Key, StringComparer.Ordinal));

    private static string[] StandardProperties(DatabaseSummaryInfo info) => new[]
    {
        info.Author, info.Comments, info.HyperlinkBase, info.Keywords, info.LastSavedBy,
        info.RevisionNumber, info.Subject, info.Title
    };

    private static DatabaseSummaryInfo BuildSummary(string[] standard, IReadOnlyDictionary<string, string> properties)
    {
        // The CAD copy constructor aliases the custom-property collection.
        // Rebuild from managed snapshots so neither write can mutate its backup.
        var builder = new DatabaseSummaryInfoBuilder
        {
            Author = standard[0], Comments = standard[1], HyperlinkBase = standard[2],
            Keywords = standard[3], LastSavedBy = standard[4], RevisionNumber = standard[5],
            Subject = standard[6], Title = standard[7]
        };
        foreach (var pair in properties) builder.CustomPropertyTable.Add(pair.Key, pair.Value);
        return builder.ToDatabaseSummaryInfo();
    }

    private static FieldEvaluationResult RefreshFields(Database database) =>
#if ZWCAD
        database.EvaluateFields(FieldEvaluationContext.Demand);
#else
        database.EvaluateFields(FieldEvaluationContext.Preview);
#endif

    internal static string? Apply(Document document, IReadOnlyDictionary<string, string> expected,
        IReadOnlyDictionary<string, string> changes)
    {
        if (document.IsReadOnly) throw new InvalidOperationException("Dibujo de solo lectura.");
        using (document.LockDocument())
        {
            var database = document.Database;
            var previousWorking = HostApplicationServices.WorkingDatabase;
            try
            {
                HostApplicationServices.WorkingDatabase = database;
                var current = Read(database);
                if (!Matches(expected, current))
                    throw new InvalidOperationException("Las propiedades cambiaron desde que se abrió el editor. Vuelve a leerlas.");
                var planned = Plan(current, changes);
                if (planned.Count == 0) return null;
                var desired = new Dictionary<string, string>(current, StringComparer.OrdinalIgnoreCase);
                foreach (var pair in planned) desired[pair.Key] = pair.Value;
                var previousStandard = StandardProperties(database.SummaryInfo);
                string? notice = null;
                try
                {
                    using (var transaction = database.TransactionManager.StartTransaction())
                    {
                        database.SummaryInfo = BuildSummary(previousStandard, desired);
                        // The native field engine covers annotations throughout the drawing,
                        // including attributes and MTEXT outside the revision table.
                        var evaluation = RefreshFields(database);
                        if (evaluation.Evaluated < evaluation.Found)
                            notice = "Propiedades actualizadas; algunos Fields del dibujo no se evaluaron. Revisa los campos pendientes.";
#if REVISION_GRIP_TESTS
                        TestAfterApply?.Invoke();
#endif
                        if (!Matches(desired, Read(database))
                            || !previousStandard.SequenceEqual(StandardProperties(database.SummaryInfo)))
                            throw new InvalidOperationException("Cambió una propiedad ajena a la selección. No se aplicaron los cambios.");
                        transaction.Commit();
                    }
                }
                catch (System.Exception originalError)
                {
                    try
                    {
                        // The disposed transaction restores entities, but SummaryInfo and
                        // native Field caches need the previous properties restored explicitly.
                        database.SummaryInfo = BuildSummary(previousStandard, current);
                        RefreshFields(database);
                        if (!Matches(current, Read(database))
                            || !previousStandard.SequenceEqual(StandardProperties(database.SummaryInfo)))
                            throw new InvalidOperationException("Las propiedades restauradas no coinciden con la lectura anterior.");
                    }
                    catch (System.Exception recoveryError)
                    {
                        throw new InvalidOperationException("La edición falló: " + originalError.Message
                            + " No se pudo completar la recuperación de las propiedades y sus Fields: " + recoveryError.Message,
                            new AggregateException(originalError, recoveryError));
                    }
                    finally
                    {
                        try { document.SendStringToExecute("_.REGEN ", false, false, false); }
                        catch { /* A refresh failure must not hide the edit or recovery error. */ }
                    }
                    throw;
                }
                try { document.SendStringToExecute("_.REGEN ", false, false, false); }
                catch (System.Exception error)
                {
                    return (notice == null ? "Propiedades actualizadas." : notice)
                        + " Ejecuta REGEN para refrescar la vista: " + error.Message;
                }
                return notice;
            }
            finally { HostApplicationServices.WorkingDatabase = previousWorking; }
        }
    }
}
