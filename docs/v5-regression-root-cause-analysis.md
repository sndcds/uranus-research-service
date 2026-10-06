# v5 regression root-cause analysis

## 1. Executive summary

**R6 — several mechanisms, with unresolved causal attribution.** The four total-loss
failures remain failures of the frozen known-positive Top-10 metric. They do not
establish absence of useful v5 results: three v5 Top-10 lists are entirely unjudged.
One loss is particularly sensitive to exact-score ties and UUID order. Other losses
reflect competition between partial query intents and changes in the selected chunk.
There is no evidence for one universal language, prefix or last-token-pooling defect.
**Custom Kulturbytes v5 fine-tuning: not yet justified.**

Outdoor −0.125 is one case and one lost known hit (ORDRIG 4→111), not a broad
sample of outdoor failures. Atmosphere −0.08 is dance-en −0.5 partly offset by
quiet-da +0.1 across five included cases. Theatre loses on two of six cases;
venue has a recurring Museumsberg pattern across DE/DA/EN plus mixed Kühlhaus results.

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

## 2. Scope und Grenzen

Baseline: PR #7 head `d8bb72957c33e6d9ef2a9838ec4e54041f3e90a7`;
completed benchmark `20261006_8cpu_001`, 611 documents, 120 executed / 105 included
cases. No reindex, new benchmark, changed judgment, threshold or gate. All original
artifact hashes and input pins were verified; deterministic re-evaluation reproduces
the original comparison byte-for-byte as parsed JSON.

[Reconstruction JSON](../benchmark/results/v5-regression-reconstruction-20261006.json)
contains every known-positive UUID/rank/score, both Top-10 lists, adjacent ranks,
winning point IDs, complete chunk texts/hashes/indexes/contexts, all chunks of the
relevant total-loss documents, eligible occurrences and same-UUID language controls.
It references the immutable complete event rankings. The existing artifacts do not
store query embeddings, all document vectors or all non-winning query/chunk scores.
Thus a losing alternative chunk's original similarity is unknown. No collection was
read to obtain additional vectors.

Ranks are event ranks after maximum-chunk aggregation. Chunk indexes below are
zero-based. Scores are compared **within** each model only. A positive boundary gap
means the event scores below rank 10; zero can still fall outside Top 10 through ties.
The judgments are event-level: occurrence IDs identify evidence and eligibility, not
independent approved occurrence relevance. Event-level evidence is never transferred
to certify accessibility of another occurrence.

## 3. Vier Total-Loss-Fälle

The field “strongest false positive” below means the highest-ranked **frozen grade-0**
competitor. An unjudged v5 leader is listed separately and is not declared irrelevant.
Even frozen zeros remain draft proposals, not human-certified truth.

### historical-q29

| Feld | Ergebnis |
| --- | --- |
| Query | Participatory art workshops for young people |
| Sprache / Kategorie | en / exhibition |
| relevante IDs | 019da011-1802-7924-8a24-821066242bba; 019db61e-a230-7e9b-a02a-8d59e4662280; 019f19b5-7503-754a-980c-5feafc43e2af |
| v3 ranks | 8, 86, 65 |
| v5 ranks | 20, 148, 109 |
| stärkster v5 false positive (draft zero) | Digitale Teilhabe – gemeinsam vernetzt — 019db91a-89d5-7c5a-90ae-7596e488a1eb, rank 34 |
| v5 leader (unjudged) | Jugendatelier |
| Hauptdiagnose | A + H: Utopia 8→20; plausible unjudged art-workshop competition. |
| Sekundärdiagnose | C plausible: changed Danish program boundary; E not isolated. |
| Confidence | High for ranks/coverage, medium for semantic explanation. |

| Known positive / UUID | Grade | v3 rank / score | v5 rank / score | Gap to boundary v3 / v5 | Same winning text |
| --- | --- | --- | --- | --- | --- |
| Kulturh(a)us Utopia / 019da011-1802-7924-8a24-821066242bba | 1 | 8 / 0.372222 | 20 / 0.418629 | -0.004295 / +0.019019 | False |
| Gården Festival / 019db61e-a230-7e9b-a02a-8d59e4662280 | 1 | 86 / 0.241284 | 148 / 0.282342 | +0.126644 / +0.155306 | False |
| Pflegende Naturkosmetika und Heikräuter / 019f19b5-7503-754a-980c-5feafc43e2af | 1 | 65 / 0.269213 | 109 / 0.309701 | +0.098715 / +0.127947 | True |

**v3 Top 10**

| Rank | Event / UUID | Score | Frozen grade | Chunk index / kind / tokens |
| --- | --- | --- | --- | --- |
| 1 | Kinderatelier / 01a0a8e7-94ad-7c44-9fcc-d782a8c28ede | 0.482972 | unjudged | 0 / content / 379 |
| 2 | Jugendatelier / 01a0a921-f23e-7e72-be8f-bdf44719f914 | 0.453879 | unjudged | 0 / content / 342 |
| 3 | St_ART der Begegnung / 01a0b9bb-80fb-76a6-a694-54ae181cfbcb | 0.408015 | unjudged | 1 / content / 476 |
| 4 | BeatsARTig / 01a066d1-8ed7-723b-b14e-b2543ae11483 | 0.407458 | unjudged | 0 / content / 120 |
| 5 | LAZY SUNDAY UPCYCLING / 019edfb6-351f-7553-a7f5-4543ccf4ade2 | 0.403813 | unjudged | 0 / content / 91 |
| 6 | kreativ:treff / 019dab00-b596-705a-85cf-53889c2f643d | 0.395721 | unjudged | 0 / content / 51 |
| 7 | Muss durch die Tür passen / 019e03bb-3970-748f-a12d-ece11bf1d52a | 0.388937 | unjudged | 0 / content / 430 |
| 8 | Kulturh(a)us Utopia / 019da011-1802-7924-8a24-821066242bba | 0.372222 | 1 | 1 / content / 476 |
| 9 | "Weg sein" - Ein Literatur- und Theaterprojekt für Jugendliche ab 12 Jahren / 01a01444-7520-7624-839c-046df141eeae | 0.371816 | unjudged | 0 / content / 231 |
| 10 | Porzellan bemalen / 01a08d89-d6b6-789f-a175-65ff2d2a8268 | 0.367927 | unjudged | 0 / content / 386 |

**v5 Top 10**

| Rank | Event / UUID | Score | Frozen grade | Chunk index / kind / tokens |
| --- | --- | --- | --- | --- |
| 1 | Jugendatelier / 01a0a921-f23e-7e72-be8f-bdf44719f914 | 0.563398 | unjudged | 0 / content / 458 |
| 2 | Kinderatelier / 01a0a8e7-94ad-7c44-9fcc-d782a8c28ede | 0.462199 | unjudged | 0 / content / 468 |
| 3 | Women Artists Film Festival / 01a06711-4848-7f8b-99fb-2347527dcac0 | 0.461876 | unjudged | 0 / content / 351 |
| 4 | LAZY SUNDAY UPCYCLING / 019edfb6-351f-7553-a7f5-4543ccf4ade2 | 0.457296 | unjudged | 0 / content / 110 |
| 5 | Kulturtag im Atelier Kreativecke / 01a08aea-d3d8-7113-b313-3c8f7b6609d9 | 0.454644 | unjudged | 0 / content / 458 |
| 6 | kreativ:treff / 019dab00-b596-705a-85cf-53889c2f643d | 0.451932 | unjudged | 0 / content / 69 |
| 7 | Green Noise Festival / 019ed978-b4b9-79cc-97da-4fce867a79da | 0.447438 | unjudged | 0 / content / 436 |
| 8 | Porzellan bemalen / 01a08d89-d6b6-789f-a175-65ff2d2a8268 | 0.446724 | unjudged | 0 / content / 470 |
| 9 | Outdoor Workshop / 019fe1bf-f903-75aa-8867-4e0607f730ae | 0.444364 | unjudged | 0 / content / 242 |
| 10 | "Weg sein" - Ein Literatur- und Theaterprojekt für Jugendliche ab 12 Jahren / 01a01444-7520-7624-839c-046df141eeae | 0.437648 | unjudged | 0 / content / 282 |

The retained grade-1 Utopia evidence explicitly lists Visionboards, Urban Sketching,
Lego printing and children's Spielmobil in a Danish aggregate program. The winning
v3 chunk starts with the bilingual-workshop introduction (476 tokens, index 1);
v5 selects its later program/tail (459 tokens, index 2). The opening context is split,
not absent from the document. Full text and both boundaries are in the reconstruction.
The new leader Jugendatelier explicitly addresses young people aged 11+ drawing and
painting together; Kinderatelier is second. Neither has a judgment for this case.
The first frozen zero, Digitale Teilhabe at 34, describes digital learning rather than
participatory art; it is below Utopia. The metric loss therefore concerns displacement
by mostly unjudged candidates, not a known irrelevant leader. No label is added.
All three positive judgments are only grade 1; no known direct/full match is lost.

### wheelchair-da

| Feld | Ergebnis |
| --- | --- |
| Query | Kulturtilbud med dokumenteret adgang for kørestole |
| Sprache / Kategorie | da / accessibility |
| relevante IDs | 01a05cc3-f200-72ad-99cf-db5ad55a3a56; 01a06740-e026-7b1c-bee7-8a7cd4f861b7 |
| v3 ranks | 9, 12 |
| v5 ranks | 17, 20 |
| stärkster v5 false positive (draft zero) | Kulturh(a)us Utopia — 019da011-1802-7924-8a24-821066242bba, rank 4 |
| v5 leader (unjudged) | Ausstellungseröffnung |
| Hauptdiagnose | A + H: identical 15-event evidence tie moves from ranks 1–15 to 9–23. |
| Sekundärdiagnose | UUID tie-break and occurrence-scoped shared text; not a changed chunk. |
| Confidence | High for tie mechanism; medium for access-wording explanation. |

| Known positive / UUID | Grade | v3 rank / score | v5 rank / score | Gap to boundary v3 / v5 | Same winning text |
| --- | --- | --- | --- | --- | --- |
| GRIND / ANDERS - Wennerberg, Burgess / Franzke / 01a05cc3-f200-72ad-99cf-db5ad55a3a56 | 2 | 9 / 0.525509 | 17 / 0.374739 | +0.000000 / +0.000000 | True |
| Viel wichtiger ist jetzt die Gegenwart - Marie-Louise Monrad Møller / 01a06740-e026-7b1c-bee7-8a7cd4f861b7 | 2 | 12 / 0.525509 | 20 / 0.374739 | +0.000000 / +0.000000 | True |

**v3 Top 10**

| Rank | Event / UUID | Score | Frozen grade | Chunk index / kind / tokens |
| --- | --- | --- | --- | --- |
| 1 | Deich ohne Schafe? / 019daf9b-da9a-7524-9b5c-0f77457ab198 | 0.525509 | unjudged | 4 / accessibility / 79 |
| 2 | Katzen-Kratz-Traum / 019dafca-d731-7476-8e4c-49231d67e882 | 0.525509 | unjudged | 3 / accessibility / 79 |
| 3 | triaden tiraden / 019df20e-4efc-7c01-8c4a-8880af01f14a | 0.525509 | unjudged | 5 / accessibility / 79 |
| 4 | SHOWER / 019e2bbb-892a-7482-a463-bb1da6b27ee5 | 0.525509 | unjudged | 3 / accessibility / 79 |
| 5 | Liquid Bodies / 019e84a4-d625-79fa-99f6-ca653015e6e1 | 0.525509 | unjudged | 3 / accessibility / 79 |
| 6 | Take Care & Stay Safe / 019eac66-4cca-7934-aeae-1dfcf2b5990d | 0.525509 | unjudged | 3 / accessibility / 79 |
| 7 | Passt das Gefühl? - Pilkentafel.dasEnsemble / 01a05c86-8cf0-7d1c-9446-75b5997dec6d | 0.525509 | unjudged | 4 / accessibility / 79 |
| 8 | Spucken wir auf Hegel! - Barletti, Waas / 01a05ca5-c01f-7946-ab28-e8da21c39172 | 0.525509 | unjudged | 4 / accessibility / 79 |
| 9 | GRIND / ANDERS - Wennerberg, Burgess / Franzke / 01a05cc3-f200-72ad-99cf-db5ad55a3a56 | 0.525509 | 2 | 4 / accessibility / 79 |
| 10 | Memokratie. Soziale Medien und autoritäre Bildpolitik - Wolfgang Ullrich / 01a05cdc-aaf1-741c-8f01-0b8b1dbe2c82 | 0.525509 | unjudged | 4 / accessibility / 79 |

**v5 Top 10**

| Rank | Event / UUID | Score | Frozen grade | Chunk index / kind / tokens |
| --- | --- | --- | --- | --- |
| 1 | Ausstellungseröffnung / 01a013db-afe2-7c3a-a2c2-dd9c3bdde3ce | 0.465643 | unjudged | 3 / accessibility / 26 |
| 2 | Nonpareille - multiple art x Druckmuseum / 01a01417-2b98-729d-a402-e884196139a5 | 0.465643 | unjudged | 3 / accessibility / 26 |
| 3 | "Weg sein" - Ein Literatur- und Theaterprojekt für Jugendliche ab 12 Jahren / 01a01444-7520-7624-839c-046df141eeae | 0.435497 | unjudged | 3 / accessibility / 35 |
| 4 | Kulturh(a)us Utopia / 019da011-1802-7924-8a24-821066242bba | 0.397602 | 0 | 1 / content / 464 |
| 5 |  / 019eb0b0-a31f-7afe-b318-91619b308052 | 0.381768 | unjudged | 3 / accessibility / 11 |
| 6 | Hoffnungssingen / 019eb18a-0236-7b9c-bcf5-3a460cd20514 | 0.381768 | unjudged | 3 / accessibility / 11 |
| 7 | Speed-Dating - Kultur trifft Politik / 019eb719-75cb-749e-be9c-fab9c5b5636f | 0.379096 | unjudged | 1 / content / 209 |
| 8 | K26 Kulturtræf / 019dce5e-3d70-7e44-9f1e-d59ab4013fd6 | 0.376715 | unjudged | 1 / content / 125 |
| 9 | Deich ohne Schafe? / 019daf9b-da9a-7524-9b5c-0f77457ab198 | 0.374739 | unjudged | 4 / accessibility / 93 |
| 10 | Katzen-Kratz-Traum / 019dafca-d731-7476-8e4c-49231d67e882 | 0.374739 | unjudged | 4 / accessibility / 93 |

Both known positives use exactly the same 79-token v3 / 93-token v5 passage:
“Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar”;
the same text says the toilets cannot be reached barrier-free with a wheelchair.
The complete 15-event exact-score tie occupies v3 ranks **1–15**, v5 **9–23**.
Eight competitors move above the tied text. GRIND remains ninth within that group;
its overall rank moves 9→17. Both known positives have **zero score gap** to rank 10
in both models. They have not become semantically remote from that boundary.
The tie-break is the same deterministic event UUID ordering in both runs.

GRIND evidence belongs to occurrence `01a05cd1-54c0-715f-a576-4abfdb882cd7`,
venue `019daf99-3496-719b-a3a4-e5c7cc906cb4`,
space `019daf9b-0e23-7ca3-ba04-2adf1043b6a5` in both runs.
The other positive's exact contexts and eligible occurrences are separately recorded
in the reconstruction. Identical venue text does not authorize copying judgments
between events or occurrences.

v5's unjudged leader uses “Der Maschinensaal kann barrierearm über den Eingang des
Kulturzentrums erreicht werden” (26 tokens): shorter, positive but incomplete access
evidence. Its concrete restriction differs from the known positives' inaccessible
toilet. The frozen zero Utopia at 4 selects an open-participation Danish program
without wheelchair access evidence. This is a real partial-intent/semantic false
positive under the frozen label, unlike the nine unjudged Top-10 candidates.

### dance-en

| Feld | Ergebnis |
| --- | --- |
| Query | A lively evening for dancing |
| Sprache / Kategorie | en / atmosphere |
| relevante IDs | 019db61e-a230-7e9b-a02a-8d59e4662280; 019e1d20-4160-770d-aacc-0427d867f8cb |
| v3 ranks | 124, 7 |
| v5 ranks | 215, 13 |
| stärkster v5 false positive (draft zero) | Anja Jacobsen — 019e1fc9-166f-73bd-92f7-8e9343d9eaf4, rank 65 |
| v5 leader (unjudged) | Boogie Woogie Workshop |
| Hauptdiagnose | A + H: Midsommar 7→13 with identical text; dancing displaces evening intent. |
| Sekundärdiagnose | D/joint-space effect plausible; a language-only explanation is contradicted by DE loss. |
| Confidence | High for displacement; medium for intent interpretation. |

| Known positive / UUID | Grade | v3 rank / score | v5 rank / score | Gap to boundary v3 / v5 | Same winning text |
| --- | --- | --- | --- | --- | --- |
| Gården Festival / 019db61e-a230-7e9b-a02a-8d59e4662280 | 1 | 124 / 0.211064 | 215 / 0.246114 | +0.149330 / +0.203015 | False |
| Midsommar Splash! / 019e1d20-4160-770d-aacc-0427d867f8cb | 2 | 7 / 0.381848 | 13 / 0.424893 | -0.021453 / +0.024236 | True |

**v3 Top 10**

| Rank | Event / UUID | Score | Frozen grade | Chunk index / kind / tokens |
| --- | --- | --- | --- | --- |
| 1 | BAM 밤 – für violette Nächte - TachoTinta / 01a09f4a-d945-7f5b-a0c2-7d0bbfa36ff4 | 0.455404 | unjudged | 1 / content / 478 |
| 2 | Salon Night / 01a066e5-2b38-739c-bb78-bdcafbd41108 | 0.438491 | unjudged | 0 / content / 148 |
| 3 | Hautnah / 019f1cc7-18f1-778d-89c5-5d6bd29717f4 | 0.433127 | unjudged | 3 / content / 384 |
| 4 | Cacao & Dance am Strand / 019ed14b-7eb0-7da0-8ee3-3321c9588b9d | 0.417534 | unjudged | 0 / content / 350 |
| 5 | Salon Night / 019edf79-0583-70dd-a9cd-388989ec6d01 | 0.414798 | unjudged | 0 / content / 162 |
| 6 | GRIND / ANDERS - Wennerberg, Burgess / Franzke / 01a05cc3-f200-72ad-99cf-db5ad55a3a56 | 0.408761 | unjudged | 0 / content / 425 |
| 7 | Midsommar Splash! / 019e1d20-4160-770d-aacc-0427d867f8cb | 0.381848 | 2 | 0 / content / 328 |
| 8 | Silent Disco / 019f1767-6e7e-7183-b14c-14f2f635eafc | 0.372420 | unjudged | 0 / content / 372 |
| 9 | Disco für alle / 01a05c60-d7d5-7197-84da-a18469bce542 | 0.366499 | unjudged | 0 / content / 69 |
| 10 | Silvestergala / 01a069ed-7ebe-7987-b7cf-f900854d7b49 | 0.360394 | unjudged | 0 / content / 112 |

**v5 Top 10**

| Rank | Event / UUID | Score | Frozen grade | Chunk index / kind / tokens |
| --- | --- | --- | --- | --- |
| 1 | Boogie Woogie Workshop / 01a0cd8c-e45f-75d2-945c-630009ae1d28 | 0.572015 | unjudged | 1 / content / 266 |
| 2 | TANGOSOMMER / 01a0f815-fe30-7f63-833d-c71c997c08ee | 0.524739 | unjudged | 0 / content / 123 |
| 3 | Hautnah / 019f1cc7-18f1-778d-89c5-5d6bd29717f4 | 0.500999 | unjudged | 5 / content / 339 |
| 4 | Discofox Workshop / 01a0e780-af00-718b-93d2-77c25c6a43e5 | 0.476144 | unjudged | 0 / content / 112 |
| 5 | Cacao & Dance am Strand / 019ed14b-7eb0-7da0-8ee3-3321c9588b9d | 0.459898 | unjudged | 0 / content / 413 |
| 6 | Gangar (N) / 019da560-7ee8-7bdf-82ac-3441a39057ef | 0.459580 | unjudged | 1 / content / 88 |
| 7 | Silvestergala / 01a069ed-7ebe-7987-b7cf-f900854d7b49 | 0.455317 | unjudged | 0 / content / 138 |
| 8 | Tanzabend mit „2 Beat’s“ in der Schloßsee Senioren Residenz / 01a0189b-1103-714a-b36a-71412c1291f5 | 0.451037 | unjudged | 0 / content / 397 |
| 9 | Friday Night / 019dd821-057f-7f3a-a781-28ee9fc44bf3 | 0.450768 | unjudged | 0 / content / 87 |
| 10 | Griechische Tänze / 01a00f78-f6e3-7694-9abe-3e2f16f4c6c9 | 0.449129 | unjudged | 0 / content / 151 |

Midsommar's full winning text is byte-identical (328 v3 / 336 v5 tokens, index 0).
It explicitly combines an African dance workshop with “Ein sommerlicher Abend
zwischen Rhythmus, Tanz, Live-Kultur”. Its fall 7→13 cannot be caused by a changed
boundary for this passage. The v5 leader is a Boogie Woogie Workshop tail (266 tokens)
with dance instruction but explicit **15:30–17:00** timing; “evening” is not established.
This suggests changed weighting of participation/dance versus evening/atmosphere,
not proof of a model-wide inability to represent dancing. The leader is unjudged here
(and separately grade 2 in dance-de; that label is not transferred).
The strongest frozen zero, Anja Jacobsen at 65, describes an experimental concert,
not a dance offer, and lies below both the leader and Midsommar.

### concerts-en

| Feld | Ergebnis |
| --- | --- |
| Query | Concerts spanning different musical genres |
| Sprache / Kategorie | en / multiple_results |
| relevante IDs | 019dab26-d79f-789a-8aa4-9b6f40b8b92d; 019e03a7-5221-7c54-b035-1762dc067c16; 019e1d7d-5af9-7490-9c51-33f8d7a051b4; 019e4022-4f8d-72c6-9f8f-00ec7cc065dd; 019e7d8e-e8b2-747c-bda0-133de3170146; 01a0193a-4873-7e68-ab0f-5c3341296424; 01a0af9b-d3a1-71cb-8749-7d28d7fe065f |
| v3 ranks | 169, 8, 6, 18, 14, 15, 93 |
| v5 ranks | 88, 37, 22, 15, 66, 83, 18 |
| stärkster v5 false positive (draft zero) | Django Galore Quartett — 019fad8e-eb0d-7d27-8674-bc33ffcd3fab, rank 97 |
| v5 leader (unjudged) | Colour Haze |
| Hauptdiagnose | A + H: Strandgut 6→22, Liv Solveig 8→37; broad music competitors. |
| Sekundärdiagnose | C for some tails, but unchanged Strandgut also loses; not EN-only. |
| Confidence | High for ranking; medium for musical-scope interpretation. |

| Known positive / UUID | Grade | v3 rank / score | v5 rank / score | Gap to boundary v3 / v5 | Same winning text |
| --- | --- | --- | --- | --- | --- |
| Su-Min Choi / 019dab26-d79f-789a-8aa4-9b6f40b8b92d | 2 | 169 / 0.254324 | 88 / 0.422123 | +0.157261 / +0.092977 | True |
| Liv Solveig / 019e03a7-5221-7c54-b035-1762dc067c16 | 1 | 8 / 0.424176 | 37 / 0.470723 | -0.012591 / +0.044378 | False |
| Strandgut: David, Ben und Finn / 019e1d7d-5af9-7490-9c51-33f8d7a051b4 | 1 | 6 / 0.444470 | 22 / 0.491403 | -0.032886 / +0.023697 | True |
| Keyo Roses Flying Circus & Krachym / 019e4022-4f8d-72c6-9f8f-00ec7cc065dd | 2 | 18 / 0.390483 | 15 / 0.499826 | +0.021101 / +0.015274 | False |
| Marc-André Hamelin / 019e7d8e-e8b2-747c-bda0-133de3170146 | 1 | 14 / 0.403689 | 66 / 0.440637 | +0.007895 / +0.074464 | False |
| Konzert Wohnzimmerchor / 01a0193a-4873-7e68-ab0f-5c3341296424 | 1 | 15 / 0.402410 | 83 / 0.424976 | +0.009174 / +0.090125 | True |
| Konzert / Al Jacobi (DK) / 01a0af9b-d3a1-71cb-8749-7d28d7fe065f | 2 | 93 / 0.302757 | 18 / 0.496363 | +0.108827 / +0.018738 | True |

**v3 Top 10**

| Rank | Event / UUID | Score | Frozen grade | Chunk index / kind / tokens |
| --- | --- | --- | --- | --- |
| 1 | Konzert 'The Big Guns' / 01a01927-b48f-72c9-bda2-d49e1e77d2ff | 0.498289 | unjudged | 0 / content / 17 |
| 2 | Konzert 'Julie & Jens' / 01a05742-a7df-7498-98e9-6e158ef2e44e | 0.455379 | unjudged | 0 / content / 9 |
| 3 | 1. Sinfoniekonzert / Synästehie / 01a0ee21-a68d-7fed-874d-a31df24a7e74 | 0.450832 | unjudged | 1 / content / 472 |
| 4 | 1. Kammerkonzert / 01a0ee25-2436-7ac4-99ac-0106d75469ad | 0.447313 | unjudged | 0 / content / 342 |
| 5 | Dave Goodman / 019fa7ce-9d08-7812-addf-84bfcdc17e5f | 0.446183 | unjudged | 1 / content / 276 |
| 6 | Strandgut: David, Ben und Finn / 019e1d7d-5af9-7490-9c51-33f8d7a051b4 | 0.444470 | 1 | 0 / content / 293 |
| 7 | Sinfoniekonzert mit dem Collegium musicum Rendsburg / 01a08b45-f315-7131-9316-fd6b3ef8dc24 | 0.424358 | unjudged | 0 / content / 469 |
| 8 | Liv Solveig / 019e03a7-5221-7c54-b035-1762dc067c16 | 0.424176 | 1 | 1 / content / 98 |
| 9 | Konzert vom JugO und dem Miniorchester / 019e6e14-3709-7c21-acfc-74e3ee09bff8 | 0.420282 | unjudged | 0 / content / 396 |
| 10 | Space Tour / 019e3ca8-3698-7f00-822d-7233ebe257d9 | 0.411584 | unjudged | 0 / content / 467 |

**v5 Top 10**

| Rank | Event / UUID | Score | Frozen grade | Chunk index / kind / tokens |
| --- | --- | --- | --- | --- |
| 1 | Colour Haze / 019fb249-fd92-73b6-ac35-861c5b8b4bdf | 0.574434 | unjudged | 1 / content / 105 |
| 2 | Avant-Goth Theater / 01a0d816-d0af-770e-927c-6d1bf77ab522 | 0.557837 | unjudged | 1 / content / 104 |
| 3 | Gangar (N) / 019da560-7ee8-7bdf-82ac-3441a39057ef | 0.556527 | unjudged | 1 / content / 88 |
| 4 | Bohren und der Club of Gore / 019daf44-f841-7694-bee2-c5f2fa02d0e2 | 0.552731 | unjudged | 1 / content / 115 |
| 5 | ... from California to the New York Island... / 01a06428-51b5-70cf-a0e3-61205e7074fc | 0.543800 | unjudged | 1 / content / 146 |
| 6 | SVIN / 019dcb28-a464-74bd-bd67-0fdfdfdb03a6 | 0.540743 | unjudged | 2 / content / 148 |
| 7 | Sunbörn / 019f5b8b-fdab-7bb9-b567-2119e7f30d8e | 0.538164 | unjudged | 1 / content / 458 |
| 8 | Stoppok: RUND-Reise - Die Solo-Tour 2026 / 019fb26a-089a-7f1e-a4c6-9c01a61fa3a2 | 0.518199 | unjudged | 1 / content / 269 |
| 9 | Dave Goodman / 019fa7ce-9d08-7812-addf-84bfcdc17e5f | 0.515587 | unjudged | 1 / content / 397 |
| 10 | CATT / 019f1718-8588-7a68-a99c-8d382b7e51af | 0.515101 | unjudged | 0 / content / 366 |

The lost v3 Top-10 positives are Strandgut (6→22, identical 293/352-token text)
and Liv Solveig (8→37, changed winning slice). Strandgut explicitly enumerates
Swing, Pop, film music and evergreens near the beginning. v5's first known positive
is instead Keyo/Krachym (18→15), whose tail explicitly lists experimental genre
mixtures. Al Jacobi also improves 93→18. Therefore “best known rank 6→15” compares
different events; it is not the displacement of one document.

The unjudged leader Colour Haze is a 105-token descriptive tail plus Concert/Rock
metadata. Its broader document may matter; the winning slice alone does not establish
all genre-spanning intent. All v5 Top-10 candidates are unjudged. The strongest frozen
zero, Django Galore Quartett at 97, describes a specific Django-style acoustic concert,
not an explicit genre-spanning format. A different leader does not prove a false
positive. Broad genre queries strongly expose the small case-specific judgment pool.

## 4. Kategorie-Regressionen

Each row lists **all** known-positive event titles with v3→v5 ranks (same UUID order
as the reconstruction), not only the first hit. Coverage is judged Top-10 slots
v3→v5; unjudged slots are `10−coverage`. Confidence concerns the observed mechanism,
not causal identification of a model component. Full UUIDs, scores and contexts
are in the linked reconstruction. Excluded cases remain excluded.

### atmosphere

Frozen macro Recall@10: **0.245714 → 0.165714**, delta **-0.080000**, gate remains failed.

| Case | Lang | v3 R@10 | v5 R@10 | Delta | Known relevant: v3→v5 ranks | Judged /10 | Likely factor / confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dance-da | da | excluded | excluded | — | no judged positives | 0→1 | mixed intents / sparse judgments; medium |
| dance-de | de | 0.4286 | 0.4286 | +0.0000 | Kapa Tult: 177→387; RUMBIA: 104→183; Hautnah: 8→5; Tanzabend mit „2 Beat’s“ in der Schloßsee Senioren Residenz: 5→3; BAM 밤 – für violette Nächte - TachoTinta: 4→13; NORDEN – The Nordic Arts Festival: 486→175; Boogie Woogie Workshop: 17→1 | 3→3 | mixed intents / sparse judgments; medium |
| dance-en | en | 0.5000 | 0.0000 | -0.5000 | Gården Festival: 124→215; Midsommar Splash!: 7→13 | 1→0 | mixed intents / sparse judgments; medium |
| quiet-da | da | 0.1000 | 0.2000 | +0.1000 | Sommerhygge: 25→2; SVIN: 227→66; Artur Rutkevich: 140→257; Dinesen & Sanz Quarte: 151→163; Sange fra Livet med Anders Agger (Udsolgt!): 63→74; Sange fra Livet med Søren Ryge Petersen: 10→39; Carol Supreme: 143→1; Casper Hejlesen Trio: 70→97; Oktoberfest mit Livemusik vom Geestland Trio 🍻🎶: 171→55; IZHAV (S): 32→14 | 1→2 | mixed intents / sparse judgments; medium |
| quiet-de | de | 0.0000 | 0.0000 | +0.0000 | Sommerhygge: 31→95; RUMBIA: 334→184; Falk: 337→166; Oktoberfest mit Livemusik vom Geestland Trio 🍻🎶: 206→67; 2. Flensburger Stummelum mit Smobar, flimr, Neurodiverdänce uvm.: 254→56; Winterkonzert Rasmus Hoffmeister: 103→13 | 0→0 | mixed intents / sparse judgments; medium |
| quiet-en | en | 0.2000 | 0.2000 | +0.0000 | Conversations: 6→60; Keyo Roses Flying Circus & Krachym: 62→63; Lukas Geniušas: 90→153; Peter Froundjiian: 181→140; Nadejda Vlaeva: 89→212; Marc-André Hamelin: 188→237; Carol Supreme: 167→9; DuoLia.: 9→11; Saint City Orchestra: 16→1; Konzert / Al Jacobi (DK): 225→208 | 2→2 | mixed intents / sparse judgments; medium |

### outdoor

Frozen macro Recall@10: **0.375000 → 0.250000**, delta **-0.125000**, gate remains failed.

| Case | Lang | v3 R@10 | v5 R@10 | Delta | Known relevant: v3→v5 ranks | Judged /10 | Likely factor / confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| historical-q11 | de | 0.3750 | 0.2500 | -0.1250 | Kulturnacht Flensburg 27: 151→45; Circus Ubuntu: 272→127; Fördecrossing: 145→84; ORDRIG: 4→111; Sommer im Garten: 2→3; Faire Woche 2026 Flensburg: 8→2; Wildkräuterwanderung: 47→18; NORDEN – The Nordic Arts Festival: 27→35 | 3→2 | one ORDRIG drop, changed DA boundary; medium |

### theatre

Frozen macro Recall@10: **0.236111 → 0.159722**, delta **-0.076389**, gate remains failed.

| Case | Lang | v3 R@10 | v5 R@10 | Delta | Known relevant: v3→v5 ranks | Judged /10 | Likely factor / confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| puppet-da | da | 0.0000 | 0.0000 | +0.0000 | Kulturh(a)us Utopia: 21→21; Sommerfest på biblioteket: 30→46 | 0→0 | no Top-10 loss; cause not established |
| puppet-de | de | 0.7500 | 0.6250 | -0.1250 | Die Riesin und ihr Topf: 8→15; Du, ich, wir!: 13→10; Eins zwei drei vier Eckstein: 1→8; Maskenball der Tiere: 10→11; Kinderatelier: 41→28; Zauberhafte Märchenwelten gestalten: 4→2; Zauberhafte Märchenwelten gestalten: 5→1; Schneewittchen: 2→3 | 6→5 | puppet-making vs performance / tail weighting; medium |
| puppet-en | en | 0.0000 | 0.0000 | +0.0000 | Kulturh(a)us Utopia: 26→23; Drachenfest: 82→113 | 0→0 | no Top-10 loss; cause not established |
| stage-da | da | 0.0000 | 0.0000 | +0.0000 | Take Care & Stay Safe: 11→27 | 0→0 | no Top-10 loss; cause not established |
| stage-de | de | 0.0000 | 0.0000 | +0.0000 | Liquid Bodies: 11→12 | 1→1 | no Top-10 loss; cause not established |
| stage-en | en | 0.6667 | 0.3333 | -0.3333 | Katzen-Kratz-Traum: 5→26; Liquid Bodies: 8→2; Spucken wir auf Hegel! - Barletti, Waas: 11→31 | 2→3 | generic venue tie vs performance text; medium |

### venue

Frozen macro Recall@10: **0.338889 → 0.241392**, delta **-0.097497**, gate remains failed.

| Case | Lang | v3 R@10 | v5 R@10 | Delta | Known relevant: v3→v5 ranks | Judged /10 | Likely factor / confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| kuehlhaus-da | da | 0.0000 | 0.0769 | +0.0769 | Koncert: Emma Rawicz & The Viridian Trio: 184→86; SVIN: 156→182; Anja Jacobsen: 106→184; ORDRIG: 492→260; Nymalet: 327→107; La.tina: 242→10; Sange fra Livet med Anders Agger (Udsolgt!): 107→199; scheitern.dreitausend & Das Aus Der Jugend: 228→54; Sange fra Livet med Søren Ryge Petersen: 97→112; Robert Stadlober & Tucholsky: 195→109; Oktoberfest mit Livemusik vom Geestland Trio 🍻🎶: 68→22; IZHAV (S): 111→82; Konzert / Al Jacobi (DK): 226→105 | 0→2 | no Top-10 loss; cause not established |
| kuehlhaus-de | de | 0.2000 | 0.1333 | -0.0667 | Max Goldt: 2→81; Rong Kong Koma: 7→85; Förde Vibes mit Lucie Glang: 172→150; RUMBIA: 336→251; Geschichtenzirkus: 24→101; Kurzfilmwerkschau: 25→102; Campus Festival Aftershowparty: 26→103; The Offenders: 1→104; Oktoberfest mit Livemusik vom Geestland Trio 🍻🎶: 87→31; Radio Fratz Soli Party: 33→1; Nachtflohmarkt: 37→2; Hells Kitchen Wrestling: 34→110; ... from California to the New York Island...: 254→23; Konzert: Deer Anna: 115→194; 1. Kammerkonzert: 184→65 | 3→2 | live music + venue conjunction / selected chunk; medium |
| kuehlhaus-en | en | 0.0000 | 0.0000 | +0.0000 | Peter Sommer, Katrine Muff, Palle Hjorth: 53→60; SVIN: 143→195; Keyo Roses Flying Circus & Krachym: 42→123; Nymalet: 344→132; Moskitto Bar (CAN): 87→102; Dinesen & Sanz Quarte: 194→315; Thorbjørn Risager & The Black Tornado: 44→120; Sange fra Livet med Søren Ryge Petersen: 118→146; Girls in Airports: 51→74 | 0→0 | no Top-10 loss; cause not established |
| museumsberg-da | da | 0.5714 | 0.2857 | -0.2857 | Kuratorenführung: 150 Jahre Museumsberg: 3→1; Gården Festival: 499→239; Slotsmarked på Engelsholm: 44→70; triaden tiraden: 6→13; Interreligiöser Dialog: 5→11; Raum. Licht. Struktur. Den Museumsberg fotografisch entdecken: 2→4; Demokratie zum Mitlachen!: 19→51 | 4→2 | specific venue vs broader art; medium |
| museumsberg-de | de | 0.8333 | 0.6667 | -0.1667 | Kuratorenführung: 150 Jahre Museumsberg: 3→1; triaden tiraden: 7→12; Hautnah: 1→15; Jahresausstellung Einblick / Ausblick: 38→8; Interreligiöser Dialog: 5→9; Raum. Licht. Struktur. Den Museumsberg fotografisch entdecken: 2→7 | 6→4 | specific venue vs broader art; medium |
| museumsberg-en | en | 0.4286 | 0.2857 | -0.1429 | Kuratorenführung: 150 Jahre Museumsberg: 3→1; Gården Festival: 474→282; Tag des offenen Denkmals: 60→24; Interreligiöser Dialog: 5→11; Raum. Licht. Struktur. Den Museumsberg fotografisch entdecken: 1→5; Kinderatelier: 93→82; Eintauchen in die Zeit des Biedermeier: 31→39 | 3→2 | specific venue vs broader art; medium |

**Concentration and shared mechanisms.**

- Atmosphere: only dance-en contributes a negative Recall delta (−0.5).
  quiet-da contributes +0.1; the other three included cases contribute zero.
  `(−0.5 + 0.1) / 5 = −0.08`. dance-da has no judged positive and is excluded.
  A whole-category failure here is not evidence of universal atmosphere degradation.
- Outdoor: exactly historical-q11, eight positives; losing ORDRIG changes 3/8 to 2/8.
  ORDRIG's Danish “ud under åben himmel” is retained in the v5 winning chunk near
  the first third; v5 truncates the later program earlier (478 tokens vs 467 v3
  tokens for the longer original text). This is severe displacement **B**, with
  changed representation **C** plausible, multilingual **E** and pooling **G**
  unisolated. Sommer im Garten remains 2→3 and Faire Woche improves 8→2;
  Wildkräuterwanderung improves 47→18. There is no shared multi-case outdoor pattern
  to estimate from this category. Explicit outdoor evidence is present, so the
  ORDRIG loss cannot be dismissed as missing evidence or only label uncertainty.
- Theatre: puppet-de loses one net known hit (−0.125); stage-en loses one of three
  (−1/3). Their mean across six cases is −0.076389. v5 promotes puppet-making
  workshops over some performances. stage-en instead replaces v3's tied generic
  theatre location chunks with performance text; Liquid Bodies improves 8→2,
  Katzen-Kratz-Traum drops 5→26. Distinct partial-intent/chunk mechanisms, not one
  demonstrated pooling problem. Four other cases have zero Recall in both models.
- Venue: all three Museumsberg translations lose coverage while the directly named
  curator tour improves 3→1. Broad art chunks displace weaker venue-related events.
  Kühlhaus-DE's Offenders drops 1→104: v3 used a music-plus-Kühlhaus tail, while v5's
  winning chunk is merely location (19 tokens). Exact venue is **not a hard filter**
  in these frozen cases. The DA gain partly offsets DE loss, and EN stays zero.
  The Museumsberg pattern crosses languages; case-specific label pools remain very
  different. It is a repeated specificity/partial-intent issue, not proof of an
  English-only weakness or a reason to alter eligibility after the fact.

## 5. Kontrollgruppe der v5-Verbesserungen

Small purposive controls, not an independent statistical sample or new evaluation:

| Case | Lang | Query | Words | Recall@10 | First known rank | v5 known event | v5 tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| historical-q02 | de | Angebote zur kulturellen Bildung | 4 | 0.1250→0.5000 | 1→1 | Schule trifft Kultur: Kulturelle Bildung in der Region Rendsburg stärken | 316 |
| quiet-da | da | Rolig livemusik i hyggelige omgivelser | 5 | 0.1000→0.2000 | 10→1 | Carol Supreme | 328 |
| creative-da | da | Skab noget med dine egne hænder | 6 | 0.0000→0.2500 | 15→1 | Lav jeres eget våbenskjold | 467 |
| nordic-en | en | Nordic sounds and Scandinavian music | 5 | 0.5000→0.7500 | 5→2 | Basco | 407 |
| songwriters-en | en | Original songs and personal stories | 5 | 0.3333→0.6667 | 2→1 | Lia L. Shoshann | 468 |

historical-q02 has explicit cultural-education evidence near the beginning;
creative-da's coat-of-arms workshop improves 15→1 with **identical text** (367/467
tokens). nordic-en improves on explicit Nordic/scandinavian wording in German text;
songwriters-en improves on German songs-and-stories descriptions. quiet-da improves
with a partial grade-1 music/mood result, not certified quiet live music. Thus short
queries, cross-language retrieval, abstract paraphrases and long chunks occur among
both gains and losses. The selected controls do not identify a query-length cutoff,
lexical-overlap rule or universal penalty for evidence near the beginning. They
cannot estimate predictive feature effects with this sample size.

## 6. Query-vs-Document-Diagnose

[The small isolated run](../benchmark/results/v5-regression-diagnostics-20261006.json)
performed **58 unique v5 forwards**, using four affected queries, their German
paraphrases, 15 distinct stored chunk texts from relevant events/direct competitors,
and fixed evidence-span variants. The shared retrieval adapter, weights, pooling and
normalization are unchanged. No collection or full-corpus benchmark was run.
[The input plan](../benchmark/diagnostics/20261006-regression-plan.json) fixes all texts,
source point IDs, roles and excerpt offsets before inference. This is exploratory.

The diagnostic raw-forward implementation exactly matches `TorchBackend.embed()`
on the canonical query/passage probes (maximum component difference 0). Canonical
scores for all 13 available matching stored winning event/chunk pairs reproduce
Qdrant scores within `3.25e-8`. This binds the small experiment to the recorded run;
it does not turn out-of-contract variants into an approved model path.

Holding the v5 query fixed, Utopia's **old v3 chunk** scores 0.458832 whereas the
actual v5 winning chunk scores 0.418629. That is concrete document-context sensitivity.
However, the old chunk is **634 v5 tokens**, exceeding the legitimate 480-token
index chunk limit; it is a diagnostic input, not a proposed replacement chunk.
For Keyo/Krachym the opposite occurs: its v5 tail scores 0.499826 versus 0.481633 for
the old v3 winning slice. Boundary changes can help and hurt within the same case.

For GRIND, Midsommar and Strandgut, winning text hashes are identical across models.
Their loss cannot be attributed to changed boundaries for those passages. Query
encoding, document encoding and their shared space still differ across models.
No v3 query vector was multiplied with a v5 document vector: the spaces are
incompatible. These artifacts cannot identify a unique query-side versus document-side
cause for cross-model displacement. The controlled within-v5 interventions below
isolate a changed **input**, not the causal contribution of a particular layer/LoRA.

Canonical selected-pair comparisons (all scores within v5):

| Case | Relevant target chunk | Unjudged leader chunk | Strongest frozen-zero chunk | Target − zero |
| --- | --- | --- | --- | --- |
| historical-q29 | 0.458832 | 0.563398 | 0.394447 | +0.064384 |
| wheelchair-da | 0.374739 | 0.465643 | 0.397602 | -0.022863 |
| dance-en | 0.424893 | 0.572015 | 0.330809 | +0.094084 |
| concerts-en | 0.491403 | 0.574433 | 0.417411 | +0.073993 |

For Utopia the target here is the old complete v3 slice; for the other cases it is
the unchanged first-known-v3-positive slice. A frozen zero does not outrank the
selected known positive in three cases. Wheelchair's Utopia false positive does:
it has broad participatory culture wording without actual wheelchair-access evidence.
This distinguishes a demonstrated frozen-label false positive from an unjudged leader.

## 7. Prefix-Diagnose

Each value is `relevant target similarity − unjudged leader similarity`, **within v5**.
The two texts and adapter are held fixed. A negative margin means the competitor
still wins this pair. This is not an event/corpus rank or threshold recalibration.
For q29 use the old v3 chunk as disclosed above.

| Case | Canonical | No Query prefix | No Document prefix | Neither prefix | German query, canonical |
| --- | --- | --- | --- | --- | --- |
| historical-q29 | -0.104566 | -0.101905 | -0.096622 | -0.089793 | -0.144532 |
| wheelchair-da | -0.090904 | -0.083244 | -0.104919 | -0.098363 | -0.062883 |
| dance-en | -0.147122 | -0.142517 | -0.073511 | -0.068764 | -0.137804 |
| concerts-en | -0.083030 | -0.050026 | -0.012668 | -0.002451 | -0.104677 |

Removing Document especially narrows dance/concert pair gaps, but **none of the
four pairs reverses** under any prefix-removal combination. Removing Query alone
has smaller/mixed effects. Prefix sensitivity **F** is measured; a predominant prefix
cause **R3** is not established. No prefix optimization or production change follows.
All prefix-free inputs violate the published canonical role-instruction contract.

## 8. Chunking-/Pooling-Diagnose

Before inference, exact evidence spans were selected from the frozen target chunks:
Utopia's participatory-project paragraph; Pilkentafel's entrance/toilet statements;
Midsommar's explicit summer-evening/dance sentence; Strandgut's first genre-listing
paragraph. Their exact character offsets and complete text are in the plan.
The relevant span was also moved to beginning/middle/end, preserving the character
multiset. Splitting context at the midpoint can split a word, and token counts can
change by one; this deliberately crude diagnostic is not production chunking.

| Case | Original span position (chars) | Full tokens | Full score | Excerpt only | First | Middle | Last |
| --- | --- | --- | --- | --- | --- | --- | --- |
| historical-q29 | 21%–49% | 634 | 0.458832 | 0.291360 | 0.435920 | 0.459951 | 0.472105 |
| wheelchair-da | 19%–81% | 93 | 0.374739 | 0.383303 | 0.398485 | 0.373576 | 0.378625 |
| dance-en | 77%–91% | 336 | 0.424893 | 0.628218 | 0.475815 | 0.424051 | 0.425162 |
| concerts-en | 5%–34% | 352 | 0.491403 | 0.450872 | 0.555038 | 0.500259 | 0.460168 |

Midsommar's isolated 42-token evening/dance sentence scores 0.628218, versus 0.424893
for the 336-token complete text. Context dilutes that intent; this supports **C/D
representation sensitivity**, even though the original chunk boundary did not change.
Putting the same sentence first improves more than putting it last. Strandgut also
scores highest with the span first; Utopia's highest relocation score is last, while
its excerpt alone is much weaker. Pilkentafel is short and barely changes.

Excerpt-only inputs also remove other query evidence: Utopia's selected paragraph
loses the later children/program details. They do not preserve every semantic
property and cannot isolate length or pooling alone.

These are **not** evidence of a systematic “information early in a long chunk is
lost by last-token pooling” rule. Last-token pooling aggregates a contextual hidden
state, not the literal last word alone. Moving/removing text changes attention,
positions, lexical context and tokenization simultaneously. No matched pooling
ablation was run, so **G remains a hypothesis**. Likewise ORDRIG's explicit outdoor
sentence survives its boundary change; the stored rankings alone cannot attribute
its severe fall to pooling. Controls creative-da and historical-q02 improve with
long chunks and relevant evidence near the beginning.

## 9. Multilingual-Diagnose

Same-UUID controls avoid comparing different translated-case judgment pools:

- GRIND: DA 9→17, DE 11→14, EN 10→14; the new German diagnostic narrows the selected
  pair gap but does not reverse it. Restricted-access semantics and ties persist.
- Midsommar: EN 7→13, DE 10→19, DA 29→34. A pure English-only failure is unsupported.
  The new German paraphrase also leaves Boogie Woogie ahead in the small pair.
- Strandgut: EN 6→22, DE 5→36, DA 10→20. The genre-spanning loss crosses languages.
- Utopia: no saved translated query group. The new German paraphrase strengthens
  Jugendatelier even more relative to Utopia; it does not isolate an English defect.

The new German wordings are reasonable diagnostic paraphrases, not approved exact
translations. Wording and language change together. **E** may contribute locally,
but **R5 (predominantly multilingual)** is not supported. DA creative-da and EN
nordic-en/songwriters-en improvements demonstrate cross-language successes too.

## 10. Judgment-Coverage

For q29, dance-en and concerts-en: **0/10** v5 results are judged. Wheelchair-da:
**1/10** judged (zero), **9/10** unjudged. Their v3 coverage is respectively 1/10,
1/10, 2/10 and 1/10. Across all 105 included cases the unchanged original report
records 874/1,050 unjudged v3 slots and 839/1,050 v5 slots.

The observed H limitation is strong, but cannot by itself explain away ORDRIG's
explicit outdoor match dropping 4→111 or off-topic partial-intent selections.
Unknown relevance stays unknown. No new positive/negative judgment, no-hit approval,
calibration decision or transfer between same-title events was made. Occurrence
context remains explicit, especially the restricted Pilkentafel accessibility.

## 11. Root-cause classification R1–R7

**Overall: R6, several mechanisms.** High-confidence observations: ranking
competition **A**, an exact-score tie/UUID effect, category concentration, partial
query intent and sparse judgments **H**. Document-context sensitivity **C** is
supported by controlled fixed-query examples; altered chunking alone cannot explain
all four losses. Some category events show severe displacement **B**.

**D/query-side versus shared-space**, **E/language**, **F/prefix** and **G/pooling**
are not uniquely identifiable as the predominant cross-model cause. Prefix/content
interventions show sensitivity, not a causal decomposition of two architectures.
Thus the narrow question “which model component caused how much?” remains **R7**.
R1 alone understates genuine known-match displacement; R2 alone overstates causal
isolation; R3/R4/R5 are not supported as a single explanation. Confidence in the
multi-mechanism operational diagnosis is medium; no statistical generalization is
claimed from four losses and five purposive improvement controls.

## 12. Empfehlung zum Fine-Tuning

**Noch nicht.** There is no experiment here establishing that a Kulturbytes-trained
LoRA would fix these failures or preserve gains. Training on incomplete machine
judgments could teach the model to demote plausible unjudged art/music offers.
A language-only or prefix-only training rationale is contradicted by the controls.

The next justified work is human review of the competing pools and occurrence-bound
combined intents, then a separately preregistered diagnostic of document/context
selection and tie behavior using approved judgments. A larger controlled ablation
would be needed to distinguish pooling from context/architecture effects. These are
recommendations for a separate task, not changes implemented here. Thresholds,
chunking, aggregation, prefixes and adapters remain unchanged.

## 13. Noch offene Fragen

- Human relevance of the new leaders and other unjudged neighbors; the six no-hit
  hypotheses remain unresolved.
- How combined venue/accessibility constraints should be represented and evaluated
  in the eventual authoritative runtime path; frozen benchmark eligibility is fixed.
- How frequent duplicated evidence/ties are outside the observed case and what
  uncertainty they introduce at K=10; no alternative tie-break gate was calculated.
- Whether the document-context effects generalize beyond these selected pairs;
  no global counterfactual ranking or pooling ablation was performed.
- The new v3 native/ONNX parity **passes for its fixed small sample**, closing the
  identified exact-graph evidence gap without certifying all possible input lengths.

## 14. Reproduktionshinweise

See [diagnostic README](../benchmark/diagnostics/README.md) for offline reconstruction,
container invocation, input/hash bindings and report assembly. The separate
[v3 parity report](../benchmark/results/v3-benchmark-onnx-parity-20261006.json) includes
all 26 native/ONNX vector pairs and five identical rankings. Its acceptance limits
were frozen before execution. Existing historical reports are not overwritten.

No model packages were added to the Research Service runtime; model imports occur
only in the explicitly isolated diagnostic worker. No model download, training,
collection access/write, reindex, alias switch, production restart/deployment or
semantic activation occurred. `semantic_query=false`. No benchmark metric, gate,
label, threshold or result was changed, and PR #7 is not merged.

Local verification: locked offline sync, Ruff, format and diff checks passed;
**484 tests passed, 24 integration tests skipped locally**, including 13 new
weight-free diagnostic tests. Those tests reconstruct the saved rankings, preserve
unknown judgments, recompute parity from saved vectors, reject identity/hash
mismatches and verify canonical diagnostic scores against the original results.
CI separately runs disposable PostGIS/Qdrant, Admin parity and Docker.
