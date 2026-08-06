"""Precompute session-structure features for the extended fusion experiment.

Outputs:
  research/data/fsld/chroma.jsonl        item_id -> 12-dim mean chroma
  research/data/fsld/role_prompts.json   role -> LAION-CLAP text embedding

Chroma is CQT-based (same as backend/ranking/harmonic_probe.py); role
prompts use the same vocabulary as the deployed role probe.

Usage:
  python research/extract_fsld_features.py \
    --items research/data/fsld/items_laion-clap-music.jsonl
"""

import argparse
import io
import json
import pathlib
import sys
import tempfile
import zipfile

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from ranking.harmonic_probe import chroma_from_audio
from ranking.role_probe import ROLE_PROMPT_TEMPLATE, ROLE_VOCAB

SAMPLE_RATE = 22050


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", default="research/data/fsld/items_laion-clap-music.jsonl")
    parser.add_argument("--zip", default="research/data/fsld/FSL10K.zip")
    parser.add_argument("--out-chroma", default="research/data/fsld/chroma.jsonl")
    parser.add_argument("--out-prompts", default="research/data/fsld/role_prompts.json")
    args = parser.parse_args()

    import librosa

    items = [json.loads(l) for l in open(args.items) if l.strip()]
    print(f"{len(items)} items", flush=True)

    # --- Part 1: role prompt embeddings (LAION-CLAP text tower) ---
    prompts_path = pathlib.Path(args.out_prompts)
    if prompts_path.exists():
        print(f"role prompts already at {prompts_path}, skipping", flush=True)
    else:
        try:
            print("Encoding role prompts with LAION-CLAP...", flush=True)
            from ranking.adapters.laion_clap import LaionClapMusicAdapter

            adapter = LaionClapMusicAdapter()
            prompts = [ROLE_PROMPT_TEMPLATE.format(role=r) for r in ROLE_VOCAB]
            embeddings = adapter.encode_text(prompts)
            prompts_path.write_text(json.dumps({
                role: emb.tolist() for role, emb in zip(ROLE_VOCAB, np.asarray(embeddings))
            }))
            print(f"→ {prompts_path}", flush=True)
        except Exception as e:
            print(f"WARNING: role prompt encoding failed ({e}); "
                  "run again once laion_clap is available", flush=True)

    # --- Part 2: chroma per item ---
    out_path = pathlib.Path(args.out_chroma)
    done = set()
    if out_path.exists():
        for line in out_path.open():
            if line.strip():
                done.add(json.loads(line)["item_id"])
        print(f"resuming: {len(done)} already done", flush=True)

    zf = zipfile.ZipFile(args.zip)
    sound_to_path = {}
    for path in zf.namelist():
        if path.startswith("audio/wav/") and path.endswith(".wav"):
            basename = path.split("/")[-1]
            sound_id = basename.split("_")[0]
            sound_to_path[sound_id] = path

    print(f"{len(sound_to_path)} wavs in zip", flush=True)

    n_ok, n_missing, n_err = 0, 0, 0
    with out_path.open("a") as out:
        for i, item in enumerate(items):
            item_id = item["item_id"]
            if item_id in done:
                continue
            sound_id = item_id.split(":")[-1]
            zip_path = sound_to_path.get(sound_id)
            if zip_path is None:
                n_missing += 1
                continue
            try:
                raw = zf.read(zip_path)
                with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
                    tmp.write(raw)
                    tmp.flush()
                    y, sr = librosa.load(tmp.name, sr=SAMPLE_RATE, mono=True)
                chroma = chroma_from_audio(y, sr)
                out.write(json.dumps({"item_id": item_id, "chroma": chroma}) + "\n")
                n_ok += 1
            except Exception as e:
                n_err += 1
                print(f"  ERR {item_id}: {e}", flush=True)
            if (i + 1) % 100 == 0:
                out.flush()
                print(f"  {i + 1}/{len(items)} (ok={n_ok} missing={n_missing} err={n_err})", flush=True)

    print(f"done: ok={n_ok} missing={n_missing} err={n_err} → {out_path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
