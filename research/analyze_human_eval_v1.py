"""Analyze the single-listener pairwise evaluation.

Pre-registered analysis script for prereg_human_v1.md (N-of-1 design):
each file under --responses is one session by the same listener; sessions
are collapsed to a per-pair majority vote and all primary statistics are
computed at the pair level. Must be committed before the first session.

Usage:
  python research/analyze_human_eval_v1.py \
    --responses research/data/listening_test/responses/ \
    --pairs research/data/listening_test/pairs.json \
    --output artifacts/human-eval-v1
"""

import argparse
import json
import pathlib
from collections import Counter

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_responses(response_dir: pathlib.Path) -> list[dict]:
    raters = []
    for f in sorted(response_dir.glob("*.json")):
        data = json.loads(f.read_text())
        raters.append(data)
    return raters


def apply_exclusions(raters: list[dict], min_pairs: int = 30) -> tuple[list[dict], list[str]]:
    excluded = []
    kept = []
    for r in raters:
        responses = r.get("responses", [])
        n = len(responses)
        if n < min_pairs:
            excluded.append(f"{r['rater_id']}: only {n} pairs (min {min_pairs})")
            continue
        choices = [resp["choice"] for resp in responses if resp["choice"] != "no_preference"]
        if choices:
            most_common_frac = Counter(choices).most_common(1)[0][1] / len(choices)
            if most_common_frac > 0.9:
                excluded.append(f"{r['rater_id']}: {most_common_frac:.0%} same choice")
                continue
        kept.append(r)
    return kept, excluded


def compute_agreement(raters, pairs_manifest, ranker_name, pair_filter=None):
    """Compute pairwise agreement between human choices and a ranker.

    Returns observations and matching rater_ids for clustered bootstrap.
    Uses the explicit {ranker}_pick field from pairs.json.
    """
    pair_lookup = {p["pair_id"]: p for p in pairs_manifest["pairs"]}
    agree = []
    rater_ids = []
    n_no_pref = 0

    pick_field = f"{ranker_name}_pick"

    for rater in raters:
        for resp in rater["responses"]:
            pid = resp["pair_id"]
            choice = resp["choice"]
            if choice == "no_preference":
                n_no_pref += 1
                continue

            pair = pair_lookup.get(pid)
            if pair is None:
                continue

            if pair_filter and not pair_filter(pair):
                continue

            if pick_field not in pair:
                raise KeyError(
                    f"pairs.json missing '{pick_field}' for pair {pid}. "
                    f"Regenerate pairs with unified weights."
                )

            if "positive_side" not in resp:
                raise KeyError(
                    f"Response for pair {pid} from rater {rater['rater_id']} "
                    f"missing 'positive_side'. The listening test page must "
                    f"record which side was assigned as positive."
                )

            ranker_picked_positive = (pair[pick_field] == "positive")
            human_chose_positive = (choice == resp["positive_side"])
            human_agrees = (human_chose_positive == ranker_picked_positive)

            agree.append(1.0 if human_agrees else 0.0)
            rater_ids.append(rater["rater_id"])

    return {
        "agreement_rate": float(np.mean(agree)) if agree else float("nan"),
        "n_valid": len(agree),
        "n_no_preference": n_no_pref,
        "observations": agree,
        "rater_ids": rater_ids,
    }


def mcnemar_test(obs_a, obs_b):
    a = np.array(obs_a)
    b = np.array(obs_b)
    assert len(a) == len(b)

    b_only = np.sum((a == 0) & (b == 1))
    a_only = np.sum((a == 1) & (b == 0))

    n_discord = a_only + b_only
    if n_discord == 0:
        return {"chi2": 0.0, "p_value": 1.0, "a_only": int(a_only),
                "b_only": int(b_only), "n_discordant": 0}

    chi2 = (abs(a_only - b_only) - 1) ** 2 / n_discord
    from scipy.stats import chi2 as chi2_dist
    p_value = float(chi2_dist.sf(chi2, df=1))

    return {
        "chi2": float(chi2),
        "p_value": p_value,
        "a_only": int(a_only),
        "b_only": int(b_only),
        "n_discordant": int(n_discord),
    }


def majority_votes(sessions, pairs_manifest):
    """Collapse one listener's sessions to a per-pair label.

    Returns {pair_id: "positive" | "negative" | None}; None when fewer than
    two sessions expressed a preference or the preferences tie.
    """
    votes = {p["pair_id"]: [] for p in pairs_manifest["pairs"]}
    for session in sessions:
        for resp in session["responses"]:
            pid = resp["pair_id"]
            if pid not in votes or resp["choice"] == "no_preference":
                continue
            if "positive_side" not in resp:
                raise KeyError(f"response for {pid} is missing 'positive_side'")
            votes[pid].append(resp["choice"] == resp["positive_side"])
    labels = {}
    for pid, v in votes.items():
        pos = sum(v)
        neg = len(v) - pos
        labels[pid] = "positive" if pos > neg else "negative" if neg > pos else None
    return labels


def pair_level_test(labels, pairs_manifest, ranker_a="fusion", ranker_b="cosine"):
    """Exact binomial on pairs where the two rankers pick different candidates."""
    from scipy.stats import binomtest

    pair_lookup = {p["pair_id"]: p for p in pairs_manifest["pairs"]}
    sides_a = 0
    n = 0
    for pid, label in labels.items():
        pair = pair_lookup[pid]
        if label is None or pair[f"{ranker_a}_pick"] == pair[f"{ranker_b}_pick"]:
            continue
        n += 1
        sides_a += label == pair[f"{ranker_a}_pick"]
    if n == 0:
        return {"n_discordant_pairs": 0}
    test = binomtest(sides_a, n, 0.5, alternative="two-sided")
    ci = test.proportion_ci(confidence_level=0.95, method="exact")
    return {
        "n_discordant_pairs": n,
        f"sides_with_{ranker_a}": int(sides_a),
        "p_two_sided": round(float(test.pvalue), 4),
        "ci95_exact": [round(float(ci.low), 3), round(float(ci.high), 3)],
    }


def pair_level_agreement(labels, pairs_manifest, ranker_name, pair_filter=None):
    rows = [
        1.0 if labels[p["pair_id"]] == p[f"{ranker_name}_pick"] else 0.0
        for p in pairs_manifest["pairs"]
        if labels[p["pair_id"]] is not None and (pair_filter is None or pair_filter(p))
    ]
    return np.array(rows)


def bootstrap_pair_delta(a, b, n_bootstrap=10000, alpha=0.05):
    rng = np.random.default_rng(42)
    idx = np.arange(len(a))
    deltas = [a[s].mean() - b[s].mean()
              for s in (rng.choice(idx, size=len(idx), replace=True) for _ in range(n_bootstrap))]
    return {
        "point_delta": round(float(a.mean() - b.mean()), 4),
        "ci_lo": round(float(np.percentile(deltas, 100 * alpha / 2)), 4),
        "ci_hi": round(float(np.percentile(deltas, 100 * (1 - alpha / 2))), 4),
        "n_pairs": int(len(a)),
    }


def cohen_kappa(x, y):
    x = np.asarray(x)
    y = np.asarray(y)
    cats = sorted(set(x) | set(y))
    po = float(np.mean(x == y))
    pe = sum((np.mean(x == c)) * (np.mean(y == c)) for c in cats)
    return 1.0 if pe == 1.0 else float((po - pe) / (1 - pe))


def intra_rater_reliability(sessions, pairs_manifest):
    """Unanimity rate and mean pairwise Cohen's kappa across sessions."""
    per_session = []
    for s in sessions:
        coded = {}
        for resp in s["responses"]:
            if resp["choice"] == "no_preference":
                coded[resp["pair_id"]] = "none"
            else:
                coded[resp["pair_id"]] = "pos" if resp["choice"] == resp["positive_side"] else "neg"
        per_session.append(coded)
    pids = [p["pair_id"] for p in pairs_manifest["pairs"]
            if all(p["pair_id"] in s for s in per_session)]
    if len(per_session) < 2 or not pids:
        return {"n_sessions": len(per_session), "unanimous_fraction": None, "mean_kappa": None}
    unanimous = sum(1 for pid in pids if len({s[pid] for s in per_session}) == 1)
    kappas = [
        cohen_kappa([per_session[i][pid] for pid in pids], [per_session[j][pid] for pid in pids])
        for i in range(len(per_session)) for j in range(i + 1, len(per_session))
    ]
    return {
        "n_sessions": len(per_session),
        "n_pairs_in_all_sessions": len(pids),
        "unanimous_fraction": round(unanimous / len(pids), 3),
        "pairwise_kappa": [round(k, 3) for k in kappas],
        "mean_kappa": round(float(np.mean(kappas)), 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", required=True)
    parser.add_argument("--pairs", required=True)
    parser.add_argument("--output", default="artifacts/human-eval-v1")
    args = parser.parse_args()

    response_dir = pathlib.Path(args.responses)
    pairs_manifest = json.loads(pathlib.Path(args.pairs).read_text())
    out_dir = pathlib.Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    raters = load_responses(response_dir)
    print(f"Loaded {len(raters)} rater files")

    raters, exclusions = apply_exclusions(raters)
    print(f"After exclusions: {len(raters)} raters")
    for ex in exclusions:
        print(f"  EXCLUDED: {ex}")

    if not raters:
        print("No valid raters. Exiting.")
        return

    # Single listener: files are sessions, the analysis unit is the pair.
    labels = majority_votes(raters, pairs_manifest)
    n_labeled = sum(1 for v in labels.values() if v is not None)
    print(f"\nPair-level labels from {len(raters)} sessions: {n_labeled}/{len(labels)} pairs")

    # H1 (primary): exact binomial on discordant-capable pairs
    print("\n=== H1: Fusion vs Cosine, pair level ===")
    h1 = pair_level_test(labels, pairs_manifest, "fusion", "cosine")
    print(f"  discordant pairs: {h1['n_discordant_pairs']}", end="")
    if h1["n_discordant_pairs"]:
        print(f"  sides with fusion: {h1['sides_with_fusion']}  "
              f"exact p={h1['p_two_sided']}  CI95={h1['ci95_exact']}")
    else:
        print()
    fusion_pairs = pair_level_agreement(labels, pairs_manifest, "fusion")
    cosine_pairs = pair_level_agreement(labels, pairs_manifest, "cosine")
    h1_delta = bootstrap_pair_delta(fusion_pairs, cosine_pairs)
    print(f"  agreement fusion={fusion_pairs.mean():.3f} cosine={cosine_pairs.mean():.3f} "
          f"delta={h1_delta['point_delta']:+.4f} "
          f"CI [{h1_delta['ci_lo']:+.4f}, {h1_delta['ci_hi']:+.4f}] "
          f"(n={h1_delta['n_pairs']} pairs, descriptive)")

    # H2 (exploratory): same, by stratum
    print("\n=== H2: By stratum (pair level) ===")
    h2 = {}
    for stratum_name in ["disagreement", "hard_similar"]:
        def sf(p, _s=stratum_name):
            return p.get("stratum") == _s
        f_s = pair_level_agreement(labels, pairs_manifest, "fusion", pair_filter=sf)
        c_s = pair_level_agreement(labels, pairs_manifest, "cosine", pair_filter=sf)
        if len(f_s):
            h2[stratum_name] = bootstrap_pair_delta(f_s, c_s)
            print(f"  [{stratum_name}] fusion={f_s.mean():.3f} cosine={c_s.mean():.3f} "
                  f"delta={h2[stratum_name]['point_delta']:+.4f} "
                  f"CI [{h2[stratum_name]['ci_lo']:+.4f}, {h2[stratum_name]['ci_hi']:+.4f}] "
                  f"n={len(f_s)}")

    # Three-ranker comparison (pair level)
    print("\n=== Three-ranker comparison (pair level) ===")
    three = {}
    for name in ["fusion", "cosine", "rules"]:
        a = pair_level_agreement(labels, pairs_manifest, name)
        three[name] = round(float(a.mean()), 4) if len(a) else None
        print(f"  {name:10s} agreement: {three[name]}")

    # Proxy label accuracy: how often the listener's majority vote picks the same-pack item
    proxy_agree = np.array(
        [1.0 if v == "positive" else 0.0 for v in labels.values() if v is not None]
    )
    print(f"\n=== Proxy label vs listener: {proxy_agree.mean():.3f} "
          f"of {len(proxy_agree)} pairs ===")

    # Intra-rater reliability across sessions
    print("\n=== Intra-rater reliability ===")
    irr = intra_rater_reliability(raters, pairs_manifest)
    print(f"  {irr}")
    if irr.get("mean_kappa") is not None and irr["mean_kappa"] < 0.4:
        print("  WARNING: mean kappa < 0.4 -- treat all results as descriptive")

    # Secondary, descriptive: per-observation McNemar (sessions are not independent)
    fusion_all = compute_agreement(raters, pairs_manifest, "fusion")
    cosine_all = compute_agreement(raters, pairs_manifest, "cosine")
    mcnemar = None
    if fusion_all["observations"] and cosine_all["observations"]:
        mcnemar = mcnemar_test(fusion_all["observations"], cosine_all["observations"])
        print(f"\n(secondary) per-observation McNemar: chi2={mcnemar['chi2']:.3f} "
              f"p={mcnemar['p_value']:.4f}  n={fusion_all['n_valid']} observations")

    report = {
        "protocol": "research/prereg_human_v1.md",
        "design": "single rater, majority vote over sessions, pair-level analysis",
        "n_sessions": len(raters),
        "exclusions": exclusions,
        "n_pairs_labeled": n_labeled,
        "h1_pair_level": {**h1, "agreement_fusion": round(float(fusion_pairs.mean()), 4),
                          "agreement_cosine": round(float(cosine_pairs.mean()), 4),
                          "bootstrap_delta": h1_delta},
        "h2_by_stratum": h2,
        "three_ranker_agreement": three,
        "proxy_label_agreement": round(float(proxy_agree.mean()), 4),
        "intra_rater_reliability": irr,
        "secondary_per_observation_mcnemar": mcnemar,
        "n_no_preference_observations": fusion_all["n_no_preference"],
    }

    with open(out_dir / "human_eval_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nSaved report to {out_dir / 'human_eval_report.json'}")


if __name__ == "__main__":
    main()
