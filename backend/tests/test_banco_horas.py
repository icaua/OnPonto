import json
import sys
import tempfile
import unittest
from datetime import date, datetime, time
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.models import (Base, Empresa, Escala, Funcionario, Competencia, MarcacaoPonto,
    HistoricoVinculoEscala, LancamentoBancoHoras, CompensacaoBancoHoras)
from app.database.migrations import aplicar_migracoes_compativeis, SCHEMA_VERSION
from app.empresas.schemas import EmpresaUpdate
from app.empresas.routes import atualizar_empresa
from app.escalas.schemas import EscalaCreate, EscalaUpdate
from app.escalas.routes import criar_escala, atualizar
from app.funcionarios.schemas import FuncionarioCreate, FuncionarioUpdate
from app.funcionarios.routes import criar_funcionario, atualizar_funcionario
from app.funcionarios.historico_escalas import escala_no_dia
from app.banco_horas.service import gerar_lancamentos
from app.competencias.routes import fechar_competencia, reabrir_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest


class BancoFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="onponto-banco-")
        self.engine = create_engine("sqlite:///" + (Path(self.temp.name) / "teste.db").as_posix())
        event.listen(self.engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.empresa = Empresa(nome="Empresa banco", prazo_compensacao_banco_horas_dias=90)
        self.db.add(self.empresa); self.db.flush()
        self.escala = Escala(empresa_id=self.empresa.id, nome="Banco", modo_apuracao="horario_fixo",
            horario_entrada_prevista=time(8), horario_saida_almoco_prevista=time(12),
            horario_retorno_almoco_prevista=time(13), horario_saida_prevista=time(17), usa_banco_horas=True)
        self.db.add(self.escala); self.db.commit()
        self.funcionario = criar_funcionario(FuncionarioCreate(empresa_id=self.empresa.id, nome="Pessoa teste",
            escala_id=self.escala.id, data_admissao=date(2026, 1, 1)), self.db)
        self.competencia = Competencia(empresa_id=self.empresa.id, mes=9, ano=2026)
        self.db.add(self.competencia); self.db.commit()

    def lancar(self, natureza="credito", minutos=120, dia=date(2026,9,1), **kwargs):
        from app.banco_horas.politica import vencimento_credito
        dados = dict(funcionario_id=self.funcionario.id, empresa_id=self.empresa.id, natureza=natureza,
            origem="ajuste_manual", minutos=minutos, data_referencia=dia, data_lancamento=dia,
            prazo_compensacao_aplicado_dias=90, observacao="Saldo inicial conferido",
            data_vencimento=vencimento_credito(dia, 90) if natureza == "credito" else None)
        dados.update(kwargs)
        item = LancamentoBancoHoras(**dados)
        self.db.add(item); self.db.flush()
        return item

    def dias(self):
        # Dias sem trabalho explicitamente conferidos; não geram atrasos artificiais.
        from app.apuracao.service import gerar_dias_faltantes
        gerar_dias_faltantes(self.db, self.competencia)
        for m in self.db.query(MarcacaoPonto).filter_by(competencia_id=self.competencia.id):
            m.status_dia = "sem_expediente"; m.conferido = True
            m.observacoes = "Dia conferido sem expediente."
        self.db.commit()

    def batida(self, dia=1, extra=60, atraso=0):
        m = self.db.query(MarcacaoPonto).filter_by(competencia_id=self.competencia.id, data=date(2026,9,dia)).one()
        m.entrada = time(8 + atraso // 60, atraso % 60)
        m.saida_almoco = time(12); m.retorno_almoco = time(13)
        m.saida = time(17 + extra // 60, extra % 60)
        m.status_dia = "normal"; m.conferido = True
        self.db.commit()
        return m

    def fechar(self):
        return fechar_competencia(self.competencia.id, FechamentoCompetenciaRequest(confirmar_pendencias=True), self.db)


class FundacaoBancoTest(BancoFixture, unittest.TestCase):
    def test_prazo_obrigatorio_e_positivo(self):
        for prazo in (0, -1, True, 1.5):
            with self.subTest(prazo=prazo), self.assertRaises(ValidationError):
                EmpresaUpdate(prazo_compensacao_banco_horas_dias=prazo)
        self.empresa.prazo_compensacao_banco_horas_dias = None; self.db.commit()
        with self.assertRaises(HTTPException) as exc:
            criar_escala(EscalaCreate(empresa_id=self.empresa.id, nome="Inválida", jornada_seg_sex_horas=8, usa_banco_horas=True), self.db)
        self.assertEqual(exc.exception.status_code, 422)
        escala = criar_escala(EscalaCreate(empresa_id=self.empresa.id, nome="Sem banco", jornada_seg_sex_horas=8), self.db)
        self.assertFalse(escala.usa_banco_horas)
        with self.assertRaises(HTTPException):
            atualizar(escala.id, EscalaUpdate(usa_banco_horas=True), self.db)

    def test_nao_remove_prazo_com_escala_habilitada(self):
        with self.assertRaises(HTTPException) as exc:
            atualizar_empresa(self.empresa.id, EmpresaUpdate(prazo_compensacao_banco_horas_dias=None), self.db)
        self.assertEqual(exc.exception.status_code, 409)

    def test_troca_registra_historico_e_novo_vinculo_prevalece_no_dia(self):
        antiga = self.escala.id
        nova = criar_escala(EscalaCreate(empresa_id=self.empresa.id, nome="Nova", jornada_seg_sex_horas=6), self.db)
        with patch("app.funcionarios.historico_escalas.hoje_local", return_value=date(2026,9,15)):
            atualizar_funcionario(self.funcionario.id, FuncionarioUpdate(escala_id=nova.id), self.db)
        self.assertEqual(escala_no_dia(self.db, self.funcionario, date(2026,9,14)).id, antiga)
        self.assertEqual(escala_no_dia(self.db, self.funcionario, date(2026,9,15)).id, nova.id)
        self.assertEqual(escala_no_dia(self.db, self.funcionario, date(2026,9,16)).id, nova.id)
        self.assertEqual(self.db.query(HistoricoVinculoEscala).count(), 2)

    def test_migracao_backfill_idempotente_preserva_snapshot(self):
        self.db.query(HistoricoVinculoEscala).delete()
        self.competencia.apuracao_fechada = '{"legado": true}'
        self.competencia.status = "fechada"
        self.db.commit(); self.db.close()
        with self.engine.begin() as c:
            c.exec_driver_sql("DROP TABLE compensacoes_banco_horas")
            c.exec_driver_sql("DROP TABLE lancamentos_banco_horas")
            c.exec_driver_sql("DROP TABLE historico_vinculo_escala")
            c.exec_driver_sql("ALTER TABLE empresas DROP COLUMN prazo_compensacao_banco_horas_dias")
            c.exec_driver_sql("ALTER TABLE empresas DROP COLUMN feriado_entra_banco")
            c.exec_driver_sql("ALTER TABLE escalas DROP COLUMN usa_banco_horas")
            c.exec_driver_sql("ALTER TABLE competencias DROP COLUMN versao_fechamento")
            c.exec_driver_sql("PRAGMA user_version=8")
        aplicar_migracoes_compativeis(self.engine); aplicar_migracoes_compativeis(self.engine)
        self.assertEqual(self.db.query(HistoricoVinculoEscala).count(), 1)
        self.assertFalse(self.db.get(Escala, 1).usa_banco_horas)
        self.assertEqual(self.db.get(Competencia, 1).apuracao_fechada, '{"legado": true}')
        self.assertEqual(self.db.query(LancamentoBancoHoras).count(), 0)
        with self.engine.connect() as c:
            self.assertEqual(c.exec_driver_sql("PRAGMA user_version").scalar_one(), SCHEMA_VERSION)
            self.assertEqual(c.exec_driver_sql("PRAGMA foreign_key_check").all(), [])

    def test_constraints_ledger_impedem_valores_invalidos(self):
        for dados in (dict(minutos=0), dict(minutos=-60), dict(natureza="ajuste_manual"),
                      dict(observacao="  "), dict(observacao=None),
                      dict(prazo_compensacao_aplicado_dias=None), dict(data_vencimento=None),
                      dict(origem="apuracao", competencia_origem_id=self.competencia.id,
                           escala_origem_id=self.escala.id, versao_fechamento=None)):
            with self.subTest(dados=dados), self.assertRaises(IntegrityError):
                self.lancar(**dados)
            self.db.rollback()

    def test_configuracao_concorrente_nao_habilita_banco_sem_prazo(self):
        from concurrent.futures import ThreadPoolExecutor
        self.escala.usa_banco_horas = False
        self.db.commit()
        empresa_id, escala_id = self.empresa.id, self.escala.id
        self.db.close()
        def alterar(ativar):
            with Session(self.engine) as db:
                try:
                    if ativar:
                        atualizar(escala_id, EscalaUpdate(usa_banco_horas=True), db)
                    else:
                        atualizar_empresa(empresa_id, EmpresaUpdate(prazo_compensacao_banco_horas_dias=None), db)
                    return 200
                except HTTPException as exc:
                    return exc.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            respostas = list(pool.map(alterar, (True, False)))
        self.assertEqual(respostas.count(200), 1)
        self.assertTrue(all(r in (200, 409, 422) for r in respostas))
        empresa, escala = self.db.get(Empresa, empresa_id), self.db.get(Escala, escala_id)
        self.assertTrue(not escala.usa_banco_horas or empresa.prazo_compensacao_banco_horas_dias > 0)


class GeracaoBancoTest(BancoFixture, unittest.TestCase):
    def test_credito_debito_diarios_neutros_e_politica_congelada(self):
        self.dias(); self.batida(1, extra=120); self.batida(2, extra=0, atraso=60)
        self.fechar()
        itens = self.db.query(LancamentoBancoHoras).order_by(LancamentoBancoHoras.data_referencia).all()
        self.assertEqual([(i.natureza, i.minutos) for i in itens], [("credito",120),("debito",60)])
        self.assertEqual(itens[0].data_vencimento, date(2026,11,30))
        self.assertIsNone(itens[1].data_vencimento)
        self.assertEqual(itens[0].escala_origem_id, self.escala.id)
        self.assertEqual(itens[0].versao_fechamento, 1)
        self.empresa.prazo_compensacao_banco_horas_dias = 180; self.db.commit()
        self.assertEqual(itens[0].prazo_compensacao_aplicado_dias, 90)
        self.assertEqual(itens[0].data_vencimento, date(2026,11,30))

    def test_sem_banco_nao_gera_lancamentos(self):
        self.escala.usa_banco_horas = False; self.db.commit()
        self.dias(); self.batida(); self.fechar()
        self.assertEqual(self.db.query(LancamentoBancoHoras).count(), 0)

    def test_falha_apos_geracao_reverte_fechamento_e_versao(self):
        self.dias(); self.batida()
        def falhar(db, competencia, resultado):
            gerar_lancamentos(db, competencia, resultado)
            raise RuntimeError("Falha simulada")
        with patch("app.competencias.routes.gerar_lancamentos", side_effect=falhar), self.assertRaises(RuntimeError):
            self.fechar()
        self.assertNotEqual(self.competencia.status, "fechada")
        self.assertEqual(self.competencia.versao_fechamento, 0)
        self.assertIsNone(self.competencia.apuracao_fechada)
        self.assertIsNone(self.competencia.data_fechamento)
        self.assertEqual(self.db.query(LancamentoBancoHoras).count(), 0)

    def test_repeticao_e_concorrencia_nao_duplicam(self):
        from concurrent.futures import ThreadPoolExecutor
        self.dias(); self.batida()
        ident = self.competencia.id; self.db.close()
        def fechar():
            with Session(self.engine) as db:
                try:
                    fechar_competencia(ident, FechamentoCompetenciaRequest(confirmar_pendencias=True), db)
                    return 200
                except HTTPException as exc:
                    return exc.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(lambda _: fechar(), range(2))), [200,409])
        self.assertEqual(fechar(), 409)
        self.assertEqual(self.db.query(LancamentoBancoHoras).count(), 1)
        self.assertEqual(self.db.get(Competencia, ident).versao_fechamento, 1)

    def test_feriado_obedece_configuracao_sem_multiplicar(self):
        from app.database.models import EventoCalendario
        self.dias(); self.batida(1, extra=0)
        self.db.add(EventoCalendario(nome="Feriado", data=date(2026,9,1), tipo="FERIADO",
                                    abrangencia="EMPRESA", empresa_id=self.empresa.id))
        self.db.commit()
        from app.apuracao.service import apurar_competencia
        resultado = apurar_competencia(self.db, self.competencia.id, gerar_calendario=False)
        self.competencia.data_fechamento = date(2026,9,30); self.competencia.versao_fechamento = 1
        self.assertEqual(gerar_lancamentos(self.db, self.competencia, resultado), [])
        self.empresa.feriado_entra_banco = True
        itens = gerar_lancamentos(self.db, self.competencia, resultado)
        self.assertEqual([(i.natureza,i.minutos) for i in itens], [("credito",480)])

    def test_lancamento_usa_historico_sem_mudar_calculo_diario(self):
        self.dias(); self.batida(1); self.batida(16)
        antiga = self.escala.id
        nova = criar_escala(EscalaCreate(empresa_id=self.empresa.id, nome="Nova", jornada_seg_sex_horas=8, usa_banco_horas=True), self.db)
        with patch("app.funcionarios.historico_escalas.hoje_local", return_value=date(2026,9,15)):
            atualizar_funcionario(self.funcionario.id, FuncionarioUpdate(escala_id=nova.id), self.db)
        self.fechar()
        itens = self.db.query(LancamentoBancoHoras).order_by(LancamentoBancoHoras.data_referencia).all()
        self.assertEqual([i.escala_origem_id for i in itens], [antiga, nova.id])


class FifoBancoTest(BancoFixture, unittest.TestCase):
    def reconciliar(self):
        from app.banco_horas.service import reconciliar
        reconciliar(self.db, self.funcionario.id)

    def saldo(self, limite=None):
        from app.banco_horas.service import calcular_saldo_banco_horas
        return calcular_saldo_banco_horas(self.db, self.funcionario.id, limite)

    def pares(self):
        return [(c.credito_id, c.debito_id, c.minutos) for c in self.db.query(CompensacaoBancoHoras)
                .filter_by(status="ativo").order_by(CompensacaoBancoHoras.id)]

    def test_varios_creditos_cobrem_debito_por_vencimento(self):
        a = self.lancar(minutos=120)
        b = self.lancar(minutos=180, data_vencimento=date(2026,9,30))
        d = self.lancar("debito", 200)
        self.reconciliar()
        self.assertEqual(self.pares(), [(b.id,d.id,180),(a.id,d.id,20)])
        self.assertEqual(self.saldo(),100)
        ids = [c.id for c in self.db.query(CompensacaoBancoHoras)]
        self.reconciliar()
        self.assertEqual([c.id for c in self.db.query(CompensacaoBancoHoras)], ids)

    def test_credito_novo_cobre_varios_debitos_mais_antigos(self):
        novo = self.lancar("debito", 60, date(2026,9,3), data_lancamento=date(2026,9,4))
        antigo = self.lancar("debito", 100, date(2026,9,1), data_lancamento=date(2026,9,4))
        credito = self.lancar(minutos=140, dia=date(2026,9,5))
        self.reconciliar()
        self.assertEqual(self.pares(), [(credito.id,antigo.id,100),(credito.id,novo.id,40)])
        self.assertEqual(self.saldo(), -20)

    def test_debito_cobre_credito_e_consulta_passada_ignora_consumo_futuro(self):
        c = self.lancar(minutos=120)
        d = self.lancar("debito", 60, date(2026,9,10))
        self.reconciliar()
        self.assertEqual(self.pares(), [(c.id,d.id,60)])
        self.assertEqual(self.saldo(date(2026,9,1)), 120)
        self.assertEqual(self.saldo(), 60)

    def test_vencidos_alertados_e_ainda_compensaveis(self):
        from app.banco_horas.service import alertas
        c = self.lancar(minutos=120, data_vencimento=date(2026,9,2))
        self.lancar(minutos=60, data_vencimento=date(2026,9,25))
        aviso = alertas(self.db, self.empresa.id, hoje=date(2026,9,22))
        self.assertEqual(aviso["vencidos"][0]["minutos_restantes"], 120)
        self.assertEqual(len(aviso["proximos_do_vencimento"]), 1)
        d = self.lancar("debito", 120, date(2026,9,22)); self.reconciliar()
        self.assertEqual(self.pares(), [(c.id,d.id,120)])
        self.assertEqual(alertas(self.db, self.empresa.id, hoje=date(2026,9,22))["vencidos"], [])

    def test_ajustes_exigem_motivo_e_estorno_preserva_historico(self):
        from app.banco_horas.schemas import AjusteCreate, EstornoRequest
        from app.banco_horas.routes import ajustar, estornar
        for motivo in ("", "   "):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError):
                AjusteCreate(funcionario_id=self.funcionario.id, natureza="credito", minutos=60,
                            data_referencia=date(2026,9,1), observacao=motivo)
        a = ajustar(AjusteCreate(funcionario_id=self.funcionario.id, natureza="credito", minutos=120,
                    data_referencia=date(2026,9,1), observacao="Conferência inicial"), self.db)
        ajustar(AjusteCreate(funcionario_id=self.funcionario.id, natureza="debito", minutos=30,
                    data_referencia=date(2026,9,2), observacao="Correção documentada"), self.db)
        self.assertEqual(self.saldo(), 90)
        estornar(a["id"], EstornoRequest(motivo="Crédito registrado em duplicidade"), self.db)
        self.assertEqual(self.saldo(), -30)
        self.assertEqual(self.db.query(LancamentoBancoHoras).count(), 2)
        self.assertEqual(self.db.query(CompensacaoBancoHoras).filter_by(status="estornado").count(), 1)

    def test_desativacao_bloqueia_saldos_individuais_positivos_e_negativos(self):
        for natureza in ("credito", "debito"):
            with self.subTest(natureza=natureza):
                self.lancar(natureza, 60); self.db.commit()
                with self.assertRaises(HTTPException) as exc:
                    atualizar(self.escala.id, EscalaUpdate(usa_banco_horas=False), self.db)
                self.assertEqual(exc.exception.status_code,409)
                self.db.rollback()
                self.db.query(LancamentoBancoHoras).delete(); self.db.commit()
        atualizar(self.escala.id, EscalaUpdate(usa_banco_horas=False), self.db)
        self.assertFalse(self.escala.usa_banco_horas)

    def test_funcionarios_com_saldos_opostos_nao_se_anulam_na_desativacao(self):
        outra = criar_funcionario(FuncionarioCreate(empresa_id=self.empresa.id, nome="Outra pessoa", escala_id=self.escala.id), self.db)
        self.lancar(minutos=60)
        self.lancar("debito",60,funcionario_id=outra.id); self.db.commit()
        with self.assertRaises(HTTPException) as exc:
            atualizar(self.escala.id, EscalaUpdate(usa_banco_horas=False), self.db)
        self.assertEqual(exc.exception.status_code,409)


class ReaberturaBancoTest(BancoFixture, unittest.TestCase):
    def test_reabre_estorna_reconstroi_e_refecha_sem_duplicar(self):
        from app.banco_horas.service import reconciliar, calcular_saldo_banco_horas
        self.dias(); self.batida(extra=120); self.fechar()
        antigo = self.db.query(LancamentoBancoHoras).one()
        debito = self.lancar("debito", 90, date(2026,10,1))
        reconciliar(self.db, self.funcionario.id); self.db.commit()
        compensacao_antiga = self.db.query(CompensacaoBancoHoras).one()
        reabrir_competencia(self.competencia.id, self.db)
        self.assertEqual(antigo.status, "estornado")
        self.assertIsNotNone(antigo.estornado_em)
        self.assertEqual(compensacao_antiga.status, "estornado")
        self.assertIsNotNone(compensacao_antiga.estornada_em)
        self.assertEqual(calcular_saldo_banco_horas(self.db,self.funcionario.id), -90)
        self.batida(extra=60); self.fechar()
        self.assertEqual(self.competencia.versao_fechamento, 2)
        novo = self.db.query(LancamentoBancoHoras).filter_by(origem="apuracao",status="ativo").one()
        self.assertEqual(novo.minutos,60)
        self.assertEqual(novo.versao_fechamento,2)
        ativa = self.db.query(CompensacaoBancoHoras).filter_by(status="ativo").one()
        self.assertEqual((ativa.credito_id,ativa.debito_id,ativa.minutos),(novo.id,debito.id,60))
        self.assertEqual(calcular_saldo_banco_horas(self.db,self.funcionario.id), -30)
        self.assertEqual(self.db.query(LancamentoBancoHoras).filter_by(origem="apuracao").count(),2)

    def test_falha_reabertura_reverte_estornos_e_snapshot(self):
        from app.banco_horas.service import estornar_competencia
        self.dias(); self.batida(); self.fechar()
        snapshot = self.competencia.apuracao_fechada
        def falhar(db, competencia):
            estornar_competencia(db, competencia)
            raise RuntimeError("Falha após estorno")
        with patch("app.competencias.routes.estornar_competencia",side_effect=falhar), self.assertRaises(RuntimeError):
            reabrir_competencia(self.competencia.id,self.db)
        self.assertEqual(self.competencia.status,"fechada")
        self.assertEqual(self.competencia.apuracao_fechada,snapshot)
        self.assertEqual(self.db.query(LancamentoBancoHoras).one().status,"ativo")

    def test_falha_fifo_reverte_lancamentos_e_compensacoes(self):
        from app.banco_horas.service import reconciliar
        self.lancar("debito",30); self.db.commit()
        self.dias(); self.batida()
        def falhar(db, funcionario_id, motivo):
            reconciliar(db, funcionario_id, motivo)
            raise RuntimeError("Falha após FIFO")
        with patch("app.competencias.routes.reconciliar",side_effect=falhar), self.assertRaises(RuntimeError):
            self.fechar()
        self.assertEqual(self.db.query(LancamentoBancoHoras).count(),1)
        self.assertEqual(self.db.query(CompensacaoBancoHoras).count(),0)
        self.assertEqual(self.competencia.versao_fechamento,0)


class FolgaBancoTest(BancoFixture, unittest.TestCase):
    def folga(self, **kwargs):
        from app.ocorrencias.routes import criar
        from app.ocorrencias.schemas import OcorrenciaCreate
        dados = dict(funcionario_id=self.funcionario.id, tipo="FOLGA_COMPENSATORIA",
                     data_inicio=date(2026,9,10), data_fim=date(2026,9,10))
        dados.update(kwargs)
        return criar(OcorrenciaCreate(**dados), self.db)

    def test_integral_gera_debito_explicito_sem_falta_ou_atraso(self):
        from app.apuracao.service import apurar_competencia
        self.dias(); self.lancar(minutos=480, dia=date(2026,8,1)); self.db.commit()
        self.folga()
        dia = next(d for d in apurar_competencia(self.db,self.competencia.id)["marcacoes"] if d["data"] == "2026-09-10")
        self.assertEqual((dia["falta"],dia["atraso_minutos"],dia["minutos_folga_compensatoria"]),(0,0,480))
        self.assertEqual(dia["status_dia"],"folga_compensatoria")
        self.fechar()
        debito = self.db.query(LancamentoBancoHoras).filter_by(origem="folga_compensatoria").one()
        self.assertEqual((debito.natureza,debito.minutos),("debito",480))
        self.assertEqual(self.db.query(CompensacaoBancoHoras).one().minutos,480)

    def test_parcial_usa_apenas_ausencia_coberta(self):
        self.dias(); self.lancar(minutos=240, dia=date(2026,8,1)); self.db.commit()
        m = self.batida(10,extra=0)
        m.saida_almoco=None; m.retorno_almoco=None; m.saida=time(12); self.db.commit()
        self.folga(hora_inicio=time(13),hora_fim=time(17))
        self.fechar()
        d = next(d for d in json.loads(self.competencia.apuracao_fechada)["marcacoes"] if d["data"] == "2026-09-10")
        self.assertEqual((d["falta"],d["atraso_minutos"],d["minutos_folga_compensatoria"]),(0,0,240))
        self.assertFalse(d["pendente_calculo"])
        self.assertEqual(self.db.query(LancamentoBancoHoras).filter_by(origem="folga_compensatoria").one().minutos,240)

    def test_insuficiente_nao_cria_ocorrencia_nem_divida(self):
        from app.database.models import OcorrenciaFuncionario
        self.dias(); self.lancar(minutos=300); self.db.commit()
        with self.assertRaises(HTTPException) as exc:
            self.folga()
        self.assertEqual(exc.exception.status_code,409)
        self.assertIn("Saldo insuficiente",exc.exception.detail)
        self.assertEqual(self.db.query(OcorrenciaFuncionario).count(),0)
        self.assertEqual(self.db.query(LancamentoBancoHoras).filter_by(natureza="debito").count(),0)

    def test_reservas_impedem_duas_folgas_usarem_mesmo_saldo(self):
        self.dias(); self.lancar(minutos=480); self.db.commit(); self.folga()
        with self.assertRaises(HTTPException) as exc:
            self.folga(data_inicio=date(2026,9,11),data_fim=date(2026,9,11))
        self.assertEqual(exc.exception.status_code,409)

    def test_fechamento_revalida_saldo_apos_ajuste_estornado(self):
        from app.banco_horas.service import estornar_ajuste
        self.dias(); credito = self.lancar(minutos=480); self.db.commit(); self.folga()
        estornar_ajuste(self.db,credito.id,"Revisão do crédito"); self.db.commit()
        with self.assertRaises(HTTPException) as exc:
            self.fechar()
        self.assertIn("Saldo insuficiente",exc.exception.detail)
        self.assertNotEqual(self.competencia.status,"fechada")
        self.assertEqual(self.competencia.versao_fechamento,0)
        self.assertEqual(self.db.query(LancamentoBancoHoras).filter_by(natureza="debito").count(),0)

    def test_sem_banco_folga_e_rejeitada(self):
        self.escala.usa_banco_horas=False; self.db.commit()
        with self.assertRaises(HTTPException) as exc:
            self.folga()
        self.assertIn("escala com banco",exc.exception.detail)


class ConsultaBancoTest(BancoFixture, unittest.TestCase):
    def test_resumo_espelho_e_desligamento_usam_ledger(self):
        from app.apuracao.service import apurar_competencia
        from app.relatorios.routes import espelho_ponto
        self.lancar(minutos=120,dia=date(2026,8,1)); self.db.commit()
        self.dias(); self.batida(extra=60)
        self.funcionario.data_demissao=date(2026,9,10); self.db.commit()
        self.fechar()
        resultado=apurar_competencia(self.db,self.competencia.id)
        banco=resultado["resumo"][0]["banco_horas"]
        self.assertEqual((banco["saldo_anterior_minutos"],banco["creditos_competencia_minutos"],banco["debitos_competencia_minutos"],banco["saldo_final_minutos"]),(120,60,0,180))
        self.assertEqual(banco["saldo_demissao_minutos"],180)
        html=espelho_ponto(self.competencia.id,self.funcionario.id,self.db).body.decode()
        self.assertIn("Saldo do banco de horas ao final da competência",html)
        self.assertIn("na data do desligamento",html)
        self.assertIn("+03:00",html)

    def test_ledger_atualizado_na_consulta_sem_modificar_snapshot(self):
        from app.apuracao.service import apurar_competencia
        from app.banco_horas.service import estornar_ajuste
        credito=self.lancar(minutos=120,dia=date(2026,8,1)); self.db.commit()
        self.dias(); self.batida(); self.fechar()
        snapshot=self.competencia.apuracao_fechada
        estornar_ajuste(self.db,credito.id,"Revisão documentada");self.db.commit()
        resultado=apurar_competencia(self.db,self.competencia.id)
        self.assertEqual(resultado["resumo"][0]["banco_horas"]["saldo_final_minutos"],60)
        self.assertEqual(self.competencia.apuracao_fechada,snapshot)
        self.assertEqual(resultado["marcacoes"],json.loads(snapshot)["marcacoes"])

    def test_sem_banco_e_fechamento_legado_nao_recebem_bloco(self):
        from app.apuracao.service import apurar_competencia
        self.escala.usa_banco_horas=False; self.db.commit(); self.dias();self.fechar()
        self.assertNotIn("banco_horas",apurar_competencia(self.db,self.competencia.id)["resumo"][0])
        self.escala.usa_banco_horas=True; self.competencia.versao_fechamento=0;self.db.commit()
        self.assertNotIn("banco_horas",apurar_competencia(self.db,self.competencia.id)["resumo"][0])

    def test_pendencia_de_calculo_bloqueia_banco_mesmo_com_fechamento_excepcional(self):
        self.dias()
        m=self.batida();m.saida=None;self.db.commit()
        with self.assertRaises(HTTPException) as exc:self.fechar()
        self.assertIn("pendência de cálculo",exc.exception.detail)
        self.assertEqual(self.db.query(LancamentoBancoHoras).count(),0)
