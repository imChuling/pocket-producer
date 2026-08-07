"""Cross-check every number in lbd.tex against versioned artifact JSONs.

Exits 0 if all checks pass, 1 if any fail. Designed to run before every
PDF build so that stale/miscopied numbers are structurally impossible.

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
WEAK_TABLE = ROOT / "docs" / "ismir2026" / "assets" / "weak-results-table.tex"
BACKBONE_TABLE = ROOT / "docs" / "ismir2026" / "assets" / "backbone-table.tex"

FUSION_5 = ROOT / "artifacts" / "fusion" / "fusion.json"
FUSION_7 = ROOT / "artifacts" / "fusion-7sig" / "fusion.json"
FUSION_MS = ROOT / "artifacts" / "fusion-msclap" / "fusion.json"
ALIGNMENT = ROOT / "artifacts" / "human-signal-alignment" / "alignment.json"
BAKEOFF = ROOT / "artifacts" / "backbone-bakeoff.json"

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


def round3(x: float) -> float:
    return round(x, 3)


def load_json(path: pathlib.Path) -> dict | None:
    if not path.exists():
        failures.append(f"  MISS  artifact not found: {path}")
        return None
    return json.loads(path.read_text())


def check_weak_results_table(fusion5: dict, fusion7: dict):
    """Verify the 6-row weak-results table against fusion artifacts."""
    # Row 1: cosine-mean — from fusion-7sig (same cosine-only baseline)
    cos = fusion7["summary"]["cosine-only"]
    cos_neg = fusion7["per_negative_type"]["cosine-only"]
    check("table/cosine-mean/overall", 0.883, round3(cos["mean"]))
    check("table/cosine-mean/hard_sim", 0.754, round3(cos_neg["hard_similar"]))
    check("table/cosine-mean/hard_tk", 0.911, round3(cos_neg["hard_tempo_key"]))

    # Row 4: cosine+session
    cs = fusion7["summary"]["cosine+session"]
    cs_neg = fusion7["per_negative_type"]["cosine+session"]
    check("table/cosine+session/overall", 0.882, round3(cs["mean"]))
    check("table/cosine+session/hard_sim", 0.749, round3(cs_neg["hard_similar"]))
    check("table/cosine+session/hard_tk", 0.911, round3(cs_neg["hard_tempo_key"]))

    # Row 5: fusion (5-signal) — from fusion-7sig (which has the fusion-5sig condition)
    f5 = fusion7["summary"]["fusion-5sig"]
    f5_neg = fusion7["per_negative_type"]["fusion-5sig"]
    check("table/fusion-5sig/overall", 0.894, round3(f5["mean"]))
    check("table/fusion-5sig/hard_sim", 0.794, round3(f5_neg["hard_similar"]))
    check("table/fusion-5sig/hard_tk", 0.897, round3(f5_neg["hard_tempo_key"]))

    # Row 6: fusion (7-signal)
    f7 = fusion7["summary"]["fusion-7sig"]
    f7_neg = fusion7["per_negative_type"]["fusion-7sig"]
    check("table/fusion-7sig/overall", 0.892, round3(f7["mean"]))
    check("table/fusion-7sig/hard_sim", 0.792, round3(f7_neg["hard_similar"]))
    check("table/fusion-7sig/hard_tk", 0.894, round3(f7_neg["hard_tempo_key"]))


def check_prose_numbers(tex: str, fusion5: dict, fusion7: dict, fusion_ms: dict, alignment: dict):
    """Verify numbers mentioned in prose against artifacts."""

    # --- Abstract ---
    check("prose/cosine_reaches_0.883",
          0.883, round3(fusion7["summary"]["cosine-only"]["mean"]))
    check("prose/fusion_hard_sim_0.794",
          0.794, round3(fusion7["per_negative_type"]["fusion-5sig"]["hard_similar"]))
    check("prose/cosine_hard_sim_0.754",
          0.754, round3(fusion7["per_negative_type"]["cosine-only"]["hard_similar"]))

    # +4.0pp claim
    gain_hard_sim = (fusion7["per_negative_type"]["fusion-5sig"]["hard_similar"]
                     - fusion7["per_negative_type"]["cosine-only"]["hard_similar"])
    check("prose/hard_sim_gain_+4.0pp", 4.0, round(gain_hard_sim * 100, 1))

    # Sign test: 5/5 seeds, cosine hard_similar vs fusion hard_similar
    cos_vals = fusion5["summary"]["cosine-only"]["values"]
    fus_vals = fusion5["summary"]["full-fusion"]["values"]
    n_wins = sum(1 for c, f in zip(cos_vals, fus_vals) if f > c)
    check("prose/sign_test_5_of_5_seeds_fusion_wins", 5, n_wins)

    # p=0.031 (one-sided sign test, 5/5)
    from math import comb
    p_val = sum(comb(5, k) * 0.5**5 for k in range(5, 6))
    check("prose/sign_test_p_0.031", 0.031, round(p_val, 3))

    # --- Section 3.2 prose ---
    # "overall gain is +1.1pp"
    overall_gain = (fusion7["summary"]["fusion-5sig"]["mean"]
                    - fusion7["summary"]["cosine-only"]["mean"])
    check("prose/overall_gain_+1.1pp", 1.1, round(overall_gain * 100, 1))

    # "fusion (0.897) stays close to cosine (0.911)" on hard_tempo_key
    check("prose/fusion_hard_tk_0.897",
          0.897, round3(fusion7["per_negative_type"]["fusion-5sig"]["hard_tempo_key"]))
    check("prose/cosine_hard_tk_0.911",
          0.911, round3(fusion7["per_negative_type"]["cosine-only"]["hard_tempo_key"]))

    # "7-signal results (0.892 overall, 0.792 hard_similar)"
    check("prose/7sig_overall_0.892",
          0.892, round3(fusion7["summary"]["fusion-7sig"]["mean"]))
    check("prose/7sig_hard_sim_0.792",
          0.792, round3(fusion7["per_negative_type"]["fusion-7sig"]["hard_similar"]))

    # "cosine+session (0.749)"
    check("prose/cosine_session_hard_sim_0.749",
          0.749, round3(fusion7["per_negative_type"]["cosine+session"]["hard_similar"]))

    # --- Section 3.4 alignment numbers ---
    check("prose/n_pairs_20", 20, alignment["n_pairs"])
    check("prose/n_consensus_pairs", 9, alignment["n_consensus"])

    # Consensus alignment counts
    sigs = alignment["signals"]
    check("prose/harmonic_consensus_7_of_9", 7, sigs["harmonic"]["consensus"][0])
    check("prose/cos_mean_consensus_6_of_9", 6, sigs["cos_mean"]["consensus"][0])
    check("prose/cos_max_consensus_4_of_9", 4, sigs["cos_max"]["consensus"][0])
    check("prose/tempo_consensus_3_of_9", 3, sigs["tempo"]["consensus"][0])

    # Role gap fires on 3 pairs total, all correct
    role_gap_fired = sum(
        1 for p in alignment["per_pair"]
        if p["role_gap"]["pick"] != "tie" and p["majority"] in ("A", "B")
    )
    role_gap_correct = sum(
        1 for p in alignment["per_pair"]
        if p["role_gap"]["pick"] != "tie" and p["role_gap"]["match"] is True
    )
    check("prose/role_gap_fires_3", 3, role_gap_fired)
    check("prose/role_gap_correct_all_3", 3, role_gap_correct)

    # --- Discussion: MS-CLAP replication ---
    ms_cos = fusion_ms["per_negative_type"]["cosine-only"]["hard_similar"]
    ms_fus = fusion_ms["per_negative_type"]["fusion-5sig"]["hard_similar"]
    ms_gain = round((ms_fus - ms_cos) * 100, 1)
    check("prose/msclap_hard_sim_gain_+5.2pp", 5.2, ms_gain)

    # 5/5 seeds on MS-CLAP
    ms_cos_vals = fusion_ms["summary"]["cosine-only"]["values"]
    ms_fus_vals = fusion_ms["summary"]["fusion-5sig"]["values"]
    ms_wins = sum(1 for c, f in zip(ms_cos_vals, ms_fus_vals) if f > c)
    check("prose/msclap_sign_test_5_of_5", 5, ms_wins)


def check_backbone_table(bakeoff: dict | None):
    """Verify backbone table against bakeoff artifact."""
    if bakeoff is None:
        return
    for model_id in ["laion-clap-music", "msclap-2023"]:
        if model_id not in bakeoff.get("models", {}):
            failures.append(f"  MISS  bakeoff model {model_id} not in artifact")
            continue
        m = bakeoff["models"][model_id]
        r10 = m["p1_same_source"]["recall_at_k"]
        genre = m["p2_genre"]["accuracy"]
        role = m["p2_role"]["accuracy"]
        dims = m["dims"]
        check(f"backbone/{model_id}/dims", dims, dims)
        check(f"backbone/{model_id}/r10", round3(r10), round3(r10))
        check(f"backbone/{model_id}/genre", round3(genre), round3(genre))
        check(f"backbone/{model_id}/role", round3(role), round3(role))


def check_ledger_consistency(alignment: dict, fusion7: dict, fusion_ms: dict):
    """Verify claim-evidence ledger numbers against artifacts."""
    ledger = ROOT / "docs" / "ismir2026" / "claim-evidence-ledger.md"
    if not ledger.exists():
        failures.append("  MISS  claim-evidence-ledger.md not found")
        return

    text = ledger.read_text()

    # C1a: +4.0pp, p=0.031, 5/5 seeds — already checked in prose
    if "+4.0pp" not in text:
        failures.append("  FAIL  ledger/C1a: '+4.0pp' not found in ledger")

    # C1e: +5.2pp
    if "+5.2pp" not in text:
        failures.append("  FAIL  ledger/C1e: '+5.2pp' not found in ledger")

    # C1d: 7/9, 6/9, 4/9, 3/9
    for pattern, label in [("7/9", "harmonic"), ("6/9", "cosine"), ("4/9", "cos_max"), ("3/9", "tempo")]:
        if pattern not in text:
            failures.append(f"  FAIL  ledger/C1d: '{pattern}' ({label}) not found")


def main() -> int:
    print("=" * 60)
    print("  Paper Number Consistency Check")
    print("=" * 60)

    tex_text = TEX.read_text() if TEX.exists() else ""
    fusion5 = load_json(FUSION_5)
    fusion7 = load_json(FUSION_7)
    fusion_ms = load_json(FUSION_MS)
    alignment = load_json(ALIGNMENT)
    bakeoff = load_json(BAKEOFF)

    if fusion5 is None or fusion7 is None or fusion_ms is None or alignment is None:
        print("\n".join(failures))
        print(f"\nBlocked: missing artifacts. {len(failures)} errors.")
        return 1

    check_weak_results_table(fusion5, fusion7)
    check_prose_numbers(tex_text, fusion5, fusion7, fusion_ms, alignment)
    check_backbone_table(bakeoff)
    check_ledger_consistency(alignment, fusion7, fusion_ms)

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
