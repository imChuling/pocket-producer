# Results: grouping threshold for the fusion score (v1)

Protocol: `research/protocol-grouping-threshold-v1.md` (committed before
scoring). Script: `research/run_grouping_threshold.py`. Output:
`artifacts/grouping-threshold/grouping_threshold.json`. Run 2026-11-17; a
second run gave identical numbers.

The vectorised scores match `backend/ranking/grouping.py`: largest
difference 2e-14 on 500 sampled train pairs, and under the script's 1e-6
check on 500 sampled held-out pairs.

## Thresholds (train packs only)

| Score | Rule | Threshold | Train precision | Train recall |
|---|---|--:|--:|--:|
| Fusion | precision >= 0.50 | 15.314 | 0.500 | 0.306 |
| Cosine | precision >= 0.50 | 0.8604 | 0.500 | 0.271 |

Train side: 484 packs, 1,389 items, 3,706 same-pack pairs, 960,260
different-pack pairs. Both scores reached the target, so the fallback
rule was not used.

## Held-out (121 packs, computed once)

408 items, 1,332 same-pack pairs, 81,696 different-pack pairs. Intervals
are 95% pack-level bootstrap intervals.

| Score | Precision | Recall | Average precision |
|---|--:|--:|--:|
| Fusion | 0.937 [0.822, 0.995] | 0.325 [0.221, 0.480] | 0.697 [0.577, 0.800] |
| Cosine | 0.915 [0.813, 0.982] | 0.266 [0.162, 0.429] | 0.571 [0.447, 0.702] |

Fusion minus cosine, average precision: +0.127 [+0.039, +0.206]. The
interval is above zero, so by the protocol's rule fusion is better than
plain cosine at telling same-pack pairs from different-pack pairs.

At the F1-maximising thresholds (secondary reference), fusion gives
precision 0.928 and recall 0.349, cosine 0.934 and 0.243.

## Uploader-disjoint subset (descriptive)

63 held-out packs whose uploader has no pack on the train side; 182 items,
473 same-pack pairs, 15,998 different-pack pairs.

| Score | Precision | Recall | Average precision |
|---|--:|--:|--:|
| Fusion | 0.905 [0.622, 1.000] | 0.300 [0.150, 0.502] | 0.650 [0.375, 0.806] |
| Cosine | 0.906 [0.712, 1.000] | 0.224 [0.093, 0.453] | 0.500 [0.303, 0.709] |

Fusion minus cosine, average precision: +0.149 [+0.017, +0.236]. The
precision intervals are wide because the subset is small.

## Reading

- At the chosen threshold, fusion finds about a third of same-pack pairs
  and is usually right when it does. Most related pairs stay below the
  threshold. Used for grouping, this means many fragments that belong
  together will be left ungrouped. That is the intended direction for a
  product where a wrong grouping costs more than a missed one.
- Precision at a fixed threshold depends on how many unrelated pairs the
  library holds. The same threshold gives 0.50 on the train side (960k
  different-pack pairs) and 0.94 on the held-out side (82k). A user's
  library is smaller than either, which would push precision up, but its
  loops are also likely to be more alike than loops from many uploaders,
  which would push it down. Neither direction is measured here.
- Online tags, tempo and key come from the product's own analysis, not
  FSLD metadata, so the tempo, key and tag terms can be distributed
  differently online. The threshold may not transfer exactly.
- Pack co-membership is a proxy. Nothing here measures whether a musician
  would group these fragments the same way, and no user grouping data was
  used.
