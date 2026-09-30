# Releases and package managers

WhisperDesk releases are driven by one source of truth: a Git tag in the form `vMAJOR.MINOR.PATCH`. For example, `v0.2.3` produces app and installer version `0.2.3`, a GitHub Release named `v0.2.3`, `WhisperDesk-0.2.3-Setup.exe`, Chocolatey version `0.2.3` and WinGet version `0.2.3`. The actual `OWNER/REPOSITORY` comes from the GitHub Actions tag context, so release and support links follow the repository location.

## One-time account and secret setup

Create these **Actions repository secrets** under GitHub → Settings → Secrets and variables → Actions:

| Secret | Purpose |
| --- | --- |
| `CHOCOLATEY_API_KEY` | API key for an account authorized to publish `whisperdesk` to the [Chocolatey Community Repository](https://community.chocolatey.org/). |
| `WINGET_CREATE_GITHUB_TOKEN` | Classic GitHub personal access token with `public_repo`, used by Microsoft's official WinGetCreate CLI to submit update pull requests. |

The workflow uses the built-in `GITHUB_TOKEN` for the GitHub Release; it does not need a separate secret. Do not put credentials in repository files or workflow YAML.

For Chocolatey, create and verify the publisher account, enable package publishing, and confirm that the account can claim/push the `whisperdesk` package ID before the first release. Chocolatey validates new package submissions. If the ID is already registered by another publisher, resolve that ownership conflict before tagging a release; the package ID must remain `whisperdesk`.

For WinGet, the first package submission is a one-time manual review. Once the first `DotSam.WhisperDesk` manifest is accepted into `microsoft/winget-pkgs`, later tag releases submit update pull requests automatically. Follow [the initial WinGet submission instructions](../packaging/winget/bootstrap/README.md) using the installer and checksum sidecar from a published GitHub Release. The release workflow warns and skips the WinGet update while this package identifier is not yet registered.

## Publish a release

After the secrets are configured and package identities are ready, create and push a version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The tag workflow validates the exact semantic-version format, runs the test suite, builds the app and Inno Setup installer, verifies unattended install/uninstall and Apps & Features metadata, builds the Chocolatey package, and generates the initial WinGet manifests as a workflow artifact. Only after those checks pass does the publish job create or verify the immutable GitHub Release asset and its SHA-256. Chocolatey and WinGet use that exact versioned URL; they never point at a mutable `latest` download.

The release scripts are safe to rerun for the same tag and commit: they verify the existing GitHub asset, checksum, and package metadata before skipping an already completed publication. A different commit or different bytes for a published version fails instead of replacing a versioned artifact. The workflow does not run package-manager publication for ordinary branch or pull-request CI.

If the tag workflow's build-and-validate job succeeds but publication later fails, do not move or recreate the release tag. Use the manual recovery workflow with the original run ID and exact tag:

```powershell
gh workflow run "Recover validated release publication" --ref main `
  -f source_run_id=36681391842 `
  -f release_tag=v0.1.0
```

Recovery downloads the original validated artifact, confirms its build job succeeded, checks the current tag still points to that run's commit, and rechecks the installer and sidecar hashes plus package metadata before resuming the idempotent publish steps. Artifacts are retained for 10 days, so recover a failed publication promptly. This path does not rebuild or retarget an already-published version.

Install after package submissions are available:

```powershell
winget install DotSam.WhisperDesk
```

```powershell
choco install whisperdesk
```

The GitHub Release is also available from the repository's Releases page. First-time package indexing and moderation are controlled by Microsoft and Chocolatey, so package-manager availability can lag the release upload.
