using System.Collections;
using System.Text.Json;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;

namespace Sincal.DwgProps;

public class Commands
{
    public sealed class Request
    {
        public string file { get; set; } = "";
        public string output { get; set; } = "";
        public string saved { get; set; } = "";
        public Dictionary<string, string?>? changes { get; set; }
        public bool revisionRead { get; set; }
        public string[]? revisionValues { get; set; }
    }

    private static Dictionary<string, string> Properties(Database database)
    {
        var values = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (DictionaryEntry item in new DatabaseSummaryInfoBuilder(database.SummaryInfo).CustomPropertyTable)
            values.Add((string)item.Key, (string)item.Value!);
        return values;
    }

    private static string StandardProperties(Database database)
    {
        var info = database.SummaryInfo;
        return JsonSerializer.Serialize(new { info.Author, info.Comments, info.HyperlinkBase,
            info.Keywords, info.RevisionNumber, info.Subject, info.Title });
    }

    private static string EntityInventory(Database database, bool revision = false)
    {
        using var transaction = database.TransactionManager.StartOpenCloseTransaction();
        var blocks = (BlockTable)transaction.GetObject(database.BlockTableId, OpenMode.ForRead);
        var inventory = new SortedDictionary<string, string>(StringComparer.Ordinal);
        foreach (ObjectId blockId in blocks)
        {
            var block = (BlockTableRecord)transaction.GetObject(blockId, OpenMode.ForRead);
            if (revision && block.Name.StartsWith("*T", StringComparison.Ordinal)) continue; // regenerated table graphics
            // AutoCAD renumbers anonymous block names on SaveAs; their handles
            // and entity ownership remain stable and identify the same objects.
            inventory[block.IsAnonymous ? "@" + block.Handle : block.Name] = string.Join(";", block.Cast<ObjectId>().Select(id => id.Handle.ToString()).OrderBy(h => h, StringComparer.Ordinal));
        }
        return JsonSerializer.Serialize(inventory);
    }

    [CommandMethod("SINCAL_DWGPROPS", CommandFlags.Modal)]
    public static void Run()
    {
        // This command belongs ONLY to the disposable Core Console worker.
        // Never terminate or operate inside a user's interactive AutoCAD.
        if (!string.Equals(System.Diagnostics.Process.GetCurrentProcess().ProcessName, "accoreconsole", StringComparison.OrdinalIgnoreCase)) return;
        var requestPath = Environment.GetEnvironmentVariable("SINCAL_DWGPROPS_REQUEST");
        if (string.IsNullOrEmpty(requestPath)) return;
        ProcessRequest(requestPath, true);
    }

    [CommandMethod("SINCAL_DWGPROPS_BATCH", CommandFlags.Modal)]
    public static void RunBatch()
    {
        if (!string.Equals(System.Diagnostics.Process.GetCurrentProcess().ProcessName, "accoreconsole", StringComparison.OrdinalIgnoreCase)) return;
        var root = Environment.GetEnvironmentVariable("SINCAL_DWGPROPS_BATCH");
        if (string.IsNullOrEmpty(root)) return;
        root = Path.GetFullPath(root);
        var inbox = Path.Combine(root, "next.json");
        File.WriteAllText(Path.Combine(root, "ready"), "ready");
        var idle = System.Diagnostics.Stopwatch.StartNew();
        while (!File.Exists(Path.Combine(root, "stop")) && idle.Elapsed.TotalSeconds < 180)
        {
            if (!File.Exists(inbox)) { System.Threading.Thread.Sleep(50); continue; }
            var requestPath = JsonSerializer.Deserialize<string>(File.ReadAllText(inbox))!;
            File.Delete(inbox);
            // Only requests in direct child directories of this private job.
            if (!string.Equals(Path.GetDirectoryName(Path.GetDirectoryName(Path.GetFullPath(requestPath))), root, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Solicitud fuera de la carpeta temporal del lote.");
            ProcessRequest(requestPath, false);
            idle.Restart();
        }
        File.WriteAllText(Path.Combine(root, "stopped"), "closed");
    }

    private static void ProcessRequest(string requestPath, bool requireOpened)
    {
        var request = JsonSerializer.Deserialize<Request>(File.ReadAllText(requestPath))!;
        try
        {
            var directory = Path.GetDirectoryName(Path.GetFullPath(requestPath));
            foreach (var path in new[] { request.file, request.output, request.saved })
                if (!Path.IsPathFullyQualified(path) || Path.GetDirectoryName(Path.GetFullPath(path)) != directory)
                    throw new InvalidOperationException("La solicitud debe usar solo archivos de su carpeta temporal.");
            var opened = HostApplicationServices.WorkingDatabase;
            if (requireOpened && !string.Equals(Path.GetFullPath(opened.Filename), Path.GetFullPath(request.file), StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("El dibujo abierto no coincide con la copia solicitada.");
            // Re-read from disk: startup LISPs may have modified the editor's
            // working database. Their changes must NOT leak into this operation.
            using var database = new Database(false, true);
            database.ReadDwgFile(request.file, FileOpenMode.OpenForReadAndAllShare, true, "");
            database.CloseInput(true);
            var original = Properties(database);
            var standard = StandardProperties(database);
            var inventory = request.changes is null ? "" : EntityInventory(database);
            var desired = new Dictionary<string, string>(original, StringComparer.Ordinal);
            object? revisionResult = null;
            if (request.revisionRead || request.revisionValues is not null)
            {
                var previous = RevisionTable.Read(database);
                revisionResult = previous;
                if (request.revisionValues is not null)
                {
                    var stableInventory = EntityInventory(database, true);
                    try
                    {
                        HostApplicationServices.WorkingDatabase = database;
                        RevisionTable.Apply(database, request.revisionValues);
                        try { RevisionTable.Verify(database, previous, request.revisionValues); }
                        catch (System.Exception error) { throw new InvalidOperationException("Antes de guardar: " + error.Message); }
                        database.SaveAs(request.saved, database.OriginalFileVersion);
                    }
                    finally { HostApplicationServices.WorkingDatabase = opened; }
                    using var verified = new Database(false, true);
                    verified.ReadDwgFile(request.saved, FileOpenMode.OpenForReadAndAllShare, true, "");
                    verified.CloseInput(true);
                    RevisionTable.Verify(verified, previous, request.revisionValues);
                    if (StandardProperties(verified) != standard || EntityInventory(verified,true) != stableInventory
                        || verified.OriginalFileVersion != database.OriginalFileVersion)
                        throw new InvalidOperationException("Cambió la estructura del DWG al crear la revisión.");
                    desired = Properties(verified);
                    var allowed = previous.properties.Where(p=>p is not null).ToHashSet(StringComparer.OrdinalIgnoreCase);
                    if (original.Count != desired.Count || original.Any(p=>!allowed.Contains(p.Key) && (!desired.TryGetValue(p.Key,out var value) || value!=p.Value)))
                        throw new InvalidOperationException("Cambió una propiedad ajena a la revisión.");
                    revisionResult = RevisionTable.Read(verified);
                }
            }
            if (request.changes is not null)
            {
                var builder = new DatabaseSummaryInfoBuilder(database.SummaryInfo);
                foreach (var change in request.changes)
                {
                    var key = desired.Keys.FirstOrDefault(k => string.Equals(k, change.Key, StringComparison.OrdinalIgnoreCase)) ?? change.Key;
                    if (change.Value is null)
                    {
                        desired.Remove(key);
                        builder.CustomPropertyTable.Remove(key);
                    }
                    else
                    {
                        desired[key] = change.Value;
                        builder.CustomPropertyTable[key] = change.Value;
                    }
                }
                database.SummaryInfo = builder.ToDatabaseSummaryInfo();
                try
                {
                    HostApplicationServices.WorkingDatabase = database;
                    database.SaveAs(request.saved, database.OriginalFileVersion);
                }
                finally { HostApplicationServices.WorkingDatabase = opened; }
                using var verify = new Database(false, true);
                verify.ReadDwgFile(request.saved, FileOpenMode.OpenForReadAndAllShare, true, "");
                verify.CloseInput(true);
                var actual = Properties(verify);
                if (actual.Count != desired.Count || desired.Any(p => !actual.TryGetValue(p.Key, out var value) || value != p.Value))
                    throw new InvalidOperationException("La lectura del DWG guardado no coincide con los cambios.");
                if (StandardProperties(verify) != standard || EntityInventory(verify) != inventory || verify.OriginalFileVersion != database.OriginalFileVersion)
                    throw new InvalidOperationException("La verificación detectó cambios ajenos a las propiedades personalizadas. No se reemplazará el original.");
            }
            File.WriteAllText(request.output, JsonSerializer.Serialize(new { ok = true, properties = desired, revision = revisionResult }));
        }
        catch (System.Exception error)
        {
            File.WriteAllText(request.output, JsonSerializer.Serialize(new { ok = false, error = error.Message }));
        }
        // Signal only AFTER the using scopes disposed all databases. The parent
        // may now stop its dedicated process if a startup hook prevents QUIT.
        File.WriteAllText(request.output + ".done", "closed");
    }
}
