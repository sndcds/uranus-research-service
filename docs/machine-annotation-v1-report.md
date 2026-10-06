# Machine annotation v1 — calibration correction

**draft / machine-proposed**, kein human-approved Ground Truth.

- Cases: **120**; Kandidatenpaare: **2352**, jedes genau einmal.
- Scores 0/1/2/3: **{0: 1650, 1: 452, 2: 133, 3: 117}**.
- Confidence: **{'medium': 1722, 'high': 117, 'low': 513}**.
- Cases mit Grad 3: **45**.
- Occurrence-Review: **632** Paare.
- Mehrdeutige Query-Auslegung: **13** Cases.
- Prioritäre menschliche Prüfung: **1354** Paare (`review_required=True`).

## Artefakte

- [Vorschläge](../benchmark/annotation/machine-proposals-v1.jsonl)
- [Review Queue](../benchmark/annotation/human-review-queue-v1.csv)
- [Validierungsbericht](../benchmark/annotation/machine-proposals-v1-validation.json)
- [Manuelle Policy und vollständiger Driftbericht](manual-calibration-v1-report.md)
- [56 vorab gespeicherte Rubriken einschließlich 42 queryspezifischer Ergänzungen](../benchmark/annotation/machine-rubrics-v1.json)

Die Rubriken bleiben bytegleich; die neue manuelle Kalibrierung hat für ihre exakten Paare Vorrang.
Queryspezifische Ergänzungen betreffen insbesondere kombinierte Kriterien, Musik-/Kunstformen,
Ortsbezüge und mehrdeutige Formulierungen. Wortlaut und vollständige Case-Zuordnung stehen im Rubriken-JSON.

Review-Reihenfolge: Grad 3 → Grad 2 → Evidenzkonflikt → Low Confidence → Occurrence-sensitiv →
No-Hit-Hypothese → Rest. Kein Kandidat wird durch Kalibrierung entfernt. Die CSV-Felder
`human_decision`/`human_notes` bleiben leer. Score 3 bedeutet weiterhin Vorschlag, nicht Approval.

## Evidenz und Grenzen

Die Offline-Heuristik verwendet ausschließlich den eingefrorenen öffentlichen Snapshot, konkrete
strukturierte Felder und Textfundstellen. Keine Modellrankings, keine Künstler-/Ortsannahmen und keine
neuen externen Quellen. Unterbewertung indirekter Formulierungen bleibt möglich; Confidence ist keine
kalibrierte Wahrscheinlichkeit. Manuelle Policy-Entscheidungen sind separat nachvollziehbar.
Zugangsangaben gelten nur für die referenzierten Occurrences; eingeschränkte Sanitäranlagen bleiben
in der Evidenz sichtbar. Bei Aggregatprogrammen ist die Teilprogramm-Zuordnung weiterhin reviewpflichtig.
Reale Zitate bei markierten Konflikten werden nicht als Beweis einer im Snapshot fehlenden Eigenschaft ausgegeben.

## Offene No-Hit-Fälle

`koreanopera-de/da/en` und `harpsichord-de/da/en`: alle sechs bleiben ungeklärt, alle 120 Kandidaten
reviewpflichtig. Keine Änderung von `expected_no_hit`; ein negativer Pool ersetzt keine menschliche
Prüfung des gesamten eligible Corpus.

## Integrität und Reproduktion

```sh
python scripts/machine_annotations.py
uv run pytest -q tests/test_machine_annotations.py
```

Der Loader stoppt bei fehlender echter Evidenz, nicht auflösbaren Feldpfaden, Hash-/Titelabweichungen
oder mehrdeutiger Zuordnung. Bestehende menschliche CSV-Eingaben dürfen nicht überschrieben werden.
Keine Approval-Felder wurden erzeugt oder verändert; keine menschliche Authentifizierung behauptet.
Original Ground Truth, Snapshot, evidence.md und Richtlinien sind byte-identisch:

| Quelle | SHA256 |
| --- | --- |
| `benchmark/ground-truth-v1.jsonl` | `a72b04ca44655ca4e8ba456e8d9698ff6ebbe47e1dde54f075780c9e6e4a8b53` |
| `benchmark/snapshots/public-events-20261005/events.jsonl` | `2de49bc71942926e953f4de76d4b5dbcfe1780a6a2a20ee2b0feb6fa97cbf7f1` |
| `benchmark/annotation/evidence.md` | `282525301580328c6c2e10e02d878d1339a139612839471c816fefd6012afa77` |
| `docs/retrieval-annotation-guidelines.md` | `149573227a99c3122efd6c8108818b727467ee4329514d6e84a1ff055d8ed4f1` |

## Cases mit vorgeschlagenem Grad 3

- `chamber-da`
- `chamber-de`
- `children-de`
- `creative-da`
- `creative-de`
- `experimental-de`
- `experimental-en`
- `folk-da`
- `folk-de`
- `folk-en`
- `gluecksburg-da`
- `gluecksburg-de`
- `gluecksburg-en`
- `historical-q01`
- `historical-q02`
- `historical-q04`
- `historical-q05`
- `historical-q06`
- `historical-q07`
- `historical-q08`
- `historical-q09`
- `historical-q11`
- `historical-q12`
- `historical-q13`
- `historical-q14`
- `historical-q15`
- `historical-q16`
- `historical-q17`
- `historical-q18`
- `historical-q20`
- `historical-q21`
- `historical-q25`
- `jazz-da`
- `jazz-de`
- `jazz-en`
- `museumsberg-da`
- `museumsberg-de`
- `museumsberg-en`
- `nordic-da`
- `nordic-de`
- `nordic-en`
- `painting-de`
- `puppet-de`
- `songwriters-da`
- `songwriters-de`

Keine offizielle v3/v5-Evaluation, Threshold-Änderung oder Aktivierung. Dataset bleibt draft.
Kein Live-Zugriff. Runtime, Admin, Planner und Encoder unverändert. PR #6 bleibt Draft und ungemergt.
