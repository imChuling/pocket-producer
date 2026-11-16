"""Which held-out packs share an uploader with the train side."""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from run_uploader_overlap_check import shared_uploader_sources, uploader_by_source  # noqa: E402


def test_packs_are_flagged_by_their_uploader(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    rows = [
        {"freesound_id": 1, "username": "a"},
        {"freesound_id": 2, "username": "a"},
        {"freesound_id": 3, "username": "b"},
        {"freesound_id": 4, "username": "c"},
    ]
    manifest.write_text("\n".join(json.dumps(r) for r in rows))
    items = [
        {"item_id": "fsld:1", "source_id": "train-pack"},
        {"item_id": "fsld:2", "source_id": "held-pack-a"},
        {"item_id": "fsld:3", "source_id": "held-pack-b"},
        {"item_id": "fsld:4", "source_id": "train-pack-c"},
    ]
    uploader = uploader_by_source(items, manifest)
    shared = shared_uploader_sources(
        {"train-pack", "train-pack-c"}, {"held-pack-a", "held-pack-b"}, uploader
    )
    assert shared == {"held-pack-a"}
