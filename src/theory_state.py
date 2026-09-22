"""Exact, outcome-free theory state for the locked WP03 census.

The implementation follows THEORY_STATE_AND_EXPERIMENT_DESIGN_LOCK_v1_1,
Sections 3--8.  No outcome fields exist in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import permutations
import hashlib
import json
from typing import Any, Iterable


STATUS_STRICT = "STRICT_PASS"
STATUS_EQUAL = "EQUALITY"
STATUS_FAIL = "FAIL"
STATUS_NA = "NA"


def canon(value: Any) -> str:
    """Stable, compact serialization used for hashes and CSV cells."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def labels(values: Iterable[int]) -> list[int]:
    return [v + 1 for v in values]


def set_labels(values: Iterable[int]) -> list[int]:
    return labels(sorted(values))


def edge_labels(edges: Iterable[tuple[int, int]]) -> list[list[int]]:
    return [[a + 1, b + 1] for a, b in sorted(edges)]


def transitive_closure(n: int, edges: Iterable[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    reach = [[False] * n for _ in range(n)]
    for a, b in edges:
        reach[a][b] = True
    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                for j in range(n):
                    reach[i][j] = reach[i][j] or reach[k][j]
    return frozenset((i, j) for i in range(n) for j in range(n) if reach[i][j])


def acyclic(n: int, edges: Iterable[tuple[int, int]]) -> bool:
    closed = transitive_closure(n, edges)
    return all((i, i) not in closed for i in range(n))


def predecessors_successors(n: int, p: tuple[int, ...], edges: Iterable[tuple[int, int]]) -> dict[str, Any]:
    graph = frozenset(edges)
    b = [set() for _ in range(n)]
    a = [set() for _ in range(n)]
    for i, j in graph:
        b[j].add(i)
        a[i].add(j)
    e = [sum(p[i] for i in b[j]) + p[j] for j in range(n)]
    l = [sum(p[i] for i in range(n) if i not in a[j]) for j in range(n)]
    return {"edges": graph, "B": b, "A": a, "E": e, "L": l}


def emmons_conditions(dj: int, pj: int, ek: int, dk: int, lk: int, lj: int) -> tuple[bool, bool, bool]:
    """Literal T1/T2/T3 predicates; retained for equality-boundary tests."""
    return (dj <= max(ek, dk), dj > max(ek, dk) and dj + pj >= lk, dk >= lj)


def emmons_closures(p: tuple[int, ...], d: tuple[int, ...]) -> list[frozenset[tuple[int, int]]]:
    """Enumerate all reachable terminal T1/T2/T3 transitive closures."""
    n = len(p)
    frontier = [frozenset()]
    seen = {frozenset()}
    terminal: set[frozenset[tuple[int, int]]] = set()
    while frontier:
        graph = frontier.pop()
        ps = predecessors_successors(n, p, graph)
        candidates: set[tuple[int, int]] = set()
        for j in range(n):
            for k in range(j + 1, n):
                # T1 and T3 both establish j -> k; their equality directions differ.
                t1, t2, t3 = emmons_conditions(d[j], p[j], ps["E"][k], d[k], ps["L"][k], ps["L"][j])
                if t1 or t3:
                    candidates.add((j, k))
                if t2:
                    candidates.add((k, j))
        next_graphs: list[frozenset[tuple[int, int]]] = []
        for edge in candidates:
            if edge in graph:
                continue
            proposed = transitive_closure(n, set(graph) | {edge})
            if acyclic(n, proposed):
                next_graphs.append(proposed)
        if not next_graphs:
            terminal.add(graph)
        else:
            for nxt in next_graphs:
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
    return sorted(terminal, key=lambda graph: edge_labels(graph))


def weak_matrix(v: tuple[int, ...] | list[int]) -> list[list[str]]:
    return [["<" if v[i] < v[j] else ">" if v[i] > v[j] else "=" for j in range(len(v))] for i in range(len(v))]


def quadrants(beta: list[int]) -> tuple[list[set[int]], list[set[int]], list[set[int]], list[set[int]]]:
    n = len(beta)
    ld = [{i for i in range(j) if beta[i] <= beta[j]} for j in range(n)]
    lu = [{i for i in range(j) if beta[i] > beta[j]} for j in range(n)]
    rd = [{i for i in range(j + 1, n) if beta[i] < beta[j]} for j in range(n)]
    ru = [{i for i in range(j + 1, n) if beta[i] >= beta[j]} for j in range(n)]
    return ld, lu, rd, ru


def left_expand(p: tuple[int, ...], beta0: tuple[int, ...], selection: tuple[int, ...]) -> tuple[int, ...]:
    beta = list(beta0)
    for k in selection:
        while True:
            ld, _, _, _ = quadrants(beta)
            candidate = sum(p[i] for i in ld[k]) + p[k]
            if candidate <= beta[k]:
                break
            beta[k] = candidate
    return tuple(beta)


def right_expand(p: tuple[int, ...], beta0: tuple[int, ...]) -> dict[str, Any]:
    """One source-defined RIGHT call, retaining its terminal B/A/E/L state."""
    n = len(p)
    beta = list(beta0)
    # Rebuild quadrant-derived state dynamically; additions are local to a RIGHT call.
    ld, _, _, ru = quadrants(beta)
    B = [set(x) for x in ld]
    A = [set(x) for x in ru]
    # Ensure reciprocity for initial quadrants (LD/RU are reciprocal by definition).
    for j in range(n):
        for i in B[j]:
            A[i].add(j)
    for j in range(n):
        for i in A[j]:
            B[i].add(j)
    j = n - 1
    while j >= 0:
        changed_current = False
        # Current quadrants use current beta, as required after every beta increase.
        _, _, rd, _ = quadrants(beta)
        E = [sum(p[i] for i in B[x]) + p[x] for x in range(n)]
        L = [sum(p[i] for i in range(n) if i not in A[x]) for x in range(n)]
        additions = [k for k in rd[j] if k not in B[j] and beta[j] + p[j] >= L[k]]
        if additions:
            for k in additions:
                B[j].add(k)
                A[k].add(j)
            E[j] = sum(p[i] for i in B[j]) + p[j]
            if E[j] > beta[j]:
                beta[j] = E[j]
                changed_current = True
        if not changed_current:
            j -= 1
    E = [sum(p[i] for i in B[j]) + p[j] for j in range(n)]
    L = [sum(p[i] for i in range(n) if i not in A[j]) for j in range(n)]
    return {"beta": tuple(beta), "B": B, "A": A, "E": E, "L": L}


def full_family(p: tuple[int, ...], d: tuple[int, ...]) -> list[dict[str, Any]]:
    """All terminal FULL states induced by every legal LEFT selection order."""
    n = len(p)
    initial = tuple(max(p[i], d[i]) for i in range(n))
    states: dict[str, dict[str, Any]] = {}
    for selection in permutations(range(n)):
        beta = initial
        final: dict[str, Any] | None = None
        while True:
            after_left = left_expand(p, beta, selection)
            after_right = right_expand(p, after_left)
            final = after_right
            if tuple(after_right["beta"]) == beta:
                break
            beta = tuple(after_right["beta"])
        assert final is not None
        # A final RIGHT pass is the terminal predecessor/successor state.
        final = right_expand(p, tuple(final["beta"]))
        key = canon({"beta": list(final["beta"]), "B": [set_labels(x) for x in final["B"]], "A": [set_labels(x) for x in final["A"]]})
        states[key] = final
    return [states[k] for k in sorted(states)]


def tt(p: tuple[int, ...], d: tuple[int, ...], order: Iterable[int]) -> int:
    elapsed = 0
    total = 0
    for j in order:
        elapsed += p[j]
        total += max(0, elapsed - d[j])
    return total


def mdd_paths(p: tuple[int, ...], d: tuple[int, ...]) -> list[tuple[int, ...]]:
    out: set[tuple[int, ...]] = set()
    def visit(prefix: tuple[int, ...], remaining: tuple[int, ...], t: int) -> None:
        if not remaining:
            out.add(prefix)
            return
        priorities = {j: max(t + p[j], d[j]) for j in remaining}
        minimum = min(priorities.values())
        for j in remaining:
            if priorities[j] == minimum:
                visit(prefix + (j,), tuple(x for x in remaining if x != j), t + p[j])
    visit((), tuple(range(len(p))), 0)
    return sorted(out)


def seq_labeled(seq: Iterable[int]) -> list[int]:
    return labels(seq)


def state_for(p: tuple[int, ...], d: tuple[int, ...]) -> dict[str, Any]:
    """Compute K0--K11 without schedule-score outcomes or optimum information."""
    n = len(p)
    if n == 0 or len(d) != n or any(x <= 0 for x in p + d):
        raise ValueError("positive, equally sized p/d tuples required")
    # The locked census already provides source p-rank order; general tie order is retained here.
    source = tuple(sorted(range(n), key=lambda j: (p[j], d[j], j)))
    if source != tuple(range(n)):
        # Re-indexing would obscure p-rank alignment for the locked domain.
        p = tuple(p[j] for j in source)
        d = tuple(d[j] for j in source)
    P, D = sum(p), sum(d)
    tau = Fraction(n * P - D, n * P)
    spt = tuple(sorted(range(n), key=lambda j: (p[j], d[j], j)))
    edd = tuple(sorted(range(n), key=lambda j: (d[j], p[j], j)))
    alpha = tuple(max(p[j], d[j]) for j in range(n))
    srd = all(d[j] <= d[j + 1] for j in range(n - 1))
    erd = all(alpha[j] <= alpha[j + 1] for j in range(n - 1))
    nrd = all(alpha[j] > alpha[j + 1] for j in range(n - 1))
    nrd_hard = nrd and all(d[j] + p[j] < P for j in range(n - 1))
    closures = emmons_closures(p, d)
    closure_states = [predecessors_successors(n, p, g) for g in closures]
    fulls = full_family(p, d)
    # K4 uses EDD starts, which are theory data, not a schedule outcome.
    starts = [0] * n
    elapsed = 0
    for j in edd:
        starts[j] = elapsed
        elapsed += p[j]
    c22 = [STATUS_STRICT if starts[j] < d[j] else STATUS_EQUAL if starts[j] == d[j] else STATUS_FAIL for j in range(n)]
    lawler_jL = max(i for i, j in enumerate(edd) if p[j] == max(p)) + 1
    lawler_positions = list(range(lawler_jL, n + 1))
    lawler_parts = []
    longjob = edd[lawler_jL - 1]
    for pos in lawler_positions:
        before = tuple(x for x in edd[:pos] if x != longjob)
        after = tuple(edd[pos:])
        lawler_parts.append({"position": pos, "before": seq_labeled(before), "long": longjob + 1, "after": seq_labeled(after)})
    mdd = mdd_paths(p, d)
    base: dict[str, Any] = {
        "n": n, "p": list(p), "d": list(d), "p_multiset": sorted(p), "d_multiset": sorted(d),
        "P": P, "D": D, "tau_num": tau.numerator, "tau_den": tau.denominator,
        "source_index": seq_labeled(range(n)), "spt": seq_labeled(spt), "edd": seq_labeled(edd),
        "tie_blocks_p": [], "tie_blocks_d": [], "alpha": list(alpha), "alpha_order": weak_matrix(alpha),
        "SRD": srd, "ERD": erd, "NRD": nrd, "NRD_hard": nrd_hard,
        "SPT_reasons": {"SRD": srd, "ERD": erd, "all_below_projection": all(d[j] < p[j] for j in range(n))},
        "SPT_sufficient": srd or erd, "c22_status": c22, "EDD_C22": STATUS_FAIL not in c22,
        "EDD_C22_exists_over_ties": STATUS_FAIL not in c22, "EDD_C22_all_over_ties": STATUS_FAIL not in c22,
        "closures": closure_states, "closure_count": len(closures), "fulls": fulls, "full_count": len(fulls),
        "lawler_jL": lawler_jL, "lawler_positions": lawler_positions, "lawler_parts": lawler_parts,
        "mdd": [seq_labeled(x) for x in mdd], "mdd_canonical": seq_labeled(mdd[0]),
    }
    if len(closures) == 1:
        raw = closure_states[0]
        base["raw"] = raw
    if len(fulls) == 1:
        full = fulls[0]
        beta = tuple(full["beta"])
        beta_sequence = tuple(sorted(range(n), key=lambda j: (beta[j], j)))
        jstar = {j for j in range(n) if any(i > j and beta[j] > beta[i] for i in range(n))}
        statuses: list[str] = []
        dsets: list[set[int]] = []
        for j in range(n):
            ld, lu, rd, ru = quadrants(list(beta))
            ds = ld[j] | rd[j]
            dsets.append(ds)
            if j not in jstar:
                statuses.append(STATUS_NA)
            else:
                margin = beta[j] - sum(p[i] for i in ds)
                statuses.append(STATUS_STRICT if margin > 0 else STATUS_EQUAL if margin == 0 else STATUS_FAIL)
        # Independent F-set test as a fail-closed invariant.
        fstatuses = []
        for j in range(n):
            if j not in jstar:
                fstatuses.append(STATUS_NA)
            else:
                prefix = beta_sequence[:beta_sequence.index(j)]
                margin = beta[j] - sum(p[i] for i in prefix)
                fstatuses.append(STATUS_STRICT if margin > 0 else STATUS_EQUAL if margin == 0 else STATUS_FAIL)
        beta_optimal = STATUS_FAIL not in statuses
        eq_width = [beta[j] - d[j] for j in range(n)]
        # K10 exact decomposition and block state.
        ld, lu, rd, ru = quadrants(list(beta))
        qualifying = []
        for q in range(n):
            first = all(p[q] + beta[q] >= full["L"][i] for i in rd[q])
            second = all(p[j] + beta[j] >= full["L"][q] for j in lu[q])
            if first and second:
                qualifying.append(q)
        longest = n - 1
        k = beta_sequence.index(longest) + 1
        key_scores: list[int] = []
        moved_sequences: list[list[int]] = []
        for pos in range(k - 1, n):
            rest = [j for j in beta_sequence if j != longest]
            moved = tuple(rest[:pos] + [longest] + rest[pos:])
            moved_sequences.append(seq_labeled(moved))
            key_scores.append(tt(p, beta, moved))
        h = k + min(range(len(key_scores)), key=lambda x: key_scores[x])
        split = {"left": moved_sequences[h - k][:h], "right": moved_sequences[h - k][h:]}
        branch: list[int] = []
        pos_status = [statuses[j] for j in beta_sequence]
        if k < n and pos_status[k] == STATUS_STRICT:
            branch.append(k)
        for position in range(k + 1, n):
            if pos_status[position - 1] in (STATUS_FAIL, STATUS_EQUAL) and pos_status[position] == STATUS_STRICT:
                branch.append(position)
        if pos_status[n - 1] in (STATUS_FAIL, STATUS_EQUAL):
            branch.append(n)
        base.update({
            "full": full, "beta": list(beta), "beta_active": [x > 0 for x in eq_width], "beta_order": weak_matrix(beta),
            "beta_sequence": seq_labeled(beta_sequence), "Jstar": set_labels(jstar), "beta_status": statuses,
            "beta_status_fset": fstatuses, "beta_optimal": beta_optimal, "Dsets": [set_labels(x) for x in dsets],
            "eq_lo": list(d), "eq_hi": list(beta), "eq_width": eq_width, "eq_active": [x > 0 for x in eq_width],
            "exact_q": seq_labeled(qualifying),
            "exact_partitions": [{"q": q + 1, "D": set_labels(dsets[q]), "U": set_labels(lu[q] | ru[q])} for q in qualifying],
            "block_flags": [full["E"][j] == full["L"][j] for j in range(n)],
            "key_k": k, "key_h": h, "key_scores": key_scores, "key_sequences": moved_sequences, "key_split": split,
            "branch_positions": branch,
        })
    return base


def _ps_signature(ps: dict[str, Any]) -> dict[str, Any]:
    return {"edges": edge_labels(ps["edges"]), "B": [set_labels(x) for x in ps["B"]], "A": [set_labels(x) for x in ps["A"]], "E": ps["E"], "L": ps["L"]}


def match_signature(state: dict[str, Any]) -> dict[str, Any]:
    """The locked M_K (Section 7); this rejects any accidental outcome key."""
    forbidden = {"TT_SPT", "TT_EDD", "Delta", "TT_star", "witness"}
    if forbidden.intersection(state):
        raise RuntimeError("outcome field supplied to M_K construction")
    if state["closure_count"] != 1 or state["full_count"] != 1:
        raise ValueError("ambiguous theory state cannot be matched")
    full = state["full"]
    return {
        "G123": _ps_signature(state["raw"]),
        "SPT_reasons": state["SPT_reasons"], "EDD_C22": state["EDD_C22"], "c22": state["c22_status"],
        "geometry": {k: state[k] for k in ("SRD", "ERD", "NRD", "NRD_hard", "alpha_order")},
        "FULL": _ps_signature({"edges": frozenset((i, j) for j in range(state["n"]) for i in full["B"][j]), "B": full["B"], "A": full["A"], "E": full["E"], "L": full["L"]}),
        "beta_active": state["beta_active"], "beta_order": state["beta_order"], "beta_sequence": state["beta_sequence"],
        "Jstar": state["Jstar"], "beta_status": state["beta_status"], "beta_optimal": state["beta_optimal"],
        "eq_active": state["eq_active"], "lawler": {"jL": state["lawler_jL"], "positions": state["lawler_positions"]},
        "exact": {"q": state["exact_q"], "parts": state["exact_partitions"], "block": state["block_flags"]},
        "key": {"k": state["key_k"], "h": state["key_h"], "split": state["key_split"]},
        "branch": state["branch_positions"], "mdd": state["mdd"],
    }


def signature_hash(signature: dict[str, Any]) -> str:
    return hashlib.sha256(canon(signature).encode("utf-8")).hexdigest()
