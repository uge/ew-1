"""Regression cases for previously omitted elevated pairs and copper extents."""
import tempfile
import unittest
from pathlib import Path
import pcbnew
import map_board_voltages as insulation
from native_multiplier import circuit

class SafetyAnalysisTests(unittest.TestCase):
    def test_elevated_pairs_use_copper_boundaries_and_actual_edges(self):
        b=pcbnew.BOARD()
        for name,y in [('/03_multiplier/CW_S2',0),('/03_multiplier/CW_S4',4)]:
            net=pcbnew.NETINFO_ITEM(b,name); b.Add(net)
            t=pcbnew.PCB_TRACK(b);t.SetStart(pcbnew.VECTOR2I(0,int(y*1e6)))
            t.SetEnd(pcbnew.VECTOR2I(10000000,int(y*1e6)))
            t.SetWidth(1000000);t.SetLayer(pcbnew.F_Cu);t.SetNet(net);b.Add(t)
        fp=pcbnew.FOOTPRINT(b);fp.SetReference('HOLE');b.Add(fp)
        pad=pcbnew.PAD(fp);pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE);pad.SetLayerSet(pcbnew.LSET.AllCuMask())
        pad.SetSize(pcbnew.VECTOR2I(1000000,1000000));pad.SetDrillSize(pcbnew.VECTOR2I(1000000,1000000))
        fp.Add(pad);pad.SetPosition(pcbnew.VECTOR2I(20000000,20000000))
        coords=[(-10,-10),(30,-10),(30,30),(-10,30),(-10,-10)]
        for a,c in zip(coords,coords[1:]):
            line=pcbnew.PCB_SHAPE(b);line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetStart(pcbnew.VECTOR2I(int(a[0]*1e6),int(a[1]*1e6)))
            line.SetEnd(pcbnew.VECTOR2I(int(c[0]*1e6),int(c[1]*1e6)))
            line.SetLayer(pcbnew.Edge_Cuts);b.Add(line)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'fixture.kicad_pcb';pcbnew.SaveBoard(str(path),b)
            report=insulation.analyze_board(str(path))
        self.assertEqual(len(report['top_surface']),1)
        pair=report['top_surface'][0]
        self.assertAlmostEqual(pair['distance_mm'],3.,delta=.005)
        self.assertEqual(pair['delta_v'],5000.)
        self.assertEqual(pair['status'],'CRITICAL')
        self.assertAlmostEqual(min(x['clearance_mm'] for x in report['edge_audit']),9.5,delta=.005)

    def test_phase_envelope_catches_negative_secondary(self):
        self.assertEqual(insulation.voltage_difference(insulation.voltage_bounds('/SEC_A'),(2500,2500)),3750)

    def test_native_model_keeps_real_sense_leg_and_ground_return(self):
        text,caps,_=circuit()
        self.assertIn('R8 HV_SENSE ',text)
        self.assertIn('R9 ',text)
        self.assertIn('C101 0 CW_S1 1n',text)
        self.assertIn('D10 0 CW_P1 D2CL75',text)
        self.assertEqual(len([c for c in caps if int(c[0][1:])>=100]),12)

if __name__=='__main__':
    unittest.main()
