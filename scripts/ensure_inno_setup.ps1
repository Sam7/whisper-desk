param(
    [string]$CompilerPath = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
)
$ErrorActionPreference = 'Stop'

$compiler = [IO.Path]::GetFullPath($CompilerPath)
$releaseNotes = Join-Path (Split-Path -Parent $compiler) 'whatsnew.htm'
$versionPattern = '<a name="(?<version>[0-9]+\.[0-9]+\.[0-9]+)"'
$versionMatch = if (Test-Path -LiteralPath $releaseNotes) {
    [regex]::Match((Get-Content -LiteralPath $releaseNotes -Raw), $versionPattern)
} else { $null }

if (!$versionMatch -or $versionMatch.Groups['version'].Value -ne '6.7.3') {
    if ($PSBoundParameters.ContainsKey('CompilerPath')) {
        throw 'The supplied compiler is not Inno Setup 6.7.3.'
    }
    $installer = Join-Path $env:RUNNER_TEMP 'innosetup-6.7.3.exe'
    Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $installer -MaximumRedirection 10
    $signature = Get-AuthenticodeSignature -FilePath $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Pyrsys B\.V\.') {
        throw 'The Inno Setup installer signature is not valid or is from an unexpected publisher.'
    }
    $setup = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru
    if ($setup.ExitCode -ne 0) { throw "Signed Inno Setup installer failed with exit code $($setup.ExitCode)." }
}

if (!(Test-Path -LiteralPath $compiler)) { throw "Inno Setup compiler was not found: $compiler" }
$versionMatch = [regex]::Match((Get-Content -LiteralPath $releaseNotes -Raw), $versionPattern)
if (!$versionMatch.Success -or $versionMatch.Groups['version'].Value -ne '6.7.3') {
    throw 'The release installer must be compiled with Inno Setup 6.7.3.'
}
Write-Output "Verified Inno Setup $($versionMatch.Groups['version'].Value): $compiler"
