"""Offline, conservative machine proposals; never imports/approves human judgments.

Reads only the four user-authorized evidence sources plus the frozen query rubrics.
No network, provider, runtime, retrieval scores or model/artist knowledge is used.
Text matching locates evidence; curated scope decisions below limit its interpretation.
The output is a review aid, not an evaluation dataset or exhaustive semantic labeling.
"""

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmark/annotation"
SOURCES = {
    "benchmark/ground-truth-v1.jsonl": (
        "a72b04ca44655ca4e8ba456e8d9698ff6ebbe47e1dde54f075780c9e6e4a8b53"
    ),
    "benchmark/snapshots/public-events-20261005/events.jsonl": (
        "2de49bc71942926e953f4de76d4b5dbcfe1780a6a2a20ee2b0feb6fa97cbf7f1"
    ),
    "benchmark/annotation/evidence.md": (
        "282525301580328c6c2e10e02d878d1339a139612839471c816fefd6012afa77"
    ),
    "docs/retrieval-annotation-guidelines.md": (
        "149573227a99c3122efd6c8108818b727467ee4329514d6e84a1ff055d8ed4f1"
    ),
}
RUBRIC_HASH = "ef0ea425dc00ffcf9471573a9e76304faebfbb75ee3aa674c64d6555c6e273f3"
AMBIGUOUS = {"open", "colourful", "concerts", "artoptions", "free_family_countries"}
SENSITIVE = {
    "access",
    "wheelchair",
    "stepfree",
    "access_registration",
    "meeting",
    "outdoor",
    "outdoor_music",
    "kuehlhaus",
    "museumsberg",
    "flensburg",
    "gluecksburg",
    "saturday",
    "cityart",
    "danish_denmark",
    "language_germany",
    "free_family_countries",
}
TEXT_FIELDS = ("title", "subtitle", "summary", "description")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def ev(field, quote):
    return {"field": field, "quote": quote}


def find(event, pattern, fields=TEXT_FIELDS):
    """Return a verbatim bounded sentence, not a naked keyword or fabricated quote."""
    for field in fields:
        value = event[field]
        for sentence in re.split(r"(?<=[.!?])\s+|\n", value):
            match = re.search(pattern, sentence, re.I)
            if match:
                start, end = max(0, match.start() - 140), min(len(sentence), match.end() + 200)
                return [ev(field, sentence[start:end])]
    return []


def typed(event, names, key="type_name"):
    for i, item in enumerate(event["event_types"]):
        if item[key] in names:
            return [ev(f"event_types.{i}.{key}", item[key])]
    return []


def eligible_occurrences(event, case):
    predicate = case["eligibility"]
    found = []
    for i, occurrence in enumerate(event["occurrences"]):
        day = occurrence["start_date"]
        if predicate["city"] and occurrence["city"].casefold() != predicate["city"].casefold():
            continue
        if predicate["venue_id"] and occurrence["venue_id"] != predicate["venue_id"]:
            continue
        if predicate["date_from"] and (not day or day < predicate["date_from"]):
            continue
        if predicate["date_to"] and (not day or day > predicate["date_to"]):
            continue
        if predicate["weekdays"] and (
            not day or date.fromisoformat(day).isoweekday() not in predicate["weekdays"]
        ):
            continue
        found.append((i, occurrence))
    return found


def facets(e):
    f = {}
    f["music"] = typed(e, {"Konzert", "Musik"}) or find(
        e, r"\blive[- ]?musik\b|\bkonzert\b|\bkoncert\b", ("title", "subtitle", "summary")
    )
    f["art"] = typed(e, {"Kunst", "Ausstellung"})
    f["exhibition"] = typed(e, {"Ausstellung"}) or find(
        e, r"\bausstellung\b|\budstilling\b", ("title", "subtitle", "summary")
    )
    f["family"] = typed(e, {"Familienveranstaltung"}) or find(
        e,
        r"für (?:die ganze|alle|kleine und große) familie|für familien|familien mit kindern|"
        r"groß und klein|jung und alt|hele familien|børn og voksne",
    )
    f["kids"] = typed(e, {"Kindertheater"}) or find(
        e, r"für kinder|kinder ab|kinderkonzert|kinderatelier|kinder-ateliers?|for børn"
    )
    f["free"] = [ev("price_type", "free")] if e["price_type"] == "free" else []
    f["jazz"] = typed(e, {"Jazz"}, "genre_name")
    f["folk"] = typed(e, {"Folk"}, "genre_name")
    f["chamber"] = typed(e, {"Kammerkonzert"}, "genre_name") or find(
        e, r"kammermusik|kammerkonzert", ("title", "subtitle")
    )
    f["small"] = find(e, r"\btrio\b|\bquartett\b|\bduo\b", ("title",))
    f["punk"] = typed(e, {"Punk"}, "genre_name")
    f["guitar"] = typed(e, {"Rock", "Metal"}, "genre_name") or find(
        e, r"\bgitarren\b|\bguitarer\b", ("summary",)
    )
    f["puppet"] = typed(e, {"Puppenspiel"}, "genre_name") or find(
        e, r"puppentheater|figurentheater|dukketeater", ("title", "subtitle", "summary")
    )
    f["stage"] = typed(e, {"Theater & Bühne", "Kindertheater"})
    f["painting"] = typed(e, {"Malerei"}, "genre_name") or find(
        e, r"\bmalerei\b|\bgemälde\b|\bmalerier\b", ("title", "subtitle", "summary")
    )
    f["tour"] = find(e, r"kuratorenführung|kuratorinnenführung|führung.{0,45}kurator")
    f["hand"] = find(
        e,
        r"gemeinsam malen|kannst du eigene bildideen|können kinder.{0,90}(?:malen|gestalten)|"
        r"eigenen kreativen projekten.{0,70}nachgehen|stift oder pinsel in die hand|"
        r"stellen ihre eigenen pflegeprodukte|zeichnen, malen und eigene kreative ideen|"
        r"du lernst.{0,80}(?:zeichnen|malen)|wir (?:zeichnen|malen|gestalten)|"
        r"collagen kleben|porzellan bemalen|lav jeres eget våbenskjold|lego-druckworkshop",
    )
    f["creative"] = f["hand"] or find(
        e,
        r"kreativ mit offenen daten|gemeinsam kreativ.{0,15}(?:werden|sein)|"
        r"kreativen fertigkeiten.{0,30}entdecken|achtsames zeichnen|malen zur entspannung",
    )
    f["workshop"] = typed(e, {"Workshop", "Kursus"}) or find(
        e, r"\bworkshop\b|\bworkshops\b|\bmalkreis\b", ("title", "subtitle", "summary")
    )
    f["outdoor"] = find(
        e,
        r"unter (?:freiem|offenem) himmel|open[- ]air|\bfreiluft|im freien|"
        r"wildkräuterwanderung|\bfreiwasser|auf der wiese|outdoorkino|"
        r"raus in die natur|outdoor naturstudien|\bstrandfest\b|im garten.*(?:feier|erwartet)",
    )
    f["culture"] = typed(
        e,
        {
            "Konzert",
            "Musik",
            "Kunst",
            "Ausstellung",
            "Theater & Bühne",
            "Kindertheater",
            "Lesung",
            "Literatur",
            "Film",
            "Tanz",
            "Performance",
            "Kultur",
            "Comedy",
        },
    )
    f["registration"] = []
    for field in TEXT_FIELDS:
        for sentence in re.split(r"(?<=[.!?])\s+|\n", e[field]):
            if re.search(r"anmeld|registrier|reservier|tilmeld", sentence, re.I) and not re.search(
                r"\bohne\b|\bnicht\b|\bkeine?\b|uden|ikke|abmeld", sentence, re.I
            ):
                f["registration"] = [ev(field, sentence[:400])]
                break
        if f["registration"]:
            break
    return f


# Explicit scope decisions after reading frozen public passages. Key: rubric, UUID suffix.
# The suffix is resolved uniquely against the complete snapshot before any proposal is written.
# Entries: score, evidence-locator regex, semantic explanation. None are human approvals.
CURATED = {}


def add(rule, score, suffixes, pattern, explanation):
    for suffix in suffixes.split():
        CURATED[rule, suffix] = (score, pattern, explanation)


add(
    "education",
    3,
    "66242bba b4013fd6 b23d0b1e",
    r"workshop|kulturelle bildung",
    "Kulturelle Praxis/Vermittlung ist ausdrücklich Veranstaltungsinhalt.",
)
add(
    "education",
    2,
    "c959f5ef d04e91bc e488a1eb c7bda536",
    r"wissensvermittlung|workshop|bildung|mitmach",
    "Konkrete Lern-/Vermittlungsanteile; breiteres bzw. nicht ausschließlich kulturelles Programm.",
)
add(
    "education",
    1,
    "fa4a8aa2",
    r"mitmach",
    "Mitmach-Angebote belegt; Lerninhalt nicht konkretisiert.",
)
add(
    "migration",
    3,
    "c246ad60 c884fc13 83db4a02 bfa36ff4",
    r"migration|flucht|geflücht",
    "Migration/Flucht ist ausdrücklich Gegenstand des Angebots bzw. erzählten Werks.",
)
add(
    "migration",
    2,
    "b10093f8 e488a1eb",
    r"integrationspolitik|teilhabe von menschen mit migrationsgeschichte",
    "Integrationspolitik bzw. Migration ist belegter Teil eines breiteren Programms.",
)
add("queer", 3, "dad94fbc", r"wild, queer", "Queere Party mit Drag ausdrücklich im Programm.")
add(
    "localhistory",
    3,
    "87c6b460",
    r"geschichte und besonderheiten des friedhofs",
    "Geschichte des konkret benannten Friedhofs Neuwerk wird in einer Führung vermittelt.",
)
add(
    "localhistory",
    2,
    "9fa4b090",
    r"sønderjyllands historie",
    "Sønderjyllands Geschichte ist expliziter Programmteil eines breiteren Literaturformats.",
)
add(
    "localhistory",
    1,
    "521951b8 88fec839",
    r"platt|tradition",
    "Regionale/plattdeutsche Kultur belegt; historische Vermittlung nicht direkt zugesichert.",
)
add(
    "youth",
    3,
    "5642e2f4 4719f914",
    r"für jugendliche|richtet sich an jugendliche",
    "Jugendliche sind ausdrücklich die Zielgruppe des Angebots.",
)
add(
    "youth",
    2,
    "bee729ba",
    r"jugendliche, kinder und erwachsene",
    "Jugendliche sind ausdrücklich Teil einer breiteren Zielgruppe.",
)
add(
    "youth",
    1,
    "870e81cb aba7077d c7bda536",
    r"jugendzirkus|junge menschen|theaterjugendclub",
    "Jugendliche wirken im Programm mit; kein eigenes Angebot für jugendliches Publikum belegt.",
)
add(
    "sustainability",
    3,
    "477659a5 745a36a4 c959f5ef c25cab37 a3b00009 3be76b85 c3a122c5",
    "klimaschutz|fair handeln|lebensmittelverschwendung|erneuerbare "
    "energien|nachhaltig|lebensmittelwertschätzung",
    "Nachhaltigkeit/Fairness/Ressourcennutzung ist ausdrücklich Veranstaltungsthema.",
)
add(
    "sustainability",
    2,
    "18bb8b7a",
    r"fairer handel und nachhaltigkeit",
    "Fairer Handel im Frühstück sowie Vortrag/Quiz, nicht ausschließlich thematische Vermittlung.",
)
add(
    "inclusion",
    3,
    "e488a1eb eb84aea2 51422bd9 d9f1bb42",
    r"digitale teilhabe|gesellschaftliche teilhabe|von und für menschen mit und ohne behinderung",
    "Teilhabe bzw. inklusives Angebot ist ausdrücklich Kern.",
)
add(
    "inclusion",
    2,
    "c5b5636f 66242bba b547e1ba",
    r"gesellschaftliche teilhabe|zusammenleben|teilhabe am platz",
    "Teilhabe/Austausch ist ausdrücklich ein wesentlicher Programmaspekt.",
)
add(
    "inclusion",
    1,
    "4a05fc2b f6523e33 6c78e8bf 8ef1a6f8",
    r"gemeinsam|familie|neue leute kennenlernen",
    "Gemeinschaftlicher Aspekt belegt; Abbau sozialer Barrieren nicht belegt.",
)
add(
    "danish_denmark",
    1,
    "650642c6 68985969 66242bba b4013fd6 d4f861b7",
    r"dänisch|dansk",
    "Dänische Sprache/Kultur bzw. Begegnung belegt; Durchführung in Dänemark nicht belegt.",
)
add(
    "language",
    3,
    "68985969 650642c6",
    r"wöchentlich|insgesamt 6",
    "Mehrteiliger Dänischkurs explizit.",
)
add(
    "language",
    2,
    "c1441978",
    r"schnupper-nachmittag",
    "Expliziter Sprachlern-Schnuppertermin, kein mehrteiliger Kurs.",
)
add(
    "language_germany",
    1,
    "68985969 650642c6 c1441978",
    r"dänisch|russisch",
    "Sprachlernen belegt; Land Deutschland ist in den erfassten Ortsfeldern nicht enthalten.",
)
add(
    "seniors",
    1,
    "34e1f389 c4b215a0",
    r"seniorenbeirat|ambulante tagespflege",
    "Seniorenvertretung bzw. Tagespflegebezug; keine ausdrückliche "
    "Senioren-Zielgruppe des Gesamtangebots.",
)
add(
    "seniors",
    0,
    "2c1291f5 7ea90fb3",
    r"senioren",
    "Seniorenresidenz als Venue belegt keine Senioren-Zielgruppe.",
)
add(
    "meeting",
    2,
    "88b30b50 745a36a4",
    r"treffpunkt:|startpunkt am",
    "Konkrete Treff-/Startpunkte innerhalb eines größeren Programms; "
    "Zuordnung zur Occurrence manuell prüfen.",
)
add(
    "meeting",
    1,
    "9dd80fa1 9e9a912c 5a44674e 1ac6918c d6808104 bfba859b",
    r"treff|gemeinsam|redaktion",
    "Tatsächlicher Treffcharakter; kein expliziter Start-/Sammelpunkt.",
)
add(
    "creative_workshop",
    3,
    "66242bba",
    r"gemeinsam kreativ zu werden",
    "Gemeinsame kreative Praxis mit expliziten Storytelling- und Druckworkshops.",
)
add(
    "creative_workshop",
    2,
    "07f730ae ccf4ade2 a8c28ede fc43e2af 9c2f643d e24250a2 43cb6ce9 e5545e2e 86302530",
    r"workshop|kreativ|gemeinsam malen|herstellung|fertigkeiten",
    "Aktive kreative Praxis belegt; gemeinsamer Workshopcharakter nicht vollständig explizit.",
)
add(
    "creative_workshop",
    2,
    "745a36a4",
    r"gemeinsam mit waldwuchs individuell gestalten",
    "Gemeinsame kreative Workshops sind Teil eines größeren Programms.",
)
add(
    "creative_workshop",
    1,
    "d0d9f774 b4013fd6 6ac4ed93",
    r"workshops|kreative",
    "Workshop/Kreativität belegt, konkretes gemeinsames gestalterisches Angebot nur teilweise.",
)


add(
    "nordic",
    3,
    "a39057ef e5f62298 9b308052 dbd35050 0cd33295 e3ce6b44",
    "norwegens reichhaltiger volksmusiktradition|umiskendeligt "
    "islandske klang|skandinavische folkmusik|skandinaviske "
    "folkemusik|skandinavischen folklore|nordisk folkemusik",
    "Nordische/skandinavische Musik ist ausdrücklich das gespielte Programm, nicht bloß Herkunft.",
)
add(
    "nordic",
    2,
    "0c5a471a 0e19e6c8 9f4cdfc9 a65a3a83",
    r"nordiske melankoli|musik skandinaviens|nordisk melankoli|nordischer seele",
    "Nordischer musikalischer Einfluss ausdrücklich beschrieben; gemischter Stil.",
)
add(
    "nordic",
    1,
    "fa4a8aa2 0229b121",
    r"skandinavische sommerstimmung|nordisches lebensgefühl",
    "Nordischer Kulturrahmen belegt; konkreter nordischer Musikstil "
    "des Programms nicht vollständig.",
)
add(
    "experimental",
    3,
    "7cc065dd",
    r"experimental noise pop symphony",
    "Experimentelle Klangform ausdrücklich als gespieltes Programm beschrieben.",
)
add(
    "experimental",
    3,
    "181cfbcb",
    r"durch die künstlerin begehbarere durchsichtige luftblase",
    "Ungewöhnliche Kunstform explizit: begehbare Luftblase als Performance-Ort.",
)
add(
    "experimental",
    2,
    "c30ab219 dda3c1d4 0ec92317 53bb618e",
    r"experimentelle|robotværket|schreibmaschinengetacke",
    "Experimentelle Arbeitsweise bzw. konkrete ungewöhnliche künstlerische Form beschrieben.",
)
add(
    "experimental",
    1,
    "8f56068e ce381783 9f4cdfc9 613a09f4 a8c28ede 8d15d358",
    r"improvisation|improviseres|experiment|elektronischer live musik",
    "Improvisation/Experimentieren bzw. elektronische Begleitung "
    "belegt; kein eindeutiger experimenteller Gesamtkern.",
)
add(
    "songwriters",
    3,
    "d066867f",
    r"fortællinger fra sit eget liv",
    "Eigene Indie-Folk-Musik ausdrücklich aus Erzählungen des eigenen "
    "Lebens entwickelt; Text bestätigt eigenes Schreiben/Produzieren.",
)
add(
    "songwriters",
    3,
    "f29e1497",
    r"ich schreibe lieder auf bierdeckel",
    "Eigenes Lied erzählt ausdrücklich von der eigenen "
    "Liedermacher-Walz; persönlicher Erzählkontext beschrieben.",
)
add(
    "songwriters",
    2,
    "b90b8710",
    r"lias texte sind oft metaphorische bilder",
    "Eigene Texte und persönlich gefärbte Geschichten belegt; "
    "autobiografischer Volltreffer nicht ausdrücklich.",
)
add(
    "songwriters",
    1,
    "abdf2307 cdfc138f e5f62298 7cc065dd 84d9cbf3 9ee1c378",
    "songs erzählen geschichten|egne favoritter|musik og "
    "fortællinger|original music|persönliche geschichten|fortællinger",
    "Eigene Musik oder erzählerischer Aspekt belegt; beide zentralen "
    "Eigenschaften zusammen nicht gesichert.",
)
add(
    "quiet",
    2,
    "fa4a8aa2 0e19e6c8 5cef2a0c",
    r"gemütliche, herzliche atmosphäre|entspannt dazuzusetzen|gemütlicher",
    "Musik mit ausdrücklich entspannter/gemütlicher Atmosphäre; "
    "durchgehend ruhige Livemusik nicht direkt zugesichert.",
)
add(
    "quiet",
    1,
    "b9fed9b7 9f4cdfc9",
    r"mal leise, mal laut|det intime og det uforudsigelige",
    "Auch leise/intime musikalische Elemente, zugleich "
    "laute/explosive Teile; kein durchgehend ruhiges Angebot.",
)
add(
    "dance",
    2,
    "99e3267a d867f8cb 23074d68 2c1291f5 0229b121 09ae1d28",
    "soundtrack fürs durchkommen|tanz-workshop|livemusik zum "
    "tanzen|geselligen abend mit musik, tanz|tanzen, lesen|lust haben "
    "boogie woogie zu tanzen",
    "Aktive Tanzmöglichkeit belegt; ausgelassener Abend als vollständiger Kontext nicht eindeutig.",
)
add(
    "dance",
    1,
    "e4662280 d29717f4 bfa36ff4",
    r"afterparty|freies tanzen|zeitgenössischem tanz",
    "Party-/Tanzanteil belegt; teils Bühnenaufführung, kein gesicherter Tanzabend fürs Publikum.",
)
add(
    "open",
    2,
    "ba2c4cd2 d0d9f774 867a79da bb8c6095 0a83ff11 e6d22757",
    r"open stage|open mic|selbst auf der bühne|kommt auf die bühne|beim auftritt vorrang",
    "Offene Auftrittsmöglichkeit explizit; mehrdeutige "
    "Query-Auslegung bleibt menschliche Reviewfrage.",
)
add(
    "open",
    1,
    "3015e6e1",
    r"publikum wird immer wieder gezielt",
    "Publikumsbeteiligung an Performance belegt; keine freie eigene Bühnenpräsentation.",
)
add(
    "harpsichord",
    1,
    "ee10f521 01bc38e5",
    r"bau- und bastelaktion",
    "Aktive Bau-/Bastelaktion belegt, aber Märchenkulissen statt "
    "Cembalobau; nur schwacher Bau-Aspekt. No-hit bleibt offen.",
)
# Scope corrections: general organizer information is not an event audience promise.
add(
    "free_family",
    1,
    "862e6c95",
    r"termin ist kostenlos",
    "Termin kostenlos; Kinderkurse werden nur allgemein als Vereinsangebot beschrieben.",
)
add(
    "free_family",
    2,
    "745a36a4",
    r"bei familien mit kindern",
    "Kostenloses Gesamtprogramm, ausdrücklicher Familienbezug nur bei einer einzelnen Wanderung.",
)
add(
    "kids",
    2,
    "3cce6612",
    r"für die ganze familie",
    "Explizites Familienangebot; Kinder nicht alleinige klare Hauptzielgruppe im Text.",
)

add(
    "registration",
    3,
    "7ea90fb3 b4013fd6",
    r"anmeldung (?:und bezahlung|bis zum)",
    "Anmeldung zum konkreten Angebot ausdrücklich vorgesehen; kein bloßer Ticket-Vorverkauf.",
)
add("children", 3, "0e551c30", r"kinderkonzert", "Konzert ausdrücklich für Kinder konzipiert.")
add(
    "creative",
    3,
    "e24250a2 a8c28ede 4719f914 31487b2a",
    r"eigene bildideen|können kinder.{0,100}gestalten|eigene kreative ideen|jeres eget våbenskjold",
    "Eigene händische Gestaltung ausdrücklich als Teilnahmeangebot beschrieben.",
)
add(
    "participatory_art",
    3,
    "43cb6ce9 db24348a",
    r"gemeinsam malen|collagen kleben",
    "Eigene aktive Kunstpraxis ausdrücklich angeboten.",
)
add(
    "outdoor",
    3,
    "f512a5d4 8cf4042f",
    r"freiwasser|wildkräuterwanderung",
    "Durchführung im Freiwasser bzw. als Kräuterwanderung explizit; nur referenzierte Occurrences.",
)
add(
    "outdoor_music",
    3,
    "d867f8cb f6523e33 35316bec",
    r"open-air-bühne|unter freiem himmel",
    "Musikprogramm ausdrücklich unter freiem Himmel; keine Ableitung aus dem Venue-Namen.",
)


def assess(e, c, rule):
    f = facets(e)
    occurrences = eligible_occurrences(e, c)
    assert occurrences or not any(v for k, v in c["eligibility"].items() if k != "contract"), (
        c["id"],
        e["id"],
    )
    evidence = []
    score = 0
    confidence = "medium"
    note = (
        "Keine hinreichende positive Evidenz für diese Suchintention in "
        "den eingefrorenen Feldern gefunden."
    )
    occurrence_ids = []

    def set_score(n, keys, why):
        nonlocal score, evidence, note
        score, note = n, why
        evidence = [x for key in keys for x in f.get(key, [])]

    def combined(a, b, why):
        set_score(2 if f[a] and f[b] else 1 if f[a] or f[b] else 0, [a, b], why)

    if rule in {"free_family", "free_family_countries"}:
        combined(
            "free",
            "family",
            "Nur der zitierte Preis-/Familienaspekt ist belegt; Vollständigkeit prüfen.",
        )
        if rule == "free_family" and f["free"] and f["family"]:
            score, confidence, note = (
                3,
                "high",
                "Kostenloser Zugang und Familien-/Kinderangebot ausdrücklich belegt.",
            )
        if rule == "free_family_countries":
            note += (
                " Veranstaltungsland fehlt als explizites Snapshot-Feld; "
                "Länder-Suchraum bleibt Reviewfrage."
            )
    elif rule in {"kids", "children", "together", "participatory_art", "youth_art"}:
        if rule == "kids":
            set_score(
                3 if f["kids"] else 2 if f["family"] else 0,
                ["kids", "family"],
                "Kinder ausdrücklich adressiert."
                if f["kids"]
                else "Familienangebot ausdrücklich belegt.",
            )
            confidence = "high" if score == 3 else "medium"
        elif rule == "children":
            f["family"] = f["kids"] or f["family"]
            combined(
                "music",
                "family",
                "Musik bzw. Kinder-/Familienbezug belegt; Musikangebot speziell für Kinder prüfen.",
            )
        elif rule == "together":
            combined(
                "creative",
                "family",
                "Aktive Kreativität bzw. Familie belegt; gemeinsame Familienteilnahme prüfen.",
            )
        else:
            set_score(
                2 if f["hand"] else 1 if f["art"] else 0,
                ["hand"] if f["hand"] else ["art"],
                "Aktive künstlerische Gestaltung belegt."
                if f["hand"]
                else "Kunst belegt; Teilnahme/Jugendzielgruppe nicht zugesichert.",
            )
            if rule == "youth_art" and score:
                score = 1
                note += " Jugendzielgruppe ist nicht belegt."
    elif rule == "registration":
        set_score(
            2 if f["registration"] else 0,
            ["registration"],
            "Anmeldung/Reservierung textlich erwähnt; Verbindlichkeit und "
            "Programmscope prüfen. Ticketkauf zählt nicht.",
        )
    elif rule == "seniors":
        evidence = find(e, r"seniorennachmittag", ("title",))
        if evidence:
            score, confidence, note = (
                3,
                "high",
                "Titel weist ausdrücklich einen Seniorennachmittag aus.",
            )
    elif rule == "discount":
        if e["price_type"] == "tiered_prices":
            score, evidence, note = (
                2,
                [ev("price_type", "tiered_prices")],
                "Gestaffelte Preise belegt; konkrete Ermäßigungsgruppe nicht belegt (maximal 2).",
            )
    elif rule in {"outdoor", "outdoor_music"}:
        if rule == "outdoor":
            set_score(
                2 if f["outdoor"] else 0,
                ["outdoor"],
                "Outdoor-Durchführung textlich belegt; Programmscope/Occurrence prüfen.",
            )
        else:
            combined(
                "music",
                "outdoor",
                "Nur zitierte Musik-/Outdooraspekte belegt; gemeinsame Durchführung prüfen.",
            )
    elif rule in {"access", "wheelchair", "stepfree", "access_registration"}:
        accesses = []
        for i, o in occurrences:
            # Most specific public field wins. Do not overwrite an explicit space restriction.
            field = next(
                (
                    k
                    for k in ("accessibility_info", "space_accessibility", "venue_accessibility")
                    if o[k]
                ),
                None,
            )
            if field and re.search(
                "barrierearm|eingeschränkt barrierefrei|rampe|aufzug|barrierefrei "
                "zugänglich|stufenlos",
                o[field],
                re.I,
            ):
                accesses.append(ev(f"occurrences.{i}.{field}", o[field]))
                occurrence_ids.append(o["id"])
        f["access"] = accesses
        if rule in {"access", "wheelchair"}:
            specific = any(
                re.search(
                    r"barrierearm|eingeschränkt barrierefrei|rampe und rollstuhlplätze",
                    x["quote"],
                    re.I,
                )
                for x in accesses
            )
            set_score(
                2 if specific else 1 if accesses else 0,
                ["access"],
                "Konkrete positive Zugangsevidenz; dokumentierte "
                "Einschränkungen/Space und Rollstuhlspezifik gesondert prüfen.",
            )
        elif rule == "stepfree":
            combined(
                "music",
                "access",
                "Konzert bzw. positive Zugangsevidenz belegt; stufenloser "
                "Gesamtweg nicht pauschal bestätigt.",
            )
        else:
            combined(
                "access",
                "registration",
                "Nur zitierte Zugangs-/Anmeldungsaspekte belegt; dieselbe "
                "Occurrence und Verbindlichkeit prüfen.",
            )
    elif rule in {"jazz", "saturday", "folk", "chamber", "punk"}:
        main = "jazz" if rule == "saturday" else rule
        fallback = "small" if rule == "chamber" else "guitar" if rule == "punk" else None
        set_score(
            2 if f[main] else 1 if fallback and f[fallback] else 0,
            [main] if f[main] else [fallback] if fallback else [],
            "Explizite Genre-/Programminformation; vollständigen "
            "Live-/Klang-/Ensemblekontext prüfen.",
        )
    elif rule in {"quiet", "concerts", "colourful"}:
        set_score(
            1 if f["music"] else 0,
            ["music"],
            "Musik belegt; gewünschte Atmosphäre/Programmvielfalt nicht daraus ableitbar.",
        )
        if rule == "concerts" and f["music"]:
            genres = sorted({t["genre_name"] for t in e["event_types"] if t["genre_name"]})
            if len(genres) > 1:
                set_score(
                    2,
                    ["music"],
                    "Mehrere Musikrichtungen ausdrücklich klassifiziert; "
                    "Plural-Auslegung bleibt Reviewfrage.",
                )
                for genre in genres:
                    evidence += typed(e, {genre}, "genre_name")
        if rule == "colourful" and not score and f["culture"]:
            set_score(
                1,
                ["culture"],
                "Kulturangebot belegt; vielseitiger Abend nicht vollständig zugesichert.",
            )
    elif rule == "puppet":
        combined(
            "puppet",
            "kids",
            "Puppenspiel bzw. Kinderangebot belegt; vollständige Verbindung prüfen.",
        )
    elif rule == "stage":
        set_score(
            2 if f["stage"] else 0,
            ["stage"],
            "Bühnen-/Theaterangebot klassifiziert; konkreten szenischen Volltreffer prüfen.",
        )
    elif rule == "painting":
        combined(
            "painting",
            "exhibition",
            "Malerei bzw. Ausstellung belegt; tatsächlich gezeigte Malerei prüfen.",
        )
    elif rule == "curator":
        set_score(
            2 if f["tour"] else 1 if f["art"] else 0,
            ["tour"] if f["tour"] else ["art"],
            "Kunstbezug belegt; kuratorische Führung nur bei explizitem Rollenbeleg.",
        )
    elif rule == "creative":
        set_score(
            2 if f["creative"] else 1 if f["art"] else 0,
            ["creative"] if f["creative"] else ["art"],
            "Aktive Gestaltung belegt."
            if f["creative"]
            else "Kunst belegt; eigenes händisches Gestalten nicht zugesichert.",
        )
    elif rule == "artoptions":
        set_score(
            2 if f["exhibition"] else 1 if f["art"] else 0,
            ["exhibition"] if f["exhibition"] else ["art"],
            "Einzelne Ausstellung/Kunst belegt; Plural-Auslegung muss menschlich geprüft werden.",
        )
    elif rule in {"kuehlhaus", "museumsberg", "flensburg", "gluecksburg", "cityart"}:
        target = {
            "kuehlhaus": "kühlhaus",
            "museumsberg": "museumsberg",
            "flensburg": "flensburg",
            "gluecksburg": "glücksburg",
            "cityart": "glücksburg",
        }[rule]
        key = "venue" if rule in {"kuehlhaus", "museumsberg"} else "city"
        f["place"] = []
        for i, o in occurrences:
            match = target in o[key].casefold() if key == "venue" else target == o[key].casefold()
            if match:
                f["place"].append(ev(f"occurrences.{i}.{key}", o[key]))
                occurrence_ids.append(o["id"])
        kind = (
            "music"
            if rule == "kuehlhaus"
            else "exhibition"
            if rule == "cityart"
            else "art"
            if rule == "museumsberg"
            else "culture"
        )
        combined(
            kind,
            "place",
            "Nur die zitierten Kultur-/Ortsaspekte belegt; gilt für die ausgewiesenen Occurrences.",
        )
        if rule == "cityart" and not f["exhibition"]:
            set_score(
                1 if f["art"] else 0,
                ["art", "place"] if f["art"] else [],
                "Stadtfilter erfüllt; Kunst ohne belegte Ausstellung.",
            )
    elif rule == "koreanopera":
        opera = typed(e, {"Musiktheater", "Musical"}, "genre_name")
        if opera and find(e, r"\boper\b", ("title", "subtitle", "summary")):
            score, evidence, note = (
                1,
                opera,
                "Opernbezug allein; koreanische Übertitel nicht belegt. Kein bestätigter No-hit.",
            )
    elif rule == "language_education":
        underlying = CURATED.get(("education", e["id"][-8:]))
        if underlying:
            score, pattern, _ = underlying
            score, evidence, note = (
                1,
                find(e, pattern),
                "Bildungs-/Vermittlungsanteil belegt; Sprachkurs nicht belegt.",
            )
    elif rule == "history_inclusion":
        underlying = CURATED.get(("inclusion", e["id"][-8:]))
        if underlying:
            _, pattern, _ = underlying
            score, evidence, note = (
                1,
                find(e, pattern),
                "Teilhabeaspekt belegt; lokale Geschichtsvermittlung nicht belegt.",
            )

    if rule in {"jazz", "saturday", "folk", "chamber"} and score == 2 and typed(e, {"Konzert"}):
        score, confidence = 3, "high"
        evidence += typed(e, {"Konzert"})
        note = "Konzert und gefragtes Genre ausdrücklich strukturiert ausgewiesen."
    if rule == "puppet" and f["puppet"] and typed(e, {"Kindertheater"}):
        score, confidence, note = (
            3,
            "high",
            "Kindertheater und Puppenspiel ausdrücklich strukturiert belegt.",
        )
    if rule == "painting" and f["exhibition"] and typed(e, {"Malerei"}, "genre_name"):
        score, confidence, note = (
            3,
            "high",
            "Ausstellung mit Malerei ausdrücklich strukturiert belegt.",
        )
    if rule in {"gluecksburg", "museumsberg", "cityart"} and score == 2:
        score, confidence, note = (
            3,
            "high",
            "Gesuchtes Kultur-/Kunstangebot und konkreter Occurrence-Ort ausdrücklich belegt.",
        )
    curated = CURATED.get((rule, e["id"][-8:]))
    if curated:
        score, pattern, note = curated
        evidence = find(e, pattern) if score else []
        assert evidence or score == 0, (rule, e["id"], pattern)
        confidence = "high" if score == 3 else "medium"
    if rule == "cityart" and e["id"].endswith("b02e3588") and score:
        score, confidence = 2, "medium"
        note = (
            "Ausstellung ist Teil eines breiteren Kulturtags in Glücksburg, "
            "kein reines Ausstellungsformat."
        )
    if curated and score:
        if rule == "free_family":
            evidence += f["free"]
        if (rule, e["id"][-8:]) == ("songwriters", "d066867f"):
            evidence += find(e, r"skrevet, spillet og produceret sin musik selv")
    if score and rule in SENSITIVE and not occurrences:
        score, confidence, evidence = 0, "low", []
        note = (
            "Erforderliche konkrete Occurrence-Evidenz fehlt; keine "
            "Orts-/Zugangseigenschaft ableiten."
        )
    if score and rule in SENSITIVE:
        # Partial matches still need explicit occurrence context. This does NOT assert access.
        if not occurrence_ids:
            occurrence_ids = [o["id"] for _, o in occurrences]
        for i, o in occurrences:
            if o["id"] in occurrence_ids:
                evidence += [
                    ev(f"occurrences.{i}.id", o["id"]),
                    ev(f"occurrences.{i}.start_date", o["start_date"]),
                ]
                if o["venue"]:
                    evidence.append(ev(f"occurrences.{i}.venue", o["venue"]))
                if o["city"]:
                    evidence.append(ev(f"occurrences.{i}.city", o["city"]))
        note += (
            " Keine Übertragung auf andere Occurrences; Event-Level-Aggregation benötigt Review."
        )
    if rule in AMBIGUOUS:
        confidence = "low"
    if not score:
        evidence, occurrence_ids = [], []
        note = (
            note
            if curated
            else "Suchintention in den eingefrorenen öffentlichen Feldern nicht "
            "positiv belegt; fehlende Information bleibt unbekannt."
        )
        if rule in {"nordic", "experimental", "songwriters", "dance", "open", "harpsichord"}:
            confidence = "low"
            note += " Semantischer Grenzfall: vollständigen Text anhand der Rubrik prüfen."
    # Stable de-duplication; includes exact field paths for independent evidence resolution.
    evidence = list({json.dumps(x, sort_keys=True): x for x in evidence}.values())
    if score:
        if e["title"] and not any(x["field"] == "title" for x in evidence):
            evidence.append(ev("title", e["title"]))
        anchors = [
            x
            for x in evidence
            if not x["field"].startswith("occurrences.") or "accessibility" in x["field"]
        ][:2]
        note += " Beleg: " + "; ".join(f"{x['field']}: {x['quote'][:520]}" for x in anchors)
    return score, confidence, note, evidence, occurrence_ids


def priority(p):
    score = p["proposed_relevance"]
    group = (
        0
        if score == 3
        else 1
        if score == 2
        else 2
        if p["confidence"] == "low"
        else 3
        if p["requires_occurrence_review"]
        else 4
    )
    # No-hit hypotheses first within their prescribed score/confidence tier.
    return group, not p["no_hit_candidate"], p["case_id"], p["event_id"]


def resolve(event, path):
    value = event
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def validate(proposals, cases, events):
    expected = {(c["id"], j["event_id"]): (c, j) for c in cases for j in c["judgments"]}
    assert len(proposals) == len(expected)
    actual = {(p["case_id"], p["event_id"]) for p in proposals}
    assert actual == set(expected) and len(actual) == len(proposals)
    for p in proposals:
        c, j = expected[p["case_id"], p["event_id"]]
        event = events[p["event_id"]]["event"]
        assert type(p["proposed_relevance"]) is int and 0 <= p["proposed_relevance"] <= 3
        assert p["confidence"] in {"high", "medium", "low"}
        assert p["document_hash"] == j["document_hash"] == events[p["event_id"]]["document_hash"]
        assert p["source_snapshot_hash"] == c["source_snapshot_hash"]
        assert p["status"] == "machine-proposed"
        assert not {
            "reviewer_a",
            "reviewer_b",
            "approved_by",
            "approved_at",
            "review_status",
        } & set(p)
        assert p["proposed_relevance"] != 3 or p["confidence"] == "high"
        if p["proposed_relevance"] > 0:
            assert p["reason"] and p["supporting_fields"] and p["evidence"]
            if p["rubric_id"] in SENSITIVE:
                assert p["requires_occurrence_review"] and p["occurrence_ids"]
                assert any(x.startswith("occurrences.") for x in p["supporting_fields"])
        assert set(p["supporting_fields"]) == {x["field"] for x in p["evidence"]}
        for evidence in p["evidence"]:
            value = resolve(event, evidence["field"])
            assert (
                evidence["quote"] == value or isinstance(value, str) and evidence["quote"] in value
            )
        ids = {o["id"] for _, o in eligible_occurrences(event, c)}
        assert set(p["occurrence_ids"]) <= ids
    for name, sha in SOURCES.items():
        assert digest(ROOT / name) == sha, f"Source changed: {name}"
    assert digest(OUT / "machine-rubrics-v1.json") == RUBRIC_HASH


def main():
    for name, sha in SOURCES.items():
        assert digest(ROOT / name) == sha, f"Source changed: {name}"
    rubrics = json.loads((OUT / "machine-rubrics-v1.json").read_text())
    assert digest(OUT / "machine-rubrics-v1.json") == RUBRIC_HASH
    cases = read_lines(ROOT / "benchmark/ground-truth-v1.jsonl")
    events = {
        r["event"]["id"]: r
        for r in read_lines(ROOT / "benchmark/snapshots/public-events-20261005/events.jsonl")
    }
    suffixes = Counter(key[-8:] for key in events)
    assert all(suffixes[suffix] == 1 for _, suffix in CURATED)
    proposals, csv_rows = [], []
    for c in cases:
        rule = rubrics["case_rubrics"][c["id"]]
        for j in c["judgments"]:
            e = events[j["event_id"]]["event"]
            score, confidence, reason, evidence, occurrence_ids = assess(e, c, rule)
            p = {
                "schema_version": "machine-proposal-v1",
                "status": "machine-proposed",
                "case_id": c["id"],
                "event_id": e["id"],
                "rubric_id": rule,
                "rubric_sha256": RUBRIC_HASH,
                "source_snapshot_hash": c["source_snapshot_hash"],
                "document_hash": j["document_hash"],
                "proposed_relevance": score,
                "confidence": confidence,
                "reason": reason,
                "supporting_fields": list(dict.fromkeys(x["field"] for x in evidence)),
                "evidence": evidence,
                "occurrence_ids": occurrence_ids,
                "requires_occurrence_review": rule in SENSITIVE,
                "no_hit_candidate": c["category"] == "no_hit",
                "requires_query_interpretation_review": rule in AMBIGUOUS,
            }
            p["review_required"] = (
                score >= 2
                or confidence == "low"
                or p["requires_occurrence_review"]
                or p["no_hit_candidate"]
            )
            proposals.append(p)
            csv_rows.append(
                {
                    "case_id": c["id"],
                    "query": c["query"],
                    "language": c["language"],
                    "category": c["category"],
                    "event_id": e["id"],
                    "event_title": e["title"],
                    "proposed_relevance": score,
                    "confidence": confidence,
                    "reason": reason,
                    "supporting_fields": json.dumps(p["supporting_fields"], ensure_ascii=False),
                    "occurrence_ids": json.dumps(occurrence_ids),
                    "human_decision": "",
                    "human_notes": "",
                    "requires_occurrence_review": p["requires_occurrence_review"],
                    "no_hit_candidate": p["no_hit_candidate"],
                    "requires_query_interpretation_review": p[
                        "requires_query_interpretation_review"
                    ],
                    "document_hash": j["document_hash"],
                    "review_required": p["review_required"],
                    "evidence_reference": f"evidence.md#{e['id']}",
                }
            )
    validate(proposals, cases, events)
    by_pair = {(p["case_id"], p["event_id"]): p for p in proposals}
    csv_rows.sort(key=lambda row: priority(by_pair[row["case_id"], row["event_id"]]))
    (OUT / "machine-proposals-v1.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in proposals)
    )
    queue_path = OUT / "human-review-queue-v1.csv"
    if queue_path.exists():
        with queue_path.open(newline="") as existing:
            assert not any(
                row["human_decision"] or row["human_notes"] for row in csv.DictReader(existing)
            ), "Refusing to overwrite human review input; keep a new version"
    with queue_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_rows)
    stats = {
        "dataset_status": "draft",
        "cases_processed": len(cases),
        "candidates_processed": len(proposals),
        "score_counts": dict(sorted(Counter(p["proposed_relevance"] for p in proposals).items())),
        "confidence_distribution": dict(Counter(p["confidence"] for p in proposals)),
        "cases_with_grade_3": sorted(
            {p["case_id"] for p in proposals if p["proposed_relevance"] == 3}
        ),
        "occurrence_review_count": sum(p["requires_occurrence_review"] for p in proposals),
        "ambiguous_query_count": len(
            {p["case_id"] for p in proposals if p["requires_query_interpretation_review"]}
        ),
        "no_hit_cases_unresolved": [c["id"] for c in cases if c["category"] == "no_hit"],
        "human_approval_created": False,
        "required_review_pairs": sum(p["review_required"] for p in proposals),
        "no_hit_review_pairs": sum(p["no_hit_candidate"] for p in proposals),
        "source_byte_hashes": SOURCES,
        "rubric_sha256": RUBRIC_HASH,
    }
    (OUT / "machine-proposals-v1-validation.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in stats.items()
                if k not in {"source_byte_hashes", "cases_with_grade_3"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
