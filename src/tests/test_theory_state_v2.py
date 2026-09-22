import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from theory_state_v2 import *
def test_v2_o2_and_diagnostics_do_not_hash():
    s=build_v2_state((1,2,3),(1,3,2)); k=mk_v2_key(s)
    assert k['schema']==SCHEMA and k['EDD_C22'] is False and k['GEOM4']==[False,True,False,False]
    assert diagnostic_mutation_invariant(s)
def test_mdd_trie_o4_and_lawler_family():
    s=build_v2_state((1,2,3,4),(8,7,6,1)); assert s['MDD_leaves_from_trie']==[[4,2,1,3],[4,3,1,2]]
    assert s['T_MDD'][0]=={'prefix':[],'argmin':[4]}
    a=build_v2_state((1,2,4),(1,3,2)); assert a['LAWLER_PARTITION_FAMILY']==[[2,[1],3,[2]],[3,[1,2],3,[]]]
