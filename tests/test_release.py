"""Release metadata must stay tag-derived and consistent across both package managers."""
import importlib.util
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from release_support import release_context, sha256_file, version_from_tag, winget_manifests, write_winget_bootstrap
from build_chocolatey import inspect_package, render_package


REPOSITORY = "ActualMaintainer/whisper-desk"
CHECKSUM = "ab" * 32


@pytest.mark.parametrize("tag, expected", [("v0.1.0", "0.1.0"), ("v1.22.300", "1.22.300")])
def test_version_extraction_is_numeric_release_tag_only(tag, expected):
    assert version_from_tag(tag) == expected


@pytest.mark.parametrize("tag", ["0.1.0", "v0.1", "v01.2.3", "v1.2.3-rc1", "v1.2.3+build", "v1.2.3\n", "v1.2.3/evil"])
def test_invalid_release_tags_fail_closed(tag):
    with pytest.raises(ValueError, match="vMAJOR.MINOR.PATCH"):
        version_from_tag(tag)


def test_context_builds_versioned_immutable_urls_from_actual_repository():
    release = release_context("v0.2.3", REPOSITORY)
    assert release["version"] == "0.2.3"
    assert release["installer_name"] == "WhisperDesk-0.2.3-Setup.exe"
    assert release["installer_url"] == "https://github.com/ActualMaintainer/whisper-desk/releases/download/v0.2.3/WhisperDesk-0.2.3-Setup.exe"
    assert release["project_url"] == "https://github.com/ActualMaintainer/whisper-desk"
    assert release["publisher"] == "DotSam"


def test_version_asset_is_written_from_tag_version(tmp_path):
    module_path = ROOT / "scripts/release_support.py"
    spec = importlib.util.spec_from_file_location("release_support_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "whisper_desk" / "assets" / "release-version.json"
    module.write_version_asset(target, "0.2.3")
    assert target.read_text(encoding="utf-8") == '{\n  "version": "0.2.3"\n}\n'
    with pytest.raises(ValueError):
        module.write_version_asset(target, "v0.2.3")


def test_sha256_calculation_is_exact(tmp_path):
    item = tmp_path / "installer.exe"
    item.write_bytes(b"tagged installer fixture\x00")
    assert sha256_file(item) == "c3a76a48e8c1ada5e21c86b9ebba4943beaa9cd8df99672d62cec36120e08e75"


def test_winget_bootstrap_consistently_carries_url_hash_and_installer_metadata(tmp_path):
    context = release_context("v0.2.3", REPOSITORY)
    generated = winget_manifests(context, CHECKSUM)
    assert set(generated) == {
        "DotSam.WhisperDesk.yaml",
        "DotSam.WhisperDesk.locale.en-US.yaml",
        "DotSam.WhisperDesk.installer.yaml",
    }
    version, locale, installer = generated.values()
    assert "PackageIdentifier: DotSam.WhisperDesk" in version
    assert "PackageVersion: 0.2.3" in version
    assert 'Publisher: DotSam' in locale
    assert "PublisherUrl: \"https://github.com/ActualMaintainer/whisper-desk\"" in locale
    assert f'InstallerUrl: "{context["installer_url"]}"' in installer
    assert f"InstallerSha256: {CHECKSUM}" in installer
    assert "InstallerType: inno" in installer
    assert "Scope: user" in installer
    assert 'Silent: "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"' in installer
    assert 'SilentWithProgress: "/SP- /SILENT /SUPPRESSMSGBOXES /NORESTART"' in installer
    assert "DisplayName: WhisperDesk" in installer
    assert "DisplayVersion: 0.2.3" in installer
    assert "Publisher: DotSam" in installer
    assert "ProductCode: \"{EF14A980-E239-414E-A6F4-ABAB4AF008F2}_is1\"" in installer
    paths = write_winget_bootstrap(context, CHECKSUM, tmp_path)
    assert all(path.parent.name == "0.2.3" and path.is_file() for path in paths)


def test_winget_rejects_bad_sha_and_context_rejects_invalid_repository():
    with pytest.raises(ValueError, match="SHA-256"):
        winget_manifests(release_context("v1.0.0", REPOSITORY), "not-a-hash")
    with pytest.raises(ValueError, match="OWNER/REPOSITORY"):
        release_context("v1.0.0", "https://github.com/Sam7/whisper-desk")


def test_chocolatey_package_generation_and_metadata_hash_and_silent_args(tmp_path):
    context = release_context("v0.2.3", REPOSITORY)
    folder = tmp_path / "package"
    nuspec = render_package(context, CHECKSUM, folder)
    ns = {"n": "http://schemas.microsoft.com/packaging/2015/06/nuspec.xsd"}
    root = ET.parse(nuspec).getroot()
    metadata = root.find("n:metadata", ns)
    assert {name: metadata.findtext(f"n:{name}", namespaces=ns) for name in ("id", "version", "title", "authors", "owners")} == {
        "id": "whisperdesk", "version": "0.2.3", "title": "WhisperDesk", "authors": "DotSam", "owners": "DotSam"
    }
    installer = (folder / "tools/chocolateyinstall.ps1").read_text(encoding="utf-8")
    assert context["installer_url"] in installer
    assert CHECKSUM in installer
    assert "Install-ChocolateyPackage @packageArgs" in installer
    assert "SilentArgs = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART'" in installer
    uninstall = (folder / "tools/chocolateyuninstall.ps1").read_text(encoding="utf-8")
    assert "unins000.exe" in uninstall and "/VERYSILENT" in uninstall
    assert "-Wait -PassThru" in uninstall
    package = tmp_path / "whisperdesk.0.2.3.nupkg"
    with zipfile.ZipFile(package, "w") as archive:
        archive.write(nuspec, nuspec.name)
        for script in (folder / "tools").iterdir():
            archive.write(script, "tools/" + script.name)
    inspect_package(package, context, CHECKSUM)


def test_chocolatey_metadata_rejects_non_sha256(tmp_path):
    with pytest.raises(ValueError, match="SHA-256"):
        render_package(release_context("v0.2.3", REPOSITORY), "wrong", tmp_path / "package")


def test_chocolatey_package_builder_refuses_stale_or_unreviewed_files(tmp_path):
    destination = tmp_path / "package"
    (destination / "tools").mkdir(parents=True)
    (destination / "tools" / "unexpected.ps1").write_text("Write-Output 'stale'", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected/stale files"):
        render_package(release_context("v0.2.3", REPOSITORY), CHECKSUM, destination)


def test_inno_app_features_name_publisher_version_and_app_identity_are_stable():
    script = (ROOT / "packaging/windows/WhisperDesk.iss").read_text(encoding="utf-8")
    assert "AppName=WhisperDesk" in script
    assert "UninstallDisplayName=WhisperDesk" in script
    assert "AppVersion={#ReleaseVersion}" in script
    assert "AppPublisher=DotSam" in script
    assert "AppId={{EF14A980-E239-414E-A6F4-ABAB4AF008F2}" in script
    assert "installer\":\"0.1.0\"" not in script


def test_release_workflow_is_tag_only_least_privilege_and_secrets_are_scoped():
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "tags:" in workflow and "'v*'" in workflow
    assert "pull_request:" not in workflow and "workflow_dispatch:" not in workflow
    assert "contents: read" in workflow and "contents: write" in workflow
    assert "secrets.CHOCOLATEY_API_KEY" in workflow
    assert "secrets.WINGET_CREATE_GITHUB_TOKEN" in workflow
    assert "--tag '${{ github.ref_name }}'" not in workflow
    assert "RELEASE_TAG: ${{ github.ref_name }}" in workflow
    assert workflow.index("Validate publishing credentials before public release") < workflow.index("Create or verify GitHub Release")
    credential_check = (ROOT / "scripts/validate_release_secrets.ps1").read_text(encoding="utf-8")
    assert "CHOCOLATEY_API_KEY" in credential_check
    assert "WINGET_CREATE_GITHUB_TOKEN" in credential_check
    winget_publisher = (ROOT / "scripts/publish_winget.ps1").read_text(encoding="utf-8")
    assert winget_publisher.count("2>&1") == 2
    assert "2>$null" not in winget_publisher
    publish_job = workflow.split("\n  publish:\n", 1)[1]
    assert "    env:" not in publish_job.splitlines()
    assert "REPOSITORY: ${{ github.repository }}" in workflow
    assert ".\\scripts\\ensure_inno_setup.ps1" in workflow
    inno_setup = (ROOT / "scripts/ensure_inno_setup.ps1").read_text(encoding="utf-8")
    assert "is-6_7_3/innosetup-6.7.3.exe" in inno_setup
    assert "Get-AuthenticodeSignature" in inno_setup and "Pyrsys B\\.V\\." in inno_setup
