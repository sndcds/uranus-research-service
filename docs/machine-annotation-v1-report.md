# Machine annotation v1 — Vorschläge zur menschlichen Prüfung

Status: **draft / machine-proposed**, kein human-approved Ground Truth.
Stand: 2026-10-06, Branch `feat/retrieval-ground-truth`, Basis PR #5 / `10d13d3`.

## Umfang und Verteilung

- Cases verarbeitet: **120**.
- Gepoolte Kandidatenpaare verarbeitet: **2352**, jedes genau einmal.
- Vorschläge: **0 = 1674**, **1 = 444**,
  **2 = 127**, **3 = 107**.
- Confidence: **high = 107**,
  **medium = 1732**,
  **low = 513**.
- Occurrence-Review: **632** Kandidatenpaare; umfasst vorsorglich
  auch negative und nur partiell passende Vorschläge zu orts-/zugangssensitiven Queries.
- Mehrdeutige Query-Auslegung: **13 Cases**:
  `open`, `colourful`, `concerts`, `artoptions` (je DE/DA/EN), `historical-q26`.
- Prioritär menschlich prüfen (`review_required=True`): **1343**
  Paare, Vereinigungsmenge ohne Doppelzählung. Darunter **120**
  Kandidaten der sechs No-Hit-Hypothesen.

## Artefakte und Review

- [Machine proposals](../benchmark/annotation/machine-proposals-v1.jsonl): Scores,
  Confidence, Begründung, konkrete Feldpfade und wörtliche Evidenzausschnitte,
  Occurrence-IDs, Snapshot-/Dokument-/Rubrik-Hashes.
- [Human review queue](../benchmark/annotation/human-review-queue-v1.csv): alle Paare,
  zuerst Score 3, dann 2, dann übrige Low-Confidence-Fälle, übrige Occurrence-Fälle,
  schließlich Rest. Innerhalb jeder Stufe stehen No-Hit-Kandidaten zuerst.
  `human_decision` und `human_notes` sind vollständig leer.
- [Vorab festgelegte Rubriken](../benchmark/annotation/machine-rubrics-v1.json).
- [Maschinenlesbarer Prüfbericht](../benchmark/annotation/machine-proposals-v1-validation.json).

Für die Hauptprüfung nach `review_required=True` filtern. Zusätzlich können Menschen
jeden übrigen Vorschlag ändern; insbesondere ist eine maschinelle 0 kein endgültiger
Irrelevanznachweis. CSV-Zeilen referenzieren den vollständigen öffentlichen Eventtext
in `evidence.md`. Positive Scores sind weder Approval noch automatische Exportfreigabe.

## Vorgehen und Grenzen

Die 56 kurzen Rubriken wurden vor der Kandidatenbewertung gespeichert. Die verbindlichen
Nutzerregeln gelten unverändert. Der deterministische Offline-Helfer kombiniert explizite
strukturierte Angaben mit Textfundstellen und fallbezogenen Scope-Entscheidungen nach
Prüfung der eingefrorenen Passagen. Er nutzt keine Retrieval-Rankings, externen Modelle,
Live-Daten, Websites oder Künstler-/Ortswissen. Die vorgeschlagenen Labels selbst sind
**maschinelle Bewertungen**, keine menschlichen Urteile.

Die Textsuche ist eine konservative Unterstützung und kein vollständiger semantischer
Beweis. Implizite Formulierungen, insbesondere dänische Paraphrasen, können unterbewertet
sein. Confidence ist eine qualitative Evidenzeinschätzung, keine kalibrierte Wahrscheinlichkeit.
Alle hohen Scores und die markierten Grenzfälle bleiben zur menschlichen Entscheidung offen.
Ein künftiger Benchmark darf diese Datei nicht als genehmigte Ground Truth laden.

Grad 3 verlangt konkrete explizite Evidenz; Genre plus Veranstaltungstyp darf als öffentliche
strukturierte Evidenz dienen (beispielsweise `Konzert` + `Jazz`). Tags allein werden nicht
verwendet. Biografische Kammermusikengagements begründen kein entsprechendes aktuelles
Programm. Allgemeine Kinderkurse eines Veranstalters begründen kein Familienangebot des
konkreten Termins. Eine Seniorenresidenz allein begründet keine Senioren-Zielgruppe.

Zugangsangaben bleiben an die konkrete Occurrence und deren Space-/Venue-Felder gebunden.
Beispielsweise bleibt der Hinweis auf nicht rollstuhlgerechte Sanitäranlagen der Pilkentafel
vollständig in der JSONL-Evidenz erhalten. Bei gemischten Veranstaltungsprogrammen muss ein
Mensch Teilprogramm und Occurrence zuordnen. Bei Score 1 wegen nur Musik/Anmeldung zeigen
Occurrence-IDs lediglich den öffentlichen Kontext; sie behaupten **keinen** passenden Zugang
oder passenden Ort. Positive Eigenschaften werden nicht auf weitere Occurrences übertragen.
Stadtangaben werden nicht per Weltwissen in Länder umgerechnet.

## Ergänzte Rubriken

Zu den 14 vorgegebenen Kernrubriken kommen 42 queryspezifische Auslegungen hinzu.
Der vollständige Wortlaut und die Case-Zuordnung stehen im eingefrorenen JSON; sein SHA256 ist
`ef0ea425dc00ffcf9471573a9e76304faebfbb75ee3aa674c64d6555c6e273f3`.

| Rubrik | Vorab festgelegte Auslegung |
| --- | --- |
| `access_registration` | 3: konkrete positive Occurrence-Zugangsevidenz UND vorgesehene Anmeldung. 2: beide mit dokumentierter Einschränkung. 1: nur eine Eigenschaft. 0: keine. Tickets zählen nicht. |
| `artoptions` | Konservative Auslegung: mehrere Ausstellungen als Optionen; Einzel-Ausstellung = 2, explizites Angebot mehrerer Ausstellungen = 3, sonst Kunst = 1, kein Bezug = 0. Plural-Auslegung bleibt Reviewfrage. |
| `chamber` | 3: ausdrücklich Kammermusik/kleines klassisches Ensemble. 2: klar kammermusikalischer Teil. 1: kleines Musikensemble anderer Art oder Klassik allein. 0: kein Bezug. |
| `children` | 3: Musikangebot ausdrücklich für Kinder. 2: Musik ausdrücklich für Familien/Jung und Alt. 1: nur Kinderangebot oder Musik. 0: keines. |
| `cityart` | Zuerst Occurrence-Stadt Glücksburg prüfen. 3 ausdrückliche Kunstausstellung; 2 wesentlicher Kunstausstellungsteil; 1 Kunst ohne Ausstellung; 0 keine Kunst. |
| `colourful` | Auslegung: vielseitiger Abend mit mehreren künstlerischen Formen. 3 ausdrücklich mehrere Formen UND Abend; 2 belegte stilistische Vielfalt am Abend; 1 einzelnes Kulturangebot/Vielfalt ohne Abend; 0 keines. Mehrdeutigkeit markieren. |
| `concerts` | Konservative Auslegung: mehrere Musikrichtungen im selben Konzertprogramm. 3 mehrere ausdrücklich gespielte Richtungen; 2 klare Vielfalt mit schwacher Ausführung; 1 einzelnes Konzertgenre; 0 keine Musik. Alternative Interpretation Vielfalt über Ergebnisliste bleibt Reviewfrage. |
| `creative` | 3: aktive eigene händische Gestaltung ausdrücklich angeboten. 2: aktive Gestaltung klar, händischer Aspekt unklar/digital. 1: belegte Kreativität ohne eigene Teilnahme. 0: kein Bezug. |
| `creative_workshop` | 3: Workshop mit gemeinsamem kreativem Arbeiten ausdrücklich angeboten. 2: kreative Praxis klar, gemeinsamer Workshopcharakter nur schwächer. 1: kreativer Teilaspekt. 0: reine Rezeption. |
| `curator` | 3: Kunstführung ausdrücklich durch Kurator:in. 2: kunstbezogene Führung mit Vermittlung, kuratorische Rolle nicht vollständig belegt. 1: Kunst ohne solche Führung. 0: keiner. Künstlergespräch nicht automatisch Kuratorenführung. |
| `dance` | 3: ausgelassene Tanzmöglichkeit am Abend ausdrücklich. 2: aktive Tanzveranstaltung, Abend/Ausgelassenheit nicht vollständig. 1: Tanz als Aufführung oder nur Partybezug. 0: kein Bezug. |
| `danish_denmark` | 3: dänische Kultur/Begegnung UND ausdrücklicher Beleg für Durchführung in Dänemark. 2: beide Aspekte mit Einschränkung. 1: nur ein wesentlicher Teil. 0: keiner. Keine Landeszuordnung aus Städtenamen. |
| `experimental` | 3: explizit experimentelle Kunstpraxis/unübliche künstlerische Form zentral. 2: belegter wesentlicher Form-/Medienbruch. 1: kleiner belegter Aspekt. 0: bloße Neuheit/Alternativästhetik reicht nicht. |
| `flensburg` | 3: ausdrücklich kulturelles Begegnungs-/Austauschangebot in Occurrence-Stadt Flensburg. 2: Kulturangebot in Flensburg ohne direkten Begegnungscharakter. 1: nur Kultur/Begegnung oder Ort. 0: keines. |
| `folk` | 3: tatsächlich gespielte Folk-/traditionelle Musik ausdrücklich. 2: wesentlicher Teil eines breiteren Musikformats. 1: kleiner expliziter Bezug. 0: keiner; Herkunft allein zählt nicht. |
| `free_family_countries` | 3: kostenlos UND Familie UND explizit Deutschland oder Dänemark als Ort (Länder als Suchraumalternativen). 2: kostenlos+Familie, Land nicht textlich belegt. 1: nur ein wesentlicher Aspekt. 0: keiner. Ländermehrdeutigkeit reviewen. |
| `gluecksburg` | 3: konkretes Kulturangebot in Occurrence-Stadt Glücksburg. 2: Ort belegt, Kulturanteil eingeschränkt. 1: nur Kultur oder Ort. 0: keines. |
| `harpsichord` | 3: Workshop zur eigenen Herstellung eines Cembalos. 2: klar entsprechendes Bauangebot mit eingeschränktem Workshopcharakter. 1: tatsächlicher Instrumentenbau oder Bau-Workshop. 0: Cembalomusik allein. Kein No-hit-Abschluss. |
| `history_inclusion` | 3: lokale Geschichte UND soziale Teilhabe ausdrücklich angeboten. 2: beide, einer eingeschränkt. 1: nur ein wesentlicher Aspekt. 0: keiner. |
| `inclusion` | 3: Abbau sozialer Teilnahmebarrieren/aktive soziale Teilhabe expliziter Kern. 2: konkretes zugängliches Begegnungs-/Mitmachangebot. 1: tatsächlicher kleiner Gemeinschaftsaspekt. 0: bloß öffentliches Event. |
| `jazz` | 3: tatsächliches Live-Jazzprogramm ausdrücklich. 2: Jazz wesentlicher Teil eines gemischten Liveprogramms. 1: belegter kleiner Jazzbezug, keine Jazzaufführung zugesichert. 0: kein Bezug; Künstlerwissen verboten. |
| `koreanopera` | 3: Oper UND ausdrücklich koreanische Übertitel. 2: wesentliche Oper mit unvollständiger Übertitel-Angabe; 1: Oper allein. 0: weder; Korea/Operngesang in Konzert allein nicht ausreichend. Kein No-hit-Abschluss. |
| `kuehlhaus` | 3: Livemusik am explizit erfassten Kühlhaus-Ort in konkreter Occurrence. 2: passende Musikveranstaltung mit nicht vollständig belegtem Livecharakter. 1: nur Musik oder Ort. 0: keines. |
| `language_education` | 3: tatsächlicher systematischer Sprachkurs mit kultureller Vermittlung. 2: tatsächliches Sprachlernen plus belegte Bildung. 1: nur einer der wesentlichen Aspekte. 0: keiner. |
| `language_germany` | 3: systematischer Sprachkurs UND Deutschland als Veranstaltungsland explizit. 2: beide Aspekte mit Einschränkung. 1: nur Sprachlernen oder ausdrückliche Länderbedingung. 0: keiner. Keine Geografie-Inferenz. |
| `museumsberg` | 3: konkrete Kunstveranstaltung am erfassten Museumsberg-Ort. 2: Kulturangebot mit begrenztem Kunstanteil am Ort. 1: nur Ort oder Kunst. 0: keines. |
| `nordic` | 3: ausdrücklich nordische/skandinavische Musik als Programm. 2: entsprechender wesentlicher Musikanteil. 1: belegter kleiner musikalischer Bezug. 0: Musikerherkunft allein belegt keinen Stil. |
| `open` | Auslegung VOR Bewertung: offene Bühne = Möglichkeit selbst aufzutreten/Open Mic, nicht Freilichtbühne. 3 explizite Teilnahme; 2 offenes Jam-/Auftrittsformat; 1 kleiner echter Bühnen-Mitmachanteil; 0 bloße Bühne. Mehrdeutigkeit markieren. |
| `outdoor_music` | 3: Live-Musik UND Durchführung draußen explizit. 2: beide mit gemischtem Außen-/Innenformat. 1: nur Musik oder nur Outdoor. 0: keines. |
| `painting` | 3: Ausstellung mit ausdrücklich gezeigter Malerei. 2: Malerei klarer Teil eines breiteren Kunstformats. 1: nur Ausstellung oder nur Malerei. 0: keines. |
| `participatory_art` | 3: eigene aktive künstlerische Praxis ausdrücklich angeboten. 2: klarer Kunst-Mitmachanteil im breiteren Programm. 1: belegte Kunst ohne Mitmachangebot. 0: weder. |
| `punk` | 3: Punkprogramm UND Gitarren/lauter Klang explizit. 2: Punkprogramm klar, Gitarrenlautstärke nicht ausdrücklich. 1: nur Rock/Gitarren oder untergeordneter Punkbezug. 0: keiner. |
| `puppet` | 3: Puppen-/Figurentheater ausdrücklich für Kinder. 2: Puppentheater mit breiter Familienzielgruppe. 1: nur Puppenspiel oder Kindertheater. 0: keines. |
| `quiet` | 3: Livemusik UND ruhig/intim UND gemütliche Atmosphäre explizit. 2: Livemusik mit ausdrücklich passender Atmosphäre, nicht alle Nuancen. 1: nur Musik. 0: keine. Akustik/Klassik allein belegt keine Ruhe. |
| `saturday` | Zuerst Datum 2026-10-10, Samstag UND Flensburg in derselben Occurrence prüfen. Dann Jazz-Rubrik: 3 direktes Live-Jazzangebot, 2 wesentlicher gemischter Anteil, 1 kleiner Jazzbezug, 0 keiner. |
| `songwriters` | 3: eigene Lieder UND persönliche Geschichten ausdrücklich im Programm. 2: eigene Lieder mit nur schwach belegtem persönlichem Erzählcharakter. 1: nur eigene Lieder/persönliche Erzählung. 0: Cover/Songwriter-Genre allein nicht vollständig. |
| `stage` | 3: konkrete inszenierte Theater-/Bühnenaufführung. 2: wesentlicher szenischer Anteil eines gemischten Formats. 1: kleinere Theaterszene/Lesung mit belegter szenischer Komponente. 0: Konzert auf Bühne allein reicht nicht. |
| `stepfree` | 3: Konzert UND explizit stufenloser Zugang an derselben Occurrence. 2: beide mit Einschränkung. 1: Musik/Konzert ohne Zugangsbeleg oder positiver Zugang allein. 0: keines. Keine Übertragung von Venue auf unbestätigten Space. |
| `together` | 3: aktive kreative Tätigkeit ausdrücklich gemeinsam als Familie. 2: beide Aspekte, gemeinsames Familienformat schwächer. 1: nur Kreativität oder Familie. 0: keines. |
| `wheelchair` | 3: Kulturangebot mit ausdrücklich rollstuhlgerechtem Zugang an konkreter Occurrence. 2: explizit teilweiser/eingeschränkter Rollstuhlzugang. 1: positive Zugangsevidenz ohne Rollstuhlspezifik. 0: keine. |
| `youth` | 3: Jugendliche ausdrücklich Hauptzielgruppe. 2: klare Jugendkomponente im breiteren Angebot. 1: belegter kleiner Bezug. 0: Kinder/Studierende/junges Ensemble allein nicht Jugendliche. |
| `youth_art` | 3: aktiver Kunstworkshop ausdrücklich für Jugendliche. 2: alle Aspekte, Zielgruppe breiter. 1: nur Kunstmitmachen oder Jugendbezug. 0: keiner. |

## Cases mit vorgeschlagenem Grad 3

| Case | Kandidaten mit Grad 3 |
| --- | ---: |
| `chamber-da` | 1 |
| `chamber-de` | 1 |
| `children-de` | 1 |
| `creative-da` | 1 |
| `creative-de` | 3 |
| `experimental-de` | 1 |
| `experimental-en` | 2 |
| `folk-da` | 2 |
| `folk-de` | 5 |
| `folk-en` | 3 |
| `gluecksburg-da` | 1 |
| `gluecksburg-de` | 3 |
| `gluecksburg-en` | 5 |
| `historical-q01` | 1 |
| `historical-q02` | 3 |
| `historical-q04` | 2 |
| `historical-q05` | 2 |
| `historical-q06` | 7 |
| `historical-q07` | 5 |
| `historical-q08` | 6 |
| `historical-q11` | 2 |
| `historical-q12` | 4 |
| `historical-q13` | 1 |
| `historical-q14` | 1 |
| `historical-q15` | 2 |
| `historical-q16` | 4 |
| `historical-q17` | 2 |
| `historical-q18` | 2 |
| `historical-q20` | 1 |
| `historical-q21` | 1 |
| `historical-q25` | 1 |
| `jazz-da` | 3 |
| `jazz-de` | 6 |
| `jazz-en` | 8 |
| `museumsberg-da` | 1 |
| `museumsberg-de` | 1 |
| `museumsberg-en` | 1 |
| `nordic-da` | 3 |
| `nordic-de` | 2 |
| `nordic-en` | 1 |
| `painting-de` | 1 |
| `puppet-de` | 2 |
| `songwriters-da` | 1 |
| `songwriters-de` | 1 |

## No-Hit bleibt ungeklärt

`koreanopera-de/da/en` und `harpsichord-de/da/en` bleiben alle offen.
`expected_no_hit` wurde nicht gesetzt. Selbst ausschließlich mit 0 vorgeschlagene Pools
belegen keinen No-Hit im gesamten eligible Corpus. Bei Cembalobau werden einzelne
Bau-/Bastelangebote lediglich als schwache Teilaspekte vorgeschlagen; ein Cembalobau-Angebot
wird damit ausdrücklich nicht behauptet. Alle 120 Pool-Kandidaten dieser Queries benötigen
menschliche Prüfung, gefolgt von der Prüfung des vollständigen eligible Corpus.

## Integrität und Validierung

Der Offline-Validator prüft vollständige und eindeutige Paarabdeckung, Integer-Scores 0–3,
Confidence-Werte, positive Begründungen/Feldpfade, Grade 3 nur mit High Confidence, exakt
auflösbare wörtliche Belege, konkrete gültige Occurrence-Referenzen, Snapshot-/Dokumentbindung,
fehlende Approval-Felder und Byte-Hashes aller vier erlaubten Quelldateien. Tests prüfen zudem
CSV-Sortierung, leere menschliche Eingaben, deterministische Reproduktion und konsistente
Bewertung gemeinsamer Kandidaten in Übersetzungsgruppen.

Reproduktion ausschließlich lokal:

```sh
python scripts/machine_annotations.py
uv run pytest -q tests/test_machine_annotations.py
```

Der Helfer verweigert das Überschreiben einer CSV mit bereits eingetragenen menschlichen
Entscheidungen oder Notizen. Menschliche Bearbeitung deshalb als neue Revision speichern.

Die Original-Ground-Truth-Datei, alle vorhandenen menschlichen Felder, der öffentliche
Snapshot und die Annotationsrichtlinien sind bytegleich erhalten. Es wurde kein menschliches
Approval erzeugt, kein `review_status=approved` gesetzt und kein menschlicher Reviewer erfunden.
Der kanonische Snapshot-Hash bleibt
`295d51592050b67be40d7a4de8dd3ac5885fbe2562700b3e3578f8b107785029`.

| Quelle | Unveränderter Datei-SHA256 |
| --- | --- |
| `benchmark/ground-truth-v1.jsonl` | `a72b04ca44655ca4e8ba456e8d9698ff6ebbe47e1dde54f075780c9e6e4a8b53` |
| `benchmark/snapshots/public-events-20261005/events.jsonl` | `2de49bc71942926e953f4de76d4b5dbcfe1780a6a2a20ee2b0feb6fa97cbf7f1` |
| `benchmark/annotation/evidence.md` | `282525301580328c6c2e10e02d878d1339a139612839471c816fefd6012afa77` |
| `docs/retrieval-annotation-guidelines.md` | `149573227a99c3122efd6c8108818b727467ee4329514d6e84a1ff055d8ed4f1` |

Keine offizielle v3/v5-Evaluation, keine Threshold-Änderung, keine Semantic-Aktivierung.
`semantic_query=false` bleibt unverändert. Kein Live-Zugriff und keine Live-Writes in diesem
Auftrag. Runtime, Admin, Planner und Encoder wurden nicht geändert.

## Ausgeführte Repository-Checks

- `UV_CACHE_DIR=/tmp/uranus-machine-uv uv sync --locked --offline`: erfolgreich.
- Ruff und Formatprüfung: erfolgreich.
- `pytest -q tests/test_machine_annotations.py`: **18 bestanden**.
- `pytest -q`: **400 bestanden, 24 übersprungen** (22 Integrationstests und zwei optionale
  Real-Encoder-Tests). Für diesen reinen Offline-Annotationsauftrag wurden keine neuen
  DB-/Qdrant-/Encoder-Integrationsläufe gestartet.
- `git diff --check`: erfolgreich.

Keine neue Remote-CI- oder Docker-Ausführung wird mit diesen lokalen Ergebnissen behauptet.
