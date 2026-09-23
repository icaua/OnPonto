from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.importadores import txt_id_tempo_maquina as adaptador
from app.importadores import txt_generico, txt_log_relogio
from app.importadores.deteccao import detectar_adaptadores_txt
from app.importadores.txt_id_tempo_maquina import (
    ErroImportacaoTxtIdTempoMaquina,
    detectar,
    parse_txt_id_tempo_maquina,
)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "relogio_id_tempo_maquina.txt"
FIXTURE_TXT_LOG_RELOGIO = Path(__file__).resolve().parent / "fixtures" / "relogio_ficticio.txt"

CABECALHO = "ID\tNome\tDepart.\tTempo\tNúmero da máquina\t"


def montar_txt(registros: list[tuple[str, str, str]]) -> bytes:
    linhas = [CABECALHO]
    for codigo, nome, tempo in registros:
        linhas.append(f"{codigo}\t{nome}\tNot Set1\t {tempo}\t1")
    return ("\r\n".join(linhas) + "\r\n").encode("utf-8")


class DetectarTests(unittest.TestCase):
    def test_reconhece_a_fixture_real(self) -> None:
        self.assertTrue(detectar(FIXTURE.read_bytes()))

    def test_variantes_confirmadas_usam_apenas_o_adaptador_dedicado(self) -> None:
        for cabecalho in (CABECALHO, "Tra. No.\tNome\tdept.\tTempo\tMáquina No."):
            with self.subTest(cabecalho=cabecalho):
                conteudo = (cabecalho + "\n10\tAna Teste\tSetor\t01/06/2026 08:00:00\t1\n").encode("utf-8")
                self.assertTrue(detectar(conteudo))
                self.assertEqual(detectar_adaptadores_txt(conteudo), [adaptador])
                registro = parse_txt_id_tempo_maquina(
                    conteudo, arquivo_nome="variante.txt", mes=6, ano=2026,
                    funcionarios=({"id": 42, "codigo": "10", "nome": "Ana Teste"},),
                )["registros"][0]
                self.assertEqual(registro["origem"]["tipo"], "txt_id_tempo_maquina")
                self.assertEqual(registro["funcionario"]["id"], 42)
                self.assertEqual(registro["batidas_originais"], ["08:00:00"])

    def test_aliases_plausiveis_com_acentos_pontuacao_e_colunas_reordenadas(self) -> None:
        for cabecalho in ("Data/Hora\tMatrícula\tFuncionário", "Attendance Time\tEmp. ID\tName",
                          "Punch Time\tBadge No.\tColaborador", "Time\tUser ID\tEmployee"):
            with self.subTest(cabecalho=cabecalho):
                conteudo = (cabecalho + "\n01/06/2026 08:00:00\t007\tAna Teste\n").encode("utf-8")
                self.assertTrue(detectar(conteudo))
                self.assertEqual(detectar_adaptadores_txt(conteudo), [adaptador])
                registro = parse_txt_id_tempo_maquina(
                    conteudo, arquivo_nome="aliases.txt", mes=6, ano=2026,
                )["registros"][0]
                self.assertEqual(registro["funcionario"]["codigo_origem"], "007")
                self.assertEqual(registro["funcionario"]["nome_origem"], "Ana Teste")
                self.assertEqual(registro["data"], "2026-06-01")
                self.assertEqual(registro["batidas_originais"], ["08:00:00"])

    def test_falta_de_qualquer_papel_rejeita_cabecalho_e_informa_so_o_ausente(self) -> None:
        colunas = ["Matrícula", "Funcionário", "Data/Hora"]
        valores = ["007", "Ana Teste", "01/06/2026 08:00:00"]
        for ausente, papel in enumerate(("ID", "Nome", "Tempo")):
            with self.subTest(papel=papel):
                cabecalho = "\t".join(c for i, c in enumerate(colunas) if i != ausente)
                linha = "\t".join(v for i, v in enumerate(valores) if i != ausente)
                conteudo = (cabecalho + "\n" + linha + "\n").encode("utf-8")
                self.assertFalse(detectar(conteudo))
                self.assertEqual(detectar_adaptadores_txt(conteudo), [txt_generico] if ausente != 2 else [])
                with self.assertRaises(ErroImportacaoTxtIdTempoMaquina) as contexto:
                    parse_txt_id_tempo_maquina(conteudo, arquivo_nome="incompleto.txt", mes=6, ano=2026)
                self.assertEqual(contexto.exception.codigo, "cabecalho_incompativel")
                self.assertEqual(str(contexto.exception), "Cabeçalho incompatível. Colunas obrigatórias ausentes: " + papel + ".")

    def test_nao_reconhece_o_layout_do_outro_adaptador_txt(self) -> None:
        self.assertFalse(detectar(FIXTURE_TXT_LOG_RELOGIO.read_bytes()))
        self.assertTrue(txt_log_relogio.parse_txt_log_relogio)  # o outro adaptador segue existindo

    def test_aliases_nao_criam_ambiguidade_com_cabecalho_minimo_do_log(self) -> None:
        conteudo = b"EnNo\tName\tDateTime\n007\tAna Teste\t2026-06-01 08:00:00\n"
        self.assertFalse(detectar(conteudo))
        self.assertEqual(detectar_adaptadores_txt(conteudo), [txt_log_relogio])

    def test_nao_reconhece_conteudo_sem_relacao(self) -> None:
        self.assertFalse(detectar(b"qualquer coisa\nsem cabecalho tabulado"))

    def test_nome_do_adaptador(self) -> None:
        self.assertEqual(adaptador.NOME_ADAPTER, "txt_id_tempo_maquina")


class ParseFixtureRealTests(unittest.TestCase):
    def test_arquivo_real_e_interpretado_por_completo(self) -> None:
        resultado = parse_txt_id_tempo_maquina(
            FIXTURE,
            arquivo_nome="relogio_id_tempo_maquina.txt",
            mes=6,
            ano=2026,
            funcionarios=(),
        )
        self.assertEqual(resultado["encoding"], "utf-8")
        self.assertEqual(resultado["total_linhas_validas"], 231)
        self.assertEqual(len(resultado["registros"]), 84)

        registro_quatro_batidas = next(
            item
            for item in resultado["registros"]
            if item["funcionario"]["codigo_origem"] == "1" and item["data"] == "2026-06-01"
        )
        self.assertEqual(
            registro_quatro_batidas["batidas_originais"],
            ["07:12:36", "12:18:10", "13:17:35", "15:51:02"],
        )
        self.assertEqual(registro_quatro_batidas["status"], "nao_conferido")
        self.assertEqual(registro_quatro_batidas["pendencias"], ["Funcionário não cadastrado para esta empresa"])
        self.assertEqual(
            registro_quatro_batidas["interpretacao"],
            {"entrada": "07:12", "saida_intervalo": "12:18", "retorno_intervalo": "13:17", "saida": "15:51"},
        )

        registro_tres_batidas = next(
            item
            for item in resultado["registros"]
            if item["funcionario"]["codigo_origem"] == "3" and item["data"] == "2026-06-01"
        )
        self.assertEqual(registro_tres_batidas["status"], "conferir")
        self.assertTrue(all(valor is None for valor in registro_tres_batidas["interpretacao"].values()))

    def test_funcionario_cadastrado_por_codigo_e_selecionado(self) -> None:
        resultado = parse_txt_id_tempo_maquina(
            FIXTURE,
            arquivo_nome="relogio_id_tempo_maquina.txt",
            mes=6,
            ano=2026,
            funcionarios=({"id": 42, "codigo": "1", "nome": "Vivaldice"},),
        )
        registro = next(
            item
            for item in resultado["registros"]
            if item["funcionario"]["codigo_origem"] == "1" and item["data"] == "2026-06-01"
        )
        self.assertTrue(registro["funcionario"]["encontrado"])
        self.assertEqual(registro["funcionario"]["id"], 42)
        self.assertTrue(registro["selecionado"])


class ParseSinteticoTests(unittest.TestCase):
    def test_quatro_batidas_preenchem_interpretacao(self) -> None:
        conteudo = montar_txt(
            [
                ("10", "TRABALHADORA TESTE", "01/06/2026     08:00:00"),
                ("10", "TRABALHADORA TESTE", "01/06/2026     12:00:00"),
                ("10", "TRABALHADORA TESTE", "01/06/2026     13:00:00"),
                ("10", "TRABALHADORA TESTE", "01/06/2026     17:00:00"),
            ]
        )
        resultado = parse_txt_id_tempo_maquina(
            conteudo, arquivo_nome="teste.txt", mes=6, ano=2026, funcionarios=()
        )
        registro = resultado["registros"][0]
        self.assertEqual(
            registro["interpretacao"],
            {"entrada": "08:00", "saida_intervalo": "12:00", "retorno_intervalo": "13:00", "saida": "17:00"},
        )
        self.assertEqual(registro["status"], "nao_conferido")
        self.assertEqual(registro["pendencias"], ["Funcionário não cadastrado para esta empresa"])

    def test_data_fora_da_competencia_e_desmarcada(self) -> None:
        conteudo = montar_txt([("10", "TRABALHADORA TESTE", "05/05/2026     08:00:00")])
        resultado = parse_txt_id_tempo_maquina(
            conteudo, arquivo_nome="teste.txt", mes=6, ano=2026, funcionarios=()
        )
        registro = resultado["registros"][0]
        self.assertTrue(registro["fora_da_competencia"])
        self.assertFalse(registro["selecionado"])

    def test_encoding_utf16_com_bom_e_suportado(self) -> None:
        conteudo = montar_txt([("10", "TRABALHADORA TESTE", "01/06/2026     08:00:00")])
        resultado = parse_txt_id_tempo_maquina(
            conteudo.decode("utf-8").encode("utf-16"),
            arquivo_nome="teste.txt",
            mes=6,
            ano=2026,
            funcionarios=(),
        )
        self.assertEqual(resultado["encoding"], "utf-16")

    def test_cabecalho_incompativel_gera_erro_legivel(self) -> None:
        conteudo = "EnNo\tName\tQuando\r\n1\tFulano\t2026-06-01 08:00:00\r\n".encode("utf-8")
        with self.assertRaises(ErroImportacaoTxtIdTempoMaquina) as contexto:
            parse_txt_id_tempo_maquina(conteudo, arquivo_nome="teste.txt", mes=6, ano=2026, funcionarios=())
        self.assertEqual(contexto.exception.codigo, "cabecalho_incompativel")

    def test_alias_de_cabecalho_nao_amplia_formato_do_valor_de_tempo(self) -> None:
        for tempo in ("2026-06-01 08:00:00", "01/06/2026 08:00"):
            with self.subTest(tempo=tempo):
                conteudo = ("Matrícula\tNome\tDateTime\n007\tAna Teste\t" + tempo + "\n").encode("utf-8")
                self.assertTrue(detectar(conteudo))
                with self.assertRaises(ErroImportacaoTxtIdTempoMaquina) as contexto:
                    parse_txt_id_tempo_maquina(conteudo, arquivo_nome="tempo.txt", mes=6, ano=2026)
                self.assertEqual(contexto.exception.codigo, "tempo_invalido")

    def test_tempo_invalido_gera_erro_legivel(self) -> None:
        conteudo = (CABECALHO + "\r\n10\tTeste\tNot Set1\t data quebrada\t1\r\n").encode("utf-8")
        with self.assertRaises(ErroImportacaoTxtIdTempoMaquina) as contexto:
            parse_txt_id_tempo_maquina(conteudo, arquivo_nome="teste.txt", mes=6, ano=2026, funcionarios=())
        self.assertEqual(contexto.exception.codigo, "tempo_invalido")

    def test_arquivo_vazio_gera_erro_legivel(self) -> None:
        with self.assertRaises(ErroImportacaoTxtIdTempoMaquina) as contexto:
            parse_txt_id_tempo_maquina(b"", arquivo_nome="teste.txt", mes=6, ano=2026, funcionarios=())
        self.assertEqual(contexto.exception.codigo, "arquivo_vazio")


if __name__ == "__main__":
    unittest.main()
