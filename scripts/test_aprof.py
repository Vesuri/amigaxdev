"""Synthetic accounting, stop-boundary and malformed-tree controls."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'share/pylib'))
from amigaxdev.aprof import parse_profile, call_tree

BASE='''AITDPROF 1
units 1024
cycleunit 128
CYCLE_UNIT 512
gap 128
high 0
overflow 0
unmatched_rts 0
unmatched_rte 0
P 100 768 3 0 0
N 0 0 0 0 128 0
N 1 0 100 0 768 1
'''
class Checks(unittest.TestCase):
    def test_tail(self):
        for tail in (0,128,256,384,512):
            h,pcs,nodes=parse_profile(BASE.replace('units 1024',f'units {896+tail}'))
            self.assertEqual(h['tail'],tail)
            self.assertEqual(call_tree(nodes)[2][0],896)
            self.assertEqual(sum(p[0] for p in pcs.values())+h['gap']+tail,h['units'])
        for units in (895,897,1409):
            with self.assertRaises(ValueError):parse_profile(BASE.replace('units 1024',f'units {units}'))
    def test_accounting(self):
        for before,after in [('768 3','769 3'),('gap 128','gap 0'),('overflow 0','overflow 1'),('AITDPROF 1','AITDPROF 2')]:
            with self.assertRaises(ValueError):parse_profile(BASE.replace(before,after))
    def test_tree(self):
        _,_,nodes=parse_profile(BASE)
        for bad in ({1:nodes[1]}, {**nodes,1:(2,256,0,768,1)},
                    {**nodes,1:(1,256,0,768,1)}):
            with self.assertRaises(ValueError):call_tree(bad)
    def test_unmatched_is_not_hidden(self):
        h,_,_=parse_profile(BASE.replace('unmatched_rts 0','unmatched_rts 7'))
        self.assertEqual(h['unmatched_rts'],7)

if __name__=='__main__':unittest.main()
