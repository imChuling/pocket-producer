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

FUSION_PACKONLY = ROOT / "artifacts" / "fusion-packonly" / "fusion.json"
ABLATION_PACKONLY = ROOT / "artifacts" / "ablation-packonly" / "ablation.json"
FUSION_MIXED = ROOT / "artifacts" / "fusion-7sig" / "fusion.json"
HELDOUT_EVAL = ROOT / "artifacts" / "heldout-eval-packonly" / "eval.json"
HELDOUT_BOOTSTRAP = ROOT / "artifacts" / "heldout-eval-packonly" / "bootstrap.json"
ALIGNMENT = ROOT / "artifacts" / "human-signal-alignment" / "alignment.json"
SPLIT = ROOT / "artifacts" / "heldout-split-packonly" / "split.json"
DEPLOY_WEIGHTS = ROOT / "artifacts" / "fusion-deploy" / "weights.json"
MSCLAP_SENSITIVITY = ROOT / "artifacts" / "msclap-sensitivity" / "sensitivity.json"
FACTORIAL = ROOT / "artifacts" / "factorial" / "factorial.json"
LAION_CORRECTION = ROOT / "artifacts" / "heldout-eval-correction" / "sensitivity.json"
MSCLAP_CORRECTION = ROOT / "artifacts" / "msclap-sensitivity-correction" / "sensitivity.json"

failures = []
passes = []


def check(label, expected, actual, tol=0.0015):
    if isinstance(expected, float) and isinstance(actual, float):
        ok = isclose(expected, actual, abs_tol=tol)
    else:
        ok = expected == actual
    if ok:
        passes.append(f"  PASS  {label}: {actual}")
    else:
        failures.append(f"  FAIL  {label}: paper={expected}, artifact={actual}")


def _normalize_ws(s):
    return re.sub(r"\s+", " ", s)


def check_in_tex(label, needle, tex):
    if _normalize_ws(needle) in _normalize_ws(tex):
        passes.append(f"  PASS  tex/{label}: '{needle}' found")
    else:
        failures.append(f"  FAIL  tex/{label}: '{needle}' NOT in lbd.tex")


def check_not_in_tex(label, needle, tex):
    if _normalize_ws(needle) not in _normalize_ws(tex):
        passes.append(f"  PASS  tex/{label}: '{needle}' correctly absent")
    else:
        failures.append(
            f"  FAIL  tex/{label}: '{needle}' should be removed but is still in lbd.tex"
        )


def round3(x):
    return round(x, 3)


def load_json(path):
    if not path.exists():
        failures.append(f"  MISS  artifact not found: {path}")
        return None
    return json.loads(path.read_text())


def check_corpus(tex, split, eval_data):
    """§3: pack-only corpus composition and split sizes."""
    check("§3/split_seed", 20260810, split["split_seed"])
    check("§3/total_sources_605", 605, split["n_total_sources"])
    check("§3/train_sources_484", 484, split["n_train_sources"])
    check("§3/heldout_sources_121", 121, split["n_heldout_sources"])
    check("§3/train_examples_981", 981, eval_data["train_examples"])

    check_in_tex("has_1797_items", "1,797", tex)
    check_in_tex("has_605_packs", "605 packs", tex)
    check_in_tex("has_484", "484", tex)
    check_in_tex("has_121_source", "121-source", tex)
    check_in_tex("has_seed_20260810", "20260810", tex)
    check_in_tex("has_source_grouped", "source-grouped", tex)
    check_in_tex("has_fixed_split", "fixed 121-source held-out split", tex)
    # Round-10 (page-budget pass): 171/981 query counts, 300 epochs, and the
    # ~75% dev-split detail moved out of the 2-page body into research/README;
    # they must NOT be asserted against lbd.tex anymore.
    check_not_in_tex("no_981_in_body", "981", tex)


def check_devset(tex, fusion, ablation):
    """§3: pack-only train-side dev numbers."""
    cos = fusion["summary"]["cosine-only"]
    cos_neg = fusion["per_negative_type"]["cosine-only"]
    f5 = fusion["summary"]["fusion-5sig"]
    f5_neg = fusion["per_negative_type"]["fusion-5sig"]

    check("§3/cosine_overall_0.9293", 0.9293, round(cos["mean"], 4))
    check("§3/cosine_hard_sim_0.8136", 0.8136, round(cos_neg["hard_similar"], 4))
    check("§3/fusion_overall_0.9249", 0.9249, round(f5["mean"], 4))
    check("§3/fusion_hard_sim_0.8133", 0.8133, round(f5_neg["hard_similar"], 4))

    gain = round((f5_neg["hard_similar"] - cos_neg["hard_similar"]) * 100, 2)
    check("§3/hard_sim_delta_-0.03pp", -0.03, gain, tol=0.005)

    tk_diff = round(
        (f5_neg["hard_tempo_key"] - cos_neg["hard_tempo_key"]) * 100, 1
    )
    check("§3/hard_tk_diff_-2.1pp_descriptive", -2.1, tk_diff, tol=0.05)

    # Round-9: this backs the tex claim "(negative in all 5 splits)", so a
    # missing key must fail rather than silently skip the assertion.
    per_seed = ablation.get("bootstrap_ci_per_seed", {})
    check("§3/per_seed_ci_present", 5, len(per_seed))
    n_neg = sum(
        1
        for s in per_seed.values()
        if s["paired-diff"]["hard_tempo_key"]["mean_diff"] < 0
    )
    check("§3/hard_tk_negative_in_all_5_splits", 5, n_neg)

    # Round-11 (micro-polish): the four absolute dev accuracies were
    # compressed to the delta "+4.0 \to -0.03\,pp"; they must NOT
    # reappear in the body (artifact checks above still verify them).
    check_not_in_tex("no_abs_accuracy_0.9293", "0.9293", tex)
    check_not_in_tex("no_abs_accuracy_0.9249", "0.9249", tex)
    check_in_tex("has_-0.03pp", "-0.03", tex)
    check_in_tex("has_label_gain_arrow", "+4.0 \\to -0.03", tex)
    # Round-9: bare "2.1" also matches the held-out LAION "+2.1", so this
    # anchors on the dev-set sentence to stay attached to the right claim.
    check_in_tex("has_dev_2.1pp", "by 2.1\\,pp", tex)
    check_in_tex("has_dev_2.1_all_splits", "negative in all 5 splits", tex)
    check_in_tex("has_exploratory", "exploratory", tex)
    check_in_tex("has_metric_definition", "pairwise ranking accuracy", tex)
    check_in_tex("has_bootstrap_unit", "source-level bootstrap", tex)
    check_in_tex("has_source_definition", "grouping unit for all splits", tex)
    check_not_in_tex("no_invalid_dev_ci", "[-3.9, -0.6]", tex)
    check_not_in_tex("no_dev_significance",
                     "significantly \\emph{worse} than\ncosine ($-2.1$", tex)


def check_label_sensitivity(tex, fusion_mixed):
    """§4: mixed-label +4.0pp claim against the old artifact."""
    cos_neg = fusion_mixed["per_negative_type"]["cosine-only"]
    f5_neg = fusion_mixed["per_negative_type"]["fusion-5sig"]
    gain = round((f5_neg["hard_similar"] - cos_neg["hard_similar"]) * 100, 1)
    check("§4/mixed_gain_+4.0pp", 4.0, gain)

    check_in_tex("has_+4.0pp", "+4.0", tex)
    check_in_tex("has_26pct", "26\\%", tex)
    check_in_tex("has_949_mixed", "949 sources", tex)
    check_in_tex("has_uploader", "uploader", tex)


def check_loso(tex, ablation):
    """§4: LOSO tempo numbers stated in prose (table removed)."""
    abl = ablation["ablation"]
    full = abl["full-fusion"]
    minus_tempo = abl["minus-tempo"]

    tempo_hs = round(
        (minus_tempo["hard_similar_mean"] - full["hard_similar_mean"]) * 100, 2
    )
    tempo_htk = round(
        (minus_tempo["hard_tempo_key_mean"] - full["hard_tempo_key_mean"]) * 100,
        2,
    )
    check("§4/loso_tempo_hs_-0.96", -0.96, tempo_hs, tol=0.005)
    check("§4/loso_tempo_htk_+0.68", 0.68, tempo_htk, tol=0.005)

    minus_key = abl["minus-key"]
    key_hs = round(
        (minus_key["hard_similar_mean"] - full["hard_similar_mean"]) * 100, 2
    )
    key_htk = round(
        (minus_key["hard_tempo_key_mean"] - full["hard_tempo_key_mean"]) * 100,
        2,
    )
    check("§4/loso_key_hs_+0.94", 0.94, key_hs, tol=0.005)
    check("§4/loso_key_htk_+1.21", 1.21, key_htk, tol=0.005)

    check_in_tex("has_-0.96", "-0.96", tex)
    check_in_tex("has_+0.68", "+0.68", tex)
    check_in_tex("has_key_loso", "$+0.94$/$+1.21$", tex)
    check_in_tex("has_loso_descriptive", "no CIs, descriptive", tex)
    check_in_tex("has_loso", "eave-one-signal-out", tex)
    # Key's dev-set LOSO must not be sold as significant or as the
    # deployment rationale (round-7 audit): held-out MS-CLAP flips sign.
    check_not_in_tex("no_key_net_harmful", "net harmful", tex)
    check_not_in_tex("no_key_deploy_gloss",
                     "consistent with the deployment decision", tex)


def check_heldout(tex, laion_corr):
    """§4: held-out LAION delta vector (Table 1) from correction run."""
    bs = laion_corr["bootstrap"]["fusion_vs_cosine"]

    hs = bs["hard_similar"]
    check("§4/heldout_hard_sim_+2.1pp", 2.1,
          round(hs["point_delta"] * 100, 1), tol=0.05)
    check("§4/hs_ci_lo_-1.0", -1.0, round(hs["ci_lo"] * 100, 1), tol=0.1)
    check("§4/hs_ci_hi_+5.3", 5.3, round(hs["ci_hi"] * 100, 1), tol=0.1)
    check("§4/hs_ci_crosses_zero", True, hs["ci_lo"] < 0 < hs["ci_hi"])
    check("§4/laion_easy_+0.2pp", 0.2,
          round(bs["easy"]["point_delta"] * 100, 1), tol=0.05)
    check("§4/laion_htk_+0.0pp", 0.0,
          round(bs["hard_tempo_key"]["point_delta"] * 100, 1), tol=0.05)
    check("§4/laion_overall_+0.6pp", 0.6,
          round(bs["overall"]["point_delta"] * 100, 1), tol=0.05)

    check_in_tex("has_+2.1pp", "+2.1", tex)
    check_in_tex("has_hs_ci", "[-1.0, +5.3]", tex)
    check_in_tex("has_laion_easy_ci", "[-0.5, +0.9]", tex)
    check_in_tex("has_laion_htk_ci", "[-0.8, +0.5]", tex)
    check_in_tex("has_laion_overall_ci", "[-0.4, +1.6]", tex)
    check_in_tex("has_bootstrap", "bootstrap", tex)

    # Round-9: the "16--17 pp" claim is about the learned fusion only
    # (cosine is frozen, not learned), so bound fusion_vs_rules alone.
    fr = laion_corr["bootstrap"]["fusion_vs_rules"]["overall"]["point_delta"]
    check("§2/laion_fusion_rules_gap_>=16pp", True, fr * 100 >= 16.0)
    check("§2/laion_fusion_rules_gap_<=17.5pp", True, fr * 100 <= 17.5)


def check_msclap_sensitivity(tex, msclap_corr):
    """§4: MS-CLAP sensitivity full delta vector (Table 1) from correction run."""
    bs = msclap_corr["bootstrap"]["fusion_vs_cosine"]

    hs = bs["hard_similar"]
    check("§4/msclap_hs_+9.9pp", 9.9,
          round(hs["point_delta"] * 100, 1), tol=0.05)
    check("§4/msclap_hs_ci_lo_+4.4", 4.4,
          round(hs["ci_lo"] * 100, 1), tol=0.1)
    check("§4/msclap_hs_ci_hi_+15.4", 15.4,
          round(hs["ci_hi"] * 100, 1), tol=0.1)
    check("§4/msclap_hs_ci_above_zero", True, hs["ci_lo"] > 0)
    check("§4/msclap_easy_+0.1pp", 0.1,
          round(bs["easy"]["point_delta"] * 100, 1), tol=0.05)
    # tol=0.1 on a 1-decimal value accepted -0.2 and 0.0 too; tightened to
    # match its siblings. Artifact point_delta is -0.1487 -> -0.1.
    check("§4/msclap_htk_-0.1pp", -0.1,
          round(bs["hard_tempo_key"]["point_delta"] * 100, 1), tol=0.05)
    check("§4/msclap_overall_+2.6pp", 2.6,
          round(bs["overall"]["point_delta"] * 100, 1), tol=0.05)

    check_in_tex("has_msclap_+9.9", "+9.9", tex)
    check_in_tex("has_msclap_hs_ci", "[+4.4, +15.4]", tex)
    check_in_tex("has_msclap_easy_ci", "[-1.2, +1.4]", tex)
    check_in_tex("has_msclap_htk_ci", "[-2.2, +2.0]", tex)
    check_in_tex("has_msclap_overall_ci", "[+1.0, +4.2]", tex)
    check_in_tex("has_7.8pp_swing", "7.8", tex)
    check_in_tex("has_config_sensitivity", "configuration sensitivity", tex)
    check_not_in_tex("no_representation_sensitivity",
                     "representation sensitivity", tex)
    check_in_tex("has_source_weighted_bpr", "source-weighted BPR", tex)

    # Round-8: key LOSO held-out non-replication (hard_similar sign flip)
    loso = msclap_corr["loso"]
    key_hs_heldout = round(
        (loso["minus-key"]["mean_hard_similar"]
         - loso["full-5sig"]["mean_hard_similar"]) * 100, 2
    )
    check("§4/key_heldout_hs_-0.12", -0.12, key_hs_heldout, tol=0.005)
    check_in_tex("has_key_heldout_-0.12", "-0.12", tex)
    check_in_tex("has_key_nonreplication", "key's", tex)

    # Round-9: rules trails the learned fusion 16--17 pp across the two
    # configurations of §3.2 (LAION 17.0, MS-CLAP 16.0). Bound fusion only:
    # cosine is frozen, not learned, and its gap (13.4 pp here) is not the claim.
    fr = msclap_corr["bootstrap"]["fusion_vs_rules"]["overall"]["point_delta"]
    check("§2/msclap_fusion_rules_gap_>=16pp", True, fr * 100 >= 16.0)
    check("§2/msclap_fusion_rules_gap_<=17.5pp", True, fr * 100 <= 17.5)
    check_in_tex("has_rules_gap_16_17", "16--17", tex)
    check_not_in_tex("no_stale_rules_gap_13_17", "13--17", tex)
    # The rules default must not be justified by denying the measured gaps
    check_not_in_tex("no_stable_advantage_denial",
                     "no stable fusion advantage", tex)

    rules = msclap_corr["heldout_summary"]["rules"]
    check("§4/rules_heldout_overall_0.787", 0.787,
          round3(rules["mean_overall"]))
    check("§4/rules_heldout_htk_0.424", 0.424,
          round3(rules["mean_hard_tempo_key"]))
    check_in_tex("has_rules_0.787", "0.787", tex)
    check_in_tex("has_rules_0.424", "0.424", tex)


def check_factorial(tex, factorial):
    """§4: descriptive 2x2 decomposition wording and numbers."""
    hs = factorial["factorial_effects"]["hard_similar"]
    # +1.9/+0.5 are marginal shifts of the fusion-cosine GAP, computed
    # from the per-condition deltas; verify from condition means.
    s = factorial["summaries"]
    deltas = {}
    for cond in s:
        fu = s[cond]["fusion"]["hard_similar"]["mean"]
        co = s[cond]["cosine"]["hard_similar"]["mean"]
        deltas[cond] = (fu - co) * 100
    repr_gap_shift = (
        (deltas["C_msclap_uniform"] - deltas["A_laion_uniform"])
        + (deltas["D_msclap_sourceweighted"] - deltas["B_laion_sourceweighted"])
    ) / 2
    train_gap_shift = (
        (deltas["B_laion_sourceweighted"] - deltas["A_laion_uniform"])
        + (deltas["D_msclap_sourceweighted"] - deltas["C_msclap_uniform"])
    ) / 2
    check("§4/factorial_gap_repr_+1.9", 1.9, round(repr_gap_shift, 1), tol=0.05)
    check("§4/factorial_gap_train_+0.5", 0.5, round(train_gap_shift, 1), tol=0.05)
    check("§4/factorial_raw_repr_-1.3", -1.3,
          round(hs["representation_effect_pp"], 1), tol=0.05)

    check_not_in_tex("no_factorial_attributes", "factorial attributes", tex)


def check_pilot_removed(tex):
    """Pilot removed from the 2-page body (review 2026-08-13): raw vote
    matrix unavailable, so kappa is not independently recomputable.
    The artifact remains in the repo; the paper must not cite it."""
    check_not_in_tex("no_pilot_kappa", "0.294", tex)
    check_not_in_tex("no_pilot_fleiss", "Fleiss", tex)
    check_not_in_tex("no_pilot_divergence", "Pilot divergence", tex)


def check_deployment(tex, weights):
    """§2: deployed fusion claims match the shipped artifact."""
    check("§2/deploy_model_id", "fusion-5sig-v1", weights["model_id"])
    check("§2/deploy_5_weights", 5, len(weights["weights"]))
    check("§2/deploy_space_msclap", ["msclap-2023"],
          weights["representation_model"])
    check("§2/deploy_trained_packonly", True,
          "pack-only train split" in weights.get("trained_on", ""))
    check("§2/deploy_source_weighted", True,
          "source-weighted BPR" in weights.get("trained_on", ""))

    check_in_tex("has_deployment_adapts", "adapts the five-signal ranker", tex)
    check_in_tex("has_msclap_delta", "MS-CLAP", tex)
    check_in_tex("has_key_zero_online", "zeroed online", tex)
    check_in_tex("has_default_ranker", "remains the default", tex)
    check_in_tex("has_fusion_selectable", "selectable", tex)
    check_not_in_tex("no_fusion_default", "is the default when session audio",
                     tex)
    check_not_in_tex("no_same_fusion_model", "same fusion model", tex)
    check_not_in_tex("no_active_regions", "active regions", tex)


def check_removed_claims(tex):
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
    check_not_in_tex("no_confounding", "confounding", tex)
    check_in_tex("has_corrective_disclosure", "protocol mismatch", tex)
    check_in_tex("has_exploratory_not_confirmatory", "exploratory", tex)
    check_not_in_tex("no_inference_reserved", "inference is reserved", tex)
    check_in_tex("has_missing_label_thesis", "missing-label problem", tex)
    check_in_tex("has_proxy_interrogation",
                 "how ranking conclusions change", tex)
    check_not_in_tex("no_not_a_similarity_problem",
                     "not a similarity problem", tex)
    # Unverified user-utility and over-broad system claims (review 2026-08-13)
    check_not_in_tex("no_costs_nothing", "costs the musician nothing", tex)
    check_not_in_tex("no_at_every_step", "at every step", tex)
    check_not_in_tex("no_every_insertion_reversible",
                     "every insertion is reversible", tex)
    check_not_in_tex("no_every_interaction_logged",
                     "every interaction is logged", tex)
    check_not_in_tex("no_test_the_design_stance", "test the design stance", tex)
    check_not_in_tex("no_validate_design", "validate the design", tex)
    # Ledger rule: body may only assert status=verified claims; S2/S3 are
    # partial (offline tests done, real-account capture pending)
    check_not_in_tex("no_working_prototype", "working prototype", tex)
    check_not_in_tex("no_live_session_read", "live Audiotool session", tex)
    check_in_tex("has_offline_validation_hedge", "live-account capture", tex)


def check_ledger_consistency():
    """Verify claim-evidence ledger references current paper structure."""
    ledger_path = ROOT / "docs" / "ismir2026" / "claim-evidence-ledger.md"
    if not ledger_path.exists():
        failures.append("  MISS  claim-evidence-ledger.md not found")
        return

    text = ledger_path.read_text()

    check_in_tex("ledger/has_packonly", "pack-only", text)
    check_in_tex("ledger/has_heldout_delta", r"hard\_similar", text)
    check_in_tex("ledger/has_freeze_commit", "43e1643", text)
    check_in_tex("ledger/has_v1_retraction", "RETRACTED", text)
    check_in_tex("ledger/has_-0.96", "0.96", text)
    check_in_tex("ledger/has_deploy", "fusion-5sig-v1", text)
    check_in_tex("ledger/has_7/9", "7/9", text)
    check_in_tex("ledger/has_msclap_sensitivity", "MS-CLAP sensitivity", text)
    check_in_tex("ledger/has_msclap_hs", "MS-CLAP sensitivity", text)
    check_in_tex("ledger/has_source_weighted", "source-weighted BPR", text)


def main():
    print("=" * 60)
    print("  Paper Number Consistency Check")
    print("=" * 60)

    tex_text = TEX.read_text() if TEX.exists() else ""
    fusion = load_json(FUSION_PACKONLY)
    ablation = load_json(ABLATION_PACKONLY)
    fusion_mixed = load_json(FUSION_MIXED)
    heldout_eval = load_json(HELDOUT_EVAL)
    heldout_bootstrap = load_json(HELDOUT_BOOTSTRAP)
    split = load_json(SPLIT)
    deploy_weights = load_json(DEPLOY_WEIGHTS)
    msclap_sens = load_json(MSCLAP_SENSITIVITY)
    factorial = load_json(FACTORIAL)
    laion_corr = load_json(LAION_CORRECTION)
    msclap_corr = load_json(MSCLAP_CORRECTION)

    if fusion is None or ablation is None or split is None:
        print("\n".join(failures))
        print(f"\nBlocked: missing core artifacts. {len(failures)} errors.")
        return 1

    if heldout_eval:
        check_corpus(tex_text, split, heldout_eval)
    check_devset(tex_text, fusion, ablation)
    if fusion_mixed:
        check_label_sensitivity(tex_text, fusion_mixed)
    check_loso(tex_text, ablation)
    if laion_corr:
        check_heldout(tex_text, laion_corr)
    check_pilot_removed(tex_text)
    if deploy_weights:
        check_deployment(tex_text, deploy_weights)
    if msclap_corr:
        check_msclap_sensitivity(tex_text, msclap_corr)
    if factorial:
        check_factorial(tex_text, factorial)
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
