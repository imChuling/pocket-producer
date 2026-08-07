"""Which signals align with human continuation preferences?

Links the two halves of the LBD evidence for the first time: the 180
external blind A/B labels (9 raters x 20 pairs) and the ranking signals
(CLAP cosine, harmonic chroma, role gap, tempo).

For every pair, each signal independently picks A or B; we compare that
pick against the human majority, stratified by rater consensus
(>=7/9 = consensus pairs).  The interesting cell is signal performance
ON CONSENSUS PAIRS: if humans reliably agree on a winner and cosine
does not recover it, continuation preference contains structure that
acoustic similarity cannot express -- and whichever signal does recover
it is the first human-grounded evidence for session conditioning.

Inputs (all already collected):
  artifacts/eval-audio-pack/manifest.json   pair -> context/candidate audio
  artifacts/eval-pack/eval_summary.json     per-pair votes + confidence
  research/data/fsld/role_prompts.json      LAION-CLAP role text embeddings

Usage:
  python research/human_signal_alignment.py --output artifacts/human-signal-alignment
"""

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

from ranking.harmonic_probe import chroma_from_audio, session_chroma, transpose_invariant_score
from ranking.role_probe import CONFIDENCE_THRESHOLD, RoleProbe

ROOT = pathlib.Path(__file__).parent.parent
AUDIO_DIR = ROOT / "artifacts" / "eval-audio-pack" / "audio"
CONSENSUS = 7 / 9  # >=7 of 9 raters


def decode(path: pathlib.Path, sr: int) -> np.ndarray:
    """Decode any container to mono float32 via ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(path),
             "-ac", "1", "-ar", str(sr), tmp.name],
            check=True,
        )
        import librosa
        y, _ = librosa.load(tmp.name, sr=sr, mono=True)
    return y


def estimate_tempo(y: np.ndarray, sr: int) -> float:
    import librosa
    tempo = librosa.beat.tempo(y=y, sr=sr)
    return float(np.atleast_1d(tempo)[0])


def tempo_match(a: float, b: float) -> float:
    """1.0 at equal tempo, linear falloff, half/double treated as equal."""
    if not a or not b:
        return 0.0
    ratios = [b / a, 2 * b / a, b / (2 * a)]
    best = min(abs(1 - r) for r in ratios)
    return max(0.0, 1.0 - 4.0 * best)


def unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-9)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/human-signal-alignment")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "artifacts/eval-audio-pack/manifest.json").read_text())
    summary = json.loads((ROOT / "artifacts/eval-pack/eval_summary.json").read_text())
    per_pair = {p["pair"]: p for p in summary["per_pair"]}

    from ranking.adapters.laion_clap import LaionClapMusicAdapter
    adapter = LaionClapMusicAdapter()

    prompt_map = json.loads((ROOT / "research/data/fsld/role_prompts.json").read_text())
    probe = RoleProbe(np.array(list(prompt_map.values())))

    # --- Per-fragment features (fragments repeat across pairs; cache) ---
    features: dict[str, dict] = {}

    def fragment_features(file_rel: str) -> dict:
        if file_rel in features:
            return features[file_rel]
        path = ROOT / "artifacts" / "eval-audio-pack" / file_rel
        y48 = decode(path, 48000)
        y22 = decode(path, 22050)
        emb = unit(np.asarray(adapter.encode_audio(y48, 48000)).reshape(-1))
        role, role_conf = probe.classify(emb)
        feats = {
            "embedding": emb,
            "chroma": chroma_from_audio(y22, 22050),
            "role": role,
            "role_conf": float(role_conf),
            "tempo": estimate_tempo(y22, 22050),
        }
        features[file_rel] = feats
        return feats

    signals = ["cos_mean", "cos_max", "harmonic", "role_gap", "tempo"]
    rows = []
    for entry in manifest:
        eval_id = entry["eval_id"]
        votes = per_pair[eval_id]
        ctx = [fragment_features(c["file"]) for c in entry["context_audio"]]
        cand = {
            "A": fragment_features(entry["candidate_A"]["file"]),
            "B": fragment_features(entry["candidate_B"]["file"]),
        }

        ctx_vecs = np.stack([c["embedding"] for c in ctx])
        mean_ctx = unit(ctx_vecs.mean(axis=0))
        sess = session_chroma([c["chroma"] for c in ctx])
        present_roles = {c["role"] for c in ctx if c["role_conf"] >= CONFIDENCE_THRESHOLD}
        ctx_tempo = float(np.mean([c["tempo"] for c in ctx]))

        score: dict[str, dict[str, float]] = {s: {} for s in signals}
        for side in ("A", "B"):
            f = cand[side]
            score["cos_mean"][side] = float(mean_ctx @ f["embedding"])
            score["cos_max"][side] = float((ctx_vecs @ f["embedding"]).max())
            score["harmonic"][side] = float(transpose_invariant_score(sess, f["chroma"])[0])
            gap = 0.0
            if f["role"] not in present_roles and f["role_conf"] >= CONFIDENCE_THRESHOLD:
                gap = f["role_conf"]
            score["role_gap"][side] = gap
            score["tempo"][side] = tempo_match(ctx_tempo, f["tempo"])

        majority = votes["majority"]  # 'A' / 'B' / 'Neither'
        row = {
            "eval_id": eval_id,
            "majority": majority,
            "agreement_ratio": votes["agreement_ratio"],
            "consensus": votes["agreement_ratio"] >= CONSENSUS,
            "avg_confidence": votes["avg_confidence"],
        }
        for s in signals:
            a, b = score[s]["A"], score[s]["B"]
            pick = "A" if a > b else ("B" if b > a else "tie")
            row[s] = {"A": round(a, 4), "B": round(b, 4), "pick": pick,
                      "match": pick == majority if majority in ("A", "B") else None}
        rows.append(row)
        print(f"pair {eval_id:2d} maj={majority:7s} agree={votes['agreement_ratio']:.2f} "
              + "  ".join(f"{s}={row[s]['pick']}{'+' if row[s]['match'] else '-' if row[s]['match'] is False else '?'}"
                          for s in signals), flush=True)

    # --- Aggregate ---
    def rate(rs, s):
        judged = [r for r in rs if r[s]["match"] is not None]
        hit = sum(1 for r in judged if r[s]["match"])
        return hit, len(judged)

    pref_rows = [r for r in rows if r["majority"] in ("A", "B")]
    consensus_rows = [r for r in pref_rows if r["consensus"]]
    split_rows = [r for r in pref_rows if not r["consensus"]]

    report = {
        "experiment": "signal alignment with external human majorities",
        "n_pairs": len(rows),
        "n_preference": len(pref_rows),
        "n_consensus": len(consensus_rows),
        "consensus_threshold": ">=7/9",
        "signals": {},
    }
    print(f"\n{'signal':10s} {'all':>10s} {'consensus':>12s} {'split':>10s}", flush=True)
    for s in signals:
        h_all, n_all = rate(pref_rows, s)
        h_con, n_con = rate(consensus_rows, s)
        h_spl, n_spl = rate(split_rows, s)
        report["signals"][s] = {
            "all": [h_all, n_all],
            "consensus": [h_con, n_con],
            "split": [h_spl, n_spl],
        }
        print(f"{s:10s} {h_all:>6d}/{n_all:<3d} {h_con:>8d}/{n_con:<3d} {h_spl:>6d}/{n_spl:<3d}", flush=True)

    report["per_pair"] = rows
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "alignment.json").write_text(json.dumps(report, indent=2))
    print(f"\n-> {out / 'alignment.json'}", flush=True)


if __name__ == "__main__":
    main()
