import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wp07_witness_audit import category, cycles, transform

def test_transform_transposition():
    mapping, cs, moved, minimum = transform([1,2,3,4],[1,4,3,2])
    assert mapping == [0,3,2,1] and moved == [2,4] and minimum == 1
    assert cycles(mapping) == [[1],[2,4],[3]]

def test_objective_categories():
    assert category(0, -1) == "EDD_ONLY_CHANGE"
    assert category(2, -1) == "BOTH_CHANGE_SAME_NET"
    assert category(2, 1) == "BOTH_CHANGE_OFFSETTING"
