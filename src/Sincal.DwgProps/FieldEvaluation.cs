using Autodesk.AutoCAD.DatabaseServices;

namespace Sincal.DwgProps;

internal static class FieldEvaluation
{
    // Only call for the independent text field just created by New Revision.
    // Preview evaluation can conceal disabled child fields: it forces a value
    // even when later Regen/Save/Open evaluations would leave that value stale.
    public static void InheritNewChildren(Field root, Transaction transaction)
        => Visit(root, root.EvaluationOption, transaction, new HashSet<ObjectId>(), 0, true);

    public static void VerifyChildren(Field root, Transaction transaction)
        => Visit(root, root.EvaluationOption, transaction, new HashSet<ObjectId>(), 0, false);

    private static void Visit(Field field, FieldEvaluationOptions expected, Transaction transaction,
                              HashSet<ObjectId> visited, int depth, bool initialize)
    {
        if (depth > 16)
            throw new InvalidOperationException("El FIELD contiene demasiados niveles de campos hijos.");
        if (field.ObjectId.IsNull || !visited.Add(field.ObjectId))
            throw new InvalidOperationException("El FIELD no está registrado o contiene una referencia circular.");
        if (field.EvaluationOption != expected)
            throw new InvalidOperationException("Las opciones de actualización del FIELD no se conservaron.");
        // Only traverse after the new parent has been evaluated, attached and
        // the table creation transaction has closed. Transient children belong
        // to the parent; disposing wrappers
        // returned by GetChildren before attachment can invalidate that tree.
        // Resident children are opened and closed exclusively by the transaction.
        foreach (var childId in field.GetChildrenIds())
        {
            if (childId.IsNull || childId.IsErased)
                throw new InvalidOperationException("El FIELD contiene un hijo que no está registrado en el dibujo.");
            var child = transaction.GetObject(childId, initialize ? OpenMode.ForWrite : OpenMode.ForRead) as Field
                ?? throw new InvalidOperationException("La referencia hija no corresponde a un FIELD.");
            if (initialize) child.EvaluationOption = expected;
            Visit(child, expected, transaction, visited, depth + 1, initialize);
        }
    }
}
