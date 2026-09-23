import json
import sys
import tempfile
import unittest
from datetime import date, time
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.models import Base, Empresa, Funcionario, Escala, Competencia, MarcacaoPonto, OcorrenciaFuncionario
from app.database.migrations import SCHEMA_VERSION, aplicar_migracoes_compativeis
from app.ocorrencias.schemas import OcorrenciaCreate, OcorrenciaUpdate
from app.ocorrencias.routes import criar, editar, excluir, listar, historico, anexar, baixar_anexo
from app.apuracao.service import apurar_competencia, detalhe_marcacao
from app.ocorrencias.interpretacao import aplicar_ocorrencias
from app.competencias.routes import fechar_competencia, reabrir_competencia
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.relatorios.routes import relatorio_impressao


class OcorrenciasTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="onponto-ocorrencias-")
        self.engine = create_engine("sqlite:///" + (Path(self.temp.name) / "teste.db").as_posix())
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.empresa = Empresa(nome="Empresa fictícia")
        self.db.add(self.empresa); self.db.flush()
        self.escala = Escala(empresa_id=self.empresa.id, nome="Horário fixo", modo_apuracao="horario_fixo",
            horario_entrada_prevista=time(8), horario_saida_almoco_prevista=time(12),
            horario_retorno_almoco_prevista=time(13), horario_saida_prevista=time(17))
        self.db.add(self.escala); self.db.flush()
        self.funcionario = Funcionario(empresa_id=self.empresa.id, nome="Pessoa fictícia", escala_id=self.escala.id)
        self.competencia = Competencia(empresa_id=self.empresa.id, mes=9, ano=2026)
        self.db.add_all([self.funcionario, self.competencia]); self.db.commit()

    def dados(self, **kwargs):
        base = dict(funcionario_id=self.funcionario.id, tipo="ATESTADO", data_inicio="2026-09-10", data_fim="2026-09-10")
        base.update(kwargs)
        return OcorrenciaCreate.model_validate(base)

    def registrar(self, **kwargs):
        return criar(self.dados(**kwargs), self.db)

    def dia(self, data="2026-09-10"):
        result = apurar_competencia(self.db, self.competencia.id)
        return next(d for d in result["marcacoes"] if d["data"] == data)

    def batidas(self, **kwargs):
        base = dict(competencia_id=self.competencia.id, funcionario_id=self.funcionario.id, data=date(2026,9,10),
            entrada=time(8), saida_almoco=time(12), retorno_almoco=time(15), saida=time(17),
            batidas_originais='["08:00:01", "12:00:02", "15:00:03", "17:00:04"]', status_dia="normal", conferido=True)
        base.update(kwargs)
        registro = MarcacaoPonto(**base); self.db.add(registro); self.db.commit()
        return registro

    def fechar(self):
        fechar_competencia(self.competencia.id, FechamentoCompetenciaRequest(confirmar_pendencias=True), self.db)

    def test_crud_quatro_tipos_e_filtros(self):
        for index, tipo in enumerate(("ATESTADO","DECLARACAO","FERIAS","AFASTAMENTO")):
            with self.subTest(tipo=tipo):
                dia = f"2026-09-{10+index}"
                o = self.registrar(tipo=tipo, data_inicio=dia, data_fim=dia,
                    hora_inicio="13:00" if tipo == "DECLARACAO" else None, hora_fim="15:00" if tipo == "DECLARACAO" else None)
                editar(o.id, OcorrenciaUpdate(observacao="Atualizada"), self.db)
                self.assertEqual(o.observacao, "Atualizada")
        self.assertEqual(len(listar(funcionario_id=self.funcionario.id, db=self.db)), 4)
        self.assertEqual(len(listar(data_inicio=date(2026,9,11),data_fim=date(2026,9,12),db=self.db)), 2)
        self.assertEqual(len(listar(competencia_id=self.competencia.id,db=self.db)), 4)
        excluir(o.id, self.db)
        self.assertEqual(len(listar(db=self.db)), 3)
        self.assertEqual(len(listar(incluir_excluidas=True,db=self.db)), 4)

    def test_validacoes_de_data_horas_e_campos_por_tipo(self):
        invalidos = [dict(data_fim="2026-09-09"),dict(data_fim=None),
            dict(tipo="DECLARACAO"),dict(hora_inicio="13:00",hora_fim="12:00"),
            dict(hora_inicio="13:00",hora_fim="13:00"),dict(hora_inicio="13:00"),
            dict(hora_inicio="13:00",hora_fim="14:00",data_fim="2026-09-11"),
            dict(tipo="FERIAS",hora_inicio="13:00",hora_fim="14:00")]
        for kwargs in invalidos:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError): self.dados(**kwargs)

    def test_funcionario_inexistente(self):
        with self.assertRaises(HTTPException) as exc: criar(self.dados(funcionario_id=999999), self.db)
        self.assertEqual(exc.exception.status_code, 404)

    def test_afastamento_aberto_incluido_em_periodo_futuro(self):
        self.registrar(tipo="AFASTAMENTO",data_fim=None)
        self.assertEqual(len(listar(data_inicio=date(2027,1,1),data_fim=date(2027,1,31),db=self.db)),1)

    def test_sobreposicao_integral_bloqueada(self):
        self.registrar(tipo="FERIAS", data_fim="2026-09-20")
        for tipo in ("ATESTADO", "AFASTAMENTO"):
            with self.subTest(tipo=tipo), self.assertRaises(HTTPException): self.registrar(tipo=tipo)
            self.db.rollback()

    def test_afastamentos_simultaneos_bloqueados(self):
        self.registrar(tipo="AFASTAMENTO",data_fim=None)
        with self.assertRaises(HTTPException): self.registrar(tipo="AFASTAMENTO",data_inicio="2026-10-01",data_fim=None)

    def test_parciais_adjacentes_permitidas_sobrepostas_bloqueadas(self):
        self.registrar(tipo="DECLARACAO",hora_inicio="13:00",hora_fim="14:00")
        self.registrar(tipo="DECLARACAO",hora_inicio="14:00",hora_fim="15:00")
        with self.assertRaises(HTTPException): self.registrar(tipo="DECLARACAO",hora_inicio="13:30",hora_fim="14:30")

    def test_patch_valida_estado_completo_e_sobreposicao(self):
        a = self.registrar(); b = self.registrar(data_inicio="2026-09-11",data_fim="2026-09-11")
        with self.assertRaises(HTTPException): editar(b.id,OcorrenciaUpdate(data_inicio=date(2026,9,10)),self.db)
        self.db.rollback()
        self.assertEqual(b.data_inicio, date(2026,9,11))
        with self.assertRaises(HTTPException): editar(a.id,OcorrenciaUpdate(data_fim=date(2026,9,9)),self.db)

    def test_fechada_bloqueia_criacao_edicao_exclusao(self):
        o = self.registrar(); self.fechar()
        snapshot = self.competencia.apuracao_fechada
        for operacao in (lambda:self.registrar(data_inicio="2026-09-12",data_fim="2026-09-12"),
                         lambda:editar(o.id,OcorrenciaUpdate(observacao="Não"),self.db),lambda:excluir(o.id,self.db)):
            with self.assertRaises(HTTPException) as exc: operacao()
            self.assertEqual(exc.exception.status_code,409); self.db.rollback()
        self.assertEqual(self.competencia.apuracao_fechada,snapshot)

    def test_edicao_para_fechada_e_afastamento_aberto_bloqueados(self):
        o = self.registrar(data_inicio="2026-08-01",data_fim="2026-08-01")
        self.fechar()
        with self.assertRaises(HTTPException): editar(o.id,OcorrenciaUpdate(data_fim=date(2026,9,1)),self.db)
        self.db.rollback()
        with self.assertRaises(HTTPException): self.registrar(tipo="AFASTAMENTO",data_inicio="2026-08-01",data_fim=None)

    def test_reabertura_permite_excluir_e_recalcular(self):
        o=self.registrar(tipo="FERIAS"); self.fechar()
        reabrir_competencia(self.competencia.id,self.db)
        excluir(o.id,self.db)
        self.assertEqual(self.dia()["ocorrencias"],[])

    def test_integrais_sem_falta_atraso_ou_jornada_exigida(self):
        for index,tipo in enumerate(("FERIAS","AFASTAMENTO","ATESTADO")):
            dia=f"2026-09-{10+index}"
            self.registrar(tipo=tipo,data_inicio=dia,data_fim=dia)
            d=self.dia(dia)
            self.assertEqual((d["falta"],d["atraso_minutos"],d["jornada_exigida_minutos"]),(0,0,0))
            self.assertEqual(d["status_dia"],tipo.lower())
            self.assertFalse(d["pendente_calculo"])
            self.assertIsNone(d["entrada"])

    def test_integral_sobre_falta_manual_sem_mudar_marcacao(self):
        r=self.batidas(entrada=None,saida_almoco=None,retorno_almoco=None,saida=None,status_dia="falta")
        self.registrar(tipo="FERIAS")
        self.assertEqual(self.dia()["falta"],0)
        self.assertEqual(r.status_dia,"falta")

    def test_integral_com_batidas_exige_revisao(self):
        self.batidas(); self.registrar(tipo="FERIAS")
        d=self.dia(); self.assertTrue(d["pendente_calculo"]); self.assertEqual(d["atraso_minutos"],0)

    def test_declaracao_abona_so_ausencia_coberta(self):
        r=self.batidas(); original=r.batidas_originais
        self.registrar(tipo="DECLARACAO",hora_inicio="13:00",hora_fim="15:00")
        d=self.dia()
        self.assertEqual((d["minutos_abonados"],d["atraso_minutos"],d["horas_trabalhadas_minutos"],d["extra_minutos"]),(120,0,360,0))
        self.assertEqual(r.batidas_originais,original); self.assertEqual(r.retorno_almoco,time(15))

    def test_abono_parcial_nao_zera_restante_da_ausencia(self):
        self.batidas(); self.registrar(tipo="DECLARACAO",hora_inicio="13:30",hora_fim="14:30")
        d=self.dia(); self.assertEqual((d["minutos_abonados"],d["atraso_minutos"]),(60,60))

    def test_atestado_parcial_mesma_regra(self):
        self.batidas(); self.registrar(hora_inicio="13:00",hora_fim="15:00")
        self.assertEqual(self.dia()["minutos_abonados"],120)

    def test_atestado_parcial_reconcilia_horario_fixo_com_batidas_so_de_manha(self):
        registro = self.batidas(saida_almoco=None, retorno_almoco=None, saida=time(12),
                                batidas_originais='["08:00:01", "12:00:02"]')
        ocorrencia = self.registrar(hora_inicio="13:00", hora_fim="17:00")
        for conferido in (True, False):
            for inicio, abono, atraso in ((13, 240, 0), (14, 180, 60)):
                with self.subTest(conferido=conferido, inicio=inicio):
                    registro.conferido = conferido
                    ocorrencia.hora_inicio = time(inicio)
                    self.db.commit()
                    antes = detalhe_marcacao(self.funcionario, registro)
                    self.assertTrue(antes["pendente_calculo"])
                    self.assertEqual(antes["pendencia_tipo"], "horario_fixo_incompleto")
                    d = self.dia()
                    self.assertFalse(d["pendente_calculo"])
                    self.assertIsNone(d["pendencia_tipo"])
                    self.assertEqual(d["pendente"], not conferido)
                    self.assertEqual(d["pendente_operacional"], not conferido)
                    self.assertEqual(d["pendencia_motivo"], None if conferido else "Registro ainda não conferido.")
                    self.assertEqual((d["minutos_abonados"], d["atraso_minutos"]), (abono, atraso))
                    self.assertEqual(d["atraso"], "00:00" if atraso == 0 else "01:00")
                    self.assertEqual(d["jornada_exigida_minutos"], 480 - abono)
                    self.assertEqual((d["horas_trabalhadas_minutos"], d["extra_minutos"], d["falta"]), (240, 0, 0))
                    self.assertEqual(registro.batidas_originais, '["08:00:01", "12:00:02"]')
                    self.assertIsNone(registro.saida_almoco)
                    self.assertIsNone(registro.retorno_almoco)

    def test_abono_parcial_nao_limpa_pendencias_de_outras_origens(self):
        registro = self.batidas()
        ocorrencia = self.registrar(hora_inicio="13:00", hora_fim="15:00")
        for tipo in ("escala_nao_cadastrada", "escala_incompleta", "ocorrencia_requer_revisao"):
            with self.subTest(tipo=tipo):
                detalhe = detalhe_marcacao(self.funcionario, registro)
                pendencia_original = dict(pendente=True, pendente_calculo=True, pendente_operacional=True,
                                         pendencia_tipo=tipo, pendencia_motivo="Pendência de outra origem.")
                detalhe.update(pendencia_original)
                aplicar_ocorrencias(detalhe, self.funcionario, registro, [ocorrencia])
                self.assertEqual(detalhe["minutos_abonados"], 120)
                self.assertEqual({chave: detalhe[chave] for chave in pendencia_original}, pendencia_original)

    def test_ocorrencia_sem_ausencia_coberta_preserva_pendencia_de_horario_fixo(self):
        self.batidas(saida_almoco=None, retorno_almoco=None, saida=time(12))
        self.registrar(hora_inicio="08:00", hora_fim="12:00")
        d = self.dia()
        self.assertTrue(d["pendente_calculo"])
        self.assertEqual(d["pendencia_tipo"], "horario_fixo_incompleto")
        self.assertEqual(d["minutos_abonados"], 0)

    def test_abono_parcial_preserva_revisao_de_situacao_manual(self):
        self.batidas(status_dia="falta")
        self.registrar(hora_inicio="13:00", hora_fim="15:00")
        d = self.dia()
        self.assertEqual(d["minutos_abonados"], 120)
        self.assertTrue(d["pendente_calculo"])
        self.assertEqual(d["pendencia_tipo"], "ocorrencia_requer_revisao")
        self.assertIn("situação manual diferente de normal", d["pendencia_motivo"])

    def test_sem_abono_de_almoco_ou_tempo_ja_trabalhado(self):
        self.batidas(); self.registrar(tipo="DECLARACAO",hora_inicio="11:00",hora_fim="13:30")
        d=self.dia(); self.assertEqual((d["minutos_abonados"],d["atraso_minutos"]),(30,90))

    def test_carga_horaria_sem_horario_fixo_fica_pendente(self):
        self.escala.modo_apuracao="carga_horaria"; self.escala.jornada_seg_sex_horas=8; self.db.commit()
        self.batidas(); self.registrar(tipo="DECLARACAO",hora_inicio="13:00",hora_fim="15:00")
        d = self.dia()
        self.assertEqual(d["pendencia_tipo"], "ocorrencia_requer_revisao")
        self.assertTrue(d["pendente_calculo"])
        self.assertIn("Abono parcial exige escala com horário fixo", d["pendencia_motivo"])

    def test_batidas_incompletas_nao_sao_inventadas(self):
        self.registrar(tipo="DECLARACAO",hora_inicio="13:00",hora_fim="15:00")
        d=self.dia(); self.assertTrue(d["pendente_calculo"]); self.assertIsNone(d["entrada"])

    def test_fora_da_competencia_nao_altera_apuracao(self):
        self.batidas(); antes=self.dia()
        self.registrar(tipo="FERIAS",data_inicio="2026-10-01",data_fim="2026-10-31")
        self.assertEqual(self.dia(),antes)

    def test_snapshot_fechado_estavel_com_novas_ocorrencias_futuras(self):
        self.registrar(tipo="FERIAS"); self.fechar(); antes=apurar_competencia(self.db,self.competencia.id)
        self.registrar(tipo="AFASTAMENTO",data_inicio="2026-10-01",data_fim=None)
        self.assertEqual(apurar_competencia(self.db,self.competencia.id),antes)

    def test_persistencia_e_auditoria_apos_exclusao(self):
        o=self.registrar(); ident=o.id
        editar(ident,OcorrenciaUpdate(observacao="Atualizado"),self.db); excluir(ident,self.db)
        with Session(self.engine) as outra:
            eventos=historico(ident,outra)
            self.assertEqual([e["acao"] for e in eventos],["criacao","alteracao","exclusao"])
            self.assertEqual(eventos[1]["depois"]["observacao"],"Atualizado")
            self.assertEqual(eventos[1]["antes"]["observacao"],None)
            self.assertIsNotNone(outra.get(OcorrenciaFuncionario,ident).excluido_em)

    def test_migracao_v4_idempotente_preserva_dados(self):
        self.db.close()
        with self.engine.begin() as c:
            c.exec_driver_sql("DROP TABLE ocorrencias_funcionario")
            c.exec_driver_sql("PRAGMA user_version=4")
        aplicar_migracoes_compativeis(self.engine); aplicar_migracoes_compativeis(self.engine)
        with self.engine.connect() as c:
            self.assertEqual(c.exec_driver_sql("SELECT COUNT(*) FROM funcionarios").scalar_one(),1)
            self.assertEqual(c.exec_driver_sql("PRAGMA integrity_check").scalar_one(),"ok")
            self.assertEqual(c.exec_driver_sql("PRAGMA foreign_key_check").all(),[])
            self.assertEqual(c.exec_driver_sql("PRAGMA user_version").scalar_one(),SCHEMA_VERSION)

    def test_anexo_download_auditoria_e_bloqueio_fechada(self):
        o=self.registrar()
        with patch("app.ocorrencias.routes.UPLOADS_DIR",Path(self.temp.name)/"uploads"):
            anexar(o.id,UploadFile(filename="teste.pdf",file=BytesIO(b"%PDF-1.4 ficticio")),self.db)
            resposta=baixar_anexo(o.id,self.db)
            self.assertEqual(Path(resposta.path).read_bytes(),b"%PDF-1.4 ficticio")
            self.assertEqual(o.historico[-1]["acao"],"anexo")
            self.fechar()
            with self.assertRaises(HTTPException): anexar(o.id,UploadFile(filename="outro.pdf",file=BytesIO(b"teste")),self.db)

    def test_anexo_invalido_e_vazio_nao_deixa_arquivo(self):
        o=self.registrar()
        pasta=Path(self.temp.name)/"uploads"
        with patch("app.ocorrencias.routes.UPLOADS_DIR",pasta):
            for nome,conteudo in (("invalido.exe",b"teste"),("vazio.pdf",b"")):
                with self.assertRaises(HTTPException): anexar(o.id,UploadFile(filename=nome,file=BytesIO(conteudo)),self.db)
            self.assertEqual([p for p in pasta.rglob('*') if p.is_file()],[])

    def test_relatorio_recebe_ocorrencia_processada_e_preserva_snapshot(self):
        self.batidas(); self.registrar(tipo="DECLARACAO",hora_inicio="13:00",hora_fim="15:00")
        html=relatorio_impressao(self.competencia.id,self.db).body.decode()
        self.assertIn("DECLARAÇÃO",html)
        self.assertIn("<td>120</td>",html)
        self.fechar()
        html_fechado=relatorio_impressao(self.competencia.id,self.db).body
        self.escala.horario_saida_prevista=time(18); self.db.commit()
        self.assertEqual(relatorio_impressao(self.competencia.id,self.db).body,html_fechado)

    def test_anexo_maior_que_limite_nao_deixa_arquivo(self):
        o=self.registrar(); pasta=Path(self.temp.name)/"uploads"
        with patch("app.ocorrencias.routes.UPLOADS_DIR",pasta):
            with self.assertRaises(HTTPException) as exc:
                anexar(o.id,UploadFile(filename="grande.pdf",file=BytesIO(b"x"*(25*1024*1024+1))),self.db)
            self.assertEqual(exc.exception.status_code,413)
            self.assertEqual([p for p in pasta.rglob('*') if p.is_file()],[])
