"""Analyze human listening evaluation results.

Pre-registered analysis script for prereg_human_v1.md.
Must be committed before first data collection session.

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


def bootstrap_delta_ci(obs_a, obs_b, rater_ids, n_bootstrap=10000, alpha=0.05):
    rng = np.random.default_rng(42)
    a = np.array(obs_a)
    b = np.array(obs_b)
    rids = np.array(rater_ids)

    unique_raters = np.unique(rids)
    n_raters = len(unique_raters)

    point_delta = float(a.mean() - b.mean())
    deltas = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        sampled = rng.choice(unique_raters, size=n_raters, replace=True)
        idx = np.concatenate([np.where(rids == r)[0] for r in sampled])
        deltas[i] = a[idx].mean() - b[idx].mean()

    lo = float(np.percentile(deltas, 100 * alpha / 2))
    hi = float(np.percentile(deltas, 100 * (1 - alpha / 2)))

    return {
        "point_delta": round(point_delta, 4),
        "ci_lo": round(lo, 4),
        "ci_hi": round(hi, 4),
        "n_bootstrap": n_bootstrap,
        "alpha": alpha,
    }


def fleiss_kappa(ratings_matrix):
    N, k = ratings_matrix.shape
    n = ratings_matrix.sum(axis=1)
    if np.any(n == 0):
        return float("nan")
    n0 = n[0]

    p_j = ratings_matrix.sum(axis=0) / (N * n0)
    P_i = (np.sum(ratings_matrix ** 2, axis=1) - n0) / (n0 * (n0 - 1))
    P_bar = P_i.mean()
    P_e = np.sum(p_j ** 2)

    if P_e == 1.0:
        return 1.0
    return float((P_bar - P_e) / (1 - P_e))


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

    # H1: fusion vs cosine, all 40 pairs
    print("\n=== H1: Fusion vs Cosine (all pairs) ===")
    fusion_all = compute_agreement(raters, pairs_manifest, "fusion")
    cosine_all = compute_agreement(raters, pairs_manifest, "cosine")

    print(f"  Fusion agreement: {fusion_all['agreement_rate']:.3f} "
          f"(n={fusion_all['n_valid']})")
    print(f"  Cosine agreement: {cosine_all['agreement_rate']:.3f} "
          f"(n={cosine_all['n_valid']})")

    mcnemar = None
    ci = None
    if fusion_all["observations"] and cosine_all["observations"]:
        mcnemar = mcnemar_test(fusion_all["observations"],
                               cosine_all["observations"])
        print(f"  McNemar: chi2={mcnemar['chi2']:.3f}, p={mcnemar['p_value']:.4f}")

        ci = bootstrap_delta_ci(
            fusion_all["observations"],
            cosine_all["observations"],
            fusion_all["rater_ids"],
        )
        print(f"  Delta (fusion - cosine): {ci['point_delta']:+.4f} "
              f"CI [{ci['ci_lo']:+.4f}, {ci['ci_hi']:+.4f}]")

    # H2: disagreement stratum vs non-disagreement stratum
    print("\n=== H2: By stratum ===")
    def _stratum_filter(name):
        def filt(p):
            return p.get("stratum") == name
        return filt

    for stratum_name in ["disagreement", "hard_similar"]:
        sf = _stratum_filter(stratum_name)
        f_s = compute_agreement(raters, pairs_manifest, "fusion", pair_filter=sf)
        c_s = compute_agreement(raters, pairs_manifest, "cosine", pair_filter=sf)
        print(f"  [{stratum_name}] fusion={f_s['agreement_rate']:.3f} "
              f"cosine={c_s['agreement_rate']:.3f} n={f_s['n_valid']}")
        if f_s["observations"] and c_s["observations"]:
            ci_s = bootstrap_delta_ci(
                f_s["observations"], c_s["observations"], f_s["rater_ids"],
            )
            print(f"    delta={ci_s['point_delta']:+.4f} "
                  f"CI [{ci_s['ci_lo']:+.4f}, {ci_s['ci_hi']:+.4f}]")

    # Three-ranker comparison
    print("\n=== Three-ranker comparison ===")
    for name in ["fusion", "cosine", "rules"]:
        result = compute_agreement(raters, pairs_manifest, name)
        print(f"  {name:10s} agreement: {result['agreement_rate']:.3f} "
              f"(n={result['n_valid']})")

    # Inter-rater reliability
    print("\n=== Inter-rater reliability ===")
    pair_ids = [p["pair_id"] for p in pairs_manifest["pairs"]]
    ratings = np.zeros((len(pair_ids), 3), dtype=int)
    pid_idx = {pid: i for i, pid in enumerate(pair_ids)}

    for rater in raters:
        for resp in rater["responses"]:
            pid = resp["pair_id"]
            if pid not in pid_idx:
                continue
            if "positive_side" not in resp:
                continue
            i = pid_idx[pid]
            if resp["choice"] == "no_preference":
                ratings[i, 2] += 1
            elif resp["choice"] == resp["positive_side"]:
                ratings[i, 0] += 1
            else:
                ratings[i, 1] += 1

    rated_rows = ratings.sum(axis=1) > 0
    if rated_rows.any():
        kappa = fleiss_kappa(ratings[rated_rows])
        print(f"  Fleiss' kappa: {kappa:.3f}")
        if kappa < 0.4:
            print("  WARNING: kappa < 0.4 -- task may be too subjective")
    else:
        print("  No rated pairs found")

    # Save report
    report = {
        "protocol": "research/prereg_human_v1.md",
        "n_raters": len(raters),
        "exclusions": exclusions,
        "h1_all_pairs": {
            "fusion_agreement": fusion_all["agreement_rate"],
            "cosine_agreement": cosine_all["agreement_rate"],
            "n_valid": fusion_all["n_valid"],
            "n_no_preference": fusion_all["n_no_preference"],
        },
    }

    if mcnemar:
        report["h1_all_pairs"]["mcnemar"] = mcnemar
    if ci:
        report["h1_all_pairs"]["bootstrap_ci"] = ci

    with open(out_dir / "human_eval_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nSaved report to {out_dir / 'human_eval_report.json'}")


if __name__ == "__main__":
    main()
