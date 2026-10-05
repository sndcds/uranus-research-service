"""Explicit maintainer check using pinned sibling checkouts, never a runtime dependency.

Each checkout needs its own installed environment. Only schemas/version constants are
imported, with no service startup, credentials, model loading or network requests.
"""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    if isinstance(value, dict):
        return {k: sorted(v) if k == "enum" else canonical(v) for k, v in value.items()}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("admin", "planner", "encoder"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    pins = json.loads((ROOT / "contracts/sources.json").read_text())
    for name in ("admin", "planner", "encoder"):
        root = getattr(args, name).resolve()
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        if sha != pins["repositories"][name]:
            raise SystemExit(name + " checkout revision differs from pin")
        working = root / "backend" if name == "admin" else root
        if name == "encoder":
            code = (
                "from uranus_research_encoder.version import metadata; "
                "import json; print(json.dumps(metadata()))"
            )
            result = json.loads(
                subprocess.check_output(
                    [str(working / ".venv/bin/python"), "-c", code], cwd=working, text=True
                )
            )
            expected = json.loads((ROOT / "contracts/encoder/expected-version.json").read_text())
            if result != expected:
                raise SystemExit("Encoder metadata drift")
            for path in (ROOT / "contracts/encoder").glob("*.json"):
                if path.name == "expected-version.json":
                    continue
                if canonical(
                    json.loads((root / "contracts" / path.name).read_text())
                ) != json.loads(path.read_text()):
                    raise SystemExit("Encoder schema drift")
        else:
            prefix = "app.research.wire" if name == "admin" else "research_planner"
            for number in range(9, 14):
                code = (
                    "import importlib,json; "
                    f'm=importlib.import_module("{prefix}.research_v{number}_schema"); '
                    f"print(json.dumps(m.PlanResponseV{number}.model_json_schema()))"
                )
                actual = json.loads(
                    subprocess.check_output(
                        [str(working / ".venv/bin/python"), "-c", code], cwd=working, text=True
                    )
                )
                filename = (
                    f"admin/planner-v{number}-response.json"
                    if name == "admin"
                    else f"planner/v{number}-response.json"
                )
                if canonical(actual) != json.loads((ROOT / "contracts" / filename).read_text()):
                    raise SystemExit(name + " response schema drift")
        print(name + ": pinned contract parity passed")


if __name__ == "__main__":
    main()
