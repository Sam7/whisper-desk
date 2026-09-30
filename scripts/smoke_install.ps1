param(
    [string]$Installer,
    [string]$Output = "$PSScriptRoot\..\artifacts\installer-smoke",
    [switch]$Install
)
if (-not $Install) { throw 'Pass -Install to exercise real installation in the current Windows account.' }
$ErrorActionPreference = 'Stop'
if (!$Installer) {
    $candidates = @(Get-ChildItem -LiteralPath "$PSScriptRoot\..\dist\installer" -Filter 'WhisperDesk-*-Setup.exe' -File -ErrorAction SilentlyContinue)
    if ($candidates.Count -ne 1) { throw 'Pass -Installer with a versioned installer path (or leave exactly one versioned installer in dist\installer).' }
    $Installer = $candidates[0].FullName
}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type 'using System; using System.Runtime.InteropServices; public static class SmokeSetupClick { [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, UIntPtr w, IntPtr l); }'
New-Item -ItemType Directory -Path $Output -Force | Out-Null
function SetupRoot {
    $candidate = Get-Process | Where-Object { $_.MainWindowTitle -like '*Whisper Desk*' -and $_.ProcessName -like 'WhisperDesk-Setup*' } | Select-Object -First 1
    if ($candidate) { return [System.Windows.Automation.AutomationElement]::FromHandle($candidate.MainWindowHandle) }
    return $null
}
function Controls {
    $rootElement = SetupRoot
    if ($rootElement) { return $rootElement.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition) }
    return @()
}
function Button([string]$Name) {
    return Controls | Where-Object { $_.Current.ClassName -eq 'TNewButton' -and $_.Current.IsEnabled -and $_.Current.Name.Replace('&','').Replace('>','').Trim() -eq $Name } | Select-Object -First 1
}
function Click($Control) {
    if (-not $Control) { throw 'Expected setup control was not found' }
    $null = [SmokeSetupClick]::PostMessage([IntPtr]$Control.Current.NativeWindowHandle, 245, [UIntPtr]::Zero, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 400
}
function Capture([string]$Name) {
    $rootElement = SetupRoot
    & "$PSScriptRoot\..\.venv\Scripts\python.exe" "$PSScriptRoot\capture_setup_window.py" $rootElement.Current.NativeWindowHandle "$Output\$Name.png"
    if ($LASTEXITCODE -ne 0) { throw 'Setup screenshot failed' }
}
$started = Get-Date
$setupProcess = Start-Process -FilePath (Resolve-Path -LiteralPath $Installer) -ArgumentList '/NORESTART',"/LOG=$([IO.Path]::GetFullPath($Output))\install.log" -WindowStyle Normal -PassThru
$deadline = (Get-Date).AddSeconds(90)
while (-not (Button 'Next') -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300 }
Capture 'initial'
Click (Button 'Next')
Capture 'acceleration'
Click (Button 'Next')
Capture 'ready'
Click (Button 'Install')
$captured = @{}
$deadline = (Get-Date).AddMinutes(20)
while ((Get-Date) -lt $deadline) {
    if (Button 'Finish') { break }
    $labels = @(Controls | ForEach-Object { $_.Current.Name })
    foreach ($label in $labels) {
        if ($label -match '^(Downloading |Installing transcription files|Checking transcription|Checking installed application)') {
            $key = ($label -replace '[^a-zA-Z0-9]+', '-').Trim('-').ToLowerInvariant()
            if (-not $captured.ContainsKey($key)) {
                Capture $key
                $captured[$key] = $true
                Write-Output $label
            }
        }
    }
    Start-Sleep -Milliseconds 500
}
if (-not (Button 'Finish')) { throw 'Installation did not complete within 20 minutes. Inspect the wizard and installer log.' }
Capture 'complete'
# Do not launch a second normal app window from this smoke test.
$launch = Controls | Where-Object { $_.Current.Name -like '*Open Whisper Desk*' } | Select-Object -First 1
if ($launch) {
    # Inno uses an owner-drawn checklist, not a Win32 checkbox (BM_SETCHECK).
    $null = [SmokeSetupClick]::PostMessage([IntPtr]$launch.Current.NativeWindowHandle, 390, [UIntPtr]::Zero, [IntPtr]::Zero)
    $null = [SmokeSetupClick]::PostMessage([IntPtr]$launch.Current.NativeWindowHandle, 256, [UIntPtr]32, [IntPtr]::Zero)
    $null = [SmokeSetupClick]::PostMessage([IntPtr]$launch.Current.NativeWindowHandle, 257, [UIntPtr]32, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 200
}
Click (Button 'Finish')
$verification = Get-Content "$env:LOCALAPPDATA\WhisperDesk\setup-verification.json" -Raw | ConvertFrom-Json
if ($verification.exit_code -ne 0) { throw 'Installed application verification failed' }
$report = [pscustomobject]@{elapsed_seconds=[math]::Round(((Get-Date)-$started).TotalSeconds,1); backend=$verification.device; screenshots=@($captured.Keys); verification=$verification}
$report | ConvertTo-Json -Depth 8 | Set-Content "$Output\report.json"
Write-Output "Installation verified: $($verification.device); report at $Output\report.json"
