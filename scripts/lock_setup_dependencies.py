"""Explicit release-lock update. Never run this during end-user installation."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REVISION = "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
REPO = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"


def fetch(url):
    with urlopen(url, timeout=60) as response:
        return response.read()


def main():
    downloads = []
    cuda_base = "https://developer.download.nvidia.com/compute/cuda/redist/"
    cuda = json.loads(fetch(cuda_base + "redistrib_12.9.1.json"))
    for name in ("cuda_cudart", "libcublas", "cuda_nvrtc", "libnvjitlink"):
        item = cuda[name]["windows-x86_64"]
        downloads.append(dict(name=name, kind="gpu", version=cuda[name]["version"],
                              url=cuda_base + item["relative_path"], size=int(item["size"]), sha256=item["sha256"]))
    base = "https://developer.download.nvidia.com/compute/cudnn/redist/"
    cudnn = json.loads(fetch(base + "redistrib_9.10.2.json"))["cudnn"]
    item = cudnn["windows-x86_64"]["cuda12"]
    downloads.append(dict(name="cudnn", kind="gpu", version=cudnn["version"],
                          url=base + item["relative_path"], size=int(item["size"]), sha256=item["sha256"]))
    metadata = json.loads(fetch(f"https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true"))
    names = {"model.bin", "config.json", "preprocessor_config.json", "tokenizer.json", "vocabulary.json"}
    for item in metadata["siblings"]:
        name = item["rfilename"]
        if name not in names:
            continue
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}"
        digest = item.get("lfs", {}).get("sha256") or hashlib.sha256(fetch(url)).hexdigest()
        downloads.append(dict(name=name, kind="model", url=url, size=item["size"], sha256=digest))
    assert {d["name"] for d in downloads if d["kind"] == "model"} == names
    manifest = dict(schema=1, runtime="cuda12.9-cudnn9.10.2", model_revision=REVISION,
                    model_repo=REPO, downloads=downloads)
    output = ROOT / "src/whisper_desk/assets/setup-dependencies.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Locked {len(downloads)} dependencies; {sum(d['size'] for d in downloads):,} download bytes")


if __name__ == "__main__":
    main()
