from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.apuracao.service import apurar_competencia
from app.database.models import ArquivoRecebido, Competencia, Empresa, Funcionario, MarcacaoPonto
from app.database.session import Base


class ApuracaoResumoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="onponto-apuracao-")
        banco = Path(self.temp_dir.name) / "apuracao.test.db"
        self.engine = create_engine(f"sqlite:///{banco}")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def criar_competencia(self, nomes: list[tuple[str, str]]) -> tuple[Competencia, list[Funcionario]]:
        empresa = Empresa(
            nome="Empresa Apuração Fictícia",
            jornada_seg_sex_horas=8,
            jornada_sabado_horas=4,
            tolerancia_atraso_minutos=5,
            tolerancia_extra_minutos=10,
        )
        self.db.add(empresa)
        self.db.flush()

        competencia = Competencia(empresa_id=empresa.id, mes=7, ano=2026)
        funcionarios = [
            Funcionario(empresa_id=empresa.id, codigo=codigo, nome=nome)
            for codigo, nome in nomes
        ]
        self.db.add_all([competencia, *funcionarios])
        self.db.commit()
        return competencia, funcionarios

    def test_resumo_agrega_metricas_situacao_e_totais_gerais(self) -> None:
        competencia, (ana, bia, caio) = self.criar_competencia(
            [
                ("F001", "Ana Fictícia"),
                ("F002", "Bia Fictícia"),
                ("F003", "Caio Fictício"),
            ]
        )
        self.db.add_all(
            [
                MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=ana.id,
                    data=date(2026, 7, 1),
                    entrada=time(8),
                    saida_almoco=time(12),
                    retorno_almoco=time(13),
                    saida=time(18),
                    status_dia="normal",
                    origem="manual",
                    conferido=True,
                ),
                MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=ana.id,
                    data=date(2026, 7, 2),
                    entrada=time(8, 30),
                    saida_almoco=time(12),
                    retorno_almoco=time(13),
                    saida=time(17),
                    status_dia="normal",
                    origem="manual",
                    conferido=True,
                ),
                MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=ana.id,
                    data=date(2026, 7, 3),
                    status_dia="falta",
                    origem="manual",
                    conferido=True,
                ),
                MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=ana.id,
                    data=date(2026, 7, 6),
                    status_dia="atestado",
                    origem="manual",
                    conferido=True,
                ),
                MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=bia.id,
                    data=date(2026, 7, 1),
                    entrada=time(8),
                    saida_almoco=time(12),
                    retorno_almoco=time(13),
                    saida=time(17),
                    status_dia="normal",
                    origem="txt_log_relogio",
                    conferido=False,
                ),
                ArquivoRecebido(
                    competencia_id=competencia.id,
                    nome_original="relogio_ficticio.txt",
                    caminho_arquivo="uploads/relogio_ficticio.txt",
                    tipo_arquivo="txt_log_relogio",
                ),
                ArquivoRecebido(
                    competencia_id=competencia.id,
                    nome_original="documento_ficticio.pdf",
                    caminho_arquivo="uploads/documento_ficticio.pdf",
                    tipo_arquivo="pdf",
                ),
            ]
        )
        self.db.commit()

        resultado = apurar_competencia(self.db, competencia.id)

        self.assertIsNotNone(resultado)
        por_codigo = {item["codigo"]: item for item in resultado["resumo"]}
        self.assertEqual(
            {
                chave: por_codigo["F001"][chave]
                for chave in (
                    "dias_processados",
                    "atrasos_minutos",
                    "extras_minutos",
                    "atrasos",
                    "extras",
                    "faltas",
                    "atestados",
                    "pendencias",
                    "situacao",
                )
            },
            {
                "dias_processados": 4,
                "atrasos_minutos": 30,
                "extras_minutos": 60,
                "atrasos": "00:30",
                "extras": "01:00",
                "faltas": 1,
                "atestados": 1,
                "pendencias": 0,
                "situacao": "conferido",
            },
        )
        self.assertEqual(por_codigo["F002"]["dias_processados"], 1)
        self.assertEqual(por_codigo["F002"]["atrasos"], "00:00")
        self.assertEqual(por_codigo["F002"]["extras"], "00:00")
        self.assertEqual(por_codigo["F002"]["pendencias"], 1)
        self.assertEqual(por_codigo["F002"]["situacao"], "pendente")
        self.assertEqual(
            {
                chave: por_codigo["F003"][chave]
                for chave in (
                    "dias_processados",
                    "atrasos_minutos",
                    "extras_minutos",
                    "atrasos",
                    "extras",
                    "faltas",
                    "atestados",
                    "pendencias",
                    "situacao",
                )
            },
            {
                "dias_processados": 0,
                "atrasos_minutos": None,
                "extras_minutos": None,
                "atrasos": None,
                "extras": None,
                "faltas": None,
                "atestados": None,
                "pendencias": None,
                "situacao": "indisponivel",
            },
        )
        self.assertEqual(
            resultado["resumo_geral"],
            {
                "funcionarios": 3,
                "conferidos": 1,
                "pendentes": 1,
                "dias_com_pendencia": 1,
                "total_arquivos": 2,
            },
        )
        self.assertEqual(len(resultado["marcacoes"]), 5)
        self.assertEqual(len(resultado["pendencias"]), 1)
        self.assertEqual(resultado["pendencias"][0]["funcionario_id"], bia.id)
        self.assertFalse(resultado["pendencias"][0]["pendente_calculo"])
        self.assertTrue(resultado["pendencias"][0]["pendente_operacional"])
        self.assertEqual(
            resultado["pendencias"][0]["pendencia_motivo"],
            "Registro ainda não conferido.",
        )
        self.assertEqual(caio.id, por_codigo["F003"]["funcionario_id"])

    def test_calculo_inseguro_invalida_duracoes_e_pendencias_contam_funcionario_data(self) -> None:
        competencia, (ana, bia) = self.criar_competencia(
            [("P001", "Ana Pendente"), ("P002", "Bia Pendente")]
        )
        self.db.add_all(
            [
                MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=ana.id,
                    data=date(2026, 7, 1),
                    entrada=time(8),
                    saida=time(16),
                    status_dia="normal",
                    origem="manual",
                    conferido=True,
                ),
                MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=ana.id,
                    data=date(2026, 7, 2),
                    entrada=time(8),
                    status_dia="normal",
                    origem="manual",
                    conferido=True,
                ),
                MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=bia.id,
                    data=date(2026, 7, 2),
                    entrada=time(8),
                    saida=time(16),
                    status_dia="normal",
                    origem="manual",
                    conferido=False,
                ),
            ]
        )
        self.db.commit()

        resultado = apurar_competencia(self.db, competencia.id)

        por_codigo = {item["codigo"]: item for item in resultado["resumo"]}
        self.assertEqual(por_codigo["P001"]["dias_processados"], 2)
        self.assertIsNone(por_codigo["P001"]["atrasos_minutos"])
        self.assertIsNone(por_codigo["P001"]["extras_minutos"])
        self.assertIsNone(por_codigo["P001"]["atrasos"])
        self.assertIsNone(por_codigo["P001"]["extras"])
        self.assertEqual(por_codigo["P001"]["faltas"], 0)
        self.assertEqual(por_codigo["P001"]["atestados"], 0)
        self.assertEqual(por_codigo["P001"]["pendencias"], 1)
        self.assertEqual(por_codigo["P001"]["situacao"], "pendente")

        self.assertEqual(por_codigo["P002"]["dias_processados"], 1)
        self.assertEqual(por_codigo["P002"]["atrasos"], "00:00")
        self.assertEqual(por_codigo["P002"]["extras"], "00:00")
        self.assertEqual(por_codigo["P002"]["pendencias"], 1)
        self.assertEqual(por_codigo["P002"]["situacao"], "pendente")
        self.assertEqual(resultado["resumo_geral"]["pendentes"], 2)
        self.assertEqual(resultado["resumo_geral"]["dias_com_pendencia"], 2)

        pendencia_calculo = next(
            item for item in resultado["pendencias"] if item["funcionario_id"] == ana.id
        )
        self.assertTrue(pendencia_calculo["pendente_calculo"])
        self.assertEqual(
            pendencia_calculo["pendencia_motivo"], "Entrada ou saída não informada."
        )

    def test_competencia_sem_marcacoes_retorna_metricas_indisponiveis(self) -> None:
        competencia, _ = self.criar_competencia(
            [("S001", "Pessoa Sem Dados"), ("S002", "Outra Pessoa Sem Dados")]
        )
        self.db.add(
            ArquivoRecebido(
                competencia_id=competencia.id,
                nome_original="arquivo_sem_marcacoes.txt",
                caminho_arquivo="uploads/arquivo_sem_marcacoes.txt",
                tipo_arquivo="txt_log_relogio",
            )
        )
        self.db.commit()

        resultado = apurar_competencia(self.db, competencia.id)

        self.assertEqual(len(resultado["resumo"]), 2)
        for item in resultado["resumo"]:
            self.assertEqual(item["dias_processados"], 0)
            self.assertEqual(item["situacao"], "indisponivel")
            for campo in (
                "atrasos_minutos",
                "extras_minutos",
                "atrasos",
                "extras",
                "faltas",
                "atestados",
                "pendencias",
            ):
                self.assertIsNone(item[campo])
        self.assertEqual(
            resultado["resumo_geral"],
            {
                "funcionarios": 2,
                "conferidos": 0,
                "pendentes": 0,
                "dias_com_pendencia": 0,
                "total_arquivos": 1,
            },
        )
        self.assertEqual(resultado["marcacoes"], [])
        self.assertEqual(resultado["pendencias"], [])

    def test_competencia_inexistente_preserva_retorno_none(self) -> None:
        self.assertIsNone(apurar_competencia(self.db, 999_999))


if __name__ == "__main__":
    unittest.main()
