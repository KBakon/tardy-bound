"""Canonical source-semantic M_K v2 representation for WP06 Stage A only."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from theory_state import state_for

SCHEMA = "TARDY_BOUND_MK_V2"
FORBIDDEN_OUTCOMES = {"TT_SPT", "TT_EDD", "Delta", "TT_star", "optimal_schedules", "witness"}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def edges_from_b(predecessors: list[set[int]]) -> list[list[int]]:
    return [[i + 1, j + 1] for j, ancestors in enumerate(predecessors) for i in sorted(ancestors)]


def mdd_trie(p: tuple[int, ...], d: tuple[int, ...]) -> tuple[list[dict[str, list[int]]], list[list[int]]]:
    """Depth-first lexicographic canonical local-argmin/tie decision trie."""
    nodes: list[dict[str, list[int]]] = []
    leaves: list[list[int]] = []
    n = len(p)
    def visit(prefix: tuple[int, ...], remaining: tuple[int, ...], elapsed: int) -> None:
        if not remaining:
            nodes.append({"prefix": [x + 1 for x in prefix], "argmin": []})
            leaves.append([x + 1 for x in prefix])
            return
        priorities = {j: max(elapsed + p[j], d[j]) for j in remaining}
        minimum = min(priorities.values())
        choices = tuple(j for j in remaining if priorities[j] == minimum)
        nodes.append({"prefix": [x + 1 for x in prefix], "argmin": [x + 1 for x in choices]})
        for job in choices:
            visit(prefix + (job,), tuple(x for x in remaining if x != job), elapsed + p[job])
    visit((), tuple(range(n)), 0)
    return nodes, leaves


def lawler_partition_family(state: dict[str, Any]) -> list[list[Any]]:
    """Ascending-k (k, sorted PRE, jmax, sorted POST) authority serialization."""
    family=[]
    for part in sorted(state["lawler_parts"], key=lambda item: item["position"]):
        family.append([part["position"], sorted(part["before"]), part["long"], sorted(part["after"])])
    return family


def build_v2_state(p: tuple[int, ...], d: tuple[int, ...]) -> dict[str, Any]:
    """Compute diagnostics and the exact v2 key without any score outcome."""
    state = state_for(p, d)
    if FORBIDDEN_OUTCOMES.intersection(state):
        raise RuntimeError("outcome leaked into Stage-A theory state")
    trie, leaves = mdd_trie(p, d)
    state["T_MDD"] = trie
    state["MDD_leaves_from_trie"] = leaves
    state["LAWLER_PARTITION_FAMILY"] = lawler_partition_family(state)
    state["G123_edges"] = [[a + 1, b + 1] for a, b in sorted(state["raw"]["edges"])] if state["closure_count"] == 1 else []
    state["G_beta_edges"] = edges_from_b(state["full"]["B"]) if state["full_count"] == 1 else []
    state["equivalence_valid"] = state["full_count"] == 1 and all(
        state["beta"][j] == max(d[j], state["full"]["E"][j]) for j in range(len(p))
    )
    return state


def mk_v2_key(state: dict[str, Any]) -> dict[str, Any]:
    """Authority Section 8.6 serialization in its prescribed field order."""
    if FORBIDDEN_OUTCOMES.intersection(state):
        raise RuntimeError("outcome supplied to M_K v2")
    if state["closure_count"] != 1 or state["full_count"] != 1 or not state["equivalence_valid"]:
        raise ValueError("ineligible theory state")
    return {
        "schema": SCHEMA,
        "G123_edges": state["G123_edges"],
        "EDD_C22": state["EDD_C22"],
        "GEOM4": [state["SRD"], state["ERD"], state["NRD"], state["NRD_hard"]],
        "G_beta_edges": state["G_beta_edges"],
        "S_beta": state["beta_sequence"],
        "BETA_STATUS": state["beta_status"],
        "LAWLER_PARTITION_FAMILY": state["LAWLER_PARTITION_FAMILY"],
        "Q_exact": state["exact_q"],
        "h_key": state["key_h"],
        "T_MDD": state["T_MDD"],
    }


def signature_hash(key: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(key).encode("utf-8")).hexdigest()


def diagnostic_mutation_invariant(state: dict[str, Any]) -> bool:
    """Proves unkeyed diagnostics cannot perturb a v2 signature."""
    before = signature_hash(mk_v2_key(state))
    copy = dict(state)
    copy["alpha"] = list(reversed(copy["alpha"]))
    copy["beta"] = [value + 1000 for value in copy["beta"]]
    copy["alpha_order"] = [["diagnostic"]]
    copy["eq_width"] = [999] * len(copy["eq_width"])
    return before == signature_hash(mk_v2_key(copy))
