"""Build the app and locked per-user Windows network installer."""
import argparse
import json
from importlib import metadata
from pathlib import Path
import shutil
import subprocess
import sys

from packaging.requirements import Requirement
from PyInstaller.archive.readers import CArchiveReader

from whisper_desk.installation import cache_name, manifest
from release_support import release_context, write_version_asset

ROOT = Path(__file__).resolve().parents[1]


def verify_packaged_sources(app):
    archive = CArchiveReader(str(app / "WhisperDesk.exe")).open_embedded_archive("PYZ.pyz")
    for source in (ROOT / "src/whisper_desk").rglob("*.py"):
        relative = source.relative_to(ROOT / "src").with_suffix("")
        name = ".".join(relative.parts).removesuffix(".__init__")
        if source.name == "__main__.py":
            continue  # Source-only python -m entry point; the EXE uses scripts/run_app.py.
        code = archive.extract(name)
        if code != compile(source.read_text(encoding="utf-8"), code.co_filename, "exec"):
            raise RuntimeError(f"Packaged {name} differs from current source. Rebuild the app before packaging.")


def collect_notices(app):
    """Include licences for the installed runtime dependency graph and Python."""
    destination = app / "licenses"
    destination.mkdir(exist_ok=True)
    pending, seen, notices = ["whisper-desk"], set(), []
    while pending:
        name = pending.pop()
        distribution = metadata.distribution(name)
        identity = distribution.metadata["Name"]
        if identity.lower() in seen:
            continue
        seen.add(identity.lower())
        notices.append(f"{identity} {distribution.version}: {distribution.metadata.get('License-Expression') or distribution.metadata.get('License') or 'See included notices/upstream licence'}")
        for requirement in distribution.requires or []:
            parsed = Requirement(requirement)
            if parsed.marker is None or parsed.marker.evaluate({"extra": ""}):
                pending.append(parsed.name)
        for filename in distribution.files or []:
            if any(part.lower().startswith(("license", "copying", "notice")) for part in filename.parts):
                source = Path(distribution.locate_file(filename))
                if source.is_file():
                    # Retain the relative path so packages with multiple Qt licences don't collide.
                    relative = Path(*[part for part in filename.parts if part not in ("..", ".")])
                    target = destination / identity / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Python's licence file was not found")
    shutil.copyfile(python_license, destination / "PYTHON-LICENSE.txt")
    shutil.copyfile(ROOT / "packaging/windows/OPENAI-WHISPER-LICENSE.txt", destination / "OPENAI-WHISPER-LICENSE.txt")
    notices.extend(["OpenAI Whisper Turbo weights: MIT; see OPENAI-WHISPER-LICENSE.txt.",
                    "NVIDIA runtime licences are installed alongside the downloaded runtime under WhisperDesk/runtime/<version>/licenses.",
                    "Qt/PySide6 libraries are dynamically linked. Source and licence information: https://www.qt.io/licensing and https://code.qt.io/."])
    (destination / "THIRD-PARTY-NOTICES.txt").write_text("\n\n".join(notices) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iscc", type=Path)
    parser.add_argument("--version", required=True, help="Release version from the vMAJOR.MINOR.PATCH tag")
    parser.add_argument("--repository", required=True, help="Actual GitHub OWNER/REPOSITORY")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/installer")
    parser.add_argument("--skip-app-build", action="store_true")
    parser.add_argument("--app-source", type=Path)
    args = parser.parse_args()
    try:
        context = release_context("v" + args.version, args.repository)
    except ValueError as exc:
        parser.error(str(exc))
    release_build = ROOT / "build/release"
    app_source = args.app_source or release_build / "app/WhisperDesk"
    version_asset = ROOT / "build/release-version.json"
    write_version_asset(version_asset, context["version"])
    compiler = args.iscc or shutil.which("ISCC.exe")
    if not compiler:
        candidate = Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe")
        compiler = candidate if candidate.is_file() else None
    if not compiler:
        parser.error("Install Inno Setup 6.7.3 or newer, or pass --iscc PATH")
    if not args.skip_app_build:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
                        "--distpath", str(release_build / "app"), "--workpath", str(release_build / "pyinstaller"),
                        "whisper-desk.spec"], cwd=ROOT, check=True)
    if not (app_source / "WhisperDesk.exe").is_file():
        parser.error("Packaged application does not exist")
    verify_packaged_sources(app_source)
    bundled_lock = app_source / "_internal/whisper_desk/assets/setup-dependencies.json"
    if json.loads(bundled_lock.read_text(encoding="utf-8")) != manifest():
        parser.error("Packaged dependency lock differs from current manifest; rebuild the app")
    # Fail rather than allowing an incidental SDK library to shadow owned runtime.
    prefixes = ("cudnn", "cublas", "cudart", "nvrtc", "nvjitlink")
    if any(p.name.lower().startswith(prefixes) for p in app_source.rglob("*.dll")):
        parser.error("Packaged app contains NVIDIA SDK DLLs; rebuild using the current spec")
    version_result = subprocess.run([str(app_source / "WhisperDesk.exe"), "--version"],
                                    check=True, capture_output=True, text=True)
    if version_result.stdout.strip() != f"WhisperDesk {context['version']}":
        parser.error("Packaged application version does not match the release tag")
    collect_notices(app_source)
    folder = ROOT / "build/installer"
    folder.mkdir(parents=True, exist_ok=True)
    value = manifest()
    generated = []
    labels = {"model.bin": "Whisper Turbo model", "config.json": "Model configuration",
              "preprocessor_config.json": "Audio configuration", "tokenizer.json": "Speech tokenizer",
              "vocabulary.json": "Model vocabulary", "cuda_cudart": "NVIDIA CUDA runtime",
              "libcublas": "NVIDIA cuBLAS", "cuda_nvrtc": "NVIDIA runtime compiler",
              "libnvjitlink": "NVIDIA runtime linker", "cudnn": "NVIDIA cuDNN"}
    for kind in ("model", "gpu"):
        generated.extend([f"procedure Download{kind.title()}Dependencies;", "begin"])
        for item in value["downloads"]:
            if item["kind"] == kind:
                generated.append(f"  DownloadLocked('{labels[item['name']]}', '{item['url']}', '{cache_name(item)}', '{item['sha256']}');")
        generated.append("end;\n")
    generated.append(f"const ModelSpaceMB = {sum(d['size'] * 2 for d in value['downloads'] if d['kind'] == 'model') // 1024**2 + 1200};")
    generated.append(f"const GpuSpaceMB = {sum(d['size'] * 8 for d in value['downloads'] if d['kind'] == 'gpu') // 1024**2};")
    include = folder / "dependencies.iss"
    include.write_text("\n".join(generated), encoding="utf-8")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(compiler), "/Q", f"/DAppSource={app_source.resolve()}",
                    f"/DManifestInclude={include.resolve()}", f"/DOutputDir={args.output_dir.resolve()}",
                    f"/DReleaseVersion={context['version']}",
                    f"/DInstallerBaseFilename={Path(context['installer_name']).stem}",
                    f"/DProjectUrl={context['project_url']}", f"/DSupportUrl={context['support_url']}",
                    str(ROOT / "packaging/windows/WhisperDesk.iss")], cwd=ROOT, check=True)
    installer = args.output_dir / context["installer_name"]
    if not installer.is_file():
        parser.error(f"Inno Setup did not create {installer}")
    checksum = __import__("release_support").sha256_file(installer)
    (installer.parent / f"{installer.name}.sha256").write_text(f"{checksum}  {installer.name}\n", encoding="ascii")
    release = {**context, "installer_path": str(installer.resolve()), "sha256": checksum}
    (release_build / "release.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    print(f"Installer: {installer}")
    print(f"SHA-256: {checksum}")


if __name__ == "__main__":
    main()
