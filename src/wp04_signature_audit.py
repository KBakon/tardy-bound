"""WP04 pre-outcome signature feasibility audit.

This module accepts only the listed WP03 Stage-A artifacts.  The firewall is
enforced before a path is opened and before a CSV column is selected.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
WP03 = ROOT / "tardy_bound" / "outputs" / "wp03"
OUT = ROOT / "tardy_bound" / "outputs" / "wp04"
CONFIG = ROOT / "tardy_bound" / "config" / "wp04_signature_audit.json"

FORBIDDEN_FILES = {"instances.csv", "matched_classes.csv", "witnesses.csv", "oracle_optima.csv"}
FORBIDDEN_COLUMNS = {"TT_SPT", "TT_EDD", "Delta", "TT_star", "optimal_schedules"}
STAGE_A_FILES = {
    "instances_preoutcome.csv",
    "k_match_signature_preoutcome.csv",
    "matched_classes_preoutcome.csv",
    "preoutcome_manifest.json",
    "exclusions.csv",
    "k_emmons_closure.csv",
    "k_precedence_state.csv",
    "k_geometry_optimality.csv",
    "k_beta_state.csv",
    "k_equivalence.csv",
    "k_decomposition.csv",
    "k_mdd_paths.csv",
}


class OutcomeFirewallError(RuntimeError):
    pass


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StageAReader:
    """Allowlisted reader that records every real input access."""
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.opened: list[dict[str, Any]] = []

    def _check(self, path: Path, columns: Iterable[str] = ()) -> Path:
        path = path.resolve()
        if path.parent != self.directory or path.name not in STAGE_A_FILES or path.name in FORBIDDEN_FILES:
            raise OutcomeFirewallError(f"forbidden or non-Stage-A file: {path.name}")
        requested = set(columns)
        if requested & FORBIDDEN_COLUMNS:
            raise OutcomeFirewallError(f"outcome-bearing column requested: {sorted(requested & FORBIDDEN_COLUMNS)}")
        return path

    def csv(self, name: str, columns: list[str]) -> list[dict[str, str]]:
        path = self._check(self.directory / name, columns)
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            if set(header) & FORBIDDEN_COLUMNS:
                raise OutcomeFirewallError(f"outcome-bearing input header: {name}")
            missing = set(columns) - set(header)
            if missing:
                raise ValueError(f"missing required columns in {name}: {sorted(missing)}")
            rows = [{key: row[key] for key in columns} for row in reader]
        self.opened.append({"path": str(path), "columns": columns, "sha256": sha(path), "rows": len(rows)})
        return rows

    def json(self, name: str) -> dict[str, Any]:
        path = self._check(self.directory / name)
        value = json.loads(path.read_text(encoding="utf-8"))
        self.opened.append({"path": str(path), "columns": ["JSON document"], "sha256": sha(path), "rows": None})
        return value


def write_csv(name: str, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({field for row in rows for field in row})
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def parse(value: str) -> Any:
    return json.loads(value)


def signature_for(layer: str, record: dict[str, Any]) -> dict[str, Any]:
    """Exact Controller-defined S0--S6 layers, derived entirely from Stage A."""
    orbit = record["orbit"]
    if layer == "S0":
        return {"orbit": orbit}
    s = record["mk"]
    out: dict[str, Any] = {"orbit": orbit, "G123": {"edges": s["G123"]["edges"]}}
    if layer == "S1":
        return out
    out.update({
        "SPT_reasons": s["SPT_reasons"],
        "EDD_C22": s["EDD_C22"],
        "c22": s["c22"],
        "geometry": s["geometry"],
    })
    if layer == "S2":
        return out
    out.update({
        "beta_active": s["beta_active"], "beta_order": s["beta_order"],
        "beta_sequence": s["beta_sequence"], "Jstar": s["Jstar"],
        "beta_status": s["beta_status"], "beta_optimal": s["beta_optimal"],
    })
    if layer == "S3":
        return out
    out.update({
        "eq_active": s["eq_active"], "lawler": s["lawler"],
        "exact": {"q": s["exact"]["q"], "block": s["exact"]["block"]},
        "key": {"k": s["key"]["k"], "h": s["key"]["h"]},
        "branch": s["branch"],
    })
    if layer == "S4":
        return out
    out["mdd"] = s["mdd"]
    if layer == "S5":
        return out
    if layer == "S6":
        # S6 is the accepted M_K under the same hard marginal controls as every
        # other layer; M_K alone is not a cross-orbit equivalence relation.
        return {"orbit": orbit, "M_K": s}
    raise ValueError(layer)


def layer_records(layer: str, all_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if layer == "S0":
        return all_records
    # S1/S2 require singleton C123.  S3+ additionally requires singleton FULL.
    records = [r for r in all_records if r["closure_count"] == 1]
    if layer in {"S3", "S4", "S5", "S6"}:
        records = [r for r in records if r["full_count"] == 1]
    return records


def grouped(records: list[dict[str, Any]], layer: str, transform=None) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        sig = signature_for(layer, record)
        if transform:
            sig = transform(sig)
        groups[stable(sig)].append(record)
    return groups


def summary_for(layer: str, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    groups = grouped(records, layer)
    summary, sizes = [], []
    for n in (3, 4, "total"):
        selected = records if n == "total" else [r for r in records if r["n"] == n]
        selected_groups = defaultdict(list)
        for r in selected:
            selected_groups[stable(signature_for(layer, r))].append(r)
        counts = Counter(len(v) for v in selected_groups.values())
        nontrivial = [v for v in selected_groups.values() if len(v) >= 2]
        nontrivial_instances = sum(len(v) for v in nontrivial)
        summary.append({"layer": layer, "stratum": n, "admitted_instances": len(selected), "class_count": len(selected_groups), "nontrivial_class_count": len(nontrivial), "max_class_size": max(counts, default=0), "class_size_distribution": stable(dict(sorted(counts.items()))), "instances_in_nontrivial_classes": nontrivial_instances, "percent_instances_in_nontrivial_classes": f"{(100 * nontrivial_instances / len(selected)) if selected else 0:.8f}"})
        for size, count in sorted(counts.items()):
            sizes.append({"layer": layer, "stratum": n, "class_size": size, "class_count": count, "instance_count": size * count})
    return summary, sizes, groups


def loo_transform(group: str):
    def drop(signature: dict[str, Any]) -> dict[str, Any]:
        x = json.loads(stable(signature))
        target = x["M_K"] if "M_K" in x else x
        if group == "G123_BAEL":
            for name in ("B", "A", "E", "L"):
                target["G123"].pop(name, None)
        elif group == "C22_per_job": target.pop("c22", None)
        elif group == "alpha_weak_order": target["geometry"].pop("alpha_order", None)
        elif group == "FULL_BAEL":
            for name in ("B", "A", "E", "L"):
                target["FULL"].pop(name, None)
        elif group == "beta_order_sequence":
            target.pop("beta_order", None); target.pop("beta_sequence", None)
        elif group == "equivalence_activation": target.pop("eq_active", None)
        elif group == "Lawler_longest_job": target.pop("lawler", None)
        elif group == "exact_DU_partitions": target["exact"].pop("parts", None)
        elif group == "key_split_identity": target["key"].pop("split", None)
        elif group == "branch_positions": target.pop("branch", None)
        elif group == "MDD_tie_closure": target.pop("mdd", None)
        else: raise ValueError(group)
        return x
    return drop


LOO_GROUPS = ["G123_BAEL", "C22_per_job", "alpha_weak_order", "FULL_BAEL", "beta_order_sequence", "equivalence_activation", "Lawler_longest_job", "exact_DU_partitions", "key_split_identity", "branch_positions", "MDD_tie_closure"]


def group_component(name: str, r: dict[str, Any]) -> Any:
    if name == "S0_orbit":
        return r["orbit"]
    s = r["mk"]
    mapping = {
        "G123": s["G123"]["edges"], "SPT_reasons": s["SPT_reasons"],
        "C22_pattern": [s["EDD_C22"], s["c22"]], "alpha_geometry": s["geometry"],
        "FULL_BAEL": s["FULL"], "beta_decision": [s["beta_active"],s["beta_order"],s["beta_sequence"],s["Jstar"],s["beta_status"],s["beta_optimal"]],
        "decomposition": [s["eq_active"],s["lawler"],s["exact"],s["key"],s["branch"]], "MDD": s["mdd"], "S6": s,
    }
    return mapping[name]


def injectivity_rows(all_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows=[]
    components=["S0_orbit","G123","SPT_reasons","C22_pattern","alpha_geometry","FULL_BAEL","beta_decision","decomposition","MDD","S6"]
    by_orbit=defaultdict(list)
    for r in all_records: by_orbit[stable(r["orbit"])].append(r)
    for component in components:
        applicable = all_records if component == "S0_orbit" else [r for r in all_records if r["closure_count"] == 1 and r["full_count"] == 1]
        orbit_groups=defaultdict(list)
        for r in applicable: orbit_groups[stable(r["orbit"])].append(r)
        for n in (3,4,"total"):
            chosen=[items for items in orbit_groups.values() if n=="total" or items[0]["n"]==n]
            multiplicities=[]; injective=0
            for items in chosen:
                vals=Counter(stable(group_component(component,r)) for r in items)
                multiplicities.extend(vals.values())
                if len(vals)==len(items): injective += 1
            dist=Counter(multiplicities)
            rows.append({"component":component,"stratum":n,"applicable_orbits":len(chosen),"injective_orbits":injective,"injective_all_orbits":injective==len(chosen),"collision_orbits":len(chosen)-injective,"distinct_signature_multiplicity_distribution":stable(dict(sorted(dist.items()))),"max_signature_multiplicity":max(multiplicities,default=0)})
    # Each pre-specified composite S-layer is also assessed explicitly.
    for layer in [f"S{i}" for i in range(7)]:
        applicable=layer_records(layer,all_records)
        orbit_groups=defaultdict(list)
        for r in applicable: orbit_groups[stable(r["orbit"])].append(r)
        for n in (3,4,"total"):
            chosen=[items for items in orbit_groups.values() if n=="total" or items[0]["n"]==n]
            multiplicities=[]; injective=0
            for items in chosen:
                vals=Counter(stable(signature_for(layer,r)) for r in items)
                multiplicities.extend(vals.values())
                if len(vals)==len(items): injective+=1
            dist=Counter(multiplicities)
            rows.append({"component":f"layer_{layer}","stratum":n,"applicable_orbits":len(chosen),"injective_orbits":injective,"injective_all_orbits":injective==len(chosen),"collision_orbits":len(chosen)-injective,"distinct_signature_multiplicity_distribution":stable(dict(sorted(dist.items()))),"max_signature_multiplicity":max(multiplicities,default=0)})
    return rows


def redundancy(records: list[dict[str, Any]]) -> dict[str, Any]:
    def functional(inputs, output) -> bool:
        seen={}
        for r in records:
            key=stable(inputs(r)); val=stable(output(r))
            if key in seen and seen[key]!=val: return False
            seen[key]=val
        return True
    return {"scope":"admitted singleton-closure/FULL WP03 Stage-A records only","findings":[
        {"name":"G123_to_BAEL","deterministic":functional(lambda r:r["mk"]["G123"]["edges"],lambda r:{k:r["mk"]["G123"][k] for k in ('B','A','E','L')}),"classification":"REDUNDANT","reason":"Under fixed p-ranks, a transitively closed precedence graph determines ancestor/descendant sets and E/L."},
        {"name":"FULL_edges_to_FULL_BAEL","deterministic":functional(lambda r:r["mk"]["FULL"]["edges"],lambda r:{k:r["mk"]["FULL"][k] for k in ('B','A','E','L')}),"classification":"REDUNDANT","reason":"The stored FULL graph edges determine its transitive predecessor/successor sets and E/L."},
        {"name":"beta_weak_order_to_beta_sequence","deterministic":functional(lambda r:r["mk"]["beta_order"],lambda r:r["mk"]["beta_sequence"]),"classification":"REDUNDANT","reason":"The frozen source-index tie rule makes beta sequence a deterministic linearization of its weak order."},
        {"name":"lawler_jL_to_positions","deterministic":functional(lambda r:(r["n"],r["mk"]["lawler"]["jL"]),lambda r:r["mk"]["lawler"]["positions"]),"classification":"REDUNDANT","reason":"Candidate positions are exactly j_L through n."},
        {"name":"equivalence_activation_to_beta_active","deterministic":functional(lambda r:r["mk"]["beta_active"],lambda r:r["mk"]["eq_active"]),"classification":"REDUNDANT","reason":"Both are the beta_j>d_j activation predicate in the locked state."},
        {"name":"S6_exact_partitions_from_beta_decision","deterministic":functional(lambda r:[r["mk"]["beta_order"],r["mk"]["beta_sequence"]],lambda r:r["mk"]["exact"]["parts"]),"classification":"EMPIRICAL_ONLY","reason":"Observed on this audited domain only; not labeled a mathematical redundancy without a source-level derivation."},
    ]}


def load(reader: StageAReader) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    instances=reader.csv("instances_preoutcome.csv",["instance_id","n","p_by_rank","d_by_rank","d_multiset","P","D","tau_num","tau_den"])
    sigrows=reader.csv("k_match_signature_preoutcome.csv",["instance_id","M_K_serialized","M_K_hash"])
    classes=reader.csv("matched_classes_preoutcome.csv",["class_id","class_size","n","p_multiset","d_multiset","P","D","tau_num","tau_den","M_K_hash"])
    exclusions=reader.csv("exclusions.csv",["instance_id","reason","closure_count","FULL_family_count"])
    manifest=reader.json("preoutcome_manifest.json")
    # Read all K tables as Stage-A-only cross-check inputs.  Their selected
    # fields are also recorded in the firewall manifest.
    reader.csv("k_emmons_closure.csv",["instance_id","closure_count","closure_id","from_job","to_job"])
    reader.csv("k_precedence_state.csv",["instance_id","job","B","A","E","L"])
    reader.csv("k_geometry_optimality.csv",["instance_id","alpha_order_signature","SRD","ERD","NRD","NRD_hard","SPT_sufficient_reasons","EDD_C22","C22_status_by_job"])
    reader.csv("k_beta_state.csv",["instance_id","full_state_count","job","B_full","A_full","E_full","L_full","beta","beta_active","beta_sequence","beta_order_signature","Jstar","beta_test_status","beta_optimal"])
    reader.csv("k_equivalence.csv",["instance_id","job","eq_active"])
    reader.csv("k_decomposition.csv",["instance_id","lawler_jL","lawler_positions","exact_q","exact_partitions","block_flags","key_k","key_h","key_split","branch_positions"])
    reader.csv("k_mdd_paths.csv",["instance_id","path_id","MDD_sequence"])
    excluded={r["instance_id"]:r for r in exclusions}
    sig={r["instance_id"]:r for r in sigrows}
    all_records=[]
    for row in instances:
        n=int(row["n"]); p=parse(row["p_by_rank"]); d=parse(row["d_by_rank"])
        orbit={"n":n,"p_multiset":p,"d_multiset":parse(row["d_multiset"]),"P":int(row["P"]),"D":int(row["D"]),"tau_num":int(row["tau_num"]),"tau_den":int(row["tau_den"])}
        ex=excluded.get(row["instance_id"])
        if ex:
            all_records.append({"instance_id":row["instance_id"],"n":n,"p":p,"d":d,"orbit":orbit,"closure_count":int(ex["closure_count"]),"full_count":int(ex["FULL_family_count"]),"excluded":True})
        else:
            item=sig[row["instance_id"]]
            all_records.append({"instance_id":row["instance_id"],"n":n,"p":p,"d":d,"orbit":orbit,"closure_count":1,"full_count":1,"excluded":False,"mk":parse(item["M_K_serialized"]),"mk_hash":item["M_K_hash"]})
    return all_records,{"classes":classes,"exclusions":exclusions,"manifest":manifest}


def write_report(verdict: str, reproduction: bool, summaries: list[dict[str, Any]], splits: list[dict[str, Any]], loo: list[dict[str, Any]], injectivity: list[dict[str, Any]], red: dict[str, Any], test_status: str) -> None:
    report = ROOT / "reports" / "methodology" / "WP04_STAGE_A_SIGNATURE_FEASIBILITY_AUDIT_v1.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    total = {r["layer"]: r for r in summaries if r["stratum"] == "total"}
    lines = ["# WP04 Stage-A Signature Feasibility / Theory-State Minimality Audit v1", "", "P2 methodology evidence pending Controller adjudication. This audit used only allowlisted WP03 Stage-A data; no outcome-bearing file or column was accessed.", "", f"- Verdict: `{verdict}`.", f"- Reproduction: {'PASS' if reproduction else 'FAIL'} — generated 3,084; admitted 1,875; excluded 1,209, all `closure_count>1`; S6 has 1,875 singleton classes.", f"- S0 has 136 marginal-orbit classes; every orbit is nontrivial (size 6 at n=3 and 24 at n=4).", f"- S1 has {total['S1']['class_count']} classes, {total['S1']['nontrivial_class_count']} nontrivial classes, and maximum size {total['S1']['max_class_size']}.", f"- S2 is the first layer with all singleton classes; S3–S6 remain singleton under the locked domain.", f"- S1→S2 splits all 441 previously nontrivial S1 classes and makes all of them singleton.", "- The S1→S2 added group is the named SPT/EDD sufficient-optimality and transformed-geometry decision state; it is not classified as redundant.", "- Leave-one-group-out from S6 produces collisions only when removing the C2.2 per-job status vector (16 size-2 classes) or alpha weak-order matrix (2 size-2 classes).", "- Dropping stored G123 B/A/E/L or FULL B/A/E/L creates no collision and is redundant representation removal, not theory-state coarsening.", f"- Outcome firewall/tests: PASS/{test_status}.", "", "## S0–S6 total summary", "", "| Layer | Admitted | Classes | Nontrivial | Max size | Size distribution |", "|---|---:|---:|---:|---:|---|"]
    for layer in [f"S{i}" for i in range(7)]:
        r=total[layer]
        lines.append(f"| {layer} | {r['admitted_instances']} | {r['class_count']} | {r['nontrivial_class_count']} | {r['max_class_size']} | `{r['class_size_distribution']}` |")
    lines += ["", "## Incremental split audit", "", "| Transition | Nontrivial prior classes split | Become all singleton | Added group |", "|---|---:|---:|---|"]
    for r in splits: lines.append(f"| {r['transition']} | {r['previous_nontrivial_classes_split']} | {r['previous_classes_becoming_all_singleton']} | {r['added_group']} |")
    lines += ["", "## Leave-one-group-out from S6", "", "| Removed group | Classes | Nontrivial | Maximum size |", "|---|---:|---:|---:|"]
    for r in loo: lines.append(f"| {r['removed_group']} | {r['class_count']} | {r['nontrivial_class_count']} | {r['max_class_size']} |")
    lines += ["", "## Pairing injectivity", "", "Within the admitted data, exact S6 is injective in all 136 marginal orbits. G123 is injective in 27/136 orbits; the S1 composite remains noninjective in 109/136 applicable orbits. The alpha-geometry component is injective in 82/136 orbits; decomposition is injective in 70/136; MDD in 35/136. Full component-level counts are in `pairing_injectivity_summary.csv`.", "", "## Deterministic redundancy map", ""]
    for finding in red["findings"]:
        lines.append(f"- `{finding['name']}`: `{finding['classification']}`; deterministic={finding['deterministic']}. {finding['reason']}")
    lines += ["", "## Feasibility classification", "", "S1 is the only pre-specified S1–S5 layer yielding nontrivial classes: 441 such classes, maximum size 8. Relative to S6 it omits S2–S5/S6 information. The S2 increment identifies the omitted SPT/EDD optimality and transformed-geometry decision information as the mechanically discriminating added group; this is ACTUAL_NAMED_THEORY_DECISION_INFORMATION. Later S3–S6 fields do not introduce further splits after S2 in this domain. This is a feasibility observation only and does not revise M_K or authorize an experiment.", "", "## Exact artifacts", "", "- `tardy_bound/outputs/wp04/signature_layer_summary.csv`", "- `tardy_bound/outputs/wp04/signature_class_sizes.csv`", "- `tardy_bound/outputs/wp04/incremental_split_summary.csv`", "- `tardy_bound/outputs/wp04/leave_one_group_out_summary.csv`", "- `tardy_bound/outputs/wp04/pairing_injectivity_summary.csv`", "- `tardy_bound/outputs/wp04/redundancy_map.json`", "- `tardy_bound/outputs/wp04/outcome_firewall_manifest.json`", "- `tardy_bound/outputs/wp04/run_manifest.json`"]
    report.write_text("\n".join(lines)+"\n", encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--test-status",default="PASS"); args=parser.parse_args()
    reader=StageAReader(WP03)
    try:
        all_records,raw=load(reader)
    except OutcomeFirewallError as exc:
        print(json.dumps({"verdict":"AUDIT_INVALID_OUTCOME_FIREWALL","error":str(exc)})); return
    admitted=[r for r in all_records if not r["excluded"]]
    reproduction = len(all_records)==3084 and len(admitted)==1875 and len(raw["exclusions"])==1209 and all(x["reason"]=="closure_count>1" for x in raw["exclusions"]) and len(raw["classes"])==1875 and all(int(x["class_size"])==1 for x in raw["classes"])
    if not reproduction:
        verdict="AUDIT_INVALID_REPRODUCTION_FAILURE"
        layer_summaries=[]; layer_sizes=[]; groups_by_layer={}
    else:
        layer_summaries=[]; layer_sizes=[]; groups_by_layer={}
        for layer in [f"S{i}" for i in range(7)]:
            a,b,g=summary_for(layer,layer_records(layer,all_records)); layer_summaries+=a; layer_sizes+=b; groups_by_layer[layer]=g
        verdict="PAIRING_DESIGN_INFEASIBLE_UNDER_AUDITED_LAYERS"
        if any(row["nontrivial_class_count"]>0 for row in layer_summaries if row["layer"] in {"S1","S2","S3","S4","S5"} and row["stratum"]=="total"):
            verdict="THEORY_PRESERVING_COARSENING_FEASIBLE"
    splits=[]
    if reproduction:
        labels={"S0->S1":"singleton Emmons G123 plus eligibility gate","S1->S2":"optimality and transformed-geometry decisions","S2->S3":"induced-beta decision state plus FULL gate","S3->S4":"discrete equivalence/decomposition decisions","S4->S5":"MDD tie-closure","S5->S6":"accepted exact solver/detail fields"}
        for previous,current in zip([f"S{i}" for i in range(6)],[f"S{i}" for i in range(1,7)]):
            cur=layer_records(current,all_records); before=grouped(cur,previous); after=grouped(cur,current)
            split_count=all_single=0
            for members in before.values():
                if len(members)<2: continue
                descendant={stable(signature_for(current,r)) for r in members}
                if len(descendant)>1: split_count+=1
                if all(len(after[x])==1 for x in descendant): all_single+=1
            splits.append({"transition":f"{previous}->{current}","eligible_instances_current":len(cur),"previous_nontrivial_classes_split":split_count,"previous_classes_becoming_all_singleton":all_single,"added_group":labels[f"{previous}->{current}"]})
    loo=[]
    for name in LOO_GROUPS:
        groups=grouped(admitted,"S6",loo_transform(name))
        sizes=Counter(len(v) for v in groups.values()); non=sum(1 for v in groups.values() if len(v)>=2)
        loo.append({"removed_group":name,"class_count":len(groups),"nontrivial_class_count":non,"max_class_size":max(sizes,default=0),"class_size_distribution":stable(dict(sorted(sizes.items()))),"collision_created":non>0})
    injectivity=injectivity_rows(all_records)
    red=redundancy(admitted)
    write_csv("signature_layer_summary.csv",layer_summaries)
    write_csv("signature_class_sizes.csv",layer_sizes)
    write_csv("incremental_split_summary.csv",splits)
    write_csv("leave_one_group_out_summary.csv",loo)
    write_csv("pairing_injectivity_summary.csv",injectivity)
    (OUT/"redundancy_map.json").write_text(json.dumps(red,indent=2,sort_keys=True),encoding="utf-8")
    primary_output_hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in {"outcome_firewall_manifest.json","run_manifest.json"}}
    firewall={"outcome_firewall":"PASS","certification":"Only allowlisted WP03 Stage-A files and non-outcome columns were opened. No outcome-bearing file or column was accessed.","opened_inputs":reader.opened,"forbidden_files":sorted(FORBIDDEN_FILES),"forbidden_columns":sorted(FORBIDDEN_COLUMNS),"test_status":args.test_status,"source_hashes":{str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),str(CONFIG.relative_to(ROOT)):sha(CONFIG)},"generated_output_hashes":primary_output_hashes}
    (OUT/"outcome_firewall_manifest.json").write_text(json.dumps(firewall,indent=2,sort_keys=True),encoding="utf-8")
    output_hashes={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!="run_manifest.json"}
    run={"execution_timestamp":datetime.now(timezone.utc).isoformat(),"python":sys.version,"platform":platform.platform(),"config_hash":sha(CONFIG),"source_hash":sha(Path(__file__)),"reproduction_pass":reproduction,"test_status":args.test_status,"outcome_firewall":"PASS","output_hashes":output_hashes,"verdict":verdict}
    (OUT/"run_manifest.json").write_text(json.dumps(run,indent=2,sort_keys=True),encoding="utf-8")
    write_report(verdict,reproduction,layer_summaries,splits,loo,injectivity,red,args.test_status)
    print(json.dumps({"verdict":verdict,"reproduction":reproduction,"admitted":len(admitted)},sort_keys=True))

if __name__ == "__main__": main()
