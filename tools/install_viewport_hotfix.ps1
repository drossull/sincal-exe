param([Parameter(Mandatory=$true)][string]$Repository,
      [Parameter(Mandatory=$true)][string]$BackupDirectory)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path -LiteralPath $Repository).Path
if(Test-Path -LiteralPath $BackupDirectory){throw 'Backup directory already exists'}
New-Item -ItemType Directory -Path $BackupDirectory | Out-Null
$items=@()
foreach($year in 2025,2027){
    $source=Join-Path $repo "src\Sincal.DwgProps\bin\$year\Sincal.DwgProps.dll"
    $target="C:\Program Files\SINCAL\native\dwgprops\$year\Sincal.DwgProps.dll"
    if((Get-AuthenticodeSignature -LiteralPath $source).Status -ne 'Valid'){throw 'Invalid signature'}
    $items+=@{Source=$source;Target=$target;Backup="DwgProps-$year.dll"}
}
$source=Join-Path $repo 'scripts\PURGEALL.ps1'
$new=(Get-Content -LiteralPath $source -Raw).Replace("`r`n","`n")
foreach($target in @('C:\Program Files\SINCAL\scripts\PURGEALL.ps1',
    "$env:APPDATA\Estandar SINCAL\scripts\PURGEALL.ps1",
    "$env:LOCALAPPDATA\SINCAL\resources\scripts\PURGEALL.ps1")){
    if(Test-Path -LiteralPath $target){
        $old=(Get-Content -LiteralPath $target -Raw).Replace("`r`n","`n")
        if($old.Replace("_.ZOOM`n_E`n",'') -ne $new){throw "Unexpected script content: $target"}
        $items+=@{Source=$source;Target=$target;Backup="PURGEALL-$($items.Count).ps1"}
    }
}
foreach($item in $items){
    $item.Before=(Get-FileHash -LiteralPath $item.Target).Hash
    $item.After=(Get-FileHash -LiteralPath $item.Source).Hash
    Copy-Item -LiteralPath $item.Target -Destination (Join-Path $BackupDirectory $item.Backup)
}
# All backups exist before the first installation write.
foreach($item in $items){
    if((Get-FileHash -LiteralPath $item.Target).Hash -ne $item.Before){throw 'Target changed during update'}
    Copy-Item -LiteralPath $item.Source -Destination $item.Target -Force
    if((Get-FileHash -LiteralPath $item.Target).Hash -ne $item.After){throw 'Installed hash differs'}
    Write-Output "Updated: $($item.Target)"
}
$items | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $BackupDirectory 'manifest.json') -Encoding UTF8
