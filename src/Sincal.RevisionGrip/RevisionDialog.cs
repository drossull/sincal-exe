using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using Sincal.DwgProps;

namespace Sincal.RevisionGrip;

internal sealed class TargetChoice
{
    public string Name { get; set; } = "";
    public string Detail { get; set; } = "";
    public bool Available { get; set; }
    public bool Selected { get; set; }
}

internal sealed class RevisionDialog : Form
{
    // Same catalog used by CUSTOM-PROPS, COPY-PROPS and coordinate commands in SINCAL_PROPS.lsp.
    internal static readonly string[] StandardProperties =
    {
        "Region", "Provincia", "Comuna", "Sector", "Tramo", "Nombre_Estructura", "DM_Inicio", "DM_Fin",
        "Dibujante", "Fecha_Inf", "Fecha_Rev", "Revision", "Comentario-rev", "No_total_planos", "Nombre_Plano",
        "Coordenada_Este_Inicio", "Coordenada_Norte_Inicio", "Coordenada_Este_Fin", "Coordenada_Norte_Fin"
    };

    private readonly RevisionEditor.Sheet? _source;
    private readonly IReadOnlyList<TargetChoice> _targets;
    private readonly IReadOnlyList<TargetChoice> _propertyTargets;
    private readonly TabControl _tabs;
    private readonly DataGridView _table;
    private readonly DataGridView _drawings;
    private readonly DataGridView _properties;
    private readonly DataGridView _propertyDrawings;
    private readonly Label _status;
    private readonly Button _apply;

    public string[][] Values { get; private set; }
    public bool ApplyProperties { get; private set; }
    public IReadOnlyDictionary<string, string> PropertyValues { get; private set; }
        = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

    public RevisionDialog(RevisionEditor.Sheet source, IReadOnlyList<TargetChoice> targets)
        : this(source, targets, new Dictionary<string, string>(), Array.Empty<TargetChoice>()) { }

    public RevisionDialog(RevisionEditor.Sheet? source, IReadOnlyList<TargetChoice> targets,
        IReadOnlyDictionary<string, string> properties, IReadOnlyList<TargetChoice> propertyTargets,
        bool propertiesFirst = false)
    {
        _source = source;
        _targets = targets;
        _propertyTargets = propertyTargets;
        Values = source?.cells.Select(row => row.Select(cell => cell.text).ToArray()).ToArray() ?? Array.Empty<string[]>();
        Text = "SINCAL · Revisiones y propiedades";
        AutoScaleMode = AutoScaleMode.Font;
        Font = SystemFonts.MessageBoxFont;
        StartPosition = FormStartPosition.CenterParent;
        ShowInTaskbar = false;
        MinimizeBox = false;
        MinimumSize = new Size(850, 600);
        Size = new Size(1080, 760);

        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(12),
            ColumnCount = 1,
            RowCount = 3
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        Controls.Add(layout);

        _tabs = new TabControl { Dock = DockStyle.Fill, AccessibleName = "Secciones del editor" };
        var revisionsPage = new TabPage("Revisiones") { Enabled = source != null };
        var propertiesPage = new TabPage("Propiedades personalizadas");
        _tabs.TabPages.Add(revisionsPage);
        _tabs.TabPages.Add(propertiesPage);
        _tabs.Selecting += (_, args) => { if (source == null && args.TabPage == revisionsPage) args.Cancel = true; };
        _tabs.SelectedIndexChanged += (_, _) => UpdateSelection();
        layout.Controls.Add(_tabs, 0, 0);
        var revisionsLayout = PageLayout(revisionsPage);
        revisionsLayout.Controls.Add(Note(source == null ? "Selecciona una viñeta compatible con REV-EDIT para editar sus revisiones."
            : source.block + " · Las celdas vinculadas actualizan DWGPROPS conservando sus Fields. Las demás editan el historial. Las inserciones del mismo bloque comparten la tabla y los DWGPROPS son globales del dibujo."), 0, 0);
        _table = Grid("Tabla de revisiones");
        _table.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        var labels = new[] { "VER", "FECHA", "DIB", "REV", "APR", "DESCRIPCIÓN" };
        for (int column = 0; column < labels.Length; column++)
        {
            _table.Columns.Add(new DataGridViewTextBoxColumn
            {
                HeaderText = labels[column],
                SortMode = DataGridViewColumnSortMode.NotSortable,
                MaxInputLength = 250,
                MinimumWidth = column == 5 ? 210 : 60,
                FillWeight = column == 5 ? 45 : column == 1 ? 15 : 10
            });
        }
        foreach (var row in source?.cells ?? Array.Empty<RevisionEditor.Cell[]>())
        {
            int index = _table.Rows.Add(row.Select(cell => (object)cell.text).ToArray());
            bool header = IsHeader(row);
            for (int column = 0; column < row.Length; column++)
            {
                var cell = _table.Rows[index].Cells[column];
                cell.ReadOnly = header || !row[column].editable;
                cell.ToolTipText = row[column].property is string key ? "DWGPROPS: " + key
                    : header ? "Encabezado de la tabla" : !row[column].editable ? "Field protegido" : "Texto del historial";
                if (cell.ReadOnly) cell.Style.BackColor = SystemColors.Control;
            }
        }
        revisionsLayout.Controls.Add(_table, 0, 1);

        revisionsLayout.Controls.Add(Note("Aplicar a los dibujos abiertos seleccionados:"), 0, 2);
        _drawings = DrawingGrid("Dibujos abiertos donde aplicar la tabla", targets, "Tablas / estado");
        revisionsLayout.Controls.Add(_drawings, 0, 3);
        revisionsLayout.Controls.Add(Note("Aplicar revisiones copiará la tabla completa, incluido el historial, a los dibujos marcados y actualizará sus propiedades vinculadas. Los cambios quedarán sin guardar."), 0, 4);

        var propertiesLayout = PageLayout(propertiesPage);
        propertiesLayout.Controls.Add(Note("Valores del dibujo actual. Marca sólo las propiedades que quieres aplicar; editar un valor no lo selecciona. Los nombres de propiedad se conservan."), 0, 0);
        _properties = Grid("Propiedades personalizadas");
        _properties.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        _properties.Columns.Add(new DataGridViewCheckBoxColumn
        {
            HeaderText = "Aplicar", Width = 65, AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _properties.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Propiedad", ReadOnly = true, MinimumWidth = 215, FillWeight = 35,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _properties.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Valor", MinimumWidth = 260, FillWeight = 65,
            SortMode = DataGridViewColumnSortMode.NotSortable, MaxInputLength = 1000,
            DefaultCellStyle = new DataGridViewCellStyle { WrapMode = DataGridViewTriState.True }
        });
        foreach (var key in StandardProperties.Concat(properties.Keys).Distinct(StringComparer.OrdinalIgnoreCase))
        {
            var existing = properties.FirstOrDefault(pair => string.Equals(pair.Key, key, StringComparison.OrdinalIgnoreCase));
            int index = _properties.Rows.Add(false, existing.Key ?? key, existing.Value ?? "");
            _properties.Rows[index].Tag = existing.Value ?? "";
            _properties.Rows[index].Cells[1].Style.BackColor = SystemColors.Control;
            _properties.Rows[index].Cells[0].ToolTipText = existing.Key == null
                ? "No existe en el dibujo actual; se creará si la marcas." : "Aplicar esta propiedad a los dibujos marcados.";
        }
        _properties.CurrentCellDirtyStateChanged += (_, _) =>
        {
            if (_properties.IsCurrentCellDirty && _properties.CurrentCell is DataGridViewCheckBoxCell)
                _properties.CommitEdit(DataGridViewDataErrorContexts.Commit);
        };
        _properties.CellValueChanged += (_, _) => UpdateSelection();
        propertiesLayout.Controls.Add(_properties, 0, 1);
        propertiesLayout.Controls.Add(Note("Aplicar a los dibujos abiertos seleccionados (no requieren viñeta):"), 0, 2);
        _propertyDrawings = DrawingGrid("Dibujos abiertos donde aplicar propiedades", propertyTargets, "Estado");
        propertiesLayout.Controls.Add(_propertyDrawings, 0, 3);
        propertiesLayout.Controls.Add(Note("Sólo se aplicarán las propiedades marcadas. Un valor vacío marcado dejará la propiedad vacía; las faltantes se crearán. Las demás propiedades se conservan. Los cambios de la pestaña Revisiones no se aplican aquí. No guarda los dibujos."), 0, 4);

        _status = Note("");
        _status.AccessibleName = "Estado del editor";
        layout.Controls.Add(_status, 0, 1);
        var buttons = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, AutoSize = true,
            FlowDirection = FlowDirection.RightToLeft, WrapContents = false
        };
        var cancel = new Button { Text = "Cancelar", AutoSize = true, DialogResult = DialogResult.Cancel };
        _apply = new Button { Text = "Aplicar revisiones", AutoSize = true };
        _apply.Click += (_, _) => Apply();
        buttons.Controls.Add(cancel);
        buttons.Controls.Add(_apply);
        layout.Controls.Add(buttons, 0, 2);
        AcceptButton = _apply;
        CancelButton = cancel;
        _tabs.SelectedIndex = propertiesFirst || source == null ? 1 : 0;
        UpdateSelection();
    }

    private static TableLayoutPanel PageLayout(TabPage page)
    {
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(8), ColumnCount = 1, RowCount = 5 };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 60));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 40));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        page.Controls.Add(layout);
        return layout;
    }

    private DataGridView DrawingGrid(string accessibleName, IReadOnlyList<TargetChoice> targets, string detailHeader)
    {
        var grid = Grid(accessibleName);
        grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        grid.Columns.Add(new DataGridViewCheckBoxColumn
        {
            HeaderText = "Aplicar", Width = 65, AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Dibujo", ReadOnly = true, FillWeight = 45,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        grid.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = detailHeader, ReadOnly = true, FillWeight = 55,
            SortMode = DataGridViewColumnSortMode.NotSortable,
            DefaultCellStyle = new DataGridViewCellStyle { WrapMode = DataGridViewTriState.True }
        });
        foreach (var target in targets)
        {
            int index = grid.Rows.Add(target.Available && target.Selected, target.Name, target.Detail);
            if (!target.Available)
            {
                grid.Rows[index].ReadOnly = true;
                grid.Rows[index].DefaultCellStyle.ForeColor = SystemColors.GrayText;
                grid.Rows[index].Cells[0].ToolTipText = target.Detail;
            }
        }
        grid.CurrentCellDirtyStateChanged += (_, _) =>
        {
            if (grid.IsCurrentCellDirty) grid.CommitEdit(DataGridViewDataErrorContexts.Commit);
        };
        grid.CellValueChanged += (_, _) => UpdateSelection();
        return grid;
    }

    private static DataGridView Grid(string accessibleName) => new DataGridView
    {
        Dock = DockStyle.Fill,
        AccessibleName = accessibleName,
        AllowUserToAddRows = false,
        AllowUserToDeleteRows = false,
        AllowUserToOrderColumns = false,
        RowHeadersVisible = false,
        BackgroundColor = SystemColors.Window,
        BorderStyle = BorderStyle.FixedSingle,
        SelectionMode = DataGridViewSelectionMode.CellSelect,
        MultiSelect = false,
        EditMode = DataGridViewEditMode.EditOnEnter,
        AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.AllCells,
        Margin = new Padding(0, 4, 0, 8)
    };

    private static Label Note(string text) => new Label
    {
        Text = text, AutoSize = true, Dock = DockStyle.Fill,
        Margin = new Padding(0, 3, 0, 6)
    };

    private static bool IsHeader(RevisionEditor.Cell[] cells)
    {
        if (cells.Length < 2) return false;
        string first = cells[0].text.Trim().ToUpperInvariant();
        return (first == "VER" || first == "REV" || first == "REVISION" || first == "REVISIÓN")
            && cells[1].text.Trim().Equals("FECHA", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsSelected(DataGridView drawings, IReadOnlyList<TargetChoice> targets, int index) =>
        targets[index].Available && Equals(drawings.Rows[index].Cells[0].Value, true);

    private bool PropertiesTab => _tabs.SelectedIndex == 1;

    private void UpdateSelection()
    {
        if (_apply is null || _status is null) return;
        var targets = PropertiesTab ? _propertyTargets : _targets;
        var drawings = PropertiesTab ? _propertyDrawings : _drawings;
        int count = Enumerable.Range(0, targets.Count).Count(index => IsSelected(drawings, targets, index));
        int properties = _properties.Rows.Cast<DataGridViewRow>().Count(row => Equals(row.Cells[0].Value, true));
        _apply.Text = PropertiesTab ? "Aplicar propiedades" : "Aplicar revisiones";
        _apply.Enabled = count > 0 && (PropertiesTab ? properties > 0 : _source != null);
        _status.ForeColor = SystemColors.ControlText;
        _status.Text = (PropertiesTab ? properties + (properties == 1 ? " propiedad marcada · " : " propiedades marcadas · ") : "")
            + count + (count == 1 ? " dibujo seleccionado." : " dibujos seleccionados.");
    }

    private void Apply()
    {
        if (PropertiesTab) { ApplySelectedProperties(); return; }
        if (_source == null) return;
        if (!_table.EndEdit() || !_drawings.EndEdit()) return;
        if (!Enumerable.Range(0, _targets.Count).Any(index => IsSelected(_drawings, _targets, index))) return;
        var values = new string[_source.cells.Length][];
        for (int row = 0; row < values.Length; row++)
        {
            values[row] = new string[_source.cells[row].Length];
            for (int column = 0; column < values[row].Length; column++)
            {
                var cell = _table.Rows[row].Cells[column];
                string value = Convert.ToString(cell.Value) ?? "";
                // Protected cells may contain expressions: preserve them without treating them as new input.
                if (!cell.ReadOnly && (value.Length > 250 || value.Any(char.IsControl)
                    || value.Contains("%<") || value.IndexOfAny(new[] { '\\', '{', '}' }) >= 0))
                {
                    _table.CurrentCell = cell;
                    _table.Focus();
                    _status.ForeColor = Color.Firebrick;
                    _status.Text = "Fila " + (row + 1) + ", " + _table.Columns[column].HeaderText
                        + ": usa texto simple de hasta 250 caracteres, sin saltos de línea ni códigos de Field.";
                    return;
                }
                values[row][column] = value;
            }
        }
        Values = values;
        ApplyProperties = false;
        for (int index = 0; index < _targets.Count; index++) _targets[index].Selected = IsSelected(_drawings, _targets, index);
        DialogResult = DialogResult.OK;
        Close();
    }

    private void ApplySelectedProperties()
    {
        if (!_properties.EndEdit() || !_propertyDrawings.EndEdit()) return;
        if (!Enumerable.Range(0, _propertyTargets.Count).Any(index => IsSelected(_propertyDrawings, _propertyTargets, index))) return;
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (DataGridViewRow row in _properties.Rows)
        {
            if (!Equals(row.Cells[0].Value, true)) continue;
            string key = Convert.ToString(row.Cells[1].Value) ?? "";
            string value = Convert.ToString(row.Cells[2].Value) ?? "";
            // Preserve unchanged legacy values; each destination validates whether it would change.
            if (value != (string?)row.Tag && (value.Length > 1000 || value.Any(char.IsControl) || value.Contains("%<")))
            {
                _properties.CurrentCell = row.Cells[2];
                _properties.Focus();
                _status.ForeColor = Color.Firebrick;
                _status.Text = key + ": usa hasta 1000 caracteres, sin saltos de línea, caracteres de control ni códigos de Field.";
                return;
            }
            values.Add(key, value);
        }
        if (values.Count == 0) return;
        PropertyValues = values;
        ApplyProperties = true;
        for (int index = 0; index < _propertyTargets.Count; index++)
            _propertyTargets[index].Selected = IsSelected(_propertyDrawings, _propertyTargets, index);
        DialogResult = DialogResult.OK;
        Close();
    }
}
