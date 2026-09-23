from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmpresaBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=180)
    cnpj: str | None = None
    cidade: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    ativa: bool = True
    observacoes: str | None = None
    prazo_compensacao_banco_horas_dias: int | None = Field(default=None, gt=0, strict=True)
    feriado_entra_banco: bool = False


class EmpresaCreate(EmpresaBase):
    pass


class EmpresaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=180)
    cnpj: str | None = None
    cidade: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    ativa: bool | None = None
    observacoes: str | None = None
    prazo_compensacao_banco_horas_dias: int | None = Field(default=None, gt=0, strict=True)
    feriado_entra_banco: bool = False


class EmpresaRead(EmpresaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
