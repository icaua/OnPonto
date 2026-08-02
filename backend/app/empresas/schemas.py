from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmpresaBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=180)
    cnpj: str | None = None
    jornada_seg_sex_horas: float = 8
    jornada_sabado_horas: float = 4
    tolerancia_atraso_minutos: int = 5
    tolerancia_extra_minutos: int = 10
    ativa: bool = True
    observacoes: str | None = None


class EmpresaCreate(EmpresaBase):
    pass


class EmpresaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=180)
    cnpj: str | None = None
    jornada_seg_sex_horas: float | None = None
    jornada_sabado_horas: float | None = None
    tolerancia_atraso_minutos: int | None = None
    tolerancia_extra_minutos: int | None = None
    ativa: bool | None = None
    observacoes: str | None = None


class EmpresaRead(EmpresaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
