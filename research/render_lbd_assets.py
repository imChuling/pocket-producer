"""Render ISMIR LBD assets from versioned evaluation artifacts.

Numbers travel one way: evaluation/bake-off JSON → these assets → the
manuscript. Nothing is ever typed into the paper by hand. Output is
deterministic: identical inputs produce byte-identical CSV and PDFs
(matplotlib CreationDate metadata is suppressed).

Usage:
  backend/.venv/bin/python research/render_lbd_assets.py \
    --evaluation artifacts/evaluation-smoke.json \
    --capacity artifacts/model-capacity.json \
    --bakeoff artifacts/backbone-bakeoff.json \
    --weak-results artifacts/pocketrank-context-v1/metrics.json \
    --out docs/ismir2026/assets
"""

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FIGSIZE = (3.5, 2.2)  # single-column ISMIR figure
DPI = 300
PDF_METADATA = {"CreationDate": None, "Producer": None, "Creator": None}


def build_results_csv(evaluation: dict) -> str:
    lines = ["model,pairwise_accuracy,evaluated,skipped"]
    for model_id in sorted(evaluation["models"]):
        entry = evaluation["models"][model_id]
        lines.append(
            f"{model_id},{entry['pairwise_accuracy']},"
            f"{entry['evaluated']},{entry['skipped']}"
        )
    return "\n".join(lines) + "\n"


def build_dataset_facts(evaluation: dict) -> dict:
    return {
        "dataset_hash": evaluation.get("dataset_hash"),
        "commit_sha": evaluation.get("commit_sha"),
        "n_examples": evaluation.get("n_examples"),
        "label_type": evaluation.get("label_type"),
        "primary_metric": evaluation.get("primary_metric"),
        "grouping": evaluation.get("grouping"),
    }


def render_results_figure(evaluation: dict, out_path: pathlib.Path) -> None:
    models = sorted(
        (m for m, e in evaluation["models"].items() if e["pairwise_accuracy"] is not None),
        key=lambda m: evaluation["models"][m]["pairwise_accuracy"],
    )
    accuracies = [evaluation["models"][m]["pairwise_accuracy"] for m in models]
    figure, axis = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    axis.barh(range(len(models)), accuracies, color="#444444")
    axis.set_yticks(range(len(models)), models, fontsize=7)
    axis.set_xlabel("pairwise accuracy", fontsize=7)
    axis.set_xlim(0, 1)
    axis.axvline(0.5, color="#999999", linewidth=0.8, linestyle="--")
    axis.tick_params(labelsize=7)
    figure.tight_layout()
    figure.savefig(out_path, metadata=PDF_METADATA)
    plt.close(figure)


def render_system_figure(out_path: pathlib.Path) -> None:
    steps = [
        "Audiotool\nsession",
        "Session\nfingerprint",
        "Retrieval\n(RRF)",
        "Ranking\n(ladder)",
        "Reversible\naction",
        "Preference\nfeedback",
    ]
    figure, axis = plt.subplots(figsize=(7.0, 1.1), dpi=DPI)
    axis.axis("off")
    for index, label in enumerate(steps):
        axis.text(
            index * 1.18 + 0.5,
            0.5,
            label,
            ha="center",
            va="center",
            fontsize=7,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "#eeeeee", "edgecolor": "#555555"},
        )
        if index < len(steps) - 1:
            axis.annotate(
                "",
                xy=(index * 1.18 + 1.06, 0.5),
                xytext=(index * 1.18 + 0.92, 0.5),
                arrowprops={"arrowstyle": "->", "color": "#555555"},
            )
    axis.set_xlim(0, len(steps) * 1.18)
    axis.set_ylim(0, 1)
    figure.savefig(out_path, metadata=PDF_METADATA, bbox_inches="tight")
    plt.close(figure)


def build_backbone_table_tex(bakeoff: dict) -> str:
    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Backbone & Dims & R@10 & Genre & Role & Bytes/frag \\",
        r"\midrule",
    ]
    for model_id in sorted(bakeoff["models"]):
        m = bakeoff["models"][model_id]
        r10 = m["p1_same_source"]["recall_at_k"]
        genre = m["p2_genre"]["accuracy"]
        role = m["p2_role"]["accuracy"]
        dims = m["dims"]
        bpf = m["embedding_bytes_per_fragment"]
        lines.append(
            f"\\texttt{{{model_id}}} & {dims} & {r10:.3f} & {genre:.3f} "
            f"& {role:.3f} & {bpf:,} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


def build_capacity_table_tex(capacity: dict) -> str:
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Model & Params & p50\,(ms) & p95\,(ms) \\",
        r"\midrule",
    ]
    for model_id in ["linear-v1", "deepsets-v1", "pocketrank-context-v1"]:
        if model_id not in capacity.get("models", {}):
            continue
        m = capacity["models"][model_id]
        params = m["trainable_parameters"]
        p50 = m["cpu_latency_ms_p50"]
        p95 = m["cpu_latency_ms_p95"]
        lines.append(
            f"\\texttt{{{model_id}}} & {params:,} & {p50:.1f} & {p95:.1f} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


def build_weak_results_table_tex(weak_results: dict | None) -> str:
    if weak_results is None:
        return "% weak-results table: no data provided\n"
    models_raw = weak_results.get("models", {})
    if isinstance(models_raw, dict):
        entries = list(models_raw.values())
    else:
        entries = models_raw
    if not entries:
        return "% weak-results table: no model entries\n"

    # Detect multiseed format (has "aggregate" key per model)
    is_multiseed = any("aggregate" in e for e in entries if isinstance(e, dict))

    if is_multiseed:
        order = ["linear-v1", "deepsets-v1", "pocketrank-context-v1"]
        items = []
        for mid, data in models_raw.items():
            agg = data.get("aggregate", {})
            items.append({"model_id": mid, "mean": agg.get("mean", 0), "std": agg.get("std", 0),
                          "ci_lo": agg.get("ci_lo", 0), "ci_hi": agg.get("ci_hi", 0),
                          "n_seeds": agg.get("n_seeds", 1)})
        items.sort(key=lambda e: order.index(e["model_id"]) if e["model_id"] in order else 999)
        best_mean = max(e["mean"] for e in items)
        lines = [
            r"\begin{tabular}{lrr}",
            r"\toprule",
            r"Model & Val Accuracy & 95\% CI \\",
            r"\midrule",
        ]
        for item in items:
            acc_str = f"{item['mean']:.3f}$\\pm${item['std']:.3f}"
            if item["mean"] == best_mean:
                acc_str = r"\textbf{" + acc_str + "}"
            ci_str = f"[{item['ci_lo']:.3f}, {item['ci_hi']:.3f}]"
            lines.append(f"\\texttt{{{item['model_id']}}} & {acc_str} & {ci_str} \\\\")
        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        return "\n".join(lines) + "\n"

    best_acc = max(e["val_pairwise_accuracy"] for e in entries)
    order = ["linear-v1", "deepsets-v1", "pocketrank-context-v1"]
    entries.sort(key=lambda e: (
        order.index(e["model_id"]) if e["model_id"] in order else 999
    ))
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Model & Val Accuracy & Train & Val \\",
        r"\midrule",
    ]
    for entry in entries:
        mid = entry["model_id"]
        acc = entry["val_pairwise_accuracy"]
        tr = entry["train_examples"]
        val = entry["val_examples"]
        acc_str = (r"\textbf{" + f"{acc:.3f}" + "}") if acc == best_acc else f"{acc:.3f}"
        lines.append(
            f"\\texttt{{{mid}}} & {acc_str} & {tr:,} & {val:,} \\\\"
        )
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines) + "\n"


def render_all(
    evaluation: dict,
    out_dir: pathlib.Path,
    capacity: dict | None = None,
    bakeoff: dict | None = None,
    weak_results: dict | None = None,
) -> list[pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    csv_path = out_dir / "ranking-results.csv"
    csv_path.write_text(build_results_csv(evaluation))
    written.append(csv_path)

    facts = build_dataset_facts(evaluation)
    if capacity:
        facts["parameter_budget"] = capacity.get("parameter_budget")
        facts["trainable_parameters"] = {
            model_id: entry["trainable_parameters"]
            for model_id, entry in capacity.get("models", {}).items()
        }
    facts_path = out_dir / "dataset-facts.json"
    facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True))
    written.append(facts_path)

    figure_path = out_dir / "ranking-results.pdf"
    render_results_figure(evaluation, figure_path)
    written.append(figure_path)

    system_path = out_dir / "system-figure.pdf"
    render_system_figure(system_path)
    written.append(system_path)

    if bakeoff:
        tex_path = out_dir / "backbone-table.tex"
        tex_path.write_text(build_backbone_table_tex(bakeoff))
        written.append(tex_path)

    if capacity:
        tex_path = out_dir / "capacity-table.tex"
        tex_path.write_text(build_capacity_table_tex(capacity))
        written.append(tex_path)

    tex_path = out_dir / "weak-results-table.tex"
    tex_path.write_text(build_weak_results_table_tex(weak_results))
    written.append(tex_path)

    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", required=True)
    parser.add_argument("--capacity", default=None)
    parser.add_argument("--bakeoff", default=None)
    parser.add_argument("--weak-results", default=None)
    parser.add_argument("--out", default="docs/ismir2026/assets")
    args = parser.parse_args()

    evaluation = json.loads(pathlib.Path(args.evaluation).read_text())
    capacity = (
        json.loads(pathlib.Path(args.capacity).read_text())
        if args.capacity
        else None
    )
    bakeoff = (
        json.loads(pathlib.Path(args.bakeoff).read_text())
        if args.bakeoff
        else None
    )
    weak_results = (
        json.loads(pathlib.Path(args.weak_results).read_text())
        if args.weak_results
        else None
    )
    written = render_all(evaluation, pathlib.Path(args.out), capacity, bakeoff, weak_results)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
