"""Download the FSLD embedding files that the paper's result chain starts from.

The embedding step itself is not deterministic (see research/README.md), so
the exact vectors used for the paper are distributed as a release asset
rather than regenerated. This script downloads the bundle, verifies its
sha256, unpacks it into research/data/fsld/ and verifies every file against
the SHA256SUMS manifest inside the bundle. Standard library only; works the
same on macOS, Linux and Windows.

    python research/fetch_embeddings.py            # download + verify
    python research/fetch_embeddings.py --file fsld-embeddings-v1.tar.gz
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys
import tarfile
import tempfile
import urllib.request

BUNDLE = "fsld-embeddings-v1"
DEFAULT_URL = (
    "https://github.com/imChuling/pocket-producer/releases/download/"
    f"{BUNDLE}/{BUNDLE}.tar.gz"
)
BUNDLE_SHA256 = "c08ecb191daec0efe3667efb5b79bfca536f1d3bb1289c2bc88709824dd4945c"

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "research" / "data" / "fsld"


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: pathlib.Path) -> None:
    print(f"downloading {url}")
    with urllib.request.urlopen(url) as response, open(target, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        for chunk in iter(lambda: response.read(1 << 20), b""):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()


def verify_manifest(folder: pathlib.Path) -> list[str]:
    problems = []
    for line in (folder / "SHA256SUMS").read_text().splitlines():
        expected, _, name = line.strip().partition("  ")
        path = folder / name
        if not path.is_file():
            problems.append(f"missing {name}")
        elif sha256_of(path) != expected:
            problems.append(f"sha256 mismatch for {name}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default=DEFAULT_URL, help="bundle URL (default: GitHub release)")
    parser.add_argument("--file", help="use an already downloaded bundle instead of --url")
    parser.add_argument("--dest", default=str(DEST), help=f"target directory (default: {DEST})")
    parser.add_argument("--force", action="store_true", help="overwrite files already present")
    args = parser.parse_args()

    dest = pathlib.Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    present = [p for p in dest.glob("items_*.jsonl")]
    if present and not args.force:
        problems = verify_manifest(dest) if (dest / "SHA256SUMS").is_file() else ["no SHA256SUMS"]
        if not problems:
            print(f"{len(present)} embedding files already present and verified in {dest}")
            return 0
        print("existing files do not match the manifest; re-fetching (" + "; ".join(problems) + ")")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        bundle = pathlib.Path(args.file) if args.file else tmp_path / f"{BUNDLE}.tar.gz"
        if not args.file:
            download(args.url, bundle)
        actual = sha256_of(bundle)
        if actual != BUNDLE_SHA256:
            print(f"bundle sha256 {actual} does not match {BUNDLE_SHA256}", file=sys.stderr)
            return 1
        print("bundle sha256 ok")
        with tarfile.open(bundle) as archive:
            members = [m for m in archive.getmembers() if m.isfile()]
            for member in members:
                name = pathlib.PurePosixPath(member.name).name
                # Skip anything outside the bundle folder and macOS "._" metadata.
                if "/" not in member.name or ".." in member.name or name.startswith("._"):
                    continue
                with archive.extractfile(member) as src, open(dest / name, "wb") as out:
                    shutil.copyfileobj(src, out)
    problems = verify_manifest(dest)
    if problems:
        print("verification failed: " + "; ".join(problems), file=sys.stderr)
        return 1
    print(f"verified {len(list(dest.glob('*.jsonl')))} files in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
