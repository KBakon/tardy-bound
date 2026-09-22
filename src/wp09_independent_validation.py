"""WP09 prospective independent residual-completeness validation.

Stage A is deliberately outcome-free: it creates frozen M_K v2 classes and
adjacent-exchange predictions before this module invokes any objective scorer.
"""
from __future__ import annotations

import csv, hashlib, itertools, json, platform, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from theory_state import tt
from theory_state_v2 import build_v2_state, canonical, mk_v2_key, signature_hash

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tardy_bound'/'outputs'/'wp09'
CONFIG=ROOT/'tardy_bound'/'config'/'wp09_independent_validation.json'
REPORT=ROOT/'reports'/'evidence'/'WP09_INDEPENDENT_RESIDUAL_COMPLETENESS_VALIDATION_v1.md'
FORBIDDEN_OUTCOMES={'TT_SPT','TT_EDD','Delta','TT_star','optimal_schedules'}

PANELS={
 'A':{'n':4,'p':(1,2,4,7),'pool':(1,3,5,7,9,11)},
 'B':{'n':5,'p':(1,2,4,7,11),'pool':(1,3,5,7,9,11,13,15,17)},
}

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(v:Any)->str:return json.dumps(v,sort_keys=True,separators=(',',':'))
def write_csv(name:str,rows:list[dict[str,Any]],fields:list[str]|None=None)->None:
 OUT.mkdir(parents=True,exist_ok=True); fields=fields or sorted({k for r in rows for k in r})
 with (OUT/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def generate():
 serial=0
 for panel,spec in PANELS.items():
  orbit=0
  for ds in itertools.combinations(spec['pool'],spec['n']):
   orbit+=1
   for d in itertools.permutations(ds):
    serial+=1;yield panel,f'{panel}_o{orbit:03d}_r{serial:05d}',spec['p'],d,ds
def g(c,d):return max(0,c-d)
def hinge(c,lo,hi):return g(c,lo)-g(c,hi)
def exchange_data(left,right):
 """Return a frozen adjacent EDD-swap prediction, else None."""
 p=left['p']; dl,dr=left['d'],right['d']; changed=[j for j in range(len(p)) if dl[j]!=dr[j]]
 if len(changed)!=2 or any(dl[j]!=dr[changed[1] if j==changed[0] else changed[0]] for j in changed):return None
 x,y=changed; a,b=sorted(changed); values=sorted((dl[a],dl[b])); lo,hi=values
 if hi not in dl or sorted(dl).index(hi)!=sorted(dl).index(lo)+1:return None
 # canonical forward has low due date on lower p-rank a.
 forward=left if dl[a]==lo else right; reverse=right if forward is left else left
 if forward['d'][a]!=lo or forward['d'][b]!=hi:return None
 cs=[sum(p[:j+1]) for j in range(len(p))]
 t=sum(p[j] for j,d in enumerate(forward['d']) if d<lo)
 pred=hinge(cs[a],lo,hi)-hinge(cs[b],lo,hi)-g(t+p[a],lo)+g(t+p[b],lo)
 return {'a_p_rank':a+1,'b_p_rank':b+1,'d_L':lo,'d_H':hi,'SPT_C_a':cs[a],'SPT_C_b':cs[b],'EDD_prefix_t':t,'I_forward':forward['instance_id'],'I_reverse':reverse['instance_id'],'predicted_delta_difference':pred,'prediction_category':'zero' if pred==0 else 'positive' if pred>0 else 'negative','prediction_magnitude':abs(pred)}
def components(nodes,edges):
 adj={x:set() for x in nodes}
 for e in edges:adj[e['I_forward']].add(e['I_reverse']);adj[e['I_reverse']].add(e['I_forward'])
 out={};i=0
 for n in sorted(nodes):
  if n not in out:
   i+=1;stack=[n]
   while stack:
    x=stack.pop()
    if x in out:continue
    out[x]=i;stack.extend(adj[x]-set(out))
 return out

def stage_a():
 records=[]; admitted=[]; instances=[]; sigs=[]; exclusions=[]
 for panel,iid,p,d,ds in generate():
  s=build_v2_state(p,d);P=sum(p);D=sum(d);tau=Fraction(len(p)*P-D,len(p)*P)
  base={'instance_id':iid,'panel':panel,'n':len(p),'p_by_rank':enc(list(p)),'d_by_rank':enc(list(d)),'d_multiset':enc(list(ds)),'P':P,'D':D,'tau_num':tau.numerator,'tau_den':tau.denominator,'SPT_order':enc(s['spt']),'EDD_order':enc(s['edd'])}
  instances.append(base);r={'instance_id':iid,'panel':panel,'p':p,'d':d,'state':s};records.append(r)
  reasons=[]
  if s['closure_count']!=1:reasons.append('closure_count>1')
  if s['full_count']!=1:reasons.append('FULL_family_count>1')
  if not s['equivalence_valid']:reasons.append('equivalence_invalid')
  if reasons:
   exclusions.append({'instance_id':iid,'panel':panel,'reason':';'.join(reasons),'closure_count':s['closure_count'],'FULL_family_count':s['full_count'],'equivalence_valid':s['equivalence_valid']});continue
  key=mk_v2_key(s);h=signature_hash(key);r.update({'M_K_v2_hash':h,'key':key,'class_key':(panel,len(p),p,ds,P,D,tau.numerator,tau.denominator,h)})
  admitted.append(r);sigs.append({'instance_id':iid,'panel':panel,'M_K_v2_serialized':canonical(key),'M_K_v2_hash':h})
 classes=defaultdict(list)
 for r in admitted:classes[r['class_key']].append(r)
 classrows=[];edge_rows=[];component_rows=[]
 for idx,(key,members) in enumerate(sorted(classes.items(),key=lambda v:v[0]),1):
  cid=f'WP09C{idx:05d}';panel,n,p,ds,P,D,tn,td,h=key
  for r in members:r['class_id']=cid
  classrows.append({'class_id':cid,'panel':panel,'n':n,'p_multiset':enc(list(p)),'d_multiset':enc(list(ds)),'P':P,'D':D,'tau_num':tn,'tau_den':td,'M_K_v2_hash':h,'class_size':len(members)})
  edges=[]
  for u,v in itertools.combinations(members,2):
   e=exchange_data(u,v)
   if e:
    e.update({'class_id':cid,'panel':panel});edges.append(e);edge_rows.append(e)
  comp=components([r['instance_id'] for r in members],edges)
  for r in members:component_rows.append({'class_id':cid,'panel':panel,'instance_id':r['instance_id'],'component_id':comp[r['instance_id']]})
 write_csv('instances_preoutcome.csv',instances);write_csv('mk_v2_signature_preoutcome.csv',sigs);write_csv('matched_classes_preoutcome.csv',classrows);write_csv('exclusions.csv',exclusions);write_csv('exchange_edges_preoutcome.csv',edge_rows);write_csv('exchange_components_preoutcome.csv',component_rows)
 names=['instances_preoutcome.csv','mk_v2_signature_preoutcome.csv','matched_classes_preoutcome.csv','exclusions.csv','exchange_edges_preoutcome.csv','exchange_components_preoutcome.csv']
 manifest={'stage':'A_PRE_OUTCOME','generated':len(records),'admitted':len(admitted),'excluded':len(exclusions),'by_panel':{x:{'generated':sum(r['panel']==x for r in records),'admitted':sum(r['panel']==x for r in admitted),'excluded':sum(r['panel']==x for r in records)-sum(r['panel']==x for r in admitted)} for x in PANELS},'exclusion_counts':dict(Counter(r['reason'] for r in exclusions)),'artifacts':{x:sha(OUT/x) for x in names},'source_config_hashes':{'wp09_independent_validation.py':sha(Path(__file__)),'wp09_independent_validation.json':sha(CONFIG)},'certification':'Stage A computed no SPT/EDD total tardiness, Delta, TT*, optimal schedule, or outcome join; class and exchange graph construction used only p/d data and frozen theory state.'}
 (OUT/'preoutcome_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding='utf-8')
 return records,admitted,classrows,edge_rows,component_rows,manifest

def optimum(p,d):
 vals=[(tt(p,d,o),o) for o in itertools.permutations(range(len(p)))];best=min(x[0] for x in vals)
 return best,[o for x,o in vals if x==best]
def stage_b(records,admitted,classrows,edges,comps,manifest):
 if any(sha(OUT/n)!=h for n,h in manifest['artifacts'].items()):raise RuntimeError('Stage-A hash mutation before release')
 lookup={r['instance_id']:r for r in records}; admitted_ids={r['instance_id'] for r in admitted};prior={r['instance_id']:r for r in csv.DictReader((OUT/'instances_preoutcome.csv').open(encoding='utf-8'))};rows=[];oracle=[];fail=[]
 for r in records:
  row=prior[r['instance_id']]
  if r['instance_id'] not in admitted_ids: rows.append(row);continue
  p,d,s=r['p'],r['d'],r['state'];sp=[x-1 for x in s['spt']];ed=[x-1 for x in s['edd']];ts,te=tt(p,d,sp),tt(p,d,ed);best,opts=optimum(p,d)
  # theorem sufficient claims are validated against the exhaustive optimum.
  checks={'SPT_sufficient':not s['SPT_sufficient'] or ts==best,'EDD_C22':not s['EDD_C22'] or te==best,'beta_optimal':not s.get('beta_optimal',False) or tt(p,d,[x-1 for x in s['beta_sequence']])==best}
  if not all(checks.values()):fail.extend(f"{r['instance_id']}:{k}" for k,v in checks.items() if not v)
  r.update({'TT_SPT':ts,'TT_EDD':te,'Delta':ts-te,'TT_star':best});row.update({'TT_SPT':ts,'TT_EDD':te,'Delta':ts-te});rows.append(row)
  oracle.append({'instance_id':r['instance_id'],'panel':r['panel'],'TT_star':best,'optimal_schedule_count':len(opts),'optimal_schedules':enc([[x+1 for x in o] for o in opts]),**checks})
 write_csv('instances.csv',rows);write_csv('oracle_optima.csv',oracle)
 edge_out=[]
 for e in edges:
  observed=lookup[e['I_forward']]['Delta']-lookup[e['I_reverse']]['Delta'];z=dict(e);z['observed_delta_difference']=observed;z['prediction_matches']=observed==e['predicted_delta_difference'];edge_out.append(z)
  if not z['prediction_matches']:fail.append(f"edge:{e['I_forward']}:{e['I_reverse']}")
 write_csv('exchange_edges.csv',edge_out);write_csv('exchange_components.csv',comps)
 by_class=defaultdict(list)
 for r in admitted:by_class[r['class_id']].append(r)
 compmap={x['instance_id']:x['component_id'] for x in comps};final=[];small=[]
 for pre in classrows:
  members=by_class[pre['class_id']];vals=[x['Delta'] for x in members];nonconst=min(vals)<max(vals);levels=defaultdict(set)
  for r in members:levels[compmap[r['instance_id']]].add(r['Delta'])
  component_levels={k:sorted(v) for k,v in levels.items()}
  # incomplete iff distinct disconnected components have distinct levels.
  incomplete=nonconst and any(x!=y for i,x in component_levels.items() for j,y in component_levels.items() if i<j)
  status='CONSTANT' if not nonconst else 'EXCHANGE_INCOMPLETE' if incomplete else 'EXCHANGE_COMPLETE'
  row=dict(pre);row.update({'Delta_min':min(vals),'Delta_max':max(vals),'Delta_values':enc(sorted(vals)),'residual_status':status,'component_delta_levels':enc(component_levels)});final.append(row)
  if incomplete:small.append(row)
 write_csv('matched_classes.csv',final)
 # Copy frozen component mapping after its immutable identity was used above.
 inv={'panel_A_generated':sum(r['panel']=='A' for r in records)==360,'panel_B_generated':sum(r['panel']=='B' for r in records)==15120,'total_generated':len(records)==15480,'domain':all(tuple(r['p'])==PANELS[r['panel']]['p'] and len(set(r['d']))==len(r['d']) and all(0<x<sum(r['p']) for x in r['d']) for r in records),'admitted_excluded_accounting':len(admitted)+(len(records)-len(admitted))==len(records),'stage_A_hashes_unchanged':all(sha(OUT/n)==h for n,h in manifest['artifacts'].items()),'edge_predictions':not fail,'component_ids_unchanged':len(comps)==len(admitted),'theorem_oracle_failures':fail}
 (OUT/'invariants.json').write_text(json.dumps(inv,indent=2,sort_keys=True),encoding='utf-8')
 return rows,final,edge_out,small,inv
def summarize(records,admitted,classes,edges,small,inv):
 panel={}
 for name in PANELS:
  cs=[r for r in classes if r['panel']==name]; nontr=[r for r in cs if int(r['class_size'])>=2];nc=[r for r in nontr if r['residual_status']!='CONSTANT'];complete=[r for r in nc if r['residual_status']=='EXCHANGE_COMPLETE'];inc=[r for r in nc if r['residual_status']=='EXCHANGE_INCOMPLETE'];es=[e for e in edges if e['panel']==name]
  panel[name]={'generated':sum(r['panel']==name for r in records),'admitted':sum(r['panel']==name for r in admitted),'excluded':sum(r['panel']==name for r in records)-sum(r['panel']==name for r in admitted),'classes':len(cs),'nontrivial':len(nontr),'nonconstant':len(nc),'exchange_complete':len(complete),'exchange_incomplete':len(inc),'class_size_distribution':dict(Counter(int(r['class_size']) for r in cs)),'edges':len(es),'zero_edges':sum(e['predicted_delta_difference']==0 for e in es),'negative_edges':sum(e['predicted_delta_difference']<0 for e in es),'nonunit_edges':sum(abs(e['predicted_delta_difference'])>1 for e in es)}
 ok=all(v is True for k,v in inv.items() if k!='theorem_oracle_failures') and not inv['theorem_oracle_failures']
 if not ok:status='IMPLEMENTATION_INVALID'
 elif any(panel[x]['nontrivial']==0 for x in PANELS):status='DESIGN_FEASIBILITY_FAILURE_NO_NONTRIVIAL_MATCHED_CLASS'
 elif any(panel[x]['nonconstant']==0 for x in PANELS):status='CONFIRMATORY_NO_RESIDUAL_IN_AT_LEAST_ONE_PANEL'
 elif small:status='CONFIRMATORY_RESIDUAL_OUTSIDE_EXCHANGE_REDUCTION'
 else:status='CONFIRMATORY_EXCHANGE_REDUCTION_TRANSFERRED'
 return panel,status
def run():
 OUT.mkdir(parents=True,exist_ok=True);records,admitted,pre,edges,comps,manifest=stage_a();rows,classes,edge_out,small,inv=stage_b(records,admitted,pre,edges,comps,manifest);panel,status=summarize(records,admitted,classes,edge_out,small,inv)
 write_csv('panel_summary.csv',[{'panel':k,**v} for k,v in panel.items()])
 report=['# WP09 Independent Residual-Completeness Validation v1','',f'- Terminal label: `{status}`.']
 for k,v in panel.items():report.append(f"- Panel {k}: generated/admitted/excluded {v['generated']}/{v['admitted']}/{v['excluded']}; nontrivial/nonconstant/complete/incomplete {v['nontrivial']}/{v['nonconstant']}/{v['exchange_complete']}/{v['exchange_incomplete']}; edges {v['edges']} (zero/negative/non-unit {v['zero_edges']}/{v['negative_edges']}/{v['nonunit_edges']}).")
 report+=['- Stage-A pre-outcome freeze and all hash checks: '+('PASS' if inv['stage_A_hashes_unchanged'] else 'FAIL')+'.','- Exact optimum, theorem, edge-prediction and component checks: '+('PASS' if not inv['theorem_oracle_failures'] else 'FAIL')+'.','- Artifacts: `tardy_bound/outputs/wp09/`; report is P2 candidate evidence pending Controller adjudication.']
 REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text('\n'.join(report)+'\n',encoding='utf-8')
 runm={'timestamp':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),'config_hash':sha(CONFIG),'stage_A_manifest_hash':sha(OUT/'preoutcome_manifest.json'),'source_hashes':{'wp09_independent_validation.py':sha(Path(__file__))},'terminal_label':status,'invariants_pass':not inv['theorem_oracle_failures'] and all(v is True for k,v in inv.items() if k!='theorem_oracle_failures'),'outputs':{p.name:sha(p) for p in OUT.iterdir() if p.name!='run_manifest.json'}}
 (OUT/'run_manifest.json').write_text(json.dumps(runm,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps({'status':status,'panel':panel},sort_keys=True))
if __name__=='__main__':run()
