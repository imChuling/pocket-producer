"""Generate data figures for the ISMIR LBD paper using SciencePlots.

Panel (a): Pairwise accuracy by negative type (cosine vs fusion), no error bars
Panel (b): Signal ranking reversal — weak-label ablation delta vs human alignment
"""

import matplotlib
matplotlib.use("Agg")
# Embed TrueType (Type 42) fonts, not Type 3 — some conference format
# checkers reject Type 3.
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
import matplotlib.pyplot as plt
import scienceplots  # noqa: F401
import json
import pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
ABLATION7 = ROOT / "artifacts" / "ablation-7sig" / "ablation.json"
FUSION7 = ROOT / "artifacts" / "fusion-7sig" / "fusion.json"
ALIGNMENT = ROOT / "artifacts" / "human-signal-alignment" / "alignment.json"
OUT_PDF = ROOT / "docs" / "ismir2026" / "assets" / "data-figures.pdf"

PDF_METADATA = {"CreationDate": None, "Producer": None, "Creator": None}

PAL = {
    "blue":      "#477DC0",
    "orange":    "#ED9B69",
    "rose":      "#C9676D",
    "lightblue": "#9BCAE7",
    "edge":      "#3A3A3A",
    "text":      "#1A1A1A",
    "sub":       "#555555",
    "green":     "#5A9E6F",
    "purple":    "#A3AAD5",
}


def render():
    ablation7 = json.loads(ABLATION7.read_text())
    fusion7 = json.loads(FUSION7.read_text())
    alignment = json.loads(ALIGNMENT.read_text())

    plt.style.use(["science", "ieee", "no-latex"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(3.5, 2.1), dpi=300)

    # ── (a) Accuracy by negative type ──
    neg_keys = ["hard_similar", "hard_tempo_key"]
    display = ["Hard-sim", "Hard-tk"]

    cos_vals = [fusion7["per_negative_type"]["cosine-only"][k] for k in neg_keys]
    fus_vals = [fusion7["per_negative_type"]["fusion-5sig"][k] for k in neg_keys]

    x = np.arange(len(neg_keys))
    w = 0.30

    ax1.bar(x - w / 2, cos_vals, w,
            label="Cosine", color=PAL["lightblue"], edgecolor=PAL["edge"],
            linewidth=0.4)
    ax1.bar(x + w / 2, fus_vals, w,
            label="Fusion", color=PAL["orange"], edgecolor=PAL["edge"],
            linewidth=0.4)

    for i, (cv, fv) in enumerate(zip(cos_vals, fus_vals)):
        ax1.text(i - w / 2, cv + 0.018, f".{int(cv*1000)}", ha="center", va="bottom",
                 fontsize=5.5, color=PAL["text"])
        ax1.text(i + w / 2, fv + 0.018, f".{int(fv*1000)}", ha="center", va="bottom",
                 fontsize=5.5, color=PAL["text"])

    ax1.set_ylabel("Pairwise accuracy", fontsize=7, color=PAL["text"])
    ax1.set_xticks(x)
    ax1.set_xticklabels(display, fontsize=6.5)
    ax1.set_ylim(0.68, 0.98)
    ax1.legend(fontsize=6, loc="upper left", frameon=True, fancybox=False,
               edgecolor=PAL["edge"], framealpha=0.95, handlelength=1.0)
    ax1.tick_params(axis="both", labelsize=6.5, colors=PAL["text"], width=0.4)
    ax1.text(0.02, 0.97, "(a)", transform=ax1.transAxes, fontsize=8,
             fontweight="bold", va="top", color=PAL["text"])
    for spine in ax1.spines.values():
        spine.set_linewidth(0.4)
        spine.set_color(PAL["edge"])

    # ── (b) Signal--preference comparison ──
    # All left-side deltas come from ONE experiment: the 7-signal
    # leave-one-signal-out ablation (artifacts/ablation-7sig), so every
    # plotted signal has a measured weak-label contribution.
    # Role-gap is still omitted: it fired on only 2/9 consensus pairs.
    paired_signals = ["tempo", "cos mean", "cos max", "harmonic"]
    paired_weak_keys = ["minus-tempo", "minus-audio_cos_mean",
                        "minus-audio_cos_max", "minus-harmonic"]
    paired_human_keys = ["tempo", "cos_mean", "cos_max", "harmonic"]

    abl7 = ablation7["ablation"]
    full_hs7 = abl7["full-7sig"]["hard_similar_mean"]

    weak_deltas = [round((full_hs7 - abl7[sk]["hard_similar_mean"]) * 100, 1)
                   for sk in paired_weak_keys]

    sigs = alignment["signals"]
    human_rates = [sigs[hk]["consensus"][0] / sigs[hk]["consensus"][1]
                   for hk in paired_human_keys]

    weak_rank = np.argsort(np.argsort([-d for d in weak_deltas])) + 1
    human_rank_paired = np.argsort(np.argsort([-r for r in human_rates])) + 1

    y_left = [5 - r for r in weak_rank]
    y_right = [5 - r for r in human_rank_paired]

    colors = [PAL["orange"], PAL["blue"], PAL["purple"], PAL["green"]]

    ax2.set_xlim(-0.3, 1.3)
    ax2.set_ylim(0.2, 5.0)

    for i, (yl, yr) in enumerate(zip(y_left, y_right)):
        ax2.plot([0, 1], [yl, yr], color=colors[i], linewidth=1.3, zorder=3)
        ax2.scatter([0], [yl], color=colors[i], s=20, zorder=4,
                    edgecolors=PAL["edge"], linewidths=0.3)
        ax2.scatter([1], [yr], color=colors[i], s=20, zorder=4,
                    edgecolors=PAL["edge"], linewidths=0.3)

        ax2.text(-0.05, yl, f"{paired_signals[i]}", ha="right", va="center",
                 fontsize=6, color=colors[i], fontweight="bold")
        ax2.text(-0.05, yl - 0.28, f"{weak_deltas[i]:+.1f}pp", ha="right",
                 va="center", fontsize=5, color=PAL["sub"])

        ax2.text(1.05, yr, f"{paired_signals[i]}", ha="left", va="center",
                 fontsize=6, color=colors[i], fontweight="bold")
        ax2.text(1.05, yr - 0.28, f"{int(round(human_rates[i]*9))}/9", ha="left",
                 va="center", fontsize=5, color=PAL["sub"])

    ax2.text(0, 4.9, "Weak-label\nLOSO ablation", ha="center", va="top",
             fontsize=6, color=PAL["text"], fontweight="bold")
    ax2.text(1, 4.9, "Human\nalignment", ha="center", va="top",
             fontsize=6, color=PAL["text"], fontweight="bold")

    ax2.set_yticks([])
    ax2.set_xticks([])
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["bottom"].set_visible(False)
    ax2.spines["left"].set_visible(False)

    ax2.text(0.02, 0.97, "(b)", transform=ax2.transAxes, fontsize=8,
             fontweight="bold", va="top", color=PAL["text"])

    fig.tight_layout(pad=0.3, w_pad=0.8)
    fig.savefig(OUT_PDF, metadata=PDF_METADATA, bbox_inches="tight", pad_inches=0.03)
    print(f"-> {OUT_PDF}")
    plt.close(fig)


if __name__ == "__main__":
    render()
