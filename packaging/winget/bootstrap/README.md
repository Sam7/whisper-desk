# First WinGet submission

The regular release workflow uses Microsoft's official `wingetcreate update` command after `DotSam.WhisperDesk` has been accepted into `microsoft/winget-pkgs`. The first submission is a one-time, reviewed action. Generate a complete three-file manifest for the first published installer with:

```powershell
$version = '0.1.0' # use the version tag that has already been published
$remote = (git remote get-url origin).Trim()
if ($remote -match '^git@github\.com:(?<repo>[^/]+/[^/]+?)(?:\.git)?$') {
    $repo = $Matches.repo
} elseif ($remote -match '^https://github\.com/(?<repo>[^/]+/[^/]+?)(?:\.git)?$') {
    $repo = $Matches.repo
} else {
    throw "Could not derive OWNER/REPOSITORY from origin: $remote"
}
$tag = "v$version"
$installer = "WhisperDesk-$version-Setup.exe"
$url = "https://github.com/$repo/releases/download/$tag/$installer"
$sha256 = ((Invoke-RestMethod "$url.sha256").Trim() -split '\s+')[0]
.\.venv\Scripts\python scripts\release_support.py winget-bootstrap --tag $tag --repository $repo --sha256 $sha256 --output artifacts\winget-bootstrap
```

Review the generated `<version>/DotSam.WhisperDesk.yaml`, `DotSam.WhisperDesk.locale.en-US.yaml` and `DotSam.WhisperDesk.installer.yaml` files. Submit that version directory to Microsoft's `microsoft/winget-pkgs` repository in one pull request, under `manifests/d/DotSam/WhisperDesk/<version>/`. The generated files set the permanent package ID, project/issues/release links, Inno type, user scope, verified silent switches, version, product code, publisher, immutable installer URL and SHA-256.

Use the GitHub website to create the one-time fork and pull request. This initial identity/ownership review stays an explicit maintainer step. After Microsoft accepts the first version, later release tags update the same package automatically using `WINGET_CREATE_GITHUB_TOKEN`.
