"""Render the representation sensitivity comparison figure.

Four columns: LAION-CLAP, MS-CLAP (sw-BPR), MERT-v1-95M (sw-BPR),
Decoupled (MERT mining + CLAP signals).
Dot-and-whisker plot of fusion-minus-cosine delta per negative regime,
with source-level bootstrap 95% CIs.

Usage:
  python research/render_three_rep_figure.py
"""

from __future__ import annotations

import json
import pathlib

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.rcParams["svg.fonttype"] = "none"

import matplotlib.pyplot as plt
import numpy as np


ROOT = pathlib.Path(__file__).resolve().parent.parent
LAION = ROOT / "artifacts" / "heldout-eval-correction" / "sensitivity.json"
MSCLAP = ROOT / "artifacts" / "msclap-sensitivity-correction" / "sensitivity.json"
MERT = ROOT / "artifacts" / "heldout-eval-mert" / "sensitivity.json"
DECOUPLED = ROOT / "artifacts" / "heldout-eval-decoupled" / "sensitivity.json"
OUT_DIR = ROOT / "artifacts" / "heldout-eval-mert"
OUT_PNG = OUT_DIR / "sensitivity-comparison.png"
OUT_PDF = OUT_DIR / "sensitivity-comparison.pdf"

REGIMES = ["easy", "hard_tempo_key", "hard_similar"]
LABELS = ["easy", "tempo-key", "similar"]

REPRESENTATIONS = [
    ("LAION-CLAP", LAION, "#477DC0", "o"),
    ("MS-CLAP + sw-BPR", MSCLAP, "#ED9B69", "s"),
    ("MERT + sw-BPR", MERT, "#6BAF6B", "D"),
    ("Decoupled", DECOUPLED, "#9B6BAF", "^"),
]


def load_delta(path: pathlib.Path) -> dict[str, dict[str, float]]:
    payload = json.loads(path.read_text())
    return payload["bootstrap"]["fusion_vs_cosine"]


def render() -> None:
    deltas = {}
    for label, path, _, _ in REPRESENTATIONS:
        if not path.exists():
            print(f"WARNING: {path} not found, skipping {label}")
            continue
        deltas[label] = load_delta(path)

    if len(deltas) < 2:
        print("Need at least 2 representations to compare. Exiting.")
        return

    n_reps = len(deltas)
    fig, ax = plt.subplots(figsize=(3.48, 2.2), dpi=300)
    y = np.arange(len(REGIMES), dtype=float)

    spread = 0.18
    offsets = np.linspace(spread, -spread, n_reps)
    rep_idx = 0

    for label, _, color, marker in REPRESENTATIONS:
        if label not in deltas:
            continue
        values = np.array([100 * deltas[label][r]["point_delta"] for r in REGIMES])
        lows = np.array([100 * deltas[label][r]["ci_lo"] for r in REGIMES])
        highs = np.array([100 * deltas[label][r]["ci_hi"] for r in REGIMES])
        yerr = np.vstack((values - lows, highs - values))
        ax.errorbar(
            values,
            y + offsets[rep_idx],
            xerr=yerr,
            fmt=marker,
            color=color,
            markerfacecolor="white",
            markeredgewidth=0.9,
            markersize=4.4,
            linewidth=1.0,
            capsize=2.2,
            capthick=0.8,
            label=label,
            zorder=3,
        )
        rep_idx += 1

    ax.axvline(0, color="#555555", linewidth=0.65, zorder=1)
    ax.set_xlim(-6.0, 18.0)
    ax.set_ylim(-0.55, len(REGIMES) - 0.45)
    ax.set_yticks(y)
    ax.set_yticklabels(LABELS, fontsize=6.8)
    ax.set_xlabel("Fusion - cosine (pp)", fontsize=7.0)
    ax.tick_params(axis="y", labelsize=6.8, width=0.55, length=0, pad=2)
    ax.tick_params(axis="x", labelsize=6.2, width=0.55, length=2.5)
    ax.grid(axis="x", color="#D9DDE2", linewidth=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(
        fontsize=5.4,
        loc="lower right",
        frameon=False,
        handletextpad=0.35,
        columnspacing=0.8,
        ncols=1,
        bbox_to_anchor=(0.995, 0.02),
        borderaxespad=0,
    )
    ax.text(
        0.995, 1.02,
        "95% CI, source bootstrap",
        transform=ax.transAxes,
        ha="right", va="bottom",
        fontsize=5.2, color="#555555",
    )
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_linewidth(0.55)
        ax.spines[spine].set_color("#4A4A4A")

    ax.set_title("Configuration sensitivity across representations",
                 fontsize=7.5, pad=8, fontweight="bold")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight", pad_inches=0.03,
                metadata={"CreationDate": None, "Producer": None, "Creator": None})
    fig.savefig(OUT_PNG, dpi=600, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)

    # Print the swing statistic
    swing_data = {}
    for regime in REGIMES:
        points = [deltas[label][regime]["point_delta"] * 100
                  for label in deltas]
        swing_data[regime] = max(points) - min(points)
    max_swing = max(swing_data.values())
    print("Cross-representation swing by regime:")
    for r, s in swing_data.items():
        print(f"  {r}: {s:.1f} pp")
    print(f"  max swing: {max_swing:.1f} pp")
    print(f"-> {OUT_PDF}")
    print(f"-> {OUT_PNG}")


if __name__ == "__main__":
    render()
