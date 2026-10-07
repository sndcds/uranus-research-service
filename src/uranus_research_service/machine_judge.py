"""Blind-only OpenAI transport and resumable machine passes. No mapping/ranking access."""

import asyncio
import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator

from uranus_research_service.ground_truth import Eligibility
from uranus_research_service.ground_truth_snapshot import PublicEvent
from uranus_research_service.json_codec import decode

PASSES = ("machine-a", "machine-b", "machine-c")
MAX_BYTES = 256 * 1024


def require(value, reason):
    if not value:
        raise ValueError(reason)


def encoded(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def digest(value):
    return sha(encoded(value))


def read(path):
    return decode(Path(path).read_bytes())


def read_lines(path):
    return [decode(line) for line in Path(path).read_bytes().splitlines()]


def atomic_new(path, value, *, jsonl=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join(encoded(r) + b"\n" for r in value) if jsonl else encoded(value) + b"\n"
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Exclusive atomic publication; never replace an answer.
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BlindCandidate(Closed):
    annotation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    query: str = Field(min_length=1, max_length=1000)
    language: Literal["de", "da", "en"]
    reference_time: str
    eligibility: Eligibility
    event: dict
    eligible_occurrence_ids: list[UUID]
    rubric: str
    scale: dict[str, str]

    @model_validator(mode="after")
    def public_evidence(self):
        require("id" not in self.event, "event_id_not_blind")
        event = PublicEvent.model_validate(
            {"id": "00000000-0000-0000-0000-000000000001", **self.event}
        )
        require(
            set(self.eligible_occurrence_ids) <= {o.id for o in event.occurrences},
            "unknown_occurrence",
        )
        require(set(self.scale) == {"0", "1", "2", "3"}, "rubric_scale")
        return self


SUPPORT = (
    "title",
    "subtitle",
    "summary",
    "description",
    "event_types",
    "tags",
    "languages",
    "price_type",
    "occurrences",
    "venue",
    "city",
    "space",
    "venue_accessibility",
    "space_accessibility",
    "accessibility_info",
)
OCCURRENCE_FIELDS = {
    "venue",
    "city",
    "space",
    "venue_accessibility",
    "space_accessibility",
    "accessibility_info",
}


class Judgment(Closed):
    annotation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    state: Literal["graded", "uncertain", "needs_more_context"]
    grade: StrictInt | None = Field(ge=0, le=3)
    confidence: StrictFloat = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=800)
    supporting_fields: list[str] = Field(max_length=20)
    occurrence_ids: list[UUID] = Field(max_length=20)

    @model_validator(mode="after")
    def consistent(self):
        require((self.state == "graded") == (self.grade is not None), "state_grade")
        require(self.reason.strip(), "empty_reason")
        require(
            not re.search(
                r"\b(v[35]|rankings?|scores?|gates?|retrieval models?|human.approved|"
                r"ground truth|gold labels?)\b",
                self.reason,
                re.I,
            ),
            "non_evidence_reason",
        )
        require(set(self.supporting_fields) <= set(SUPPORT), "unknown_field")
        require(len(set(self.supporting_fields)) == len(self.supporting_fields), "duplicate_field")
        require(len(set(self.occurrence_ids)) == len(self.occurrence_ids), "duplicate_occurrence")
        if self.grade is not None and self.grade > 0:
            require(self.supporting_fields, "positive_evidence_required")
        return self


def validate_judgment(value, candidate):
    j = Judgment.model_validate(value)
    require(j.annotation_id == candidate["annotation_id"], "annotation_identity")
    ids = {str(i) for i in j.occurrence_ids}
    require(ids <= set(candidate["eligible_occurrence_ids"]), "occurrence_eligibility")
    if j.grade is not None and j.grade > 0:
        require(ids, "positive_occurrence_context_required")
    occurrences = [o for o in candidate["event"]["occurrences"] if o["id"] in ids]
    # Non-positive states may cite a field precisely because evidence is absent.
    # Keep field allowlisting and occurrence membership for every state.
    for f in j.supporting_fields if j.grade is not None and j.grade > 0 else []:
        if f in OCCURRENCE_FIELDS:
            require(any(o[f] for o in occurrences), "empty_occurrence_evidence")
        elif f == "occurrences":
            require(occurrences, "missing_occurrence")
        else:
            require(candidate["event"][f], "empty_evidence")
    return j.model_dump(mode="json")


def load_blind(directory):
    """Only explicitly listed blind files are opened. Never imports the operator mapper."""
    directory = Path(directory)
    plan = read(directory / "plan.json")
    require(plan["worker_sha256"] == sha(Path(__file__).read_bytes()), "worker_code_changed")
    require(
        set(plan["blind_files"])
        == {
            "blind-candidates.jsonl",
            "annotation-package.json",
            "policy-v1.json",
            "judge-v1.schema.json",
            "judge-v1.txt",
            "pass-a.txt",
            "pass-b.txt",
            "pass-c.txt",
        },
        "blind_file_set",
    )
    for name, checksum in plan["blind_files"].items():
        require(
            name
            in {
                "blind-candidates.jsonl",
                "annotation-package.json",
                "policy-v1.json",
                "judge-v1.schema.json",
                "judge-v1.txt",
                "pass-a.txt",
                "pass-b.txt",
                "pass-c.txt",
            },
            "nonblind_input_path",
        )
        require(sha((directory / name).read_bytes()) == checksum, "blind_input_changed")
    packet = read_lines(directory / "blind-candidates.jsonl")
    for p in packet:
        BlindCandidate.model_validate(p)
    require(
        len({p["annotation_id"] for p in packet}) == len(packet) == plan["pair_count"],
        "packet_count",
    )
    meta = read(directory / "annotation-package.json")
    require(digest(packet) == meta["packet_sha256"], "packet_hash")
    require(plan["package_sha256"] == meta["package_sha256"], "package_identity")
    require(re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,99}", plan["model"]), "model_required")
    return plan, packet


def prompt_text(directory, pass_name):
    require(pass_name in PASSES, "unknown_pass")
    return (
        (directory / "judge-v1.txt").read_text()
        + "\n"
        + (directory / f"pass-{pass_name[-1]}.txt").read_text()
    )


def api_payload(candidate, plan, prompt, schema):
    # Closed nested input validation occurs on the actual object submitted to the API.
    c = BlindCandidate.model_validate(candidate).model_dump(mode="json")
    content = {
        "annotation_id": c["annotation_id"],
        "query": {"text": c["query"], "language": c["language"]},
        "rubric": {"query_specific": c["rubric"], "scale": c["scale"]},
        "eligibility": {
            "requirements": c["eligibility"],
            "reference_time": c["reference_time"],
            "eligible_occurrence_ids": c["eligible_occurrence_ids"],
        },
        "evidence": c["event"],
    }
    result = {
        "model": plan["model"],
        "store": False,
        "instructions": prompt,
        "input": [{"role": "user", "content": encoded(content).decode()}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "blind_machine_judgment",
                "strict": True,
                "schema": schema,
            }
        },
        "temperature": 0,
        "reasoning": {"effort": "none"},
        "max_output_tokens": 1200,
    }
    require(len(encoded(result)) <= MAX_BYTES, "request_size")
    return result


class APIError(Exception):
    def __init__(self, category, retry=False, request_id=None):
        super().__init__(category)
        self.category, self.retry, self.request_id = category, retry, request_id


def safe_id(value):
    return (
        value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value) else None
    )


class OpenAIJudge:
    def __init__(self, key, *, transport=None):
        require(bool(key) and key.strip() == key, "OPENAI_API_KEY_required")
        self.client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1/",
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(60, connect=10),
            transport=transport,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
        )

    async def close(self):
        await self.client.aclose()

    async def request(self, method, path, payload=None, client_id=None):
        require(
            (method == "POST" and path == "responses")
            or (method == "GET" and re.fullmatch(r"models/[a-z0-9][a-z0-9.-]{1,99}", path)),
            "api_path",
        )
        try:
            self.client.cookies.clear()
            headers = {"X-Client-Request-Id": client_id} if client_id else {}
            async with self.client.stream(method, path, json=payload, headers=headers) as response:
                request_id = safe_id(response.headers.get("x-request-id"))
                if response.status_code != 200:
                    category = (
                        "rate_limit"
                        if response.status_code == 429
                        else "temporary_http"
                        if response.status_code in (408, 500, 502, 503, 504)
                        else "http_rejected"
                    )
                    raise APIError(category, category != "http_rejected", request_id)
                if (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                    != "application/json"
                    or response.headers.get("content-encoding", "identity") != "identity"
                ):
                    raise APIError("response_headers", request_id=request_id)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise APIError("response_size", request_id=request_id)
                try:
                    return decode(bytes(body)), request_id
                except (ValueError, TypeError):
                    raise APIError("response_json", request_id=request_id) from None
        except httpx.TransportError:
            raise APIError("network", retry=True) from None
        finally:
            self.client.cookies.clear()

    async def available(self, model):
        require(re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,99}", model), "invalid_model_id")
        body, _ = await self.request("GET", f"models/{model}")
        require(body.get("id") == model, "model_unavailable_or_alias")


def usage_of(body):
    usage = body.get("usage", {})
    return {
        k: usage[k]
        for k in ("input_tokens", "output_tokens", "total_tokens")
        if type(usage.get(k)) is int and usage[k] >= 0
    }


def parse_response(body, candidate, model):
    require(body.get("model") == model, "response_model_changed")
    require(body.get("status") == "completed", "response_incomplete")
    parts = [part for o in body["output"] if o.get("type") == "message" for part in o["content"]]
    require(len(parts) == 1 and parts[0].get("type") == "output_text", "response_refusal_or_shape")
    require(
        set(usage_of(body)) == {"input_tokens", "output_tokens", "total_tokens"}, "missing_usage"
    )
    return validate_judgment(decode(parts[0]["text"]), candidate)


def record_identity(plan, pass_name, run_id, purpose, prompt):
    return {
        "model": plan["model"],
        "run_id": run_id,
        "pass_name": pass_name,
        "purpose": purpose,
        "provenance": "machine-judgment-not-human",
        "prompt_version": "judge-v1",
        "prompt_sha256": sha(prompt.encode()),
        "package_sha256": plan["package_sha256"],
        "plan_sha256": digest(plan),
    }


async def run_pass(
    directory,
    destination,
    pass_name,
    run_id,
    purpose,
    client,
    *,
    approval=None,
    sleep=asyncio.sleep,
):
    plan, packet = load_blind(directory)
    require(purpose in {"dry-run", "full"}, "purpose")
    require(re.fullmatch(r"[a-z0-9_-]{1,80}", run_id), "run_id")
    if purpose == "full":
        require(
            approval
            and approval.get("authorization") == "explicit-cost-approval"
            and approval.get("plan_sha256") == digest(plan)
            and approval.get("approval_reference", "").strip(),
            "full_run_cost_approval_required",
        )
        require(approval.get("max_judgments") == len(packet) * 3, "approval_size")
        require(approval.get("dry_report_sha256"), "approved_dry_report_required")
    selected = (
        packet
        if purpose == "full"
        else [p for p in packet if p["annotation_id"] in plan["dry_annotation_ids"]]
    )
    require(purpose != "dry-run" or len(selected) <= 20, "dry_run_size")
    prompt = prompt_text(directory, pass_name)
    schema = read(directory / "judge-v1.schema.json")
    identity = record_identity(plan, pass_name, run_id, purpose, prompt)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / ".run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = {
            **identity,
            "annotation_ids": [p["annotation_id"] for p in selected],
            "max_attempts": 3,
            "cost_approval_sha256": digest(approval) if approval else None,
        }
        manifest_path = destination / "manifest.json"
        if manifest_path.exists():
            require(read(manifest_path) == manifest, "resume_identity_changed")
        else:
            atomic_new(manifest_path, manifest)
        await client.available(plan["model"])
        for candidate in selected:
            aid = candidate["annotation_id"]
            final = destination / "records" / f"{aid}.json"
            if final.exists():
                existing = read(final)
                require(
                    all(existing.get(k) == v for k, v in identity.items()), "resume_record_identity"
                )
                validate_judgment({k: existing[k] for k in Judgment.model_fields}, candidate)
                continue
            payload = api_payload(candidate, plan, prompt, schema)
            for attempt in range(1, 4):
                reserved = destination / "attempts" / f"{aid}-{attempt}.request.json"
                completed = destination / "attempts" / f"{aid}-{attempt}.result.json"
                if reserved.exists():
                    if completed.exists():
                        previous = read(completed)
                        if previous["status"] == "success":
                            atomic_new(final, previous["judgment"])
                            break
                        require(previous.get("retryable"), "previous_nonretryable_failure")
                    continue  # Interrupted request may have been billed. Never overwrite it.
                client_id = str(uuid5(NAMESPACE_URL, f"{digest(identity)}:{aid}:{attempt}"))
                meta = {
                    **identity,
                    "annotation_id": aid,
                    "attempt_count": attempt,
                    "client_request_id": client_id,
                    "request_sha256": digest(payload),
                }
                atomic_new(reserved, {**meta, "status": "started"})
                started = time.monotonic()
                usage, request_id, response_id = {}, None, None
                try:
                    body, request_id = await client.request("POST", "responses", payload, client_id)
                    usage, response_id = usage_of(body), safe_id(body.get("id"))
                    judgment = parse_response(body, candidate, plan["model"])
                    row = {
                        **judgment,
                        **identity,
                        "attempt_count": attempt,
                        "request_id": request_id,
                        "response_id": response_id,
                        "latency_ms": (time.monotonic() - started) * 1000,
                        "usage": usage,
                        "status": "success",
                    }
                    atomic_new(completed, {**meta, "status": "success", "judgment": row})
                    atomic_new(final, row)
                    break
                except (APIError, ValueError, KeyError, TypeError) as error:
                    retry = isinstance(error, APIError) and error.retry
                    category = (
                        error.category
                        if isinstance(error, APIError)
                        else "invalid_judgment_or_contract"
                    )
                    atomic_new(
                        completed,
                        {
                            **meta,
                            "status": "failed",
                            "error_category": category,
                            "retryable": retry,
                            "request_id": request_id or getattr(error, "request_id", None),
                            "response_id": response_id,
                            "usage": usage,
                            "latency_ms": (time.monotonic() - started) * 1000,
                        },
                    )
                    if not retry:
                        raise APIError(category) from None
                    if attempt < 3:
                        await sleep(2**attempt)
            require(final.exists(), "attempt_budget_exhausted")
        rows = [read(destination / "records" / f"{p['annotation_id']}.json") for p in selected]
        output = destination / f"{pass_name}.jsonl"
        if output.exists():
            require(read_lines(output) == rows, "completed_run_changed")
        else:
            atomic_new(output, rows, jsonl=True)
    return rows
