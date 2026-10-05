"""Prepare a hash-checked, locked wheelhouse before an offline Docker build.

Run with Python 3.13 on the same OS/architecture as the target image.
Networking occurs only during this explicit build step, never in the service.
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "wheelhouse"


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    if TARGET.exists():
        raise SystemExit("wheelhouse already exists; review/remove it before rebuilding")
    TARGET.mkdir()
    run(
        "uv",
        "export",
        "--locked",
        "--no-dev",
        "--no-emit-project",
        "--format",
        "requirements-txt",
        "--output-file",
        str(TARGET / "requirements.txt"),
    )
    run(
        "uv",
        "run",
        "--no-project",
        "--with",
        "pip",
        "--python",
        "3.13",
        "python",
        "-m",
        "pip",
        "download",
        "--require-hashes",
        "--only-binary=:all:",
        "--requirement",
        str(TARGET / "requirements.txt"),
        "--dest",
        str(TARGET),
    )
    run("uv", "build", "--wheel", "--out-dir", str(TARGET))


if __name__ == "__main__":
    main()
