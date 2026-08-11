"""Build the per-item license manifest for the Freesound Loop Dataset.

"Creative Commons" is not one license: each of the 9,493 loops carries its
own license URL and its own permissions. This script classifies every item
and records what each may be used for. Only `research_ok` items enter weak
pretraining; only `redistribution_ok` items may ship in public artifacts.

Inputs (fetched on demand):
  research/data/fsld/metadata.json    from inside FSL10K.zip (Zenodo 3967852),
                                      extracted via HTTP Range without
                                      downloading the 8.8 GB archive
  research/data/fsld/annotations/     annotations.zip from the same record

Output:
  research/data/fsld/manifest.jsonl   one line per loop
"""

import argparse
import io
import json
import pathlib
import zipfile

FSLD_ZENODO_RECORD = "https://zenodo.org/records/3967852"
FSL10K_URL = f"{FSLD_ZENODO_RECORD}/files/FSL10K.zip"
ANNOTATIONS_URL = f"{FSLD_ZENODO_RECORD}/files/annotations.zip"

DATA_DIR = pathlib.Path(__file__).parent / "data" / "fsld"

# license URL substring → (class, research_ok, redistribution_ok, product_ok,
#                          attribution_required)
LICENSE_RULES = [
    ("publicdomain/zero", ("cc0", True, True, True, False)),
    ("licenses/zero", ("cc0", True, True, True, False)),
    ("licenses/by-nc", ("cc-by-nc", True, False, False, True)),
    ("licenses/by", ("cc-by", True, True, True, True)),
    ("licenses/sampling+", ("sampling-plus", True, False, False, True)),
]


def classify_license(url: str) -> dict:
    for needle, (
        license_class,
        research_ok,
        redistribution_ok,
        product_ok,
        attribution_required,
    ) in LICENSE_RULES:
        if needle in url:
            return {
                "license_class": license_class,
                "research_ok": research_ok,
                "redistribution_ok": redistribution_ok,
                "product_ok": product_ok,
                "attribution_required": attribution_required,
            }
    return {
        "license_class": "unknown",
        "research_ok": False,
        "redistribution_ok": False,
        "product_ok": False,
        "attribution_required": True,
    }


class _HttpFile(io.RawIOBase):
    """Minimal seekable HTTP file for reading single zip members remotely."""

    def __init__(self, url: str):
        import requests

        self.url = url
        self.session = requests.Session()
        head = self.session.head(url, allow_redirects=True, timeout=30)
        self.size = int(head.headers["Content-Length"])
        self.pos = 0

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def tell(self):
        return self.pos

    def readable(self):
        return True

    def seekable(self):
        return True

    def read(self, n=-1):
        if n == -1:
            n = self.size - self.pos
        if n == 0:
            return b""
        end = min(self.size - 1, self.pos + n - 1)
        response = self.session.get(
            self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=180
        )
        response.raise_for_status()
        data = response.content
        self.pos += len(data)
        return data


def ensure_metadata() -> dict:
    path = DATA_DIR / "metadata.json"
    if not path.exists():
        print("fetching metadata.json from inside FSL10K.zip (ranged reads)…")
        archive = zipfile.ZipFile(_HttpFile(FSL10K_URL))
        member = next(
            info
            for info in archive.infolist()
            if info.filename.endswith("metadata.json")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(archive.read(member))
    return json.loads(path.read_text())


def ensure_annotations() -> dict[str, dict]:
    root = DATA_DIR / "annotations"
    if not root.exists():
        import requests

        print("fetching annotations.zip…")
        payload = requests.get(ANNOTATIONS_URL, timeout=300).content
        zipfile.ZipFile(io.BytesIO(payload)).extractall(DATA_DIR)
    annotations: dict[str, dict] = {}
    for path in root.rglob("sound-*.json"):
        sound_id = path.stem.removeprefix("sound-")
        annotations[sound_id] = json.loads(path.read_text())
    return annotations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", default=str(DATA_DIR / "manifest.jsonl")
    )
    args = parser.parse_args()

    metadata = ensure_metadata()
    annotations = ensure_annotations()

    rows = []
    for sound_id, entry in sorted(metadata.items()):
        row = {
            "freesound_id": int(entry.get("id") or sound_id),
            "name": entry.get("name", ""),
            "username": entry.get("username", ""),
            "pack": entry.get("pack") or None,
            "pack_name": entry.get("pack_name") or None,
            "source_id": entry.get("pack")
            or f"user:{entry.get('username', 'unknown')}",
            "license_url": entry.get("license", ""),
            **classify_license(entry.get("license", "")),
            "tags": entry.get("tags", []),
            "metadata_bpm": (entry.get("annotations") or {}).get("bpm"),
        }
        annotation = annotations.get(str(sound_id))
        if annotation and not annotation.get("discard"):
            row["annotated"] = True
            row["annotation_bpm"] = annotation.get("bpm")
            row["key"] = annotation.get("key")
            row["mode"] = annotation.get("mode")
            row["signature"] = annotation.get("signature")
            row["genres"] = annotation.get("genres", [])
            row["instrumentation"] = annotation.get("instrumentation", {})
            row["well_cut"] = annotation.get("well_cut")
        else:
            row["annotated"] = False
        rows.append(row)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["license_class"]] = counts.get(row["license_class"], 0) + 1
    annotated = sum(1 for row in rows if row["annotated"])
    research_ok = sum(1 for row in rows if row["research_ok"])
    redistribution_ok = sum(1 for row in rows if row["redistribution_ok"])
    print(f"total={len(rows)} annotated={annotated}")
    for license_class, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {license_class:15s} {count}")
    print(f"research_ok={research_ok} redistribution_ok={redistribution_ok}")
    print(f"→ {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
