param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$Version
)
$ErrorActionPreference = 'Stop'
if ((Split-Path -Leaf $Package) -ne "whisperdesk.$Version.nupkg") { throw 'Chocolatey package filename/version mismatch.' }
$install = Start-Process -FilePath 'choco.exe' -ArgumentList @('install','whisperdesk','--version',$Version,'--source',(Split-Path -Parent $Package),'--yes','--no-progress','--limit-output') -Wait -PassThru
if ($install.ExitCode -ne 0) { throw "Local Chocolatey package install failed with $($install.ExitCode)." }
$app = Join-Path $env:LOCALAPPDATA 'Programs\WhisperDesk\WhisperDesk.exe'
if (!(Test-Path -LiteralPath $app)) { throw 'Chocolatey did not install WhisperDesk.' }
$entry = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{EF14A980-E239-414E-A6F4-ABAB4AF008F2}_is1'
if ($entry.DisplayName -ne 'WhisperDesk' -or $entry.DisplayVersion -ne $Version -or $entry.Publisher -ne 'DotSam') { throw 'Chocolatey install Apps & Features metadata mismatch.' }
$remove = Start-Process -FilePath 'choco.exe' -ArgumentList @('uninstall','whisperdesk','--version',$Version,'--yes','--no-progress','--limit-output') -Wait -PassThru
if ($remove.ExitCode -ne 0) { throw "Chocolatey uninstall failed with $($remove.ExitCode)." }
if (Test-Path -LiteralPath $app) { throw 'Chocolatey uninstall left the application installed.' }
Write-Output 'Generated Chocolatey package installed and uninstalled successfully.'
