from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.importadores.interpretacao_batidas import interpretar_batidas


class InterpretarBatidasTests(unittest.TestCase):
    def test_quatro_horarios_e_normal_e_preenche_tudo(self) -> None:
        resultado = interpretar_batidas(["08:00", "12:00", "13:00", "17:00"])
        self.assertEqual(
            resultado,
            {
                "entrada": "08:00",
                "saida_almoco": "12:00",
                "retorno_almoco": "13:00",
                "saida": "17:00",
                "status": "normal",
                "status_dia": "normal",
                "observacoes": None,
            },
        )

    def test_dois_horarios_preenche_apenas_entrada_e_saida(self) -> None:
        resultado = interpretar_batidas(["08:00", "17:00"])
        self.assertEqual(resultado["entrada"], "08:00")
        self.assertEqual(resultado["saida"], "17:00")
        self.assertIsNone(resultado["saida_almoco"])
        self.assertIsNone(resultado["retorno_almoco"])
        self.assertEqual(resultado["status"], "pendente_conferencia")

    def test_um_horario_preenche_apenas_entrada(self) -> None:
        resultado = interpretar_batidas(["08:00"])
        self.assertEqual(resultado["entrada"], "08:00")
        self.assertTrue(all(resultado[campo] is None for campo in ("saida_almoco", "retorno_almoco", "saida")))
        self.assertEqual(resultado["status"], "pendente_conferencia")

    def test_tres_horarios_nao_adivinha_nenhum_campo(self) -> None:
        resultado = interpretar_batidas(["08:00", "12:00", "17:00"])
        self.assertTrue(
            all(resultado[campo] is None for campo in ("entrada", "saida_almoco", "retorno_almoco", "saida"))
        )
        self.assertEqual(resultado["status"], "pendente_conferencia")

    def test_mais_de_quatro_horarios_nao_adivinha_nenhum_campo(self) -> None:
        resultado = interpretar_batidas(["08:00", "08:00", "12:00", "13:00", "17:00", "17:30"])
        self.assertTrue(
            all(resultado[campo] is None for campo in ("entrada", "saida_almoco", "retorno_almoco", "saida"))
        )
        self.assertEqual(resultado["status"], "pendente_conferencia")

    def test_zero_horarios_fica_pendente_sem_conferencia(self) -> None:
        resultado = interpretar_batidas([])
        self.assertTrue(
            all(resultado[campo] is None for campo in ("entrada", "saida_almoco", "retorno_almoco", "saida"))
        )
        self.assertEqual(resultado["status"], "pendente")


if __name__ == "__main__":
    unittest.main()
