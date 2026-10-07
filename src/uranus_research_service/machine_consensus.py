"""Machine-only agreement/sealing before retrieval deblinding. Never reads rankings."""

from collections import Counter, defaultdict
from itertools import combinations

from uranus_research_service.machine_judge import (
    PASSES,
    Judgment,
    atomic_new,
    digest,
    load_blind,
    prompt_text,
    read,
    read_lines,
    record_identity,
    require,
    sha,
    validate_judgment,
)

CAVEAT = (
    "Exploratory machine-consensus judgments, not human-reviewed or human-approved labels, "
    "not gold labels or ground truth, and not production approval. "
    "Correlated model errors remain possible."
)


def classify(answers, minimum=0.8):
    grades = [r["grade"] for r in answers]
    confidences = [r["confidence"] for r in answers]
    if any(r["state"] != "graded" for r in answers):
        return {"classification": "unresolved", "strict": None, "majority": None}
    counts = Counter(grades)
    grade, n = counts.most_common(1)[0]
    spread = max(grades) - min(grades)
    kind = (
        "strong_consensus"
        if n == 3
        else "material_disagreement"
        if spread >= 2
        else "adjacent_disagreement"
    )
    return {
        "classification": kind,
        "raw_majority": grade if n >= 2 else None,
        "strict": grade if n == 3 else None,
        "majority": grade
        if n == 3 or (n == 2 and spread <= 1 and min(confidences) >= minimum)
        else None,
    }


def machine_agreement(triples):
    pairwise = {}
    for a, b in combinations(range(3), 2):
        matrix = [[0] * 4 for _ in range(4)]
        state_disagreement = 0
        for rows in triples:
            x, y = rows[a], rows[b]
            state_disagreement += x["state"] != y["state"]
            if x["state"] == y["state"] == "graded":
                matrix[x["grade"]][y["grade"]] += 1
        n = sum(map(sum, matrix))
        exact = sum(matrix[i][i] for i in range(4))
        adjacent = sum(matrix[i][j] for i in range(4) for j in range(4) if abs(i - j) <= 1)
        expected = (
            sum(sum(matrix[i]) * sum(row[i] for row in matrix) for i in range(4)) / n**2
            if n
            else None
        )
        observed = exact / n if n else None
        pairwise[f"{PASSES[a]}:{PASSES[b]}"] = {
            "graded_pairs": n,
            "confusion_matrix_0_3": matrix,
            "raw_exact_agreement": observed,
            "within_one_agreement": adjacent / n if n else None,
            "state_disagreement": state_disagreement,
            "cohen_kappa": (observed - expected) / (1 - expected) if n and expected < 1 else None,
        }
    return {
        "name": "inter-run machine agreement",
        "pairs": pairwise,
        "all_three_exact": sum(
            all(r["state"] == "graded" for r in rows) and len({r["grade"] for r in rows}) == 1
            for rows in triples
        ),
        "confidence_by_pass": {
            name: {
                "min": min(rows[i]["confidence"] for rows in triples),
                "mean": sum(rows[i]["confidence"] for rows in triples) / len(triples),
                "max": max(rows[i]["confidence"] for rows in triples),
            }
            for i, name in enumerate(PASSES)
        },
        "limitations": "Machine runs, not human annotators. Correlated errors and class imbalance "
        "limit kappa; null if undefined.",
    }


def calculate(packet, sides, strata, minimum):
    require(set(strata) == {p["annotation_id"] for p in packet}, "bias_strata_identity")
    for value in strata.values():
        require(set(value) == {"language", "category", "text_length_bin"}, "bias_metadata_leak")
    sets = {"strict": [], "majority": [], "disagreements": []}
    triples, groups = [], defaultdict(list)
    for candidate in packet:
        aid = candidate["annotation_id"]
        rows = [side[aid] for side in sides]
        triples.append(rows)
        assessment = classify(rows, minimum)
        common = {
            "annotation_id": aid,
            "classification": assessment["classification"],
            "confidence": {
                "min": min(r["confidence"] for r in rows),
                "mean": sum(r["confidence"] for r in rows) / 3,
            },
            "provenance": "machine-consensus-not-human",
        }
        for mode in ("strict", "majority"):
            if assessment[mode] is not None:
                sets[mode].append({**common, "grade": assessment[mode], "consensus_type": mode})
        sets["disagreements"].append(
            {
                **common,
                "grades": [r["grade"] for r in rows],
                "states": [r["state"] for r in rows],
                "strict_accepted": assessment["strict"] is not None,
                "majority_accepted": assessment["majority"] is not None,
            }
        )
        for field, value in strata[aid].items():
            groups[f"{field}:{value}"].append(rows)
    bias = {}
    for name, rows in sorted(groups.items()):
        bias[name] = {
            "pair_count": len(rows),
            "grades_by_pass": {
                p: dict(Counter(str(r[i]["grade"]) for r in rows if r[i]["state"] == "graded"))
                for i, p in enumerate(PASSES)
            },
            "unresolved_by_pass": {
                p: sum(r[i]["state"] != "graded" for r in rows) for i, p in enumerate(PASSES)
            },
            "agreement": machine_agreement(rows),
        }
    return sets, machine_agreement(triples), bias


def seal(work, destination):
    require(not destination.exists(), "new_seal_directory_required")
    plan, packet = load_blind(work / "blind")
    sides, run_hashes = [], {}
    for name in PASSES:
        path = work / "full" / name / f"{name}.jsonl"
        rows = read_lines(path)
        identity = record_identity(
            plan, name, plan["run_ids"][name], "full", prompt_text(work / "blind", name)
        )
        require(
            len(rows) == len(packet) and len({r["annotation_id"] for r in rows}) == len(packet),
            "incomplete_full_run",
        )
        side = {r["annotation_id"]: r for r in rows}
        for p in packet:
            row = side[p["annotation_id"]]
            require(all(row.get(k) == v for k, v in identity.items()), "run_identity")
            validate_judgment({k: row[k] for k in Judgment.model_fields}, p)
        sides.append(side)
        run_hashes[name] = sha(path.read_bytes())
    strata = read(work / "bias-strata.json")
    require(digest(strata) == plan["bias_strata_sha256"], "bias_strata_changed")
    policy = read(work / "blind/policy-v1.json")
    sets, agreement, bias = calculate(packet, sides, strata, policy["majority_min_confidence"])
    destination.mkdir(parents=True)
    for mode, rows in sets.items():
        atomic_new(destination / f"{mode}.jsonl", rows, jsonl=True)
    atomic_new(destination / "inter-run-agreement.json", agreement)
    atomic_new(destination / "pre-deblinding-bias.json", bias)
    manifest = {
        "schema_version": "phase2dm-machine-seal-v1",
        "status": "sealed-machine-only",
        "caveat": CAVEAT,
        "plan_sha256": digest(plan),
        "package_sha256": plan["package_sha256"],
        "run_sha256": run_hashes,
        "pair_count": len(packet),
        "bias_strata_sha256": digest(strata),
        "files": {p.name: sha(p.read_bytes()) for p in sorted(destination.iterdir())},
    }
    atomic_new(destination / "seal.json", manifest)  # Last publication enables deblinding.
    return manifest


def verify_seal(work, directory):
    plan, _ = load_blind(work / "blind")
    manifest = read(directory / "seal.json")
    require(
        manifest["status"] == "sealed-machine-only" and manifest["plan_sha256"] == digest(plan),
        "seal_identity",
    )
    require(
        set(manifest["files"])
        == {
            "strict.jsonl",
            "majority.jsonl",
            "disagreements.jsonl",
            "inter-run-agreement.json",
            "pre-deblinding-bias.json",
        },
        "seal_files",
    )
    for name, checksum in manifest["files"].items():
        require(sha((directory / name).read_bytes()) == checksum, "sealed_content_changed")
    for name in PASSES:
        require(
            sha((work / "full" / name / f"{name}.jsonl").read_bytes())
            == manifest["run_sha256"][name],
            "sealed_run_changed",
        )
    return manifest
