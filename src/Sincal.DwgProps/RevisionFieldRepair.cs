using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using Autodesk.AutoCAD.DatabaseServices;

namespace Sincal.DwgProps;

// Explicit maintenance operation for the known revision-table child-field defect.
// It never discovers tables or edits SummaryInfo, history, or viewport entities.
public static class RevisionFieldRepair
{
    private static readonly Dictionary<int,string> Expected = new()
    {
        [0]="Revision", [1]="Fecha_Rev", [2]="Dibujante", [5]="Comentario-rev"
    };
    public sealed record FieldState(string handle, string code, int option, FieldState[] children);
    public sealed record CellState(string text, FieldState? field);
    public sealed record TableState(string handle, string geometry, CellState[][] cells,
                                    Dictionary<int,string> expectedValues, bool repair);
    public sealed record Snapshot(TableState[] tables, string otherFields);

    private static string Id(ObjectId id) => id.IsNull ? "" : id.Handle.ToString();
    private static bool TitleBlock(BlockTableRecord block)
        => !block.IsFromExternalReference && !block.IsFromOverlayReference
            && (block.Name.StartsWith("VIÑETA",StringComparison.OrdinalIgnoreCase)
                || block.Name.StartsWith("VINETA",StringComparison.OrdinalIgnoreCase));
    private static void ValidateOwner(BlockTableRecord owner, Transaction tr)
    {
        if(owner.IsFromExternalReference || owner.IsFromOverlayReference)
            throw new InvalidOperationException("No se reparan cuadros pertenecientes a referencias externas.");
        if(TitleBlock(owner)) return;
        // Follow only references to this selected anonymous definition. No scan
        // of unrelated blocks, layouts, tables or model-space entities is needed.
        if(owner.IsAnonymous)
            foreach(ObjectId id in owner.GetBlockReferenceIds(true,false))
                if(tr.GetObject(id,OpenMode.ForRead) is BlockReference reference && reference.IsDynamicBlock
                    && reference.BlockTableRecord==owner.ObjectId
                    && tr.GetObject(reference.DynamicBlockTableRecord,OpenMode.ForRead) is BlockTableRecord original
                    && TitleBlock(original)) return;
        throw new InvalidOperationException("La tabla seleccionada no pertenece a una definición VIÑETA o VINETA.");
    }
    private static Table Open(Database db, Transaction tr, string handle, OpenMode mode=OpenMode.ForRead)
    {
        if(!long.TryParse(handle,NumberStyles.HexNumber,CultureInfo.InvariantCulture,out var value) || value<=0)
            throw new InvalidOperationException("Identificador de tabla no válido.");
        var id=db.GetObjectId(false,new Handle(value),0);
        var table=tr.GetObject(id,mode) as Table
            ?? throw new InvalidOperationException("El identificador solicitado no corresponde a una tabla.");
        if(table.Columns.Count!=6 || table.Rows.Count<2 || table.Rows.Count>30)
            throw new InvalidOperationException("El cuadro no tiene la distribución de revisiones compatible.");
        return table;
    }
    private static FieldState ReadField(ObjectId id, Transaction tr, HashSet<ObjectId> seen, int depth=0)
    {
        if(id.IsNull || id.IsErased || depth>16 || !seen.Add(id))
            throw new InvalidOperationException("Árbol de Fields no válido o no registrado.");
        var field=tr.GetObject(id,OpenMode.ForRead) as Field
            ?? throw new InvalidOperationException("Una referencia del cuadro no es un FIELD.");
        return new(Id(id),field.GetFieldCode(),(int)field.EvaluationOption,
            field.GetChildrenIds().Select(child=>ReadField(child,tr,seen,depth+1)).ToArray());
    }
    private static void ValidateFieldOwner(Table table, FieldState root, Transaction tr)
    {
        var field=(Field)tr.GetObject(FieldId(table.Database,root.handle),OpenMode.ForRead);
        var child=(Field)tr.GetObject(FieldId(table.Database,root.children[0].handle),OpenMode.ForRead);
        if(child.OwnerId!=field.ObjectId)
            throw new InvalidOperationException("El FIELD hijo pertenece a otro campo; no se modificará una referencia compartida.");
    }
    private static TableState Read(Database db, Transaction tr, string handle)
    {
        var table=Open(db,tr,handle);
        var owner=(BlockTableRecord)tr.GetObject(table.OwnerId,OpenMode.ForRead);
        ValidateOwner(owner,tr);
        var cells=Enumerable.Range(0,table.Rows.Count).Select(r=>Enumerable.Range(0,6).Select(c=> {
            var cell=table.Cells[r,c];
            if(cell.Contents.Count!=1)
                throw new InvalidOperationException("El cuadro contiene celdas compuestas; requiere revisión manual.");
            var id=cell.Contents[0].FieldId;
            return new CellState(cell.TextString,id.IsNull ? null : ReadField(id,tr,new()));
        }).ToArray()).ToArray();
        var geometry=JsonSerializer.Serialize(new {
            owner=Id(table.OwnerId),ownerName=owner.IsAnonymous ? "" : owner.Name,
            layout=owner.IsLayout ? Id(owner.LayoutId) : "",
            table.Visible,position=new[]{table.Position.X,table.Position.Y,table.Position.Z},
            table.Rotation,normal=new[]{table.Normal.X,table.Normal.Y,table.Normal.Z},
            scale=new[]{table.ScaleFactors.X,table.ScaleFactors.Y,table.ScaleFactors.Z},
            layer=Id(table.LayerId),style=Id(table.TableStyle),
            rows=Enumerable.Range(0,table.Rows.Count).Select(r=>table.Rows[r].Height).ToArray(),
            columns=Enumerable.Range(0,6).Select(c=>table.Columns[c].Width).ToArray(),
            cells=Enumerable.Range(0,table.Rows.Count).Select(r=>Enumerable.Range(0,6).Select(c=> {
                var cell=table.Cells[r,c];
                return new { textStyle=cell.TextStyleId?.Handle.ToString(),cell.TextHeight,
                    alignment=cell.Alignment?.ToString(),cellStyle=cell.Style };
            }).ToArray()).ToArray()
        });
        var properties=new DatabaseSummaryInfoBuilder(db.SummaryInfo).CustomPropertyTable;
        var expectedValues=new Dictionary<int,string>();
        bool repair=false;
        foreach(var pair in Expected)
        {
            var root=cells[0][pair.Key].field
                ?? throw new InvalidOperationException("Falta un FIELD en la revisión actual.");
            var match=Regex.Match(root.code,@"^\\AcVar CustomDP\.([^\s]+)(?:\s+\\f\s+""%tc1"")?\s*$");
            if(!match.Success || !string.Equals(match.Groups[1].Value,pair.Value,StringComparison.OrdinalIgnoreCase)
                || root.option!=(int)FieldEvaluationOptions.Automatic || root.children.Length!=1)
                throw new InvalidOperationException("El FIELD no corresponde al patrón de revisión reparable.");
            var child=root.children[0];
            if(child.code!=root.code || child.children.Length!=0
                || child.option is not (0 or (int)FieldEvaluationOptions.Automatic))
                throw new InvalidOperationException("El FIELD hijo no corresponde al patrón deshabilitado conocido.");
            ValidateFieldOwner(table,root,tr);
            if(!properties.Contains(match.Groups[1].Value))
                throw new InvalidOperationException("Falta la propiedad DWGPROPS "+pair.Value+".");
            var value=(string)properties[match.Groups[1].Value]!;
            expectedValues[pair.Key]=root.code.Contains("%tc1") ? value.ToUpperInvariant() : value;
            repair |= child.option==0;
        }
        return new(Id(table.ObjectId),geometry,cells,expectedValues,repair);
    }
    private static ObjectId FieldId(Database db,string handle)
        => db.GetObjectId(false,new Handle(long.Parse(handle,NumberStyles.HexNumber,CultureInfo.InvariantCulture)),0);
    private static string OtherFields(Database db,Transaction tr,IEnumerable<string> selected)
    {
        var excluded=new HashSet<string>(selected,StringComparer.OrdinalIgnoreCase);
        var result=new List<(string table,int row,int column,int content,FieldState field)>();
        // Read-only preservation check. Selection and all mutations remain
        // restricted to the explicitly requested table handles. A field can be
        // owned by one table yet referenced by another, so ownership alone is
        // insufficient to prevent a shared-field change from escaping the scope.
        foreach(ObjectId blockId in (BlockTable)tr.GetObject(db.BlockTableId,OpenMode.ForRead))
            foreach(ObjectId objectId in (BlockTableRecord)tr.GetObject(blockId,OpenMode.ForRead))
            {
                if(tr.GetObject(objectId,OpenMode.ForRead) is not Table table || excluded.Contains(Id(objectId))) continue;
                for(int r=0;r<table.Rows.Count;r++)
                    for(int c=0;c<table.Columns.Count;c++)
                        for(int content=0;content<table.Cells[r,c].Contents.Count;content++)
                        {
                            var fieldId=table.Cells[r,c].Contents[content].FieldId;
                            if(!fieldId.IsNull) result.Add((Id(objectId),r,c,content,ReadField(fieldId,tr,new())));
                        }
            }
        return JsonSerializer.Serialize(result.OrderBy(item=>item.table,StringComparer.Ordinal)
            .ThenBy(item=>item.row).ThenBy(item=>item.column).ThenBy(item=>item.content)
            .Select(item=>new {item.table,item.row,item.column,item.content,item.field}));
    }

    public static Snapshot Repair(Database db, string[] tableHandles)
    {
        if(tableHandles is null || tableHandles.Length<1 || tableHandles.Length>100
            || tableHandles.Any(string.IsNullOrWhiteSpace)
            || tableHandles.Distinct(StringComparer.OrdinalIgnoreCase).Count()!=tableHandles.Length)
            throw new InvalidOperationException("Selecciona entre una y cien tablas distintas para reparar.");
        Snapshot before;
        using(var tr=db.TransactionManager.StartOpenCloseTransaction())
        {
            var tables=tableHandles.Select(handle=>Read(db,tr,handle)).ToArray();
            before=new(tables,OtherFields(db,tr,tables.Select(t=>t.handle)));
            if(before.tables.Select(t=>t.handle).Distinct().Count()!=before.tables.Length)
                throw new InvalidOperationException("La solicitud repite una tabla.");
        }
        var working=HostApplicationServices.WorkingDatabase;
        try
        {
            HostApplicationServices.WorkingDatabase=db;
            using(var tr=db.TransactionManager.StartTransaction())
            {
                foreach(var saved in before.tables.Where(t=>t.repair))
                {
                    var table=Open(db,tr,saved.handle,OpenMode.ForWrite);
                    table.SuppressRegenerateTable(true);
                    try
                    {
                        foreach(var column in Expected.Keys)
                        {
                            // Existing table variants may reference the same Field.
                            // Replace only this cell with an independent text field;
                            // never mutate its old parent/child objects in place.
                            var field=new Field("%<"+saved.cells[0][column].field!.code+">%",true);
                            field.EvaluationOption=FieldEvaluationOptions.Automatic;
                            db.AddDBObject(field);
                            tr.AddNewlyCreatedDBObject(field,true);
                            field.Evaluate((int)FieldEvaluationContext.Preview,db);
                            if(field.EvaluationStatus.Status!=FieldEvaluationStatus.Success
                                || field.GetFieldCode(FieldCodeFlags.EvaluatedText)!=saved.expectedValues[column])
                                throw new InvalidOperationException("No se pudo actualizar un FIELD de la revisión.");
                            table.Cells[0,column].Contents[0].FieldId=field.ObjectId;
                            ((Field)tr.GetObject(table.Cells[0,column].Contents[0].FieldId,OpenMode.ForWrite))
                                .Evaluate((int)FieldEvaluationContext.Preview,db);
                        }
                    }
                    finally { table.SuppressRegenerateTable(false); }
                    // The table must rebuild its stored field tree; changing only
                    // the exposed child flags is lost when the existing table saves.
                    table.GenerateLayout();
                    table.RecomputeTableBlock(true);
                }
                tr.Commit();
            }
            // Newly rebuilt table children are resident only after closure of
            // the regeneration transaction. Never dispose transient child wrappers.
            using(var tr=db.TransactionManager.StartTransaction())
            {
                foreach(var saved in before.tables.Where(t=>t.repair))
                {
                    var table=Open(db,tr,saved.handle);
                    foreach(var column in Expected.Keys)
                    {
                        var field=(Field)tr.GetObject(table.Cells[0,column].Contents[0].FieldId,OpenMode.ForRead);
                        FieldEvaluation.InheritNewChildren(field,tr);
                        FieldEvaluation.VerifyChildren(field,tr);
                    }
                }
                tr.Commit();
            }
            Verify(db,before);
            return before;
        }
        finally { HostApplicationServices.WorkingDatabase=working; }
    }
    private static bool SameExpression(FieldState left,FieldState right)
        => left.code==right.code && left.children.Length==right.children.Length
            && left.children.Zip(right.children).All(pair=>SameExpression(pair.First,pair.Second));
    private static bool Automatic(FieldState field)
        => field.option==(int)FieldEvaluationOptions.Automatic && field.children.All(Automatic);
    private static string Difference(string before,string after)
    {
        using var left=JsonDocument.Parse(before);using var right=JsonDocument.Parse(after);
        var old=left.RootElement.EnumerateArray().ToArray();var current=right.RootElement.EnumerateArray().ToArray();
        static string Identify(JsonElement cell)
        {
            var field=cell.GetProperty("field");
            var children=string.Join(",",field.GetProperty("children").EnumerateArray()
                .Select(child=>child.GetProperty("handle").GetString()+":"+child.GetProperty("option").GetInt32()));
            return $"tabla {cell.GetProperty("table").GetString()}, fila {cell.GetProperty("row").GetInt32()}, "
                +$"columna {cell.GetProperty("column").GetInt32()}, FIELD {field.GetProperty("handle").GetString()} "
                +$"opción {field.GetProperty("option").GetInt32()}, hijos [{children}]";
        }
        for(int i=0;i<Math.Min(old.Length,current.Length);i++)
            if(old[i].GetRawText()!=current[i].GetRawText())
                return "Antes: "+Identify(old[i])+"; después: "+Identify(current[i])+".";
        return $"Cantidad de referencias: {old.Length} → {current.Length}.";
    }
    public static void Verify(Database db, Snapshot before)
    {
        using var tr=db.TransactionManager.StartOpenCloseTransaction();
        var otherFields=OtherFields(db,tr,before.tables.Select(t=>t.handle));
        if(otherFields!=before.otherFields)
            throw new InvalidOperationException("La reparación alteró Fields de otra tabla. El original no se reemplazará. "
                +Difference(before.otherFields,otherFields));
        foreach(var saved in before.tables)
        {
            var current=Read(db,tr,saved.handle);
            if(current.geometry!=saved.geometry || current.cells.Length!=saved.cells.Length
                || JsonSerializer.Serialize(current.expectedValues)!=JsonSerializer.Serialize(saved.expectedValues))
                throw new InvalidOperationException("La reparación alteró la geometría, formato o propiedades del cuadro.");
            for(int r=0;r<saved.cells.Length;r++)
                for(int c=0;c<6;c++)
                {
                    var old=saved.cells[r][c];var now=current.cells[r][c];
                    if(r==0 && Expected.ContainsKey(c))
                    {
                        if(old.field is null || now.field is null || !SameExpression(old.field,now.field)
                            || !Automatic(now.field) || now.text!=saved.expectedValues[c])
                            throw new InvalidOperationException("No se conservaron los Fields automáticos o sus valores actuales.");
                        if(!saved.repair && JsonSerializer.Serialize(old)!=JsonSerializer.Serialize(now))
                            throw new InvalidOperationException("Se modificó un FIELD que no requería reparación.");
                    }
                    else if(JsonSerializer.Serialize(old)!=JsonSerializer.Serialize(now))
                        throw new InvalidOperationException("La reparación modificó una celda ajena a la revisión actual.");
                }
        }
    }
}
