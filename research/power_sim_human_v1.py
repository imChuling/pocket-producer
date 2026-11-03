"""Power for prereg_human_v1.md section 4.1 (single-rater, pair-level design).

The unit of analysis is the pair: three sessions by one listener are
collapsed to a majority vote. Only pairs where fusion_pick != cosine_pick
can separate the two rankers, so the primary test is an exact two-sided
binomial on that subset. This script reports the critical count and the
power at several per-session preference strengths, propagating a
per-session P(side with fusion) through the 3-session majority vote.

Usage:
  backend/.venv/bin/python research/power_sim_human_v1.py \
    --pairs research/data/listening_test/pairs.json
"""

import argparse
import json
import pathlib

from scipy.stats import binom

ALPHA = 0.05
SESSIONS = 3


def critical_count(n: int, alpha: float) -> int:
    """Smallest k with two-sided exact P(X >= k | p = 0.5) <= alpha."""
    return next(k for k in range(n + 1) if 2 * binom.sf(k - 1, n, 0.5) <= alpha)


def majority_prob(p_session: float, sessions: int = SESSIONS) -> float:
    """P(majority of `sessions` votes side with fusion | per-session p)."""
    return float(binom.sf(sessions // 2, sessions, p_session))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", default="research/data/listening_test/pairs.json")
    parser.add_argument("--output", default="artifacts/human-eval-v1/power_sim.json")
    args = parser.parse_args()

    pairs = json.loads(pathlib.Path(args.pairs).read_text())["pairs"]
    n = sum(1 for p in pairs if p["fusion_pick"] != p["cosine_pick"])
    k = critical_count(n, ALPHA)
    p_crit = 2 * binom.sf(k - 1, n, 0.5)
    print(f"{len(pairs)} pairs, {n} discordant-capable; reject H0 at >= {k}/{n} "
          f"(exact two-sided p = {p_crit:.3f})")

    rows = []
    for p_session in (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90):
        p_pair = majority_prob(p_session)
        power = float(binom.sf(k - 1, n, p_pair))
        rows.append({"p_session": p_session, "p_pair_majority": round(p_pair, 3),
                     "power": round(power, 3)})
        print(f"  per-session P(fusion)={p_session:.2f}  "
              f"pair-level={p_pair:.3f}  power={power:.2f}")

    out = pathlib.Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "protocol": "research/prereg_human_v1.md section 4.1 (single rater, pair-level)",
        "pairs_file": args.pairs,
        "n_pairs": len(pairs), "n_discordant_capable": n, "sessions": SESSIONS,
        "alpha": ALPHA, "critical_count": k, "critical_p_two_sided": round(p_crit, 4),
        "power": rows,
        "note": "exact binomial on majority-vote labels over the discordant-capable pairs; "
                "sessions from one listener are not treated as independent observations",
    }, indent=2))
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
