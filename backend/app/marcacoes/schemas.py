from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict


STATUS_DIA = {"normal", "falta", "atestado", "folga", "feriado", "pendente", "pendente_conferencia"}
ORIGENS = {"manual", "arquivo", "ocr", "xlsx_importado"}


class MarcacaoBase(BaseModel):
    competencia_id: int
    funcionario_id: int
    data: date
    entrada: time | None = None
    saida_almoco: time | None = None
    retorno_almoco: time | None = None
    saida: time | None = None
    status_dia: str = "pendente"
    origem: str = "manual"
    conferido: bool = False
    observacoes: str | None = None


class MarcacaoCreate(MarcacaoBase):
    pass


class MarcacaoUpdate(BaseModel):
    competencia_id: int | None = None
    funcionario_id: int | None = None
    data: date | None = None
    entrada: time | None = None
    saida_almoco: time | None = None
    retorno_almoco: time | None = None
    saida: time | None = None
    status_dia: str | None = None
    origem: str | None = None
    conferido: bool | None = None
    observacoes: str | None = None


class MarcacaoRead(MarcacaoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
