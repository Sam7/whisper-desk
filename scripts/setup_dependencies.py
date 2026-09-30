"""Developer smoke-test/download entry point using the same locked dependencies."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from whisper_desk.installation import acquire, manifest, stage_dependencies
from whisper_desk.setup_support import main as setup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--stage-only", action="store_true", help="Use packaged --setup-verify to prove DLL isolation")
    parser.add_argument("--audio", type=Path)
    args = parser.parse_args()
    value = manifest()
    items = [d for d in value["downloads"] if not args.cpu or d["kind"] == "model"]

    def download(item):
        print(f"Acquiring {item['name']} ({item['size']:,} bytes)", flush=True)
        acquire(item, args.cache)
        print(f"Verified {item['name']}", flush=True)

    with ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(download, items))
    if args.download_only:
        return 0
    stage_dependencies(args.root, args.cache, value, gpu=not args.cpu)
    if args.stage_only:
        return 0
    return setup("verify", root=args.root, output=args.root / "verification.json", gpu=not args.cpu, audio=args.audio)


if __name__ == "__main__":
    raise SystemExit(main())
