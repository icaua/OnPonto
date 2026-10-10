"""Unidade de validação/escrita com rollback também nas falhas anteriores ao commit."""
from functools import wraps
from inspect import signature

from fastapi import HTTPException
from sqlalchemy.orm.exc import StaleDataError
from app.ocorrencias.service import iniciar_escrita


def atomica(funcao):
    assinatura = signature(funcao)

    @wraps(funcao)
    def executar(*args, **kwargs):
        db = assinatura.bind(*args, **kwargs).arguments["db"]
        try:
            iniciar_escrita(db)
            return funcao(*args, **kwargs)
        except StaleDataError as erro:
            db.rollback()
            raise HTTPException(409, detail={"codigo": "revisao_conflitante",
                "mensagem": "O registro foi alterado em outra janela. Recarregue e revise sua edição."}) from erro
        except Exception:
            db.rollback()
            raise

    return executar
