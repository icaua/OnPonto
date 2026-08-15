from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.importadores.txt_log_relogio import ErroImportacaoTxt, parse_txt_log_relogio


CABECALHO = [
    "No",
    "TMNo",
    "EnNo",
    "Name",
    "GMNo",
    "Mode",
    "In/Out",
    "VM",
    "Department",
    "DateTime",
]


def montar_txt(registros: list[tuple[str, str, str]], cabecalho: list[str] | None = None) -> str:
    linhas = ["\t".join(cabecalho or CABECALHO)]
    for numero, (codigo, nome, data_hora) in enumerate(registros, start=1):
        linhas.append(
            "\t".join(
                [
                    str(numero),
                    "1",
                    codigo,
                    nome,
                    "1",
                    "0",
                    "1",
                    "Dedo",
                    "Dep1",
                    data_hora,
                ]
            )
        )
    return "\r\n".join(linhas) + "\r\n"


class ParseTxtLogRelogioTests(unittest.TestCase):
    def parse(
        self,
        registros: list[tuple[str, str, str]],
        *,
        funcionarios: tuple[dict, ...] = ({"id": 10, "codigo": "5", "nome": "Lana Fernanda"},),
        mes: int = 7,
        ano: int = 2026,
        encoding: str = "utf-8",
    ) -> dict:
        conteudo = montar_txt(registros).encode(encoding)
        return parse_txt_log_relogio(
            conteudo,
            arquivo_nome="ALOG_TESTE.txt",
            mes=mes,
            ano=ano,
            funcionarios=funcionarios,
        )

    def test_arquivo_utf16_com_bom(self) -> None:
        resultado = self.parse(
            [("5", "LANA FERNANDA", "2026-07-01 08:03:17")],
            encoding="utf-16",
        )

        self.assertEqual(resultado["encoding"], "utf-16")
        self.assertEqual(resultado["total_linhas_validas"], 1)
        registro = resultado["registros"][0]
        self.assertEqual(registro["batidas_originais"], ["08:03:17"])
        self.assertEqual(registro["interpretacao"]["entrada"], "08:03")
        self.assertTrue(
            all(
                registro["interpretacao"][campo] is None
                for campo in ("saida_intervalo", "retorno_intervalo", "saida")
            )
        )
        self.assertEqual(registro["status"], "conferir")
        self.assertIn("Apenas uma batida encontrada", registro["pendencias"])

    def test_arquivo_utf16_le_sem_bom_detectavel(self) -> None:
        resultado = self.parse(
            [("5", "LANA FERNANDA", "2026-07-01 08:03:17")],
            encoding="utf-16-le",
        )

        self.assertEqual(resultado["encoding"], "utf-16-le")
        self.assertEqual(resultado["registros"][0]["data"], "2026-07-01")

    def test_utf8_com_bom_e_utf8_sem_bom(self) -> None:
        registros = [("5", "LANA FERNANDA", "2026-07-01 08:03:17")]
        for encoding, esperado in (("utf-8-sig", "utf-8-sig"), ("utf-8", "utf-8")):
            with self.subTest(encoding=encoding):
                resultado = self.parse(registros, encoding=encoding)
                self.assertEqual(resultado["encoding"], esperado)

    def test_quatro_batidas_preenchem_interpretacao(self) -> None:
        resultado = self.parse(
            [
                ("5", "LANA FERNANDA", "2026-07-01 08:03:17"),
                ("5", "LANA FERNANDA", "2026-07-01 14:22:59"),
                ("5", "LANA FERNANDA", "2026-07-01 15:27:54"),
                ("5", "LANA FERNANDA", "2026-07-01 17:08:23"),
            ]
        )
        registro = resultado["registros"][0]

        self.assertEqual(
            registro["interpretacao"],
            {
                "entrada": "08:03",
                "saida_intervalo": "14:22",
                "retorno_intervalo": "15:27",
                "saida": "17:08",
            },
        )
        self.assertEqual(registro["status"], "nao_conferido")
        self.assertEqual(registro["pendencias"], [])
        self.assertTrue(registro["selecionado"])

    def test_duas_batidas_preenchem_apenas_entrada_e_saida(self) -> None:
        registro = self.parse(
            [
                ("5", "LANA FERNANDA", "2026-07-02 08:01:02"),
                ("5", "LANA FERNANDA", "2026-07-02 17:09:58"),
            ]
        )["registros"][0]

        self.assertEqual(registro["interpretacao"]["entrada"], "08:01")
        self.assertEqual(registro["interpretacao"]["saida"], "17:09")
        self.assertIsNone(registro["interpretacao"]["saida_intervalo"])
        self.assertIsNone(registro["interpretacao"]["retorno_intervalo"])
        self.assertEqual(registro["status"], "conferir")
        self.assertIn("Apenas duas batidas encontradas", registro["pendencias"])

    def test_tres_batidas_nao_adivinham_posicao_ausente(self) -> None:
        registro = self.parse(
            [
                ("5", "LANA FERNANDA", "2026-07-03 08:01:02"),
                ("5", "LANA FERNANDA", "2026-07-03 12:03:04"),
                ("5", "LANA FERNANDA", "2026-07-03 17:05:06"),
            ]
        )["registros"][0]

        self.assertTrue(all(valor is None for valor in registro["interpretacao"].values()))
        self.assertEqual(registro["status"], "conferir")
        self.assertIn("Quantidade ímpar de batidas", registro["pendencias"])
        self.assertEqual(len(registro["batidas_originais"]), 3)

    def test_cinco_batidas_preservam_todas_sem_sugestao(self) -> None:
        horarios = ["07:59:01", "10:00:02", "12:00:03", "13:00:04", "17:05:05"]
        registro = self.parse(
            [("5", "LANA FERNANDA", f"2026-07-04 {horario}") for horario in horarios]
        )["registros"][0]

        self.assertEqual(registro["batidas_originais"], horarios)
        self.assertTrue(all(valor is None for valor in registro["interpretacao"].values()))
        self.assertIn("Mais de quatro batidas encontradas", registro["pendencias"])

    def test_funcionario_e_localizado_primeiro_pelo_codigo_exato(self) -> None:
        funcionarios = (
            {"id": 11, "codigo": "5", "nome": "Pessoa Diferente"},
            {"id": 12, "codigo": "6", "nome": "Lana Fernanda"},
        )
        registro = self.parse(
            [("5", "LANA FERNANDA", "2026-07-01 08:03:17")],
            funcionarios=funcionarios,
        )["registros"][0]

        self.assertEqual(registro["funcionario"]["id"], 11)
        self.assertEqual(registro["funcionario"]["nome_cadastrado"], "Pessoa Diferente")
        self.assertTrue(registro["funcionario"]["encontrado"])

    def test_funcionario_e_localizado_por_nome_normalizado(self) -> None:
        funcionarios = ({"id": 13, "codigo": "9", "nome": "Lâna   Fernánda"},)
        registro = self.parse(
            [("999", "  LANA FERNANDA  ", "2026-07-01 08:03:17")],
            funcionarios=funcionarios,
        )["registros"][0]

        self.assertEqual(registro["funcionario"]["id"], 13)
        self.assertTrue(registro["funcionario"]["encontrado"])

    def test_funcionario_nao_encontrado_nao_e_criado_nem_selecionado(self) -> None:
        registro = self.parse(
            [("404", "PESSOA INEXISTENTE", "2026-07-01 08:03:17")],
            funcionarios=(),
        )["registros"][0]

        self.assertIsNone(registro["funcionario"]["id"])
        self.assertFalse(registro["funcionario"]["encontrado"])
        self.assertFalse(registro["selecionado"])
        self.assertIn("Funcionário não cadastrado para esta empresa", registro["pendencias"])

    def test_nome_duplicado_e_ambiguo(self) -> None:
        funcionarios = (
            {"id": 20, "codigo": "1", "nome": "José da Silva"},
            {"id": 21, "codigo": "2", "nome": "JOSE  DA SILVA"},
        )
        registro = self.parse(
            [("999", "Jose da Silva", "2026-07-01 08:03:17")],
            funcionarios=funcionarios,
        )["registros"][0]

        self.assertFalse(registro["funcionario"]["encontrado"])
        self.assertIsNone(registro["funcionario"]["id"])

    def test_data_fora_da_competencia_e_desmarcada(self) -> None:
        registro = self.parse(
            [("5", "LANA FERNANDA", "2026-06-30 07:58:18")]
        )["registros"][0]

        self.assertTrue(registro["fora_da_competencia"])
        self.assertFalse(registro["selecionado"])
        self.assertIn("Data fora da competência selecionada", registro["pendencias"])

    def test_datetime_invalido_gera_erro_legivel(self) -> None:
        conteudo = montar_txt([("5", "LANA FERNANDA", "01/07/2026 08:03")]).encode("utf-8")

        with self.assertRaises(ErroImportacaoTxt) as contexto:
            parse_txt_log_relogio(
                conteudo,
                arquivo_nome="ALOG_TESTE.txt",
                mes=7,
                ano=2026,
            )

        self.assertEqual(contexto.exception.codigo, "datetime_invalido")
        self.assertIn("linha 2", str(contexto.exception))

    def test_txt_sem_colunas_obrigatorias_gera_erro_legivel(self) -> None:
        conteudo = "EnNo\tName\tQuando\n5\tLana\t2026-07-01 08:03:17\n".encode("utf-8")

        with self.assertRaises(ErroImportacaoTxt) as contexto:
            parse_txt_log_relogio(
                conteudo,
                arquivo_nome="ALOG_TESTE.txt",
                mes=7,
                ano=2026,
            )

        self.assertEqual(contexto.exception.codigo, "cabecalho_incompativel")
        self.assertIn("DateTime", str(contexto.exception))

    def test_encoding_nao_reconhecido_gera_erro_legivel(self) -> None:
        with self.assertRaises(ErroImportacaoTxt) as contexto:
            parse_txt_log_relogio(
                b"\xff\xff\xff",
                arquivo_nome="ALOG_TESTE.txt",
                mes=7,
                ano=2026,
            )

        self.assertEqual(contexto.exception.codigo, "encoding_nao_reconhecido")
        self.assertIn("Não foi possível", str(contexto.exception))

    def test_arquivo_vazio_gera_erro_legivel(self) -> None:
        with self.assertRaises(ErroImportacaoTxt) as contexto:
            parse_txt_log_relogio(
                b"",
                arquivo_nome="ALOG_TESTE.txt",
                mes=7,
                ano=2026,
            )

        self.assertEqual(contexto.exception.codigo, "arquivo_vazio")
        self.assertIn("está vazio", str(contexto.exception))

    def test_batidas_sao_ordenadas_e_preservam_segundos(self) -> None:
        registro = self.parse(
            [
                ("5", "LANA FERNANDA", "2026-07-01 17:08:23"),
                ("5", "LANA FERNANDA", "2026-07-01 08:03:17"),
                ("5", "LANA FERNANDA", "2026-07-01 15:27:54"),
                ("5", "LANA FERNANDA", "2026-07-01 14:22:59"),
            ]
        )["registros"][0]

        self.assertEqual(
            registro["batidas_originais"],
            ["08:03:17", "14:22:59", "15:27:54", "17:08:23"],
        )

    def test_aceita_caminho_e_gera_id_deterministico(self) -> None:
        conteudo = montar_txt([("5", "LANA FERNANDA", "2026-07-01 08:03:17")]).encode("utf-8")
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "ALOG_FICTICIO.txt"
            caminho.write_bytes(conteudo)
            primeiro = parse_txt_log_relogio(
                caminho,
                arquivo_nome=caminho.name,
                mes=7,
                ano=2026,
                funcionarios=({"id": 10, "codigo": "5", "nome": "Lana Fernanda"},),
            )
            segundo = parse_txt_log_relogio(
                caminho,
                arquivo_nome=caminho.name,
                mes=7,
                ano=2026,
                funcionarios=({"id": 10, "codigo": "5", "nome": "Lana Fernanda"},),
            )

        self.assertEqual(primeiro["registros"][0]["id"], segundo["registros"][0]["id"])
        self.assertEqual(
            primeiro["registros"][0]["origem"],
            {"tipo": "txt_log_relogio", "arquivo": "ALOG_FICTICIO.txt"},
        )

    def test_id_muda_quando_funcionario_resolvido_muda(self) -> None:
        conteudo = montar_txt([("5", "LANA FERNANDA", "2026-07-01 08:03:17")]).encode("utf-8")
        primeira = parse_txt_log_relogio(
            conteudo,
            arquivo_nome="ALOG_TESTE.txt",
            mes=7,
            ano=2026,
            funcionarios=({"id": 10, "codigo": "5", "nome": "Lana Fernanda"},),
        )
        segunda = parse_txt_log_relogio(
            conteudo,
            arquivo_nome="ALOG_TESTE.txt",
            mes=7,
            ano=2026,
            funcionarios=({"id": 11, "codigo": "5", "nome": "Lana Fernanda"},),
        )

        self.assertNotEqual(primeira["registros"][0]["id"], segunda["registros"][0]["id"])


if __name__ == "__main__":
    unittest.main()
