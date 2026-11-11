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
    private readonly RevisionEditor.Sheet _source;
    private readonly IReadOnlyList<TargetChoice> _targets;
    private readonly DataGridView _table;
    private readonly DataGridView _drawings;
    private readonly Label _status;
    private readonly Button _apply;

    public string[][] Values { get; private set; }

    public RevisionDialog(RevisionEditor.Sheet source, IReadOnlyList<TargetChoice> targets)
    {
        _source = source;
        _targets = targets;
        Values = source.cells.Select(row => row.Select(cell => cell.text).ToArray()).ToArray();
        Text = "SINCAL · Editor de revisiones";
        AutoScaleMode = AutoScaleMode.Font;
        Font = SystemFonts.MessageBoxFont;
        StartPosition = FormStartPosition.CenterParent;
        ShowInTaskbar = false;
        MinimizeBox = false;
        MinimumSize = new Size(850, 560);
        Size = new Size(1080, 720);

        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(12),
            ColumnCount = 1,
            RowCount = 7
        };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 60));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 40));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        Controls.Add(layout);

        layout.Controls.Add(Note(source.block + " · Las celdas vinculadas actualizan DWGPROPS conservando sus Fields. Las demás editan el historial. Las inserciones del mismo bloque comparten la tabla y los DWGPROPS son globales del dibujo."), 0, 0);
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
        foreach (var row in source.cells)
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
        layout.Controls.Add(_table, 0, 1);

        layout.Controls.Add(Note("Aplicar a los dibujos abiertos seleccionados:"), 0, 2);
        _drawings = Grid("Dibujos abiertos donde aplicar la tabla");
        _drawings.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
        _drawings.AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.AllCells;
        _drawings.Columns.Add(new DataGridViewCheckBoxColumn
        {
            HeaderText = "Aplicar", Width = 65, AutoSizeMode = DataGridViewAutoSizeColumnMode.None,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _drawings.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Dibujo", ReadOnly = true, FillWeight = 45,
            SortMode = DataGridViewColumnSortMode.NotSortable
        });
        _drawings.Columns.Add(new DataGridViewTextBoxColumn
        {
            HeaderText = "Tablas / estado", ReadOnly = true, FillWeight = 55,
            SortMode = DataGridViewColumnSortMode.NotSortable,
            DefaultCellStyle = new DataGridViewCellStyle { WrapMode = DataGridViewTriState.True }
        });
        foreach (var target in targets)
        {
            int index = _drawings.Rows.Add(target.Available && target.Selected, target.Name, target.Detail);
            if (!target.Available)
            {
                _drawings.Rows[index].ReadOnly = true;
                _drawings.Rows[index].DefaultCellStyle.ForeColor = SystemColors.GrayText;
                _drawings.Rows[index].Cells[0].ToolTipText = target.Detail;
            }
        }
        _drawings.CurrentCellDirtyStateChanged += (_, _) =>
        {
            if (_drawings.IsCurrentCellDirty) _drawings.CommitEdit(DataGridViewDataErrorContexts.Commit);
        };
        _drawings.CellValueChanged += (_, _) => UpdateSelection();
        layout.Controls.Add(_drawings, 0, 3);

        layout.Controls.Add(Note("Aplicar copiará la tabla completa, incluido el historial, a los dibujos marcados y actualizará sus propiedades vinculadas. Los cambios quedarán sin guardar."), 0, 4);
        _status = Note("");
        _status.AccessibleName = "Estado del editor";
        layout.Controls.Add(_status, 0, 5);
        var buttons = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill, AutoSize = true,
            FlowDirection = FlowDirection.RightToLeft, WrapContents = false
        };
        var cancel = new Button { Text = "Cancelar", AutoSize = true, DialogResult = DialogResult.Cancel };
        _apply = new Button { Text = "Aplicar", AutoSize = true };
        _apply.Click += (_, _) => Apply();
        buttons.Controls.Add(cancel);
        buttons.Controls.Add(_apply);
        layout.Controls.Add(buttons, 0, 6);
        AcceptButton = _apply;
        CancelButton = cancel;
        UpdateSelection();
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

    private bool IsSelected(int index) => _targets[index].Available && Equals(_drawings.Rows[index].Cells[0].Value, true);

    private void UpdateSelection()
    {
        if (_apply is null || _status is null) return;
        int count = Enumerable.Range(0, _targets.Count).Count(IsSelected);
        _apply.Enabled = count > 0;
        _status.ForeColor = SystemColors.ControlText;
        _status.Text = count + (count == 1 ? " dibujo seleccionado." : " dibujos seleccionados.");
    }

    private void Apply()
    {
        if (!_table.EndEdit() || !_drawings.EndEdit()) return;
        if (!Enumerable.Range(0, _targets.Count).Any(IsSelected)) return;
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
        for (int index = 0; index < _targets.Count; index++) _targets[index].Selected = IsSelected(index);
        DialogResult = DialogResult.OK;
        Close();
    }
}
