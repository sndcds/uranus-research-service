# Frozen-case inspection — controlled v3/v5 benchmark

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

Build `20261006_8cpu_001`. Inspection triggers were fixed before results: loss of all known relevant top-10 hits or absolute Recall@10/MRR@10/nDCG@10 change >=0.10. There are **30 material regressions and 51 material improvements across 71 distinct cases**; ten cases satisfy both because different metrics move in opposite directions. All 30 regression cases were inspected, plus the representative improvements below.

Inspection compares frozen wording, selected v3/v5 chunks and boundaries, model-specific scores, existing labels and eligibility. Case eligibility and occurrence sets were independently rechecked against the snapshot for all 240 executions. The same max-chunk aggregation is used without any threshold: neither threshold changes nor different eligibility explains these differences. Boundary changes are observations, not a causal isolation of tokenizer versus model effects.

The accompanying `case-inspection-20261006_8cpu_001.json` records all 71 triggered cases, the top three chunks and first known positive with event/point IDs, hashes, indices, tokens, context IDs and short excerpts. Full public chunk text is in the separate `chunks-v3/v5-*.json` artifacts. An absent grade means unjudged, never an inferred zero. The notes are analyst hypotheses, not new relevance judgments or human approval.

## Every material regression

| Case | Language/category | Δ Recall@10 | Δ MRR@10 | Δ nDCG@10 | First known rank | Unjudged top10 |
| --- | --- | --- | --- | --- | --- | --- |
| historical-q01 | de/family | -0.1429 | -0.1667 | -0.2578 | 2→3 | 7→9 |
| historical-q05 | de/workshops | +0.0000 | -0.1667 | -0.0296 | 2→3 | 6→6 |
| historical-q08 | de/family | -0.1000 | -0.5000 | -0.0381 | 1→2 | 3→4 |
| historical-q11 | de/outdoor | -0.1250 | +0.0000 | -0.1296 | 2→2 | 7→8 |
| historical-q17 | de/music | -0.1538 | +0.3000 | +0.0740 | 5→2 | 6→8 |
| historical-q20 | de/workshops | -0.0714 | +0.0000 | -0.1831 | 1→1 | 4→5 |
| historical-q29 | en/exhibition | -0.3333 | -0.1250 | -0.1480 | 8→20 | 9→10 |
| stepfree-de | de/accessibility | +0.0769 | -0.1250 | +0.0409 | 4→8 | 9→8 |
| wheelchair-de | de/accessibility | +0.0000 | -0.1667 | -0.1438 | 3→6 | 9→9 |
| wheelchair-da | da/accessibility | -0.5000 | -0.1111 | -0.1846 | 9→17 | 9→9 |
| dance-en | en/atmosphere | -0.5000 | -0.1429 | -0.2754 | 7→13 | 9→10 |
| jazz-de | de/music | -0.1667 | +0.8571 | +0.1455 | 7→1 | 7→8 |
| jazz-en | en/music | -0.1250 | +0.8333 | +0.1583 | 6→1 | 6→7 |
| puppet-de | de/theatre | -0.1250 | +0.0000 | -0.2181 | 1→1 | 4→5 |
| stage-en | en/theatre | -0.3333 | +0.3000 | -0.0335 | 5→2 | 8→7 |
| painting-de | de/exhibition | +0.0000 | -0.7500 | -0.1411 | 1→4 | 8→8 |
| painting-da | da/exhibition | +0.0000 | -0.8750 | -0.3212 | 1→8 | 9→9 |
| curator-de | de/exhibition | +0.1667 | -0.1667 | +0.0814 | 2→3 | 7→6 |
| kuehlhaus-de | de/venue | -0.0667 | +0.0000 | -0.3843 | 1→1 | 7→8 |
| museumsberg-de | de/venue | -0.1667 | +0.0000 | +0.2256 | 1→1 | 4→6 |
| museumsberg-da | da/venue | -0.2857 | +0.5000 | +0.2653 | 2→1 | 6→8 |
| museumsberg-en | en/venue | -0.1429 | +0.0000 | +0.2594 | 1→1 | 7→8 |
| folk-de | de/genre | +0.2000 | -0.2500 | +0.0343 | 2→4 | 7→6 |
| punk-en | en/genre | +0.0000 | -0.3571 | -0.1825 | 2→7 | 8→8 |
| songwriters-de | de/paraphrase | +0.0000 | -0.5000 | -0.3382 | 1→2 | 8→8 |
| creative-de | de/paraphrase | -0.5000 | -0.3333 | -0.3210 | 2→6 | 7→9 |
| open-en | en/ambiguous | -0.1667 | +0.0000 | -0.0567 | 1→1 | 6→7 |
| colourful-en | en/ambiguous | +0.0000 | -0.9000 | -0.1565 | 1→10 | 8→9 |
| concerts-de | de/multiple_results | -0.1111 | +0.2083 | -0.0123 | 8→3 | 8→9 |
| concerts-en | en/multiple_results | -0.2857 | -0.1667 | -0.0850 | 6→15 | 8→10 |

### historical-q01

Query: kostenlose Veranstaltungen für Familien

Likely factors: **coverage; combined intent; chunking**. v5 promotes unjudged Frühstücksschnack and a Faire-Woche slice containing free admission and a family registration clause; the known Zwergentreff first hit is replaced by a grade-1 aggregate-event hit. One matching slice does not establish the whole free-and-family intent.

### historical-q05

Query: Sprachkurse

Likely factors: **coverage**. The unchanged full-text hashes for the English refresher, Plattdeutsch taster and Danish course show a ranking change without boundary change. An unjudged explicit language course moves ahead of the known grade-3 Danish course (rank 2→3).

### historical-q08

Query: Veranstaltungen für Seniorinnen und Senioren

Likely factors: **coverage; repeated event variants**. An unjudged Seniorennachmittag with explicit AG für ältere Bürger text replaces the grade-1 Seniorenbeirat at rank 1. Many separate event UUIDs share a title; title identity must not transfer labels.

### historical-q11

Query: Veranstaltungen im Freien

Likely factors: **coverage; aggregate programs; chunking**. v5 promotes an unjudged Campus Festival slice listing picnic, garden and open areas, then the graded mixed-program Faire Woche. Sommer im Garten remains explicit outdoor evidence; the single-case outdoor gate still loses one known top-10 hit.

### historical-q17

Query: Musikveranstaltungen draußen

Likely factors: **coverage; mixed metrics; data quality**. Midsommar Splash with explicit open-air music rises 5→2, but fewer known positives remain in top 10. Sommer im Garten is frozen grade 0 for this case despite garden/music wording: a label-review lead, not an automatic correction.

### historical-q20

Query: Workshops für gemeinsames kreatives Arbeiten

Likely factors: **coverage; graded ordering**. Both models retain kreativ:treff at rank 1 with identical text. v5 then favors Malkreis and an unjudged Kulturtag instead of LAZY SUNDAY/Kinderatelier; lower graded gain is not loss of the first match.

### historical-q29

Query: Participatory art workshops for young people

Likely factors: **coverage; cross-language chunks**. v5 ranks unjudged Jugendatelier first with explicit creative work for ages 11+, and Kinderatelier second. The first known positive Kulturh(a)us Utopia moves 8→20; its Danish program is split differently (v3 chunk 1, v5 chunk 2). This lost-all gate cannot establish that the unjudged top results are irrelevant.

### stepfree-de

Query: Konzerte mit stufenlosem Zugang

Likely factors: **combined intent; chunk selection; coverage**. v3 starts with an accessibility slice about a barrier-free stage. v5 starts with concert-description tails lacking step-free access; its first known positive is a Pilkentafel restricted-access slice. Max-chunk scoring can favor one query component without proving the conjunction.

### wheelchair-de

Query: Kulturangebote mit ausdrücklich beschriebenem Rollstuhlzugang

Likely factors: **accessibility wording; coverage**. v5 favors the Druckmuseum barrierearm entrance text over explicit ramp/wheelchair-seat and Pilkentafel restricted-access text. The known Deich ohne Schafe? falls 3→6 with the same evidence hash; boundaries do not explain that particular fall.

### wheelchair-da

Query: Kulturtilbud med dokumenteret adgang for kørestole

Likely factors: **accessibility wording; ties; coverage**. The unchanged Pilkentafel text documents level access but inaccessible toilets. Many events share its exact vector and UUID tie-breaking; known GRIND / ANDERS moves 9→17 as other barrierearm/ramp texts rank higher. Evidence remains tied to its own occurrence.

### dance-en

Query: A lively evening for dancing

Likely factors: **intent ambiguity; coverage; chunking**. Known Midsommar Splash moves 7→13 with identical text. v5 favors an unjudged Boogie Woogie course tail whose stated time is 15:30–17:00: dancing is evidenced, evening is not. Dance performance versus participating in dance also needs human review.

### jazz-de

Query: Jazz live erleben

Likely factors: **coverage; mixed metrics; chunking**. Warmbluetig moves to rank 1 through a tail describing improvisation, Jazz venues and its live performance. First-positive rank improves 7→1 while known top-10 coverage falls; no global language-quality inference follows.

### jazz-en

Query: Experience live jazz

Likely factors: **coverage; mixed metrics; chunking**. v5 places graded Nighthawks and Warmbluetig first/second, with jazz-related content tails. It loses one other known top-10 hit. v3 leads with an unjudged Daniel Glass Trio text explicitly describing jazz, showing the pool limitation.

### puppet-de

Query: Puppentheater für Kinder

Likely factors: **semantic emphasis; graded relevance**. v5 favors two grade-1 puppet-theatre craft activities above grade-3 Schneewittchen. Participation in building a fairy-tale set is a weaker match than the already graded performance; maximum chunk aggregation itself is identical.

### stage-en

Query: A staged theatrical performance

Likely factors: **generic venue evidence; label review; chunking**. v3 top results are identical theatre location slices. v5 favors actual performance text: Avant-Goth is frozen grade 0 despite explicitly describing immersive theatre, while Liquid Bodies is grade 2. Recall decreases but first-positive rank improves; keep the apparent label tension for human review.

### painting-de

Query: Ausstellungen mit Malerei

Likely factors: **semantic specificity; coverage; chunking**. Known Jahresausstellung falls 1→4; both versions explicitly contain Malerei, but v5 truncates the long chunk earlier. v5 leads with unjudged ACHTundECKIG, whose returned text says exhibition without specifically establishing painting.

### painting-da

Query: Udstillinger med maleri

Likely factors: **coverage; semantic specificity**. Known Nonpareille (print/art techniques, grade 1) moves 1→8 with unchanged chunk text. The v5 leader Kunst im Norden is unjudged and has an art/exhibition passage plus a painting tag. This does not establish a corpus-wide relevance loss.

### curator-de

Query: Kunst mit einer Kuratorenführung entdecken

Likely factors: **coverage; mixed metrics**. v5 retrieves the unjudged, explicitly titled Kuratorenführung at rank 1. Known Innere Gefährten moves 2→3, lowering MRR, although known Recall@10 increases. The new top result explicitly describes a curator leading the exhibition.

### kuehlhaus-de

Query: Livemusik im Kühlhaus

Likely factors: **combined intent; graded relevance; chunk selection**. v3 leads with grade-2 Offenders/LOIT text explicitly mentioning a Kühlhaus stage performance. v5 leads with a grade-1 DJ fundraising party and then a flea market; venue overlap does not establish live music. Venue-related nDCG declines substantially.

### museumsberg-de

Query: Kunst auf dem Museumsberg

Likely factors: **venue specificity; mixed metrics; coverage**. v3 uses Museumsberg location slices; v5 ranks grade-3 Kuratorenführung first but then generic art texts such as kunstkur.park (Pinneberg). Exact venue is not a hard predicate in this frozen case, so it remains a semantic ranking problem. nDCG improves while recall falls.

### museumsberg-da

Query: Kunst på Museumsberg

Likely factors: **venue specificity; mixed metrics; coverage**. The same pattern as DE: v5 promotes the explicitly named Museumsberg curator tour to rank 1, then broader art texts; it loses two known top-10 events. Frozen eligibility is unchanged and does not encode a venue filter.

### museumsberg-en

Query: Art at Museumsberg

Likely factors: **venue specificity; mixed metrics; coverage**. v3 ranks a Museumsberg location slice first, v5 the grade-3 curator-tour content. Higher early graded relevance coexists with loss of one known top-10 result and unjudged broader art results.

### folk-de

Query: Folk und traditionelle Musik

Likely factors: **coverage; cross-language ranking**. v5 leads with an unjudged Danish Carol Supreme passage explicitly discussing folk tradition. The first known positive changes from Gangar at 2 to Nichtseattle/Aalkreih at 4; overall known Recall@10 increases. MRR regression alone is not proof of worse folk retrieval.

### punk-en

Query: Punk music and loud guitars

Likely factors: **coverage; cross-language ranking; label review**. Known ONspace goes Punk falls 2→7 with identical text. v5 leads with unjudged Welcome to Psycho Hell whose slice explicitly discusses punk/garage-rock. Frozen Punk meets Metal is grade 0 here despite explicit punk text; record this tension without relabeling.

### songwriters-de

Query: Selbstgeschriebene Lieder und persönliche Geschichten

Likely factors: **coverage; close ranking; chunking**. An unjudged Lia L. Shoshann description of songs and personal stories overtakes known David Lübke by only about 0.0003 within v5. The selected Lübke slice changes and still explicitly discusses writing songs. MRR loss is sensitive to incomplete judgments.

### creative-de

Query: Mit den eigenen Händen etwas gestalten

Likely factors: **coverage; chunking; semantic specificity**. Both models lead with unjudged Porzellan bemalen, but v5 selects a short final bullet-list slice rather than the whole workshop text. Known Kinderatelier falls 2→6 as craft market/herb material moves up; a market is not automatically hands-on participation.

### open-en

Query: Open stage

Likely factors: **coverage; broad intent**. The first two Open Stage events and the unjudged Offene Bühne keep their order; returned text hashes match. The recall drop concerns later top-10 positions, not loss of the direct named matches.

### colourful-en

Query: A colourful cultural evening

Likely factors: **ambiguous wording; coverage; chunking**. v3 leads with grade-1 BAM and its violet-night performance text; v5 favors unjudged Kultur-trifft-Politik networking and La.tina. The query is underspecified. BAM falls 1→10 with changed boundaries, while known Recall@10 is unchanged.

### concerts-de

Query: Konzerte mit unterschiedlichen Musikrichtungen

Likely factors: **coverage; mixed metrics; short slices**. v5 favors short tails from Colour Haze/Bohren, and known Stoppok rises to rank 3. v3 starts with short generic concert/title text. Known Recall@10 decreases although the first known positive improves 8→3; broad music queries outgrow the judgment pool.

### concerts-en

Query: Concerts spanning different musical genres

Likely factors: **coverage; short slices; cross-language ranking**. All v5 top-10 events are unjudged for this case. Its leaders include Colour Haze, Avant-Goth and Gangar short content tails. First known positive is Keyo/Krachym at 15 versus Strandgut at 6 for v3. This is a genuine frozen-metric lost-all failure, not confirmed absence of relevant music.

## Representative improvements

DE/DA/EN, semantic paraphrases, descriptive search, accessibility and cultural style are represented. Partial grade-1 improvements are explicitly distinguished from a full match.

### historical-q02

Query (de, cultural_style): Angebote zur kulturellen Bildung

| Δ Recall@10 | Δ MRR@10 | Δ nDCG@10 | First known rank |
| --- | --- | --- | --- |
| +0.3750 | +0.0000 | +0.2106 | 1→1 |

Observed factors: **cultural education**. Both keep the explicit Schule trifft Kultur offer first; v5 adds three known relevant top-10 events. Its retrieved K26 program explicitly mentions practical cultural knowledge and exchange.

### historical-q27

Query (en, accessibility): Accessible events requiring registration

| Δ Recall@10 | Δ MRR@10 | Δ nDCG@10 | First known rank |
| --- | --- | --- | --- |
| +0.5000 | +0.2500 | +0.2641 | 269→4 |

Observed factors: **partial combined intent**. Known K26 rises into top 10 through explicit registration text. That slice does not establish accessibility; grade 1 is only partial relevance. The improvement does not demonstrate satisfying both requirements.

### stepfree-da

Query (da, accessibility): Koncerter med trinfri adgang

| Δ Recall@10 | Δ MRR@10 | Δ nDCG@10 | First known rank |
| --- | --- | --- | --- |
| +0.2308 | +0.8333 | +0.3603 | 6→1 |

Observed factors: **partial combined intent; cross-language**. First known positive rises 6→1 via Danish participatory-concert text, with grade 1. The selected slice does not establish step-free access. Improved pooled metrics must not be presented as accessibility certification.

### quiet-da

Query (da, atmosphere): Rolig livemusik i hyggelige omgivelser

| Δ Recall@10 | Δ MRR@10 | Δ nDCG@10 | First known rank |
| --- | --- | --- | --- |
| +0.1000 | +0.9000 | +0.3979 | 10→1 |

Observed factors: **descriptive wording; partial relevance**. First known positive moves 10→1, Carol Supreme with music/dance/mood wording, grade 1; Sommerhygge grade 2 follows. This is a measured graded-ranking gain, not proof that every top result satisfies quiet live music.

### nordic-en

Query (en, cultural_style): Nordic sounds and Scandinavian music

| Δ Recall@10 | Δ MRR@10 | Δ nDCG@10 | First known rank |
| --- | --- | --- | --- |
| +0.2500 | +0.3000 | +0.3156 | 5→2 |

Observed factors: **explicit cultural style; coverage**. Basco moves into the early ranks with explicit Nordic Folk and Scandinavian folklore text. The new unjudged leader explicitly describes Scandinavian folk music despite an empty title field; no artist-background inference is needed.

### songwriters-en

Query (en, paraphrase): Original songs and personal stories

| Δ Recall@10 | Δ MRR@10 | Δ nDCG@10 | First known rank |
| --- | --- | --- | --- |
| +0.3333 | +0.5000 | +0.6778 | 2→1 |

Observed factors: **semantic paraphrase**. v5 ranks Lia L. Shoshann grade 2 first through explicit songs/stories text, versus grade-1 Vinyl Stories as first known v3 match. The same artist/event is unjudged in the DE case: judgments are case-specific.

### creative-da

Query (da, paraphrase): Skab noget med dine egne hænder

| Δ Recall@10 | Δ MRR@10 | Δ nDCG@10 | First known rank |
| --- | --- | --- | --- |
| +0.2500 | +1.0000 | +0.7126 | 15→1 |

Observed factors: **cross-language paraphrase**. Lav jeres eget våbenskjold, grade 3, moves 15→1 with an identical content hash explicitly inviting participants to make their own coat of arms. This improvement is not caused by a changed boundary for that returned passage.

## Four lost-all cases and limits

`historical-q29` (8→20), `wheelchair-da` (9→17), `dance-en` (7→13), and `concerts-en` (6→15) fail the lost-all gate. The arrows are the best known relevant event rank in each model, not necessarily the same event. All v5 top-10 results are unjudged in three of these cases; wheelchair-da has nine unjudged and one frozen zero.

Coverage is sparse: 874/1,050 v3 and 839/1,050 v5 top-10 slots are unjudged. Identical query translations can have different pooled event judgments, and repeated event titles can identify different UUIDs. A frozen zero can conflict with apparent text evidence; such observations above are review leads only. No label, calibration, no-hit status or threshold was changed.

A production decision requires human review of the new top-result pools, separate checking of combined constraints and occurrence context, and validation of the production document/SQL path. These observations do not cancel the preregistered failed gates.
