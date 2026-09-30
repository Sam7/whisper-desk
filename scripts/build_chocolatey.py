"""Render, pack, and verify the release-specific Chocolatey package."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

from release_support import CHOCO_ID, release_context, sha256_file


ROOT = Path(__file__).resolve().parents[1]
SILENT_ARGS = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART"


def render_package(context: dict[str, str], checksum: str, destination: Path) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("Installer SHA-256 must be 64 lowercase hexadecimal characters")
    destination = Path(destination)
    tools = destination / "tools"
    expected_files = {
        f"{CHOCO_ID}.nuspec",
        "tools/chocolateyinstall.ps1",
        "tools/chocolateyuninstall.ps1",
    }
    if destination.exists():
        unexpected = [path.relative_to(destination).as_posix()
                      for path in destination.rglob("*")
                      if path.is_file() and path.relative_to(destination).as_posix() not in expected_files]
        if unexpected:
            raise ValueError(f"Refusing to package unexpected/stale files: {', '.join(unexpected)}")
    tools.mkdir(parents=True, exist_ok=True)
    nuspec = (ROOT / "packaging/chocolatey/whisperdesk.nuspec").read_text(encoding="utf-8")
    nuspec = nuspec.replace("<version>0.0.0</version>", f"<version>{context['version']}</version>")
    nuspec = nuspec.replace("https://github.com/placeholder/placeholder/issues", context["support_url"])
    nuspec = nuspec.replace("https://github.com/placeholder/placeholder/tree/main/packaging/chocolatey",
                            context["project_url"] + "/tree/main/packaging/chocolatey")
    nuspec = nuspec.replace("https://github.com/placeholder/placeholder", context["project_url"])
    if "placeholder" in nuspec or "<version>0.0.0</version>" in nuspec:
        raise ValueError("Unresolved Chocolatey package metadata")
    nuspec_path = destination / f"{CHOCO_ID}.nuspec"
    nuspec_path.write_text(nuspec, encoding="utf-8", newline="\n")
    script = (ROOT / "packaging/chocolatey/tools/chocolateyinstall.ps1").read_text(encoding="utf-8")
    script = script.replace("__INSTALLER_URL__", context["installer_url"]).replace("__INSTALLER_SHA256__", checksum)
    if "__INSTALLER_" in script:
        raise ValueError("Unresolved Chocolatey installer metadata")
    (tools / "chocolateyinstall.ps1").write_text(script, encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "packaging/chocolatey/tools/chocolateyuninstall.ps1", tools / "chocolateyuninstall.ps1")
    return nuspec_path


def inspect_package(package: Path, context: dict[str, str], checksum: str) -> None:
    with zipfile.ZipFile(package) as archive:
        nuspec_name = next((name for name in archive.namelist() if name.lower().endswith(".nuspec")), None)
        if not nuspec_name:
            raise ValueError("Chocolatey archive has no nuspec")
        root = ET.fromstring(archive.read(nuspec_name))
        # Chocolatey rewrites the nuspec namespace to its legacy 2010 schema
        # while packing; read direct metadata children by local name.
        metadata = next((child for child in root if child.tag.rsplit("}", 1)[-1] == "metadata"), None)
        if metadata is None:
            raise ValueError("Chocolatey package nuspec has no metadata element")
        actual = {
            name: next((child.text for child in metadata
                        if child.tag.rsplit("}", 1)[-1] == name), None)
            for name in ("id", "version", "title", "authors", "projectUrl", "bugTrackerUrl")
        }
        expected = {"id": CHOCO_ID, "version": context["version"], "title": "WhisperDesk",
                    "authors": "DotSam", "projectUrl": context["project_url"], "bugTrackerUrl": context["support_url"]}
        if actual != expected:
            raise ValueError(f"Chocolatey package metadata mismatch: {actual!r}")
        scripts = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist()
                              if name.lower().endswith(("chocolateyinstall.ps1", "chocolateyuninstall.ps1")))
        for required in (context["installer_url"], checksum, SILENT_ARGS,
                         "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"):
            if required not in scripts:
                raise ValueError(f"Chocolatey package is missing required install metadata: {required}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--checksum", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--choco", default="choco")
    args = parser.parse_args(argv)
    try:
        context = release_context(args.tag, args.repository)
        if args.installer.name != context["installer_name"]:
            raise ValueError(f"Expected {context['installer_name']}, received {args.installer.name}")
        checksum = sha256_file(args.installer)
        if args.checksum:
            recorded = args.checksum.read_text(encoding="ascii").split()[0]
            if recorded != checksum:
                raise ValueError("Installer SHA-256 sidecar does not match the installer")
        args.output.mkdir(parents=True, exist_ok=True)
        package_dir = args.output / "package"
        nuspec = render_package(context, checksum, package_dir)
        result = subprocess.run([args.choco, "pack", str(nuspec), "--outputdirectory", str(args.output)],
                                check=False, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("choco pack failed: " + (result.stderr or result.stdout).strip())
        package = args.output / f"{CHOCO_ID}.{context['version']}.nupkg"
        if not package.is_file():
            raise RuntimeError("choco pack did not create the expected versioned package")
        inspect_package(package, context, checksum)
        print(f"Chocolatey package: {package}")
        print(f"Installer SHA-256: {checksum}")
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
