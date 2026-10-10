"""DTO exclusivo para a futura branch de OCR; não produz marcações."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Recorte(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    largura: float = Field(gt=0, le=1)
    altura: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def dentro_da_pagina(self):
        if self.x+self.largura>1 or self.y+self.altura>1: raise ValueError("Recorte fora da página.")
        return self

class SugestaoCampo(BaseModel):
    campo: Literal["data", "entrada", "saida_almoco", "retorno_almoco", "saida"]
    valor: str | None = None
    confianca: float | None = Field(default=None,ge=0,le=1)
    origem: str = Field(min_length=1,max_length=180)
    recorte: Recorte | None = None
    revisao_humana: Literal["pendente", "aceita", "rejeitada"] = "pendente"
    justificativa: str | None = None

class PropostaDocumento(BaseModel):
    documento_id: int = Field(gt=0)
    funcionario_id: int = Field(gt=0)
    competencia_id: int = Field(gt=0)
    pagina: int = Field(ge=1)
    campos: list[SugestaoCampo]
    revisao_humana: Literal["pendente", "concluida"] = "pendente"
