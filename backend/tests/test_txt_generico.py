from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.importadores import txt_generico, txt_id_tempo_maquina, txt_log_relogio
from app.importadores.deteccao import detectar_adaptadores_txt
from app.importadores.txt_generico import parse_txt_generico


class TxtGenericoTests(unittest.TestCase):
    def test_fallback_nao_toma_o_lugar_dos_layouts_homologados(self) -> None:
        fixtures = Path(__file__).resolve().parent / "fixtures"
        self.assertEqual(
            detectar_adaptadores_txt((fixtures / "relogio_ficticio.txt").read_bytes()),
            [txt_log_relogio],
        )
        self.assertEqual(
            detectar_adaptadores_txt((fixtures / "relogio_id_tempo_maquina.txt").read_bytes()),
            [txt_id_tempo_maquina],
        )

    def test_semicolon_aliases_e_data_hora_brasileira(self) -> None:
        conteudo = (
            "Matrícula;Funcionário;Data e Hora;Terminal\n"
            "77;João da Silva;01/08/2026 08:01:00;A\n"
            "77;João da Silva;01/08/2026 12:02:00;A\n"
            "77;João da Silva;01/08/2026 13:00:00;A\n"
            "77;João da Silva;01/08/2026 17:11:00;A\n"
        ).encode("utf-8")
        self.assertEqual(detectar_adaptadores_txt(conteudo), [txt_generico])
        resultado = parse_txt_generico(
            conteudo,
            arquivo_nome="variacao.txt",
            mes=8,
            ano=2026,
            funcionarios=({"id": 5, "codigo": "77", "nome": "João da Silva"},),
        )
        self.assertEqual(resultado["total_linhas_validas"], 4)
        self.assertEqual(len(resultado["registros"]), 1)
        registro = resultado["registros"][0]
        self.assertEqual(registro["funcionario"]["codigo_origem"], "77")
        self.assertEqual(registro["funcionario"]["nome_origem"], "João da Silva")
        self.assertEqual(registro["batidas_originais"], ["08:01:00", "12:02:00", "13:00:00", "17:11:00"])
        self.assertTrue(registro["funcionario"]["encontrado"])
        self.assertTrue(registro["selecionado"])

    def test_data_separada_com_quatro_colunas_de_horario(self) -> None:
        conteudo = (
            "Código|Nome|Data|Entrada|Saída Almoço|Retorno Almoço|Saída\n"
            "F10|Maria Teste|02/08/2026|08:00|12:00|13:00|17:00\n"
        ).encode("utf-8")
        self.assertEqual(detectar_adaptadores_txt(conteudo), [txt_generico])
        resultado = parse_txt_generico(
            conteudo, arquivo_nome="largo.txt", mes=8, ano=2026, funcionarios=()
        )
        registro = resultado["registros"][0]
        self.assertEqual(registro["batidas_originais"], ["08:00:00", "12:00:00", "13:00:00", "17:00:00"])
        self.assertEqual(registro["interpretacao"]["entrada"], "08:00")
        self.assertEqual(registro["interpretacao"]["saida"], "17:00")

    def test_cabecalho_ingles_e_iso_sem_segundos(self) -> None:
        conteudo = (
            "Employee ID,Employee Name,Timestamp\n"
            "9,Ana Souza,2026-08-03 09:02\n"
            "9,Ana Souza,2026-08-03 18:05\n"
        ).encode("utf-8")
        self.assertEqual(detectar_adaptadores_txt(conteudo), [txt_generico])
        resultado = parse_txt_generico(
            conteudo, arquivo_nome="english.csv.txt", mes=8, ano=2026, funcionarios=()
        )
        registro = resultado["registros"][0]
        self.assertEqual(registro["funcionario"]["codigo_origem"], "9")
        self.assertEqual(registro["batidas_originais"], ["09:02:00", "18:05:00"])

    def test_cp1252_e_linha_de_rodape_sao_tolerados(self) -> None:
        texto = (
            "Código;Nome;Horário Marcação\n"
            "1;José da Conceição;04/08/2026 08:00:00\n"
            "1;José da Conceição;04/08/2026 17:00:00\n"
            "Relatório gerado automaticamente\n"
        )
        conteudo = texto.encode("cp1252")
        resultado = parse_txt_generico(
            conteudo, arquivo_nome="cp1252.txt", mes=8, ano=2026, funcionarios=()
        )
        self.assertEqual(resultado["encoding"], "cp1252")
        self.assertEqual(resultado["total_linhas_validas"], 2)
        self.assertEqual(resultado["total_linhas_ignoradas"], 1)
        self.assertEqual(len(resultado["avisos"]), 1)

    def test_linhas_sem_cabecalho_com_id_nome_datetime(self) -> None:
        conteudo = (
            "15  Carlos Pereira  05/08/2026 08:03:00\n"
            "15  Carlos Pereira  05/08/2026 12:00:00\n"
            "15  Carlos Pereira  05/08/2026 13:02:00\n"
            "15  Carlos Pereira  05/08/2026 17:09:00\n"
        ).encode("utf-8")
        self.assertEqual(detectar_adaptadores_txt(conteudo), [txt_generico])
        resultado = parse_txt_generico(
            conteudo, arquivo_nome="livre.txt", mes=8, ano=2026, funcionarios=()
        )
        self.assertEqual(resultado["registros"][0]["funcionario"]["codigo_origem"], "15")
        self.assertEqual(resultado["registros"][0]["funcionario"]["nome_origem"], "Carlos Pereira")
        self.assertEqual(len(resultado["registros"][0]["batidas_originais"]), 4)


if __name__ == "__main__":
    unittest.main()
