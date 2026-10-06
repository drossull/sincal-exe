using System.Text.Json;
using System.Text.RegularExpressions;
using Autodesk.AutoCAD.DatabaseServices;

namespace Sincal.DwgProps;

public static class RevisionTable
{
    public sealed record Snapshot(string layout, string block, string[][] rows, string?[] fields, string?[] properties, string geometry = "");
    private static readonly string?[] Expected = { "Revision", "Fecha_Rev", "Dibujante", null, null, "Comentario-rev" };

    private static string? Code(Table table, int r, int c, Transaction tr)
    {
        var cell = table.Cells[r,c];
        if (cell.Contents.Count != 1) throw new InvalidOperationException("El cuadro contiene celdas compuestas; requiere revisión manual.");
        var id = cell.Contents[0].FieldId;
        return id.IsNull ? null : ((Field)tr.GetObject(id, OpenMode.ForRead)).GetFieldCode();
    }

    private static string? Property(string? code)
    {
        if (code is null) return null;
        var match = Regex.Match(code, @"^\\AcVar CustomDP\.([^\s]+)(?:\s+\\f\s+""%tc1"")?\s*$");
        if (!match.Success) throw new InvalidOperationException("Un FIELD del cuadro no corresponde a una propiedad DWGPROPS compatible.");
        return match.Groups[1].Value;
    }

    private static List<Table> Tables(BlockTableRecord block, Transaction tr)
        => block.Cast<ObjectId>().Select(id => tr.GetObject(id, OpenMode.ForRead)).OfType<Table>()
            .Where(t => t.Columns.Count == 6 && t.Rows.Count >= 2 && t.Rows.Count <= 30
                && Code(t,0,0,tr)?.Contains("CustomDP.Revision ") == true).ToList();

    private static (Layout layout, BlockTableRecord definition, List<Table> tables, Table visible) Find(Database db, Transaction tr)
    {
        var layouts = ((DBDictionary)tr.GetObject(db.LayoutDictionaryId, OpenMode.ForRead)).Cast<System.Collections.DictionaryEntry>()
            .Select(e => (Layout)tr.GetObject((ObjectId)e.Value!, OpenMode.ForRead)).Where(l => !l.ModelType).ToList();
        if (layouts.Count != 1) throw new InvalidOperationException("Nueva revisión requiere exactamente un layout por DWG.");
        var paper = (BlockTableRecord)tr.GetObject(layouts[0].BlockTableRecordId, OpenMode.ForRead);
        var candidates = paper.Cast<ObjectId>().Select(id => tr.GetObject(id, OpenMode.ForRead)).OfType<BlockReference>()
            .Where(b => b.IsDynamicBlock && Tables((BlockTableRecord)tr.GetObject(b.BlockTableRecord, OpenMode.ForRead), tr).Any(t => t.Visible)).ToList();
        if (candidates.Count != 1) throw new InvalidOperationException("No se encontró una única viñeta dinámica con cuadro de revisiones compatible.");
        var reference = candidates[0];
        var definition = (BlockTableRecord)tr.GetObject(reference.DynamicBlockTableRecord, OpenMode.ForRead);
        var blocks = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
        foreach (ObjectId bid in blocks)
            foreach (ObjectId eid in (BlockTableRecord)tr.GetObject(bid, OpenMode.ForRead))
                if (tr.GetObject(eid, OpenMode.ForRead) is BlockReference other && other.IsDynamicBlock
                    && other.DynamicBlockTableRecord == definition.ObjectId && other.ObjectId != reference.ObjectId)
                    throw new InvalidOperationException("La viñeta tiene más de una inserción; no se modificará una definición compartida.");
        var records = definition.GetAnonymousBlockIds().Cast<ObjectId>().Append(definition.ObjectId).Distinct();
        var tables = records.SelectMany(id => Tables((BlockTableRecord)tr.GetObject(id, OpenMode.ForRead), tr)).ToList();
        var visible = Tables((BlockTableRecord)tr.GetObject(reference.BlockTableRecord, OpenMode.ForRead), tr).Where(t => t.Visible).ToList();
        if (visible.Count != 1) throw new InvalidOperationException("La viñeta muestra varios cuadros; no se puede elegir uno automáticamente.");
        return (layouts[0], definition, tables, visible[0]);
    }

    private static Snapshot ReadTable(Table table, string layout, string block, Transaction tr)
    {
        var fields = Enumerable.Range(0,6).Select(c => Code(table,0,c,tr)).ToArray();
        var properties = fields.Select(Property).ToArray();
        for (int c=0;c<6;c++)
            if (Expected[c] is not null && !string.Equals(properties[c], Expected[c], StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("La distribución de Fields del cuadro no coincide con la viñeta compatible.");
        var rows = new List<string[]>();
        for (int r=0;r<table.Rows.Count;r++)
        {
            var row = new string[6];
            for (int c=0;c<6;c++)
            {
                if (r>0 && Code(table,r,c,tr) is not null) throw new InvalidOperationException("El historial contiene Fields: no se desplazará automáticamente.");
                row[c]=table.Cells[r,c].TextString;
            }
            rows.Add(row);
        }
        return new Snapshot(layout, block, rows.ToArray(), fields, properties);
    }

    public static Snapshot Read(Database db)
    {
        using var tr = db.TransactionManager.StartOpenCloseTransaction();
        var found = Find(db,tr);
        var snapshot = ReadTable(found.visible,found.layout.LayoutName,found.definition.Name,tr);
        var expected = JsonSerializer.Serialize(snapshot);
        foreach (var table in found.tables)
            if (JsonSerializer.Serialize(ReadTable(table,snapshot.layout,snapshot.block,tr)) != expected)
                throw new InvalidOperationException("Las variantes del bloque tienen historiales distintos. Revísalas antes de crear una revisión.");
        // Freeze the property values, not a potentially outdated display cache.
        var props = new DatabaseSummaryInfoBuilder(db.SummaryInfo).CustomPropertyTable;
        for(int c=0;c<6;c++)
            if(snapshot.properties[c] is string key)
            {
                if (!props.Contains(key)) throw new InvalidOperationException("Falta la propiedad " + key);
                var value = (string)props[key]!;
                snapshot.rows[0][c] = snapshot.fields[c]!.Contains("%tc1") ? value.ToUpperInvariant() : value;
            }
        var geometry = JsonSerializer.Serialize(found.tables.OrderBy(t=>t.Handle.Value).Select(t=>new {
            handle=t.Handle.ToString(),t.Visible,x=t.Position.X,y=t.Position.Y,z=t.Position.Z,
            style=t.TableStyle.Handle.ToString(),rows=Enumerable.Range(0,t.Rows.Count).Select(r=>t.Rows[r].Height).ToArray(),
            evaluation=Enumerable.Range(0,6).Select(c=>t.Cells[0,c].Contents[0].FieldId.IsNull ? -1 : (int)((Field)tr.GetObject(t.Cells[0,c].Contents[0].FieldId,OpenMode.ForRead)).EvaluationOption).ToArray(),
            columns=Enumerable.Range(0,t.Columns.Count).Select(c=>t.Columns[c].Width).ToArray() }));
        return snapshot with { geometry = geometry };
    }

    public static Snapshot Apply(Database db, string[] values)
    {
        if(values.Length != 6 || values.Any(s => string.IsNullOrWhiteSpace(s) || s.Length>250 || s.Any(char.IsControl)
            || s.Contains("%<") || s.Contains('\\') || s.Contains('{') || s.Contains('}')))
            throw new InvalidOperationException("Completa los seis datos con texto simple (máximo 250 caracteres).");
        var old = Read(db);
        if(string.Equals(values[0].Trim(),old.rows[0][0].Trim(),StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("La nueva revisión coincide con la actual; no se desplazó el historial.");
        using var tr = db.TransactionManager.StartTransaction();
        var found = Find(db,tr);
        var evaluation=found.tables.ToDictionary(t=>t.ObjectId,t=>Enumerable.Range(0,6).Select(c=>t.Cells[0,c].Contents[0].FieldId.IsNull
            ? FieldEvaluationOptions.Disable : ((Field)tr.GetObject(t.Cells[0,c].Contents[0].FieldId,OpenMode.ForRead)).EvaluationOption).ToArray());
        var props = new DatabaseSummaryInfoBuilder(db.SummaryInfo);
        for(int c=0;c<6;c++) if(old.properties[c] is string key) props.CustomPropertyTable[key]=values[c];
        db.SummaryInfo=props.ToDatabaseSummaryInfo();
        foreach(var table in found.tables)
        {
            table.UpgradeOpen();
            for(int r=table.Rows.Count-1;r>=1;r--)
                for(int c=0;c<6;c++) table.Cells[r,c].TextString=old.rows[r-1][c];
            for(int c=0;c<6;c++)
            {
                if(old.fields[c] is null) table.Cells[0,c].TextString=values[c];
                else
                {
                    // Dynamic table variants can share field objects. Give each
                    // updated table an independent field with the same expression.
                    // A table cell needs a text field containing the AcVar child,
                    // not a bare evaluator field (which displays #### in a cell).
                    var field=new Field("%<" + old.fields[c] + ">%", true);
                    field.EvaluationOption=evaluation[table.ObjectId][c];
                    db.AddDBObject(field);
                    tr.AddNewlyCreatedDBObject(field,true);
                    field.Evaluate((int)FieldEvaluationContext.Preview,db);
                    if(field.EvaluationStatus.Status != FieldEvaluationStatus.Success)
                        throw new InvalidOperationException("No se pudo evaluar FIELD: " + field.EvaluationStatus.Status + " " + field.EvaluationStatus.ErrorMessage);
                    var evaluated=field.GetFieldCode(FieldCodeFlags.EvaluatedText);
                    var expected=old.fields[c]!.Contains("%tc1")?values[c].ToUpperInvariant():values[c];
                    if(evaluated != expected) throw new InvalidOperationException("El FIELD de la columna " + (c+1) + " no muestra el valor solicitado.");
                    table.Cells[0,c].Contents[0].FieldId=field.ObjectId;
                    var attached=(Field)tr.GetObject(table.Cells[0,c].Contents[0].FieldId,OpenMode.ForWrite);
                    attached.Evaluate((int)FieldEvaluationContext.Preview,db);
                }
            }
            table.GenerateLayout();
            table.RecomputeTableBlock(true);
        }
        tr.Commit();
        return old;
    }

    public static void Verify(Database db, Snapshot old, string[] values)
    {
        var current=Read(db);
        if(current.geometry != old.geometry)
            throw new InvalidOperationException("Los datos no caben sin cambiar las dimensiones del cuadro. Acorta los textos; el original no se modificó.");
        if(current.rows.Length != old.rows.Length || !current.fields.SequenceEqual(old.fields)
            || !current.rows[0].SequenceEqual(values.Select((v,c)=>old.fields[c]?.Contains("%tc1")==true?v.ToUpperInvariant():v)))
            throw new InvalidOperationException("No se conservaron los Fields o la nueva revisión.");
        for(int r=1;r<current.rows.Length;r++)
            if(!current.rows[r].SequenceEqual(old.rows[r-1])) throw new InvalidOperationException("El historial no se desplazó correctamente.");
        using var tr=db.TransactionManager.StartOpenCloseTransaction();
        foreach(var table in Find(db,tr).tables)
            for(int c=0;c<6;c++)
                if(table.Cells[0,c].TextString != current.rows[0][c])
                    throw new InvalidOperationException("La presentación del FIELD de la columna " + (c+1) + " no se actualizó; no se reemplazará el original.");
    }
}
