# Exploratory v3/v5 threshold analysis

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

Production relevance policy remains `max(0.10, best_score * 0.40)` and is unchanged. Ranking metrics in this comparison use no threshold, so ranking regressions cannot be attributed to applying that production threshold.

Curves use fixed absolute candidate thresholds independently for each model, binary positive grade >=1, and only judged pairs from the 105 included cases. Unjudged results remain unknown and are excluded from precision/recall/F1/FPR. This is a pooled judged-pair analysis, not corpus-wide precision.

There is no calibration/evaluation split. The same frozen draft cases generate all curves; translations share intentions and subgroup sizes are small. Any F1 maximum is descriptive exploratory evidence, not an independently evaluated tuned threshold.

## v3

| Threshold | Precision | Recall | F1 | FPR | TP | FP | FN | TN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -1.0000 | 0.3333 | 1.0000 | 0.5000 | 1.0000 | 700 | 1400 | 0 | 0 |
| 0.0000 | 0.3356 | 1.0000 | 0.5025 | 0.9900 | 700 | 1386 | 0 | 14 |
| 0.0500 | 0.3440 | 0.9971 | 0.5115 | 0.9507 | 698 | 1331 | 2 | 69 |
| 0.1000 | 0.3686 | 0.9700 | 0.5342 | 0.8307 | 679 | 1163 | 21 | 237 |
| 0.1500 | 0.4168 | 0.9271 | 0.5751 | 0.6486 | 649 | 908 | 51 | 492 |
| 0.2000 | 0.4983 | 0.8586 | 0.6306 | 0.4321 | 601 | 605 | 99 | 795 |
| 0.2500 | 0.6023 | 0.7400 | 0.6641 | 0.2443 | 518 | 342 | 182 | 1058 |
| 0.3000 | 0.6811 | 0.5829 | 0.6282 | 0.1364 | 408 | 191 | 292 | 1209 |
| 0.3500 | 0.7602 | 0.4257 | 0.5458 | 0.0671 | 298 | 94 | 402 | 1306 |
| 0.4000 | 0.7621 | 0.2471 | 0.3732 | 0.0386 | 173 | 54 | 527 | 1346 |
| 0.4500 | 0.8194 | 0.1686 | 0.2796 | 0.0186 | 118 | 26 | 582 | 1374 |
| 0.5000 | 0.9701 | 0.0929 | 0.1695 | 0.0014 | 65 | 2 | 635 | 1398 |
| 0.5500 | 0.9583 | 0.0329 | 0.0635 | 0.0007 | 23 | 1 | 677 | 1399 |
| 0.6000 | 1.0000 | 0.0029 | 0.0057 | 0.0000 | 2 | 0 | 698 | 1400 |
| 0.6500 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.7000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.7500 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.8000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.8500 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.9000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.9500 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |

Exploratory grid maximum F1: 0.6641 at threshold 0.25. No production recommendation follows from this maximum.

Per-language and per-category curves are retained in the model result JSON. Their metric implementation is identical.

| Unresolved no-hit hypothesis | >=0 | >=0.25 | >=0.5 | >=0.75 | >=1 |
| --- | --- | --- | --- | --- | --- |
| harpsichord-da | 610 | 29 | 0 | 0 | 0 |
| harpsichord-de | 610 | 30 | 0 | 0 | 0 |
| harpsichord-en | 609 | 36 | 0 | 0 | 0 |
| koreanopera-da | 569 | 8 | 0 | 0 | 0 |
| koreanopera-de | 569 | 7 | 0 | 0 | 0 |
| koreanopera-en | 541 | 5 | 0 | 0 | 0 |

## v5

| Threshold | Precision | Recall | F1 | FPR | TP | FP | FN | TN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -1.0000 | 0.3333 | 1.0000 | 0.5000 | 1.0000 | 700 | 1400 | 0 | 0 |
| 0.0000 | 0.3335 | 1.0000 | 0.5002 | 0.9993 | 700 | 1399 | 0 | 1 |
| 0.0500 | 0.3354 | 1.0000 | 0.5023 | 0.9907 | 700 | 1387 | 0 | 13 |
| 0.1000 | 0.3445 | 0.9957 | 0.5119 | 0.9471 | 697 | 1326 | 3 | 74 |
| 0.1500 | 0.3749 | 0.9714 | 0.5410 | 0.8100 | 680 | 1134 | 20 | 266 |
| 0.2000 | 0.4332 | 0.9214 | 0.5893 | 0.6029 | 645 | 844 | 55 | 556 |
| 0.2500 | 0.5078 | 0.8386 | 0.6325 | 0.4064 | 587 | 569 | 113 | 831 |
| 0.3000 | 0.5828 | 0.7443 | 0.6537 | 0.2664 | 521 | 373 | 179 | 1027 |
| 0.3500 | 0.6561 | 0.5886 | 0.6205 | 0.1543 | 412 | 216 | 288 | 1184 |
| 0.4000 | 0.7351 | 0.4400 | 0.5505 | 0.0793 | 308 | 111 | 392 | 1289 |
| 0.4500 | 0.7804 | 0.2843 | 0.4168 | 0.0400 | 199 | 56 | 501 | 1344 |
| 0.5000 | 0.7344 | 0.1343 | 0.2271 | 0.0243 | 94 | 34 | 606 | 1366 |
| 0.5500 | 0.9412 | 0.0457 | 0.0872 | 0.0014 | 32 | 2 | 668 | 1398 |
| 0.6000 | 0.9000 | 0.0129 | 0.0254 | 0.0007 | 9 | 1 | 691 | 1399 |
| 0.6500 | 1.0000 | 0.0071 | 0.0142 | 0.0000 | 5 | 0 | 695 | 1400 |
| 0.7000 | 1.0000 | 0.0014 | 0.0029 | 0.0000 | 1 | 0 | 699 | 1400 |
| 0.7500 | 1.0000 | 0.0014 | 0.0029 | 0.0000 | 1 | 0 | 699 | 1400 |
| 0.8000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.8500 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.9000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 0.9500 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |
| 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | 700 | 1400 |

Exploratory grid maximum F1: 0.6537 at threshold 0.30. No production recommendation follows from this maximum.

Per-language and per-category curves are retained in the model result JSON. Their metric implementation is identical.

| Unresolved no-hit hypothesis | >=0 | >=0.25 | >=0.5 | >=0.75 | >=1 |
| --- | --- | --- | --- | --- | --- |
| harpsichord-da | 611 | 155 | 0 | 0 | 0 |
| harpsichord-de | 611 | 137 | 0 | 0 | 0 |
| harpsichord-en | 611 | 151 | 0 | 0 | 0 |
| koreanopera-da | 608 | 13 | 0 | 0 | 0 |
| koreanopera-de | 611 | 2 | 0 | 0 | 0 |
| koreanopera-en | 611 | 7 | 0 | 0 | 0 |

Counts for the six unresolved hypotheses are exploratory returned-event counts, **not confirmed false positives**. They do not enter quality gates or threshold confusion matrices.

## Recommendation

**Insufficient evidence for a production v5 threshold.** Human review must first confirm relevance and inspect unjudged top results and all six no-hit hypotheses across the eligible corpus. Then establish a held-out split at query-group level, stratified where feasible, and measure threshold trade-offs separately for each model. Preserve the current disabled semantic capability and existing threshold until a separate decision.
