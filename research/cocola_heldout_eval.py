"""Evaluate COCOLA coherence as a ranking signal on the held-out split.

Pre-computes COCOLA embeddings for all held-out FSLD items, then evaluates
using the same weak-pair evaluation framework as the main paper: for each
held-out query, a positive (same-pack sibling) must rank above negatives
(easy / hard_tempo_key / hard_similar from other packs).

COCOLA scoring: for each (query_context, candidate) pair, compute the
max-pooled COCOLA pairwise score between context items and the candidate.
This parallels how the paper's CLAP cosine uses max-pooled similarity.

Usage:
  python research/cocola_heldout_eval.py \
    --audio-dir artifacts/cocola-audio \
    --output artifacts/cocola-eval
"""

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import torch
import librosa

ROOT = pathlib.Path(__file__).resolve().parent.parent
COCOLA_ROOT = ROOT.parent.parent / "cocola"
sys.path.insert(0, str(COCOLA_ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from contrastive_model import constants
from contrastive_model.contrastive_model import CoCola
from feature_extraction.feature_extraction import CoColaFeatureExtractor
from ranking.features import key_match, tempo_match

SPLIT_PATH = ROOT / "artifacts" / "heldout-split-packonly" / "split.json"
ITEMS_PATH = ROOT / "research" / "data" / "fsld" / "items_laion-clap-music_packonly.jsonl"
ITEMS_LAION_PATH = ROOT / "research" / "data" / "fsld" / "items_laion-clap-music_packonly.jsonl"

SAMPLE_RATE = 16000
CLIP_SECONDS = 5
CLIP_SAMPLES = SAMPLE_RATE * CLIP_SECONDS


def load_audio(path: pathlib.Path) -> torch.Tensor:
    y, sr = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    if len(y) < CLIP_SAMPLES:
        y = np.pad(y, (0, CLIP_SAMPLES - len(y)))
    else:
        y = y[:CLIP_SAMPLES]
    return torch.from_numpy(y).float().unsqueeze(0)


def classify_negative(context_items, neg_item):
    """Classify a negative into easy/hard_tempo_key/hard_similar tier."""
    ctx_bpms = [it["bpm"] for it in context_items if it.get("bpm")]
    ctx_bpm = float(np.mean(ctx_bpms)) if ctx_bpms else None
    ctx_keys = {it.get("key") for it in context_items if it.get("key")}

    n_bpm = neg_item.get("bpm")
    n_key = neg_item.get("key")

    tempo_ok = (ctx_bpm is not None and n_bpm and tempo_match(ctx_bpm, n_bpm) > 0.8)
    key_ok = (not ctx_keys or any(key_match(k, n_key) == 1.0 for k in ctx_keys))

    if tempo_ok and key_ok:
        return "hard_similar"
    tempo_bad = (ctx_bpm is not None and n_bpm and tempo_match(ctx_bpm, n_bpm) == 0.0)
    key_bad = (bool(ctx_keys) and all(key_match(k, n_key) == 0.0 for k in ctx_keys))
    if tempo_bad or key_bad:
        return "easy"
    return "hard_tempo_key"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--output", default="artifacts/cocola-eval")
    parser.add_argument("--checkpoint", default=str(COCOLA_ROOT / "COCOLA_HP_v1.ckpt"))
    parser.add_argument("--mode", default="both", choices=["both", "harmonic", "percussive"])
    args = parser.parse_args()

    audio_dir = pathlib.Path(args.audio_dir)

    # --- Load data ---
    split = json.loads(SPLIT_PATH.read_text())
    heldout_sources = set(split["heldout_source_ids"])

    items_by_id = {}
    with open(ITEMS_PATH) as f:
        for line in f:
            d = json.loads(line)
            if d["source_id"] in heldout_sources:
                items_by_id[d["item_id"]] = d

    by_source = {}
    for item in items_by_id.values():
        by_source.setdefault(item["source_id"], []).append(item)

    query_sources = {s: its for s, its in by_source.items() if len(its) >= 3}
    print(f"Held-out: {len(items_by_id)} items, {len(by_source)} sources, "
          f"{len(query_sources)} queryable")

    # --- Load COCOLA ---
    torch.serialization.add_safe_globals([
        constants.EmbeddingMode, constants.ModelInputType,
        constants.Dataset, constants.ModelFeatureExtractorType,
        constants.FeatureExtractionTime,
    ])
    model = CoCola.load_from_checkpoint(args.checkpoint)
    model.eval()
    mode_map = {"both": constants.EmbeddingMode.BOTH,
                "harmonic": constants.EmbeddingMode.HARMONIC,
                "percussive": constants.EmbeddingMode.PERCUSSIVE}
    model.set_embedding_mode(mode_map[args.mode])
    extractor = CoColaFeatureExtractor()
    print(f"COCOLA loaded (mode={args.mode})")

    # --- Pre-compute COCOLA embeddings ---
    print("Pre-computing COCOLA embeddings...")
    cocola_emb = {}
    n_ok = 0
    n_miss = 0
    for item_id, item in items_by_id.items():
        fsid = item_id.replace("fsld:", "")
        audio_path = audio_dir / f"{fsid}.mp3"
        if not audio_path.exists():
            n_miss += 1
            continue
        try:
            waveform = load_audio(audio_path)
            feat = extractor(waveform)
            with torch.no_grad():
                emb = model.encoder(feat.unsqueeze(0))
                emb = model.tanh(model.layer_norm(emb))
            cocola_emb[item_id] = emb.squeeze(0)
            n_ok += 1
        except Exception as e:
            print(f"  WARN {fsid}: {e}")
            n_miss += 1
        if n_ok % 50 == 0 and n_ok > 0:
            print(f"  [{n_ok}/{len(items_by_id)}]", flush=True)

    print(f"Embeddings: {n_ok} ok, {n_miss} missing")

    # --- Evaluate ---
    # Pre-build a tensor of all embeddings for batched scoring
    emb_ids = list(cocola_emb.keys())
    emb_tensor = torch.stack([cocola_emb[k] for k in emb_ids])
    emb_idx = {k: i for i, k in enumerate(emb_ids)}

    def batch_scores_vs_context(candidate_ids, context_ids):
        """Compute max-pooled COCOLA score for each candidate against context.
        Returns array of shape (len(candidate_ids),)."""
        if not candidate_ids or not context_ids:
            return np.array([])
        ctx_embs = torch.stack([cocola_emb[c] for c in context_ids])
        scores = []
        for cid in candidate_ids:
            cand_emb = cocola_emb[cid].unsqueeze(0).expand(len(context_ids), -1)
            with torch.no_grad():
                s = model.similarity.pairwise(cand_emb, ctx_embs)
            scores.append(float(s.max()))
        return np.array(scores)

    results = {"easy": [], "hard_tempo_key": [], "hard_similar": [], "overall": []}
    n_examples = 0

    for source_id, source_items in query_sources.items():
        for query_item in source_items:
            qid = query_item["item_id"]
            if qid not in cocola_emb:
                continue

            context = [it for it in source_items if it["item_id"] != qid]
            ctx_ids = [it["item_id"] for it in context if it["item_id"] in cocola_emb]
            if not ctx_ids:
                continue

            # Positive: max COCOLA score between query and context siblings
            pos_score = float(batch_scores_vs_context([qid], ctx_ids)[0])

            # Negatives from other sources
            neg_pool = [it for it in items_by_id.values()
                        if it["source_id"] != source_id and it["item_id"] in cocola_emb]

            # Classify negatives
            tier_items = {"easy": [], "hard_tempo_key": [], "hard_similar": []}
            for neg in neg_pool:
                tier = classify_negative(context, neg)
                tier_items[tier].append(neg["item_id"])

            # Batch score each tier
            tier_scores = {}
            for tier, neg_ids in tier_items.items():
                if neg_ids:
                    tier_scores[tier] = batch_scores_vs_context(neg_ids, ctx_ids)
                else:
                    tier_scores[tier] = np.array([])

            # Hit rate: positive > max negative per tier
            all_neg_scores = []
            for tier in ["easy", "hard_tempo_key", "hard_similar"]:
                scores = tier_scores[tier]
                if len(scores) > 0:
                    max_neg = float(scores.max())
                    hit = 1.0 if pos_score > max_neg else 0.0
                    results[tier].append(hit)
                    all_neg_scores.append(max_neg)

            if all_neg_scores:
                overall_hit = 1.0 if pos_score > max(all_neg_scores) else 0.0
                results["overall"].append(overall_hit)

            n_examples += 1
            if n_examples % 20 == 0:
                rates = {t: f"{np.mean(v):.3f}" if v else "N/A"
                         for t, v in results.items()}
                print(f"  [{n_examples}] easy={rates['easy']} htk={rates['hard_tempo_key']} "
                      f"hs={rates['hard_similar']} all={rates['overall']}", flush=True)

    # --- Report ---
    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    report = {
        "method": "COCOLA coherence (max-pooled pairwise score vs context)",
        "model": "COCOLA_HP_v1",
        "mode": args.mode,
        "n_examples": n_examples,
        "n_items_with_embeddings": n_ok,
        "n_items_missing_audio": n_miss,
        "hit_rates": {},
    }

    print(f"\n{'='*60}")
    print(f"  COCOLA Held-Out Evaluation ({args.mode})")
    print(f"  {n_examples} examples from {len(query_sources)} sources")
    print(f"{'='*60}")

    for tier in ["easy", "hard_tempo_key", "hard_similar", "overall"]:
        vals = results[tier]
        if vals:
            rate = np.mean(vals)
            report["hit_rates"][tier] = {"rate": round(float(rate), 4), "n": len(vals)}
            print(f"  {tier:20s}: {rate:.4f} ({len(vals)} examples)")
        else:
            report["hit_rates"][tier] = {"rate": None, "n": 0}
            print(f"  {tier:20s}: N/A")

    # --- CLAP cosine baseline on same examples (apples-to-apples) ---
    print(f"\n  CLAP cosine baseline (same examples, for direct comparison):")

    clap_emb = {}
    with open(ITEMS_PATH) as f:
        for line in f:
            d = json.loads(line)
            if d["item_id"] in cocola_emb:
                clap_emb[d["item_id"]] = np.array(d["embedding"], dtype=np.float32)

    def clap_cosine(a_id, b_id):
        a, b = clap_emb[a_id], clap_emb[b_id]
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    clap_results = {"easy": [], "hard_tempo_key": [], "hard_similar": [], "overall": []}
    for source_id, source_items in query_sources.items():
        for query_item in source_items:
            qid = query_item["item_id"]
            if qid not in cocola_emb or qid not in clap_emb:
                continue
            context = [it for it in source_items if it["item_id"] != qid]
            ctx_ids = [it["item_id"] for it in context
                       if it["item_id"] in cocola_emb and it["item_id"] in clap_emb]
            if not ctx_ids:
                continue

            pos_clap = max(clap_cosine(qid, c) for c in ctx_ids)

            neg_pool = [it for it in items_by_id.values()
                        if it["source_id"] != source_id
                        and it["item_id"] in cocola_emb
                        and it["item_id"] in clap_emb]

            tier_items = {"easy": [], "hard_tempo_key": [], "hard_similar": []}
            for neg in neg_pool:
                tier = classify_negative(context, neg)
                tier_items[tier].append(neg["item_id"])

            all_neg_clap = []
            for tier in ["easy", "hard_tempo_key", "hard_similar"]:
                neg_ids = tier_items[tier]
                if neg_ids:
                    neg_clap = [max(clap_cosine(nid, c) for c in ctx_ids) for nid in neg_ids]
                    max_neg = max(neg_clap)
                    clap_results[tier].append(1.0 if pos_clap > max_neg else 0.0)
                    all_neg_clap.append(max_neg)

            if all_neg_clap:
                clap_results["overall"].append(1.0 if pos_clap > max(all_neg_clap) else 0.0)

    report["clap_cosine_baseline"] = {}
    for tier in ["easy", "hard_tempo_key", "hard_similar", "overall"]:
        vals = clap_results[tier]
        if vals:
            rate = np.mean(vals)
            report["clap_cosine_baseline"][tier] = {"rate": round(float(rate), 4), "n": len(vals)}
            print(f"  {tier:20s}: {rate:.4f} ({len(vals)} examples)")

    print(f"\n  Paper baselines (full held-out, not subset):")
    print(f"  {'overall':20s}: ~0.929")
    print(f"  {'hard_similar':20s}: ~0.814")

    (out / "cocola_eval.json").write_text(json.dumps(report, indent=2))
    print(f"\n-> {out / 'cocola_eval.json'}")


if __name__ == "__main__":
    main()
