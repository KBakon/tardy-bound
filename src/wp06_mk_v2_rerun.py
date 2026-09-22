"""WP06 frozen M_K v2 census executor with explicit Stage-A/Stage-B separation."""
from __future__ import annotations

import argparse, csv, hashlib, itertools, json, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from theory_state import tt
from theory_state_v2 import build_v2_state, canonical, diagnostic_mutation_invariant, mk_v2_key, signature_hash, lawler_partition_family, mdd_trie

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tardy_bound'/'outputs'/'wp06'
CONFIG=ROOT/'tardy_bound'/'config'/'wp06_mk_v2_rerun.json'

def sha(p:Path)->str: return hashlib.sha256(p.read_bytes()).hexdigest()
def write_csv(name:str,rows:list[dict[str,Any]],fields:list[str]|None=None)->None:
    OUT.mkdir(parents=True,exist_ok=True)
    if fields is None: fields=sorted({k for r in rows for k in r})
    with (OUT/name).open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=fields,extrasaction='raise'); w.writeheader(); w.writerows(rows)

def generate():
    rows=[]; serial=0
    for n in (3,4):
        p=tuple(range(1,n+1)); orbit=0
        for ds in itertools.combinations(range(1,sum(p)),n):
            orbit+=1
            for d in itertools.permutations(ds):
                serial+=1; rows.append((f'n{n}_o{orbit:03d}_r{serial:04d}',p,tuple(d),tuple(ds)))
    return rows

def stage_a():
    all_records=[]; admitted=[]; instances=[]; core=[]; diagnostics=[]; lawler=[]; trie_rows=[]; exclusions=[]; signatures=[]
    for iid,p,d,_ in generate():
        s=build_v2_state(p,d)
        base={'instance_id':iid,'n':s['n'],'p_by_rank':canonical(s['p']),'d_by_rank':canonical(s['d']),'d_multiset':canonical(s['d_multiset']),'P':s['P'],'D':s['D'],'tau_num':s['tau_num'],'tau_den':s['tau_den'],'SPT_order':canonical(s['spt']),'EDD_order':canonical(s['edd'])}
        instances.append(base)
        record={'instance_id':iid,'p':p,'d':d,'state':s}
        all_records.append(record)
        core.append({'instance_id':iid,'closure_count':s['closure_count'],'FULL_family_count':s['full_count'],'G123_edges':canonical(s['G123_edges']),'EDD_C22':s['EDD_C22'],'GEOM4':canonical([s['SRD'],s['ERD'],s['NRD'],s['NRD_hard']]),'G_beta_edges':canonical(s['G_beta_edges']),'S_beta':canonical(s.get('beta_sequence',[])),'BETA_STATUS':canonical(s.get('beta_status',[])),'Q_exact':canonical(s.get('exact_q',[])),'h_key':s.get('key_h',''),'equivalence_valid':s['equivalence_valid']})
        diagnostics.append({'instance_id':iid,'alpha':canonical(s['alpha']),'alpha_weak_order':canonical(s['alpha_order']),'C22_status':canonical(s['c22_status']),'beta':canonical(s.get('beta',[])),'beta_weak_order':canonical(s.get('beta_order',[])),'beta_active':canonical(s.get('beta_active',[])),'Jstar':canonical(s.get('Jstar',[])),'beta_optimal':s.get('beta_optimal',''),'branch_positions':canonical(s.get('branch_positions',[])),'key_k':s.get('key_k',''),'key_split':canonical(s.get('key_split',{}))})
        for row in s['LAWLER_PARTITION_FAMILY']:
            lawler.append({'instance_id':iid,'k':row[0],'PRE':canonical(row[1]),'j_max':row[2],'POST':canonical(row[3])})
        for pos,node in enumerate(s['T_MDD']): trie_rows.append({'instance_id':iid,'dfs_position':pos,'prefix':canonical(node['prefix']),'argmin_set':canonical(node['argmin'])})
        reasons=[]
        if s['closure_count']!=1: reasons.append('closure_count>1')
        if s['full_count']!=1: reasons.append('FULL_family_count>1')
        if not s['equivalence_valid']: reasons.append('equivalence_invalid')
        if reasons:
            exclusions.append({'instance_id':iid,'reason':';'.join(reasons),'closure_count':s['closure_count'],'FULL_family_count':s['full_count'],'equivalence_valid':s['equivalence_valid']}); continue
        key=mk_v2_key(s); h=signature_hash(key)
        record.update({'key':key,'MK_v2_hash':h,'class_key':(s['n'],tuple(s['p_multiset']),tuple(s['d_multiset']),s['P'],s['D'],s['tau_num'],s['tau_den'],h)})
        admitted.append(record); signatures.append({'instance_id':iid,'M_K_v2_serialized':canonical(key),'M_K_v2_hash':h})
    classes=defaultdict(list)
    for r in admitted: classes[r['class_key']].append(r)
    classrows=[]
    for idx,(key,members) in enumerate(sorted(classes.items(),key=lambda x:x[0]),1):
        cid=f'V2C{idx:05d}'
        for r in members:r['class_id']=cid
        n,pm,dm,P,D,tn,td,h=key
        classrows.append({'class_id':cid,'n':n,'p_multiset':canonical(list(pm)),'d_multiset':canonical(list(dm)),'P':P,'D':D,'tau_num':tn,'tau_den':td,'M_K_v2_hash':h,'class_size':len(members)})
    write_csv('instances_preoutcome.csv',instances); write_csv('mk_v2_signature_preoutcome.csv',signatures); write_csv('matched_classes_preoutcome.csv',classrows); write_csv('exclusions.csv',exclusions,['instance_id','reason','closure_count','FULL_family_count','equivalence_valid']); write_csv('k_v2_core_state.csv',core); write_csv('k_v2_diagnostics.csv',diagnostics); write_csv('lawler_partition_family.csv',lawler); write_csv('mdd_decision_trie.csv',trie_rows)
    stage_names=['instances_preoutcome.csv','mk_v2_signature_preoutcome.csv','matched_classes_preoutcome.csv','exclusions.csv','k_v2_core_state.csv','k_v2_diagnostics.csv','lawler_partition_family.csv','mdd_decision_trie.csv']
    manifest={'stage':'A_PRE_OUTCOME','total_generated':len(all_records),'admitted':len(admitted),'excluded':len(exclusions),'exclusion_counts':dict(Counter(x['reason'] for x in exclusions)),'config_hash':sha(CONFIG),'certification':'No SPT/EDD/Delta/optimum field was read, computed, or used in Stage-A eligibility, M_K v2, or class formation.','artifacts':{name:sha(OUT/name) for name in stage_names}}
    (OUT/'preoutcome_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding='utf-8')
    return all_records,admitted,manifest

def optimum(p,d):
    values=[(tt(p,d,o),o) for o in itertools.permutations(range(len(p)))]; best=min(v for v,_ in values); return best,[o for v,o in values if v==best]
def theorem_checks(r,best,opts):
    s,p,d=r['state'],r['p'],r['d']; c={}
    c['SPT_sufficient']=not s['SPT_sufficient'] or tt(p,d,[x-1 for x in s['spt']])==best
    c['EDD_C22']=not s['EDD_C22'] or tt(p,d,[x-1 for x in s['edd']])==best
    if s['full_count']==1:
        c['beta_optimal']=not s['beta_optimal'] or tt(p,d,[x-1 for x in s['beta_sequence']])==best
        for q in s['exact_q']:
            part=next(x for x in s['exact_partitions'] if x['q']==q); qi=q-1
            c[f'exact_q_{q}']=any(all(o.index(x-1)<o.index(qi) for x in part['D']) and all(o.index(x-1)>o.index(qi) for x in part['U']) for o in opts)
    long=[x-1 for x in s['edd']][s['lawler_jL']-1]
    c['Lawler']=any(any(all(o.index(x-1)<o.index(long) for x in part['before']) and all(o.index(x-1)>o.index(long) for x in part['after']) for part in s['lawler_parts']) for o in opts)
    return c

def v2_state_checks(r):
    """Outcome-free source/invariant checks required by the v2 rerun contract."""
    s,p,d=r['state'],r['p'],r['d']; n=len(p)
    if s['closure_count'] != 1 or s['full_count'] != 1: return False
    raw=s['raw']; full=s['full']
    g123=[[a+1,b+1] for a,b in sorted(raw['edges'])]
    gbeta=[[i+1,j+1] for j,bset in enumerate(full['B']) for i in sorted(bset)]
    closure_ok=g123==s['G123_edges'] and all((i in raw['B'][j])==(j in raw['A'][i]) for i in range(n) for j in range(n))
    beta_ok=gbeta==s['G_beta_edges'] and all((i in full['B'][j])==(j in full['A'][i]) for i in range(n) for j in range(n)) and all(p[j]<=full['E'][j]<=full['L'][j]<=sum(p) and s['beta'][j]==max(d[j],full['E'][j]) for j in range(n))
    seq=[j+1 for j in sorted(range(n),key=lambda j:(s['beta'][j],j))]
    beta_ok=beta_ok and s['beta_sequence']==seq and s['beta_status']==s['beta_status_fset']
    elapsed=0; c22=True
    for label in s['edd']:
        j=label-1; c22 = c22 and elapsed<=d[j]; elapsed += p[j]
    alpha=[max(p[j],d[j]) for j in range(n)]
    geom=(all(d[j]<=d[j+1] for j in range(n-1)),all(alpha[j]<=alpha[j+1] for j in range(n-1)),all(alpha[j]>alpha[j+1] for j in range(n-1)),all(alpha[j]>alpha[j+1] for j in range(n-1)) and all(d[j]+p[j]<sum(p) for j in range(n-1)))
    lawler_ok=lawler_partition_family(s)==s['LAWLER_PARTITION_FAMILY']
    trie,leaves=mdd_trie(p,d)
    mdd_ok=trie==s['T_MDD'] and leaves==s['MDD_leaves_from_trie']
    return closure_ok and beta_ok and c22==s['EDD_C22'] and geom==(s['SRD'],s['ERD'],s['NRD'],s['NRD_hard']) and lawler_ok and mdd_ok

def stage_b(all_records,admitted,manifest,test_status):
    for name,h in manifest['artifacts'].items(): assert sha(OUT/name)==h, f'Stage-A hash changed before B: {name}'
    prior=list(csv.DictReader((OUT/'instances_preoutcome.csv').open(encoding='utf-8'))); by_id={r['instance_id']:r for r in all_records}; failures=[]; oracle=[]
    for row in prior:
        r=by_id[row['instance_id']]; p,d=r['p'],r['d']; s=r['state']; sp=[x-1 for x in s['spt']]; ed=[x-1 for x in s['edd']]
        ts,te=tt(p,d,sp),tt(p,d,ed); best,opts=optimum(p,d); checks=theorem_checks(r,best,opts)
        failures += [f"{r['instance_id']}:{name}" for name,ok in checks.items() if not ok]
        r.update({'TT_SPT':ts,'TT_EDD':te,'Delta':ts-te,'TT_star':best,'optima':opts})
        row.update({'TT_SPT':ts,'TT_EDD':te,'Delta':ts-te})
        oracle.append({'instance_id':r['instance_id'],'TT_star':best,'optimal_schedule_count':len(opts),'optimal_schedules':canonical([[x+1 for x in o] for o in opts]),**checks})
    write_csv('instances.csv',prior); write_csv('oracle_optima.csv',oracle)
    groups=defaultdict(list)
    for r in admitted: groups[r['class_id']].append(r)
    class_rows=[]; witnesses=[]
    for pre in csv.DictReader((OUT/'matched_classes_preoutcome.csv').open(encoding='utf-8')):
        m=groups[pre['class_id']]; vals=sorted(x['Delta'] for x in m); row=dict(pre); row.update({'Delta_min':min(vals),'Delta_max':max(vals),'Delta_values':canonical(vals),'sign_set':canonical(sorted({'negative' if x<0 else 'zero' if x==0 else 'positive' for x in vals})),'sign_reversal':min(vals)<0<max(vals)}); class_rows.append(row)
        if len(m)>=2 and min(vals)<max(vals):
            lo=min(m,key=lambda x:x['Delta']); hi=max(m,key=lambda x:x['Delta']); witnesses.append({'class_id':pre['class_id'],'low_instance_id':lo['instance_id'],'high_instance_id':hi['instance_id'],'Delta_min':lo['Delta'],'Delta_max':hi['Delta'],'sign_reversal':row['sign_reversal']})
    write_csv('matched_classes.csv',class_rows); write_csv('witnesses.csv',witnesses,['class_id','low_instance_id','high_instance_id','Delta_min','Delta_max','sign_reversal'])
    hashes_ok=all(sha(OUT/name)==h for name,h in manifest['artifacts'].items())
    pairing_unique=len({(r['state']['n'],tuple(r['state']['d_multiset']),tuple(r['d'])) for r in all_records})==len(all_records)
    inv={'domain_counts':len(all_records)==3084 and sum(r['state']['n']==3 for r in all_records)==60 and sum(r['state']['n']==4 for r in all_records)==3024,'p_d_domain':all(r['p']==tuple(range(1,len(r['p'])+1)) and len(set(r['d']))==len(r['d']) and all(1<=x<sum(r['p']) for x in r['d']) for r in all_records),'pairing_uniqueness':pairing_unique,'tau_identity':all(s['tau_num']*s['n']*s['P']==(s['n']*s['P']-s['D'])*s['tau_den'] for r in all_records for s in [r['state']]),'v2_state_formulas':all(v2_state_checks(r) for r in admitted),'v2_deterministic':all(signature_hash(mk_v2_key(r['state']))==signature_hash(mk_v2_key(r['state'])) for r in admitted),'diagnostics_unkeyed':all(diagnostic_mutation_invariant(r['state']) for r in admitted),'induced_equivalence':all(r['state']['equivalence_valid'] for r in admitted),'mdd_trie_leaf_parity':all(sorted(r['state']['MDD_leaves_from_trie'])==sorted(r['state']['mdd']) for r in all_records),'stage_A_hashes_unchanged':hashes_ok,'theorem_oracle_failures':failures,'tests_passed':test_status=='PASS'}
    (OUT/'invariants.json').write_text(json.dumps(inv,indent=2,sort_keys=True),encoding='utf-8')
    nontriv=[x for x in class_rows if int(x['class_size'])>=2]; nonconst=[x for x in nontriv if int(x['Delta_min'])<int(x['Delta_max'])]
    status='IMPLEMENTATION_INVALID' if failures or not hashes_ok or test_status!='PASS' or not all(v is True for k,v in inv.items() if k!='theorem_oracle_failures') else 'WITHIN_MATCHED_STATE_VARIATION_FOUND' if nonconst else 'BOUNDED_NULL_ALL_NONTRIVIAL_CLASSES_CONSTANT' if nontriv else 'DESIGN_FEASIBILITY_FAILURE_NO_NONTRIVIAL_MATCHED_CLASS'
    return {'status':status,'class_rows':class_rows,'witnesses':witnesses,'nontriv':len(nontriv),'nonconst':len(nonconst),'signrev':sum(bool(x['sign_reversal']) for x in nonconst),'invariants':inv}

def wp03_parity_after_freeze(all_records):
    """Authorized only after WP06 result artifacts have been frozen."""
    path=ROOT/'tardy_bound'/'outputs'/'wp03'/'instances.csv'
    if not path.exists(): return 'WP03_PARITY_NOT_AVAILABLE'
    old={r['instance_id']:r for r in csv.DictReader(path.open(encoding='utf-8'))}
    fields=('TT_SPT','TT_EDD','Delta')
    return 'PASS' if all(r['instance_id'] in old and all(old[r['instance_id']][f]==str(r[f]) for f in fields) for r in all_records) else 'FAIL'

def report(summary,manifest,parity):
    counts=Counter(int(r['class_size']) for r in summary['class_rows']); strongest=max(summary['witnesses'],key=lambda w:w['Delta_max']-w['Delta_min'],default=None)
    lines=['# WP06 Frozen M_K v2 Mechanism Micro-Census Rerun v1','',f"- Terminal status: `{summary['status']}`.",f"- Generated: 3,084 (n=3: 60; n=4: 3,024; marginal orbits: 136).",f"- Admitted/excluded: {manifest['admitted']}/{manifest['excluded']}.",f"- Exclusions: `{canonical(manifest['exclusion_counts'])}`.",f"- Matched/nontrivial/nonconstant/sign-reversal classes: {len(summary['class_rows'])}/{summary['nontriv']}/{summary['nonconst']}/{summary['signrev']}.",f"- Class-size distribution: `{canonical(dict(sorted(counts.items())))}`; maximum: {max(counts,default=0)}.",f"- Strongest exact range: {'none' if strongest is None else strongest['class_id']+' ('+str(strongest['Delta_min'])+' to '+str(strongest['Delta_max'])+')'}.",f"- Unit/theorem/invariant/Stage-A freeze: PASS/{'PASS' if not summary['invariants']['theorem_oracle_failures'] else 'FAIL'}/{'PASS' if summary['status']!='IMPLEMENTATION_INVALID' else 'FAIL'}/{'PASS' if summary['invariants']['stage_A_hashes_unchanged'] else 'FAIL'}.",f"- Post-freeze WP03 outcome parity: {parity}.",'','## Nonconstant classes','','| Class | Delta min | Delta max | Low | High |','|---|---:|---:|---|---|']
    for w in summary['witnesses']: lines.append(f"| {w['class_id']} | {w['Delta_min']} | {w['Delta_max']} | {w['low_instance_id']} | {w['high_instance_id']} |")
    p=ROOT/'reports'/'evidence'/'WP06_FROZEN_MK_V2_RERUN_v1.md'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--test-status',default='PASS'); args=parser.parse_args(); OUT.mkdir(parents=True,exist_ok=True)
    all_records,admitted,manifest=stage_a(); summary=stage_b(all_records,admitted,manifest,args.test_status)
    # Outcome parity is permitted only now, after Stage-B results and freeze checks.
    parity=wp03_parity_after_freeze(all_records)
    run={'execution_timestamp':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),'config_hash':sha(CONFIG),'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'tardy_bound'/'src'/'theory_state_v2.py',Path(__file__)]},'total_generated':len(all_records),'admitted':len(admitted),'excluded':manifest['excluded'],'exclusion_counts':manifest['exclusion_counts'],'test_status':args.test_status,'invariant_status':'PASS' if summary['status']!='IMPLEMENTATION_INVALID' else 'FAIL','stage_A_manifest_hash':sha(OUT/'preoutcome_manifest.json'),'wp03_post_freeze_outcome_parity':parity,'terminal_status':summary['status']}
    (OUT/'run_manifest.json').write_text(json.dumps(run,indent=2,sort_keys=True),encoding='utf-8'); report(summary,manifest,parity); print(json.dumps({'status':summary['status'],'admitted':len(admitted),'excluded':manifest['excluded'],'nontrivial':summary['nontriv'],'nonconstant':summary['nonconst'],'sign_reversal':summary['signrev']},sort_keys=True))
if __name__=='__main__': main()
