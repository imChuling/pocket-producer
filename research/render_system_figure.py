"""Generate the system figure for the ISMIR LBD paper.

Color palette: soft academic pastels.
Layout: 2x3 grid, U-shaped flow, feedback loop on the left.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import pathlib

DPI = 300
PDF_METADATA = {"CreationDate": None, "Producer": None, "Creator": None}

COLORS = {
    "session":     "#9bcae7",
    "fingerprint": "#d4e6a9",
    "retrieval":   "#a3aad5",
    "fusion":      "#d4bfdc",
    "ranking":     "#f9d1d2",
    "action":      "#c3a8af",
    "arrow":       "#444444",
    "feedback":    "#477dc0",
    "edge":        "#3a3a3a",
    "text":        "#1a1a1a",
    "subtext":     "#555555",
    "badge_bg":    "#4a4a4a",
    "badge_text":  "#ffffff",
}

BOX_W = 2.0
BOX_H = 0.9
GAP_X = 0.45
GAP_Y = 0.5
BADGE_R = 0.13


def draw_box(ax, cx, cy, num, label, sublabel, color):
    x0 = cx - BOX_W / 2
    y0 = cy - BOX_H / 2

    shadow = FancyBboxPatch(
        (x0 + 0.025, y0 - 0.025), BOX_W, BOX_H,
        boxstyle="round,pad=0.1",
        facecolor="#00000010", edgecolor="none", zorder=1,
    )
    ax.add_patch(shadow)

    box = FancyBboxPatch(
        (x0, y0), BOX_W, BOX_H,
        boxstyle="round,pad=0.1",
        facecolor=color, edgecolor=COLORS["edge"], linewidth=0.9, zorder=2,
    )
    ax.add_patch(box)

    badge_x = x0 - 0.05
    badge_y = y0 + BOX_H + 0.05
    circle = plt.Circle((badge_x, badge_y), BADGE_R,
                         facecolor=COLORS["badge_bg"], edgecolor="none", zorder=5)
    ax.add_patch(circle)
    ax.text(badge_x, badge_y, str(num),
            ha="center", va="center", fontsize=7,
            fontweight="bold", color=COLORS["badge_text"], zorder=6)

    ax.text(cx, cy + 0.12, label, ha="center", va="center",
            fontsize=8.5, fontweight="semibold", color=COLORS["text"], zorder=3)
    if sublabel:
        ax.text(cx, cy - 0.16, sublabel, ha="center", va="center",
                fontsize=6, color=COLORS["subtext"], style="italic", zorder=3)


def draw_arrow_simple(ax, x1, y1, x2, y2, color=None, lw=1.2, ls="-",
                      shrinkA=0, shrinkB=0):
    color = color or COLORS["arrow"]
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>", color=color, linewidth=lw, linestyle=ls,
        mutation_scale=12, zorder=4, shrinkA=shrinkA, shrinkB=shrinkB,
    )
    ax.add_patch(arrow)


def render(out_pdf, out_png=None):
    fig_w, fig_h = 7.2, 3.4
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    ax.set_aspect("equal")
    ax.axis("off")

    row1_y = 2.1
    row2_y = 0.5
    xs = [1.3, 1.3 + BOX_W + GAP_X, 1.3 + 2 * (BOX_W + GAP_X)]

    top = [
        (1, "Audiotool Session",     "live Nexus document",               "session"),
        (2, "Session Fingerprint",   "tempo, roles, chroma, intent",      "fingerprint"),
        (3, "Multi-Space Retrieval", "cosine, tempo, key, tag, role",     "retrieval"),
    ]
    bot = [
        (6, "Reversible Insertion",  "single-transaction undo",           "action"),
        (5, "Ladder Ranking",        "rules → fusion → reranker", "ranking"),
        (4, "BPR Fusion",            "5-param logistic, +4.0 pp",         "fusion"),
    ]

    for i, (n, lbl, sub, key) in enumerate(top):
        draw_box(ax, xs[i], row1_y, n, lbl, sub, COLORS[key])
    for i, (n, lbl, sub, key) in enumerate(bot):
        draw_box(ax, xs[i], row2_y, n, lbl, sub, COLORS[key])

    # Top row arrows (right)
    for i in range(2):
        draw_arrow_simple(ax,
            xs[i] + BOX_W / 2 + 0.04, row1_y,
            xs[i+1] - BOX_W / 2 - 0.04, row1_y)

    # Right side: down
    draw_arrow_simple(ax,
        xs[2], row1_y - BOX_H / 2 - 0.04,
        xs[2], row2_y + BOX_H / 2 + 0.04)

    # Bottom row arrows (left)
    for i in range(2, 0, -1):
        draw_arrow_simple(ax,
            xs[i] - BOX_W / 2 - 0.04, row2_y,
            xs[i-1] + BOX_W / 2 + 0.04, row2_y)

    # Feedback loop (dashed blue, left side)
    fb_x = xs[0] - BOX_W / 2 - 0.4
    segments = [
        ((xs[0] - BOX_W / 2 - 0.04, row2_y), (fb_x, row2_y), "-"),
        ((fb_x, row2_y), (fb_x, row1_y), "-"),
        ((fb_x, row1_y), (xs[0] - BOX_W / 2 - 0.04, row1_y), "-|>"),
    ]
    for (x1, y1), (x2, y2), style in segments:
        a = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle=style, color=COLORS["feedback"],
            linewidth=1.0, linestyle="--", mutation_scale=11, zorder=4,
        )
        ax.add_patch(a)

    ax.text(fb_x - 0.15, (row1_y + row2_y) / 2, "preference\nfeedback",
            ha="center", va="center", fontsize=6,
            color=COLORS["feedback"], rotation=90, style="italic")

    margin = 0.3
    ax.set_xlim(fb_x - 0.5, xs[2] + BOX_W / 2 + margin)
    ax.set_ylim(row2_y - BOX_H / 2 - margin, row1_y + BOX_H / 2 + BADGE_R + 0.25)

    fig.savefig(out_pdf, metadata=PDF_METADATA, bbox_inches="tight", pad_inches=0.05)
    if out_png:
        fig.savefig(out_png, bbox_inches="tight", pad_inches=0.05, dpi=DPI)
    plt.close(fig)


def main():
    base = pathlib.Path(__file__).resolve().parent.parent
    out_pdf = base / "docs" / "ismir2026" / "assets" / "system-figure.pdf"
    out_png = "/tmp/system-figure-preview.png"
    render(out_pdf, out_png)
    print(f"→ {out_pdf}")
    print(f"→ {out_png}")


if __name__ == "__main__":
    main()
