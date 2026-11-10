# Solo la instancia que solicito ZET; nunca iniciar CAD ni abrir/guardar DWG.
param(
    [Parameter(Mandatory=$true)][string]$ProgId,
    [Parameter(Mandatory=$true)][long]$WindowHandle,
    [Parameter(Mandatory=$true)][string]$LogPath
)
$ErrorActionPreference = 'Stop'
$cad = $null
$original = $null
$completed = 0
$failed = 0

function Write-ZeLog([string]$Message) {
    Add-Content -LiteralPath $LogPath -Value $Message -Encoding UTF8
}

function Wait-ZeIdle {
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        # IsQuiescent no es fiable en ZWCAD; consultar el comando del dibujo.
        try { if ([int]$cad.ActiveDocument.GetVariable('CMDACTIVE') -eq 0) { return } } catch {}
        Start-Sleep -Milliseconds 150
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'CAD esta ocupado. Termina el comando activo y vuelve a ejecutar ZET.'
}

try {
    $cad = [Runtime.InteropServices.Marshal]::GetActiveObject($ProgId)
    if ([long]$cad.HWND -ne $WindowHandle) {
        throw "La instancia COM no corresponde al CAD que solicito ZET (ventana $WindowHandle; COM $($cad.HWND)). No se modifico ningun dibujo."
    }
    Wait-ZeIdle
    $original = $cad.ActiveDocument
    $documents = @($cad.Documents | ForEach-Object { $_ })
    foreach ($document in $documents) {
        $name = '(documento cerrado)'
        try {
            Wait-ZeIdle
            $name = $document.Name
            if ([int]$document.GetVariable('CMDACTIVE') -ne 0) {
                throw 'Tiene un comando activo; se omite sin cancelarlo.'
            }
            $document.Activate()
            if ($cad.ActiveDocument.Name -ne $name) { throw 'CAD no activo el dibujo solicitado.' }
            $cad.ZoomExtents()
            $completed++
            Write-ZeLog "OK $name"
        } catch {
            $failed++
            Write-ZeLog "ERROR $name : $($_.Exception.Message)"
        }
    }
} catch {
    $failed++
    Write-ZeLog "ERROR $($_.Exception.Message)"
} finally {
    if ($null -ne $original) {
        try { Wait-ZeIdle; $original.Activate() }
        catch { $failed++; Write-ZeLog "ERROR al volver al dibujo inicial: $($_.Exception.Message)" }
    }
    $summary = "ZET: $completed dibujos encuadrados; $failed errores. No se guardaron archivos."
    Write-ZeLog $summary
    if ($null -ne $original) {
        try { $original.SendCommand("(princ `"\n$summary`")(princ)`n") }
        catch { Write-ZeLog 'Consulta este registro: no se pudo mostrar el resumen en CAD.' }
    }
}
if ($failed -gt 0) { exit 1 }
