from __future__ import annotations

import json
import sys
import tempfile
import unittest
from calendar import monthrange
from datetime import date, time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.apuracao.service import apurar_competencia
from app.database.models import Competencia, Empresa, Escala, Funcionario, MarcacaoPonto
from app.database.session import Base
from app.marcacoes.schemas import STATUS_DIA


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

    def criar_contexto(
        self,
        nomes: list[tuple[str, str]],
        *,
        mes: int = 2,
        ano: int = 2026,
        com_escala: bool = True,
        funcionarios_ativos: bool = True,
        modo_apuracao: str = "carga_horaria",
    ) -> tuple[Competencia, Escala | None, list[Funcionario]]:
        empresa = Empresa(nome="Empresa Apuração Fictícia")
        self.db.add(empresa)
        self.db.flush()

        escala = None
        if com_escala:
            escala = Escala(
                empresa_id=empresa.id,
                nome="Padrão",
                modo_apuracao=modo_apuracao,
                jornada_seg_sex_horas=8 if modo_apuracao == "carga_horaria" else None,
                jornada_sabado_horas=4 if modo_apuracao == "carga_horaria" else None,
                horario_entrada_prevista=time(8) if modo_apuracao == "horario_fixo" else None,
                horario_saida_almoco_prevista=(
                    time(12) if modo_apuracao == "horario_fixo" else None
                ),
                horario_retorno_almoco_prevista=(
                    time(13) if modo_apuracao == "horario_fixo" else None
                ),
                horario_saida_prevista=time(17) if modo_apuracao == "horario_fixo" else None,
                regime_sabado="nao_trabalha",
                regime_domingo="nao_trabalha",
                tolerancia_atraso_minutos=5,
                tolerancia_extra_minutos=10,
                tolerancia_intervalo_minutos=10,
            )
            self.db.add(escala)
            self.db.flush()

        competencia = Competencia(empresa_id=empresa.id, mes=mes, ano=ano)
        funcionarios = [
            Funcionario(
                empresa_id=empresa.id,
                escala_id=escala.id if escala else None,
                codigo=codigo,
                nome=nome,
                ativo=funcionarios_ativos,
            )
            for codigo, nome in nomes
        ]
        self.db.add_all([competencia, *funcionarios])
        self.db.commit()
        return competencia, escala, funcionarios

    def test_fevereiro_gera_28_dias_quatro_domingo_e_eh_idempotente(self) -> None:
        competencia, _, (funcionario,) = self.criar_contexto(
            [("F001", "Pessoa Calendário")]
        )

        primeiro = apurar_competencia(self.db, competencia.id)

        self.assertEqual(primeiro["resumo"][0]["dias_processados"], 28)
        self.assertEqual(len(primeiro["marcacoes"]), 28)
        domingos = [item for item in primeiro["marcacoes"] if item["status_dia"] == "domingo"]
        sabados = [
            item for item in primeiro["marcacoes"] if item["status_dia"] == "sem_expediente"
        ]
        uteis = [item for item in primeiro["marcacoes"] if item["status_dia"] == "normal"]
        self.assertEqual([item["data"] for item in domingos], ["2026-02-01", "2026-02-08", "2026-02-15", "2026-02-22"])
        self.assertEqual(len(sabados), 4)
        self.assertEqual(len(uteis), 20)
        self.assertTrue(all(item["conferido"] for item in [*domingos, *sabados]))
        self.assertTrue(all(not item["conferido"] for item in uteis))
        self.assertTrue(all(item["origem"] == "calendario" for item in primeiro["marcacoes"]))
        self.assertEqual(primeiro["resumo"][0]["pendencias"], 20)

        ids_primeira_apuracao = {item["id"] for item in primeiro["marcacoes"]}
        segundo = apurar_competencia(self.db, competencia.id)
        ids_segunda_apuracao = {item["id"] for item in segundo["marcacoes"]}
        self.assertEqual(ids_segunda_apuracao, ids_primeira_apuracao)
        self.assertEqual(
            self.db.query(MarcacaoPonto)
            .filter(
                MarcacaoPonto.competencia_id == competencia.id,
                MarcacaoPonto.funcionario_id == funcionario.id,
            )
            .count(),
            28,
        )

    def test_calendario_preserva_marcacao_importada_existente(self) -> None:
        competencia, _, (funcionario,) = self.criar_contexto(
            [("F002", "Pessoa Importada")]
        )
        batidas = json.dumps(["08:00:00", "12:00:00", "13:00:00", "17:00:00"])
        importada = MarcacaoPonto(
            competencia_id=competencia.id,
            funcionario_id=funcionario.id,
            data=date(2026, 2, 2),
            entrada=time(8),
            saida_almoco=time(12),
            retorno_almoco=time(13),
            saida=time(17),
            status_dia="normal",
            origem="txt_log_relogio",
            conferido=False,
            batidas_originais=batidas,
        )
        self.db.add(importada)
        self.db.commit()
        id_importada = importada.id

        resultado = apurar_competencia(self.db, competencia.id)
        preservada = self.db.get(MarcacaoPonto, id_importada)

        self.assertEqual(len(resultado["marcacoes"]), 28)
        self.assertEqual(preservada.id, id_importada)
        self.assertEqual(preservada.origem, "txt_log_relogio")
        self.assertEqual(preservada.batidas_originais, batidas)
        self.assertEqual(preservada.entrada, time(8))

    def test_normal_nao_conferido_aparece_pendente_sem_invalidar_calculo(self) -> None:
        competencia, _, (funcionario,) = self.criar_contexto(
            [("F003", "Pessoa Não Conferida")]
        )
        ultimo_dia = monthrange(competencia.ano, competencia.mes)[1]
        for dia in range(1, ultimo_dia + 1):
            data_marcacao = date(competencia.ano, competencia.mes, dia)
            if dia == 2:
                marcacao = MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=funcionario.id,
                    data=data_marcacao,
                    entrada=time(8),
                    saida_almoco=time(12),
                    retorno_almoco=time(13),
                    saida=time(17),
                    status_dia="normal",
                    origem="manual",
                    conferido=False,
                )
            else:
                marcacao = MarcacaoPonto(
                    competencia_id=competencia.id,
                    funcionario_id=funcionario.id,
                    data=data_marcacao,
                    status_dia="folga",
                    origem="manual",
                    conferido=True,
                )
            self.db.add(marcacao)
        self.db.commit()

        resultado = apurar_competencia(self.db, competencia.id)
        resumo = resultado["resumo"][0]
        pendencia = resultado["pendencias"][0]

        self.assertEqual(resumo["dias_processados"], 28)
        self.assertEqual(resumo["pendencias"], 1)
        self.assertEqual(resumo["situacao"], "pendente")
        self.assertEqual(resumo["atrasos_minutos"], 0)
        self.assertEqual(resumo["extras_minutos"], 0)
        self.assertFalse(pendencia["pendente_calculo"])
        self.assertTrue(pendencia["pendente_operacional"])
        self.assertEqual(pendencia["pendencia_motivo"], "Registro ainda não conferido.")

    def test_funcionario_sem_escala_gera_calendario_com_pendencia_de_cadastro(self) -> None:
        competencia, _, (funcionario,) = self.criar_contexto(
            [("F004", "Pessoa Sem Escala")],
            com_escala=False,
        )

        resultado = apurar_competencia(self.db, competencia.id)

        self.assertEqual(len(resultado["marcacoes"]), 28)
        self.assertTrue(all(item["status_dia"] == "normal" for item in resultado["marcacoes"]))
        self.assertTrue(all(not item["conferido"] for item in resultado["marcacoes"]))
        self.assertTrue(all(item["pendente_calculo"] for item in resultado["marcacoes"]))
        self.assertTrue(
            all(
                item["pendencia_tipo"] == "escala_nao_cadastrada"
                for item in resultado["marcacoes"]
            )
        )
        self.assertIsNone(resultado["resumo"][0]["atrasos_minutos"])
        self.assertEqual(resultado["resumo"][0]["pendencias"], 28)

        escala = Escala(
            empresa_id=funcionario.empresa_id,
            nome="Escala cadastrada depois",
            modo_apuracao="carga_horaria",
            jornada_seg_sex_horas=8,
            jornada_sabado_horas=None,
            regime_sabado="nao_trabalha",
            regime_domingo="nao_trabalha",
        )
        self.db.add(escala)
        self.db.flush()
        funcionario.escala_id = escala.id
        self.db.commit()

        reprocessado = apurar_competencia(self.db, competencia.id)
        domingos = [
            item for item in reprocessado["marcacoes"] if item["status_dia"] == "domingo"
        ]
        sabados = [
            item
            for item in reprocessado["marcacoes"]
            if item["status_dia"] == "sem_expediente"
        ]
        self.assertEqual(len(domingos), 4)
        self.assertEqual(len(sabados), 4)
        self.assertTrue(all(item["conferido"] for item in [*domingos, *sabados]))
        self.assertEqual(reprocessado["resumo"][0]["pendencias"], 20)
        self.assertEqual(len(reprocessado["marcacoes"]), 28)

    def test_calendario_nao_reclassifica_dia_ja_tocado_pelo_usuario(self) -> None:
        competencia, escala, _ = self.criar_contexto(
            [("F004-B", "Pessoa com Decisão Manual")]
        )
        primeiro = apurar_competencia(self.db, competencia.id)
        domingo = next(
            item for item in primeiro["marcacoes"] if item["data"] == "2026-02-01"
        )
        marcacao = self.db.get(MarcacaoPonto, domingo["id"])
        marcacao.origem = "manual"
        marcacao.status_dia = "falta"
        marcacao.conferido = True
        escala.regime_domingo = "trabalha"
        self.db.commit()

        reprocessado = apurar_competencia(self.db, competencia.id)
        preservado = next(
            item for item in reprocessado["marcacoes"] if item["id"] == marcacao.id
        )
        self.assertEqual(preservado["status_dia"], "falta")
        self.assertTrue(preservado["conferido"])
        self.assertEqual(preservado["origem"], "manual")

    def test_horario_fixo_usa_horarios_e_tolerancias_da_escala(self) -> None:
        competencia, _, (funcionario,) = self.criar_contexto(
            [("F005", "Pessoa Horário Fixo")],
            modo_apuracao="horario_fixo",
        )
        self.db.add(
            MarcacaoPonto(
                competencia_id=competencia.id,
                funcionario_id=funcionario.id,
                data=date(2026, 2, 2),
                entrada=time(8, 6),
                saida_almoco=time(12),
                retorno_almoco=time(13, 15),
                saida=time(17, 21),
                status_dia="normal",
                origem="manual",
                conferido=True,
            )
        )
        self.db.commit()

        resultado = apurar_competencia(
            self.db,
            competencia.id,
            gerar_calendario=False,
        )
        detalhe = resultado["marcacoes"][0]

        self.assertEqual(detalhe["jornada_prevista_minutos"], 480)
        self.assertEqual(detalhe["horas_trabalhadas_minutos"], 480)
        self.assertEqual(detalhe["atraso_minutos"], 21)
        self.assertEqual(detalhe["extra_minutos"], 0)
        self.assertFalse(detalhe["pendente_calculo"])

    def test_funcionario_inativo_sem_marcacoes_permanece_indisponivel(self) -> None:
        competencia, _, _ = self.criar_contexto(
            [("F006", "Pessoa Inativa")],
            funcionarios_ativos=False,
        )

        resultado = apurar_competencia(self.db, competencia.id)

        self.assertEqual(resultado["marcacoes"], [])
        self.assertEqual(resultado["resumo"][0]["dias_processados"], 0)
        self.assertEqual(resultado["resumo"][0]["situacao"], "indisponivel")

    def test_status_dia_expoe_somente_os_nove_motivos(self) -> None:
        self.assertEqual(
            STATUS_DIA,
            {
                "normal",
                "falta",
                "atestado",
                "folga",
                "feriado",
                "domingo",
                "sem_expediente",
                "trabalho_externo",
                "afastamento",
            },
        )

    def test_competencia_inexistente_preserva_retorno_none(self) -> None:
        self.assertIsNone(apurar_competencia(self.db, 999_999))


if __name__ == "__main__":
    unittest.main()
