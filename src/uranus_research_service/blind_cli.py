"""Offline operator CLI: python -m uranus_research_service.blind_cli --help."""

import argparse
from pathlib import Path

from uranus_research_service.blind_expansion import (
    CONFIG_PATH,
    coverage,
    export,
    read,
    write_new,
)
from uranus_research_service.blind_review import (
    Adjudication,
    Approval,
    ReviewBatch,
    agreement,
    conflicts,
    freeze,
    import_batch,
    prepare_freeze,
    review_inputs_hash,
    validate_batch,
)
from uranus_research_service.controlled_evaluation import lines, require
from uranus_research_service.semantic_manifest import digest


def checked_package(root, directory):
    bundle, packet, runs = export(root)
    require(read(directory / "blind-mapping.json") == bundle, "package_changed")
    require(lines(directory / "blind-candidates.jsonl") == packet, "blind_packet_changed")
    require(
        read(directory / "annotation-package.json")["packet_sha256"] == digest(packet),
        "packet_digest_changed",
    )
    return bundle, packet, runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("export", "validate", "import", "agreement", "adjudication", "freeze")
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--package", type=Path)
    parser.add_argument("--a", type=Path)
    parser.add_argument("--b", type=Path)
    parser.add_argument("--adjudicated", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        bundle, packet, runs = export(args.root)
        dest = args.output
        require(not dest.exists(), "export_destination_must_be_new")
        write_new(dest / "blind-mapping.json", bundle)
        write_new(dest / "blind-candidates.jsonl", packet, jsonl=True)
        write_new(dest / "annotation-schema.json", ReviewBatch.model_json_schema())
        write_new(dest / "adjudication-schema.json", Adjudication.model_json_schema())
        write_new(dest / "approval-schema.json", Approval.model_json_schema())
        write_new(dest / "sampling-plan.json", read(args.root / CONFIG_PATH))
        write_new(dest / "judgment-coverage-before.json", coverage(runs, bundle))
        write_new(
            dest / "annotation-package.json",
            {
                "schema_version": "phase2d-blind-package-v1",
                "package_sha256": digest(bundle),
                "packet_sha256": digest(packet),
                "count": len(packet),
            },
        )
        write_new(
            dest / "manifest.json",
            {
                "status": "draft",
                "human_annotations": 0,
                "package_sha256": digest(bundle),
                "query_count": len(bundle["selection"]["cases"]),
                "pair_count": len(packet),
                "input_manifest_sha256": bundle["input_manifest_sha256"],
            },
        )
        return
    require(args.package is not None and args.a is not None, "package_and_a_required")
    bundle, packet, runs = checked_package(args.root, args.package)
    a = validate_batch(read(args.a), bundle, packet)
    if args.command == "validate":
        result = {"status": "valid-draft", "annotator": a.annotator, "answers": len(a.answers)}
    elif args.command == "import":
        result = import_batch(read(args.a), bundle, packet)
    else:
        require(args.b is not None, "second_independent_review_required")
        b = validate_batch(read(args.b), bundle, packet)
        old = {c["case_id"]: c["grades"] for c in runs[0]["cases"]}
        if args.command == "agreement":
            result = agreement(a, b, bundle, packet)
        elif args.command == "adjudication":
            result = {
                "status": "draft",
                "package_sha256": digest(bundle),
                "review_inputs_sha256": review_inputs_hash(a, b),
                "conflicts": conflicts(a, b, bundle, packet, old),
            }
        else:
            require(args.adjudicated is not None, "human_adjudication_file_required")
            draft = prepare_freeze(a, b, read(args.adjudicated), bundle, packet, old)
            # Without approval, export only a reviewable draft (not a frozen judgment set).
            result = freeze(draft, read(args.approval)) if args.approval else draft
    write_new(args.output, result)


if __name__ == "__main__":
    main()
