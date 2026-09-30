import json
import sys
import unittest
from datetime import date, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.database.session import Base
from app.database.models import Empresa, Escala, Funcionario, Competencia, MarcacaoPonto, ArquivoRecebido
from app.apuracao.routes import obter_apuracao
from app.apuracao.service import apurar_competencia
from app.competencias.routes import fechar_competencia, inicializar_calendario
from app.competencias.schemas import FechamentoCompetenciaRequest
from app.marcacoes.routes import conferir_lote, ConferenciaLote, atualizar_marcacao
from app.marcacoes.schemas import MarcacaoUpdate


class ConfiabilidadeOperacionalTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        empresa = Empresa(nome="Empresa Fictícia Operacional")
        self.db.add(empresa); self.db.flush()
        escala = Escala(empresa_id=empresa.id, nome="Escala fictícia", jornada_seg_sex_horas=8)
        self.db.add(escala); self.db.flush()
        self.f = Funcionario(empresa_id=empresa.id, escala_id=escala.id, nome="Pessoa Fictícia", data_admissao=date(2026,9,1), data_demissao=date(2026,9,1))
        self.c = Competencia(empresa_id=empresa.id, mes=9, ano=2026)
        self.db.add_all([self.f, self.c]); self.db.commit()

    def dia(self, **kw):
        campos = dict(competencia_id=self.c.id, funcionario_id=self.f.id, data=date(2026,9,1), entrada=time(8), saida_almoco=time(12), retorno_almoco=time(13), saida=time(17), conferido=False)
        campos.update(kw); m=MarcacaoPonto(**campos); self.db.add(m); self.db.commit(); return m

    def test_normal_aguarda_mas_nao_e_problema(self):
        self.dia()
        r=apurar_competencia(self.db,self.c.id)
        self.assertEqual(r['operacional']['problemas'],0)
        self.assertEqual(r['operacional']['aguardando_conferencia'],1)
        self.assertFalse(r['fechamento']['pode_fechar'])
        self.assertEqual(r['fechamento']['proxima_acao'],'continuar_conferencia')

    def test_lote_misto_confere_so_validos(self):
        bom=self.dia()
        self.f.data_demissao=date(2026,9,2); self.db.commit()
        ruim=self.dia(data=date(2026,9,2),saida=None,batidas_originais='["08:00","12:00","13:00"]')
        r=conferir_lote(ConferenciaLote(competencia_id=self.c.id,marcacoes_ids=[bom.id,ruim.id]), self.db)
        self.assertEqual((r['total_conferidos'],r['total_problemas']),(1,1))
        self.db.refresh(ruim); self.assertFalse(ruim.conferido)
        with self.assertRaises(HTTPException): atualizar_marcacao(ruim.id,MarcacaoUpdate(conferido=True),self.db)
        for confirmar in (False,True):
            with self.assertRaises(HTTPException): fechar_competencia(self.c.id,FechamentoCompetenciaRequest(confirmar_pendencias=confirmar),self.db)
        self.db.rollback()
        self.assertNotEqual(self.db.get(Competencia,self.c.id).status,'fechada')

    def test_get_nao_modifica_banco_nem_inicializa(self):
        antes=list(self.db.execute(text('SELECT * FROM competencias')))
        for _ in range(2): obter_apuracao(self.c.id,self.db)
        self.assertEqual(self.db.query(MarcacaoPonto).count(),0)
        self.assertEqual(antes,list(self.db.execute(text('SELECT * FROM competencias'))))
        self.assertFalse(self.db.new); self.assertFalse(self.db.dirty)
        inicializar_calendario(self.c.id,self.db)
        self.assertEqual(self.db.query(MarcacaoPonto).count(),1)

    def test_zero_calculado_e_ausencia_diferem(self):
        vazio=apurar_competencia(self.db,self.c.id)
        self.assertIsNone(vazio['resumo'][0]['extras_minutos'])
        self.dia()
        calculado=apurar_competencia(self.db,self.c.id)
        self.assertEqual(calculado['resumo'][0]['extras_minutos'],0)

    def test_fechamento_valido_e_snapshot(self):
        self.dia(conferido=True)
        self.assertTrue(apurar_competencia(self.db,self.c.id)['fechamento']['pode_fechar'])
        fechar_competencia(self.c.id,FechamentoCompetenciaRequest(),self.db)
        self.assertEqual(self.c.status,'fechada')
        self.assertIsNotNone(self.c.apuracao_fechada)

    def test_funcionario_nao_resolvido_bloqueia(self):
        self.dia(conferido=True)
        self.db.add(ArquivoRecebido(competencia_id=self.c.id,nome_original='ficticio.txt',caminho_arquivo='ficticio.txt',tipo_arquivo='txt_generico',controle_importacao_json=json.dumps({'estado':'confirmada','pendencias':[{'registro_id':'x','tipo':'funcionario_nao_encontrado','mensagem':'Não cadastrado'}]})))
        self.db.commit()
        r=apurar_competencia(self.db,self.c.id)
        self.assertFalse(r['fechamento']['pode_fechar'])
        self.assertEqual(r['operacional']['conflitos_importacao'],1)


if __name__ == '__main__': unittest.main()
