import sys
import inspect
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wp09_independent_validation import exchange_data, generate, hinge, stage_a

def test_frozen_panel_counts():
 rows=list(generate())
 assert len(rows)==15480
 assert sum(x[0]=='A' for x in rows)==360 and sum(x[0]=='B' for x in rows)==15120

def test_exchange_prediction_orientation():
 p=(1,2,4,7)
 left={'instance_id':'left','p':p,'d':(3,1,5,7)}
 right={'instance_id':'right','p':p,'d':(1,3,5,7)}
 e=exchange_data(left,right)
 assert e and e['I_forward']=='right' and e['predicted_delta_difference']==hinge(1,1,3)-hinge(3,1,3)-max(0,1-1)+max(0,2-1)

def test_stage_a_has_no_objective_evaluator_call():
 source=inspect.getsource(stage_a)
 assert 'tt(' not in source and 'optimum(' not in source
