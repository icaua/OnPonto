from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FuncionarioBase(BaseModel):
    empresa_id: int
    codigo: str | None = None
    nome: str = Field(..., min_length=1, max_length=180)
    cargo: str | None = None
    ativo: bool = True
    jornada_especifica_seg_sex_horas: float | None = None
    jornada_especifica_sabado_horas: float | None = None
    observacoes: str | None = None


class FuncionarioCreate(FuncionarioBase):
    pass


class FuncionarioUpdate(BaseModel):
    empresa_id: int | None = None
    codigo: str | None = None
    nome: str | None = Field(default=None, min_length=1, max_length=180)
    cargo: str | None = None
    ativo: bool | None = None
    jornada_especifica_seg_sex_horas: float | None = None
    jornada_especifica_sabado_horas: float | None = None
    observacoes: str | None = None


class FuncionarioRead(FuncionarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
