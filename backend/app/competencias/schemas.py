from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


STATUS_COMPETENCIA = {"aberta", "em_conferencia", "conferida", "fechada"}


class CompetenciaBase(BaseModel):
    empresa_id: int
    mes: int = Field(..., ge=1, le=12)
    ano: int = Field(..., ge=2000, le=2100)
    status: str = "aberta"
    data_recebimento: date | None = None
    data_fechamento: date | None = None
    observacoes: str | None = None


class CompetenciaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empresa_id: int
    mes: int = Field(..., ge=1, le=12)
    ano: int = Field(..., ge=2000, le=2100)
    data_recebimento: date | None = None
    observacoes: str | None = None


class CompetenciaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empresa_id: int | None = None
    mes: int | None = Field(default=None, ge=1, le=12)
    ano: int | None = Field(default=None, ge=2000, le=2100)
    data_recebimento: date | None = None
    observacoes: str | None = None


class CompetenciaRead(CompetenciaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class FechamentoCompetenciaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmar_pendencias: bool = False


class CompetenciaAcaoRead(BaseModel):
    id: int
    status: str
    data_fechamento: date | None
    total_pendencias: int
    fechamento_excepcional: bool
    mensagem: str
