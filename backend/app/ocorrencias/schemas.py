from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Tipo = Literal["ATESTADO", "DECLARACAO", "FERIAS", "AFASTAMENTO", "FOLGA_COMPENSATORIA"]


class OcorrenciaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    funcionario_id: int
    tipo: Tipo
    data_inicio: date
    data_fim: date | None = None
    hora_inicio: time | None = None
    hora_fim: time | None = None
    observacao: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.data_fim is None and self.tipo != "AFASTAMENTO":
            raise ValueError("Informe a data final; somente afastamento admite período aberto.")
        if self.data_fim and self.data_fim < self.data_inicio:
            raise ValueError("A data final não pode ser anterior à inicial.")
        if bool(self.hora_inicio) != bool(self.hora_fim):
            raise ValueError("Informe os dois horários ou nenhum.")
        if self.tipo == "DECLARACAO" and not self.hora_inicio:
            raise ValueError("Declaração exige hora inicial e final.")
        if self.hora_inicio:
            if self.tipo not in {"ATESTADO", "DECLARACAO", "FOLGA_COMPENSATORIA"}:
                raise ValueError("Férias e afastamento são períodos integrais.")
            if self.data_fim != self.data_inicio:
                raise ValueError("Ocorrência parcial deve começar e terminar no mesmo dia.")
            if self.hora_inicio.tzinfo or self.hora_fim.tzinfo:
                raise ValueError("Use horários locais sem fuso horário.")
            if self.hora_fim <= self.hora_inicio:
                raise ValueError("A hora final deve ser maior que a inicial.")
        return self


class OcorrenciaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    funcionario_id: int | None = None
    tipo: Tipo | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    hora_inicio: time | None = None
    hora_fim: time | None = None
    observacao: str | None = Field(default=None, max_length=5000)


class OcorrenciaRead(OcorrenciaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    empresa_id: int
    anexo_nome: str | None
    created_at: datetime
    updated_at: datetime
    excluido_em: datetime | None
    historico: list[dict]
