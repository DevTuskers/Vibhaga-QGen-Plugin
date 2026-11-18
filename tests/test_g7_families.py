"""Synthetic English fixtures; real subprocess claim audits for G7 families."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt
import vdd_g7_families as g7


def examples():
    return [g7.build_vertical_scale(figure_id='g7scale',
                stem='A thermometer reads from -10 to 40 in steps of 10; the level is 20.',
                v_min=-10,v_max=40,step=10,level=20),
            g7.build_factor_tree(figure_id='g7factors',
                stem='Split 60 into 6 and 10, then 6 into 2 and 3, and 10 into 2 and 5.',
                n=60,splits={60:(6,10),6:(2,3),10:(2,5)}),
            g7.build_cube_array(figure_id='g7cubes',
                stem='Unit cubes have edge 1; stack heights are 2 and 3.',
                stacks={(0,0):2,(1,0):3,(0,1):2,(1,1):3})]


def audit(b):
    with tempfile.TemporaryDirectory() as tmp:
        paths = b.write(tmp)
        p = subprocess.run([sys.executable,str(TOOLS/'audit-claim-set.py'),str(paths['claims'])],
                           text=True,capture_output=True)
        assert p.returncode == 0, p.stdout+p.stderr


class G7FamiliesTests(unittest.TestCase):
    def test_happy_paths_and_claims(self):
        scale,tree,cubes = examples()
        for b in (scale,tree,cubes):
            audit(b)
        self.assertIn('reads T 20 on AB',scale.claims)
        self.assertIn('axis AB from -10 to 40',scale.claims)
        self.assertIn('derive 40 - -10 = 50',scale.claims)
        self.assertIn('60 = 6 × 10',tree.claims)
        self.assertIn('derive 2 * 3 * 2 * 5 = 60',tree.claims)
        self.assertIn('derive 2 + 2 + 3 + 3 = 10',cubes.claims)
        self.assertIn('hidden cubes are included',cubes.claims)

    def test_figure_modes(self):
        for b in (g7.build_vertical_scale(figure_id='scale',stem='Read the marked level.',v_min=-1,v_max=1,step=.5,level=-.25,values='figure',pointer='marker'),
                  g7.build_factor_tree(figure_id='tree',stem='Read the tree.',n=12,splits={12:(2,6),6:(2,3)},values='figure'),
                  g7.build_cube_array(figure_id='cubes',stem='Count the cubes.',stacks={(0,0):1},values='figure')):
            audit(b)

    def test_letters_hidden_counts_and_bounds(self):
        b = g7.build_factor_tree(figure_id='tree1', stem='12 2 6 3', n=12,
                                splits={12:(2,6),6:(2,3)}, leaves='ABC')
        audit(b)
        self.assertIn('label "A" names node1', b.claims)
        b = g7.build_cube_array(figure_id='cubes1', stem='Count the cubes.',
                               stacks={(c,r):2 for c in range(2) for r in range(2)}, values='figure')
        audit(b)
        self.assertIn('1 cubes have no exposed', b.claims)
        with self.assertRaises(vt.TemplateError):
            g7.build_factor_tree(figure_id='tree1', stem='Read it.',n=256,
                                 splits={256:(16,16),16:(4,4),4:(2,2)},values='figure')
        with self.assertRaises(vt.TemplateError):
            g7.build_factor_tree(figure_id='tree1', stem='Read it.',n=6,
                                 splits={6:(2,3)},leaves='AB',values='figure')
        audit(g7.build_vertical_scale(figure_id='scale2',stem='Bounds -10 and 10; step 5; level -5.',
              v_min=-10,v_max=10,step=5,level=-5))
        with self.assertRaises(vt.TemplateError):
            g7.build_vertical_scale(figure_id='scale2',stem='Bounds 10 and 10; step 5; level 5.',
              v_min=-10,v_max=10,step=5,level=-5)
        audit(g7.build_vertical_scale(figure_id='scale1',stem='Read it.',
              v_min=0,v_max=1,step=.1,level=.35,values='figure'))

    def test_seed_stability(self):
        code = ('import json; from tests.test_g7_families import examples; '
                'print(json.dumps([(b.doc,b.anchors,b.claims) for b in examples()],ensure_ascii=False))')
        import os
        results = [subprocess.run([sys.executable,'-c',code], cwd=TOOLS.parent,
                   env={**os.environ,'PYTHONHASHSEED':seed},capture_output=True,text=True,check=True).stdout
                   for seed in ('1','77')]
        self.assertEqual(*results)

    def test_scale_refusals(self):
        base=dict(figure_id='scale',stem='0 10 2 4',v_min=0,v_max=10,step=2,level=4)
        for kw in ({'level':11},{'step':3},{'step':.01},{'level':4.1},
                   {'v_min':.5},{'values':'bad'},{'pointer':[]},{'unit':'සි'}, {'stem':'Read it.'}):
            with self.subTest(kw=kw),self.assertRaises(vt.TemplateError):
                g7.build_vertical_scale(**{**base,**kw})
        for key in ('v_min','v_max','step','level'):
            for bad in (True,'2',float('nan'),float('inf'),10**1000,None):
                with self.subTest(key=key,bad=type(bad)),self.assertRaises(vt.TemplateError):
                    g7.build_vertical_scale(**{**base,key:bad})

    def test_tree_refusals(self):
        base=dict(figure_id='tree',stem='12 2 6 3',n=12,splits={12:(2,6),6:(2,3)})
        for kw in ({'splits':[]},{'splits':{12:(2,5)}},{'splits':{12:(1,12)}},
                   {'splits':{12:(2,6)}},{'splits':{12:(2,6),6:(2,3),10:(2,5)}},
                   {'splits':{12:(2,6,1)}},{'leaves':'AAZ'},{'leaves':'AB'},
                   {'stem':'Read it.'},{'values':'bad'}):
            with self.subTest(kw=kw),self.assertRaises(vt.TemplateError):
                g7.build_factor_tree(**{**base,**kw})
        for bad in (True,'2',float('nan'),float('inf'),10**1000,None):
            for kw in ({'n':bad},{'splits':{12:(bad,6)}},{'splits':{bad:(2,6)}}):
                with self.subTest(kw=str(type(bad))),self.assertRaises(vt.TemplateError):
                    g7.build_factor_tree(**{**base,**kw})
        with self.assertRaises(vt.TemplateError):
            g7.build_factor_tree(figure_id='deep',stem='Tree.',n=64,splits={64:(2,32),32:(2,16),16:(2,8),8:(2,4),4:(2,2)},values='figure')

    def test_cube_refusals(self):
        base=dict(figure_id='cubes',stem='1 2',stacks={(0,0):2})
        for kw in ({'stacks':[]},{'stacks':{}},{'stacks':{(0,0):0}},
                   {'stacks':{(5,0):1}},{'stacks':{(0,4):1}},{'stacks':{(0,0):5}},
                   {'stacks':{(1,1):1}},{'stacks':{'00':1}},{'unit_cube':0},
                   {'stem':'Read it.'},{'values':'bad'},
                   {'stacks':{(c,r):4 for c in range(5) for r in range(4)}}):
            with self.subTest(kw=kw),self.assertRaises(vt.TemplateError):
                g7.build_cube_array(**{**base,**kw})
        for bad in (True,'2',float('nan'),float('inf'),10**1000,None):
            for kw in ({'unit_cube':bad},{'stacks':{(0,0):bad}},{'stacks':{(bad,0):2}}):
                with self.subTest(bad=type(bad)),self.assertRaises(vt.TemplateError):
                    g7.build_cube_array(**{**base,**kw})


if __name__ == '__main__':
    unittest.main()
