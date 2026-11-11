using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Windows.Forms;
using Sincal.RevisionGrip;

// Standalone WinForms regression: compile only this file and RevisionDialog.cs,
// without CAD references. No Show/ShowDialog, mouse, keyboard or capture calls.
internal static class RevisionDialogStandalone
{
    private static void Check(bool value, string message)
    {
        if (!value) throw new InvalidOperationException(message);
    }

    private static IEnumerable<Control> Controls(Control parent)
    {
        foreach (Control child in parent.Controls)
        {
            yield return child;
            foreach (var descendant in Controls(child)) yield return descendant;
        }
    }

    private static T Control<T>(Form dialog, string name) where T : Control
    {
        var control = Controls(dialog).OfType<T>().Single(item => item.AccessibleName == name);
        // Tab selection notifications need a native handle, even while the form stays hidden.
        _ = control.Handle;
        return control;
    }

    private static void Apply(RevisionDialog dialog) => typeof(RevisionDialog)
        .GetMethod("Apply", BindingFlags.Instance | BindingFlags.NonPublic)!.Invoke(dialog, null);

    private static TargetChoice[] Targets() => new[]
    {
        new TargetChoice { Name = "Actual.dwg", Available = true, Selected = true },
        new TargetChoice { Name = "Otro.dwg", Available = true },
        new TargetChoice { Name = "Lectura.dwg", Detail = "Sólo lectura", Available = false }
    };

    private static Sincal.DwgProps.RevisionEditor.Sheet Sheet() => new Sincal.DwgProps.RevisionEditor.Sheet
    {
        block = "VIÑETA",
        cells = new[]
        {
            new[] { Cell("A", true, "Revision"), Cell("Fecha", true), Cell("D", true), Cell("R", true), Cell("P", true), Cell("FIELD", false) },
            new[] { Cell("VER", true), Cell("FECHA", true), Cell("DIB", true), Cell("REV", true), Cell("APR", true), Cell("DESCRIPCIÓN", true) }
        }
    };

    private static Sincal.DwgProps.RevisionEditor.Cell Cell(string text, bool editable, string? property = null) =>
        new Sincal.DwgProps.RevisionEditor.Cell { text = text, editable = editable, property = property };

    private static readonly IReadOnlyDictionary<string, string> Properties = new Dictionary<string, string>
    {
        ["region"] = "Metropolitana",
        ["Personalizada"] = @"C:\Planos\{original}"
    };

    [STAThread]
    private static void Main()
    {
        var revisionTargets = Targets();
        var propertyTargets = Targets();
        using (var dialog = new RevisionDialog(Sheet(), revisionTargets, Properties, propertyTargets))
        {
            var tabs = Control<TabControl>(dialog, "Secciones del editor");
            var properties = Control<DataGridView>(dialog, "Propiedades personalizadas");
            var revisions = Control<DataGridView>(dialog, "Tabla de revisiones");
            var drawings = Control<DataGridView>(dialog, "Dibujos abiertos donde aplicar propiedades");
            var apply = Controls(dialog).OfType<Button>().Single(button => button.Text == "Aplicar revisiones");
            Check(tabs.SelectedIndex == 0 && apply.Enabled, "Revision command must retain its default tab");
            Check(properties.Rows.Count == 20 && properties.Columns[1].ReadOnly, "Catalog must include source keys once and preserve names");
            Check(Convert.ToString(properties.Rows[0].Cells[1].Value) == "region", "Existing property spelling changed");
            Check(properties.Rows.Cast<DataGridViewRow>().All(row => Equals(row.Cells[0].Value, false)), "Properties were implicitly selected");
            Check(revisions.Rows[0].Cells[5].ReadOnly && revisions.Rows[1].Cells.Cast<DataGridViewCell>().All(cell => cell.ReadOnly), "Protected revision cells became editable");
            Check(drawings.Rows[2].ReadOnly && Equals(drawings.Rows[2].Cells[0].Value, false), "Read-only destination is selectable");
            tabs.SelectedIndex = 1;
            Check(apply.Text == "Aplicar propiedades" && !apply.Enabled, "Properties require explicit selection");
            revisions.Rows[0].Cells[0].Value = "HIDDEN";
            properties.Rows[0].Cells[2].Value = "";
            Check(Equals(properties.Rows[0].Cells[0].Value, false), "Editing must not select a property implicitly");
            properties.Rows[0].Cells[0].Value = true;
            drawings.Rows[0].Cells[0].Value = false;
            drawings.Rows[1].Cells[0].Value = true;
            Control<DataGridView>(dialog, "Dibujos abiertos donde aplicar la tabla").Rows[0].Cells[0].Value = false;
            Check(apply.Enabled, "Selected property and drawing must enable Apply");
            Apply(dialog);
            Check(dialog.DialogResult == DialogResult.OK && dialog.ApplyProperties, "Property mode result missing");
            Check(dialog.PropertyValues.Count == 1 && dialog.PropertyValues["region"] == "", "Selected blank must be an explicit value");
            Check(dialog.Values[0][0] == "A" && revisionTargets[0].Selected, "Applying properties consumed hidden revisions");
            Check(!propertyTargets[0].Selected && propertyTargets[1].Selected, "Property destination selection was lost");
        }

        revisionTargets = Targets();
        propertyTargets = Targets();
        using (var dialog = new RevisionDialog(Sheet(), revisionTargets, Properties, propertyTargets, true))
        {
            var tabs = Control<TabControl>(dialog, "Secciones del editor");
            Check(tabs.SelectedIndex == 1, "Properties command must open its tab");
            var properties = Control<DataGridView>(dialog, "Propiedades personalizadas");
            properties.Rows[0].Cells[0].Value = true;
            properties.Rows[0].Cells[2].Value = "bad\nvalue";
            Control<DataGridView>(dialog, "Dibujos abiertos donde aplicar propiedades").Rows[0].Cells[0].Value = false;
            tabs.SelectedIndex = 0;
            Control<DataGridView>(dialog, "Tabla de revisiones").Rows[0].Cells[0].Value = "B";
            Apply(dialog);
            Check(dialog.DialogResult == DialogResult.OK && !dialog.ApplyProperties && dialog.Values[0][0] == "B", "Revisions must apply independently");
            Check(dialog.PropertyValues.Count == 0 && propertyTargets[0].Selected, "Applying revisions consumed hidden properties");
        }

        using (var dialog = new RevisionDialog(null, Array.Empty<TargetChoice>(), Properties, Targets()))
        {
            var tabs = Control<TabControl>(dialog, "Secciones del editor");
            Check(tabs.SelectedIndex == 1 && !tabs.TabPages[0].Enabled, "Properties must work without a vignette");
            tabs.SelectedIndex = 0;
            Check(tabs.SelectedIndex == 1, "Unavailable revision tab accepted selection");
            var properties = Control<DataGridView>(dialog, "Propiedades personalizadas");
            properties.Rows[0].Cells[0].Value = true;
            foreach (var invalid in new[] { "%<field>%", "bad\nvalue", new string('x', 1001) })
            {
                properties.Rows[0].Cells[2].Value = invalid;
                Apply(dialog);
                Check(dialog.DialogResult != DialogResult.OK && dialog.PropertyValues.Count == 0, "Invalid selected value was accepted");
            }
            properties.Rows[0].Cells[2].Value = @"C:\Planos\{revisión}";
            Apply(dialog);
            Check(dialog.DialogResult == DialogResult.OK && dialog.PropertyValues["region"] == @"C:\Planos\{revisión}", "Ordinary paths and braces must remain valid");
        }

        foreach (var legacy in new[] { "%<old-field>%", new string('x', 1001) })
        using (var dialog = new RevisionDialog(null, Array.Empty<TargetChoice>(),
            new Dictionary<string, string> { ["Region"] = legacy }, Targets()))
        {
            Control<DataGridView>(dialog, "Propiedades personalizadas").Rows[0].Cells[0].Value = true;
            Apply(dialog);
            Check(dialog.DialogResult == DialogResult.OK && dialog.PropertyValues["Region"] == legacy,
                "Selecting an unchanged legacy value must defer destination-specific validation");
        }

        propertyTargets = Targets();
        using (var dialog = new RevisionDialog(null, Array.Empty<TargetChoice>(), Properties, propertyTargets))
        {
            var properties = Control<DataGridView>(dialog, "Propiedades personalizadas");
            properties.Rows[0].Cells[0].Value = true;
            properties.Rows[0].Cells[2].Value = "Cancelled";
            Control<DataGridView>(dialog, "Dibujos abiertos donde aplicar propiedades").Rows[0].Cells[0].Value = false;
            dialog.DialogResult = DialogResult.Cancel;
            dialog.Close();
            Check(dialog.PropertyValues.Count == 0 && propertyTargets[0].Selected, "Cancel changed output or selections");
        }
        Console.WriteLine("PASS property catalog, explicit selection, active-tab isolation, validation, no-vignette and Cancel");
    }
}

namespace Sincal.DwgProps
{
    internal static class RevisionEditor
    {
        internal sealed class Cell
        {
            public string text = "";
            public bool editable;
            public string? property;
        }
        internal sealed class Sheet
        {
            public string block = "";
            public Cell[][] cells = Array.Empty<Cell[]>();
        }
    }
}
