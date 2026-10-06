# No argument means the historical CMD behavior: all DWGs in the current folder.
function Get-SincalDrawingSelection {
    param([string]$DrawingListFile)
    if (-not $DrawingListFile) {
        return @(Get-ChildItem -LiteralPath (Get-Location).Path -File -Filter '*.dwg')
    }
    $selection = Get-Content -LiteralPath $DrawingListFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($selection.schema -ne 1 -or -not $selection.files -or $selection.files.Count -gt 1000) {
        throw 'Lista de DWG no válida. No se usará la carpeta como alternativa.'
    }
    $seen = @{}
    foreach ($name in $selection.files) {
        if (-not [IO.Path]::IsPathRooted($name)) { throw 'Se requiere una ruta absoluta.' }
        $file = Get-Item -LiteralPath $name -ErrorAction Stop
        if ($file.PSIsContainer -or $file.Extension -ine '.dwg' -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'La selección debe contener archivos DWG regulares.' }
        if (-not $seen.ContainsKey($file.FullName)) { $seen[$file.FullName] = $true; $file }
    }
}
