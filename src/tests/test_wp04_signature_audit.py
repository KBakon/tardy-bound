import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from wp04_signature_audit import OutcomeFirewallError, StageAReader, signature_for

def _reader():
    # Rejection occurs before a file is opened; no pytest temporary directory is needed.
    return StageAReader(Path(__file__).resolve().parents[1]/'outputs'/'wp04')

def test_outcome_file_is_rejected_before_opening():
    reader=_reader()
    with pytest.raises(OutcomeFirewallError):
        reader.csv('instances.csv',['instance_id'])

def test_outcome_column_is_rejected_before_opening():
    reader=_reader()
    with pytest.raises(OutcomeFirewallError):
        reader.csv('instances_preoutcome.csv',['Delta'])

def test_s1_uses_graph_only_not_derived_bael():
    record={'orbit':{'n':3},'mk':{'G123':{'edges':[[1,2]],'B':[[1]],'A':[[]],'E':[1],'L':[1]}}}
    assert signature_for('S1',record)=={'orbit':{'n':3},'G123':{'edges':[[1,2]]}}
