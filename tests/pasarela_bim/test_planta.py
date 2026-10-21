import unittest
import itertools
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from pasarela_bim.planta import (leer_dxf, convertir_dwg, _exportacion_completa,
                                 _esperar_conversion, _unidades_cabecera)


def drawing(entities, blocks="", unit=6):
    return (f"0\nSECTION\n2\nHEADER\n9\n$INSUNITS\n70\n{unit}\n0\nENDSEC\n"
            + ("0\nSECTION\n2\nBLOCKS\n"+blocks+"0\nENDSEC\n" if blocks else "")
            + "0\nSECTION\n2\nENTITIES\n"+entities+"0\nENDSEC\n0\nEOF\n").encode()


class TestPlanta(unittest.TestCase):
    def test_preserves_survey_coordinates_and_normalizes_declared_units(self):
        data = drawing("0\nLINE\n8\nCAMINO\n10\n350000000\n20\n6000000000\n30\n120000\n11\n350010000\n21\n6000000000\n31\n121000\n", unit=4)
        result = leer_dxf(data)
        self.assertEqual(result["entidades"][0]["puntos_m"], [[350000,6000000,120],[350010,6000000,121]])
        self.assertTrue(result["avisos"])

    def test_insert_applies_base_rotation_scale_and_layer(self):
        blocks = "0\nBLOCK\n2\nROAD\n10\n10\n20\n20\n0\nLINE\n8\n0\n10\n10\n20\n20\n11\n15\n21\n20\n0\nENDBLK\n"
        result = leer_dxf(drawing("0\nINSERT\n2\nROAD\n8\nMEDIANA\n10\n300000\n20\n6000000\n41\n2\n50\n90\n",blocks))
        line = result["entidades"][0]
        self.assertEqual(line["capa"],"MEDIANA")
        self.assertEqual(line["puntos_m"],[[300000,6000000,0],[300000,6000010,0]])

    def test_bulged_polyline_is_sampled_instead_of_straight_chord(self):
        result = leer_dxf(drawing("0\nLWPOLYLINE\n10\n0\n20\n0\n42\n1\n10\n10\n20\n0\n"))
        points=result["entidades"][0]["puntos_m"]
        self.assertGreater(len(points),10)
        self.assertAlmostEqual(min(p[1] for p in points),-5)
        self.assertEqual(points[-1],[10,0,0])

    def test_paperspace_excluded_and_unsupported_entities_reported(self):
        result = leer_dxf(drawing("0\nLINE\n67\n1\n10\n0\n11\n1\n0\nLINE\n10\n0\n11\n2\n0\nSPLINE\n"))
        self.assertEqual(len(result["entidades"]),1)
        self.assertIn("SPLINE",result["avisos"][0])

    def test_unknown_units_and_invalid_data_rejected(self):
        for data in (b"AutoCAD Binary DXF",b"html",drawing("0\nLINE\n",unit=99),drawing("0\nLINE\n10\nnan\n")):
            with self.subTest(data=data):
                with self.assertRaises(ValueError): leer_dxf(data)

    def test_conversion_requires_matching_marker_complete_dxf_and_same_units(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); out=folder/'planta.dxf'; marker=folder/'complete'
            out.write_bytes(drawing("0\nLINE\n10\n0\n11\n2\n",unit=4))
            marker.write_text("other\n4\n4\n")
            self.assertIsNone(_exportacion_completa(out,marker,"job"))
            marker.write_text("job\n4\n")
            self.assertIsNone(_exportacion_completa(out,marker,"job"))
            marker.write_text("job\n4\n4\n")
            self.assertEqual(_exportacion_completa(out,marker,"job"),4)
            self.assertEqual(_unidades_cabecera(out.read_bytes()),4)
            out.write_bytes(out.read_bytes().replace(b"EOF",b""))
            self.assertIsNone(_exportacion_completa(out,marker,"job"))
            marker.write_text("job\n4\n6\n")
            with self.assertRaisesRegex(ValueError,"unidades"):
                _exportacion_completa(out,marker,"job")

    def test_complete_export_does_not_wait_for_unresponsive_quit(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); out=folder/'planta.dxf'; marker=folder/'complete'
            out.write_bytes(drawing("0\nLINE\n10\n0\n11\n2\n",unit=6))
            marker.write_text("job\n6\n6\n")
            process=Mock();process.poll.return_value=None
            clock=itertools.count(step=.4)
            with patch('pasarela_bim.planta.time.monotonic',side_effect=lambda:next(clock)), patch('pasarela_bim.planta.time.sleep'):
                self.assertEqual(_esperar_conversion(process,out,marker,"job"),6)

    def test_conversion_failure_stops_only_its_own_process(self):
        with tempfile.TemporaryDirectory() as directory:
            process=Mock();process.poll.return_value=None
            with patch('pasarela_bim.planta.localizar_conversor',return_value=Path('motor.exe')), patch('pasarela_bim.planta._preparar_perfil_aislado'), patch('pasarela_bim.planta.subprocess.Popen',return_value=process) as popen, patch('pasarela_bim.planta._esperar_conversion',side_effect=ValueError('exportación incompleta')):
                with self.assertRaisesRegex(ValueError,'incompleta'):
                    convertir_dwg(b'AC1032 private test',Path(directory)/'job')
                process.kill.assert_called_once_with()
                process.wait.assert_called_once_with(timeout=10)
                args=popen.call_args.args[0]
                self.assertIn('/readonly',args)
                self.assertIn('/isolate',args)
                self.assertEqual(args[-2:],['/p','PASARELA_IMPORT'])

if __name__ == "__main__": unittest.main()
