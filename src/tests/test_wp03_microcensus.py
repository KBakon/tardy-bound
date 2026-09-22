import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wp03_microcensus import generate
def test_census_shape():
    rows=generate(); assert len(rows)==3084
    assert sum(1 for _,p,_,_ in rows if len(p)==3)==60
    assert sum(1 for _,p,_,_ in rows if len(p)==4)==3024
    assert len({(p,d) for _,p,d,_ in rows})==3084
