"""Opt-in Docker mT5 real-inference and cgroup memory probe; synthetic input only.

Needs a running *current-source* container and model weights/HF connectivity.
Unlike /health or Document Query, this exercises mT5 generation. It is NOT
semantic-quality signoff or a concurrency load-test certification.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

_CONSTRAINTS = Path(__file__).resolve().parents[1] / "constraints/docker-linux-cpu-2026-11.txt"

TEXT = (
    "سازمان هواشناسی اعلام کرد که بارش باران در روزهای آینده در شمال کشور "
    "افزایش می‌یابد. کارشناسان توصیه کردند رانندگان پیش از سفر شرایط جاده‌ها "
    "را بررسی کنند و به هشدارهای هواشناسی توجه داشته باشند."
)
# Cgroup readings are obtained *inside* the running container, not from host RAM.
_CGROUP_SCRIPT = """\
import json
from pathlib import Path
base = Path('/sys/fs/cgroup')
def read(*names):
    for name in names:
        try:
            text = (base / name).read_text().strip()
            return int(text) if text != 'max' else None
        except (FileNotFoundError, PermissionError, ValueError):
            pass
    return None
print(json.dumps({'current_bytes': read('memory.current', 'memory/memory.usage_in_bytes'),
                  'peak_bytes': read('memory.peak', 'memory/memory.max_usage_in_bytes'),
                  'limit_bytes': read('memory.max', 'memory/memory.limit_in_bytes')}))
"""


def _local_url(value: str) -> str:
    parts = urlsplit(value)
    if (parts.scheme != "http" or parts.hostname not in ("127.0.0.1", "localhost")
            or parts.username is not None or parts.password is not None
            or parts.path not in ("", "/") or parts.query or parts.fragment
            or not 1 <= (parts.port or 0) <= 65535):
        raise ValueError("--base-url must be plain http://127.0.0.1:<port> or localhost")
    return value.rstrip("/")


def _docker_value(container: str, args: list[str]) -> str | None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", container):
        raise ValueError("invalid Docker container name")
    try:
        run = subprocess.run(
            ["docker", *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return run.stdout.strip() if run.returncode == 0 else None


def _cgroup_memory(container: str) -> dict | None:
    output = _docker_value(container, ["exec", container, "python", "-c", _CGROUP_SCRIPT])
    if not output:
        return None
    try:
        value = json.loads(output)
        if not isinstance(value, dict):
            return None
        return {key: val if type(val) is int and val >= 0 else None
                for key, val in ((key, value.get(key))
                                 for key in ("current_bytes", "peak_bytes", "limit_bytes"))}
    except (ValueError, TypeError):
        return None


def _dependency_snapshot(container: str) -> dict:
    """Check installed runtime versions against the audited Docker snapshot."""
    raw = _docker_value(container, ["exec", container, "python", "-m", "pip", "freeze", "--all"])
    if raw is None or not _CONSTRAINTS.is_file():
        return {"status": "NOT_MEASURED", "mismatch_names": []}

    def parse(lines):
        result = {}
        for line in lines:
            if line and not line.startswith("#") and "==" in line:
                name, version = line.split("==", 1)
                result[re.sub(r"[-_.]+", "-", name.strip()).casefold()] = version.strip()
        return result

    pinned_bytes = _CONSTRAINTS.read_bytes()
    pinned = parse(pinned_bytes.decode("utf-8").splitlines())
    installed = parse(raw.splitlines())
    mismatches = sorted(name for name, expected in pinned.items()
                        if installed.get(name) != expected)
    return {
        "status": "MATCH" if pinned and not mismatches else "MISMATCH",
        "pin_count": len(pinned),
        "mismatch_names": mismatches,  # only package names, never private text
        "constraints_sha256": hashlib.sha256(pinned_bytes).hexdigest(),
    }


def _request_summary(base_url: str, timeout: float, phase: str) -> dict:
    started = time.perf_counter()
    result = {"phase": phase, "http_status": None, "elapsed_ms": None,
              "summary_characters": None, "summary_sha256": None,
              "error_type": None}
    try:
        with httpx.Client(
            base_url=base_url, timeout=httpx.Timeout(timeout, connect=15.0),
            trust_env=False,
        ) as client:
            response = client.post(
                "/api/v1/summarization/text",
                json={"text": TEXT, "summary_length": "medium"},
            )
        result["http_status"] = response.status_code
        if response.status_code != 200:
            result["error_type"] = "UnexpectedHTTPStatus"
            return result
        payload = response.json()
        summary = payload.get("summary") if isinstance(payload, dict) else None
        if (not isinstance(summary, str) or not summary.strip()
                or payload.get("summary_length") != "medium"
                or payload.get("input_characters") != len(TEXT)
                or payload.get("output_characters") != len(summary)):
            result["error_type"] = "InvalidSummaryContract"
            return result
        result["summary_characters"] = len(summary)
        result["summary_sha256"] = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as error:
        # Never include exception message: it could embed an untrusted URL/body.
        result["error_type"] = type(error).__name__
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result


def run(base_url: str, container: str, timeout: float, parallel: int) -> dict:
    if not math.isfinite(timeout) or not 10 <= timeout <= 3600:
        raise ValueError("--timeout must be 10..3600 seconds")
    if type(parallel) is not int or not 1 <= parallel <= 4:
        raise ValueError("--parallel must be 1..4")
    url = _local_url(base_url)
    before = _cgroup_memory(container)
    image_id = _docker_value(container, ["inspect", "--format", "{{.Image}}", container])
    dependency_snapshot = _dependency_snapshot(container)
    observations: list[dict] = []
    try:
        with httpx.Client(
            base_url=url, timeout=httpx.Timeout(15.0, connect=10.0), trust_env=False,
        ) as client:
            health = client.get("/api/v1/health")
            health_http = health.status_code
    except httpx.HTTPError:
        health_http = None
    if health_http == 200:
        observations.append(_request_summary(url, timeout, "first_observed"))
        if observations[-1]["summary_characters"] is not None:
            observations.append(_request_summary(url, timeout, "warm_repeat"))
        if len(observations) == 2 and observations[-1]["summary_characters"] is not None:
            if parallel > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
                    futures = [executor.submit(_request_summary, url, timeout,
                                               f"concurrent_{i + 1}")
                               for i in range(parallel)]
                    observations.extend(future.result() for future in futures)
    after = _cgroup_memory(container)
    ok = (
        health_http == 200 and len(observations) >= 2
        and all(v["http_status"] == 200 and v["summary_characters"] is not None
                for v in observations)
    )
    return {
        "schema_version": 1,
        "scope": "real_mt5_docker_structural_and_resource_probe",
        "status": "STRUCTURAL_PASS" if ok else "BLOCKED",
        "model_inference_exercised": bool(observations),
        "health_http_status": health_http,
        "container_image_id": image_id,
        "container_name": container,
        "dependency_snapshot": dependency_snapshot,
        "memory_before": before,
        "memory_after": after,
        "observations": observations,
        "peak_memory_semantics": "Cgroup lifetime high-water mark; not isolated to this test",
        "semantic_accuracy": "NOT_REVIEWED",
        "production_go": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8003")
    parser.add_argument("--container", default="mt5-stage13-preview")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run(args.base_url, args.container, args.timeout, args.parallel)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as file:
            json.dump(report, file, ensure_ascii=False, sort_keys=True, indent=2)
            file.write("\n")
    except (OSError, ValueError) as error:
        parser.exit(2, f"Production probe configuration/output failed: {type(error).__name__}\n")
    print(f"Model probe: {report['status']} (not semantic quality); report: {args.output}")
    return 0 if report["status"] == "STRUCTURAL_PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
