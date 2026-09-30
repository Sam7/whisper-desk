param(
    [string]$Installer,
    [string]$Output = "$PSScriptRoot\..\artifacts\installer-ui",
    [ValidateSet('system', 'light', 'dark')][string]$Theme = 'system'
)
$ErrorActionPreference = 'Stop'
if (!$Installer) {
    $candidates = @(Get-ChildItem -LiteralPath "$PSScriptRoot\..\dist\installer" -Filter 'WhisperDesk-*-Setup.exe' -File -ErrorAction SilentlyContinue)
    if ($candidates.Count -ne 1) { throw 'Pass -Installer with a versioned installer path (or leave exactly one versioned installer in dist\installer).' }
    $Installer = $candidates[0].FullName
}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type 'using System; using System.Runtime.InteropServices; public static class InstallerCaptureClick { [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, UIntPtr w, IntPtr l); }'
$themeKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
$originalTheme = Get-ItemPropertyValue -LiteralPath $themeKey -Name AppsUseLightTheme
$themeChanged = $Theme -ne 'system'
$setupProcess = $null
function SetupRoot {
    $script:setupProcess.Refresh()
    # Inno's loader spawns its own setup process.
    $candidate = Get-Process | Where-Object { $_.MainWindowTitle -like '*Whisper Desk*' -and $_.ProcessName -like '*Setup*' } | Select-Object -First 1
    if ($candidate) { return [System.Windows.Automation.AutomationElement]::FromHandle($candidate.MainWindowHandle) }
    return $null
}
function InvokeSetupButton([string]$Name) {
    $rootElement = SetupRoot
    $controls = $rootElement.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($control in $controls) {
        if ($control.Current.ClassName -eq 'TNewButton' -and $control.Current.Name.Replace('&', '').Replace('>', '').Trim() -eq $Name -and $control.Current.IsEnabled) {
            $null = [InstallerCaptureClick]::PostMessage([IntPtr]$control.Current.NativeWindowHandle, 245, [UIntPtr]::Zero, [IntPtr]::Zero)
            return
        }
    }
    throw "Setup button not found: $Name"
}
function CaptureSetup([string]$Name) {
    Start-Sleep -Milliseconds 300
    $rootElement = SetupRoot
    & "$PSScriptRoot\..\.venv\Scripts\python.exe" "$PSScriptRoot\capture_setup_window.py" $rootElement.Current.NativeWindowHandle "$Output\$Name.png"
    if ($LASTEXITCODE -ne 0) { throw 'Capture failed' }
}
try {
    if ($themeChanged) { Set-ItemProperty -LiteralPath $themeKey -Name AppsUseLightTheme -Value ([int]($Theme -eq 'light')) }
    $setupProcess = Start-Process -FilePath (Resolve-Path -LiteralPath $Installer) -WindowStyle Normal -PassThru
    $deadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Milliseconds 300
        $rootElement = SetupRoot
        $nextFound = $false
        if ($rootElement) {
            $controls = $rootElement.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
            $nextFound = @($controls | Where-Object { $_.Current.Name.Replace('&','').Replace('>','').Trim() -eq 'Next' -and $_.Current.IsEnabled }).Count -gt 0
        }
    } until ($nextFound -or (Get-Date) -gt $deadline)
    if (-not $nextFound) { throw 'Setup did not reach its first page' }
    CaptureSetup 'initial'
    InvokeSetupButton 'Next'
    CaptureSetup 'acceleration'
    InvokeSetupButton 'Next'
    CaptureSetup 'ready'
    # This capture script never clicks Install.
    InvokeSetupButton 'Cancel'
    Start-Sleep -Milliseconds 300
    $confirmation = (SetupRoot).FindFirst([System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, 'Exit Setup'))
    if ($confirmation) {
        $yes = $confirmation.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, 'Yes'))
        if ($yes) { $null = [InstallerCaptureClick]::PostMessage([IntPtr]$yes.Current.NativeWindowHandle, 245, [UIntPtr]::Zero, [IntPtr]::Zero) }
    }
    Write-Output "Captured installer pages in $Output"
} finally {
    if ($themeChanged) { Set-ItemProperty -LiteralPath $themeKey -Name AppsUseLightTheme -Value $originalTheme }
}
