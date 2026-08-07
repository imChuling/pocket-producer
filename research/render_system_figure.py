"""Generate the system figure for the ISMIR LBD paper.

Color palette: soft academic pastels from user's reference image.
Layout: 2x3 grid with feedback loop. Column-width figure.
Output: docs/ismir2026/assets/system-figure.pdf
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
    "subtext":     "#444444",
    "num":         "#ffffff",
    "num_bg":      "#555555",
}

BOX_W = 2.1
BOX_H = 0.82
GAP_X = 0.32
GAP_Y = 0.45


def draw_box(ax, cx, cy, num, label, sublabel, color):
    x0 = cx - BOX_W / 2
    y0 = cy - BOX_H / 2

    shadow = FancyBboxPatch(
        (x0 + 0.02, y0 - 0.02), BOX_W, BOX_H,
        boxstyle="round,pad=0.08",
        facecolor="#00000012",
        edgecolor="none",
        zorder=1,
    )
    ax.add_patch(shadow)

    box = FancyBboxPatch(
        (x0, y0), BOX_W, BOX_H,
        boxstyle="round,pad=0.08",
        facecolor=color,
        edgecolor=COLORS["edge"],
        linewidth=0.9,
        zorder=2,
    )
    ax.add_patch(box)

    circle = plt.Circle((x0 + 0.22, y0 + BOX_H - 0.18), 0.12,
                         facecolor=COLORS["num_bg"], edgecolor="none", zorder=3)
    ax.add_patch(circle)
    ax.text(x0 + 0.22, y0 + BOX_H - 0.18, str(num),
            ha="center", va="center", fontsize=6.5,
            fontweight="bold", color=COLORS["num"], zorder=4)

    ax.text(cx + 0.08, cy + 0.1, label, ha="center", va="center",
            fontsize=8.5, fontweight="semibold", color=COLORS["text"], zorder=3)
    if sublabel:
        ax.text(cx + 0.08, cy - 0.16, sublabel, ha="center", va="center",
                fontsize=6, color=COLORS["subtext"], style="italic", zorder=3)


def draw_arrow(ax, x1, y1, x2, y2, color=None, lw=1.2, ls="-"):
    color = color or COLORS["arrow"]
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>",
        color=color,
        linewidth=lw,
        linestyle=ls,
        mutation_scale=12,
        zorder=5,
    )
    ax.add_patch(arrow)


def main():
    fig_w = 7.5
    fig_h = 2.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    ax.set_aspect("equal")
    ax.axis("off")

    row1_y = 1.7
    row2_y = 0.5

    xs = [
        1.2,
        1.2 + BOX_W + GAP_X,
        1.2 + 2 * (BOX_W + GAP_X),
    ]

    boxes_top = [
        (1, "Audiotool Session", "live Nexus document", "session"),
        (2, "Session Fingerprint", "tempo, roles, chroma, intent", "fingerprint"),
        (3, "Multi-Space Retrieval", "cosine, tempo, key, tag, role", "retrieval"),
    ]
    boxes_bottom = [
        (6, "Reversible Insertion", "single-transaction undo", "action"),
        (5, "Ladder Ranking", "rules → fusion → reranker", "ranking"),
        (4, "BPR Fusion", "5-param logistic, +4.0pp", "fusion"),
    ]

    for i, (num, label, sub, key) in enumerate(boxes_top):
        draw_box(ax, xs[i], row1_y, num, label, sub, COLORS[key])

    for i, (num, label, sub, key) in enumerate(boxes_bottom):
        draw_box(ax, xs[i], row2_y, num, label, sub, COLORS[key])

    # Top row arrows (right)
    for i in range(2):
        draw_arrow(ax,
                   xs[i] + BOX_W / 2 + 0.03, row1_y,
                   xs[i + 1] - BOX_W / 2 - 0.03, row1_y)

    # Right side: down
    draw_arrow(ax,
               xs[2], row1_y - BOX_H / 2 - 0.03,
               xs[2], row2_y + BOX_H / 2 + 0.03)

    # Bottom row arrows (left)
    for i in range(2, 0, -1):
        draw_arrow(ax,
                   xs[i] - BOX_W / 2 - 0.03, row2_y,
                   xs[i - 1] + BOX_W / 2 + 0.03, row2_y)

    # Feedback loop: left side, dashed blue
    fb_x = xs[0] - BOX_W / 2 - 0.35
    for (x1, y1), (x2, y2), style in [
        ((xs[0] - BOX_W / 2 - 0.03, row2_y), (fb_x, row2_y), "-"),
        ((fb_x, row2_y), (fb_x, row1_y), "-"),
        ((fb_x, row1_y), (xs[0] - BOX_W / 2 - 0.03, row1_y), "-|>"),
    ]:
        arrow = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle=style,
            color=COLORS["feedback"],
            linewidth=1.0,
            linestyle="--",
            mutation_scale=11,
            zorder=4,
        )
        ax.add_patch(arrow)

    ax.text(fb_x - 0.12, (row1_y + row2_y) / 2, "preference\nfeedback",
            ha="center", va="center", fontsize=6,
            color=COLORS["feedback"], rotation=90, style="italic",
            fontweight="medium")

    ax.set_xlim(-0.15, xs[2] + BOX_W / 2 + 0.25)
    ax.set_ylim(-0.15, row1_y + BOX_H / 2 + 0.2)

    out = pathlib.Path(__file__).resolve().parent.parent / "docs" / "ismir2026" / "assets" / "system-figure.pdf"
    fig.savefig(out, metadata=PDF_METADATA, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)

    # Also save PNG preview
    fig2, ax2 = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI)
    ax2.set_aspect("equal")
    ax2.axis("off")
    for i, (num, label, sub, key) in enumerate(boxes_top):
        draw_box(ax2, xs[i], row1_y, num, label, sub, COLORS[key])
    for i, (num, label, sub, key) in enumerate(boxes_bottom):
        draw_box(ax2, xs[i], row2_y, num, label, sub, COLORS[key])
    for i in range(2):
        draw_arrow(ax2, xs[i] + BOX_W / 2 + 0.03, row1_y,
                   xs[i + 1] - BOX_W / 2 - 0.03, row1_y)
    draw_arrow(ax2, xs[2], row1_y - BOX_H / 2 - 0.03,
               xs[2], row2_y + BOX_H / 2 + 0.03)
    for i in range(2, 0, -1):
        draw_arrow(ax2, xs[i] - BOX_W / 2 - 0.03, row2_y,
                   xs[i - 1] + BOX_W / 2 + 0.03, row2_y)
    for (x1, y1), (x2, y2), style in [
        ((xs[0] - BOX_W / 2 - 0.03, row2_y), (fb_x, row2_y), "-"),
        ((fb_x, row2_y), (fb_x, row1_y), "-"),
        ((fb_x, row1_y), (xs[0] - BOX_W / 2 - 0.03, row1_y), "-|>"),
    ]:
        arrow = FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle=style,
            color=COLORS["feedback"], linewidth=1.0, linestyle="--",
            mutation_scale=11, zorder=4,
        )
        ax2.add_patch(arrow)
    ax2.text(fb_x - 0.12, (row1_y + row2_y) / 2, "preference\nfeedback",
             ha="center", va="center", fontsize=6,
             color=COLORS["feedback"], rotation=90, style="italic", fontweight="medium")
    ax2.set_xlim(-0.15, xs[2] + BOX_W / 2 + 0.25)
    ax2.set_ylim(-0.15, row1_y + BOX_H / 2 + 0.2)
    preview = "/tmp/system-figure-preview.png"
    fig2.savefig(preview, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig2)
    print(f"→ {out}")
    print(f"→ {preview}")


if __name__ == "__main__":
    main()
