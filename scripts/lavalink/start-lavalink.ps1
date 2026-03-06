<#
簡易 Lavalink 啟動腳本（Windows PowerShell）

用途：在 `scripts/lavalink` 資料夾中執行，會下載 Lavalink.jar（若不存在），並用 Java 啟動。
此為測試性腳本，請先確認系統已安裝 Java 17+。
#>

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $here

$jar = Join-Path $here 'Lavalink.jar'
if (-not (Test-Path $jar)) {
    Write-Host 'Lavalink.jar 不存在，開始下載...'
    $url = 'https://github.com/freyacodes/Lavalink/releases/latest/download/Lavalink.jar'
    Invoke-WebRequest -Uri $url -OutFile $jar
    Write-Host '下載完成'
}

Write-Host '啟動 Lavalink (確保 application.yml 已設定)'
Start-Process -NoNewWindow -FilePath 'java' -ArgumentList "-jar `"$jar`"" -WorkingDirectory $here
