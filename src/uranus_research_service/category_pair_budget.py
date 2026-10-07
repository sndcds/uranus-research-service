"""Offline-only, paired A/B budget contract. No transport, API key or execution command."""

import argparse
import fcntl
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, StrictInt

from uranus_research_service import category_machine_execution as legacy
from uranus_research_service.category_machine_cost_pilot import Prices, price, usage
from uranus_research_service.machine_blind_review import parse
from uranus_research_service.machine_judge import (
    Closed,
    atomic_new,
    digest,
    read,
    require,
    safe_id,
    sha,
)

BASELINE = "b87cfd3f2a93b91baad3c33fc839c6eab55d1bda"
DEST = Path("benchmark/review/category-coverage-pair-budget-v1")
PRICE_SOURCE = Path("benchmark/review/category-coverage-cost-pilot-v1/pilot-price-manifest.json")
SEED = "category-coverage-paired-order-v1"
PASSES = ("machine-a", "machine-b")
CAP = "12.00"


class Approval(Closed):
    schema_version: Literal["category-pair-budget-approval-v1"]
    authorization: Literal["explicit-operator-cost-approval"]
    approval_reference: str = Field(min_length=1, max_length=1000)
    contract_review_reference: str = Field(min_length=1, max_length=1000)
    kind: Literal["initial", "continuation"]
    contract_sha256: str
    order_sha256: str
    packet_sha256: str
    prompt_sha256: str
    legacy_contract_sha256: str
    legacy_cost_report_sha256: str
    prices_sha256: str
    model: Literal[legacy.MODEL]
    pair_count: Literal[1506]
    pass_count: Literal[2]
    request_count: Literal[3012]
    passes: legacy.PassApproval
    max_amount_usd: Literal["12.00"]
    max_input_tokens: StrictInt
    max_output_tokens: StrictInt
    execution_root: str
    previous_approval_sha256: str | None = None
    stopped_state_sha256: str | None = None


def code_hashes():
    return {
        **legacy.code_hashes(),
        "category_machine_cost_pilot.py": sha(
            Path(__file__).with_name("category_machine_cost_pilot.py").read_bytes()
        ),
        "category_pair_budget.py": sha(Path(__file__).read_bytes()),
    }


def ordered(shapes):
    require(len(shapes) == len({r["annotation_id"] for r in shapes}) == legacy.COUNT, "order_count")
    return sorted(deepcopy(shapes), key=lambda r: digest([SEED, r["annotation_id"]]))


def contract_data(package=legacy.PACKAGE, price_source=PRICE_SOURCE):
    old, cost, _, _, shapes = legacy.load_execution(package, legacy.DEST, legacy.MODEL)
    source = read(price_source)
    require(source["model"] == legacy.MODEL, "price_model")
    prices = Prices.model_validate(source["prices"]).model_dump()
    require(
        Decimal(prices["cached_input_per_million"]) <= Decimal(prices["input_per_million"]),
        "cached_price",
    )
    order = {
        "schema_version": "category-pair-order-v1",
        "seed": SEED,
        "algorithm": "sha256-canonical-json-array(seed,annotation_id)",
        "within_pair": list(PASSES),
        "pairs": ordered(shapes),
    }
    contract = {
        "schema_version": "category-pair-budget-contract-v1",
        "baseline_main": BASELINE,
        "preparation_only": True,
        "transport_enabled": False,
        "model": legacy.MODEL,
        "parameters": old["parameters"],
        "response_schema_sha256": old["response_schema_sha256"],
        "run_ids": {
            name: "paired-" + digest([SEED, digest(order), prices, name])[:24] for name in PASSES
        },
        "pass_output_directories": {name: name for name in PASSES},
        "packet_sha256": legacy.PACKET_SHA,
        "prompt_sha256": old["prompt_sha256"],
        "legacy_contract_sha256": sha((legacy.DEST / "execution-contract.json").read_bytes()),
        "legacy_cost_report_sha256": sha((legacy.DEST / "cost-report.json").read_bytes()),
        "order_digest": digest(order),
        "price_source_sha256": sha(price_source.read_bytes()),
        "prices": prices,
        "prices_sha256": digest(prices),
        "code_sha256": code_hashes(),
        "pair_count": 1506,
        "pass_count": 2,
        "request_count": 3012,
        "passes": list(PASSES),
        "machine-c": "forbidden",
        "max_attempts_per_request": 1,
        "operator_hard_cap_usd": CAP,
        "max_input_tokens": cost["estimated_input_tokens"],
        "max_output_tokens": cost["estimated_output_token_ceiling"],
        "per_pass_input_ceiling": cost["estimated_input_tokens"] // 2,
        "per_pass_output_ceiling": cost["estimated_output_token_ceiling"] // 2,
        "budget_rule": "actual settled USD + outstanding USD + both next reservations <= cap",
        "reservation_rule": "uncached input byte estimate plus 1200 output tokens, each pass",
        "unknown_usage_rule": "retain full reservation; block further requests pending audit",
        "token_rule": "conservative input/output reservations never refunded",
        "budget_stop": "budget_exhausted_partial",
        "continuation_rule": (
            "new approval binds previous approval and stopped state; cumulative cap unchanged"
        ),
        "partial_pair_rule": "quarantine; no next pair or export until both passes settled",
        "consensus_rule": "disabled in this PR; future consumers must require complete pair set",
    }
    return contract, order


def reservation_cost(shape, contract):
    return price(
        shape["estimated_input_tokens"], shape["estimated_output_tokens"], 0, contract["prices"]
    )


def preflight(contract, order):
    first = order["pairs"][0]
    ceiling = price(
        contract["max_input_tokens"], contract["max_output_tokens"], 0, contract["prices"]
    )
    return {
        "schema_version": "category-pair-budget-preflight-v1",
        "status": "prepared_not_approved",
        "api_requests": 0,
        "pair_count": 1506,
        "request_count": 3012,
        "operator_hard_cap_usd": CAP,
        "legacy_full_envelope_usd": str(ceiling),
        "legacy_12_usd_guard_result": "amount_budget_too_small"
        if ceiling > Decimal(CAP)
        else "fits",
        "first_pair_annotation_id": first["annotation_id"],
        "first_pair_reservation_usd": str(2 * reservation_cost(first, contract)),
        "first_pair_fits_money_cap": 2 * reservation_cost(first, contract) <= Decimal(CAP),
        "full_completion_guaranteed": False,
        "unspent_12_usd_is_not_a_target": True,
        "on_budget_stop": {
            "status": "budget_exhausted_partial",
            "api_calls": "none further",
            "automatic_resume": False,
            "consensus": False,
            "reevaluation": False,
            "new_explicit_approval_required": True,
        },
    }


def prepare(output):
    require(not output.exists(), "output_exists")
    require(
        not output.resolve().is_relative_to(legacy.DEST.resolve())
        and not output.resolve().is_relative_to(legacy.PACKAGE.resolve())
        and not output.resolve().is_relative_to(PRICE_SOURCE.parent.resolve()),
        "historical_output",
    )
    c, order = contract_data()
    files = {
        "execution-contract.json": c,
        "request-order.json": order,
        "approval-schema.json": Approval.model_json_schema(),
        "budget-preflight.json": preflight(c, order),
    }
    for name, value in files.items():
        atomic_new(output / name, value)
    atomic_new(
        output / "artifact-sha256.json",
        {"files": {n: sha((output / n).read_bytes()) for n in sorted(files)}},
    )


def load(directory):
    c, order = contract_data()
    expected = {
        "execution-contract.json": c,
        "request-order.json": order,
        "approval-schema.json": Approval.model_json_schema(),
        "budget-preflight.json": preflight(c, order),
    }
    index = read(directory / "artifact-sha256.json")["files"]
    require(set(index) == set(expected), "artifact_set")
    for name, value in expected.items():
        require(
            read(directory / name) == value and sha((directory / name).read_bytes()) == index[name],
            "artifact_changed",
        )
    return c, order


def check_approval(raw, contract, order, directory, output):
    a = Approval.model_validate(raw).model_dump(by_alias=True)
    require(
        a["approval_reference"].strip() and a["contract_review_reference"].strip(),
        "approval_reference",
    )
    require(
        all(type(raw[k]) is int for k in ("pair_count", "pass_count", "request_count")), "counts"
    )
    for k in (
        "model",
        "packet_sha256",
        "prompt_sha256",
        "legacy_contract_sha256",
        "legacy_cost_report_sha256",
        "prices_sha256",
        "pair_count",
        "pass_count",
        "request_count",
        "max_input_tokens",
        "max_output_tokens",
    ):
        require(a[k] == contract[k], "approval_binding")
    require(
        a["contract_sha256"] == sha((directory / "execution-contract.json").read_bytes())
        and a["order_sha256"] == sha((directory / "request-order.json").read_bytes()),
        "approval_hashes",
    )
    require(digest(order) == contract["order_digest"], "order_binding")
    root = Path(a["execution_root"])
    require(
        root.is_absolute()
        and output.resolve() == root.resolve()
        and not root.resolve().is_relative_to(Path("benchmark").resolve()),
        "execution_root",
    )
    if a["kind"] == "initial":
        require(
            a["previous_approval_sha256"] is None and a["stopped_state_sha256"] is None,
            "initial_approval",
        )
    else:
        require(a["previous_approval_sha256"] and a["stopped_state_sha256"], "continuation_binding")
    return a


def initial_state(approval):
    require(approval["kind"] == "initial", "initial_required")
    return {
        "status": "ready",
        "completed_pairs": 0,
        "current": None,
        "actual_usd": "0",
        "outstanding_usd": "0",
        "reserved_input_per_pass": 0,
        "reserved_output_per_pass": 0,
        "dispatched_requests": 0,
        "response_ids": [],
        "approval_sha256": digest(approval),
    }


def admit(state, contract, order):
    require(state["status"] == "ready" and state["current"] is None, "cannot_admit")
    index = state["completed_pairs"]
    require(index < contract["pair_count"], "all_pairs_complete")
    row = order["pairs"][index]
    both = 2 * reservation_cost(row, contract)
    result = deepcopy(state)
    if Decimal(state["actual_usd"]) + Decimal(state["outstanding_usd"]) + both > Decimal(CAP):
        result["status"] = "budget_exhausted_partial"
        return result
    if (
        state["reserved_input_per_pass"] + row["estimated_input_tokens"]
        > contract["per_pass_input_ceiling"]
        or state["reserved_output_per_pass"] + row["estimated_output_tokens"]
        > contract["per_pass_output_ceiling"]
    ):
        result["status"] = "technical_limit_partial"
        return result
    result["reserved_input_per_pass"] += row["estimated_input_tokens"]
    result["reserved_output_per_pass"] += row["estimated_output_tokens"]
    result["outstanding_usd"] = str(both)
    result["current"] = {
        "annotation_id": row["annotation_id"],
        "payload_sha256": row["payload_sha256"],
        "reservation_each_usd": str(both / 2),
        "passes": dict.fromkeys(PASSES, "reserved"),
    }
    result["status"] = "pair_reserved"
    return result


def dispatch(state, pass_name):
    require(pass_name in PASSES and state["current"] is not None, "pass_or_pair")
    require(state["status"] in ("pair_reserved", "pair_partial"), "dispatch_state")
    require(state["current"]["passes"][pass_name] == "reserved", "never_resend")
    if pass_name == "machine-b":
        require(state["current"]["passes"]["machine-a"] == "settled", "a_before_b")
    result = deepcopy(state)
    result["current"]["passes"][pass_name] = "in_flight"
    result["status"] = "in_flight"
    result["dispatched_requests"] += 1
    require(result["dispatched_requests"] <= 3012, "request_cap")
    return result


def settle(state, pass_name, measured, response_id, contract, order):
    require(
        state["status"] == "in_flight"
        and pass_name in PASSES
        and state["current"]["passes"][pass_name] == "in_flight",
        "settlement_state",
    )
    require(
        set(measured)
        == {
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_input_tokens",
            "reasoning_tokens",
        },
        "usage_fields",
    )
    verified = usage(
        {
            "usage": {
                **{k: measured[k] for k in ("input_tokens", "output_tokens", "total_tokens")},
                "input_tokens_details": {"cached_tokens": measured["cached_input_tokens"]},
                "output_tokens_details": {"reasoning_tokens": measured["reasoning_tokens"]},
            }
        }
    )
    require(verified == measured, "usage_contract")
    row = order["pairs"][state["completed_pairs"]]
    require(
        measured["input_tokens"] <= row["estimated_input_tokens"]
        and measured["output_tokens"] <= row["estimated_output_tokens"],
        "usage_exceeds_reservation",
    )
    require(response_id and response_id not in state["response_ids"], "response_id")
    actual = price(
        measured["input_tokens"],
        measured["output_tokens"],
        measured["cached_input_tokens"] or 0,
        contract["prices"],
    )
    require(actual <= Decimal(state["current"]["reservation_each_usd"]), "cost_exceeds_reservation")
    result = deepcopy(state)
    result["actual_usd"] = str(Decimal(state["actual_usd"]) + actual)
    result["outstanding_usd"] = str(
        Decimal(state["outstanding_usd"]) - Decimal(state["current"]["reservation_each_usd"])
    )
    result["response_ids"].append(response_id)
    result["current"]["passes"][pass_name] = "settled"
    require(
        Decimal(result["actual_usd"]) + Decimal(result["outstanding_usd"]) <= Decimal(CAP),
        "hard_cap",
    )
    if all(v == "settled" for v in result["current"]["passes"].values()):
        result["completed_pairs"] += 1
        result["current"] = None
        result["status"] = (
            "complete" if result["completed_pairs"] == contract["pair_count"] else "ready"
        )
    else:
        result["status"] = "pair_partial"
    return result


def continue_budget(state, approval):
    require(
        state["status"] == "budget_exhausted_partial" and state["current"] is None,
        "continuation_state",
    )
    require(
        approval["kind"] == "continuation"
        and approval["previous_approval_sha256"] == state["approval_sha256"]
        and approval["stopped_state_sha256"] == digest(state),
        "new_explicit_approval_required",
    )
    require(digest(approval) != state["approval_sha256"], "new_approval_required")
    result = deepcopy(state)
    result["approval_sha256"] = digest(approval)
    result["status"] = "ready"
    # No spending/counter reset. Under the same cap the next admission may still refuse.
    return result


def require_complete(state):
    require(
        state["status"] == "complete"
        and state["completed_pairs"] == 1506
        and state["dispatched_requests"] == 3012
        and state["current"] is None
        and Decimal(state["outstanding_usd"]) == 0,
        "no_consensus_or_export_for_partial",
    )


class Ledger:
    """Locked append-only offline state machine. No network or transport is available here."""

    def __init__(self, directory, output):
        require(
            output.is_absolute()
            and not output.resolve().is_relative_to(Path("benchmark").resolve()),
            "external_ledger_root_required",
        )
        self.directory, self.output = directory, output
        self.contract, self.order = load(directory)
        packet, _ = legacy.load_packet(legacy.PACKAGE)
        self.packet = {p["annotation_id"]: p for p in packet}
        self.state, self.tail, self.events, self.lock = None, None, 0, None

    def __enter__(self):
        self.output.mkdir(parents=True, exist_ok=True)
        self.lock = (self.output / ".lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for i, path in enumerate(sorted((self.output / "journal").glob("*.json"))):
                require(path.name == f"{i:06}.json", "journal_gap")
                event = read(path)
                require(
                    set(event) == {"previous_sha256", "operation", "state_sha256"}
                    and event["previous_sha256"] == self.tail,
                    "journal_chain",
                )
                self.state = self.transition(event["operation"])
                require(digest(self.state) == event["state_sha256"], "journal_state")
                self.tail, self.events = sha(path.read_bytes()), i + 1
            return self
        except BaseException:
            self.lock.close()
            raise

    def __exit__(self, *_):
        self.lock.close()

    def transition(self, operation):
        kind = operation["kind"]
        allowed = {
            "initialize": {"kind", "approval"},
            "continue": {"kind", "approval"},
            "admit": {"kind"},
            "dispatch": {"kind", "pass_name"},
            "settle": {"kind", "pass_name", "response_sha256"},
            "fail": {"kind"},
        }
        require(kind in allowed and set(operation) == allowed[kind], "operation_schema")
        if kind in ("initialize", "continue"):
            approval = check_approval(
                operation["approval"], self.contract, self.order, self.directory, self.output
            )
            if kind == "initialize":
                require(self.state is None, "already_initialized")
                return initial_state(approval)
            return continue_budget(self.state, approval)
        require(self.state is not None, "approval_required")
        if kind == "admit":
            return admit(self.state, self.contract, self.order)
        if kind == "dispatch":
            return dispatch(self.state, operation["pass_name"])
        if kind == "fail":
            require(self.state["status"] == "in_flight", "failure_state")
            state = deepcopy(self.state)
            state["status"] = "request_failed_partial"
            return state
        pass_name = operation["pass_name"]
        path = self.response_path(pass_name)
        require(sha(path.read_bytes()) == operation["response_sha256"], "response_hash")
        body = read(path)
        require(body.get("service_tier") == "default", "unpriced_service_tier")
        candidate = self.packet[self.state["current"]["annotation_id"]]
        parse(body, candidate, self.contract["model"])
        return settle(
            self.state, pass_name, usage(body), safe_id(body.get("id")), self.contract, self.order
        )

    def append(self, operation):
        require(self.lock is not None and not self.lock.closed, "ledger_lock_required")
        state = self.transition(operation)
        event = {
            "previous_sha256": self.tail,
            "operation": operation,
            "state_sha256": digest(state),
        }
        path = self.output / "journal" / f"{self.events:06}.json"
        atomic_new(path, event)
        self.state, self.tail, self.events = state, sha(path.read_bytes()), self.events + 1
        return deepcopy(state)

    def response_path(self, pass_name):
        require(pass_name in PASSES and self.state and self.state["current"], "response_pair")
        return (
            self.output / pass_name / "responses" / f"{self.state['current']['annotation_id']}.json"
        )

    def request_intent(self, pass_name):
        """Durably mark intent BEFORE handing the exact blind payload to a future worker."""
        require(pass_name in PASSES and self.state and self.state["current"], "request_pair")
        require(
            not self.response_path(pass_name).exists(), "saved_response_requires_reconciliation"
        )
        candidate = self.packet[self.state["current"]["annotation_id"]]
        payload = legacy.request_for(candidate, self.contract["model"], legacy.PROMPT.read_text())
        require(
            sha(legacy.wire(payload)) == self.state["current"]["payload_sha256"], "payload_binding"
        )
        self.append({"kind": "dispatch", "pass_name": pass_name})
        client_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{self.output.resolve()}:{digest(self.contract)}:{candidate['annotation_id']}:{pass_name}",
            )
        )
        return {
            "client_request_id": client_id,
            "run_id": self.contract["run_ids"][pass_name],
            "payload": payload,
        }

    def record_response(self, pass_name, body):
        """Offline receipt validation; persist atomically, then settle. No provider calls."""
        # Check state before creating an orphan or accepting a result from the wrong pass.
        require(
            self.state["status"] == "in_flight"
            and pass_name in PASSES
            and self.state["current"]["passes"][pass_name] == "in_flight",
            "receipt_state",
        )
        path = self.response_path(pass_name)
        if path.exists():
            require(read(path) == body, "never_overwrite_response")
        else:
            atomic_new(path, body)
        return self.append(
            {"kind": "settle", "pass_name": pass_name, "response_sha256": sha(path.read_bytes())}
        )

    def resume_action(self):
        require(self.state is not None, "approval_required")
        status = self.state["status"]
        if status == "in_flight":
            name = next(k for k, v in self.state["current"]["passes"].items() if v == "in_flight")
            return (
                "reconcile_saved_response_offline"
                if self.response_path(name).exists()
                else "operator_audit_required_no_resend"
            )
        return {
            "ready": "admit_next_pair",
            "pair_reserved": "dispatch_machine_a",
            "pair_partial": "dispatch_reserved_machine_b_only",
            "budget_exhausted_partial": "new_explicit_approval_required",
            "technical_limit_partial": "blocked_technical_limit",
            "request_failed_partial": "operator_audit_required_no_resend",
            "complete": "complete_no_more_requests",
        }[status]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("validate")
    verify.add_argument("--contract", type=Path, default=DEST)
    check = sub.add_parser("check-approval")
    check.add_argument("--contract", type=Path, default=DEST)
    check.add_argument("--approval", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.command == "prepare":
        prepare(args.output)
    else:
        c, order = load(args.contract)
        if args.command == "check-approval":
            check_approval(read(args.approval), c, order, args.contract, args.output)
    print("Offline validation complete. No API calls; no execution authorization created.")


if __name__ == "__main__":
    main()
