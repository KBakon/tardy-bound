import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wp06_mk_v2_rerun import generate
import inspect
import wp06_mk_v2_rerun
def test_frozen_census_shape():
    rows=generate(); assert len(rows)==3084 and sum(len(p)==3 for _,p,_,_ in rows)==60 and sum(len(p)==4 for _,p,_,_ in rows)==3024

def test_stage_a_path_does_not_call_outcome_scorer():
    assert 'tt(' not in inspect.getsource(wp06_mk_v2_rerun.stage_a)
