"""Release metadata and package manifest helpers. Tags are the sole release version input."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = "WhisperDesk"
PUBLISHER = "DotSam"
WINGET_ID = "DotSam.WhisperDesk"
CHOCO_ID = "whisperdesk"
APP_ID = "{EF14A980-E239-414E-A6F4-ABAB4AF008F2}_is1"
VERSION_RE = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def version_from_tag(tag: str) -> str:
    match = VERSION_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"Invalid release tag {tag!r}; expected vMAJOR.MINOR.PATCH (for example v0.2.3)")
    return ".".join(match.groups())


def release_context(tag: str, repository: str) -> dict[str, str]:
    version = version_from_tag(tag)
    if not REPOSITORY_RE.fullmatch(repository):
        raise ValueError("Repository must be OWNER/REPOSITORY")
    filename = f"{PRODUCT}-{version}-Setup.exe"
    url = f"https://github.com/{repository}/releases/download/{tag}/{filename}"
    return {"tag": tag, "version": version, "repository": repository,
            "product": PRODUCT, "publisher": PUBLISHER, "winget_id": WINGET_ID,
            "chocolatey_id": CHOCO_ID, "installer_name": filename,
            "installer_url": url, "release_url": f"https://github.com/{repository}/releases/tag/{tag}",
            "project_url": f"https://github.com/{repository}",
            "publisher_url": f"https://github.com/{repository}",
            "support_url": f"https://github.com/{repository}/issues",
            "product_code": APP_ID}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_version_asset(path: Path, version: str) -> None:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise ValueError("Version must be a numeric MAJOR.MINOR.PATCH release version")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": version}, indent=2) + "\n", encoding="utf-8")


def _yaml_string(value: str) -> str:
    # JSON double-quoted strings are a valid YAML scalar and safely escape metadata.
    return json.dumps(value, ensure_ascii=False)


def winget_manifests(context: dict[str, str], checksum: str) -> dict[str, str]:
    if not SHA256_RE.fullmatch(checksum):
        raise ValueError("Installer SHA-256 must be 64 lowercase hexadecimal characters")
    q = _yaml_string
    base = WINGET_ID
    version_manifest = (f"PackageIdentifier: {WINGET_ID}\nPackageVersion: {context['version']}\n"
                       "DefaultLocale: en-US\nManifestType: version\nManifestVersion: 1.10.0\n")
    locale_manifest = "\n".join([
        "PackageIdentifier: " + WINGET_ID,
        "PackageVersion: " + context["version"],
        "PackageLocale: en-US",
        "Publisher: " + PUBLISHER,
        "PublisherUrl: " + q(context["publisher_url"]),
        "PublisherSupportUrl: " + q(context["support_url"]),
        "Author: " + PUBLISHER,
        "PackageName: " + PRODUCT,
        "PackageUrl: " + q(context["project_url"]),
        "License: Proprietary",
        "Copyright: " + q("Copyright (c) DotSam"),
        "ShortDescription: " + q("Private, offline voice transcription for Windows, powered by Whisper Turbo."),
        "Description: " + q("WhisperDesk is a native Windows desktop app for fast local speech-to-text. Audio stays on your computer. Transcription works offline after setup, with NVIDIA GPU acceleration or CPU mode."),
        "Moniker: whisperdesk",
        "Tags:",
        "  - dictation",
        "  - offline",
        "  - privacy",
        "  - speech-to-text",
        "  - transcription",
        "  - whisper",
        "ReleaseNotesUrl: " + q(context["release_url"]),
        "ManifestType: defaultLocale",
        "ManifestVersion: 1.10.0",
        "",
    ])
    installer_manifest = "\n".join([
        "PackageIdentifier: " + WINGET_ID,
        "PackageVersion: " + context["version"],
        "InstallerLocale: en-US",
        "Platform:",
        "  - Windows.Desktop",
        "MinimumOSVersion: 10.0.22000.0",
        "UpgradeBehavior: install",
        "InstallModes:",
        "  - interactive",
        "  - silent",
        "  - silentWithProgress",
        "Installers:",
        "  - Architecture: x64",
        "    Scope: user",
        "    ElevationRequirement: elevationProhibited",
        "    InstallerUrl: " + q(context["installer_url"]),
        "    InstallerSha256: " + checksum,
        "    InstallerType: inno",
        "    InstallerSwitches:",
        '      Silent: "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"',
        '      SilentWithProgress: "/SP- /SILENT /SUPPRESSMSGBOXES /NORESTART"',
        "    ProductCode: " + q(APP_ID),
        "    AppsAndFeaturesEntries:",
        "      - DisplayName: " + PRODUCT,
        "        DisplayVersion: " + context["version"],
        "        Publisher: " + PUBLISHER,
        "        ProductCode: " + q(APP_ID),
        "ManifestType: installer",
        "ManifestVersion: 1.10.0",
        "",
    ])
    return {f"{base}.yaml": version_manifest,
            f"{base}.locale.en-US.yaml": locale_manifest,
            f"{base}.installer.yaml": installer_manifest}


def write_winget_bootstrap(context: dict[str, str], checksum: str, output: Path) -> list[Path]:
    output = Path(output)
    written = []
    for name, contents in winget_manifests(context, checksum).items():
        target = output / context["version"] / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8", newline="\n")
        written.append(target)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    tag = sub.add_parser("context", help="Validate a vMAJOR.MINOR.PATCH tag and print immutable release metadata")
    tag.add_argument("--tag", required=True)
    tag.add_argument("--repository", required=True)
    tag.add_argument("--output", type=Path)
    tag.add_argument("--github-output", action="store_true")
    asset = sub.add_parser("winget-bootstrap", help="Generate first-submission WinGet manifests")
    asset.add_argument("--tag", required=True)
    asset.add_argument("--repository", required=True)
    asset.add_argument("--sha256", required=True)
    asset.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        context = release_context(args.tag, args.repository)
        if args.command == "context":
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
            if args.github_output:
                with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
                    for key, value in context.items():
                        stream.write(f"{key}={value}\n")
            if not args.output and not args.github_output:
                print(json.dumps(context, indent=2))
        else:
            written = write_winget_bootstrap(context, args.sha256, args.output)
            for path in written:
                print(path)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
