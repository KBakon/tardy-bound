"""WP10 frozen cross-state exchange telescoping audit (WP09 consumer only)."""
from __future__ import annotations
import ast,csv,hashlib,json,platform,sys
from collections import defaultdict,deque,Counter
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]; WP09=ROOT/'tardy_bound'/'outputs'/'wp09'; OUT=ROOT/'tardy_bound'/'outputs'/'wp10'; CONFIG=ROOT/'tardy_bound'/'config'/'wp10_cross_state_audit.json'; REPORT=ROOT/'reports'/'evidence'/'WP10_CROSS_STATE_EXCHANGE_TELESCOPING_AND_CONNECTIVITY_AUDIT_v1.md'
OUTCOME={'TT_SPT','TT_EDD','Delta','TT_star','optimal_schedules'}
TARGETS={'WP09C00412','WP09C00483','WP09C00654','WP09C00718','WP09C01026','WP09C01104','WP09C01158','WP09C01626','WP09C01703','WP09C01713','WP09C01757'}
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def parse(x):return ast.literal_eval(x)
def enc(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def validate_stage_a_headers(headers):
 if OUTCOME.intersection(headers or []):raise RuntimeError('outcome-bearing Stage-A input rejected')
def read(path:Path,allow_outcome=False):
 with path.open(newline='',encoding='utf-8') as f:
  r=csv.DictReader(f)
  if not allow_outcome:
   try:validate_stage_a_headers(r.fieldnames)
   except RuntimeError as e:raise RuntimeError(f'{e}: {path.name}') from e
  return list(r)
def write(name,rows):
 OUT.mkdir(parents=True,exist_ok=True);fields=sorted({k for r in rows for k in r}) if rows else ['status']
 with (OUT/name).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def g(c,d):return max(0,c-d)
def hinge(c,lo,hi):return g(c,lo)-g(c,hi)
def adjacent_swap(a,b):
 """Adjacent-due-rank edge with deterministic WP08 forward orientation."""
 da,db=a['d'],b['d'];diff=[j for j in range(len(da)) if da[j]!=db[j]]
 if len(diff)!=2:return None
 x,y=diff
 if da[x]!=db[y] or da[y]!=db[x]:return None
 lo,hi=sorted((da[x],da[y])); sd=sorted(da)
 if sd.index(hi)!=sd.index(lo)+1:return None
 aidx,bidx=sorted(diff);forward=a if da[aidx]==lo else b;reverse=b if forward is a else a
 p=a['p'];cs=[sum(p[:j+1]) for j in range(len(p))];t=sum(p[j] for j,d in enumerate(forward['d']) if d<lo)
 pred=hinge(cs[aidx],lo,hi)-hinge(cs[bidx],lo,hi)-g(t+p[aidx],lo)+g(t+p[bidx],lo)
 return {'a_p_rank':aidx+1,'b_p_rank':bidx+1,'d_L':lo,'d_H':hi,'SPT_C_a':cs[aidx],'SPT_C_b':cs[bidx],'EDD_prefix_t':t,'I_forward':forward['instance_id'],'I_reverse':reverse['instance_id'],'predicted_delta_difference':pred}
def shortest_path(nodes,start,goal):
 """BFS with lexicographic tuple/id neighbor ordering; never sees outcomes."""
 byid={n['instance_id']:n for n in nodes};adj=defaultdict(list)
 for i,u in enumerate(nodes):
  for v in nodes[i+1:]:
   if adjacent_swap(u,v):adj[u['instance_id']].append(v['instance_id']);adj[v['instance_id']].append(u['instance_id'])
 key=lambda iid:(tuple(byid[iid]['d']),iid)
 for x in adj:adj[x].sort(key=key)
 q=deque([start]);prev={start:None}
 while q:
  x=q.popleft()
  if x==goal:break
  for y in adj[x]:
   if y not in prev:prev[y]=x;q.append(y)
 if goal not in prev:return []
 out=[];x=goal
 while x is not None:out.append(x);x=prev[x]
 return list(reversed(out))
def state_coordinate_changes(sig_a,sig_b):
 if not sig_a or not sig_b:return ['EXCLUDED_OR_INELIGIBLE']
 a,b=json.loads(sig_a),json.loads(sig_b)
 return [k for k in a if a[k]!=b[k]]
def stage_a():
 required=['instances_preoutcome.csv','mk_v2_signature_preoutcome.csv','matched_classes_preoutcome.csv','exchange_components_preoutcome.csv','exclusions.csv','preoutcome_manifest.json']
 for n in required:
  if not (WP09/n).exists():raise RuntimeError(f'missing frozen WP09 input: {n}')
 instances=read(WP09/'instances_preoutcome.csv'); sigrows=read(WP09/'mk_v2_signature_preoutcome.csv');comps=read(WP09/'exchange_components_preoutcome.csv'); exclusions=read(WP09/'exclusions.csv')
 byid={r['instance_id']:{**r,'p':tuple(parse(r['p_by_rank'])),'d':tuple(parse(r['d_by_rank'])),'orbit':(r['panel'],r['d_multiset'])} for r in instances}; sig={r['instance_id']:r['M_K_v2_serialized'] for r in sigrows}; sig_hash={r['instance_id']:r['M_K_v2_hash'] for r in sigrows}; ex={r['instance_id']:r['reason'] for r in exclusions}
 # Class identity follows the frozen pre-outcome class relation, not a recomputation.
 cls={};
 for r in read(WP09/'matched_classes_preoutcome.csv'):
  cls[(r['panel'],r['d_multiset'],r['M_K_v2_hash'])]=r['class_id']
 for iid,node in byid.items():node['mk_hash']=sig_hash.get(iid,'');node['class_id']=cls.get((node['panel'],node['d_multiset'],node['mk_hash']),'')
 members=defaultdict(list);compid={}
 for r in comps:
  if r['class_id'] in TARGETS:members[r['class_id']].append(r['instance_id']);compid[r['instance_id']]=r['component_id']
 pairs=[];paths=[];legs=[];trans=[];orbit_nodes=defaultdict(list)
 for n in byid.values():orbit_nodes[n['orbit']].append(n)
 pairno=0
 for cid in sorted(TARGETS):
  ids=sorted(members[cid]);
  for i,x in enumerate(ids):
   for y in ids[i+1:]:
    if compid[x]==compid[y]:continue
    pairno+=1;pid=f'XP{pairno:03d}';start,goal=x,y;nodes=orbit_nodes[byid[start]['orbit']];path=shortest_path(nodes,start,goal)
    pairs.append({'pair_id':pid,'class_id':cid,'endpoint_1':start,'endpoint_2':goal,'component_1':compid[start],'component_2':compid[goal],'path_exists':bool(path),'path_length':max(0,len(path)-1)})
    for step,iid in enumerate(path):
     n=byid[iid];paths.append({'pair_id':pid,'class_id':cid,'step':step,'instance_id':iid,'d_by_rank':enc(n['d']),'M_K_v2_hash':n['mk_hash'],'M_K_v2_class':n['class_id'],'exclusion_reason':ex.get(iid,''),'is_endpoint':iid in {start,goal},'in_endpoint_class':n['class_id']==cid})
    total=0
    for k,(u,v) in enumerate(zip(path,path[1:]),1):
     e=adjacent_swap(byid[u],byid[v]);assert e
     directed=e['predicted_delta_difference'] if u==e['I_forward'] else -e['predicted_delta_difference']
     total+=directed;e.update({'pair_id':pid,'class_id':cid,'leg':k,'path_from':u,'path_to':v,'path_predicted_delta_difference':directed});legs.append(e)
     changed=state_coordinate_changes(sig.get(u),sig.get(v));trans.append({'pair_id':pid,'class_id':cid,'leg':k,'from_instance_id':u,'to_instance_id':v,'from_class':byid[u]['class_id'],'to_class':byid[v]['class_id'],'coordinate_changes':enc(changed),'leaves_endpoint_class':byid[u]['class_id']==cid and byid[v]['class_id']!=cid,'returns_endpoint_class':byid[u]['class_id']!=cid and byid[v]['class_id']==cid})
    pairs[-1]['telescoped_predicted_delta_difference']=total if path else ''
 if len(pairs)!=22:raise RuntimeError(f'cross-component endpoint count {len(pairs)} != 22')
 for name,data in [('cross_component_pairs_preoutcome.csv',pairs),('canonical_paths_preoutcome.csv',paths),('path_leg_predictions_preoutcome.csv',legs),('theory_state_transitions_preoutcome.csv',trans)]:write(name,data)
 names=['cross_component_pairs_preoutcome.csv','canonical_paths_preoutcome.csv','path_leg_predictions_preoutcome.csv','theory_state_transitions_preoutcome.csv']
 manifest={'stage':'A_PRE_OUTCOME','required_inputs':{n:sha(WP09/n) for n in required},'artifacts':{n:sha(OUT/n) for n in names},'source_config_hashes':{'wp10_cross_state_audit.py':sha(Path(__file__)),'wp10_cross_state_audit.json':sha(CONFIG)},'certification':'Stage A rejected outcome-bearing sources and used only frozen WP09 Stage-A p/d, signature, class, component, and exclusion data.'}
 (OUT/'outcome_firewall_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding='utf-8')
 return pairs,paths,legs,trans,manifest
def stage_b(pairs,paths,legs,trans,manifest):
 if any(sha(OUT/n)!=h for n,h in manifest['artifacts'].items()):raise RuntimeError('Stage-A hash mutation')
 outcomes={r['instance_id']:r for r in read(WP09/'instances.csv',allow_outcome=True)};lrows=[];fail=[]
 for e in legs:
  observed=int(outcomes[e['I_forward']]['Delta'])-int(outcomes[e['I_reverse']]['Delta']);z=dict(e);z.update({'observed_delta_difference':observed,'prediction_matches':observed==e['predicted_delta_difference']});lrows.append(z)
  if not z['prediction_matches']:fail.append(e['pair_id'])
 legby=defaultdict(list)
 for e in lrows:legby[e['pair_id']].append(e)
 final=[]
 for p in pairs:
  obs=int(outcomes[p['endpoint_1']]['Delta'])-int(outcomes[p['endpoint_2']]['Delta']); # path orientation may differ; compare path start/end exact IDs
  path=[x for x in paths if x['pair_id']==p['pair_id']];start=min(path,key=lambda x:int(x['step']))['instance_id'] if path else '' ;end=max(path,key=lambda x:int(x['step']))['instance_id'] if path else ''
  observed=int(outcomes[start]['Delta'])-int(outcomes[end]['Delta']) if path else ''
  pred=p['telescoped_predicted_delta_difference'];ok=bool(path) and int(pred)==observed and all(x['prediction_matches'] for x in legby[p['pair_id']])
  status='TELESCOPES_VIA_STANDARD_EXCHANGE_PATH' if ok else 'NO_ADJACENT_EXCHANGE_PATH_IN_FROZEN_ORBIT' if not path else 'PATH_EXISTS_BUT_WP08_TELESCOPE_FAILS'
  z=dict(p);z.update({'path_start':start,'path_end':end,'observed_endpoint_delta_difference':observed,'classification':status});final.append(z)
  if not ok:fail.append(p['pair_id'])
 write('cross_component_pairs.csv',final);write('canonical_paths.csv',[{**x,'observed_Delta':outcomes[x['instance_id']]['Delta']} for x in paths]);write('path_leg_verification.csv',lrows);write('theory_state_transitions.csv',trans)
 sums=[]
 for cid in sorted(TARGETS):
  ps=[p for p in final if p['class_id']==cid];sums.append({'class_id':cid,'cross_component_pairs':len(ps),'all_cross_component_pairs_telescope':all(p['classification']=='TELESCOPES_VIA_STANDARD_EXCHANGE_PATH' for p in ps),'failed_pairs':sum(p['classification']!='TELESCOPES_VIA_STANDARD_EXCHANGE_PATH' for p in ps)})
 write('class_connectivity_summary.csv',sums)
 unchanged=all(sha(OUT/n)==h for n,h in manifest['artifacts'].items()); inv={'target_classes':len(TARGETS)==11,'cross_component_pairs':len(final)==22,'stage_A_hashes_unchanged':unchanged,'all_leg_predictions_match':not fail,'all_telescope':all(p['classification']=='TELESCOPES_VIA_STANDARD_EXCHANGE_PATH' for p in final)}
 status='CROSS_STATE_EXCHANGE_TELESCOPING_COMPLETE' if all(inv.values()) else 'GENUINE_RESIDUAL_BEYOND_FROZEN_EXCHANGE_DECOMPOSITION' if not any(p['classification']=='PATH_EXISTS_BUT_WP08_TELESCOPE_FAILS' for p in final) else 'IMPLEMENTATION_INVALID'
 return final,lrows,sums,inv,status
def run():
 OUT.mkdir(parents=True,exist_ok=True);pairs,paths,legs,trans,manifest=stage_a();final,lrows,sums,inv,status=stage_b(pairs,paths,legs,trans,manifest)
 (OUT/'run_manifest.json').write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),'terminal_label':status,'invariants':inv,'stage_A_manifest_hash':sha(OUT/'outcome_firewall_manifest.json'),'output_hashes':{p.name:sha(p) for p in OUT.iterdir() if p.name!='run_manifest.json'}},indent=2,sort_keys=True),encoding='utf-8')
 lengths=Counter(int(x['path_length']) for x in final);left=sum(any(not bool(x['in_endpoint_class']) for x in paths if x['pair_id']==p['pair_id']) for p in final)
 REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(f'''# WP10 Cross-State Exchange Telescoping and Connectivity Audit v1\n\n- Terminal label: `{status}`.\n- Frozen target classes/cross-component pairs: 11/22.\n- Canonical path-length distribution: `{dict(sorted(lengths.items()))}`.\n- Paths leaving the endpoint `M_K v2` class: {left}/22.\n- Exact WP08 leg and telescoped endpoint verification: {sum(p['classification']=='TELESCOPES_VIA_STANDARD_EXCHANGE_PATH' for p in final)}/22 PASS.\n- Stage-A outcome firewall/hash freeze: {'PASS' if inv['stage_A_hashes_unchanged'] else 'FAIL'}.\n- Theory-state transitions are serialized as changed frozen-key coordinates; no new determinant is asserted.\n- Artifacts: `tardy_bound/outputs/wp10/`.\n''',encoding='utf-8')
 print(json.dumps({'status':status,'pairs':len(final),'lengths':dict(lengths),'left':left},sort_keys=True))
if __name__=='__main__':run()
