"""La mira se dibuja con el estilo, el tamaño, el grosor y la transparencia pedidos."""

import unittest

from yxi96_mira.render import pixel, premultiply_bgra, render
from yxi96_mira.settings import MiraSettings, load_settings, save_settings


class RenderTests(unittest.TestCase):
    def test_punto_blanco_en_el_centro(self):
        red, green, blue, alpha = pixel(MiraSettings(style="punto", color="#FFFFFF", opacity=1), 0, 0)
        self.assertGreater(red, 240)
        self.assertGreater(green, 240)
        self.assertGreater(blue, 240)
        self.assertGreater(alpha, 240)

    def test_la_esquina_queda_transparente(self):
        _width, _height, rgba = render(MiraSettings())
        self.assertEqual(rgba[3], 0)

    def test_transparencia_baja_el_alfa(self):
        _solid = pixel(MiraSettings(style="punto", opacity=1), 0, 0)[3]
        faded = pixel(MiraSettings(style="punto", opacity=0.5), 0, 0)[3]
        self.assertGreater(_solid, 240)
        self.assertTrue(110 <= faded <= 150)

    def test_el_color_elegido_pinta_el_punto(self):
        red, green, blue, alpha = pixel(MiraSettings(style="punto", color="#FF0000"), 0, 0)
        self.assertGreater(red, 240)
        self.assertLess(green, 15)
        self.assertLess(blue, 15)
        self.assertGreater(alpha, 240)

    def test_la_cruz_cerrada_ocupa_el_centro_y_la_abierta_no(self):
        closed = pixel(MiraSettings(style="cruz", size=20, thickness=2, outline=False), 0, 0)[3]
        opened = pixel(MiraSettings(style="cruz_abierta", size=20, thickness=2, outline=False), 0, 0)[3]
        self.assertGreater(closed, 200)
        self.assertEqual(opened, 0)

    def test_el_circulo_esta_hueco_y_el_punto_lo_rellena(self):
        ring = pixel(MiraSettings(style="circulo", size=16, thickness=2, outline=False), 0, 0)[3]
        dotted = pixel(MiraSettings(style="circulo_punto", size=16, thickness=2, outline=False), 0, 0)[3]
        self.assertEqual(ring, 0)
        self.assertGreater(dotted, 200)

    def test_el_cuadrado_y_las_marcas_dejan_el_centro_libre(self):
        square = pixel(MiraSettings(style="cuadrado", size=18, thickness=2, outline=False), 0, 0)[3]
        marks = pixel(MiraSettings(style="marcas", size=18, thickness=2, outline=False), 0, 0)[3]
        self.assertEqual(square, 0)
        self.assertEqual(marks, 0)

    def test_mas_grosor_cubre_un_pixel_que_antes_estaba_vacio(self):
        thin = pixel(MiraSettings(style="cruz", size=20, thickness=1, outline=False), 10, 3)[3]
        thick = pixel(MiraSettings(style="cruz", size=20, thickness=8, outline=False), 10, 3)[3]
        self.assertLess(thin, 40)
        self.assertGreater(thick, 200)

    def test_mas_tamano_agranda_el_cuadro(self):
        small, _, _ = render(MiraSettings(style="punto", size=4, thickness=1))
        large, _, _ = render(MiraSettings(style="punto", size=40, thickness=1))
        self.assertGreater(large, small)
        self.assertEqual(small % 2, 1)

    def test_el_contorno_es_oscuro_fuera_del_punto(self):
        red, _green, _blue, alpha = pixel(MiraSettings(style="punto", size=6, thickness=2, outline=True), 5, 0)
        self.assertGreater(alpha, 40)
        self.assertLess(red, 40)

    def test_todos_los_estilos_dibujan(self):
        for style, _label in (
            ("punto", ""),
            ("cruz", ""),
            ("cruz_abierta", ""),
            ("circulo", ""),
            ("circulo_punto", ""),
            ("cruz_circulo", ""),
            ("marcas", ""),
            ("cuadrado", ""),
        ):
            width, height, rgba = render(MiraSettings(style=style, size=18, thickness=3))
            self.assertEqual(width, height)
            self.assertEqual(len(rgba), width * height * 4)
            self.assertGreater(max(rgba[3::4]), 200)

    def test_premultiplicado_bgra(self):
        self.assertEqual(premultiply_bgra(bytes([255, 0, 0, 128])), bytes([0, 0, 128, 128]))


class SettingsTests(unittest.TestCase):
    def test_los_valores_fuera_de_rango_se_recortan(self):
        shape = MiraSettings(style="no-existe", size=400, thickness=0, opacity=8, color="fff").clamped()
        self.assertEqual(shape.style, "punto")
        self.assertEqual(shape.size, 64)
        self.assertEqual(shape.thickness, 1)
        self.assertEqual(shape.opacity, 1)
        self.assertEqual(shape.color, "#FFFFFF")

    def test_el_archivo_redondo_conserva_el_perfil(self):
        import tempfile
        from pathlib import Path

        shape = MiraSettings(style="marcas", size=22, thickness=4, opacity=0.4, color="#39FF6A", offset_x=-3)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mira.json"
            save_settings(shape, path)
            loaded = load_settings(path)
        self.assertEqual(loaded.style, "marcas")
        self.assertEqual(loaded.size, 22)
        self.assertEqual(loaded.thickness, 4)
        self.assertAlmostEqual(loaded.opacity, 0.4)
        self.assertEqual(loaded.color, "#39FF6A")
        self.assertEqual(loaded.offset_x, -3)

    def test_un_archivo_viejo_sigue_abriendo(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mira.json"
            path.write_text('{"name": "viejo"}', encoding="utf-8")
            loaded = load_settings(path)
        self.assertEqual(loaded.style, "punto")


if __name__ == "__main__":
    unittest.main()
