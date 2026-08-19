"""Render the held-out sensitivity figure for the ISMIR LBD.

The figure is a dot-and-whisker plot of the held-out fusion-minus-cosine
delta, using the versioned corrective artifacts.  This is the most direct
visualization of the paper's bounded empirical claim: the apparent gain is
configuration- and negative-regime-dependent.

The plot deliberately does not show bars or connect categorical regimes with
lines.  Points show the estimate in percentage points and whiskers show the
source-level bootstrap 95% CI recorded in each artifact.
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
FACTORIAL = ROOT / "artifacts" / "factorial" / "factorial.json"
OUT_PDF = ROOT / "docs" / "ismir2026" / "assets" / "heldout-sensitivity.pdf"
OUT_SVG = ROOT / "docs" / "ismir2026" / "assets" / "heldout-sensitivity.svg"
OUT_PNG = ROOT / "docs" / "ismir2026" / "assets" / "heldout-sensitivity.png"
OUT_GRAY = ROOT / "docs" / "ismir2026" / "assets" / "heldout-sensitivity-gray.png"

PDF_METADATA = {"CreationDate": None, "Producer": None, "Creator": None}
SVG_METADATA = {"Creator": "SciPilot figure renderer"}
REGIMES = ["easy", "hard_tempo_key", "hard_similar"]
LABELS = ["easy", "tempo-key", "similar"]
COLORS = {"LAION-CLAP": "#477DC0", "MS-CLAP + sw-BPR": "#ED9B69"}
MARKERS = {"LAION-CLAP": "o", "MS-CLAP + sw-BPR": "s"}


def load_delta(path: pathlib.Path) -> dict[str, dict[str, float]]:
    payload = json.loads(path.read_text())
    return payload["bootstrap"]["fusion_vs_cosine"]


def load_factorial() -> dict[str, dict[str, float]]:
    payload = json.loads(FACTORIAL.read_text())
    return payload["fusion_cosine_deltas_pp"]


def render() -> None:
    deltas = {
        "LAION-CLAP": load_delta(LAION),
        "MS-CLAP + sw-BPR": load_delta(MSCLAP),
    }
    factorial = load_factorial()

    # Editorial two-panel layout: a forest plot for the held-out comparison
    # and a small factorial map for the development-only configuration check.
    # Both panels are data-derived; pastel blocks are only an encoding aid.
    # Stack the panels vertically.  In the two-column paper layout a side-by-
    # side heatmap makes the configuration labels unreadably small; stacking
    # gives both panels the full column width while preserving the same data.
    fig, (ax, hx) = plt.subplots(
        2, 1, figsize=(3.48, 2.95), dpi=300,
        gridspec_kw={"height_ratios": [1.35, 0.9], "hspace": 0.72},
    )
    y = np.arange(len(REGIMES), dtype=float)
    offsets = {"LAION-CLAP": 0.105, "MS-CLAP + sw-BPR": -0.105}

    for label in ("LAION-CLAP", "MS-CLAP + sw-BPR"):
        values = np.array([100 * deltas[label][r]["point_delta"] for r in REGIMES])
        lows = np.array([100 * deltas[label][r]["ci_lo"] for r in REGIMES])
        highs = np.array([100 * deltas[label][r]["ci_hi"] for r in REGIMES])
        yerr = np.vstack((values - lows, highs - values))
        ax.errorbar(
            values,
            y + offsets[label],
            xerr=yerr,
            fmt=MARKERS[label],
            color=COLORS[label],
            markerfacecolor="white",
            markeredgewidth=0.9,
            markersize=4.6,
            linewidth=1.0,
            capsize=2.4,
            capthick=0.8,
            label=label,
            zorder=3,
        )

    ax.axvline(0, color="#555555", linewidth=0.65, zorder=1)
    ax.set_xlim(-5.5, 17.8)
    ax.set_ylim(-0.55, len(REGIMES) - 0.45)
    ax.set_yticks(y)
    ax.set_yticklabels(LABELS, fontsize=6.8)
    ax.set_xlabel("Fusion − cosine (pp)", fontsize=7.0)
    ax.tick_params(axis="y", labelsize=6.8, width=0.55, length=0, pad=2)
    ax.tick_params(axis="x", labelsize=6.2, width=0.55, length=2.5)
    ax.grid(axis="x", color="#D9DDE2", linewidth=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(
        fontsize=5.6,
        loc="lower right",
        frameon=False,
        handletextpad=0.35,
        columnspacing=0.8,
        ncols=1,
        bbox_to_anchor=(0.995, 0.02),
        borderaxespad=0,
    )
    ax.text(
        0.995,
        1.02,
        "95% CI · source bootstrap",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=5.2,
        color="#555555",
    )
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_linewidth(0.55)
        ax.spines[spine].set_color("#4A4A4A")

    ax.text(-0.02, 1.16, "(a)  Held-out", transform=ax.transAxes,
            fontsize=7.2, fontweight="bold", va="top")

    # Panel (b): a compact 2x2 configuration map.  This is more informative
    # than another bar chart because it exposes the full representation x
    # training interaction behind the held-out cross-configuration swing.
    config_keys = [
        "A_laion_uniform",
        "B_laion_sourceweighted",
        "C_msclap_uniform",
        "D_msclap_sourceweighted",
    ]
    config_labels = ["L/U", "L/S", "M/U", "M/S"]
    heat_rows = ["easy", "tempo–key", "similar"]
    heat_keys = ["easy", "hard_tempo_key", "hard_similar"]
    matrix = np.array([[factorial[c][r] for c in config_keys] for r in heat_keys])
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "pp_diverging", ["#9BCAE7", "#D4BFDC", "#F9D1D2", "#ED9B69"]
    )
    norm = matplotlib.colors.TwoSlopeNorm(vmin=-4.5, vcenter=0.0, vmax=2.6)
    hx.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")
    hx.set_xticks(np.arange(len(config_labels)))
    hx.set_xticklabels(config_labels, fontsize=6.8)
    hx.set_yticks(np.arange(len(heat_rows)))
    hx.set_yticklabels(heat_rows, fontsize=6.8)
    hx.tick_params(length=0, pad=2)
    for spine in hx.spines.values():
        spine.set_visible(False)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            hx.text(j, i, f"{value:+.1f}", ha="center", va="center",
                    fontsize=7.0, color="#20262B", fontweight="bold")
    hx.set_xlabel("representation / training", fontsize=6.5, labelpad=6)
    hx.text(-0.02, 1.24, "(b)  Dev factorial", transform=hx.transAxes,
            fontsize=7.2, fontweight="bold", va="top")
    hx.text(1.0, 1.24, "L: LAION  M: MS-CLAP  U: uniform  S: source-weighted",
            transform=hx.transAxes, ha="right", va="top", fontsize=5.0,
            color="#555555")

    fig.subplots_adjust(left=0.16, right=0.995, bottom=0.22, top=0.91)
    fig.savefig(OUT_PDF, metadata=PDF_METADATA, bbox_inches="tight", pad_inches=0.025)
    fig.savefig(OUT_SVG, metadata=SVG_METADATA, bbox_inches="tight", pad_inches=0.025)
    fig.savefig(OUT_PNG, dpi=600, bbox_inches="tight", pad_inches=0.025)

    # A grayscale preview is part of the publication QA loop.
    from PIL import Image, ImageOps

    ImageOps.grayscale(Image.open(OUT_PNG)).save(OUT_GRAY)
    plt.close(fig)
    print(f"-> {OUT_PDF}")
    print(f"-> {OUT_SVG}")
    print(f"-> {OUT_PNG}")
    print(f"-> {OUT_GRAY}")


if __name__ == "__main__":
    render()
