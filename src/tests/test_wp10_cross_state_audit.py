import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wp10_cross_state_audit import adjacent_swap, validate_stage_a_headers

def test_adjacent_exchange_prediction_is_oriented():
 a={'instance_id':'a','p':(1,2,4,7,11),'d':(3,1,5,7,9)};b={'instance_id':'b','p':(1,2,4,7,11),'d':(1,3,5,7,9)}
 e=adjacent_swap(a,b)
 assert e and e['I_forward']=='b' and e['d_L']==1 and e['d_H']==3

def test_outcome_column_is_rejected():
 try: validate_stage_a_headers(['instance_id','Delta'])
 except RuntimeError: return
 assert False,'outcome-bearing Stage-A input must be rejected'
