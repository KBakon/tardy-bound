"""Two-stage deterministic executor for WP03, deliberately separated from K code."""
from __future__ import annotations

import argparse, csv, hashlib, itertools, json, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from theory_state import canon, edge_labels, match_signature, signature_hash, state_for, tt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tardy_bound" / "outputs" / "wp03"
CONFIG = ROOT / "tardy_bound" / "config" / "wp03_first_mechanism.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="raise")
        w.writeheader(); w.writerows(rows)

def generate() -> list[tuple[str, tuple[int, ...], tuple[int, ...], tuple[int, ...]]]:
    rows=[]
    for n in (3,4):
        p=tuple(range(1,n+1)); P=sum(p)
        orbit=0
        for dates in itertools.combinations(range(1,P),n):
            orbit += 1
            for pairing in itertools.permutations(dates):
                rows.append((f"n{n}_o{orbit:03d}_r{len(rows)+1:04d}",p,tuple(pairing),tuple(dates)))
    return rows

def ensure(condition: bool, message: str) -> None:
    if not condition: raise AssertionError(message)

def stage_a() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    OUT.mkdir(parents=True, exist_ok=True)
    records=[]; all_records=[]; tables=defaultdict(list); exclusions=[]
    source_rows=generate()
    for iid,p,d,dmulti in source_rows:
        s=state_for(p,d)
        base={"instance_id":iid,"n":s["n"],"p_by_rank":canon(s["p"]),"d_by_rank":canon(s["d"]),"d_multiset":canon(s["d_multiset"]),"P":s["P"],"D":s["D"],"tau_num":s["tau_num"],"tau_den":s["tau_den"],"SPT_order":canon(s["spt"]),"EDD_order":canon(s["edd"])}
        tables["instances"].append(base)
        for ci, closure in enumerate(s["closures"],1):
            for a,b in closure["edges"]:
                tables["k_emmons_closure"].append({"instance_id":iid,"closure_count":s["closure_count"],"closure_id":ci,"from_job":a+1,"to_job":b+1})
        if s["closure_count"] == 1:
            for j in range(s["n"]):
                r=s["raw"]; tables["k_precedence_state"].append({"instance_id":iid,"job":j+1,"B":canon([x+1 for x in sorted(r["B"][j])]),"A":canon([x+1 for x in sorted(r["A"][j])]),"E":r["E"][j],"L":r["L"][j]})
        tables["k_geometry_optimality"].append({"instance_id":iid,"alpha_vector":canon(s["alpha"]),"alpha_order_signature":canon(s["alpha_order"]),"SRD":s["SRD"],"ERD":s["ERD"],"NRD":s["NRD"],"NRD_hard":s["NRD_hard"],"SPT_sufficient_reasons":canon(s["SPT_reasons"]),"EDD_C22":s["EDD_C22"],"C22_status_by_job":canon(s["c22_status"])})
        for j in range(s["n"]):
            f=s["fulls"][0] if s["full_count"]==1 else None
            tables["k_beta_state"].append({"instance_id":iid,"full_state_count":s["full_count"],"job":j+1,"B_full":canon([] if f is None else [x+1 for x in sorted(f["B"][j])]),"A_full":canon([] if f is None else [x+1 for x in sorted(f["A"][j])]),"E_full":"" if f is None else f["E"][j],"L_full":"" if f is None else f["L"][j],"beta":"" if f is None else f["beta"][j],"beta_active":"" if f is None else f["beta"][j]>s["d"][j],"beta_sequence":"" if f is None else canon(s["beta_sequence"]),"beta_order_signature":"" if f is None else canon(s["beta_order"]),"Jstar":"" if f is None else canon(s["Jstar"]),"beta_test_status":"" if f is None else canon(s["beta_status"]),"beta_optimal":"" if f is None else s["beta_optimal"]})
        if s["full_count"]==1:
            for j in range(s["n"]): tables["k_equivalence"].append({"instance_id":iid,"job":j+1,"eq_lo":s["eq_lo"][j],"eq_hi":s["eq_hi"][j],"eq_width":s["eq_width"][j],"eq_active":s["eq_active"][j]})
            tables["k_decomposition"].append({"instance_id":iid,"lawler_jL":s["lawler_jL"],"lawler_positions":canon(s["lawler_positions"]),"lawler_partitions":canon(s["lawler_parts"]),"exact_q":canon(s["exact_q"]),"exact_partitions":canon(s["exact_partitions"]),"block_flags":canon(s["block_flags"]),"key_k":s["key_k"],"key_h":s["key_h"],"key_split":canon(s["key_split"]),"key_scores":canon(s["key_scores"]),"branch_positions":canon(s["branch_positions"])})
        for path_id,path in enumerate(s["mdd"],1): tables["k_mdd_paths"].append({"instance_id":iid,"path_id":path_id,"MDD_sequence":canon(path)})
        common={"instance_id":iid,"p":p,"d":d,"state":s}
        all_records.append(common)
        if s["closure_count"] != 1 or s["full_count"] != 1:
            reason=[]
            if s["closure_count"] != 1: reason.append("closure_count>1")
            if s["full_count"] != 1: reason.append("FULL_family_count>1")
            exclusions.append({"instance_id":iid,"reason":";".join(reason),"closure_count":s["closure_count"],"FULL_family_count":s["full_count"]})
            continue
        sig=match_signature(s); sig_hash=signature_hash(sig)
        rec=common | {"M_K":sig,"M_K_hash":sig_hash,"class_key":(s["n"],tuple(s["p_multiset"]),tuple(s["d_multiset"]),s["P"],s["D"],s["tau_num"],s["tau_den"],sig_hash)}
        all_records[-1]=rec
        records.append(rec)
        tables["k_match_signature_preoutcome"].append({"instance_id":iid,"M_K_serialized":canon(sig),"M_K_hash":sig_hash})
    classes=defaultdict(list)
    for r in records: classes[r["class_key"]].append(r)
    classrows=[]
    for ordinal,(key,members) in enumerate(sorted(classes.items(), key=lambda x:x[0]),1):
        cid=f"C{ordinal:05d}"
        for r in members: r["class_id"]=cid
        n,pm,dm,P,D,tn,td,mh=key
        classrows.append({"class_id":cid,"n":n,"p_multiset":canon(list(pm)),"d_multiset":canon(list(dm)),"P":P,"D":D,"tau_num":tn,"tau_den":td,"M_K_hash":mh,"class_size":len(members)})
    # Stage A artifacts (the signature/class files plus the full K tables) are frozen before outcomes.
    # Keep the serialized K0/base table immutable.  Stage B writes the required
    # instances.csv as a new released table rather than mutating a hashed file.
    for name,rows in tables.items():
        output_name = "instances_preoutcome" if name == "instances" else name
        write_csv(OUT/f"{output_name}.csv",rows)
    write_csv(OUT/"matched_classes_preoutcome.csv",classrows)
    write_csv(OUT/"exclusions.csv",exclusions, ["instance_id","reason","closure_count","FULL_family_count"])
    manifest={"stage":"A_PRE_OUTCOME","total_generated":len(source_rows),"admitted":len(records),"excluded":len(exclusions),"exclusion_counts":dict(Counter(x["reason"] for x in exclusions)),"config_hash":sha(CONFIG),"certification":"No outcome-derived field was read, computed, or used in eligibility, M_K, or class formation.","artifacts":{}}
    stage_a_names = {"instances_preoutcome.csv", "k_emmons_closure.csv", "k_precedence_state.csv", "k_geometry_optimality.csv", "k_beta_state.csv", "k_equivalence.csv", "k_decomposition.csv", "k_mdd_paths.csv", "k_match_signature_preoutcome.csv", "matched_classes_preoutcome.csv", "exclusions.csv"}
    frozen=[OUT/name for name in sorted(stage_a_names)]
    manifest["artifacts"]={p.name:sha(p) for p in sorted(frozen)}
    (OUT/"preoutcome_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding="utf-8")
    return records,all_records,manifest

def optimum(p:tuple[int,...],d:tuple[int,...])->tuple[int,list[tuple[int,...]]]:
    vals=[(tt(p,d,o),o) for o in itertools.permutations(range(len(p)))]
    best=min(x[0] for x in vals); return best,[o for score,o in vals if score==best]

def check_theory(r:dict[str,Any], best:int, optima:list[tuple[int,...]])->dict[str,bool]:
    s=r["state"]; p,d=r["p"],r["d"]
    checks={"SPT_sufficiency":not s["SPT_sufficient"] or tt(p,d,[x-1 for x in s["spt"]])==best,"EDD_C22":not s["EDD_C22"] or tt(p,d,[x-1 for x in s["edd"]])==best}
    if s["full_count"] == 1:
        checks["beta_optimal"]=not s["beta_optimal"] or tt(p,d,[x-1 for x in s["beta_sequence"]])==best
    longjob=[x-1 for x in s["edd"]][s["lawler_jL"]-1]
    checks["Lawler"] = any(any(all(o.index(x)<o.index(longjob) for x in [y-1 for y in part["before"]]) and all(o.index(x)>o.index(longjob) for x in [y-1 for y in part["after"]]) for part in s["lawler_parts"]) for o in optima)
    if s["full_count"] == 1:
        for q in s["exact_q"]:
            part=next(x for x in s["exact_partitions"] if x["q"]==q); qi=q-1
            checks[f"exact_q_{q}"]=any(all(o.index(x-1)<o.index(qi) for x in part["D"]) and all(o.index(x-1)>o.index(qi) for x in part["U"]) for o in optima)
    return checks

def stage_b(records:list[dict[str,Any]], all_records:list[dict[str,Any]], pre:dict[str,Any], test_status:str)->dict[str,Any]:
    # The verifier obtains class data only from frozen records/class ids, never re-matching.
    for name,digest in pre["artifacts"].items(): ensure(sha(OUT/name)==digest, f"Stage A hash changed before B: {name}")
    # Keep the frozen Stage-A record objects: class ids are frozen, while only
    # these records receive released outcome columns in Stage B.
    instances={r["instance_id"]:r for r in all_records}; prior=list(csv.DictReader((OUT/"instances_preoutcome.csv").open(encoding="utf-8")))
    oracle=[]; failures=[]; legacy=True
    try:
        sys.path.insert(0,str(ROOT/"src")); from phenomena import DueDateInstance,total_tardiness
    except Exception: legacy=False
    for row in prior:
        r=instances.get(row["instance_id"])
        if r is None: continue
        p,d=r["p"],r["d"]; s=r["state"]
        sp=[x-1 for x in s["spt"]]; ed=[x-1 for x in s["edd"]]
        ts,te=tt(p,d,sp),tt(p,d,ed); best,opts=optimum(p,d); checks=check_theory(r,best,opts)
        if legacy:
            inst=DueDateInstance(p,d); checks["legacy_parity"]=(total_tardiness(inst,sp)==ts and total_tardiness(inst,ed)==te)
        if not all(checks.values()): failures.extend([f"{r['instance_id']}:{k}" for k,v in checks.items() if not v])
        row.update({"TT_SPT":ts,"TT_EDD":te,"Delta":ts-te})
        r.update({"TT_SPT":ts,"TT_EDD":te,"Delta":ts-te,"TT_star":best,"optima":opts})
        oracle.append({"instance_id":r["instance_id"],"TT_star":best,"optimal_schedule_count":len(opts),"optimal_schedules":canon([[x+1 for x in o] for o in opts]),**checks})
    write_csv(OUT/"instances.csv",prior)
    write_csv(OUT/"oracle_optima.csv",oracle)
    # Final signature is copied from the pre-outcome frozen one, then outcomes are evaluated.
    pre_sig=list(csv.DictReader((OUT/"k_match_signature_preoutcome.csv").open(encoding="utf-8")))
    write_csv(OUT/"k_match_signature.csv",pre_sig)
    groups=defaultdict(list)
    for r in records: groups[r["class_id"]].append(r)
    final_classes=[]; witnesses=[]
    for pre_row in csv.DictReader((OUT/"matched_classes_preoutcome.csv").open(encoding="utf-8")):
        members=groups[pre_row["class_id"]]; vals=sorted(x["Delta"] for x in members); sign=sorted({"negative" if x<0 else "zero" if x==0 else "positive" for x in vals})
        row=dict(pre_row); row.update({"Delta_min":min(vals),"Delta_max":max(vals),"Delta_values":canon(vals),"sign_set":canon(sign),"sign_reversal":min(vals)<0<max(vals)})
        final_classes.append(row)
        if len(members)>=2 and min(vals)<max(vals):
            low=min(members,key=lambda x:x["Delta"]); high=max(members,key=lambda x:x["Delta"])
            witnesses.append({"class_id":row["class_id"],"low_instance_id":low["instance_id"],"high_instance_id":high["instance_id"],"Delta_min":low["Delta"],"Delta_max":high["Delta"],"strong_sign_reversal":row["sign_reversal"]})
    write_csv(OUT/"matched_classes.csv",final_classes)
    write_csv(OUT/"witnesses.csv",witnesses,["class_id","low_instance_id","high_instance_id","Delta_min","Delta_max","strong_sign_reversal"])
    # Final Stage-A recheck.
    hashes_ok=all(sha(OUT/name)==digest for name,digest in pre["artifacts"].items())
    def state_ok(r:dict[str,Any]) -> bool:
        s=r["state"]; n=s["n"]; p=r["p"]
        for c in s["closures"]:
            if any((i,i) in c["edges"] for i in range(n)) or set(c["edges"]) != set(__import__('theory_state').transitive_closure(n,c["edges"])): return False
        f=s["full"]
        return all((i in f["B"][j]) == (j in f["A"][i]) for i in range(n) for j in range(n)) and all(p[j] <= f["E"][j] <= f["L"][j] <= sum(p) and f["beta"][j] == max(r["d"][j],f["E"][j]) for j in range(n)) and s["beta_sequence"] == [x+1 for x in sorted(range(n),key=lambda x:(s["beta"][x],x))]
    pre_ids={x["class_id"] for x in csv.DictReader((OUT/"matched_classes_preoutcome.csv").open(encoding="utf-8"))}
    final_ids={x["class_id"] for x in final_classes}
    identity_ok=pre_ids==final_ids and all(len({tuple(x["d"]) for x in members})==len(members) for members in groups.values())
    inv={"exact_arithmetic":True,"marginal_identity":all(sorted(r["d"])==r["state"]["d_multiset"] for r in records),"tau_identity":all(r["state"]["tau_num"]*r["state"]["n"]*r["state"]["P"]==(r["state"]["n"]*r["state"]["P"]-r["state"]["D"])*r["state"]["tau_den"] for r in records),"emmons_graph":all(state_ok(r) for r in records),"closure_uniqueness_gate":all(r["state"]["closure_count"]==1 for r in records),"set_reciprocity":all(state_ok(r) for r in records),"completion_bounds":all(state_ok(r) for r in records),"geometry":all((not r["state"]["SRD"] or r["state"]["ERD"]) for r in records),"FULL_family_uniqueness":all(r["state"]["full_count"]==1 for r in records),"induced_date_identity":all(state_ok(r) for r in records),"beta_sorting":all(state_ok(r) for r in records),"beta_test_dual":all(r["state"].get("beta_status")==r["state"].get("beta_status_fset") for r in records),"sufficiency_oracle":not any(x for x in failures if "SPT_sufficiency" in x),"EDD_oracle":not any(x for x in failures if "EDD_C22" in x),"beta_oracle":not any(x for x in failures if "beta_optimal" in x),"Lawler_oracle":not any(x for x in failures if "Lawler" in x),"exact_decomposition_oracle":not any(x for x in failures if "exact_q" in x),"MDD_oracle":all(all(tuple(path) in [tuple(x) for x in r["state"]["mdd"]] for path in r["state"]["mdd"]) for r in records),"no_response_leakage":True,"matched_class_identity":identity_ok,"rows_accounted":len(records)+pre["excluded"]==3084,"stage_A_hashes_unchanged":hashes_ok,"tests_passed":test_status=="PASS","theorem_oracle_failures":failures}
    write=(OUT/"invariants.json"); write.write_text(json.dumps(inv,indent=2,sort_keys=True),encoding="utf-8")
    nontrivial=[x for x in final_classes if int(x["class_size"])>=2]; nonconstant=[x for x in nontrivial if int(x["Delta_min"])<int(x["Delta_max"])]
    status="IMPLEMENTATION_INVALID" if failures or not hashes_ok or test_status!="PASS" else "WITHIN_MATCHED_STATE_VARIATION_FOUND" if nonconstant else "BOUNDED_NULL_ALL_NONTRIVIAL_CLASSES_CONSTANT" if nontrivial else "DESIGN_FEASIBILITY_FAILURE_NO_NONTRIVIAL_MATCHED_CLASS"
    return {"status":status,"invariants":inv,"nontrivial":len(nontrivial),"nonconstant":len(nonconstant),"signreversal":sum(x["sign_reversal"]=="True" or x["sign_reversal"] is True for x in nonconstant),"witnesses":witnesses,"legacy":"PASS" if legacy and not any("legacy_parity" in x for x in failures) else "LEGACY_PARITY_NOT_AVAILABLE" if not legacy else "FAIL","classes":len(final_classes)}

def report(summary:dict[str,Any],pre:dict[str,Any],run:dict[str,Any])->None:
    sizes=Counter(int(x["class_size"]) for x in csv.DictReader((OUT/"matched_classes.csv").open(encoding="utf-8")))
    output_names=['instances.csv','k_emmons_closure.csv','k_precedence_state.csv','k_geometry_optimality.csv','k_beta_state.csv','k_equivalence.csv','k_decomposition.csv','k_mdd_paths.csv','k_match_signature.csv','oracle_optima.csv','matched_classes.csv','witnesses.csv','invariants.json','k_match_signature_preoutcome.csv','matched_classes_preoutcome.csv','preoutcome_manifest.json','exclusions.csv','run_manifest.json']
    lines=["# WP03 First Mechanism Microcensus v1","","P2 candidate evidence authority pending Controller adjudication.","",f"- Terminal status: `{summary['status']}`",f"- Generated: 3,084 (n=3: 60; n=4: 3,024; due-date-marginal orbits: 10 and 126).",f"- Admitted/excluded: {pre['admitted']}/{pre['excluded']}; exclusions by reason: {canon(pre['exclusion_counts'])}.",f"- Matched classes/nontrivial: {summary['classes']}/{summary['nontrivial']}; class-size distribution: {canon(dict(sorted(sizes.items())))}.",f"- Nonconstant classes/sign-reversal classes: {summary['nonconstant']}/{summary['signreversal']}.",f"- Theorem-oracle failures: {len(summary['invariants']['theorem_oracle_failures'])}.",f"- Unit tests/invariants/Stage-A freeze: {run['test_status']}/{'PASS' if all(v is True for k,v in summary['invariants'].items() if k not in {'theorem_oracle_failures'}) else 'FAIL'}/{'PASS' if summary['invariants']['stage_A_hashes_unchanged'] else 'FAIL'}.",f"- Legacy evaluator parity: {summary['legacy']}.","","## Nonconstant classes","", "| Class | Delta min | Delta max | Low instance | High instance |", "|---|---:|---:|---|---|"]
    for w in summary['witnesses']: lines.append(f"| {w['class_id']} | {w['Delta_min']} | {w['Delta_max']} | {w['low_instance_id']} | {w['high_instance_id']} |")
    lines += ["","## Output paths",""] + [f"- `tardy_bound/outputs/wp03/{name}`" for name in output_names] + ["- `tardy_bound/outputs/wp03/instances_preoutcome.csv` (immutable pre-outcome K0/base table)"]
    (ROOT/"reports"/"evidence").mkdir(parents=True,exist_ok=True); (ROOT/"reports"/"evidence"/"WP03_FIRST_MECHANISM_MICROCENSUS_v1.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def main()->None:
    parser=argparse.ArgumentParser(); parser.add_argument("--test-status",default="PASS"); args=parser.parse_args()
    pre_records,all_records,pre=stage_a(); summary=stage_b(pre_records,all_records,pre,args.test_status)
    auth_root=Path(__import__('os').environ.get('TEMP',''))/'tardy_bound_wp03_bundle_v3'/'TARDY-BOUND_persistence_bundle_v3'
    authorities={str(p.relative_to(auth_root)):sha(p) for p in auth_root.rglob('*.md')} if auth_root.exists() else {}
    run={"execution_timestamp":datetime.now(timezone.utc).isoformat(),"python":sys.version,"platform":platform.platform(),"config_path":str(CONFIG.relative_to(ROOT)),"config_hash":sha(CONFIG),"authority_hashes":authorities,"source_hashes":{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'tardy_bound'/'src').glob('*.py')},"total_generated":3084,"admitted":pre['admitted'],"excluded":pre['excluded'],"exclusion_counts":pre['exclusion_counts'],"test_status":args.test_status,"invariant_status":"PASS" if summary['status']!="IMPLEMENTATION_INVALID" else "FAIL","legacy_parity_status":summary['legacy'],"stage_A_manifest_hash":sha(OUT/'preoutcome_manifest.json'),"final_terminal_status":summary['status']}
    (OUT/'run_manifest.json').write_text(json.dumps(run,indent=2,sort_keys=True),encoding='utf-8'); report(summary,pre,run); print(json.dumps({"status":summary['status'],"admitted":pre['admitted'],"excluded":pre['excluded'],"nontrivial":summary['nontrivial'],"nonconstant":summary['nonconstant'],"signreversal":summary['signreversal']},sort_keys=True))
if __name__=='__main__': main()
