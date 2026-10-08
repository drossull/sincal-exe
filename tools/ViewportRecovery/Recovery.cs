using System.Text.Json;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;

// Standalone recovery helper, not loaded by the application or user AutoCAD.
// Its input/output are restricted to an explicitly named temporary copy folder.
public class Recovery
{
    public sealed record Request(string current, string reference, string output, string[] handles);

    static string Properties(Database db)
    {
        var info=db.SummaryInfo;
        var custom=new SortedDictionary<string,string>(StringComparer.Ordinal);
        foreach(System.Collections.DictionaryEntry item in new DatabaseSummaryInfoBuilder(info).CustomPropertyTable)
            custom.Add((string)item.Key,(string)item.Value!);
        return JsonSerializer.Serialize(new {info.Author,info.Comments,info.HyperlinkBase,info.Keywords,
            info.RevisionNumber,info.Subject,info.Title,custom});
    }

    static string Inventory(Database db)
    {
        using var tr=db.TransactionManager.StartOpenCloseTransaction();
        var result=new SortedDictionary<string,string>();
        foreach(ObjectId id in (BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForRead))
        {
            var block=(BlockTableRecord)tr.GetObject(id,OpenMode.ForRead);
            result[block.Handle.ToString()]=string.Join(";",block.Cast<ObjectId>().Select(e=>e.Handle.ToString()).OrderBy(e=>e));
        }
        return JsonSerializer.Serialize(result);
    }

    static Database Read(string path)
    {
        var db = new Database(false, true);
        db.ReadDwgFile(path, FileOpenMode.OpenForReadAndAllShare, true, "");
        db.CloseInput(true);
        return db;
    }

    static Viewport Get(Database db, Transaction tr, string handle, OpenMode mode)
        => tr.GetObject(db.GetObjectId(false, new Handle(Convert.ToInt64(handle, 16)), 0), mode) as Viewport
            ?? throw new InvalidOperationException("Handle is not a viewport: " + handle);

    static string LayoutName(Viewport vp, Transaction tr)
    {
        var owner = (BlockTableRecord)tr.GetObject(vp.OwnerId, OpenMode.ForRead);
        if (!owner.IsLayout || owner.LayoutId.IsNull) throw new InvalidOperationException("Viewport is not in a layout");
        return ((Layout)tr.GetObject(owner.LayoutId, OpenMode.ForRead)).LayoutName;
    }

    static void SameFrame(Viewport a, Viewport b, Transaction ta, Transaction tb)
    {
        if (LayoutName(a, ta) != LayoutName(b, tb) || a.CenterPoint.DistanceTo(b.CenterPoint) > 1e-7
            || Math.Abs(a.Width-b.Width)>1e-7 || Math.Abs(a.Height-b.Height)>1e-7)
            throw new InvalidOperationException("Viewport frame/layout changed; automatic recovery refused");
    }

    static void SameView(Viewport a, Viewport b)
    {
        if (a.ViewCenter.GetDistanceTo(b.ViewCenter)>1e-8 || a.ViewTarget.DistanceTo(b.ViewTarget)>1e-8
            || (a.ViewDirection-b.ViewDirection).Length>1e-8 || Math.Abs(a.ViewHeight-b.ViewHeight)>1e-8
            || Math.Abs(a.TwistAngle-b.TwistAngle)>1e-10)
            throw new InvalidOperationException("Recovered viewport failed verification: " + JsonSerializer.Serialize(new {
                actual=new {center=a.ViewCenter.ToString(),target=a.ViewTarget.ToString(),direction=a.ViewDirection.ToString(),height=a.ViewHeight,twist=a.TwistAngle},
                expected=new {center=b.ViewCenter.ToString(),target=b.ViewTarget.ToString(),direction=b.ViewDirection.ToString(),height=b.ViewHeight,twist=b.TwistAngle}}));
    }

    [CommandMethod("SINCAL_RECOVER_VIEWPORT_COPIES", CommandFlags.Modal)]
    public static void Run()
    {
        if (!string.Equals(System.Diagnostics.Process.GetCurrentProcess().ProcessName, "accoreconsole", StringComparison.OrdinalIgnoreCase)) return;
        var requestPath = Environment.GetEnvironmentVariable("SINCAL_VIEWPORT_RECOVERY_REQUEST");
        if (requestPath is null) return;
        var root = Path.GetDirectoryName(Path.GetFullPath(requestPath))!;
        if (!root.StartsWith(Path.GetTempPath(), StringComparison.OrdinalIgnoreCase)
            || !Path.GetFileName(root).StartsWith("SINCAL-viewport-recovery-", StringComparison.Ordinal)) return;
        try
        {
            var request = JsonSerializer.Deserialize<Request>(File.ReadAllText(requestPath))!;
            foreach (var path in new[] {request.current, request.reference, request.output})
                if (!Path.IsPathFullyQualified(path) || !string.Equals(Path.GetDirectoryName(path),root,StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Only temporary copies are allowed");
            if (File.Exists(request.output) || request.handles.Length == 0) throw new InvalidOperationException("Output exists or empty viewport selection");
            using var current = Read(request.current);
            using var reference = Read(request.reference);
            var properties=Properties(current);
            var inventory=Inventory(current);
            var previous = HostApplicationServices.WorkingDatabase;
            try
            {
            HostApplicationServices.WorkingDatabase=current;
            using (var ta = current.TransactionManager.StartTransaction())
            using (var tb = reference.TransactionManager.StartOpenCloseTransaction())
            {
                foreach (var handle in request.handles.Distinct())
                {
                    var a = Get(current,ta,handle,OpenMode.ForWrite);
                    var b = Get(reference,tb,handle,OpenMode.ForRead);
                    SameFrame(a,b,ta,tb);
                    var locked = a.Locked;
                    a.Locked = false;
                    a.ViewDirection = b.ViewDirection;
                    a.ViewTarget = b.ViewTarget;
                    a.TwistAngle = b.TwistAngle;
                    a.ViewHeight = b.ViewHeight;
                    a.ViewCenter = b.ViewCenter;
                    a.Locked = locked;
                    SameView(a,b);
                }
                ta.Commit();
            }
                using(var tc=current.TransactionManager.StartOpenCloseTransaction())
                using(var tb=reference.TransactionManager.StartOpenCloseTransaction())
                    foreach(var handle in request.handles) SameView(Get(current,tc,handle,OpenMode.ForRead),Get(reference,tb,handle,OpenMode.ForRead));
                current.SaveAs(request.output,true,current.OriginalFileVersion,current.SecurityParameters);
            }
            finally { HostApplicationServices.WorkingDatabase=previous; }
            using var verified = Read(request.output);
            if(Properties(verified)!=properties || Inventory(verified)!=inventory || verified.OriginalFileVersion!=current.OriginalFileVersion)
                throw new InvalidOperationException("Properties, entity inventory or DWG version changed");
            using var tv = verified.TransactionManager.StartOpenCloseTransaction();
            using var tr = reference.TransactionManager.StartOpenCloseTransaction();
            foreach(var handle in request.handles)
            {
                var a=Get(verified,tv,handle,OpenMode.ForRead);
                var b=Get(reference,tr,handle,OpenMode.ForRead);
                SameFrame(a,b,tv,tr);
                SameView(a,b);
            }
            File.WriteAllText(Path.Combine(root,"result.json"),JsonSerializer.Serialize(new {ok=true,request.handles}));
        }
        catch(System.Exception error)
        {
            File.WriteAllText(Path.Combine(root,"result.json"),JsonSerializer.Serialize(new {ok=false,error=error.ToString()}));
        }
        File.WriteAllText(Path.Combine(root,"done"),"closed");
    }
}
