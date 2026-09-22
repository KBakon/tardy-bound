import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from theory_state import *

def test_o1_o2():
    a=state_for((1,2,3),(1,3,6)); assert a['SRD'] and a['ERD'] and a['spt']==a['edd'] and tt((1,2,3),(1,3,6),(0,1,2))==0
    b=state_for((1,2,3),(1,3,2)); assert not b['SRD'] and b['ERD'] and b['alpha']==[1,3,3] and not b['EDD_C22']; assert tt((1,2,3),(1,3,2),(0,1,2))==4 and tt((1,2,3),(1,3,2),(0,2,1))==5
def test_o3_o4_o5():
    a=state_for((1,2,3),(4,2,5)); assert a['closure_count']==1 and edge_labels(a['raw']['edges'])==[[1,3],[2,1],[2,3]] and a['beta']==[4,2,6] and a['beta_sequence']==[2,1,3] and a['beta_optimal'] and a['EDD_C22'] and 1 in a['exact_q']
    b=state_for((1,2,3,4),(8,7,6,1)); assert b['NRD'] and b['NRD_hard'] and b['beta_status']==['FAIL','EQUALITY','STRICT_PASS','NA'] and b['key_h']==1 and b['branch_positions']==[1,4] and b['mdd']==[[4,2,1,3],[4,3,1,2]]
    c=state_for((1,2,4),(1,3,2)); assert c['lawler_jL']==2 and c['lawler_positions']==[2,3]
def test_equality_rules_and_outcome_guard():
    # O6: each predicate is exercised directly at its exact equality boundary.
    assert emmons_conditions(5,1,3,5,9,9)[0]  # T1: d_j=max(E_k,d_k)
    assert not emmons_conditions(5,1,3,5,6,9)[1]  # T2 first bound is strict
    assert emmons_conditions(6,1,3,5,7,9)[1]  # T2 second bound equality fires
    assert emmons_conditions(8,1,3,5,9,5)[2]  # T3: d_k=L_j
    assert not state_for((1,2,3),(2,2,1))['NRD']
    s=state_for((1,2,3),(4,2,5)); assert s['beta_status']==s['beta_status_fset']
    s['Delta']=1
    try: match_signature(s); assert False
    except RuntimeError: pass
