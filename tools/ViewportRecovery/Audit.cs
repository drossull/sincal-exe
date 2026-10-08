using System.Text.Json;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;

public class ViewportAudit
{
    [CommandMethod("SINCAL_AUDIT_VIEWPORT_COPIES", CommandFlags.Modal)]
    public static void Run()
    {
        if (System.Diagnostics.Process.GetCurrentProcess().ProcessName != "accoreconsole") return;
        var root = Environment.GetEnvironmentVariable("SINCAL_VP_AUDIT_ROOT");
        if (root == null || !Path.GetFullPath(root).StartsWith(Path.GetTempPath(), StringComparison.OrdinalIgnoreCase)
            || !Path.GetFileName(root).StartsWith("SINCAL-vp-audit-")) return;
        var files = JsonSerializer.Deserialize<string[]>(File.ReadAllText(Path.Combine(root,"files.json")))!;
        using var output = new StreamWriter(Path.Combine(root,"audit.jsonl"));
        foreach(var file in files)
        {
            try {
                if (Path.GetDirectoryName(Path.GetFullPath(file)) != root) throw new InvalidOperationException("Only audit copies allowed");
                using var db = new Database(false,true);
                db.ReadDwgFile(file,FileOpenMode.OpenForReadAndAllShare,true,""); db.CloseInput(true);
                using var tr = db.TransactionManager.StartOpenCloseTransaction();
                var views = new List<object>();
                foreach (ObjectId id in (BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForRead)) {
                    var block=(BlockTableRecord)tr.GetObject(id,OpenMode.ForRead);
                    if (!block.IsLayout) continue;
                    var layout=(Layout)tr.GetObject(block.LayoutId,OpenMode.ForRead);
                    if (layout.ModelType) continue;
                    var layoutViews=layout.GetViewports();
                    var overall=layoutViews.Count>0 ? layoutViews[0] : ObjectId.Null;
                    foreach(ObjectId entity in block) {
                        if (tr.GetObject(entity,OpenMode.ForRead) is not Viewport vp) continue;
                        views.Add(new {handle=vp.Handle.ToString(),layout=layout.LayoutName,
                            overall=entity==overall,overallKnown=!overall.IsNull,
                            frame=new[]{vp.CenterPoint.X,vp.CenterPoint.Y,vp.CenterPoint.Z,vp.Width,vp.Height},
                            view=new[]{vp.ViewCenter.X,vp.ViewCenter.Y,vp.ViewTarget.X,vp.ViewTarget.Y,vp.ViewTarget.Z,
                                vp.ViewDirection.X,vp.ViewDirection.Y,vp.ViewDirection.Z,vp.ViewHeight,vp.TwistAngle},
                            locked=vp.Locked});
                    }
                }
                output.WriteLine(JsonSerializer.Serialize(new {file,views}));
            } catch(System.Exception error) {output.WriteLine(JsonSerializer.Serialize(new{file,error=error.Message}));}
            output.Flush();
        }
        File.WriteAllText(Path.Combine(root,"done"),"done");
    }
}
