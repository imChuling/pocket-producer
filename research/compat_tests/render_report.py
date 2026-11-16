"""Figures for a behavioural-test report.

    python -m research.compat_tests.render_report --report <report.json> --output <dir>

Writes pass_matrix, pitch_response and artefact_inflation, each as PNG
(300 dpi) and PDF.
"""

import argparse
import json
import pathlib

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

DISPLAY_NAMES = {
    "clap_cos_mix": "MS-CLAP cosine (mix)",
    "clap_cos_mean": "MS-CLAP cosine (mean)",
    "clap_cos_max": "MS-CLAP cosine (max)",
    "laion_cos_mix": "LAION-CLAP cosine (mix)",
    "fusion5_online": "Fusion, as deployed",
    "fusion5_with_key": "Fusion with key",
    "harmonic_transpose_invariant": "Harmonic fit (any key)",
    "tempo": "Tempo match",
    "key_exact": "Key match (exact)",
    "key_fifth": "Key match (fifths)",
    "chroma_as_is": "Chroma",
    "chroma_beat_aligned": "Beat-aligned chroma",
    "progression_search": "Best alignment (any key, any delay)",
    "rhythm_on_grid": "Rhythm on beat grid",
    "onset_pattern": "Onset pattern",
    "cocola": "COCOLA",
}

GROUPS = [
    ("Embedding similarity", ["clap_cos_mix", "clap_cos_mean", "clap_cos_max", "laion_cos_mix"]),
    (
        "Deployed signals",
        [
            "fusion5_online",
            "fusion5_with_key",
            "harmonic_transpose_invariant",
            "tempo",
            "key_exact",
            "key_fifth",
        ],
    ),
    (
        "Classical features",
        [
            "chroma_as_is",
            "chroma_beat_aligned",
            "progression_search",
            "rhythm_on_grid",
            "onset_pattern",
        ],
    ),
    ("Coherence model", ["cocola"]),
]

PITCH_SCORERS = [
    "chroma_as_is",
    "chroma_beat_aligned",
    "cocola",
    "clap_cos_mix",
    "laion_cos_mix",
    "fusion5_online",
]

# Okabe-Ito, distinguishable under the common forms of colour blindness.
LINE_COLORS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]
BAR_COLORS = ("#0072B2", "#E69F00")

PASS_MARK, REVERSED_MARK = "▲", "▼"

# Cells a signal is not built to respond to: rhythm-only signals ignore pitch
# and bar-level harmony, harmony-only signals ignore sub-beat timing and tempo,
# and the best-alignment search maximises over key and delay by design.
# Embeddings, fusion and COCOLA claim general compatibility, so none here.
_RHYTHM_ONLY = ("rhythm_on_grid", "onset_pattern", "tempo")
_HARMONY_ONLY = (
    "chroma_as_is",
    "chroma_beat_aligned",
    "key_exact",
    "key_fifth",
    "harmonic_transpose_invariant",
)
OUT_OF_SCOPE = {
    **{name: frozenset({"P2", "P4"}) for name in _RHYTHM_ONLY},
    **{name: frozenset({"P5", "tempo_control"}) for name in _HARMONY_ONLY},
    "progression_search": frozenset({"P2", "P4"}),
}


def display(name: str) -> str:
    return DISPLAY_NAMES.get(name, name)


def verdict(summary: dict | None) -> str | None:
    """'pass' if the CI lies above 0.5, 'reversed' if below, else 'blind'."""
    if not summary or summary.get("wins") is None:
        return None
    lo, hi = summary.get("ci95") or (None, None)
    if lo is not None and lo > 0.5:
        return "pass"
    if hi is not None and hi < 0.5:
        return "reversed"
    return "blind"


def grouped_scorers(report: dict) -> list[tuple[str, list[str]]]:
    present = list(report.get("scorers", []))
    groups = [(title, [s for s in names if s in present]) for title, names in GROUPS]
    known = {s for _, names in GROUPS for s in names}
    other = [s for s in present if s not in known]
    if other:
        groups.append(("Other", other))
    return [(title, names) for title, names in groups if names]


def _test_summary(report: dict, test: str, scorer: str, key: str) -> dict | None:
    entry = report.get("tests", {}).get(test, {}).get("scorers", {}).get(scorer)
    return entry.get(key) if entry else None


def _pooled(report: dict, name: str, scorer: str) -> dict | None:
    return report.get("pooled", {}).get(name, {}).get(scorer)


ENDPOINTS = [
    ("P1", "True stem\nvs random", lambda r, s: r.get("reference_true_vs_random", {}).get(s)),
    ("P2", "Transposed\n(vs control)", lambda r, s: _pooled(r, "pitch_vs_control", s)),
    ("P3", "Tape-speed\nchange", lambda r, s: _pooled(r, "varispeed", s)),
    (
        "P4",
        "One bar late\n(harmony moves)",
        lambda r, s: _test_summary(r, "beatshift4", s, "harmony_moves"),
    ),
    ("P5", "0.37 beat late", lambda r, s: _test_summary(r, "beatshift0.37", s, "vs_original")),
]
CONTROL_COLUMN = (
    "tempo_control",
    "Tempo change\n(vs control)",
    lambda r, s: _pooled(r, "tempo_vs_control", s),
)


def _save(fig, output: pathlib.Path, stem: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fig.savefig(output / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(output / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def pass_matrix(report: dict, output: pathlib.Path) -> None:
    groups = grouped_scorers(report)
    columns = [*ENDPOINTS, CONTROL_COLUMN]
    col_x = [float(i) for i in range(len(ENDPOINTS))] + [len(ENDPOINTS) + 0.35]
    gap = 0.5

    rows, y = [], 0.0
    group_spans = []
    for title, names in groups:
        top = y
        for name in names:
            rows.append((name, y))
            y += 1.0
        group_spans.append((title, top, y))
        y += gap
    height = y - gap

    cmap = plt.get_cmap("PuOr_r")
    norm = TwoSlopeNorm(vmin=0.2, vcenter=0.5, vmax=0.8)

    fig, ax = plt.subplots(figsize=(1.25 * len(columns) + 3.4, 0.36 * height + 2.0))
    for name, row_y in rows:
        for (key, _, getter), x in zip(columns, col_x):
            summary = getter(report, name)
            call = verdict(summary)
            if call is None:
                continue
            wins = float(summary["wins"])
            colour = cmap(norm(np.clip(wins, 0.2, 0.8)))
            ax.add_patch(Rectangle((x, row_y), 1, 1, facecolor=colour, edgecolor="white", lw=1.5))
            if key in OUT_OF_SCOPE.get(name, ()):
                with plt.rc_context({"hatch.linewidth": 0.6}):
                    ax.add_patch(
                        Rectangle(
                            (x + 0.04, row_y + 0.06),
                            0.92,
                            0.88,
                            fill=False,
                            hatch="///",
                            edgecolor="#8c8c8c",
                            lw=0,
                        )
                    )
            mark = {"pass": f" {PASS_MARK}", "reversed": f" {REVERSED_MARK}"}.get(call, "")
            strong = abs(wins - 0.5) > 0.22
            ax.text(
                x + 0.5,
                row_y + 0.5,
                f"{wins:.2f}{mark}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if strong else "#1a1a1a",
                fontweight="bold" if call != "blind" else "normal",
            )

    ax.set_xlim(-0.05, col_x[-1] + 1.05)
    ax.set_ylim(height + 0.05, -0.05)
    ax.set_xticks([x + 0.5 for x in col_x])
    ax.set_xticklabels(
        [label if code == "tempo_control" else f"{code}\n{label}" for code, label, _ in columns],
        fontsize=8,
    )
    ax.xaxis.tick_top()
    ax.set_yticks([row_y + 0.5 for _, row_y in rows])
    ax.set_yticklabels([display(name) for name, _ in rows], fontsize=8.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for title, top, bottom in group_spans:
        ax.text(
            -3.3,
            (top + bottom) / 2,
            title,
            rotation=90,
            ha="center",
            va="center",
            fontsize=8,
            color="#555555",
            transform=ax.transData,
            clip_on=False,
        )

    scalar = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    bar = fig.colorbar(scalar, ax=ax, fraction=0.035, pad=0.02)
    bar.set_label("Share of pairs where the original ranks higher", fontsize=8)
    bar.ax.tick_params(labelsize=7)
    ax.set_title("Does each scorer prefer the original?", fontsize=11, pad=46, loc="left")
    fig.text(
        0.01,
        0.005,
        f"{PASS_MARK} 95% CI above 0.5 (passes)   {REVERSED_MARK} 95% CI below 0.5 "
        "(prefers the altered version)   no mark: CI includes 0.5   blank: not measured\n"
        "hatched: the signal is not built to see this change",
        fontsize=7.5,
        color="#444444",
    )
    _save(fig, output, "pass_matrix")


def _pitch_points(report: dict, scorer: str) -> tuple[list[float], list[float]]:
    points = []
    for test in report.get("tests", {}).values():
        if test.get("family") != "pitch":
            continue
        summary = (test.get("scorers", {}).get(scorer) or {}).get("vs_original")
        if summary and summary.get("drop_in_sd") is not None:
            points.append((float(test["value"]), float(summary["drop_in_sd"])))
    points.sort()
    return [p[0] for p in points], [p[1] for p in points]


def pitch_response(report: dict, output: pathlib.Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.axhline(0.0, color="#888888", lw=0.8, zorder=0)
    drawn = 0
    for scorer, colour in zip(PITCH_SCORERS, LINE_COLORS):
        xs, ys = _pitch_points(report, scorer)
        if not xs:
            continue
        ax.plot(xs, ys, marker="o", ms=3.5, lw=1.6, color=colour, label=display(scorer))
        control = _test_summary(report, "pitch_roundtrip", scorer, "vs_original")
        if control and control.get("drop_in_sd") is not None:
            ax.axhline(float(control["drop_in_sd"]), color=colour, lw=1.0, ls="--", alpha=0.8)
        drawn += 1

    ax.set_xlabel("Transposition of the target stem (semitones)")
    ax.set_ylabel("Score drop vs original (SD of the scorer)")
    ax.set_title("How far scores fall as the target is transposed", fontsize=11, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    if drawn:
        values = sorted({x for s in PITCH_SCORERS for x in _pitch_points(report, s)[0]})
        ax.set_xticks(values)
        ax.set_xticklabels([f"{v:+g}" for v in values])
        handles, labels = ax.get_legend_handles_labels()
        handles.append(Line2D([0], [0], color="#555555", lw=1.0, ls="--"))
        labels.append("Same colour, dashed: shift up and back (processing only)")
        ax.legend(
            handles,
            labels,
            fontsize=7.5,
            frameon=False,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.16),
            ncol=2,
        )
    _save(fig, output, "pitch_response")


def artefact_inflation(report: dict, output: pathlib.Path) -> None:
    tempo_tests = [
        name for name, test in report.get("tests", {}).items() if test.get("family") == "tempo"
    ]
    rows = []
    for _, names in grouped_scorers(report):
        for scorer in names:
            summaries = [_test_summary(report, t, scorer, "vs_original") for t in tempo_tests]
            per_test = [float(s["wins"]) for s in summaries if s and s.get("wins") is not None]
            if not per_test:
                continue
            control = _pooled(report, "tempo_vs_control", scorer)
            rows.append(
                (
                    scorer,
                    float(np.mean(per_test)),
                    float(control["wins"]) if control and control.get("wins") is not None else None,
                )
            )

    fig, ax = plt.subplots(figsize=(7.2, 0.42 * max(len(rows), 1) + 1.6))
    y = np.arange(len(rows))
    h = 0.38
    ax.barh(y - h / 2, [r[1] for r in rows], height=h, color=BAR_COLORS[0],
            label="Original vs tempo-changed")
    controlled = [(i, r[2]) for i, r in enumerate(rows) if r[2] is not None]
    if controlled:
        ax.barh([i + h / 2 for i, _ in controlled], [v for _, v in controlled], height=h,
                color=BAR_COLORS[1], label="Round-trip control vs tempo-changed")
    ax.axvline(0.5, color="#555555", lw=0.9, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels([display(r[0]) for r in rows], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xlabel("Share of pairs where the first version ranks higher")
    ax.set_title(
        "Tempo: how much of the preference is processing artefact",
        fontsize=11,
        loc="left",
        pad=26,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(
        fontsize=7.5, frameon=False, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2
    )
    _save(fig, output, "artefact_inflation")


def render(report: dict, output: pathlib.Path) -> list[pathlib.Path]:
    output = pathlib.Path(output)
    pass_matrix(report, output)
    pitch_response(report, output)
    artefact_inflation(report, output)
    stems = ("pass_matrix", "pitch_response", "artefact_inflation")
    return [output / f"{s}.{ext}" for s in stems for ext in ("png", "pdf")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the behavioural-test figures")
    parser.add_argument("--report", required=True, help="report.json from run_behavioral")
    parser.add_argument("--output", required=True, help="directory for the figures")
    args = parser.parse_args()
    report = json.loads(pathlib.Path(args.report).read_text())
    for path in render(report, pathlib.Path(args.output)):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
