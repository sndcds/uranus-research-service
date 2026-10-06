# Final calibration review v1 — PR #6

Status: **calibration-policy / machine-proposed; dataset remains draft**. Diese Nachprüfung wurde vom Nutzer beauftragt; sie ist keine menschliche Annotation oder Benchmark-Freigabe. Es wurden keine Reviewer-Identitäten oder Approval-Felder angelegt.

## Umfang und Ergebnis

Basis: `29c8527b1ed0126219a7e7a0074587d6013b365d`. Ausschließlich die 16 markierten Evidenzkonflikte und fünf offenen Policy-Paare wurden anhand ihrer **vollständigen** eingefrorenen Eventtexte, strukturierten Felder und Occurrences nachgeprüft. Query-Rubriken und die allgemeine Heuristik wurden nicht neu bewertet.

- 21 Entscheidungen: 16 bestehende Scores geändert (3 höher, 13 niedriger); fünf zuvor offene Paare explizit kalibriert.
- Gegenüber den bisherigen Maschinenvorschlägen: **16 geändert, 5 unverändert**. Bei den fünf neuen Kalibrierungen bedeutet „changed: yes“ die neue Policy-Festlegung, nicht eine Scoreänderung.
- Kalibrierte Paare: **280**. Verbleibende Kalibrierung/Evidenz-Konflikte: **0**. Offene Kalibrierungspaare: **0**.
- Scoreverteilung 0/1/2/3 vorher: **1640 / 461 / 134 / 117**; nachher: **1650 / 452 / 133 / 117**.
- Grad 3: unverändert **117**; **keine** Änderung mit Beteiligung von Grad 3. Alle bleiben high-confidence Maschinenvorschläge und menschlich reviewpflichtig.
- Prioritäre Review-Paare: **1354** von insgesamt **2352** in **120** Cases. Alle Queue-Zeilen bleiben erhalten.
- Die übrigen **2331** Vorschläge bleiben inhaltlich unverändert, einschließlich aller q15+ Vorschläge. Auf anderen kalibrierten Zeilen ändert sich lediglich der gemeinsame Kalibrierungsdatei-Hash.
- Alle sechs No-Hit-Hypothesen (`koreanopera-de/da/en`, `harpsichord-de/da/en`) bleiben ungeklärt; `expected_no_hit` bleibt unverändert null.

## Bewertungsgrundlage

Nur die sechs im Auftrag genannten lokalen Dateien wurden als Evidenz verwendet: Ground Truth, Snapshot, evidence.md, Richtlinien, Kalibrierungsdatei und bisheriger Kalibrierungsbericht. Keine externen Quellen, Webseiten, Live-Daten oder Künstler-/Venue-Annahmen.

Grad 0 bedeutet hier „erforderlicher Bezug nicht belegt“, nicht den Nachweis, dass eine Eigenschaft tatsächlich fehlt. Die Zitate bei Grad 0 dokumentieren den vorhandenen Inhalt; die Begründung berücksichtigt den vollständigen Eventdatensatz. Grad 1 bei La.tina bewertet den kleinen Sprachkursbestandteil auf Aggregatebene. Regionale kulturelle Identität kann nach der vorgegebenen Lokalgeschichte-Rubrik Grad 1 tragen, ersetzt aber keine historische Vermittlung für Grad 2.

## Einzelentscheidungen

### 1. historical-q03 — Reading Party "Let's Get Cosy"

- case_id: `historical-q03`
- event_id: `01a0c369-117f-7172-aed1-c50b052af59d`
- Query: barrierefreie Veranstaltungen
- document_hash: `5ad8506a7a8b18a498ab05308144eccc355f11cb1ccc4cf2f8c3eb5846eacfc9`
- Vorher kalibriert: **1**; final: **2**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 2**.
- Begründung: Die Beschreibung belegt barrierearmen Zugang und eine barrierefreie Toilette im Isa für den einzigen erfassten Termin. Konkrete Teilbarrierefreiheit rechtfertigt 2; vollständige Barrierefreiheit wird nicht behauptet.
- supporting_fields: `description`, `title`, `occurrences.0.id`, `occurrences.0.start_date`
- requires_occurrence_review: `true`

Konkrete positive Occurrence-Evidenz:

- `occurrences.0`: `01a0c370-2822-74a9-b346-189418e07389`, 2026-10-15; venue_id `None`, space_id `None`.
Keine Übertragung auf weitere Termine oder Räume.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Das Isa ist barrierearm zugänglich und verfügt über eine barrierefreie Toilette."
- `title`: "Reading Party \"Let's Get Cosy\""

### 2. historical-q05 — La.tina

- case_id: `historical-q05`
- event_id: `019e6df1-b798-7db1-bd65-ca7bd04e91bc`
- Query: Sprachkurse
- document_hash: `f380aedbe93fc691d74d1cbe81c3b67c745d79b898ca98ca3afb9a9f8f28facc`
- Vorher kalibriert: **0**; final: **1**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **0 → 1**.
- Begründung: Das Festivalprogramm enthält am 13.06. um 14 Uhr ausdrücklich einen QUECHUA SPRACHKURS im Kulturhof. Sprachlernen ist damit ein echter, aber kleiner Teil des mehrtägigen Tanz-, Musik- und Kulturprogramms. Auf Aggregatebene 1, kein eigenständiges Sprachkursangebot mit Grad 3.
- supporting_fields: `description`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "14:00 Uhr QUECHUA SPRACHKURS Kulturhof"

### 3. historical-q06 — Parkfest im Christiansenpark

- case_id: `historical-q06`
- event_id: `019eba56-fe7d-79dc-9683-d2eac4ebb2f1`
- Query: Veranstaltungen zum Thema Nachhaltigkeit
- document_hash: `616ae9e56a0da886b0a71047248dc538c30bf2c5e3dd3da0a9373b9f5efb6668`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Botanische und historische Führungen sowie traditionelles Handwerk sind belegt. Ein Nachhaltigkeitsziel, Ressourcenbezug oder ökologischer Bildungsinhalt wird nicht benannt. Natur und Handwerk allein begründen keine positive Nachhaltigkeitsrelevanz.
- supporting_fields: `description`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "einen botanischen und einen historischen Rundgang durch den Park)"
- `title`: "Parkfest im Christiansenpark"

### 4. historical-q06 — Liquid Bodies

- case_id: `historical-q06`
- event_id: `019e84a4-d625-79fa-99f6-ca653015e6e1`
- Query: Veranstaltungen zum Thema Nachhaltigkeit
- document_hash: `cefbe8a5e29fe14a6df20ad200953db605a994b2e6eb6ebaeb2c405678e7c8ea`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Wasser dient als künstlerischer Bezug für Care, Körper und gesellschaftliches Zusammenleben. Der vollständige Text benennt keinen ökologischen oder Nachhaltigkeitsinhalt; Wasser allein reicht nicht.
- supporting_fields: `summary`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `summary`: "Die Glitch AG untersucht in ihrer Trilogie OPEN WATER über drei Jahre und Arbeiten das utopische Potential von Wasser im Hinblick auf unser gesellschaftliches Miteinander."
- `title`: "Liquid Bodies"

### 5. historical-q07 — Cultural Pearl Kulturtag

- case_id: `historical-q07`
- event_id: `019e63f7-ebeb-7952-9304-e496b02e3588`
- Query: Angebote für Kinder
- document_hash: `06f865310d623c6ddf897f9614d825b88651b640adb708a423153810d111d2b4`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Der Kulturtag stellt die lokale Kulturszene vor und lädt allgemein zum gemeinsamen Erleben ein. Kinder oder Familien werden weder als Zielgruppe noch als konkrete Teilnehmendengruppe genannt. Kultur für alle ist kein Kinderbeleg.
- supporting_fields: `summary`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `summary`: "Im Mittelpunkt steht die vielfältige Glücksburger Kulturszene: Lokale Kulturakteurinnen und Kulturakteure präsentieren ihre Angebote, Projekte und Ideen an verschiedenen Orten im gesamten Stadtgebiet und machen Kultur für alle erlebbar."
- `title`: "Cultural Pearl Kulturtag"

### 6. historical-q07 — Skandaløs Festival

- case_id: `historical-q07`
- event_id: `019daf20-38e6-7283-9746-c604f6523e33`
- Query: Angebote für Kinder
- document_hash: `896f84cb170690e4a05326f00f7c3aafce06b85ba0847247632c63bd3e2d49cb`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Das vollständige Festivalprogramm beschreibt Musik, Kunst, Kultur und politische Inhalte, aber kein Kinder- oder Familienangebot. Allgemeine Teilnahme und Festivalcharakter begründen keine Kinderrelevanz.
- supporting_fields: `description`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Alle zwei Jahre bietet ein überwiegend ehrenamtliches Team bis zu 4000 Besucher:innen ein vielseitiges Programm aus Musik, Kunst und Kultur sowie Raum zur Auseinandersetzung mit gesellschafts- und umweltpolitischen Themen."
- `title`: "Skandaløs Festival"

### 7. historical-q07 — KulturRotation 143

- case_id: `historical-q07`
- event_id: `019e262e-5660-76c8-93cc-c7736848b4d3`
- Query: Angebote für Kinder
- document_hash: `5c1736ac8e378a23880d578c635bc8ac1f20fc7b3f15f1f186abe074d6671513`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Das offene, nicht kommerzielle Kulturformat in Kiel-Gaarden benennt keine Kinder oder Familien. Offenheit und kostenloser Zugang ersetzen keinen belegten Kinderbezug.
- supporting_fields: `summary`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `summary`: "Alle Angebote sind kostenlos, offen und spontan erlebbar."
- `title`: "KulturRotation 143"

### 8. historical-q08 — Disco für alle

- case_id: `historical-q08`
- event_id: `01a05c60-d7d5-7197-84da-a18469bce542`
- Query: Veranstaltungen für Seniorinnen und Senioren
- document_hash: `04788ebdbdf515b5327229a72237d6c77759f1670541f87ad0e5a9c2cb84a848`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Die Disco richtet sich ausdrücklich an Menschen mit und ohne Behinderung. Das ist Inklusion, aber kein belegtes Angebot für ältere Menschen; Senioren oder eine entsprechende Alterszielgruppe fehlen.
- supporting_fields: `description`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Im Sinne der Inklusion sind alle Menschen mit und ohne Behinderung herzlich eingeladen."
- `title`: "Disco für alle"

### 9. historical-q08 — Gesteins- und Fossiliensprechstunde

- case_id: `historical-q08`
- event_id: `01a0f032-2002-72db-8819-57013c0b40b8`
- Query: Veranstaltungen für Seniorinnen und Senioren
- document_hash: `3ad62bbd8b6010626cd96647a8d318a35a4306372429271ff50ed958932206ea`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Die Sprechstunde bietet Besucherinnen und Besuchern fachliche Bestimmung mitgebrachter Gesteine und Fossilien. Ein Seniorenbezug oder eine altersbezogene Zielgruppe ist nicht angegeben.
- supporting_fields: `summary`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `summary`: "Besuchende des Eiszeit-Hauses können Versteinerungen und Gesteine unseren Experten zur Bestimmung vorlegen."
- `title`: "Gesteins- und Fossiliensprechstunde"

### 10. historical-q08 — DI.DAY

- case_id: `historical-q08`
- event_id: `019ddd54-2a60-76c7-8ccb-8d67862e6c95`
- Query: Veranstaltungen für Seniorinnen und Senioren
- document_hash: `941e0c6151b7283b64bcd030a4c50ad9a5ac25a5b2039db5a363d280845160d4`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Digitale Selbstständigkeit und allgemeine Hilfe sind belegt; die Organisationsbeschreibung nennt Kinder, Jugendliche und Erwachsene. Senioren oder ältere Menschen werden nicht eigens angesprochen. Allgemeine Erwachsene begründen keine Seniorenrelevanz.
- supporting_fields: `description`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Neben 3D-Druckern, Lötkolben, VR-Headsets, Siebdruck und Werkzeugen aller Art bieten wir Schulungen und Kurse für Kinder, Jugendliche und Erwachsene an."
- `title`: "DI.DAY"

### 11. historical-q12 — Digitale Teilhabe – gemeinsam vernetzt

- case_id: `historical-q12`
- event_id: `019db91a-89d5-7c5a-90ae-7596e488a1eb`
- Query: Integration und Migration
- document_hash: `e4c3d1a6f20501aab85835c3e48ea27bb45223da10fd1d85f1ee96ed7f67403a`
- Vorher kalibriert: **1**; final: **2**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 2**.
- Begründung: Ein eigener Praxisbeitrag behandelt ausdrücklich die digitale Teilhabe von Menschen mit Migrationsgeschichte anhand eines Erfahrungsberichts aus Kiel-Gaarden. Das ist ein klarer inhaltlicher Integrationsbestandteil, aber nicht das Hauptthema des gesamten Aktionstags.
- supporting_fields: `description`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "**Digitale Teilhabe von Menschen mit Migrationsgeschichte, Wolfgang Schulz (Initiative Smart Gaarden)**"
- `title`: "Digitale Teilhabe – gemeinsam vernetzt"

### 12. historical-q12 — Der (rote) Faden

- case_id: `historical-q12`
- event_id: `019f1c76-eb40-79ea-88e1-4ee976848158`
- Query: Integration und Migration
- document_hash: `5bef489c194d5e039b28c1c24848bf51dcf95dc4de0b5444cc27589031f6af65`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Der Text behandelt Rollen in Beruf, Familie und Freundeskreis sowie persönliche Identität. Migration, Flucht oder interkulturelle Integration sind nicht belegt. Soziale Rollen allein rechtfertigen keinen positiven Score.
- supporting_fields: `summary`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `summary`: "Wir alle spielen Rollen."
- `title`: "Der (rote) Faden"

### 13. historical-q14 — DenkMal!

- case_id: `historical-q14`
- event_id: `01a0b3aa-28bf-7a09-9295-6c17ab731dc5`
- Query: lokale Geschichte
- document_hash: `b63e1493b62211a3de7c3b16aeff1d9640572c58e858b98fe07c543d6abb17c9`
- Vorher kalibriert: **2**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **2 → 0**.
- Begründung: Die Führung behandelt das 19. Jahrhundert, Denkmäler und die Konstruktion von Geschichtsbildern allgemein. Keine konkrete lokale oder regionale Geschichte ist als Inhalt benannt; der Museumsstandort allein reicht nicht.
- supporting_fields: `summary`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `summary`: "Inwiefern hierüber Geschichte und Geschichtsbilder konstruiert, funktionalisiert und interpretiert werden, ist Gegenstand dieser Führung."
- `title`: "DenkMal!"

### 14. historical-q14 — Aalkreih

- case_id: `historical-q14`
- event_id: `019fa7f6-e5bd-78a2-8f48-2806521951b8`
- Query: lokale Geschichte
- document_hash: `c4e51b52b12bd4853e441a41760a532202bd4ee7915fd70b7b8fe7753137d0e4`
- Vorher kalibriert: **2**; final: **1**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **2 → 1**.
- Begründung: Die Beschreibung benennt regionale Sprache, kulturelle Wurzeln und eine thematische Verwurzelung in Nordfriesland ausdrücklich. Damit ist regionale kulturelle Identität belegt, aber keine substanzielle Vermittlung regionaler Geschichte: nur indirekter Teilbezug mit Grad 1.
- supporting_fields: `description`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Aalkreih steht für einen musikalischen Ansatz, der regionale Sprache und kulturelle Wurzeln mit einem zeitgemäßen Sound zusammenbringt."
- `description`: "Thematisch ist die Band stark in Nordfriesland verwurzelt."

### 15. historical-q14 — triaden tiraden

- case_id: `historical-q14`
- event_id: `019df20e-4efc-7c01-8c4a-8880af01f14a`
- Query: lokale Geschichte
- document_hash: `23018da2a6af58efd1c0fd7009ef732bb5a790c00a3aa6d3de7dd35f44ae4676`
- Vorher kalibriert: **1**; final: **0**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **1 → 0**.
- Begründung: Vorgestellt werden literarische und audiovisuelle Werke sowie Bibliotheksalltag. Die lokalen Künstlerbiografien und Veranstaltungsorte belegen keine lokale Geschichtsvermittlung im Programm.
- supporting_fields: `summary`, `title`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `summary`: "**Stefanie Oeding** entziffert tägliche Aufzeichnungen aus dem analogen Bibliotheksalltag."
- `title`: "triaden tiraden"

### 16. historical-q14 — Schnupperkurs Plattdeutsch

- case_id: `historical-q14`
- event_id: `01a06ade-f5ed-7571-9630-854d88fec839`
- Query: lokale Geschichte
- document_hash: `dbebcb7b512a9e7ee76a57695d8193bcb6bcded3edab9c1fc294fde2937d05fd`
- Vorher kalibriert: **2**; final: **1**.
- changed: **yes** (Scoreänderung); Maschinenscore vorher/nachher: **2 → 1**.
- Begründung: Neben ersten Sprachschritten werden ausdrücklich kulturelle Hintergründe des Plattdeutschen vermittelt. Regionaler kultureller Kontext ist belegt, historische Inhalte als wesentlicher Bestandteil jedoch nicht; daher 1 statt 2.
- supporting_fields: `description`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Gleichzeitig erfahren Sie Wissenswertes über die kulturellen Hintergründe sowie den besonderen Klang und Rhythmus des Plattdeutschen."

### 17. historical-q02 — Cultural Pearl Kulturtag

- case_id: `historical-q02`
- event_id: `019e63f7-ebeb-7952-9304-e496b02e3588`
- Query: Angebote zur kulturellen Bildung
- document_hash: `06f865310d623c6ddf897f9614d825b88651b640adb708a423153810d111d2b4`
- Vorher kalibriert: **unresolved**; final: **0**.
- changed: **yes** (neue Kalibrierungsentscheidung); Maschinenscore vorher/nachher: **0 → 0**.
- Begründung: Die vollständige Beschreibung belegt Kulturpräsentation, Begegnung und gemeinsames Erleben, aber kein konkretes Lernen oder Vermittlungsangebot. Breite Typzuordnungen wie Workshop und Rundgang allein dokumentieren keinen tatsächlich beschriebenen kulturellen Bildungsbestandteil.
- supporting_fields: `description`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Am 19. September lädt die Stadt Glücksburg zum Kulturtag Glücksburg ein. Im Mittelpunkt steht die vielfältige Glücksburger Kulturszene: Lokale Kulturakteurinnen und Kulturakteure präsentieren ihre Angebote, Projekte und Ideen an verschiedenen Orten im gesamten Stadtgebiet und machen Kultur für alle erlebbar."

### 18. historical-q03 — Deich ohne Schafe?

- case_id: `historical-q03`
- event_id: `019daf9b-da9a-7524-9b5c-0f77457ab198`
- Query: barrierefreie Veranstaltungen
- document_hash: `b57d3b66048aa42e37c446b3959971922b053cfb4411909ebee7077bba643022`
- Vorher kalibriert: **unresolved**; final: **2**.
- changed: **yes** (neue Kalibrierungsentscheidung); Maschinenscore vorher/nachher: **2 → 2**.
- Begründung: Für jeden der fünf erfassten Pilkentafel-Termine ist im jeweiligen Space-Feld ebenerdiger, stufenloser Zugang mit ausreichend breiten Türen ausdrücklich belegt. Die Sanitäranlagen sind nicht rollstuhlgerecht erreichbar. Deshalb eingeschränkte Barrierefreiheit mit Grad 2, nur für die einzeln referenzierten Occurrences.
- supporting_fields: `occurrences.0.space_accessibility`, `occurrences.1.space_accessibility`, `occurrences.2.space_accessibility`, `occurrences.3.space_accessibility`, `occurrences.4.space_accessibility`, `occurrences.0.id`, `occurrences.0.start_date`, `occurrences.0.venue`, `occurrences.0.space`, `occurrences.1.id`, `occurrences.1.start_date`, `occurrences.1.venue`, `occurrences.1.space`, `occurrences.2.id`, `occurrences.2.start_date`, `occurrences.2.venue`, `occurrences.2.space`, `occurrences.3.id`, `occurrences.3.start_date`, `occurrences.3.venue`, `occurrences.3.space`, `occurrences.4.id`, `occurrences.4.start_date`, `occurrences.4.venue`, `occurrences.4.space`
- requires_occurrence_review: `true`

Konkrete positive Occurrence-Evidenz:

- `occurrences.0`: `019dafa6-9317-7389-83d3-0added49359b`, 2026-04-23; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.1`: `019dafa6-9318-727c-b400-90fac8eb9f43`, 2026-05-01; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.2`: `019dafa6-9318-7784-925d-34bdb65a5227`, 2026-04-30; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.3`: `019dafa6-9318-7b19-8cc1-946f90de0c2b`, 2026-04-24; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.4`: `019dafa6-9319-7acf-bca7-96dcb1cb66ee`, 2026-05-02; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
Keine Übertragung auf weitere Termine oder Räume.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `occurrences.0.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.1.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.2.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.3.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.4.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."

### 19. historical-q03 — SHOWER

- case_id: `historical-q03`
- event_id: `019e2bbb-892a-7482-a463-bb1da6b27ee5`
- Query: barrierefreie Veranstaltungen
- document_hash: `d4be4181016ae2ac934bb4578580008d30b113a3139d4b5d93026ff4360ddf2c`
- Vorher kalibriert: **unresolved**; final: **2**.
- changed: **yes** (neue Kalibrierungsentscheidung); Maschinenscore vorher/nachher: **2 → 2**.
- Begründung: Für jeden der sechs erfassten Pilkentafel-Termine dokumentiert das jeweilige Space-Feld ebenerdigen, stufenlosen Zugang und ausreichend breite Türen, aber nicht rollstuhlgerecht erreichbare Sanitäranlagen. Das belegt Grad 2 für diese Occurrences, keine uneingeschränkte Barrierefreiheit.
- supporting_fields: `occurrences.0.space_accessibility`, `occurrences.1.space_accessibility`, `occurrences.2.space_accessibility`, `occurrences.3.space_accessibility`, `occurrences.4.space_accessibility`, `occurrences.5.space_accessibility`, `occurrences.0.id`, `occurrences.0.start_date`, `occurrences.0.venue`, `occurrences.0.space`, `occurrences.1.id`, `occurrences.1.start_date`, `occurrences.1.venue`, `occurrences.1.space`, `occurrences.2.id`, `occurrences.2.start_date`, `occurrences.2.venue`, `occurrences.2.space`, `occurrences.3.id`, `occurrences.3.start_date`, `occurrences.3.venue`, `occurrences.3.space`, `occurrences.4.id`, `occurrences.4.start_date`, `occurrences.4.venue`, `occurrences.4.space`, `occurrences.5.id`, `occurrences.5.start_date`, `occurrences.5.venue`, `occurrences.5.space`
- requires_occurrence_review: `true`

Konkrete positive Occurrence-Evidenz:

- `occurrences.0`: `019e2bbf-4ec9-705c-b23d-36e25d429997`, 2026-05-21; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.1`: `019e2bda-d2c4-7cd6-b2f6-2252f6030f0b`, 2026-05-22; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.2`: `019e2bda-d2c6-7262-853e-c6d520bca6ee`, 2026-05-28; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.3`: `019e2bda-d2c6-7541-bb02-0d1b147bf001`, 2026-05-23; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.4`: `019e2bda-d2c7-7478-9474-d2796c7fbbe2`, 2026-05-29; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
- `occurrences.5`: `019e2bda-d2c7-771a-b95d-3dd1b93bf12d`, 2026-05-30; venue_id `019daf99-3496-719b-a3a4-e5c7cc906cb4`, space_id `019daf9b-0e23-7ca3-ba04-2adf1043b6a5`.
Keine Übertragung auf weitere Termine oder Räume.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `occurrences.0.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.1.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.2.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.3.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.4.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."
- `occurrences.5.space_accessibility`: "Die Theaterwerkstatt Pilkentafel ist eingeschränkt barrierefrei. Der Zugang zum Foyer und in den Theatersaal sind ebenerdig und stufenlos erreichbar. Die Eingangstüren sind ausreichend breit. Die sanitären Anlagen sind leider nicht barrierefrei mit einem Rollstuhl zu erreichen. Bei Fragen oder Hilfestellungen sind wir über unsere erreichbar."

### 20. historical-q07 — Kulturtag: Glücksburger Tiny House – Kurzführung & Besichtigung

- case_id: `historical-q07`
- event_id: `01a042e9-cf5a-7252-aff4-043771488e9c`
- Query: Angebote für Kinder
- document_hash: `59accf1a2b32dd684a8b7dc820f31a7cc3958ac2052e6f09f82568b22e789205`
- Vorher kalibriert: **unresolved**; final: **0**.
- changed: **yes** (neue Kalibrierungsentscheidung); Maschinenscore vorher/nachher: **0 → 0**.
- Begründung: Kurzführung und Besichtigung erläutern nachhaltige Bau- und Wohnkultur. Kinder oder Familien sind weder im vollständigen Text noch in den strukturierten Feldern als Zielgruppe benannt. Anschauliche Vermittlung allein macht kein Kinderangebot.
- supporting_fields: `description`
- requires_occurrence_review: `false`

occurrence_ids: `[]`; keine positive occurrence-spezifische Eigenschaft behauptet.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Wie wollen wir in Zukunft wohnen? Bei einer Kurzführung durch das energieautarke Tiny House „sunny & tiny“ geht es um Bau- und Wohnkultur im Wandel: von nachhaltigen Baustoffen über erneuerbare Energien bis hin zu neuen Formen des Wohnens. Das mobile Infomobil von artefact zeigt anschaulich, wie klimafreundliches Bauen und Wohnen praktisch umgesetzt werden können."

### 21. historical-q11 — Lange Nacht der Demokratie

- case_id: `historical-q11`
- event_id: `01a06b28-2fd0-7080-93ee-c732aba7077d`
- Query: Veranstaltungen im Freien
- document_hash: `0abfd13eb392820f31697d8d4ee87f216c5128ee836ab956a30a8d78885ece27`
- Vorher kalibriert: **unresolved**; final: **0**.
- changed: **yes** (neue Kalibrierungsentscheidung); Maschinenscore vorher/nachher: **0 → 0**.
- Begründung: Das konkrete Nordkolleg-Programm nennt musikalische Beiträge und Demokratie-Tische im Pavillon. Eine Durchführung im Freien oder ein Outdoor-Teilprogramm wird nicht ausdrücklich beschrieben. Weder die landesweite Veranstaltungsreihe noch der Raumname erlauben diese Ableitung.
- supporting_fields: `description`
- requires_occurrence_review: `true`

Geprüfter Ortskontext: `occurrences.0`, `01a06b2d-c30c-7ba9-87e0-22bfd57a0003`, 2026-10-02, Nordkolleg Rendsburg / Pavillon. Kein positiver Outdoor-Beleg; `occurrence_ids` im Vorschlag bleiben leer.

Exakte Evidenzanker (Feldpfade relativ zum Snapshot-Objekt `event`):

- `description`: "Am 2. Oktober 2026 wird zum dritten Mal die »Lange Nacht der Demokratie« in Schleswig-Holstein stattfinden. Die Lange Nacht der Demokratie ermöglicht Inspiration, Begegnung sowie Reflexion zur Bedeutung von Demokratie. In der Nacht vor dem Tag der Deutschen Einheit wird in vielfältigsten Formaten über Demokratie philosophiert, diskutiert, gestritten und geslammt, Musik und Kultur genossen, gelacht und gefeiert. Die Lange Nacht begeistert zum Mitmachen für die Demokratie."

## Integrität und Validierung

Original Ground Truth, Snapshot, evidence.md und Annotation Guidelines bleiben byte-identisch; ebenso die vorhandenen Rubriken. Der Generator prüft die vier gepinnten Quellhashes. Tests fixieren alle 21 Paare und prüfen zusätzlich sämtliche 280 Kalibrierungen gegen alle vier hypothetischen Heuristik-Scores. Ein Hashvergleich sichert den Inhalt der 2331 nicht nachgeprüften Vorschläge.

Accessibility-Tests prüfen sämtliche fünf bzw. sechs Pilkentafel-Occurrences einzeln, einschließlich stufenlosem Zugang **und** nicht rollstuhlgerecht erreichbaren Sanitäranlagen. Für Reading Party gilt nur der einzelne eingefrorene Termin. Menschliche CSV-Felder bleiben leer.

Lokale Ergebnisse: `uv sync --locked --offline`, Ruff, Format und `git diff --check` erfolgreich. `uv run pytest -q`: **431 bestanden, 24 übersprungen** (Integration bzw. optionale Real-Encoder-Tests); darin **49 Annotationstests**. Lokal wurden keine DB-/Qdrant-/Encoder-Dienste verwendet. Disposable Integration und Docker sind separat im bestehenden CI-Workflow zu prüfen.

GitHub wird ausschließlich für den beauftragten PR-Status, CI, Beschreibungsupdate und Ready-Markierung verwendet. Der CI-Status des finalen Heads wird vor Ready geprüft und in der PR-Beschreibung bzw. Abschlussmeldung ausgewiesen. Dieser Report behauptet kein vorab bekanntes Remote-CI-Ergebnis.

Keine Live-Zugriffe, Deployments, DB-/Qdrant-Writes, Reindexes, Alias-Switches, Service-Restarts, Admin-/Planner-/Encoder-/Runtime-Änderungen oder semantische Aktivierung. `semantic_query=false`. Kein finales v3/v5-Benchmarking, keine Threshold-Änderung, keine menschliche Freigabe und kein Merge.
