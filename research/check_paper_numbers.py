"""Cross-check paper numbers in lbd.tex against versioned artifact JSONs.

Exits 0 if all checks pass, 1 if any fail. Designed to run before every
PDF build to catch stale/miscopied numbers.

Two-layer verification:
  1. Artifact check: hardcoded paper number == artifact value
  2. Tex presence check: number string appears in current lbd.tex

Limitations: presence checks confirm substrings exist but cannot verify
they appear in the correct context (e.g. attached to the right method).
Manual review is still required for semantic correctness.

Usage:
  python research/check_paper_numbers.py
"""

import json
import pathlib
import re
import sys
from math import isclose

ROOT = pathlib.Path(
    sys.argv[sys.argv.index("--root") + 1]
    if "--root" in sys.argv
    else pathlib.Path(__file__).resolve().parent.parent
)
TEX = ROOT / "docs" / "ismir2026" / "lbd.tex"
LOSO_TABLE = ROOT / "docs" / "ismir2026" / "assets" / "loso-table.tex"

FUSION_PACKONLY = ROOT / "artifacts" / "fusion-packonly" / "fusion.json"
ABLATION_PACKONLY = ROOT / "artifacts" / "ablation-packonly" / "ablation.json"
FUSION_MIXED = ROOT / "artifacts" / "fusion-7sig" / "fusion.json"
HELDOUT_EVAL = ROOT / "artifacts" / "heldout-eval-packonly" / "eval.json"
HELDOUT_BOOTSTRAP = ROOT / "artifacts" / "heldout-eval-packonly" / "bootstrap.json"
HELDOUT_LOSO = ROOT / "artifacts" / "heldout-eval-packonly" / "loso.json"
ALIGNMENT = ROOT / "artifacts" / "human-signal-alignment" / "alignment.json"
SPLIT = ROOT / "artifacts" / "heldout-split-packonly" / "split.json"
DEPLOY_WEIGHTS = ROOT / "artifacts" / "fusion-deploy" / "weights.json"
MSCLAP_SENSITIVITY = ROOT / "artifacts" / "msclap-sensitivity" / "sensitivity.json"

failures = []
passes = []


def check(label: str, expected, actual, tol=0.0015):
    if isinstance(expected, float) and isinstance(actual, float):
        ok = isclose(expected, actual, abs_tol=tol)
    else:
        ok = expected == actual
    if ok:
        passes.append(f"  PASS  {label}: {actual}")
    else:
        failures.append(f"  FAIL  {label}: paper={expected}, artifact={actual}")


def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def check_in_tex(label: str, needle: str, tex: str):
    if _normalize_ws(needle) in _normalize_ws(tex):
        passes.append(f"  PASS  tex/{label}: '{needle}' found")
    else:
        failures.append(f"  FAIL  tex/{label}: '{needle}' NOT in lbd.tex")


def check_not_in_tex(label: str, needle: str, tex: str):
    if _normalize_ws(needle) not in _normalize_ws(tex):
        passes.append(f"  PASS  tex/{label}: '{needle}' correctly absent")
    else:
        failures.append(
            f"  FAIL  tex/{label}: '{needle}' should be removed but is still in lbd.tex"
        )


def round3(x: float) -> float:
    return round(x, 3)


def load_json(path: pathlib.Path) -> dict | None:
    if not path.exists():
        failures.append(f"  MISS  artifact not found: {path}")
        return None
    return json.loads(path.read_text())


def check_corpus(tex: str, split: dict, eval_data: dict):
    """§3: pack-only corpus composition and split sizes."""
    check("§3/split_seed", 20260810, split["split_seed"])
    check("§3/total_sources_605", 605, split["n_total_sources"])
    check("§3/train_sources_484", 484, split["n_train_sources"])
    check("§3/heldout_sources_121", 121, split["n_heldout_sources"])
    check("§3/train_examples_981", 981, eval_data["train_examples"])

    check_in_tex("has_1797_items", "1,797", tex)
    check_in_tex("has_605_packs", "605 packs", tex)
    check_in_tex("has_484", "484", tex)
    check_in_tex("has_981", "981", tex)
    check_in_tex("has_121_source", "121-source", tex)
    check_in_tex("has_seed_20260810", "20260810", tex)
    check_in_tex("has_source_grouped", "source-grouped", tex)
    check_in_tex("has_committed_before", "committed to version control", tex)
    # Denominator honesty: query-bearing source counts must be stated.
    check_in_tex("has_171_query_sources", "171", tex)
    check_in_tex("has_54_query_sources", "54", tex)
    check_in_tex("has_323_examples", "323", tex)


def check_devset(tex: str, fusion: dict, ablation: dict):
    """§3: pack-only train-side dev numbers."""
    cos = fusion["summary"]["cosine-only"]
    cos_neg = fusion["per_negative_type"]["cosine-only"]
    f5 = fusion["summary"]["fusion-5sig"]
    f5_neg = fusion["per_negative_type"]["fusion-5sig"]

    check("§3/cosine_overall_0.929", 0.929, round3(cos["mean"]))
    check("§3/cosine_hard_sim_0.814", 0.814, round3(cos_neg["hard_similar"]))
    check("§3/fusion_overall_0.925", 0.925, round3(f5["mean"]))
    check("§3/fusion_hard_sim_0.813", 0.813, round3(f5_neg["hard_similar"]))

    gain = round((f5_neg["hard_similar"] - cos_neg["hard_similar"]) * 100, 2)
    check("§3/hard_sim_delta_-0.03pp", -0.03, gain, tol=0.005)

    # hard_tempo_key deficit: DESCRIPTIVE mean only. The earlier
    # pair-level, endpoint-averaged dev CI was statistically invalid and
    # must not reappear; inference lives in the held-out bootstrap.
    tk_diff = round(
        (f5_neg["hard_tempo_key"] - cos_neg["hard_tempo_key"]) * 100, 1
    )
    check("§3/hard_tk_diff_-2.1pp_descriptive", -2.1, tk_diff, tol=0.05)

    per_seed = ablation.get("bootstrap_ci_per_seed", {})
    if per_seed:
        n_neg = sum(
            1
            for s in per_seed.values()
            if s["paired-diff"]["hard_tempo_key"]["mean_diff"] < 0
        )
        check("§3/hard_tk_negative_in_all_5_splits", 5, n_neg)

    check_in_tex("has_0.929", "0.929", tex)
    check_in_tex("has_0.814", "0.814", tex)
    check_in_tex("has_0.925", "0.925", tex)
    check_in_tex("has_0.813", "0.813", tex)
    check_in_tex("has_-0.03pp", "-0.03", tex)
    check_in_tex("has_2.1pp", "2.1", tex)
    check_in_tex("has_descriptive", "descriptive", tex)
    check_not_in_tex("no_invalid_dev_ci", "[-3.9, -0.6]", tex)
    check_not_in_tex("no_dev_significance", "significantly \\emph{worse} than\ncosine ($-2.1$", tex)


def check_label_sensitivity(tex: str, fusion_mixed: dict):
    """§4.1: mixed-label +4.0pp claim against the old artifact."""
    cos_neg = fusion_mixed["per_negative_type"]["cosine-only"]
    f5_neg = fusion_mixed["per_negative_type"]["fusion-5sig"]
    gain = round((f5_neg["hard_similar"] - cos_neg["hard_similar"]) * 100, 1)
    check("§4.1/mixed_gain_+4.0pp", 4.0, gain)

    check_in_tex("has_+4.0pp", "+4.0", tex)
    check_in_tex("has_26pct", "26\\%", tex)
    check_in_tex("has_949_mixed", "949 sources", tex)
    check_in_tex("has_uploader", "uploader", tex)


def parse_loso_table(table_tex: str) -> dict:
    """Parse LOSO table cells: {signal: [easy, hard_similar, hard_tempo_key]}."""
    rows = {}
    for line in table_tex.splitlines():
        if "&" not in line or r"\toprule" in line or r"\midrule" in line:
            continue
        cells = [c.strip() for c in line.rstrip("\\").split("&")]
        if len(cells) != 4:
            continue
        name = re.sub(r"\\textbf\{([^}]*)\}", r"\1", cells[0])
        name = name.replace("\\_", "_").replace("\\", "").strip()
        vals = []
        for c in cells[1:]:
            m = re.search(r"([+-]?\d+\.\d+)", c)
            if m:
                vals.append(float(m.group(1)))
        if len(vals) == 3:
            rows[name] = vals
    return rows


def check_loso_table(tex: str, ablation: dict):
    """§4.2: verify LOSO table cells against the pack-only ablation."""
    table_tex = LOSO_TABLE.read_text() if LOSO_TABLE.exists() else ""
    table_rows = parse_loso_table(table_tex)
    abl = ablation["ablation"]
    full = abl["full-fusion"]

    signals = {
        "audio_cos_mean": "minus-audio_cos_mean",
        "audio_cos_max": "minus-audio_cos_max",
        "tempo": "minus-tempo",
        "key": "minus-key",
        "tag_jaccard": "minus-tag_jaccard",
    }
    neg_order = ["easy", "hard_similar", "hard_tempo_key"]
    for sig_name, minus_key in signals.items():
        row = table_rows.get(sig_name)
        if row is None:
            failures.append(f"  FAIL  loso_table/{sig_name}: row not found in table tex")
            continue
        for col, neg_type in enumerate(neg_order):
            key = f"{neg_type}_mean"
            artifact_pp = round((abl[minus_key][key] - full[key]) * 100, 2)
            check(
                f"loso_table/{sig_name}/{neg_type}",
                row[col],
                artifact_pp,
                tol=0.005,
            )

    check_in_tex("has_-0.96", "-0.96", tex)
    check_in_tex("has_+0.68", "+0.68", tex)
    check_in_tex("has_key_+0.94", "+0.94", tex)
    check_in_tex("has_key_+1.21", "+1.21", tex)
    check_in_tex("has_loso", "leave-one-signal-out", tex)
    check_in_tex("has_construction_caveat", "built in", tex)


def check_heldout_loso(tex: str, loso: dict):
    """§4.2: held-out LOSO directional replication."""
    tempo = loso["loso_deltas"]["tempo"]
    key = loso["loso_deltas"]["key"]
    check("§4.2/heldout_tempo_hs_-1.48", -1.48, round(tempo["hard_similar"] * 100, 2))
    check("§4.2/heldout_tempo_tk_+0.37", 0.37, round(tempo["hard_tempo_key"] * 100, 2))
    check("§4.2/heldout_key_hs_+0.62", 0.62, round(key["hard_similar"] * 100, 2))
    check("§4.2/heldout_key_tk_+0.97", 0.97, round(key["hard_tempo_key"] * 100, 2))

    check_in_tex("has_-1.48", "-1.48", tex)
    check_in_tex("has_+0.37", "+0.37", tex)
    check_in_tex("has_+0.62", "+0.62", tex)
    check_in_tex("has_+0.97", "+0.97", tex)


def check_heldout(tex: str, eval_data: dict, bootstrap: dict):
    """§4.3: single confirmatory run + corrected bootstrap CIs."""
    delta_hs = round(eval_data["track1_delta"]["hard_similar"] * 100, 1)
    check("§4.3/heldout_hard_sim_+1.5pp", 1.5, delta_hs, tol=0.05)

    pool_hs = bootstrap["pooled"]["hard_similar"]
    check("§4.3/hs_ci_lo_-1.5", -1.5, round(pool_hs["ci_lo"] * 100, 1), tol=0.05)
    check("§4.3/hs_ci_hi_+4.7", 4.7, round(pool_hs["ci_hi"] * 100, 1), tol=0.05)
    check("§4.3/hs_ci_crosses_zero", True, pool_hs["ci_lo"] < 0 < pool_hs["ci_hi"])

    pool_tk = bootstrap["pooled"]["hard_tempo_key"]
    check("§4.3/tk_delta_-1.0pp", -1.0, round(pool_tk["point_delta"] * 100, 1), tol=0.05)
    check("§4.3/tk_ci_below_zero", True, pool_tk["ci_hi"] < 0)

    pool_all = bootstrap["pooled"]["overall"]
    check("§4.3/overall_+0.4pp", 0.4, round(pool_all["point_delta"] * 100, 1), tol=0.05)
    check("§4.3/overall_ci_crosses_zero", True,
          pool_all["ci_lo"] < 0 < pool_all["ci_hi"])

    method = bootstrap.get("method", "")
    check("§4.3/joint_resampling_method", True, "joint source resampling" in method)

    check_in_tex("has_+1.5pp", "+1.5", tex)
    check_in_tex("has_hs_ci", "[-1.5, +4.7]", tex)
    check_in_tex("has_-1.0pp", "-1.0", tex)
    check_in_tex("has_+0.4pp", "+0.4", tex)
    check_in_tex("has_joint_resampling", "joint", tex)
    check_in_tex("has_bootstrap", "bootstrap", tex)
    check_in_tex("has_sensitivity_reanalysis", "sensitivity re-analysis", tex)


def check_pilot(tex: str, alignment: dict):
    """§4.4: exploratory pilot numbers."""
    check("§4.4/n_consensus_9", 9, alignment["n_consensus"])
    sigs = alignment["signals"]
    check("§4.4/harmonic_7_of_9", 7, sigs["harmonic"]["consensus"][0])
    check("§4.4/tempo_3_of_9", 3, sigs["tempo"]["consensus"][0])

    check("§4.4/n_preference_19", 19, alignment["n_preference"])
    check("§4.4/n_pairs_20", 20, alignment["n_pairs"])

    check_in_tex("has_kappa_0.294", "0.294", tex)
    check_in_tex("has_7/9", "7/9", tex)
    check_in_tex("has_3/9", "3/9", tex)
    check_in_tex("has_19_preference", "19", tex)
    check_in_tex("has_neither_exclusion", "neither", tex)


def check_deployment(tex: str, weights: dict):
    """§2: deployed fusion claims match the shipped artifact."""
    check("§2/deploy_model_id", "fusion-5sig-v1", weights["model_id"])
    check("§2/deploy_5_weights", 5, len(weights["weights"]))
    check("§2/deploy_space_msclap", ["msclap-2023"], weights["representation_model"])
    check("§2/deploy_trained_packonly", True,
          "pack-only train split" in weights.get("trained_on", ""))
    check("§2/deploy_source_weighted", True,
          "source-weighted BPR" in weights.get("trained_on", ""))

    check_in_tex("has_separate_production_model", "separate production model", tex)
    check_in_tex("has_msclap_delta", "MS-CLAP", tex)
    check_in_tex("has_key_zero_online", "constant zero online", tex)
    check_in_tex("has_fallback", "falls back", tex)
    # Gate C: rules is the default; fusion is selectable, never default.
    check_in_tex("has_rules_default", "default} ranker is the", tex)
    check_in_tex("has_fusion_selectable", "selectable", tex)
    check_not_in_tex("no_fusion_default", "is the default when session audio", tex)
    # The deployed model is NOT the offline-evaluated model (different
    # backbone, weights, and training data); the paper must not say so.
    check_not_in_tex("no_same_fusion_model", "same fusion model", tex)
    check_not_in_tex("no_active_regions", "active regions", tex)


def check_msclap_sensitivity(tex: str, sens: dict):
    """§4.2+§4.3: MS-CLAP sensitivity re-analysis numbers."""
    bs = sens["bootstrap"]["fusion_vs_cosine"]

    hs = bs["hard_similar"]
    check("§4.3/msclap_hs_+9.2pp", 9.2,
          round(hs["point_delta"] * 100, 1), tol=0.05)
    check("§4.3/msclap_hs_ci_lo_+4.3", 4.3,
          round(hs["ci_lo"] * 100, 1), tol=0.05)
    check("§4.3/msclap_hs_ci_hi_+14.3", 14.3,
          round(hs["ci_hi"] * 100, 1), tol=0.05)
    check("§4.3/msclap_hs_ci_above_zero", True, hs["ci_lo"] > 0)

    htk = bs["hard_tempo_key"]
    check("§4.3/msclap_htk_-1.8pp", -1.8,
          round(htk["point_delta"] * 100, 1), tol=0.05)
    check("§4.3/msclap_htk_ci_lo_-4.5", -4.5,
          round(htk["ci_lo"] * 100, 1), tol=0.05)
    check("§4.3/msclap_htk_ci_hi_+0.6", 0.6,
          round(htk["ci_hi"] * 100, 1), tol=0.05)

    overall = bs["overall"]
    check("§4.3/msclap_overall_+2.0pp", 2.0,
          round(overall["point_delta"] * 100, 1), tol=0.05)
    check("§4.3/msclap_overall_ci_lo_+0.6", 0.6,
          round(overall["ci_lo"] * 100, 1), tol=0.05)
    check("§4.3/msclap_overall_ci_hi_+3.5", 3.5,
          round(overall["ci_hi"] * 100, 1), tol=0.05)

    loso = sens["loso"]
    full_hs = loso["full-5sig"]["mean_hard_similar"]
    full_htk = loso["full-5sig"]["mean_hard_tempo_key"]
    tempo_hs = round((loso["minus-tempo"]["mean_hard_similar"] - full_hs) * 100, 1)
    tempo_htk = round((loso["minus-tempo"]["mean_hard_tempo_key"] - full_htk) * 100, 1)
    key_hs = round((loso["minus-key"]["mean_hard_similar"] - full_hs) * 100, 1)
    check("§4.2/msclap_tempo_hs_-6.9", -6.9, tempo_hs, tol=0.05)
    check("§4.2/msclap_tempo_htk_+0.7", 0.7, tempo_htk, tol=0.05)
    check("§4.2/msclap_key_hs_-0.4", -0.4, key_hs, tol=0.05)

    check_in_tex("has_msclap_+9.2", "+9.2", tex)
    check_in_tex("has_msclap_hs_ci", "[+4.3, +14.3]", tex)
    check_in_tex("has_msclap_htk_-1.8", "-1.8", tex)
    check_in_tex("has_msclap_htk_ci", "[-4.5, +0.6]", tex)
    check_in_tex("has_msclap_overall_+2.0", "+2.0", tex)
    check_in_tex("has_msclap_overall_ci", "[+0.6, +3.5]", tex)
    check_in_tex("has_7.7pp_swing", "7.7", tex)
    check_in_tex("has_msclap_tempo_-6.9", "-6.9", tex)
    check_in_tex("has_msclap_key_reversal", "-0.4", tex)
    check_in_tex("has_representation_sensitive", "representation-sensitive", tex)
    check_in_tex("has_source_weighted_bpr", "source-weighted BPR", tex)


def check_removed_claims(tex: str):
    """Deleted claims that must NOT reappear in prose."""
    check_not_in_tex("no_v1_cosine_0.883", "0.883", tex)
    check_not_in_tex("no_v1_fusion_0.794", "0.794", tex)
    check_not_in_tex("no_v1_heldout_+0.83", "+0.83", tex)
    check_not_in_tex("no_v1_ci", "[-2.38, +4.17]", tex)
    check_not_in_tex("no_v1_seed", "20260809", tex)
    check_not_in_tex("no_v1_1755", "1,755", tex)
    check_not_in_tex("no_v1_949_packs", "949 FSLD", tex)
    check_not_in_tex("no_frozen_before", "frozen before", tex)
    check_not_in_tex("no_preregistered_claim", "preregister", tex)
    check_not_in_tex("no_viable", "viable", tex)
    check_not_in_tex("no_p_0.031", "p=0.031", tex)
    check_not_in_tex("no_sign_test", "sign test", tex)
    check_not_in_tex("no_proper_generalization", "proper generalization", tex)


def check_ledger_consistency():
    """Verify claim-evidence ledger references current paper structure."""
    ledger_path = ROOT / "docs" / "ismir2026" / "claim-evidence-ledger.md"
    if not ledger_path.exists():
        failures.append("  MISS  claim-evidence-ledger.md not found")
        return

    text = ledger_path.read_text()

    check_in_tex("ledger/has_packonly", "pack-only", text)
    check_in_tex("ledger/has_+1.5pp", "+1.5pp", text)
    check_in_tex("ledger/has_freeze_commit", "43e1643", text)
    check_in_tex("ledger/has_v1_retraction", "RETRACTED", text)
    check_in_tex("ledger/has_-0.96", "0.96", text)
    check_in_tex("ledger/has_deploy", "fusion-5sig-v1", text)
    check_in_tex("ledger/has_7/9", "7/9", text)
    check_in_tex("ledger/has_msclap_sensitivity", "MS-CLAP sensitivity", text)
    check_in_tex("ledger/has_+9.2pp", "+9.2pp", text)
    check_in_tex("ledger/has_source_weighted", "source-weighted BPR", text)

    active = text.split("## Removed claims")[0]
    check_not_in_tex("ledger/no_v1_heldout_active", "[−0.85, +2.67]", active)


def main() -> int:
    print("=" * 60)
    print("  Paper Number Consistency Check")
    print("=" * 60)

    tex_text = TEX.read_text() if TEX.exists() else ""
    fusion = load_json(FUSION_PACKONLY)
    ablation = load_json(ABLATION_PACKONLY)
    fusion_mixed = load_json(FUSION_MIXED)
    heldout_eval = load_json(HELDOUT_EVAL)
    heldout_bootstrap = load_json(HELDOUT_BOOTSTRAP)
    heldout_loso = load_json(HELDOUT_LOSO)
    alignment = load_json(ALIGNMENT)
    split = load_json(SPLIT)
    deploy_weights = load_json(DEPLOY_WEIGHTS)
    msclap_sens = load_json(MSCLAP_SENSITIVITY)

    if fusion is None or ablation is None or split is None:
        print("\n".join(failures))
        print(f"\nBlocked: missing core artifacts. {len(failures)} errors.")
        return 1

    if heldout_eval:
        check_corpus(tex_text, split, heldout_eval)
    check_devset(tex_text, fusion, ablation)
    if fusion_mixed:
        check_label_sensitivity(tex_text, fusion_mixed)
    check_loso_table(tex_text, ablation)
    if heldout_loso:
        check_heldout_loso(tex_text, heldout_loso)
    if heldout_eval and heldout_bootstrap:
        check_heldout(tex_text, heldout_eval, heldout_bootstrap)
    if alignment:
        check_pilot(tex_text, alignment)
    if deploy_weights:
        check_deployment(tex_text, deploy_weights)
    if msclap_sens:
        check_msclap_sensitivity(tex_text, msclap_sens)
    check_removed_claims(tex_text)
    check_ledger_consistency()

    for line in passes:
        print(line)
    if failures:
        print()
        for line in failures:
            print(line)

    print()
    print(f"  {len(passes)} passed, {len(failures)} failed")
    print("=" * 60)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
