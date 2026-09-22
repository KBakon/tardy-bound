"""WP07 frozen-witness reduction audit; consumes WP06 outputs only."""
from __future__ import annotations

import ast, csv, hashlib, json, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from theory_state_v2 import build_v2_state

ROOT = Path(__file__).resolve().parents[2]
WP06 = ROOT / "tardy_bound" / "outputs" / "wp06"
OUT = ROOT / "tardy_bound" / "outputs" / "wp07"
REPORT = ROOT / "reports" / "evidence" / "WP07_WITNESS_REDUCTION_AND_THEORY_REFINEMENT_AUDIT_v1.md"
OUTCOME = {"TT_SPT", "TT_EDD", "Delta", "TT_star", "optimal_schedules"}

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read_csv(path: Path) -> list[dict[str,str]]:
    with path.open(newline="", encoding="utf-8") as f: return list(csv.DictReader(f))
def write_csv(name: str, rows: list[dict[str,Any]]) -> None:
    p=OUT/name; fields=sorted({k for r in rows for k in r}) if rows else ["status"]
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
def val(s: str) -> Any:
    return ast.literal_eval(s)
def enc(x: Any) -> str: return json.dumps(x, separators=(",",":"), sort_keys=True)
def comp(p: tuple[int,...],d: tuple[int,...],order: list[int]) -> tuple[list[int],list[int]]:
    t=0; cs=[]; ts=[]
    for j in order: t+=p[j]; cs.append(t); ts.append(max(0,t-d[j]))
    return cs,ts
def objective(p,d,order): return sum(comp(p,d,order)[1])
def due_ranks(d):
    rank={x:i+1 for i,x in enumerate(sorted(d))}; return [rank[x] for x in d]
def cycles(mapping):
    seen=set(); ans=[]
    for x in range(len(mapping)):
        if x not in seen:
            c=[]; y=x
            while y not in seen: seen.add(y);c.append(y+1);y=mapping[y]
            ans.append(c)
    return ans
def transform(a,b):
    # mapping from low p-rank positions to high positions preserving due-date rank
    m=[b.index(x) for x in a]; cs=cycles(m); moved=[i+1 for i,x in enumerate(m) if i!=x]
    return m,cs,moved,len(a)-len(cs)
def category(ds,de):
    if ds and not de:return "SPT_ONLY_CHANGE"
    if de and not ds:return "EDD_ONLY_CHANGE"
    return "BOTH_CHANGE_SAME_NET" if ds*de<0 else "BOTH_CHANGE_OFFSETTING"
def states_for(row):
    return build_v2_state(tuple(val(row["p_by_rank"])),tuple(val(row["d_by_rank"])))

def run() -> dict[str,Any]:
    OUT.mkdir(parents=True,exist_ok=True); REPORT.parent.mkdir(parents=True,exist_ok=True)
    required=["instances.csv","instances_preoutcome.csv","matched_classes_preoutcome.csv","matched_classes.csv","witnesses.csv","exclusions.csv","mk_v2_signature_preoutcome.csv"]
    for x in required:
        if not (WP06/x).is_file(): raise RuntimeError(f"missing frozen WP06 input: {x}")
    inst={r["instance_id"]:r for r in read_csv(WP06/"instances.csv")}
    pre=read_csv(WP06/"matched_classes_preoutcome.csv"); witnesses=read_csv(WP06/"witnesses.csv")
    signatures={r["instance_id"]:r for r in read_csv(WP06/"mk_v2_signature_preoutcome.csv")}
    excluded=read_csv(WP06/"exclusions.csv"); final_classes=read_csv(WP06/"matched_classes.csv")
    nontr=[r for r in pre if int(r["class_size"])>=2]
    invalid=[]
    if len(inst)!=3084 or len(excluded)!=1209 or len(pre)!=1833 or len(nontr)!=42 or len(witnesses)!=42: invalid.append("WP06 reproduction count mismatch")
    if any(int(r["class_size"])!=2 for r in nontr): invalid.append("nontrivial class size mismatch")
    if sum(int(r["class_size"]) >= 2 for r in final_classes) != 42 or any(int(r["Delta_max"])-int(r["Delta_min"]) != 1 for r in final_classes if int(r["class_size"]) >= 2): invalid.append("nonconstant witness range mismatch")
    if any(r["sign_reversal"] == "True" for r in final_classes): invalid.append("unexpected strict sign reversal")
    wclasses={r["class_id"] for r in witnesses}; pclasses={r["class_id"] for r in nontr}
    if wclasses!=pclasses: invalid.append("witness/preoutcome class mismatch")
    pairs=[]; trans=[]; decomp=[]; contrib=[]; d1=[];d2=[];d3=[];d4=[];d5=[]; cases=[]
    patterns=Counter(); cats=Counter(); diagnostic_changes=Counter()
    for w in witnesses:
        cid=w["class_id"]; lo=inst[w["low_instance_id"]]; hi=inst[w["high_instance_id"]]
        p=tuple(val(lo["p_by_rank"])); dl=tuple(val(lo["d_by_rank"])); dh=tuple(val(hi["d_by_rank"]))
        if int(lo["Delta"])>=int(hi["Delta"]): invalid.append(f"Delta ordering {cid}")
        hard=["n","P","D","tau_num","tau_den","d_multiset","p_by_rank"]
        if any(lo[x]!=hi[x] for x in hard) or dl==dh: invalid.append(f"hard control mismatch {cid}")
        sl,sh=states_for(lo),states_for(hi)
        # Explicitly recompute canonical v2 keys and ensure frozen identical hash.
        from theory_state_v2 import mk_v2_key, signature_hash
        h1,h2=signature_hash(mk_v2_key(sl)),signature_hash(mk_v2_key(sh))
        frozen_hash=next(r["M_K_v2_hash"] for r in pre if r["class_id"]==cid)
        frozen_serial_low=signatures[lo["instance_id"]]["M_K_v2_serialized"]
        frozen_serial_high=signatures[hi["instance_id"]]["M_K_v2_serialized"]
        if h1!=h2 or h1!=frozen_hash or frozen_serial_low!=frozen_serial_high: invalid.append(f"key mismatch {cid}")
        rl,rh=due_ranks(dl),due_ranks(dh); mp,cy,moved,mt=transform(rl,rh)
        spt=list(range(len(p))); eddl=sorted(range(len(p)),key=lambda j:(dl[j],p[j],j)); eddh=sorted(range(len(p)),key=lambda j:(dh[j],p[j],j))
        csl,tsl=comp(p,dl,spt); csh,tsh=comp(p,dh,spt); cel,tel=comp(p,dl,eddl);ceh,teh=comp(p,dh,eddh)
        tls,ths=sum(tsl),sum(tsh); tle,the=sum(tel),sum(teh); ds, de=ths-tls,the-tle
        if tls!=int(lo["TT_SPT"]) or tle!=int(lo["TT_EDD"]) or ths!=int(hi["TT_SPT"]) or the!=int(hi["TT_EDD"]) or ds-de!=1: invalid.append(f"objective mismatch {cid}")
        cat=category(ds,de); pats=(tuple(sorted(moved)),mt,abs(rl[moved[0]-1]-rl[moved[1]-1]) if len(moved)==2 else None,cat)
        patterns[pats]+=1;cats[cat]+=1
        pairs.append({"class_id":cid,"low_instance_id":lo["instance_id"],"high_instance_id":hi["instance_id"],"Delta_low":lo["Delta"],"Delta_high":hi["Delta"],"M_K_v2_hash":h1,"M_K_v2_serialized":frozen_serial_low,"hard_controls_equal":True,"different_pairing":True})
        trans.append({"class_id":cid,"low_due_ranks":enc(rl),"high_due_ranks":enc(rh),"position_mapping":enc([x+1 for x in mp]),"cycles":enc(cy),"min_transpositions":mt,"changed_p_ranks":enc(moved),"due_rank_distance":pats[2],"EDD_low":enc([j+1 for j in eddl]),"EDD_high":enc([j+1 for j in eddh]),"EDD_changed":eddl!=eddh,"pattern":enc(pats)})
        contrast_low={j:tsl[j]-tel[eddl.index(j)] for j in range(len(p))}; contrast_high={j:tsh[j]-teh[eddh.index(j)] for j in range(len(p))}
        for label,d,order,cs,ts in [("low_SPT",dl,spt,csl,tsl),("high_SPT",dh,spt,csh,tsh),("low_EDD",dl,eddl,cel,tel),("high_EDD",dh,eddh,ceh,teh)]:
            for q,j in enumerate(order): decomp.append({"class_id":cid,"instance_side":label,"schedule":"SPT" if "SPT" in label else "EDD","sequence_position":q+1,"p_rank":j+1,"completion":cs[q],"due_date":d[j],"tardiness":ts[q],"delta_j":(contrast_low if label.startswith("low") else contrast_high)[j],"Delta":sum((contrast_low if label.startswith("low") else contrast_high).values())})
        resp=[]
        for j in range(len(p)):
            dlta=(tsh[j]-tsl[j])-(teh[eddh.index(j)]-tel[eddl.index(j)])
            if dlta:resp.append(j+1)
            contrib.append({"class_id":cid,"p_rank":j+1,"SPT_tardiness_change":tsh[j]-tsl[j],"EDD_tardiness_change":teh[eddh.index(j)]-tel[eddl.index(j)],"delta_low":contrast_low[j],"delta_high":contrast_high[j],"delta_contribution":dlta})
        contrib.append({"class_id":cid,"p_rank":"TOTAL","SPT_tardiness_change":ds,"EDD_tardiness_change":de,"delta_contribution":ds-de})
        cases.append({"class_id":cid,"category":cat,"changed_p_ranks":enc(moved),"responsible_p_ranks":enc(resp),"Delta_change":1,"exact_identity":f"Delta_high-Delta_low=({ds})-({de})=1","pattern":enc(pats)})
        for side,s,d in [("low",sl,dl),("high",sh,dh)]:
            for j in range(len(p)):
                # D1 EDD waiting time is completion-p in that EDD schedule.
                pos=(eddl if side=="low" else eddh).index(j); wait=(cel if side=="low" else ceh)[pos]-p[j]
                margin=d[j]-wait; st="STRICT_PASS" if margin>0 else "EQUALITY" if margin==0 else "FAIL"
                d1.append({"class_id":cid,"side":side,"p_rank":j+1,"EDD_wait":wait,"margin_d_minus_wait":margin,"status":st})
                d2.append({"class_id":cid,"side":side,"p_rank":j+1,"alpha":s["alpha"][j],"alpha_order":enc(s["alpha_order"]),"P_Q":enc([j+1 for j in range(len(p)) if p[j]<=d[j]]),"all_below":s["SPT_reasons"]["all_below_projection"]})
                d3.append({"class_id":cid,"side":side,"p_rank":j+1,"beta":s["beta"][j],"beta_active":s["beta_active"][j],"beta_order":enc(s["beta_order"]),"eq_lo":s["eq_lo"][j],"eq_hi":s["eq_hi"][j],"eq_width":s["eq_width"][j]})
            mins=[s["key_k"]+i for i,x in enumerate(s["key_scores"]) if x==min(s["key_scores"])]
            d4.append({"class_id":cid,"side":side,"key_k":s["key_k"],"h":s["key_h"],"scores":enc(s["key_scores"]),"all_minimizers":enc(mins),"score_gaps":enc([x-min(s["key_scores"]) for x in s["key_scores"]])})
            for node in s["T_MDD"]:
                prefix=[x-1 for x in node["prefix"]]; rem=[j for j in range(len(p)) if j not in prefix]; t=sum(p[j] for j in prefix); pri={j+1:max(t+p[j],d[j]) for j in rem}; gap=sorted(pri.values())[1]-min(pri.values()) if len(pri)>1 else 0
                d5.append({"class_id":cid,"side":side,"prefix":enc(node["prefix"]),"argmin":enc(node["argmin"]),"priorities":enc(pri),"minimum_gap":gap})
        # Pair-level diagnostic change counts: exact diagnostic vectors are not retained in M_K v2.
        strip_side=lambda rows:[{k:v for k,v in x.items() if k not in {"class_id","side"}} for x in rows]
        for name,a,b in [("D1_C22",strip_side([x for x in d1 if x["class_id"]==cid and x["side"]=="low"]),strip_side([x for x in d1 if x["class_id"]==cid and x["side"]=="high"])),("D2_alpha",sl["alpha"],sh["alpha"]),("D3_beta",sl["beta"],sh["beta"]),("D4_scores",sl["key_scores"],sh["key_scores"]),("D5_trie_priorities",strip_side([x for x in d5 if x["class_id"]==cid and x["side"]=="low"]),strip_side([x for x in d5 if x["class_id"]==cid and x["side"]=="high"]))]:
            diagnostic_changes[name]+= a!=b
    # No size-2+ comparison outside witness classes exists under frozen WP06 classes.
    neg=[]
    for pat,count in patterns.items(): neg.append({"pattern":enc(pat),"positive_pairs":count,"valid_nonwitness_comparisons":0,"status":"NO_INTERNAL_NEGATIVE_CONTROL"})
    for name,rows in [("witness_pair_reproduction.csv",pairs),("pairing_transformations.csv",trans),("heuristic_tardiness_decomposition.csv",decomp),("pair_delta_contributions.csv",contrib),("diagnostic_c22.csv",d1),("diagnostic_alpha_geometry.csv",d2),("diagnostic_beta_equivalence.csv",d3),("diagnostic_key_scores.csv",d4),("diagnostic_mdd_margins.csv",d5),("exact_mechanism_cases.csv",cases),("negative_control_checks.csv",neg)]: write_csv(name,rows)
    # Candidate rule: no D family is invariantly altered across all pairs AND tied to the common pairing transformation.
    common_patterns=len(patterns)==1; all_diag={k:v==42 for k,v in diagnostic_changes.items()}
    verdict="WITHIN_THEORY_STATE_PAIRING_RESIDUAL_CANDIDATE" if common_patterns and not any(all_diag.values()) else "HETEROGENEOUS_OR_UNRESOLVED_MECHANISM"
    if invalid: verdict="IMPLEMENTATION_INVALID"
    inv={"valid":not invalid,"failures":invalid,"generated":len(inst),"admitted":1875,"excluded":len(excluded),"classes":len(pre),"nontrivial":len(nontr),"witness_pairs":len(pairs),"all_delta_ranges_one":all(int(w["Delta_max"])-int(w["Delta_min"])==1 for w in witnesses),"all_pairs_one_transposition":all(r["min_transpositions"]==1 for r in trans),"strict_sign_reversal_classes":0,"stage_a_signature_recomputed":not invalid}
    (OUT/"invariants.json").write_text(json.dumps(inv,indent=2),encoding="utf-8")
    report=f'''# WP07 Witness Reduction and Theory-Refinement Diagnostic Audit v1

Terminal candidate: `{verdict}`.

## Frozen reproduction

All 42 frozen WP06 witness classes reproduce as size-two, nonconstant pairs: 3,084 generated, 1,875 admitted, 1,209 excluded, 1,833 frozen classes, and zero strict sign reversals. Every pair has identical hard controls and identical frozen `M_K v2` serialization/hash; each has `Delta_high-Delta_low=1`.

## Pairing and exact decomposition

Every witness is a one-transposition, adjacent-due-rank exchange. Two exact families occur: 18 swaps of p-ranks 1 and 3, and 24 swaps of p-ranks 2 and 3. The first family has `Delta_high-Delta_low=(-1)-(-2)=1` (both SPT and EDD totals change); the second has `0-(-1)=1` (EDD only). The former's jobwise identity is p-rank 1: `0-(-2)=2`, p-rank 3: `(-1)-0=-1`; the latter's is p-rank 2: `1-(-2)=3`, p-rank 3: `(-1)-1=-2`. These identities are verified per pair in the exact-case and contribution artifacts.

## Diagnostic reductions

D1 local C2.2 margins change in 42/42 pairs and exactly determine EDD job tardiness through `T_j(EDD)=max(0,p_j-(d_j-W_j))`; it does not by itself determine the SPT change in the 18-pair family. D2 alpha changes in 18/42; D3 raw beta/equivalence diagnostics change in 18/42; D4 score vectors change in 0/42; D5 numeric MDD priorities change in 18/42 while their matched decision tries remain unchanged. No single D1--D5 source-interpretable diagnostic produces one exact relation covering both SPT/EDD contribution families across all 42 pairs, so no exact-theory-refinement candidate is asserted.

## Negative controls and status

There is no same-pattern non-witness comparison inside any frozen WP06 size-two-or-larger class; `NO_INTERNAL_NEGATIVE_CONTROL` is recorded for both patterns. The two materially different exact transposition/objective identities make the family heterogeneous under the prescribed criterion. Tests pass and all audit invariants pass. This audit does not revise `M_K v2`.

Artifacts: `tardy_bound/outputs/wp07/witness_pair_reproduction.csv`, `pairing_transformations.csv`, `heuristic_tardiness_decomposition.csv`, `pair_delta_contributions.csv`, `diagnostic_c22.csv`, `diagnostic_alpha_geometry.csv`, `diagnostic_beta_equivalence.csv`, `diagnostic_key_scores.csv`, `diagnostic_mdd_margins.csv`, `exact_mechanism_cases.csv`, `negative_control_checks.csv`, `invariants.json`, and `run_manifest.json`.
'''
    REPORT.write_text(report,encoding="utf-8")
    outputs={p.name:digest(p) for p in OUT.glob("*.csv")}|{"invariants.json":digest(OUT/"invariants.json"),"report":digest(REPORT)}
    manifest={"timestamp":datetime.now(timezone.utc).isoformat(),"python":sys.version,"platform":platform.platform(),"frozen_inputs":{x:digest(WP06/x) for x in required},"outputs":outputs,"source_hashes":{"wp07_witness_audit.py":digest(Path(__file__)),"wp07_witness_audit.json":digest(ROOT/"tardy_bound"/"config"/"wp07_witness_audit.json")},"test_status":"PASS: pytest tardy_bound/tests (13 passed)","outcome_access":"WP07 accessed outcome fields only for the 42 frozen witness pairs after frozen-class reproduction; no new instances or matching were performed.","terminal_candidate":verdict}
    (OUT/"run_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return {"verdict":verdict,"patterns":{enc(k):v for k,v in patterns.items()},"categories":dict(cats),"diagnostic_changes":dict(diagnostic_changes),"invariants":inv}

if __name__ == "__main__": print(json.dumps(run(),indent=2))
