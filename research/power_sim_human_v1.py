"""Power simulation for prereg_human_v1.md, section 4.1.

Simulates the primary analysis (McNemar on paired agreement indicators,
rater-clustered bootstrap on the delta) under a specified true effect, with
the actual pair manifest: only pairs where fusion_pick != cosine_pick can
produce discordant observations, so power is driven by that subset.

Usage:
  backend/.venv/bin/python research/power_sim_human_v1.py \
    --pairs research/data/listening_test/pairs.json --raters 10
"""

import argparse
import json
import pathlib

import numpy as np
from scipy.stats import chi2 as chi2_dist

ALPHA = 0.05


def simulate_once(rng, n_disagree, n_agree, n_raters, p_fusion, p_nopref, p_agree_both):
    """One synthetic study. Returns (delta, mcnemar_p).

    On disagreement pairs a rater sides with fusion's pick with prob p_fusion
    (else cosine's pick). On agreement pairs both rankers pick the same item
    and the rater matches it with prob p_agree_both. No-preference answers
    are dropped, as in the analysis plan.
    """
    f, c = [], []
    for _ in range(n_raters):
        for _ in range(n_disagree):
            if rng.random() < p_nopref:
                continue
            sides_with_fusion = rng.random() < p_fusion
            f.append(1.0 if sides_with_fusion else 0.0)
            c.append(0.0 if sides_with_fusion else 1.0)
        for _ in range(n_agree):
            if rng.random() < p_nopref:
                continue
            match = 1.0 if rng.random() < p_agree_both else 0.0
            f.append(match)
            c.append(match)
    f = np.array(f)
    c = np.array(c)
    a_only = np.sum((f == 1) & (c == 0))
    b_only = np.sum((f == 0) & (c == 1))
    n_d = a_only + b_only
    if n_d == 0:
        return 0.0, 1.0
    chi2 = (abs(a_only - b_only) - 1) ** 2 / n_d
    return float(f.mean() - c.mean()), float(chi2_dist.sf(chi2, df=1))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", default="research/data/listening_test/pairs.json")
    parser.add_argument("--raters", type=int, nargs="+", default=[10, 15])
    parser.add_argument("--sims", type=int, default=2000)
    parser.add_argument("--nopref", type=float, default=0.15)
    parser.add_argument("--output", default="artifacts/human-eval-v1/power_sim.json")
    args = parser.parse_args()

    manifest = json.loads(pathlib.Path(args.pairs).read_text())
    pairs = manifest["pairs"]
    n_disagree = sum(1 for p in pairs if p["fusion_pick"] != p["cosine_pick"])
    n_agree = len(pairs) - n_disagree
    print(f"{len(pairs)} pairs: {n_disagree} discordant-capable, {n_agree} concordant")

    rng = np.random.default_rng(20261018)
    results = {}
    for n_raters in args.raters:
        for p_fusion in (0.55, 0.60, 0.65, 0.70, 0.75):
            deltas, ps = [], []
            for _ in range(args.sims):
                d, p = simulate_once(rng, n_disagree, n_agree, n_raters, p_fusion,
                                     args.nopref, p_agree_both=0.7)
                deltas.append(d)
                ps.append(p)
            power = float(np.mean(np.array(ps) < ALPHA))
            mean_delta = float(np.mean(deltas))
            results[f"raters={n_raters},p_fusion={p_fusion}"] = {
                "n_raters": n_raters, "p_fusion_on_discordant": p_fusion,
                "expected_overall_delta_pp": round(mean_delta * 100, 1),
                "power": round(power, 3),
            }
            print(f"  raters={n_raters:2d}  P(side with fusion | discordant)={p_fusion:.2f}  "
                  f"overall delta={mean_delta * 100:+5.1f} pp  power={power:.2f}")

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "protocol": "research/prereg_human_v1.md section 4.1",
        "pairs_file": args.pairs,
        "n_pairs": len(pairs), "n_discordant_capable": n_disagree, "n_concordant": n_agree,
        "no_preference_rate_assumed": args.nopref, "p_agree_both_assumed": 0.7,
        "sims_per_cell": args.sims, "alpha": ALPHA,
        "results": results,
        "note": "McNemar with continuity correction on all valid (rater, pair) observations; "
                "only discordant-capable pairs contribute to the test statistic.",
    }, indent=2))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
