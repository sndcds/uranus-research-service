# Adapter-Audit des abgeschlossenen v3/v5-Benchmarks

Urteil **A: `v3 retrieval-LoRA vs v5 retrieval-LoRA`**.

v3 verwendet zwei unterschiedliche Jina-Retrieval-LoRAs, deren Gewichte vor der
Inferenz in zwei getrennte ONNX-Exporte gemergt wurden. v5 lädt und aktiviert den
Jina-PEFT-LoRA `retrieval` tatsächlich; Query und Document teilen diesen Adapter und
werden zusätzlich durch `Query: ` beziehungsweise `Document: ` unterschieden.
`peft0.21.1` ist somit keine bloß installierte, ungenutzte Abhängigkeit.

Untersucht wurde PR #7 am Benchmark-Head
`24ebec8f391cdc3d14ea90581e7bea9c0acf0c81`, abgeschlossener Build
`20261006_8cpu_001`. Der frühere Pilot `20261006_001` ist nicht die Vergleichsbasis.
Dieser Audit verändert weder Ergebnisse noch deren Bewertung. Eine unten erklärte
Lücke im historischen v3-Graph-Paritätsnachweis bleibt ausdrücklich offen.

This benchmark uses a frozen draft relevance dataset containing machine proposals plus manually calibrated scoring policy. It is suitable for provisional comparative evaluation, not final production approval.

## Vergleich

| Eigenschaft | v3 | v5 |
|---|---|---|
| Repository | `jinaai/jina-embeddings-v3-hf` | `jinaai/jina-embeddings-v5-text-small` |
| Revision | `d18862d9a48706220815554fac3ebb4dfa46fc28` | `dd76d535f5447ca3897a9c893fb1e612ead98192` |
| Base architecture | `JinaEmbeddingsV3Model`, 24 Layer, Hidden Size 1024 | natives `Qwen3Model`, 28 Layer, Hidden Size 1024 |
| PEFT installiert | Export: 0.21.1; im verwendeten ONNX-Inferenzcontainer kein PEFT-Paketverzeichnis | 0.21.1, bei der Inferenz verwendet |
| LoRA/Adapter vorhanden | Jina `retrieval_query` und `retrieval_passage` | Jina `adapters/retrieval` |
| LoRA/Adapter tatsächlich aktiv | Ja, beide taskabhängig in den ONNX-Gewichten enthalten; keine dynamischen LoRA-Layer nötig | Ja, dynamisch injizierte LoRA-Layer; `set_adapter("retrieval")` bei Load und jedem Embed |
| Query mechanism | Rohtext, Query-ONNX-Session | `Query: ` + Text, gemeinsamer Retrieval-LoRA |
| Document mechanism | Rohtext, Passage-ONNX-Session | `Document: ` + Text, gemeinsamer Retrieval-LoRA |
| Query adapter/task | `retrieval_query`; HTTP `kind="query"` | `retrieval`; HTTP `kind="query"` |
| Document adapter/task | `retrieval_passage`; HTTP `kind="passage"` | `retrieval`; HTTP `kind="passage"` |
| Adapter source | Unterverzeichnisse desselben gepinnten Jina-Snapshots, danach lokaler Export | Unterverzeichnis desselben gepinnten Jina-Snapshots |
| Custom Kulturbytes training | Keine solchen Gewichte im ausgeführten Pfad | Keine solchen Gewichte im ausgeführten Pfad |
| Pooling | Attention-mask-weighted mean, float32 | Letztes Nicht-Padding-Token, float32 |
| Normalization | Eine L2-Normalisierung nach Pooling | Eine L2-Normalisierung nach Pooling |
| Dimension | 1024 | 1024 |

## Beweiskette und Untersuchungsgrenzen

Ausgangspunkt waren die gespeicherten Ausführungsartefakte, nicht README-Angaben:

- [v3-Resultat](../benchmark/results/v3-20261006_8cpu_001.json),
  [v5-Resultat](../benchmark/results/v5-20261006_8cpu_001.json),
  [Ausführungsumgebung](../benchmark/results/environment-20261006_8cpu_001.json)
  und [Prüfsummen der Resultate](../benchmark/results/artifact-sha256.json).
- [Modell-Provenienz](../benchmark/contracts/model-provenance.json),
  [v3-Exportmanifest](../benchmark/contracts/jina-v3-merged-artifacts.json),
  [v5-Inferenzartefakte](../benchmark/contracts/jina-v5-artifacts.json) und
  [unveränderter v5-Thread-Paritätsbericht](../benchmark/results/v5-thread-parity-20261006_8cpu_001.json).
- Neue [Audit-Evidenz](../benchmark/contracts/adapter-audit-v1/evidence.json):
  gefilterte Container-Konfiguration, SHA256 der tatsächlich installierten/gemounteten
  Encoder-Quellen, erneut geprüfte Gewichte, Adapter-Tensorheader, Graph-Metadaten,
  Paketversionen und historische Prüfberichte. Keine Credentials oder Rohlogs.
- Byte-identische Konfigurationskopien:
  [v3-Modell](../benchmark/contracts/adapter-audit-v1/v3-model-config.json),
  [v3-Query](../benchmark/contracts/adapter-audit-v1/v3-query-adapter-config.json),
  [v3-Passage](../benchmark/contracts/adapter-audit-v1/v3-passage-adapter-config.json),
  [v5-Retrieval](../benchmark/contracts/adapter-audit-v1/v5-retrieval-adapter-config.json).
  Ihre Hashes entsprechen den bereits beim Benchmark gespeicherten Manifesten.

Auf dem AI-Host wurden ausschließlich die vorhandenen, bereits beendeten isolierten
Benchmark-Container, deren Dateien/Mounts und Modellartefakte gelesen. Die jeweils
17 Encoder-Python-Dateien stimmen mit den dokumentierten Commits überein:
v3 `48ce71550d5dad8c697facd3767aef8b4be97cc1`,
v5 `1938c72caa6102452ae0afa18ef86d9a95ead878`.
Alle verwendeten Modelldatei-Hashes stimmen mit den Benchmark-Manifesten überein.

Die Aktivierung ist durch diesen Codeabgleich, den zwingenden Load-/Embed-Pfad und
den abgeschlossenen erfolgreichen Lauf belegt. Ein damaliger Python-Objektdump von
`active_adapters` liegt nicht vor. Für diesen Audit wurde kein Modell neu geladen
und keine Inferenz ausgeführt. Die ONNX-Inspektion las nur Graph-Metadaten ohne
externe Gewichtsarrays. Das ist kein neuer numerischer Paritätstest.

## Tatsächlich ausgeführte Funktionsketten

Der [Benchmark-Runner](../src/uranus_research_service/controlled_runner.py) ist vom
HTTP-Request-Pfad des Research-Service getrennt:

```text
main → run → compatible → GET /version + GET /ready
Dokument: documents(snapshot) → POST /chunks → embed(..., kind="passage")
Query:    Fall.query                         → embed(..., kind="query")
embed → BenchHTTP/InternalClient._request → POST /embed
Encoder create_app: embed endpoint → process → backend.embed
```

`compatible()` prüft die exakten modellabhängigen Pins und Readiness vor der Arbeit;
der Runner prüft erneut nach der Ausführung. `embed()` prüft Antwortvertrag und
Vektoren. Die `/ready`-Antworten sind nicht als vollständige historische Dumps
archiviert; ihr erfolgreicher Check ist Voraussetzung für den gespeicherten Lauf.
`/version` allein wäre kein Nachweis der Adapter-Aktivierung.

**v3:** Encoder-App mit `ENCODER_BACKEND=onnx-merged` → Lifespan →
`MergedOnnxBackend.load()` → `verify_manifest()` → separate ONNX-Sessions für
`query`/`passage` → `MergedOnnxBackend.embed()` → `self._sessions[kind].run()` →
Mean-Pooling → L2. Der tatsächliche Container nutzt `/merged` als read-only
Exportwurzel, ONNX Runtime 1.30.0 CPU, Basic-Optimierung, 8 Intra-op-/1 Inter-op-Thread.
Siehe gepinnte [App](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/src/uranus_research_encoder/app.py),
[Backend](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/src/uranus_research_encoder/merged_onnx_backend.py)
und [Manifestprüfung](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/src/uranus_research_encoder/merged_artifacts.py).

**v5:** Externer `v5_benchmark_threads8.py`-Launcher → `create_app` mit injiziertem
`BenchmarkThreads8` → dessen `load()` → unverändertes `TorchBackend.load()` →
`cached_snapshot()` → native `Qwen3Config`/`Qwen3Model.from_pretrained()` →
`load_adapter(.../adapters/retrieval, adapter_name="retrieval")` →
`set_adapter("retrieval")` → CPU/eval → `loaded=True`.
Beim Embed: `TorchBackend.embed()` → Lock + `torch.inference_mode()` →
`set_adapter("retrieval")` → `_input(text, kind)` → Tokenizer → Modellforward →
letztes Nicht-Padding-Token → einmal `F.normalize`.
Siehe gepinntes [Modellmodul](https://github.com/sndcds/uranus-research-encoder/blob/1938c72caa6102452ae0afa18ef86d9a95ead878/src/uranus_research_encoder/model.py).

Der externe Launcher ändert nur das Thread-Profil und prüft 1-/8-Thread-Parität;
er ersetzt keine Adapterwahl. Launcher-SHA256:
`3d76905df23430fbcd031a1275b6d82ecafddfd86f93d691ef3f9e9283114921`.
Encoder-`model.py`-SHA256 im Lauf, Thread-Test und erneut gelesenen Source-Mount:
`84791df7e936f69ea61ccbdd974be8f6ad6e00217acd5969f709ef1cfc6e4ca8`.
Runtime: Torch 2.11.0+cpu, Transformers 5.17.0, PEFT 0.21.1, CPU/eager, float32.

## v3: zwei gemergte Retrieval-LoRAs

Die Source-Adapter heißen auf Disk `retrieval_query` und `retrieval_passage`.
Das Modell-Config nennt die entsprechenden Aufgaben `retrieval.query` und
`retrieval.passage`. HTTP verwendet `query` und `passage`. Diese unterschiedlichen
Schreibweisen bezeichnen keine zusätzlichen Adapter. Die im Config ebenfalls
enthaltenen natürlichsprachlichen Task-Instructions werden im ausgeführten
ONNX-Pfad **nicht** vor den Text gesetzt.

Beide LoRAs haben `r=4`, `lora_alpha=1`, `lora_dropout=0`, also Skalierung 1/4.
Targets: `word_embeddings`, `token_type_embeddings`, `q_proj`, `k_proj`, `v_proj`,
`o_proj`, `fc1`, `fc2`, `dense`. Jeder Source-Adapter enthält 294 BF16-Tensoren
für 147 Zielmatrizen. Die gepinnten Gewichte:

| Datei | SHA256 |
|---|---|
| `retrieval_query/adapter_model.safetensors` | `5b55dd1322ab7d62e62e3ee7626700b8e3d3e63238dc74fc2bb816542366e0a4` |
| `retrieval_passage/adapter_model.safetensors` | `b3483926d79143fbc21719ebc955d6ddb063d522c8993b886000ff24cf6bf15a` |
| `retrieval-query/model.onnx.data` | `3d653038a7c7be6d8176ff88e2ed535c6d63b7bf7197c13c9ad790d15ac41c21` |
| `retrieval-passage/model.onnx.data` | `3a2d9715e86aec888e2a1f8c4642307aafdb13276901c3a90b4b8d45554b7267` |

Der [Exportworker](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/scripts/export_merged_onnx.py)
lädt pro Exportprozess den passenden Adapter und aktiviert ihn.
[`merge_verified()`](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/src/uranus_research_encoder/merged_export.py)
prüft den erwarteten gewichteten LoRA-Delta-Merge, ersetzt die LoRA-Wrapper durch
Basislayer und verwirft verbleibende ungemergte Layer. Für Linear-Layer entspricht
dies `W + (alpha/r) * (B @ A)`; Embedding-Layer berücksichtigen die Transposition.
Die archivierten Merge-Audits bestätigen für beide Aufgaben 147/147 exakte
Gewichtsmatches und native Vorher-/Nachher-Parität. Das ist Export, kein Training.

Die tatsächlich verwendeten Graphen haben nur `input_ids` und `attention_mask`
als Inputs, Output `text_embeds`, jeweils 389 Initializer, keine LoRA-Initializer
und keine `task_id`-Nodes. Beide Graph-Protobuf-Dateien haben denselben Hash
`8b80f212fd9c37e3291d0ce4edc625d7dcccb00c5ad7eaddd7045593ce74e5c4`.
Sie referenzieren aber jeweils ihre **unterschiedliche** lokale `model.onnx.data`.
Die identischen Graph-Hashes bedeuten deshalb nicht identische Modellgewichte.

### Historische Adapter-Banks sind ein anderer Backend-Pfad

Der Encoder kennt zusätzlich das Backend `onnx`, das hier **nicht** ausgeführt
wurde. Dessen ursprünglicher Graph hat einen skalaren `task_id`-Input und
Adapter-Banks: Query Bank 0, Passage Bank 1. Der gepinnte
[ONNX-Artifact-Audit](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/validation/onnx-artifact-audit.json)
und [Audit-Code](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/scripts/audit_onnx.py)
belegen 294/294 bitgenaue Adapter-Tensoren je Aufgabe gegen die PEFT-Dateien,
maximale Differenz 0, sowie 198 Task-Gathers. Diese Bank-Prüfung darf nicht mit
dem tatsächlich verwendeten `onnx-merged`-Pfad verwechselt werden.

Das Exportmanifest erfasst außerdem Jina-Adapter `classification`, `separation`
und `text_matching`; keiner wird von den beiden Benchmark-Sessions ausgewählt.

### Grenze des historischen numerischen Paritätsnachweises

Der ältere [Merged-ONNX-Paritätsbericht](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/validation/server-merged-onnx-basic-parity.json)
meldet Erfolg, identische Rankings und maximale Vektordifferenz
`3.948807716369629e-7`. Er referenziert jedoch Exportmanifest
`aff3546a806a98ac8d730be33f24db43874e3c26ca37f94b3ab9dca85959fd1c`
([archiviertes Exportmanifest](https://github.com/sndcds/uranus-research-encoder/blob/48ce71550d5dad8c697facd3767aef8b4be97cc1/validation/server-merged-export-manifest.json))
und Graph-Hash `d728e7ca6f1fb96ebd58f197ac000e7bc63a2426537a1886bc8358a357cdf49d`.
Das tatsächlich verwendete Exportmanifest hat Hash
`b7e54abad7b74fb49a579475b6aa2c4c2fa191c8fc5c5539694dbcfbbd7604ce`
und den oben genannten anderen Graph-Hash. Die externen Gewichtsdateien und
Merge-Audits stimmen dagegen bytegenau überein.

Damit ist die Adapter-/Gewichtsidentität belegt, aber der historische Bericht
ist **kein numerischer Paritätsnachweis für die exakten Benchmark-Graph-Dateien**.
Der Audit erklärt den Graph-Unterschied nicht ohne weitere Evidenz für harmlos.
Auch das Exportfeld `release_parity` wurde nach Erstellung nicht zu einem solchen
Nachweis aktualisiert. Für eine weitergehende Aussage über exakte native/ONNX-
Äquivalenz wäre eine separate Prüfung dieser Graphen nötig. Sie wurde hier nicht
ausgeführt; Ergebnisse und bestehende Reproduktionsdokumente wurden nicht verändert.

## v5: tatsächlich geladener PEFT-LoRA

Quelle ist `adapters/retrieval` innerhalb des oben gepinnten Jina-v5-Snapshots.
Es gibt kein zusätzliches Adapter-Repository. Die Datei
`adapter_config.json` hat SHA256
`f37c5d6dd368e2675e54e01b685252d4d44eed042c773a48f56ebe1565cd0320`,
`adapter_model.safetensors` hat SHA256
`2bc6ab71895eb04664e4d995ee29e1620603f3a3fc4dfc573bc2383dfc85bb94`.
Der Config-Wert `revision=null` bedeutet hier keine ungepinnte Auflösung:
`load_adapter()` erhält den absoluten lokalen Pfad im exakten Snapshot; dessen
Config und Gewichte sind zusätzlich per SHA256 gebunden.

Typ `LORA`, Task `FEATURE_EXTRACTION`, `r=32`, `lora_alpha=32`, Skalierung 1,
`lora_dropout=0.1`, `bias="none"`, keine `modules_to_save`, kein DoRA/rsLoRA.
Der Adapter enthält 392 BF16-Tensoren: A/B für sieben Targets in allen 28 Layern.
Targets: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`.
Inferenz verwendet float32 und `model.eval()`; der konfigurierte Dropout ist
im Eval-Modus ausgeschaltet. Die Base-Gewichte haben SHA256
`045fa75ff963a528cda2589fb1ca0a9ad848b53511780ed4f08f6fe10f6167c3`.

Der Loader prüft Config, fehlende/unerwartete Modellgewichte und Adaptergewichte
und setzt `loaded=True` erst nach erfolgreichem Laden und Aktivieren. Jeder
Embed-Aufruf aktiviert `retrieval` erneut innerhalb des Locks. Ein fehlender
Adapter führt zum Fehler, nicht zu Base-only-Inferenz.

Die tatsächlich installierte Transformers-Integration `PeftAdapterMixin` wurde
als Quelltext gelesen und gehasht. `load_adapter()` verwendet dort PEFTs
`inject_adapter_in_model` und lädt die Adaptergewichte; `set_adapter()` aktiviert
die `BaseTunerLayer`. Die Modellklasse bleibt `Qwen3Model`. Ein Test ausschließlich
auf `isinstance(model, PeftModel)` wäre hier irreführend: Transformers integriert
PEFT direkt in die Modellklasse. Die Aktivierung hängt nicht vom Vorhandensein
eines äußeren `PeftModel`-Wrappers ab.

Query und Document verwenden denselben Adapter, dieselben Layer und dasselbe
Pooling. Ihre Unterscheidung ist der tatsächliche Eingabetext mit `Query: ` bzw.
`Document: `. Es gibt keinen separaten Retrieval-Task-Token und keinen `task_id`;
die normalen Tokenizer-Spezialtokens bleiben erhalten. Der HTTP-Typ heißt auch
für v5 `passage`, nicht `document`. Die Präfixe gehen bereits in die Tokenzählung
für das unveränderte Chunk-Contract `sections-480-overlap64-v2` ein.

## Weitere Artefakte, Downloads und eigenes Training

Der aktuell gemountete v5-Snapshot enthält 22 Dateien, darunter zusätzlich die
Adapter `classification`, `clustering`, `text_matching` und Repository-Python.
Die sechs Dateien in `jina-v5-artifacts.json` beschreiben die ausgewählten
Inferenzartefakte, **kein vollständiges Cache-Inventar**. Die dortigen Zähler
`repository_code_files=0` und `other_task_adapters=0` dürfen deshalb nicht als
Beweis ihrer physischen Abwesenheit im Cache gelesen werden. Wann die zusätzlichen
Dateien relativ zum Benchmark in den Cache gelangten, wurde nicht festgestellt.

Sie werden vom geprüften Uranus-Code nicht geladen: Er entfernt `auto_map` und
Wrapper-Metadaten, erzeugt eine native `Qwen3Config`, verwendet `Qwen3Model` und
lädt gezielt `adapters/retrieval`. `trust_remote_code=False` gilt für den
Tokenizer. Der als Text inspizierte Jina-Wrapper würde weitere Adapter laden,
ist aber nicht der ausgeführte Uranus-Pfad. Cache-Präsenz ist keine Aktivierung.
`allow_patterns` löscht keine bereits vorhandenen Cache-Dateien.

Die gelesene v5-Hub-Wurzel enthält nur das gepinnte Jina-v5-Repository. Runtime-
Loads verwenden `local_files_only=True`, `HF_HUB_OFFLINE=1` und
`TRANSFORMERS_OFFLINE=1`. Base und Adapter stammen aus demselben lokalen Snapshot;
`Qwen3Model` bezeichnet eine installierte Transformers-Klasse, keinen zusätzlichen
Download eines Qwen-Repositories. v3 lädt nur den lokalen geprüften Export.
Der getrennte Provisionierungs-Code `prefetch_model.py` pinnt Repository und
Revision; er ist nicht Teil der Inferenzkette.

Damit sind die verwendeten Modell-/Adapter-Abhängigkeiten anhand Code, Mounts
und Dateihashes geschlossen nachvollziehbar. Es liegt keine historische
Paketaufzeichnung des Netzwerkverkehrs vor; behauptet wird weder eine vollständige
Inventur aller Caches auf dem Host noch, dass dort niemals andere Downloads
stattgefunden hätten.

Die verwendeten Adapter sind Jina-veröffentlichte Retrieval-Gewichte. Bei v3
entstehen daraus lokale, überprüfte Merge-Artefakte. In den untersuchten
versionierten Python-/Markdown-/Projektdateien von Service, Encoder, Planner und
Admin wurden keine Kulturbytes-/Uranus-Trainingspipeline und keine im Benchmark
verwendeten eigenen LoRA-Gewichte gefunden. Die konkret untersuchten Commits und
Suchgrenzen stehen in `evidence.json` unter `training_search`. Kleine synthetische
PEFT-Testadapter im Encoder prüfen die Implementierung; sie sind kein auf
Kulturbytes-Daten trainierter oder im Benchmark verwendeter Adapter.
Das ist eine Aussage über die belegten Pfade und untersuchten Repositories,
keine Behauptung über sämtliche denkbaren externen Trainingsaktivitäten.

## Interpretation und Vergleichbarkeit

Die technische Adapter-Konfiguration entspricht **A**, mit gemergter v3-LoRA
und dynamisch aktivierter v5-LoRA. Hinsichtlich Adapter-/Task-Auswahl ist es ein
Vergleich beider Retrieval-Konfigurationen, kein versehentlicher Vergleich von
v3 Retrieval gegen v5 Base. v3 hat zwei spezialisierte Adapter, v5 einen gemeinsamen
Adapter plus Rollenpräfixe. Unterschiedliche Ränge, Targets, Pooling, Tokenizer und
Backends sind Teil dieses Modell-/Retrievalsystem-Vergleichs; er isoliert weder
LoRA-Wirkung noch Base-Architektur als einzelne Ursache.

**Ändert das die Interpretation des abgeschlossenen Benchmarks?** Die Adapter-
Klärung begründet keine Neuberechnung und keine Änderung der gespeicherten
Metriken oder Gates. Das bestehende vorläufige Gate-Ergebnis bleibt unverändert;
eine schlechtere/bessere Zahl darf insbesondere nicht nachträglich mit einem
angeblich fehlenden v5-Adapter erklärt werden. Die zusätzliche Evidenzgrenze beim
v3-Graph-Paritätstest schränkt jedoch die Aussage ein, dass die exakten exportierten
Benchmark-Graphen bereits durch diesen historischen Test numerisch zertifiziert
seien. Eine uneingeschränkte solche Behauptung ist nicht belegt.

Der gleiche eingefrorene Corpus, Eligibility und Evaluator sind in den bestehenden
[Input-/Result-Prüfungen](../benchmark/results/input-and-result-audit-20261006_8cpu_001.json)
und im [Vergleichsartefakt](../benchmark/results/v3-v5-comparison-20261006_8cpu_001.json)
dokumentiert. Dieser Audit fügt keine neue Qualitätsbewertung hinzu.
Der Datensatz bleibt vorläufig, die sechs No-hit-Hypothesen bleiben ungeklärt;
`semantic_query=false`, keine Aktivierungs- oder Produktionsfreigabe.

## Regression und Verifikation

[Sechs Offline-Tests](../tests/test_adapter_audit.py) binden die kopierten Adapter-
Configs an die ursprünglichen Hashes, Modell-/Backend-Pins an den Runner, installierte
Encoder-Quellen an die Ausführungs-Provenienz, v3-Tasks an getrennte Exportgewichte
und v5 an echten Retrieval-LoRA plus Präfixe. Auch die historische Graph-Paritätslücke
und die Unterscheidung zwischen Cache-Präsenz und Verwendung bleiben explizit
geprüft. Die Tests laden keine Modelle und ersetzen keinen Modell-Paritätstest.
Alle bestehenden Resultat-Hashes werden zusätzlich überprüft.

Prüfbefehle: `uv sync --locked --offline`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run pytest -q`, `git diff --check`.
Lokal: **471 passed, 24 skipped**, darunter sechs neue Audit-Tests; Locked-Offline-Sync,
Ruff, Format und Diff-Prüfung erfolgreich. Die ausgelassenen Integrationstests sind
kein lokaler Live-Nachweis; CI führt PostGIS/Qdrant/Admin-Parität und Docker isoliert
aus. Alle fünf eingefrorenen Inputs stimmen mit ihren Pins und dem Benchmark-Head
bytegenau überein; alle Resultate sind unverändert.

Die neuen Dateien sind ausschließlich Audit-Dokumentation, kleine öffentliche
Config-/Evidenz-Fixtures und Tests. Benchmark-Eingaben, Resultate, Runtime, Labels,
Gates, Encoder-/Planner-/Admin-Code und `semantic_query` bleiben unverändert.
Keine Container gestartet, keine Inferenz, keine Modell-Downloads, kein Training,
keine DB-/Qdrant-Zugriffe, kein Reindex, kein Deployment, kein Aliaswechsel,
keine Service-Restarts und kein Merge von PR #7 in diesem Audit.
