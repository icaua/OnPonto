"""Contexto por operação; consulta em lotes e uma interpretação diária compartilhada."""
from calendar import monthrange
from datetime import date, timedelta
from types import SimpleNamespace
from dataclasses import replace
import hashlib
import json
from sqlalchemy import or_
from app.database.models import Funcionario, MarcacaoPonto, ArquivoRecebido, OcorrenciaFuncionario
from app.funcionarios.historico_escalas import ResolvedorEscalas
from app.calendario.service import dentro_vinculo, feriados_da_competencia
from app.dominio.apuracao import apurar_dia, placeholder_calendario_intocado
from app.dominio.contratos import ContextoCalendario
from app.dominio.conferencia import classificar_dia
from app.banco_horas.regras import distribuir_dia
from app.apuracao import adaptadores
from app.apuracao.dsr import preparar_dsr


def valores(obj):
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns}


class ContextoApuracao:
    def __init__(self, db, competencia, funcionario_id=None):
        self.db,self.competencia=db,competencia
        self.empresa=competencia.empresa
        self.inicio=date(competencia.ano,competencia.mes,1)
        self.fim=date(competencia.ano,competencia.mes,monthrange(competencia.ano,competencia.mes)[1])
        consulta=db.query(Funcionario).filter_by(empresa_id=competencia.empresa_id)
        if funcionario_id is not None: consulta=consulta.filter_by(id=funcionario_id)
        self.funcionarios=consulta.order_by(Funcionario.nome).all()
        self.por_id={f.id:f for f in self.funcionarios}
        self.resolvedor=ResolvedorEscalas(db,competencia.empresa_id)
        self.dtos_funcionarios={f.id:adaptadores.funcionario(f) for f in self.funcionarios}
        self.feriados=feriados_da_competencia(db,self.empresa,competencia.ano,competencia.mes)
        consulta=db.query(MarcacaoPonto).filter_by(competencia_id=competencia.id)
        if funcionario_id is not None: consulta=consulta.filter_by(funcionario_id=funcionario_id)
        self.marcacoes=consulta.order_by(MarcacaoPonto.data,MarcacaoPonto.funcionario_id).all()
        self.por_funcionario={}
        for m in self.marcacoes: self.por_funcionario.setdefault(m.funcionario_id,[]).append(m)
        self.ocorrencias={}
        for o in db.query(OcorrenciaFuncionario).join(Funcionario).filter(Funcionario.empresa_id==self.empresa.id,
                OcorrenciaFuncionario.excluido_em.is_(None),OcorrenciaFuncionario.data_inicio<=self.fim+timedelta(days=6),
                or_(OcorrenciaFuncionario.data_fim.is_(None),OcorrenciaFuncionario.data_fim>=self.inicio-timedelta(days=6))).order_by(
                OcorrenciaFuncionario.data_inicio.desc(),OcorrenciaFuncionario.id.desc()):
            self.ocorrencias.setdefault(o.funcionario_id,[]).append(o)
        self.arquivos=db.query(ArquivoRecebido).filter_by(competencia_id=competencia.id).all()
        desconhecidos=[a.id for a in self.arquivos if not a.controle_importacao_json]
        self.arquivos_com_marcacoes={id for id, in db.query(MarcacaoPonto.arquivo_origem_id).filter(
            MarcacaoPonto.arquivo_origem_id.in_(desconhecidos)).distinct()} if desconhecidos else set()
        self.tem_dsr=any(json.loads(v.configuracao_json).get("politica_dsr") for vs in self.resolvedor.versoes.values() for v in vs) or any(
            s.politica_dsr for s in self.resolvedor.escalas)
        self.referencias={}
        if self.tem_dsr:
            for m in db.query(MarcacaoPonto).join(Funcionario).filter(Funcionario.empresa_id==self.empresa.id,
                    MarcacaoPonto.data.between(self.inicio-timedelta(days=6),self.fim+timedelta(days=6))):
                self.referencias.setdefault(m.funcionario_id,[]).append(m)
        self.dsr=None
        self.recalculados=[]

    def assinatura(self, funcionario):
        f=funcionario
        # Contadores derivados; a revisão humana permanece nas marcações.
        if not hasattr(self,"assinatura_global"):
            globais={"motor":2,"periodo":[self.inicio,self.fim],"empresa":valores(self.empresa),
                "feriados":sorted((d,n) for d,n in self.feriados.items()),"escalas":[valores(s) for s in self.resolvedor.escalas],
                "versoes":[valores(v) for vs in self.resolvedor.versoes.values() for v in vs]}
            if self.tem_dsr:
                from app.calendario.service import consultar_eventos
                globais["eventos_referencia"]=[valores(e) for ano in range((self.inicio-timedelta(days=6)).year,(self.fim+timedelta(days=6)).year+1)
                    for e in consultar_eventos(self.db,ano,tipo="FERIADO")]
            self.assinatura_global=hashlib.sha256(json.dumps(globais,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()
        dados={"global":self.assinatura_global,"funcionario":valores(f),"vinculos":[valores(v) for v in self.resolvedor.vinculos.get(f.id,[])],
            "ocorrencias":[valores(o) for o in self.ocorrencias.get(f.id,[])],
            "marcacoes":[valores(m) for m in (self.referencias.get(f.id,[]) if self.tem_dsr else self.por_funcionario.get(f.id,[]))]}
        return hashlib.sha256(json.dumps(dados,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()

    def detalhes(self, funcionario_id=None):
        if self.dsr is None:
            self.dsr,self.calculos_dsr=preparar_dsr(self.db,self.competencia,self.empresa,self.funcionarios,self.resolvedor)
        detalhes,acumuladores=[],{}
        for m in self.marcacoes if funcionario_id is None else self.por_funcionario.get(funcionario_id,[]):
            f=self.por_id.get(m.funcionario_id)
            if f is None or (not dentro_vinculo(f,m.data) and placeholder_calendario_intocado(m)): continue
            regra=self.resolvedor.regra_no_dia(f,m.data)
            dto=replace(self.dtos_funcionarios[f.id],escala=regra)
            d=(self.calculos_dsr.get(m.id) or apurar_dia(dto,adaptadores.marcacoes(m),
                ContextoCalendario(tuple(self.feriados.get(m.data,[]))),adaptadores.ocorrencias(self.ocorrencias.get(f.id,[])))).para_api_legada()
            d["revisao"]=m.revisao
            dsr=self.dsr.get((f.id,m.data))
            if dsr:
                d["dsr"]=dsr
                if dsr["desconto_dias"] is None:
                    d.update(pendente_calculo=True,pendencia_tipo="dsr_requer_revisao",pendencia_motivo=
                        "DSR exige conferir os seis dias anteriores ao descanso: " + ", ".join(dsr["dias_pendentes"]))
            distribuir_dia(d,regra,m,self.empresa,acumuladores)
            detalhes.append(classificar_dia(d))
        if funcionario_id is not None: self.recalculados.append(funcionario_id)
        return detalhes
