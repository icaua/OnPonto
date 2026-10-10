"""Ledger carregado em lote, válido somente na operação/transação corrente."""
from app.database.models import LancamentoBancoHoras, CompensacaoBancoHoras


class LedgerEmMemoria:
    def __init__(self, db, funcionarios_ids):
        self.itens={}
        self.compensacoes=[]
        self.compensacoes_por_funcionario={}
        self.cache={}
        ids=list(set(funcionarios_ids))
        if not ids: return
        for i in db.query(LancamentoBancoHoras).filter(LancamentoBancoHoras.funcionario_id.in_(ids)).order_by(
                LancamentoBancoHoras.data_referencia,LancamentoBancoHoras.data_lancamento,LancamentoBancoHoras.id):
            self.itens.setdefault(i.funcionario_id,[]).append(i)
        donos={i.id:i.funcionario_id for itens in self.itens.values() for i in itens}
        if donos:
            self.compensacoes=db.query(CompensacaoBancoHoras).join(LancamentoBancoHoras,
                LancamentoBancoHoras.id==CompensacaoBancoHoras.credito_id).filter(CompensacaoBancoHoras.status=="ativo",
                LancamentoBancoHoras.funcionario_id.in_(ids)).all()
            for c in self.compensacoes: self.compensacoes_por_funcionario.setdefault(donos[c.credito_id],[]).append(c)

    def situacao(self, funcionario_id, data_limite=None, incluir_estornados=False):
        chave=(funcionario_id,data_limite,incluir_estornados)
        if chave in self.cache: return self.cache[chave]
        itens=[i for i in self.itens.get(funcionario_id,[]) if
               (data_limite is None or i.data_referencia<=data_limite) and (incluir_estornados or i.status=="ativo")]
        ativos={i.id for i in itens if i.status=="ativo"}
        consumidos={i.id:0 for i in itens}
        for c in self.compensacoes_por_funcionario.get(funcionario_id,[]):
            # Débito posterior ao corte não consome crédito nesta consulta.
            if c.credito_id in ativos and c.debito_id in ativos:
                consumidos[c.credito_id]+=c.minutos;consumidos[c.debito_id]+=c.minutos
        resultado=[(i,consumidos[i.id],i.minutos-consumidos[i.id] if i.status=="ativo" else 0) for i in itens]
        self.cache[chave]=resultado
        return resultado
