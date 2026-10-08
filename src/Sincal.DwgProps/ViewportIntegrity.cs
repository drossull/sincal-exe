using Autodesk.AutoCAD.DatabaseServices;

namespace Sincal.DwgProps;

public static class ViewportIntegrity
{
    public sealed record State(double[] numbers, string flags);
    public static Dictionary<string,State> Read(Database db)
    {
        using var tr=db.TransactionManager.StartOpenCloseTransaction();
        var result=new Dictionary<string,State>();
        foreach(ObjectId bid in (BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForRead))
            foreach(ObjectId id in (BlockTableRecord)tr.GetObject(bid,OpenMode.ForRead))
                if(tr.GetObject(id,OpenMode.ForRead) is Viewport v)
                    result.Add(v.Handle.ToString(),new State(new[]{
                        v.CenterPoint.X,v.CenterPoint.Y,v.CenterPoint.Z,v.Width,v.Height,
                        v.ViewCenter.X,v.ViewCenter.Y,v.ViewHeight,v.TwistAngle,
                        v.ViewTarget.X,v.ViewTarget.Y,v.ViewTarget.Z,
                        v.ViewDirection.X,v.ViewDirection.Y,v.ViewDirection.Z,v.CustomScale},
                        $"{v.OwnerId.Handle}|{v.Locked}|{v.On}|{v.PerspectiveOn}|{v.NonRectClipOn}|"+
                        (v.NonRectClipEntityId.IsNull?"":v.NonRectClipEntityId.Handle.ToString())+"|"+
                        string.Join(",",v.GetFrozenLayers().Cast<ObjectId>().Select(x=>x.Handle.ToString()).OrderBy(x=>x))));
        return result;
    }
    public static void Verify(Database db, Dictionary<string,State> before)
    {
        var after=Read(db);
        if(after.Count!=before.Count || before.Any(p=> !after.TryGetValue(p.Key,out var value)
            || value.flags!=p.Value.flags || value.numbers.Where((n,i)=>Math.Abs(n-p.Value.numbers[i])>1e-8).Any()))
            throw new InvalidOperationException("El guardado alteró un viewport. El DWG original no se reemplazará.");
    }
}
