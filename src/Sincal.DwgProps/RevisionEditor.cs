using System.Collections;
#if ZWCAD
using System.Web.Script.Serialization;
using ZwSoft.ZwCAD.DatabaseServices;
#else
using System.Text.Json;
using Autodesk.AutoCAD.DatabaseServices;
#endif
using System.Text.RegularExpressions;

namespace Sincal.DwgProps;

// Separate from New Revision: cell edits never shift or recreate rows/Fields.
public static class RevisionEditor
{
    public sealed record Change(string table, int row, int column, string value);
    public sealed record Cell(string text, string? field, string? property, bool editable);
    public sealed record Sheet(string id, string block, string[] locations, Cell[][] cells);
    public sealed record Snapshot(Sheet[] tables, string integrity);
    private sealed record Group(string id, string block, string[] locations, List<Table> variants);

    private static string Serialize<T>(T value)
    {
#if ZWCAD
        return new JavaScriptSerializer { MaxJsonLength=int.MaxValue }.Serialize(value);
#else
        return JsonSerializer.Serialize(value);
#endif
    }

    private static bool IsVignette(string name) => name.StartsWith("VIÑETA",StringComparison.OrdinalIgnoreCase)
        || name.StartsWith("VINETA",StringComparison.OrdinalIgnoreCase);

    private static void SuppressTable(Table table,bool suppress)
    {
#if !ZWCAD
        table.SuppressRegenerateTable(suppress);
#endif
    }

    private static string? Code(Table t, int r, int c, Transaction tr)
    {
        var cell=t.Cells[r,c];
        if(cell.Contents.Count!=1) throw new InvalidOperationException("Tabla con celdas compuestas: requiere edición manual.");
        var id=cell.Contents[0].FieldId;
        return id.IsNull?null:((Field)tr.GetObject(id,OpenMode.ForRead)).GetFieldCode();
    }
    private static string? Property(string? code)
    {
        if(code is null) return null;
        var m=Regex.Match(code,@"^\\AcVar CustomDP\.([^\s]+)(?:\s+\\f\s+""%tc1"")?\s*$");
        return m.Success?m.Groups[1].Value:null;
    }
    private static List<Table> Tables(BlockTableRecord record,Transaction tr) => record.Cast<ObjectId>()
        .Select(id=>tr.GetObject(id,OpenMode.ForRead)).OfType<Table>()
        .Where(t=>t.Columns.Count==6 && t.Rows.Count>=1 && t.Cells[0,0].Contents.Count==1
            && string.Equals(Property(Code(t,0,0,tr)),"Revision",StringComparison.OrdinalIgnoreCase))
        .OrderBy(t=>t.Handle.Value).ToList();

    private static List<Group> Find(Database db,Transaction tr,ObjectId? definitionId=null)
    {
        var roots=new Dictionary<ObjectId,List<string>>();
        void Visit(ObjectId recordId,string location,HashSet<ObjectId> ancestors)
        {
            if(ancestors.Count>32 || !ancestors.Add(recordId)) throw new InvalidOperationException("Bloques anidados cíclicos o demasiado profundos.");
            foreach(ObjectId id in (BlockTableRecord)tr.GetObject(recordId,OpenMode.ForRead))
            {
                if(tr.GetObject(id,OpenMode.ForRead) is not BlockReference reference) continue;
                var definition=reference.IsDynamicBlock?reference.DynamicBlockTableRecord:reference.BlockTableRecord;
                var block=(BlockTableRecord)tr.GetObject(definition,OpenMode.ForRead);
                if(block.IsFromExternalReference || block.Name.StartsWith("*T",StringComparison.Ordinal)) continue;
                var place=location+" / "+block.Name+" ["+reference.Handle+"]";
                if(IsVignette(block.Name)) {
                    if(!roots.ContainsKey(definition)) roots[definition]=new();
                    roots[definition].Add(place);
                } else Visit(reference.BlockTableRecord,place,new HashSet<ObjectId>(ancestors));
            }
        }
        if(definitionId.HasValue)
        {
            if(definitionId.Value.IsNull || tr.GetObject(definitionId.Value,OpenMode.ForRead) is not BlockTableRecord selected
                || selected.IsFromExternalReference || !IsVignette(selected.Name))
                throw new InvalidOperationException("Selecciona una definición de viñeta válida del dibujo.");
            roots.Add(selected.ObjectId,new List<string>{selected.Name});
        }
        else
        {
            foreach(DictionaryEntry entry in (DBDictionary)tr.GetObject(db.LayoutDictionaryId,OpenMode.ForRead))
            {
                var layout=(Layout)tr.GetObject((ObjectId)entry.Value!,OpenMode.ForRead);
                Visit(layout.BlockTableRecordId,layout.LayoutName,new HashSet<ObjectId>());
            }
        }
        var result=new List<Group>();
        foreach(var root in roots)
        {
            var definition=(BlockTableRecord)tr.GetObject(root.Key,OpenMode.ForRead);
            var originals=Tables(definition,tr);
            var variants=definition.IsDynamicBlock?definition.GetAnonymousBlockIds().Cast<ObjectId>().Select(id=>Tables((BlockTableRecord)tr.GetObject(id,OpenMode.ForRead),tr)).ToList():new List<List<Table>>();
            if(variants.Any(v=>v.Count!=originals.Count)) throw new InvalidOperationException("Las variantes de "+definition.Name+" tienen distintas tablas; no es seguro asociarlas.");
            for(int i=0;i<originals.Count;i++)
            {
                var table=originals[i];
                if(table.Rows.Count<1 || table.Rows.Count>100 || table.Columns.Count<1 || table.Columns.Count>30)
                    throw new InvalidOperationException("Tabla fuera del límite de 100 filas y 30 columnas.");
                result.Add(new Group(definition.Handle+":"+table.Handle,definition.Name,root.Value.ToArray(),variants.Select(v=>v[i]).Prepend(table).ToList()));
            }
        }
        if(result.Count==0)
        {
            if(roots.Count==0)
                throw new InvalidOperationException("No se encontraron bloques insertados con prefijo VIÑETA.");
            var names=roots.Keys.Select(id=>((BlockTableRecord)tr.GetObject(id,OpenMode.ForRead)).Name);
            throw new InvalidOperationException("Se encontró la viñeta ("+string.Join(", ",names)+"), pero su cuadro de revisiones no es compatible. "
                +"El editor requiere una tabla de AutoCAD de seis columnas, directamente dentro del bloque, con el FIELD Revision en la primera celda. "
                +"Los cuadros dibujados con textos y líneas aún no están admitidos.");
        }
        if(result.Count>100) throw new InvalidOperationException("Demasiadas tablas de viñeta en un DWG.");
        return result;
    }

    private static Cell[][] Cells(Table t,Database db,Transaction tr)
    {
        var props=new DatabaseSummaryInfoBuilder(db.SummaryInfo).CustomPropertyTable;
        return Enumerable.Range(0,t.Rows.Count).Select(r=>Enumerable.Range(0,t.Columns.Count).Select(c=> {
            var code=Code(t,r,c,tr);var property=r==0?Property(code):null;
            var actual=property is null?null:props.Keys.Cast<string>().SingleOrDefault(k=>string.Equals(k,property,StringComparison.OrdinalIgnoreCase));
            var text=t.Cells[r,c].TextString;
            if(actual is not null) { text=(string)props[actual]!; if(code!.Contains("%tc1")) text=text.ToUpperInvariant(); }
            return new Cell(text,code,actual,code is null || actual is not null);
        }).ToArray()).ToArray();
    }

    public static Snapshot Read(Database db,ObjectId? definitionId=null)
    {
        using var tr=db.TransactionManager.StartTransaction();
        var groups=Find(db,tr,definitionId);var sheets=new List<Sheet>();
        foreach(var group in groups)
        {
            var rows=Cells(group.variants[0],db,tr);
            foreach(var variant in group.variants.Skip(1))
                if(Serialize(Cells(variant,db,tr))!=Serialize(rows))
                    throw new InvalidOperationException("Las variantes de "+group.block+" no coinciden; no se mezclarán sus tablas.");
            sheets.Add(new Sheet(group.id,group.block,group.locations,rows));
        }
        var integrity=Serialize(groups.Select(g=>new {g.id,g.block,g.locations,tables=g.variants.Select(t=>new {
            handle=t.Handle.ToString(),t.Visible,x=t.Position.X,y=t.Position.Y,z=t.Position.Z,style=t.TableStyle.Handle.ToString(),
            rows=Enumerable.Range(0,t.Rows.Count).Select(r=>t.Rows[r].Height).ToArray(),
            columns=Enumerable.Range(0,t.Columns.Count).Select(c=>t.Columns[c].Width).ToArray(),
            cells=Enumerable.Range(0,t.Rows.Count).Select(r=>Enumerable.Range(0,t.Columns.Count).Select(c=> {
                var cell=t.Cells[r,c];var id=cell.Contents[0].FieldId;
                return new { style=cell.TextStyleId?.Handle.ToString(),cell.TextHeight,alignment=cell.Alignment?.ToString(),
#if ZWCAD
                    // ZWCAD rebuilds table FIELD objects on commit; preserve their cell and semantics.
                    field=id.IsNull?null:"FIELD",
#else
                    field=id.IsNull?null:id.Handle.ToString(),
#endif
                    code=Code(t,r,c,tr),evaluator=id.IsNull?null:((Field)tr.GetObject(id,OpenMode.ForRead)).EvaluatorId,
                    evaluation=id.IsNull?-1:(int)((Field)tr.GetObject(id,OpenMode.ForRead)).EvaluationOption };
            }).ToArray()).ToArray()
        }).ToArray()}).ToArray());
        var result=new Snapshot(sheets.ToArray(),integrity);
        tr.Commit();
        return result;
    }

    public static Dictionary<string,string> DesiredProperties(Snapshot old,Change[] changes)
    {
        if(changes.Length<1 || changes.Length>3000) throw new InvalidOperationException("Selecciona entre 1 y 3000 celdas modificadas.");
        var props=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);var seen=new HashSet<string>();
        foreach(var change in changes)
        {
            var table=old.tables.SingleOrDefault(t=>t.id==change.table);
            if(table is null || change.row<0 || change.row>=table.cells.Length || change.column<0 || change.column>=table.cells[change.row].Length
                || !seen.Add(change.table+":"+change.row+":"+change.column)) throw new InvalidOperationException("Celda inexistente o repetida.");
            if(change.value is null || change.value.Length>250 || change.value.Any(char.IsControl) || change.value.Contains("%<") || change.value.IndexOfAny(new[]{'\\','{','}'})>=0)
                throw new InvalidOperationException("Usa texto simple de hasta 250 caracteres por celda.");
            var cell=table.cells[change.row][change.column];
            if(!cell.editable) throw new InvalidOperationException("FIELD protegido: no se conoce una propiedad DWG editable para esta celda.");
            if(cell.property is string key)
            {
                if(props.TryGetValue(key,out var previous) && previous!=change.value) throw new InvalidOperationException("Valores contradictorios para la propiedad "+key);
                props[key]=change.value;
            }
        }
        return props;
    }

    public static void Apply(Database db,Snapshot old,Change[] changes,ObjectId? definitionId=null)
    {
        var values=DesiredProperties(old,changes);
        using var tr=db.TransactionManager.StartTransaction();
        var groups=Find(db,tr,definitionId);
        foreach(var group in groups) foreach(var table in group.variants)
        for(int c=0;c<table.Columns.Count;c++)
        {
            var id=table.Cells[0,c].Contents[0].FieldId;
            if(id.IsNull) continue;
            var field=(Field)tr.GetObject(id,OpenMode.ForRead);
            if(Property(field.GetFieldCode()) is not null
                && !string.Equals(field.EvaluatorId,"AcVar",StringComparison.OrdinalIgnoreCase)
                && !string.Equals(field.EvaluatorId,"_text",StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("El FIELD de la tabla no tiene un evaluador de propiedades válido.");
        }
        var props=new DatabaseSummaryInfoBuilder(db.SummaryInfo);
        foreach(var pair in values) props.CustomPropertyTable[pair.Key]=pair.Value;
        db.SummaryInfo=props.ToDatabaseSummaryInfo();
        foreach(var group in groups)
        foreach(var table in group.variants)
        {
            var edits=changes.Where(c=>c.table==group.id).ToArray();
            // Fields are evaluated in place. Never assign TextString/FieldId to a field cell.
            var related=old.tables.Single(s=>s.id==group.id).cells[0].Any(c=>c.property is not null && values.ContainsKey(c.property));
            if(edits.Length==0 && !related) continue;
            table.UpgradeOpen();
            // AutoCAD needs one batch to retain shared FIELD objects in dynamic definitions.
            // ZWCAD rebuilds those objects natively and does not implement this managed API.
            SuppressTable(table,true);
            try
            {
                foreach(var change in edits)
                    if(Code(table,change.row,change.column,tr) is null) table.Cells[change.row,change.column].TextString=change.value;
                for(int c=0;c<table.Columns.Count;c++)
                {
                    var id=table.Cells[0,c].Contents[0].FieldId;
                    if(id.IsNull) continue;
                    var field=(Field)tr.GetObject(id,OpenMode.ForWrite);var property=Property(field.GetFieldCode());
                    if(property is null || !values.ContainsKey(property)) continue;
#if ZWCAD
                    // Evaluating the text wrapper alone leaves its child CustomDP result cached.
                    foreach(var childId in field.GetChildrenIds())
                        ((Field)tr.GetObject(childId,OpenMode.ForWrite)).Evaluate((int)FieldEvaluationContext.Demand,db);
                    field.Evaluate((int)FieldEvaluationContext.Demand,db);
#else
                    field.Evaluate((int)FieldEvaluationContext.Preview,db);
#endif
                    if(field.EvaluationStatus.Status!=FieldEvaluationStatus.Success) throw new InvalidOperationException("No se pudo evaluar el FIELD "+property);
                }
            }
            finally { SuppressTable(table,false); }
        }
        tr.Commit();
    }

    public static void Verify(Database db,Snapshot old,Change[] changes,ObjectId? definitionId=null)
    {
        var properties=DesiredProperties(old,changes);var current=Read(db,definitionId);
        if(current.integrity!=old.integrity) throw new InvalidOperationException("Cambió el formato, tamaño, identidad o propiedades de los Fields. El original no se reemplazará.");
        foreach(var sheet in old.tables)
        {
            var actual=current.tables.Single(t=>t.id==sheet.id);
            for(int r=0;r<sheet.cells.Length;r++) for(int c=0;c<sheet.cells[r].Length;c++)
            {
                var cell=sheet.cells[r][c];var expected=cell.text;
                var edit=changes.SingleOrDefault(e=>e.table==sheet.id && e.row==r && e.column==c);
                if(edit is not null) expected=edit.value;
                if(cell.property is string key && properties.TryGetValue(key,out var value)) expected=cell.field!.Contains("%tc1")?value.ToUpperInvariant():value;
                if(actual.cells[r][c].text!=expected) throw new InvalidOperationException("La tabla guardada no coincide con los cambios solicitados.");
            }
        }
        // Check the persisted FIELD result too, not only its source DWG property.
        using var tr=db.TransactionManager.StartTransaction();
        foreach(var group in Find(db,tr,definitionId)) foreach(var table in group.variants)
        for(int c=0;c<table.Columns.Count;c++)
        {
            var code=Code(table,0,c,tr);var key=Property(code);
            if(key is null || !properties.TryGetValue(key,out var value)) continue;
            var field=(Field)tr.GetObject(table.Cells[0,c].Contents[0].FieldId,OpenMode.ForRead);
            var expected=code!.Contains("%tc1")?value.ToUpperInvariant():value;
            if(field.GetFieldCode(FieldCodeFlags.EvaluatedText)!=expected || table.Cells[0,c].TextString!=expected)
                throw new InvalidOperationException("El resultado visible del FIELD "+key+" no coincide con DWGPROPS.");
        }
        tr.Commit();
    }
}
