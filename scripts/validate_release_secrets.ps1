$ErrorActionPreference = 'Stop'

if (!$env:CHOCOLATEY_API_KEY) {
    throw 'Configure the CHOCOLATEY_API_KEY Actions secret before publishing a release.'
}
if (!$env:GH_TOKEN) {
    throw 'The publish job needs its built-in GitHub token to inspect WinGet and publish release assets.'
}

$manifestRoot = 'manifests/d/DotSam/WhisperDesk'
$listing = & gh api "repos/microsoft/winget-pkgs/contents/$manifestRoot?ref=master" --jq '.[].name' 2>&1
$status = $LASTEXITCODE
if ($status -eq 0) {
    if (!$env:WINGET_CREATE_GITHUB_TOKEN) {
        throw 'DotSam.WhisperDesk is registered; configure WINGET_CREATE_GITHUB_TOKEN before publishing its next update.'
    }
} elseif (($listing -join "`n") -match 'Not Found|HTTP 404') {
    Write-Warning 'DotSam.WhisperDesk is not registered yet; the initial reviewed WinGet submission is still required.'
} else {
    throw "Could not safely determine the WinGet package registration status: $($listing -join ' ')"
}

Write-Output 'Release publishing credentials are ready.'
