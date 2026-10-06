"""Measure only the dedicated Encoder PID while the isolated benchmark driver runs."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def sample(pid):
    status = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value, _ = line.split()
            status[key[:-1]] = int(value) * 1024
    stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    status["cpu_seconds"] = (int(stat[11]) + int(stat[12])) / os.sysconf("SC_CLK_TCK")
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["v3", "v5"], required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--cpus", type=int, choices=[2, 8], default=2)
    args = parser.parse_args()
    suffix = "8cpu-" if args.cpus == 8 else ""
    name = f"kulturbytes-benchmark-{args.model}-{suffix}20261006"
    profile = "8cpu-8threads" if args.cpus == 8 else "2cpu-original-threads"
    pid = int(
        subprocess.check_output(
            ["sudo", "-n", "docker", "inspect", "--format", "{{.State.Pid}}", name], text=True
        )
    )
    config = json.loads(
        subprocess.check_output(["sudo", "-n", "docker", "inspect", name], text=True)
    )[0]["HostConfig"]
    if config["NanoCpus"] != args.cpus * 10**9:
        raise SystemExit("benchmark_cpu_limit_mismatch")
    before = sample(pid)
    started = time.perf_counter()
    child = subprocess.Popen(
        [
            ".venv/bin/python",
            "-m",
            "uranus_research_service.controlled_runner",
            "run",
            "--model",
            args.model,
            "--build",
            args.build,
        ],
        env={**os.environ, "CONTROLLED_BENCHMARK_PROFILE": profile},
    )
    rss = []
    while child.poll() is None:
        rss.append(sample(pid)["VmRSS"])
        time.sleep(1)
    after = sample(pid)
    elapsed = time.perf_counter() - started
    result = {
        "model": args.model,
        "container": name,
        "encoder_startup_loaded_rss_bytes": before["VmRSS"],
        "encoder_end_rss_bytes": after["VmRSS"],
        "encoder_peak_rss_bytes": after["VmHWM"],
        "encoder_sampled_peak_rss_bytes": max(rss, default=before["VmRSS"]),
        "encoder_cpu_seconds": after["cpu_seconds"] - before["cpu_seconds"],
        "encoder_cpu_percent_one_core_basis": 100
        * (after["cpu_seconds"] - before["cpu_seconds"])
        / elapsed,
        "wall_seconds": elapsed,
        "sample_interval_seconds": 1,
        "driver_cpu_included": False,
        "driver_exit_code": child.returncode,
        "execution_profile": profile,
        "container_cpu_limit": args.cpus,
        "container_memory_limit_bytes": config["Memory"],
        "container_memory_plus_swap_bytes": config["MemorySwap"],
        "startup_definition": "loaded process before corpus build; not pre-load RSS",
        "steady_state_definition": "resident set after all queries; includes allocator state",
    }
    path = Path(f"benchmark/results/resources-{args.model}-{args.build}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    raise SystemExit(child.returncode)


if __name__ == "__main__":
    main()
