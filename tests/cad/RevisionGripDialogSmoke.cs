using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using Sincal.DwgProps;
using Timer = System.Windows.Forms.Timer;
#if ZWCAD
using ZwSoft.ZwCAD.ApplicationServices;
using ZwSoft.ZwCAD.DatabaseServices;
using ZwSoft.ZwCAD.Runtime;
using CadApplication = ZwSoft.ZwCAD.ApplicationServices.Application;
#else
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
using CadApplication = Autodesk.AutoCAD.ApplicationServices.Application;
#endif

namespace Sincal.RevisionGrip;

// Compiled only when RevisionGripTests=true; no mouse, keyboard or capture automation.
public static class RevisionGripDialogSmoke
{
    private static readonly Dictionary<Document, RevisionEditor.Snapshot> Before = new Dictionary<Document, RevisionEditor.Snapshot>();
    private static Timer? timer;
    private static Action? detachTrace;
    private static string root = "";
    private static string phase = "DIALOG";
    private static bool inspected;
    private static bool failed;

    private static void Log(string message) => File.AppendAllText(Path.Combine(root, "native-result.txt"), message + Environment.NewLine);
    private static void Assert(bool value, string message)
    {
        if (!value) throw new InvalidOperationException(message);
    }
    private static IEnumerable<Control> Descendants(Control parent)
    {
        foreach (Control child in parent.Controls)
        {
            yield return child;
            foreach (var descendant in Descendants(child)) yield return descendant;
        }
    }

    [CommandMethod("SINCAL_REV_DIALOG_SMOKE", CommandFlags.Session)]
    public static void Run() => Start(false);

    [CommandMethod("SINCAL_REV_WRAPPER_SMOKE", CommandFlags.Session)]
    public static void Wrapper() => Start(true);

    private static void Start(bool wrapper)
    {
        var source = CadApplication.DocumentManager.MdiActiveDocument;
        root = Path.GetDirectoryName(source.Name)!;
        if (!Path.GetFileName(root).StartsWith("sincal-revision-grip-native-", StringComparison.Ordinal)
            || Path.GetFileName(source.Name) != "source.dwg")
            throw new InvalidOperationException("Dialog smoke only accepts the runner's temporary source.dwg.");
        try
        {
            phase = wrapper ? "WRAPPER" : "DIALOG";
            detachTrace?.Invoke();
            detachTrace = null;
            if (wrapper)
            {
                void Starting(object sender, CommandEventArgs args) => Log("WRAPPER_COMMAND_START " + args.GlobalCommandName);
                void Ended(object sender, CommandEventArgs args) => Log("WRAPPER_COMMAND_END " + args.GlobalCommandName);
                source.CommandWillStart += Starting;
                source.CommandEnded += Ended;
                detachTrace = () => { source.CommandWillStart -= Starting; source.CommandEnded -= Ended; };
            }
            Before.Clear();
            inspected = false;
            failed = false;
            foreach (Document document in CadApplication.DocumentManager)
                if (Path.GetDirectoryName(document.Name) == root
                    && new[] { "source.dwg", "target.dwg", "omitted.dwg", "fault.dwg" }.Contains(Path.GetFileName(document.Name)))
                    using (document.LockDocument()) Before.Add(document, RevisionEditor.Read(document.Database));
            var sheet = Before[source].tables.Single();
            // Reuse the first native grip result; requesting it twice without CAD's
            // grip cleanup creates duplicate native wrapper entries in AutoCAD.
            var referenceId = RevisionGripSmoke.ButtonEntity;
            Assert(!referenceId.IsNull && referenceId.Database == source.Database, "Core smoke grip source is missing");
            if (!wrapper) Assert(RevisionGripSmoke.Button != null, "Core smoke button is missing");
            timer?.Dispose();
            timer = new Timer { Interval = 100 };
            var started = DateTime.UtcNow;
            timer.Tick += (_, _) =>
            {
                var dialog = System.Windows.Forms.Application.OpenForms.Cast<Form>().OfType<RevisionDialog>().FirstOrDefault();
                if (dialog == null)
                {
                    if ((DateTime.UtcNow - started).TotalSeconds > 30)
                    {
                        timer!.Stop();
                        failed = true;
                        Log(phase + " CMDNAMES=" + CadApplication.GetSystemVariable("CMDNAMES")
                            + " CMDACTIVE=" + CadApplication.GetSystemVariable("CMDACTIVE"));
                        Log("FAIL " + phase + " editor did not open");
                    }
                    return;
                }
                timer!.Stop();
                try
                {
                    var controls = Descendants(dialog).ToArray();
                    var table = controls.OfType<DataGridView>().Single(grid => grid.AccessibleName == "Tabla de revisiones");
                    var drawings = controls.OfType<DataGridView>().Single(grid => grid.AccessibleName == "Dibujos abiertos donde aplicar la tabla");
                    Assert(table.Columns.Count == 6 && table.Rows.Count == sheet.cells.Length, "Dialog table dimensions differ");
                    for (int row = 0; row < sheet.cells.Length; row++)
                        for (int column = 0; column < 6; column++)
                        {
                            var expected = sheet.cells[row][column];
                            var cell = table.Rows[row].Cells[column];
                            Assert(Convert.ToString(cell.Value) == expected.text, "Dialog cell differs from drawing");
                            Assert(cell.ReadOnly == (RevisionTransfer.IsHeader(sheet.cells[row]) || !expected.editable), "Dialog editability differs");
                            if (expected.property != null) Assert(cell.ToolTipText == "DWGPROPS: " + expected.property, "Property tooltip missing");
                        }
                    Assert(drawings.Rows.Count == CadApplication.DocumentManager.Count, "Open drawing list is incomplete");
                    foreach (DataGridViewRow row in drawings.Rows)
                        Assert(Equals(row.Cells[0].Value, true) == (Convert.ToString(row.Cells[1].Value) == source.Name), "Unexpected selected drawing");
                    var editable = table.Rows.Cast<DataGridViewRow>().SelectMany(row => row.Cells.Cast<DataGridViewCell>()).First(cell => !cell.ReadOnly);
                    editable.Value = "CANCELAR";
                    var target = drawings.Rows.Cast<DataGridViewRow>().First(row => !row.ReadOnly && Convert.ToString(row.Cells[1].Value) != source.Name);
                    target.Cells[0].Value = true;
                    inspected = true;
                    Log("PASS dialog opened from " + (wrapper ? "REV-EDIT wrapper" : "hot grip") + "; grids, Fields and selected drawings inspected");
                }
                catch (System.Exception error) { failed = true; Log("FAIL " + phase + " " + error); }
                finally
                {
                    dialog.DialogResult = DialogResult.Cancel;
                    dialog.Close();
                    source.SendStringToExecute("SINCAL_REV_DIALOG_CHECK ", true, false, false);
                }
            };
            timer.Start();
            if (wrapper)
            {
                RevisionGripPlugin.TestSelect(referenceId);
                source.SendStringToExecute("REV-EDIT\n", true, false, false);
            }
            else
                Assert(RevisionGripSmoke.Button!.OnHotGrip(referenceId, default) == GripData.ReturnValue.GripHotToWarm, "Grip did not return to warm state");
            Log(phase + "_QUEUED");
        }
        catch (System.Exception error) { timer?.Stop(); failed = true; Log("FAIL " + phase + " " + error); }
    }

    [CommandMethod("SINCAL_REV_DIALOG_CHECK", CommandFlags.Session)]
    public static void Check()
    {
        try
        {
            Assert(inspected && !failed, "Dialog inspection failed");
            foreach (var item in Before)
                using (item.Key.LockDocument())
                    Assert(RevisionTransfer.Matches(item.Value, RevisionEditor.Read(item.Key.Database)), "Cancel changed a drawing: " + item.Key.Name);
            Log("PASS cancel preserved all drawing tables, DWGPROPS, Fields and geometry");
            Log(phase + "_DONE");
        }
        catch (System.Exception error) { Log("FAIL " + phase + " " + error); }
        finally { timer?.Dispose(); timer = null; detachTrace?.Invoke(); detachTrace = null; Before.Clear(); }
    }
}
