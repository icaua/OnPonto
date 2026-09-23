from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AjusteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    funcionario_id: int
    natureza: Literal["credito", "debito"]
    minutos: int = Field(gt=0, strict=True)
    data_referencia: date
    observacao: str = Field(min_length=1, max_length=5000)

    @field_validator("observacao")
    @classmethod
    def motivo_obrigatorio(cls, value):
        if not value.strip():
            raise ValueError("Informe o motivo do ajuste manual.")
        return value.strip()


class EstornoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: str = Field(min_length=1, max_length=5000)

    @field_validator("motivo")
    @classmethod
    def motivo_obrigatorio(cls, value):
        if not value.strip():
            raise ValueError("Informe o motivo do estorno.")
        return value.strip()
