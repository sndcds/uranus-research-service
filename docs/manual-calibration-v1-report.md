# Manual calibration v1 — PR #6 correction

Status: **calibration-policy**, weiterhin **draft / machine-proposed**. Keine menschliche Benchmark-Freigabe.

Basis: `430c1a3f23e356405ed60dc4abcca3465235e5e0`. 275 kalibrierte Paare in 14 Cases (historical-q01 bis q14).
Geänderte Scores: **65**, davon **52 Upgrades**, **13 Downgrades**; **210 unverändert**.
Verteilung 0/1/2/3 vorher: **{0: 1674, 1: 444, 2: 127, 3: 107}**; nachher: **{0: 1640, 1: 461, 2: 134, 3: 117}**.

## Architektur und Bindung

`assess()` bleibt die bisherige Heuristik. `load_manual_calibration()` validiert die separate Policy;
`apply_calibration()` ist die abschließende paarbezogene Policy-Schicht. Der Endscore wird ausschließlich
aus `expected_relevance` genommen, unabhängig vom heuristischen Score. Die Policy gilt nicht automatisch
für Übersetzungen oder q15+. Dort bleiben Vorschläge unverändert und alle Grade 3 prioritär reviewpflichtig.

Kalibrierungsdatei: [manual-calibration-v1.json](../benchmark/annotation/manual-calibration-v1.json), SHA256 `f0f72a735987fafdc12031ba1e19808b29e4f0babb1e851c6379fd0fd5df8ab8`.
Jede angewandte Policy ist im Proposal durch Version, Hash und `calibration_applied` gebunden.

Resolution verwendet exakten Snapshot-Titel und Case-Kandidatenmitgliedschaft. Die vom Auftrag gekürzten
Titel sind in der Datei als exakte Snapshot-Titel gespeichert: Oktoberfest einschließlich Emojis, ORDRIG
mit Untertitel Sønderjyllands Bogfest, BAM mit TachoTinta sowie GRIND / ANDERS mit den Beteiligten.
Die beiden gleichnamigen Demokratie-Nächte in q04 werden durch die ausdrücklich vorgegebenen Städte
Husby/Rendsburg unterschieden. Die ausdrücklich für **alle** Seniorennachmittage gegebenen q08/q09-Regeln
expandieren auf sämtliche exakten Titelkandidaten und speichern jeweils die eindeutige Snapshot-UUID.
Unaufgelöste Titelmehrdeutigkeiten: **0**. Ohne eindeutige Resolution stoppt der Loader.

## Alle Änderungen mit Beteiligung von Grad 3

| Case | Event (UUID) | Vorher | Kalibriert |
| --- | --- | ---: | ---: |
| historical-q01 | Punk meets Metal (`019f07bc-6405-7969-9413-34f2e19f4d02`) | 1 | 3 |
| historical-q01 | Deniz & Ove (`019f17e8-61d1-7cc6-b5a0-b79013a7c6b6`) | 1 | 3 |
| historical-q01 | DLRG Strandfest (`019f21e0-09f2-7117-a1e2-09a05763485d`) | 1 | 3 |
| historical-q02 | Kulturh(a)us Utopia (`019da011-1802-7924-8a24-821066242bba`) | 3 | 2 |
| historical-q02 | K26 Kulturtræf (`019dce5e-3d70-7e44-9f1e-d59ab4013fd6`) | 3 | 2 |
| historical-q02 | HOFkulTOUR 2026 (`019f16f0-7bc7-796c-abee-a299672e1fb4`) | 0 | 3 |
| historical-q04 | Circus Ubuntu (`019e00e2-c2d9-7717-8d5f-f79f870e81cb`) | 0 | 3 |
| historical-q06 | Faires Frühstück: "Ausgezeichnet" essen in netter Runde (`01a0c997-26d8-72e7-985f-dc4318bb8b7a`) | 2 | 3 |
| historical-q06 | Filmische Perspektiven auf Fairness (`01a02003-c5f1-718f-b656-0802c3a122c5`) | 3 | 2 |
| historical-q07 | Maskenball der Tiere (`019e55b1-f420-790b-8390-3c563cce6612`) | 2 | 3 |
| historical-q09 | Tag des offenen Denkmals 2026 (`019fef40-7688-7bbe-997b-e7242c966554`) | 0 | 3 |
| historical-q11 | NORDEN – The Nordic Arts Festival (`01a0c8fb-4bbe-75e8-9d61-0c380229b121`) | 0 | 3 |
| historical-q11 | Sommer im Garten (`019e6382-ca19-7f89-90e4-13b5ba2c4cd2`) | 0 | 3 |
| historical-q11 | ORDRIG (`019e5e75-be89-78b2-b574-cf5f9fa4b090`) | 0 | 3 |
| historical-q12 | Medeamaterial (`019e1312-0f42-701e-86fe-f2bfb10093f8`) | 2 | 3 |
| historical-q14 | ORDRIG (`019e5e75-be89-78b2-b574-cf5f9fa4b090`) | 2 | 3 |

## Kalibrierung/Evidenz-Konflikte

**16** Konflikte werden ausdrücklich markiert; der kalibrierte Score bleibt erhalten.
Ein tatsächliches öffentliches Zitat belegt hier den beschriebenen Sachverhalt, nicht zwingend den
vollen kalibrierten Relevanzgrad. Der Konflikttext nennt die fehlende oder stärkere Eigenschaft ausdrücklich.
Es werden keine fehlenden Eigenschaften in Zitate hineingelesen. Alle kalibrierten Grade 3 besitzen
konkrete Evidenz und High Confidence; keiner dieser Grade-3-Fälle steht auf der Konfliktliste.

| Case | Event | Konflikt |
| --- | --- | --- |
| historical-q03 | Reading Party "Let's Get Cosy" | Öffentlicher Text nennt barrierearmen Zugang plus barrierefreie Toilette; könnte stärker als Grad 1 gewertet werden. Kalibrierung bleibt 1. |
| historical-q05 | La.tina | Programm nennt ausdrücklich QUECHUA SPRACHKURS; Kalibrierung bleibt trotzdem 0. |
| historical-q06 | Parkfest im Christiansenpark | Botanischer Rundgang und historische Handwerke belegt; ausdrücklicher Nachhaltigkeitsbezug fehlt. |
| historical-q06 | Liquid Bodies | Wasser/Fürsorge sind belegt, Nachhaltigkeit nicht ausdrücklich. Kalibrierter Teilbezug 1 bleibt erhalten. |
| historical-q07 | Cultural Pearl Kulturtag | Kultur für alle, aber keine ausdrücklich genannte Kinderzielgruppe im Snapshot. |
| historical-q07 | Skandaløs Festival | Allgemeines Festivalprogramm, aber kein ausdrücklicher Kinderbezug im erfassten Text. |
| historical-q07 | KulturRotation 143 | Offenes allgemeines Kulturangebot; Kinderzielgruppe nicht ausdrücklich belegt. |
| historical-q08 | Disco für alle | Inklusion/Behinderung ist belegt, Seniorenbezug nicht ausdrücklich. |
| historical-q08 | Gesteins- und Fossiliensprechstunde | Allgemeine offene Sprechstunde; Seniorenbezug nicht ausdrücklich belegt. |
| historical-q08 | DI.DAY | Allgemeine Kurse für Erwachsene erwähnt, kein ausdrücklicher Seniorenbezug des konkreten Termins. |
| historical-q12 | Digitale Teilhabe – gemeinsam vernetzt | Ein eigener Programmbeitrag nennt digitale Teilhabe von Menschen mit Migrationsgeschichte; könnte stärker als 1 bewertet werden. |
| historical-q12 | Der (rote) Faden | Soziale Rollen/Familie belegt, Migration bzw. interkulturelle Teilhabe nicht ausdrücklich. |
| historical-q14 | DenkMal! | Allgemeine Denkmal-/Geschichtsvermittlung belegt, konkrete lokale Geschichte nicht ausdrücklich. |
| historical-q14 | Aalkreih | Regionale Sprache/kulturelle Wurzeln belegt, historische Vermittlung nicht explizit; Policy hält 2 fest. |
| historical-q14 | triaden tiraden | Lokaler Bibliotheksalltag und regionale Biografien belegt, kein klarer geschichtlicher Programminhalt. |
| historical-q14 | Schnupperkurs Plattdeutsch | Plattdeutsche Sprache und kulturelle Hintergründe belegt, explizite Geschichtsvermittlung nicht zugesichert. |

## Offene Policy-Paare — kein Score erzwungen

Diese Fälle sind keine Titelmehrdeutigkeiten. Für sie fehlt im Auftrag ein eindeutiger Score;
bestehende Maschinenvorschläge bleiben bestehen, mit Low Confidence und obligatorischem Review.

- `historical-q02` / `019e63f7-ebeb-7952-9304-e496b02e3588` — Cultural Pearl Kulturtag: Explizit manuelle Prüfung angefordert; kein Kalibrierungsscore vorgegeben.
- `historical-q03` / `019daf9b-da9a-7524-9b5c-0f77457ab198` — Deich ohne Schafe?: Positive Pilkentafel-Zugangsevidenz vorhanden, aber Paar nicht in der positiven Kalibrierungsliste; Null-Regel für fehlende Evidenz nicht anwendbar.
- `historical-q03` / `019e2bbb-892a-7482-a463-bb1da6b27ee5` — SHOWER: Positive Pilkentafel-Zugangsevidenz vorhanden, aber Paar nicht in der positiven Kalibrierungsliste; Null-Regel für fehlende Evidenz nicht anwendbar.
- `historical-q07` / `01a042e9-cf5a-7252-aff4-043771488e9c` — Kulturtag: Glücksburger Tiny House – Kurzführung & Besichtigung: In der vollständigen expliziten Bewertungsaufzählung nicht enthalten.
- `historical-q11` / `01a06b28-2fd0-7080-93ee-c732aba7077d` — Lange Nacht der Demokratie: In der expliziten Bewertungsaufzählung nicht enthalten.

## Alle kalibrierten Paare

| Case | Event (UUID) | Vorher | Kalibriert |
| --- | --- | ---: | ---: |
| historical-q01 | Faire Woche 2026 Flensburg (`01a0201f-5f06-7983-9497-62b4745a36a4`) | 2 | 1 |
| historical-q01 | Duo Berlinskaya/Ancelle (`019e7d56-e0af-7e67-a4a0-a11de03b3b22`) | 0 | 0 |
| historical-q01 | Lange Nacht der Demokratie (`01a06b28-2fd0-7080-93ee-c732aba7077d`) | 1 | 1 |
| historical-q01 | Ein Riss ist auch ein Anfang – Vernissage (`019fe7de-0270-7c90-82f8-3ece25b10c36`) | 1 | 1 |
| historical-q01 | Spielplatztreff Wetterfrösche (`019ed164-56e8-7e64-96d5-b38d9e9a912c`) | 3 | 3 |
| historical-q01 | Punk meets Metal (`019f07bc-6405-7969-9413-34f2e19f4d02`) | 1 | 3 |
| historical-q01 | Anna Depenbusch & Kaiser Quartett (`019f172f-a2ce-739c-a0b5-70c9ea2a68dd`) | 0 | 0 |
| historical-q01 | Carls Reise (`01a06bcf-49b9-791e-8efe-371e96c0d2c3`) | 1 | 1 |
| historical-q01 | Electronic Movement (`01a05e11-54dd-7132-9fa1-93b61b7d86db`) | 0 | 0 |
| historical-q01 | Kreativ im Skizzenbuch - Achtsames Zeichnen (`01a01952-9d9c-762e-afd0-86a2c38c40af`) | 0 | 0 |
| historical-q01 | Open Stage Night Vol 2 (`019edfce-97fd-7c57-ac8e-9b79bb8c6095`) | 1 | 1 |
| historical-q01 | Colour Haze (`019fb249-fd92-73b6-ac35-861c5b8b4bdf`) | 0 | 0 |
| historical-q01 | Zwergentreff (`019eb683-7f8b-79bc-b8da-aa956ed6b03c`) | 0 | 1 |
| historical-q01 | Outdoor Workshop (`019fe1bf-f903-75aa-8867-4e0607f730ae`) | 0 | 0 |
| historical-q01 | DI.DAY (`019ddd54-2a60-76c7-8ccb-8d67862e6c95`) | 1 | 1 |
| historical-q01 | Parkfest im Christiansenpark (`019eba56-fe7d-79dc-9683-d2eac4ebb2f1`) | 1 | 2 |
| historical-q01 | Kulturnacht Flensburg 27 (`019db01b-f059-743c-8a3e-802545d8ed5b`) | 1 | 1 |
| historical-q01 | Deniz & Ove (`019f17e8-61d1-7cc6-b5a0-b79013a7c6b6`) | 1 | 3 |
| historical-q01 | Du, ich, wir! (`019e5590-85ea-7912-b1bc-294a2950d78e`) | 0 | 1 |
| historical-q01 | DLRG Strandfest (`019f21e0-09f2-7117-a1e2-09a05763485d`) | 1 | 3 |
| historical-q02 | Kulturh(a)us Utopia (`019da011-1802-7924-8a24-821066242bba`) | 3 | 2 |
| historical-q02 | Antonio Andrade Trio (`019fa309-ec43-77ef-bb9e-a54c2bd018dc`) | 0 | 0 |
| historical-q02 | Einladung ins Gartencafé (`019fefb8-5fd5-7937-958d-7cc125d60f74`) | 0 | 0 |
| historical-q02 | Veredeln statt Verschwenden (`01a05c25-eda0-7271-a363-bd05c959f5ef`) | 2 | 0 |
| historical-q02 | La.tina (`019e6df1-b798-7db1-bd65-ca7bd04e91bc`) | 2 | 2 |
| historical-q02 | Konzert Wohnzimmerchor (`01a0193a-4873-7e68-ab0f-5c3341296424`) | 0 | 0 |
| historical-q02 | Summerfeeling mit Lavinia Luna (`019e3745-12a7-7b13-ae12-76a3e9d728ec`) | 0 | 0 |
| historical-q02 | Digitale Teilhabe – gemeinsam vernetzt (`019db91a-89d5-7c5a-90ae-7596e488a1eb`) | 2 | 0 |
| historical-q02 | Jahresausstellung Einblick / Ausblick (`019f6e88-ed03-743b-9166-a4de613a09f4`) | 0 | 2 |
| historical-q02 | Kulturnacht Flensburg 27 (`019db01b-f059-743c-8a3e-802545d8ed5b`) | 0 | 0 |
| historical-q02 | KuRD 2026 (`019dd89e-f434-7cbd-bc59-60d3c7bda536`) | 2 | 2 |
| historical-q02 | KulturRotation 143 (`019e262e-5660-76c8-93cc-c7736848b4d3`) | 0 | 0 |
| historical-q02 | K26 Kulturtræf (`019dce5e-3d70-7e44-9f1e-d59ab4013fd6`) | 3 | 2 |
| historical-q02 | Schule trifft Kultur: Kulturelle Bildung in der Region Rendsburg stärken (`01a00ef9-aa7e-7d6e-b7d6-ca7fb23d0b1e`) | 3 | 3 |
| historical-q02 | DADA heute! (`019dab32-3e27-7f90-86f0-61f249ef3320`) | 0 | 0 |
| historical-q02 | Sommerhygge (`019daa5f-1b98-70fc-aaba-45c5fa4a8aa2`) | 1 | 0 |
| historical-q02 | Urbane Klangwelten (`019ddabc-ebea-7a24-acb1-06eedc2373ac`) | 0 | 0 |
| historical-q02 | MOSAIK Themen-Treffen (`01a01e94-3034-7d8b-8e1b-e26c0b926d25`) | 0 | 1 |
| historical-q02 | HOFkulTOUR 2026 (`019f16f0-7bc7-796c-abee-a299672e1fb4`) | 0 | 3 |
| historical-q03 | Silent Disco (`019f1767-6e7e-7183-b14c-14f2f635eafc`) | 0 | 0 |
| historical-q03 | Schachtreff Flensburg (`019eb717-3e02-713f-aa20-280ea93ff69f`) | 0 | 0 |
| historical-q03 | triaden tiraden (`019df20e-4efc-7c01-8c4a-8880af01f14a`) | 2 | 1 |
| historical-q03 | Katzen-Kratz-Traum (`019dafca-d731-7476-8e4c-49231d67e882`) | 2 | 2 |
| historical-q03 | Scheersberg Music Night (`01a07758-c058-778a-9dc1-0a06d0512382`) | 0 | 0 |
| historical-q03 | Das blaue kaninchen öffnet seine Türen! (`019f642a-6008-797e-8ac8-d09b77deddc9`) | 0 | 0 |
| historical-q03 | No Challenge No Chance (`019daf89-1621-7a82-95c3-e9b485c6483d`) | 0 | 0 |
| historical-q03 | Angora Club & Knietenbrink & Cosmo Thunder (`019db542-ea38-7270-8561-9315abdf2307`) | 0 | 0 |
| historical-q03 | Kulturnacht Flensburg 27 (`019db01b-f059-743c-8a3e-802545d8ed5b`) | 0 | 0 |
| historical-q03 | Lange Nacht der Demokratie (`01a06b28-2fd0-7080-93ee-c732aba7077d`) | 0 | 0 |
| historical-q03 | Ein Riss ist auch ein Anfang – Vernissage (`019fe7de-0270-7c90-82f8-3ece25b10c36`) | 0 | 0 |
| historical-q03 | Cultural Pearl Kulturtag (`019e63f7-ebeb-7952-9304-e496b02e3588`) | 0 | 0 |
| historical-q03 | Konzert vom JugO und dem Miniorchester (`019e6e14-3709-7c21-acfc-74e3ee09bff8`) | 0 | 0 |
| historical-q03 | La.tina (`019e6df1-b798-7db1-bd65-ca7bd04e91bc`) | 0 | 0 |
| historical-q03 | Take Care & Stay Safe (`019eac66-4cca-7934-aeae-1dfcf2b5990d`) | 2 | 2 |
| historical-q03 | Die kleine Hausapotheke (`019f9a1c-4f5d-74fd-ae85-7b347a278631`) | 0 | 0 |
| historical-q03 | Reading Party "Let's Get Cosy" (`01a0c369-117f-7172-aed1-c50b052af59d`) | 0 | 1 |
| historical-q03 | Liquid Bodies (`019e84a4-d625-79fa-99f6-ca653015e6e1`) | 2 | 2 |
| historical-q04 | Gemeinsam Schach (`019daaf4-ec73-785c-9b93-fdef83ecc9f2`) | 0 | 0 |
| historical-q04 | Faire Woche 2026 Flensburg (`01a0201f-5f06-7983-9497-62b4745a36a4`) | 2 | 2 |
| historical-q04 | Lange Nacht der Demokratie (`01a06c08-e652-7f4e-a471-a6c0a712f7fa`) | 2 | 2 |
| historical-q04 | Oktoberfest mit Livemusik vom Geestland Trio 🍻🎶 (`01a018be-3c48-7292-a0a4-90ce7ea90fb3`) | 3 | 3 |
| historical-q04 | K26 Kulturtræf (`019dce5e-3d70-7e44-9f1e-d59ab4013fd6`) | 3 | 3 |
| historical-q04 | Rezwan Taha (`019dbeac-5d56-712f-a734-6f5e0c5a471a`) | 0 | 0 |
| historical-q04 | Digitale Teilhabe – gemeinsam vernetzt (`019db91a-89d5-7c5a-90ae-7596e488a1eb`) | 0 | 0 |
| historical-q04 | Trüffelmenü (`01a06a00-bea4-7380-bd52-3c7cbf30c753`) | 0 | 0 |
| historical-q04 | Lange Nacht der Demokratie (`01a06b28-2fd0-7080-93ee-c732aba7077d`) | 0 | 0 |
| historical-q04 | Circus Ubuntu (`019e00e2-c2d9-7717-8d5f-f79f870e81cb`) | 0 | 3 |
| historical-q04 | Du, ich, wir! (`019e5590-85ea-7912-b1bc-294a2950d78e`) | 0 | 0 |
| historical-q04 | Electronic Movement (`01a05e11-54dd-7132-9fa1-93b61b7d86db`) | 0 | 0 |
| historical-q04 | Friday Night mit Jan & Jan (`019f54d1-f5cd-7b50-831c-c9be1f6370af`) | 0 | 0 |
| historical-q04 | Memokratie. Soziale Medien und autoritäre Bildpolitik - Wolfgang Ullrich (`01a05cdc-aaf1-741c-8f01-0b8b1dbe2c82`) | 0 | 0 |
| historical-q04 | Kulturnacht Flensburg 27 (`019db01b-f059-743c-8a3e-802545d8ed5b`) | 0 | 0 |
| historical-q04 | Maskenball der Tiere (`019e55b1-f420-790b-8390-3c563cce6612`) | 0 | 0 |
| historical-q04 | Das blaue kaninchen öffnet seine Türen! (`019f642a-6008-797e-8ac8-d09b77deddc9`) | 0 | 0 |
| historical-q04 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019feff6-d7b3-74d1-af77-0358d6808104`) | 0 | 0 |
| historical-q04 | Die Riesin und ihr Topf (`019e5584-a0b8-7c8d-be46-4a364449c464`) | 0 | 0 |
| historical-q04 | Silent Disco (`019f1767-6e7e-7183-b14c-14f2f635eafc`) | 0 | 0 |
| historical-q05 | Alawari (`019e4eca-5346-7956-8365-e8d68f56068e`) | 0 | 0 |
| historical-q05 | 1. Bundessiegerkonzert Duo Pianoforte Klavier vierhändig (`019da5ae-5d78-7d0b-a4e5-5bf7e818a886`) | 0 | 0 |
| historical-q05 | IZHAV (S) (`01a07c26-8f40-70bc-ac84-7347d066867f`) | 0 | 0 |
| historical-q05 | Woord un Klang - en plattdüütschen Ovend (`01a06af6-9901-7ecf-aea9-0192a65a3a83`) | 0 | 0 |
| historical-q05 | Kulturh(a)us Utopia (`019da011-1802-7924-8a24-821066242bba`) | 0 | 0 |
| historical-q05 | Ralph Turnheim (`019f1751-496e-7e7d-8f52-7737d4f6c2fe`) | 0 | 0 |
| historical-q05 | Communitytreffen (`019d5f3a-de7e-780a-9fa0-dc24e5545e2e`) | 0 | 0 |
| historical-q05 | Keyo Roses Flying Circus & Krachym (`019e4022-4f8d-72c6-9f8f-00ec7cc065dd`) | 0 | 0 |
| historical-q05 | Max Goldt (`019da550-26e2-7b03-96c0-b421d56a5c9a`) | 0 | 0 |
| historical-q05 | Pappelapapp (`019da5da-2b04-7ab2-8d2f-3f9856ebf2b1`) | 0 | 0 |
| historical-q05 | Sonntags Signale (`019d73fb-0e46-78f0-9287-04037cea026e`) | 0 | 0 |
| historical-q05 | Speed-Dating - Kultur trifft Politik (`019eb719-75cb-749e-be9c-fab9c5b5636f`) | 0 | 0 |
| historical-q05 | Die kleine Hausapotheke (`019f9a1c-4f5d-74fd-ae85-7b347a278631`) | 0 | 0 |
| historical-q05 | La.tina (`019e6df1-b798-7db1-bd65-ca7bd04e91bc`) | 0 | 0 |
| historical-q05 | Russisch lernen (`019fe1dc-d55d-7fb4-96ff-5bd5c1441978`) | 2 | 2 |
| historical-q05 | Träumer und Genies (`019e7d92-523d-7302-a74d-3b0d96f74a66`) | 0 | 0 |
| historical-q05 | Circus Ubuntu (`019e00e2-c2d9-7717-8d5f-f79f870e81cb`) | 0 | 0 |
| historical-q05 | Gangar (N) (`019da560-7ee8-7bdf-82ac-3441a39057ef`) | 0 | 0 |
| historical-q05 | Dänisch für Anfänger (`019fe1f8-79fa-7ccf-af26-935c68985969`) | 3 | 3 |
| historical-q05 | Dänisch für leicht Fortgeschrittene (`019fe206-af8d-7f3a-acf8-f8d4650642c6`) | 3 | 3 |
| historical-q06 | Klimapark (`019ed180-c4b5-7e7c-8bb2-04fc477659a5`) | 3 | 3 |
| historical-q06 | Tag der Städtebauförderung (`019dd805-5eef-7120-afba-14e688b30b50`) | 0 | 1 |
| historical-q06 | Parkfest im Christiansenpark (`019eba56-fe7d-79dc-9683-d2eac4ebb2f1`) | 0 | 1 |
| historical-q06 | Faire Woche 2026 Flensburg (`01a0201f-5f06-7983-9497-62b4745a36a4`) | 3 | 3 |
| historical-q06 | Veredeln statt Verschwenden (`01a05c25-eda0-7271-a363-bd05c959f5ef`) | 3 | 3 |
| historical-q06 | De Steensöker (`01a0f046-5be9-73d7-a7be-c9d0941348ad`) | 0 | 0 |
| historical-q06 | Power-Rallye im Energie-Erlebnis-Park (`019ed94d-1e74-7214-bc66-6437c25cab37`) | 3 | 3 |
| historical-q06 | Filmvorführung: Verwundene Fäden (`019eb5e3-5e29-72dc-8cac-3fcbceb3307b`) | 0 | 0 |
| historical-q06 | Faires Frühstück: "Ausgezeichnet" essen in netter Runde (`01a0c997-26d8-72e7-985f-dc4318bb8b7a`) | 2 | 3 |
| historical-q06 | Nachhaltigkeitsmarkt (`019ed93e-2d76-7731-b228-371aa3b00009`) | 3 | 3 |
| historical-q06 | Wo soll das alles hin? (`019dc61d-7b39-789e-a72b-60233be76b85`) | 3 | 3 |
| historical-q06 | Filmische Perspektiven auf Fairness (`01a02003-c5f1-718f-b656-0802c3a122c5`) | 3 | 2 |
| historical-q06 | Flensburger Kurzfilmstreifzug (`019e4137-be25-77b3-9d3b-4661b547e1ba`) | 0 | 0 |
| historical-q06 | 1. Bundessiegerkonzert Duo Pianoforte Klavier vierhändig (`019da5ae-5d78-7d0b-a4e5-5bf7e818a886`) | 0 | 0 |
| historical-q06 | Liquid Bodies (`019e84a4-d625-79fa-99f6-ca653015e6e1`) | 0 | 1 |
| historical-q06 | Kreativ im Skizzenbuch - Malen zur Entspannung (`01a019af-9251-780c-9c4a-b1e7d40b88eb`) | 0 | 0 |
| historical-q06 | Gemeinschaftliches Hoffnungssingen mit Patrick Zinndorf (`01a0c98b-dcfd-7a9b-8649-a9177071023e`) | 0 | 0 |
| historical-q06 | Recorder Recorder / ZOOK (`019dcafe-0b23-7751-981b-92400d38d2c9`) | 0 | 0 |
| historical-q06 | Lange Nacht der Demokratie (`01a06b28-2fd0-7080-93ee-c732aba7077d`) | 0 | 0 |
| historical-q06 | Nadejda Vlaeva (`019e7d8b-c6a6-7852-b11c-96e6de46d5ae`) | 0 | 0 |
| historical-q07 | Geschichtenzirkus (`019e742f-7543-7ec1-bcdb-28e3d8124600`) | 3 | 3 |
| historical-q07 | Jonglierworkshop (`019e1574-ab7e-70a9-804b-28c513a1b141`) | 0 | 1 |
| historical-q07 | Du, ich, wir! (`019e5590-85ea-7912-b1bc-294a2950d78e`) | 3 | 3 |
| historical-q07 | Cultural Pearl Kulturtag (`019e63f7-ebeb-7952-9304-e496b02e3588`) | 0 | 1 |
| historical-q07 | Knallwut (`019e034e-dbcf-7a5f-b77e-17d4866f0e2d`) | 3 | 3 |
| historical-q07 | Silvestergala (`01a069ed-7ebe-7987-b7cf-f900854d7b49`) | 0 | 0 |
| historical-q07 | Skandaløs Festival (`019daf20-38e6-7283-9746-c604f6523e33`) | 0 | 1 |
| historical-q07 | Where The Waves Took Her (`019f51e0-900d-71f9-bbef-6f0ec884fc13`) | 0 | 0 |
| historical-q07 | Spieletreff (`019daafb-5a19-7560-8dea-c1104a05fc2b`) | 2 | 2 |
| historical-q07 | Förde Vibes mit Lucie Glang (`019e1dce-5351-7ee6-85b9-fc262bf42e59`) | 0 | 0 |
| historical-q07 | Circus Ubuntu (`019e00e2-c2d9-7717-8d5f-f79f870e81cb`) | 0 | 2 |
| historical-q07 | Parkfest im Christiansenpark (`019eba56-fe7d-79dc-9683-d2eac4ebb2f1`) | 0 | 2 |
| historical-q07 | Kinderatelier (`01a0a8e7-94ad-7c44-9fcc-d782a8c28ede`) | 3 | 3 |
| historical-q07 | KulturRotation 143 (`019e262e-5660-76c8-93cc-c7736848b4d3`) | 0 | 1 |
| historical-q07 | Mittwochsdisco (`019e4012-88b5-7213-904a-654dd9f1bb42`) | 0 | 0 |
| historical-q07 | Julius Fischer (`019f17df-e1c2-7f4d-88a8-bfc1816d9711`) | 0 | 0 |
| historical-q07 | Pfoten hoch! (`019e55cc-5709-7978-b35b-6ae037bee9ff`) | 3 | 3 |
| historical-q07 | WILD LIGHTS (`01a0d253-65c0-7e84-b05b-95474577a274`) | 2 | 2 |
| historical-q07 | Maskenball der Tiere (`019e55b1-f420-790b-8390-3c563cce6612`) | 2 | 3 |
| historical-q08 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019fefd9-0306-7639-ae29-c9cc196e1720`) | 3 | 3 |
| historical-q08 | Lange Nacht der Demokratie (`01a06b28-2fd0-7080-93ee-c732aba7077d`) | 0 | 0 |
| historical-q08 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019fefdb-e8a2-781a-af3a-9e7a5a44674e`) | 3 | 3 |
| historical-q08 | Ein Riss ist auch ein Anfang – Vernissage (`019fe7de-0270-7c90-82f8-3ece25b10c36`) | 0 | 0 |
| historical-q08 | Electronic Movement (`01a05e11-54dd-7132-9fa1-93b61b7d86db`) | 0 | 0 |
| historical-q08 | Tanzabend mit „2 Beat’s“ in der Schloßsee Senioren Residenz (`01a0189b-1103-714a-b36a-71412c1291f5`) | 0 | 2 |
| historical-q08 | Faire Woche 2026 Flensburg (`01a0201f-5f06-7983-9497-62b4745a36a4`) | 0 | 0 |
| historical-q08 | folkBALTICA Herbstkonzert im Slesvighus (`01a08f5e-a50b-7f81-83d4-f328ba124429`) | 0 | 0 |
| historical-q08 | Space Tour (`019e3ca8-3698-7f00-822d-7233ebe257d9`) | 0 | 0 |
| historical-q08 | Chaos Comedy Club (`019db8ff-3bb0-789b-a21f-c5d810fdfb01`) | 0 | 0 |
| historical-q08 | Disco für alle (`01a05c60-d7d5-7197-84da-a18469bce542`) | 0 | 1 |
| historical-q08 | Seniorenbeirat, 6. Sitzung (`019e6367-8acf-7911-9a21-fa3b34e1f389`) | 1 | 1 |
| historical-q08 | Oktoberfest mit Livemusik vom Geestland Trio 🍻🎶 (`01a018be-3c48-7292-a0a4-90ce7ea90fb3`) | 0 | 2 |
| historical-q08 | Gesteins- und Fossiliensprechstunde (`01a0f032-2002-72db-8819-57013c0b40b8`) | 0 | 1 |
| historical-q08 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019fefcb-f888-7db1-94c7-4a8780f67e8f`) | 3 | 3 |
| historical-q08 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019feff3-23c3-7f80-902d-4793d56d6934`) | 3 | 3 |
| historical-q08 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019feffb-1e38-7aac-8b56-d5bb841bd67f`) | 3 | 3 |
| historical-q08 | DI.DAY (`019ddd54-2a60-76c7-8ccb-8d67862e6c95`) | 0 | 1 |
| historical-q08 | Herbstzauber im Garten & Tag der offenen Tür unserer neuen ambulanten Tagespflege (`019ff029-2694-7bc6-ab86-d114c4b215a0`) | 1 | 2 |
| historical-q08 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019feff6-d7b3-74d1-af77-0358d6808104`) | 3 | 3 |
| historical-q09 | Tag der Städtebauförderung (`019dd805-5eef-7120-afba-14e688b30b50`) | 2 | 2 |
| historical-q09 | Gemeinsam schmeckt’s besser (`019fb7fc-ab4b-7a13-a9a9-7ed69dd80fa1`) | 1 | 1 |
| historical-q09 | Tag des offenen Denkmals 2026 (`019fef40-7688-7bbe-997b-e7242c966554`) | 0 | 3 |
| historical-q09 | Faire Woche 2026 Flensburg (`01a0201f-5f06-7983-9497-62b4745a36a4`) | 2 | 2 |
| historical-q09 | 2. Sinfoniekonzert (`01a0ee22-95a8-7f8e-a4a0-721333e64829`) | 0 | 0 |
| historical-q09 | Das blaue kaninchen öffnet seine Türen! (`019f642a-6008-797e-8ac8-d09b77deddc9`) | 0 | 1 |
| historical-q09 | Traditionelle Pastaparty (`019ef9a4-5e67-7ec1-8ba4-c72866ecdbc6`) | 0 | 0 |
| historical-q09 | Spielplatztreff Wetterfrösche (`019ed164-56e8-7e64-96d5-b38d9e9a912c`) | 1 | 1 |
| historical-q09 | Electronic Movement (`01a05e11-54dd-7132-9fa1-93b61b7d86db`) | 0 | 0 |
| historical-q09 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019fefdb-e8a2-781a-af3a-9e7a5a44674e`) | 1 | 0 |
| historical-q09 | Friday Night (`019dd821-057f-7f3a-a781-28ee9fc44bf3`) | 0 | 0 |
| historical-q09 | Lange Nacht der Demokratie (`01a06b28-2fd0-7080-93ee-c732aba7077d`) | 0 | 0 |
| historical-q09 | Kulturnacht Flensburg 27 (`019db01b-f059-743c-8a3e-802545d8ed5b`) | 0 | 0 |
| historical-q09 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019fefd5-329c-7251-9bd9-2f491ac6918c`) | 1 | 0 |
| historical-q09 | Flensburger Kurzfilmstreifzug (`019e4137-be25-77b3-9d3b-4661b547e1ba`) | 0 | 1 |
| historical-q09 | Offene Redaktion (`019dab14-b605-723f-aba8-54d6bfba859b`) | 1 | 0 |
| historical-q09 | Stefanie Boltz (`019f173e-8e40-701f-beb0-bdb07bec3440`) | 0 | 0 |
| historical-q09 | Seniorennachmittag - "Einfach mal raus: Treffen, reden, lachen" - Herzliche Einladung! (`019feff6-d7b3-74d1-af77-0358d6808104`) | 1 | 0 |
| historical-q09 | K26 Kulturtræf (`019dce5e-3d70-7e44-9f1e-d59ab4013fd6`) | 0 | 1 |
| historical-q09 | Stoppok: RUND-Reise - Die Solo-Tour 2026 (`019fb26a-089a-7f1e-a4c6-9c01a61fa3a2`) | 0 | 0 |
| historical-q10 | Lange Nacht der Demokratie: In welcher Welt willst Du leben? (`01a0c875-4812-728c-8c4b-de622c76de06`) | 0 | 0 |
| historical-q10 | Summerfeeling mit Norma & Friends (`019e3733-cc8e-7b5a-9d69-8fa18d9b53a4`) | 0 | 0 |
| historical-q10 | Summerfeeling mit Rasmus Hoffmeister (`019e371e-6ccc-71f9-93c6-05ee70f5cdc9`) | 0 | 0 |
| historical-q10 | Bohren und der Club of Gore (`019daf44-f841-7694-bee2-c5f2fa02d0e2`) | 2 | 2 |
| historical-q10 | Summerfeeling mit Paul Eastham (`019e373e-1b30-7538-a8a1-721bb0d554f4`) | 0 | 0 |
| historical-q10 | Sonntagslunch à la chef (`019ed14a-0b5c-7108-ad22-131f8863cb19`) | 0 | 0 |
| historical-q10 | Angora Club & Knietenbrink & Cosmo Thunder (`019db542-ea38-7270-8561-9315abdf2307`) | 0 | 0 |
| historical-q10 | Rumregatta (`019daa4c-cdfc-7895-8c03-855852da0ed5`) | 0 | 0 |
| historical-q10 | SVIN (`019dcb28-a464-74bd-bd67-0fdfdfdb03a6`) | 0 | 0 |
| historical-q10 | Summerfeeling mit Lavinia Luna (`019e3745-12a7-7b13-ae12-76a3e9d728ec`) | 0 | 0 |
| historical-q10 | Kulturh(a)us Utopia (`019da011-1802-7924-8a24-821066242bba`) | 0 | 0 |
| historical-q10 | Lange Nacht der Demokratie (`01a06b28-2fd0-7080-93ee-c732aba7077d`) | 0 | 0 |
| historical-q10 | "Was uns wirklich glücklich macht" (`019edfae-073e-7daf-a62b-c3ba12203082`) | 0 | 0 |
| historical-q10 | Kulturnacht Flensburg 27 (`019db01b-f059-743c-8a3e-802545d8ed5b`) | 0 | 0 |
| historical-q10 | Husum Ahoi! Nr. 5 (`019fad3e-baec-74ad-844a-a475316c55ee`) | 0 | 0 |
| historical-q10 | Faire Woche 2026 Flensburg (`01a0201f-5f06-7983-9497-62b4745a36a4`) | 0 | 0 |
| historical-q10 | Tanzabend mit „2 Beat’s“ in der Schloßsee Senioren Residenz (`01a0189b-1103-714a-b36a-71412c1291f5`) | 0 | 0 |
| historical-q10 | Titanic Boygroup (`019fdc72-178f-78a8-af98-beab7f78d991`) | 0 | 0 |
| historical-q10 | European Future Talks (`019dc9c4-0c91-7d53-932d-1a1a3cda1d4d`) | 0 | 0 |
| historical-q10 | Innere Gefährten (`019dbded-ece7-783d-8d5f-562cd9680deb`) | 0 | 0 |
| historical-q11 | Ein Riss ist auch ein Anfang – Vernissage (`019fe7de-0270-7c90-82f8-3ece25b10c36`) | 0 | 0 |
| historical-q11 | Circus Ubuntu (`019e00e2-c2d9-7717-8d5f-f79f870e81cb`) | 0 | 2 |
| historical-q11 | Nymalet (`019e6977-7a5c-7584-922d-4baf3ec3ac9a`) | 0 | 0 |
| historical-q11 | Bachs Spuren (`01a0a532-d9c6-7437-8363-2d479640a0cd`) | 0 | 0 |
| historical-q11 | Kulturnacht Flensburg 27 (`019db01b-f059-743c-8a3e-802545d8ed5b`) | 0 | 1 |
| historical-q11 | Sego (`019e98ca-c4a6-7a4e-b2d1-dc59db1fcea3`) | 0 | 0 |
| historical-q11 | Tanz und Musik Jamsession (`019ddad3-c861-72fb-a7e9-e4094e1072af`) | 0 | 0 |
| historical-q11 | NORDEN – The Nordic Arts Festival (`01a0c8fb-4bbe-75e8-9d61-0c380229b121`) | 0 | 3 |
| historical-q11 | GRIND / ANDERS - Wennerberg, Burgess / Franzke (`01a05cc3-f200-72ad-99cf-db5ad55a3a56`) | 0 | 0 |
| historical-q11 | Sommer im Garten (`019e6382-ca19-7f89-90e4-13b5ba2c4cd2`) | 0 | 3 |
| historical-q11 | ONspace goes Punk (`019e6961-60f4-7bbe-a386-f039cfd9fb9b`) | 0 | 0 |
| historical-q11 | Electronic Movement (`01a05e11-54dd-7132-9fa1-93b61b7d86db`) | 0 | 0 |
| historical-q11 | Fördecrossing (`019e3c81-b184-70a7-89ac-73a5f512a5d4`) | 3 | 3 |
| historical-q11 | ORDRIG (`019e5e75-be89-78b2-b574-cf5f9fa4b090`) | 0 | 3 |
| historical-q11 | Avant-Goth Theater (`01a0d816-d0af-770e-927c-6d1bf77ab522`) | 0 | 0 |
| historical-q11 | Nix för Bangbüxen (`019e3b9b-8449-76ef-9912-daa7e6387d86`) | 0 | 0 |
| historical-q11 | Das blaue kaninchen öffnet seine Türen! (`019f642a-6008-797e-8ac8-d09b77deddc9`) | 0 | 0 |
| historical-q11 | Wildkräuterwanderung (`01a0c366-8dbc-7a1b-aaf4-383a8cf4042f`) | 3 | 3 |
| historical-q11 | Faire Woche 2026 Flensburg (`01a0201f-5f06-7983-9497-62b4745a36a4`) | 2 | 2 |
| historical-q12 | MOSAIK Themen-Treffen (`01a0f13d-a497-7133-9a27-ba89c246ad60`) | 3 | 3 |
| historical-q12 | Hautnah (`019f1cc7-18f1-778d-89c5-5d6bd29717f4`) | 0 | 0 |
| historical-q12 | Where The Waves Took Her (`019f51e0-900d-71f9-bbef-6f0ec884fc13`) | 3 | 3 |
| historical-q12 | Das blaue kaninchen öffnet seine Türen! (`019f642a-6008-797e-8ac8-d09b77deddc9`) | 0 | 1 |
| historical-q12 | David Lübke: "Wo der Mond die Erde küsst"-Tour 2026 (`019fa7e6-5064-7310-9df2-2890f29e1497`) | 0 | 0 |
| historical-q12 | Wohin mit mir? (`019f54ef-75df-7aee-851b-d3cd83db4a02`) | 3 | 3 |
| historical-q12 | Marc-André Hamelin (`019e7d8e-e8b2-747c-bda0-133de3170146`) | 0 | 0 |
| historical-q12 | Culk (`019e03b3-7338-73d5-ac34-129f260c7a99`) | 0 | 0 |
| historical-q12 | Medeamaterial (`019e1312-0f42-701e-86fe-f2bfb10093f8`) | 2 | 3 |
| historical-q12 | Arne Semsrott: Gegenmacht (`019f4608-8996-72e3-9d34-0544db82c659`) | 0 | 2 |
| historical-q12 | De Steensöker (`019dc64c-c219-7629-90f8-61469283a67d`) | 0 | 0 |
| historical-q12 | Avant-Goth Theater (`01a0d816-d0af-770e-927c-6d1bf77ab522`) | 0 | 0 |
| historical-q12 | Festtagslunch (`01a069e2-9587-7f80-bd02-3804ab2c127f`) | 0 | 0 |
| historical-q12 | Flensburg fühlt die Mobilitätswende (`019fd167-b370-71f5-9e3b-53cc95f5262a`) | 0 | 0 |
| historical-q12 | BAM 밤 – für violette Nächte - TachoTinta (`01a09f4a-d945-7f5b-a0c2-7d0bbfa36ff4`) | 3 | 3 |
| historical-q12 | Faire Woche 2026 Flensburg (`01a0201f-5f06-7983-9497-62b4745a36a4`) | 0 | 1 |
| historical-q12 | Digitale Teilhabe – gemeinsam vernetzt (`019db91a-89d5-7c5a-90ae-7596e488a1eb`) | 2 | 1 |
| historical-q12 | Naturkosmetik und Kräuter (`019f9a39-9cd8-717c-9369-300e01a33082`) | 0 | 0 |
| historical-q12 | Rumregatta (`019daa4c-cdfc-7895-8c03-855852da0ed5`) | 0 | 0 |
| historical-q12 | Der (rote) Faden (`019f1c76-eb40-79ea-88e1-4ee976848158`) | 0 | 1 |
| historical-q13 | 1. Bundessiegerkonzert Duo Pianoforte Klavier vierhändig (`019da5ae-5d78-7d0b-a4e5-5bf7e818a886`) | 0 | 0 |
| historical-q13 | Speed-Dating - Kultur trifft Politik (`019eb719-75cb-749e-be9c-fab9c5b5636f`) | 0 | 0 |
| historical-q13 | Zeichnen im Museum (`01a067af-dddf-733c-aaf7-833c05c7c126`) | 0 | 0 |
| historical-q13 | Oh Hiroshima (`019e1578-90c3-701c-b9f9-b11275a6c62c`) | 0 | 0 |
| historical-q13 | K26 Kulturtræf (`019dce5e-3d70-7e44-9f1e-d59ab4013fd6`) | 0 | 0 |
| historical-q13 | Campus Festival Flensburg 2026 (`019ea218-800e-7421-9bcd-b85ed0d9f774`) | 0 | 0 |
| historical-q13 | KINKTASTIC (`019dd78e-468a-775e-a35a-0804dad94fbc`) | 3 | 3 |
| historical-q13 | triaden tiraden (`019df20e-4efc-7c01-8c4a-8880af01f14a`) | 0 | 0 |
| historical-q13 | KulturRotation 143 (`019e262e-5660-76c8-93cc-c7736848b4d3`) | 0 | 0 |
| historical-q13 | Simon & Jan (`019f5a6c-2703-7fdd-b09f-87f4572de163`) | 0 | 0 |
| historical-q13 | Kulturh(a)us Utopia (`019da011-1802-7924-8a24-821066242bba`) | 0 | 0 |
| historical-q13 | Where The Waves Took Her (`019f51e0-900d-71f9-bbef-6f0ec884fc13`) | 0 | 0 |
| historical-q13 | KuRD 2026 (`019dd89e-f434-7cbd-bc59-60d3c7bda536`) | 0 | 0 |
| historical-q13 | Sange fra Livet med Søren Ryge Petersen (`019f02f3-a079-7e64-b317-362f9ee1c378`) | 0 | 0 |
| historical-q13 | Ausstellungseröffnung - Wenn Einsamkeit laut wird - Open Call Plakatentwürfe (`01a0ebd9-2a2c-7fa0-9227-25ede3d119a2`) | 0 | 0 |
| historical-q13 | Salò (`019fdc5b-c85e-7798-81aa-fe71eaa038e6`) | 0 | 0 |
| historical-q13 | Summerfeeling mit Theo Klattenhoff (`019e373a-f614-73db-94f3-5d7496065324`) | 0 | 0 |
| historical-q13 | Kurzfilme im Hof 26 (`019f17fc-2896-7e8a-8737-3b0f3d675c09`) | 0 | 0 |
| historical-q13 | Julekoncert med Árstíðir (`019dcefa-5fd1-703e-b3a1-7d05e5f62298`) | 0 | 0 |
| historical-q13 | Konzert Pouya Abdi (`01a067f8-af99-72e1-80ce-b90ca7396e37`) | 0 | 0 |
| historical-q14 | After Work in der Alten Post (`019f1cb7-39b6-7177-a129-5c20f1a3e958`) | 0 | 0 |
| historical-q14 | DenkMal! (`01a0b3aa-28bf-7a09-9295-6c17ab731dc5`) | 0 | 2 |
| historical-q14 | kunstkur.park (`01a0bad2-8447-79e3-bca8-108384330135`) | 0 | 0 |
| historical-q14 | Pink & White Sunset BBQ (`019eb0af-94d0-728f-8f11-1e6d7d17c835`) | 0 | 0 |
| historical-q14 | Aalkreih (`019fa7f6-e5bd-78a2-8f48-2806521951b8`) | 1 | 2 |
| historical-q14 | Filmvorführung: Verwundene Fäden (`019eb5e3-5e29-72dc-8cac-3fcbceb3307b`) | 0 | 0 |
| historical-q14 | La.tina (`019e6df1-b798-7db1-bd65-ca7bd04e91bc`) | 0 | 1 |
| historical-q14 | Cultural Pearl Kulturtag (`019e63f7-ebeb-7952-9304-e496b02e3588`) | 0 | 1 |
| historical-q14 | Flens345 (`019f17f6-aca2-7a4b-b9f7-32a213aa624d`) | 0 | 1 |
| historical-q14 | Tag des Friedhofs (`01a0a537-14a3-720c-8204-c72887c6b460`) | 3 | 3 |
| historical-q14 | Ginevra Lamberti: Das Wasser wiegt schwerer als die Zeit (`019eb5f2-356f-72b2-9bf0-5967d0fd97e6`) | 0 | 0 |
| historical-q14 | Steps in Time (`019e897f-3791-7ae7-baa4-0c239e013031`) | 0 | 0 |
| historical-q14 | Glücksburger Biermeile (`019ed14b-72a4-74ba-bc05-315d59801d86`) | 0 | 0 |
| historical-q14 | triaden tiraden (`019df20e-4efc-7c01-8c4a-8880af01f14a`) | 0 | 1 |
| historical-q14 | Schnupperkurs Plattdeutsch (`01a06ade-f5ed-7571-9630-854d88fec839`) | 1 | 2 |
| historical-q14 | Kapa Tult (`019e0e4a-1f62-7c17-b361-8a5499e3267a`) | 0 | 0 |
| historical-q14 | ORDRIG (`019e5e75-be89-78b2-b574-cf5f9fa4b090`) | 2 | 3 |
| historical-q14 | Conversations (`019dc3b0-94d4-7ce6-9b7c-15ee0e19e6c8`) | 0 | 0 |
| historical-q14 | Electronic Movement (`01a05e11-54dd-7132-9fa1-93b61b7d86db`) | 0 | 1 |
| historical-q14 | Tag der Städtebauförderung (`019dd805-5eef-7120-afba-14e688b30b50`) | 0 | 2 |

## Prüfungen und Grenzen

Tests prüfen alle 275 Paare gegen jeden hypothetischen heuristischen Score 0–3, eindeutige
Resolution, echte Feld-/Zitatreferenzen, fehlende/falsche Evidenz, Approval-Ausschluss, unveränderte
Originalquellen, Occurrence-Grenzen, Queue-Priorität und Fortbestand offener Entscheidungen.
Die vier Originaldateien werden vor/nach Verarbeitung anhand der gepinnten Byte-SHA256 geprüft.
Alle sechs No-Hit-Fälle bleiben ungeklärt; `expected_no_hit` wird nicht geändert.
Kein Live-Zugriff, keine Inferenz, kein Deployment, kein Merge, keine Aktivierung. `semantic_query=false`.
Lokale Ausführung: `uv sync --locked --offline`, Ruff, Format und `git diff --check` grün.
`pytest -q`: **409 bestanden, 24 übersprungen** (22 Integration, zwei optionale Real-Encoder-Tests).
Annotationsprüfungen: **27 bestanden**. Keine Live-Provider für diese Prüfungen verwendet.
Remote-CI wird hier nicht als für den neuen Head beobachtet behauptet; der Auftrag verbietet Webrequests.
