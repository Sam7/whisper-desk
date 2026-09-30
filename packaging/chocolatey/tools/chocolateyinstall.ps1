$ErrorActionPreference = 'Stop'
$packageArgs = @{
    PackageName = 'whisperdesk'
    FileType = 'exe'
    SilentArgs = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'
    Url64bit = '__INSTALLER_URL__'
    Checksum64 = '__INSTALLER_SHA256__'
    ChecksumType64 = 'sha256'
    ValidExitCodes = @(0)
}
Install-ChocolateyPackage @packageArgs
