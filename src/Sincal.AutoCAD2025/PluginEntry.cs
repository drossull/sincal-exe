using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.Windows;
using Autodesk.Windows;

using AcApp = Autodesk.AutoCAD.ApplicationServices.Application;

namespace Sincal.AutoCAD2025;

public class PluginEntry : IExtensionApplication
{
    private static readonly string RibbonTabId = "SINCAL_TAB";
    private static PaletteSet? _paletteSet;
    private static SincalPanel? _panel;
    private static bool _ribbonReady;

    public void Initialize()
    {
        AcApp.Idle += OnIdle;
        WriteMessage("SINCAL AutoCAD 2025 cargado.");
    }

    public void Terminate()
    {
        AcApp.Idle -= OnIdle;
        if (_paletteSet is not null)
        {
            _paletteSet.Visible = false;
            _paletteSet.Dispose();
            _paletteSet = null;
            _panel = null;
        }
    }

    [CommandMethod("SINCAL_PANEL")]
    public static void ShowPaletteCommand() => ShowPalette();

    [CommandMethod("SINCAL_ZE")]
    public static void ZoomExtentsCommand() => ZoomExtents();

    private static void OnIdle(object? sender, EventArgs e)
    {
        if (_ribbonReady)
        {
            return;
        }

        if (CreateRibbon())
        {
            _ribbonReady = true;
            AcApp.Idle -= OnIdle;
        }
    }

    private static bool CreateRibbon()
    {
        var ribbon = ComponentManager.Ribbon;
        if (ribbon is null)
        {
            return false;
        }

        foreach (RibbonTab tab in ribbon.Tabs)
        {
            if (tab.Id == RibbonTabId)
            {
                return true;
            }
        }

        var tabSincal = new RibbonTab
        {
            Title = "SINCAL",
            Id = RibbonTabId
        };

        var panelSource = new RibbonPanelSource { Title = "Herramientas" };
        var panel = new RibbonPanel { Source = panelSource };

        panelSource.Items.Add(CreateButton("Zoom Extents", "SINCAL_ZE", ZoomExtents));
        panelSource.Items.Add(CreateButton("Abrir SINCAL", "SINCAL_PANEL", ShowPalette));

        tabSincal.Panels.Add(panel);
        ribbon.Tabs.Add(tabSincal);
        return true;
    }

    private static RibbonButton CreateButton(string text, string commandName, Action action)
    {
        return new RibbonButton
        {
            Name = commandName,
            Id = commandName,
            Text = text,
            ShowText = true,
            Orientation = System.Windows.Controls.Orientation.Vertical,
            Size = RibbonItemSize.Large,
            CommandHandler = new RibbonActionHandler(action)
        };
    }

    private static void ShowPalette()
    {
        if (_paletteSet is null)
        {
            _panel = new SincalPanel();
            _paletteSet = new PaletteSet("SINCAL")
            {
                Style = PaletteSetStyles.NameEditable |
                        PaletteSetStyles.ShowAutoHideButton |
                        PaletteSetStyles.ShowCloseButton |
                        PaletteSetStyles.ShowPropertiesMenu,
                DockEnabled = (DockSides)((int)DockSides.Left + (int)DockSides.Right)
            };
            _paletteSet.AddVisual("SINCAL", _panel);
            _paletteSet.MinimumSize = new System.Drawing.Size(320, 220);
        }

        _panel?.RefreshContext();
        _paletteSet.Visible = true;
        _paletteSet.KeepFocus = true;
    }

    private static void ZoomExtents()
    {
        var doc = AcApp.DocumentManager.MdiActiveDocument;
        if (doc is null)
        {
            return;
        }

        doc.SendStringToExecute("_.ZOOM _E ", true, false, false);
    }

    internal static string GetActiveDocumentName()
    {
        var doc = AcApp.DocumentManager.MdiActiveDocument;
        return doc?.Name ?? "Sin dibujo activo";
    }

    internal static void WriteMessage(string message)
    {
        var doc = AcApp.DocumentManager.MdiActiveDocument;
        Editor? editor = doc?.Editor;
        editor?.WriteMessage($"\n[SINCAL] {message}");
    }
}

internal sealed class RibbonActionHandler : ICommand
{
    private readonly Action _action;

    public RibbonActionHandler(Action action)
    {
        _action = action;
    }

    public bool CanExecute(object? parameter) => true;

    public void Execute(object? parameter) => _action();

    public event EventHandler? CanExecuteChanged
    {
        add { }
        remove { }
    }
}

internal sealed class SincalPanel : UserControl
{
    private readonly TextBlock _hostText;
    private readonly TextBlock _docText;

    public SincalPanel()
    {
        var root = new StackPanel
        {
            Margin = new Thickness(12)
        };

        root.Children.Add(new TextBlock
        {
            Text = "SINCAL Suite 1.0 · release 28.0.0",
            FontSize = 20,
            FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 12)
        });

        _hostText = new TextBlock { Margin = new Thickness(0, 0, 0, 6) };
        _docText = new TextBlock { Margin = new Thickness(0, 0, 0, 12) };
        root.Children.Add(_hostText);
        root.Children.Add(_docText);

        var zoomButton = new Button
        {
            Content = "Zoom Extents",
            Margin = new Thickness(0, 0, 0, 8),
            Padding = new Thickness(8)
        };
        zoomButton.Click += (_, _) => PluginEntry.ZoomExtentsCommand();
        root.Children.Add(zoomButton);

        var infoButton = new Button
        {
            Content = "Actualizar contexto",
            Padding = new Thickness(8)
        };
        infoButton.Click += (_, _) => RefreshContext();
        root.Children.Add(infoButton);

        Content = root;
        RefreshContext();
    }

    public void RefreshContext()
    {
        _hostText.Text = "Host: AutoCAD 2025 (.NET 8)";
        _docText.Text = "Dibujo activo: " + PluginEntry.GetActiveDocumentName();
    }
}
