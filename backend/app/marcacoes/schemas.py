from datetime import date, datetime, time

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


STATUS_DIA = {
    "normal",
    "falta",
    "atestado",
    "folga",
    "feriado",
    "domingo",
    "sem_expediente",
    "trabalho_externo",
    "afastamento",
    "pendente",
    "pendente_conferencia",
}
ORIGENS = {"manual", "arquivo", "ocr", "xlsx_importado", "txt_log_relogio"}


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
    model_config = ConfigDict(extra="forbid")

    entrada: time | None = None
    saida_almoco: time | None = None
    retorno_almoco: time | None = None
    saida: time | None = None
    status_dia: str | None = None
    conferido: bool | None = None
    observacoes: str | None = None


class MarcacaoRead(MarcacaoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batidas_originais: list[str] = Field(default_factory=list)
    arquivo_origem_id: int | None = None
    arquivo_origem_nome: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("batidas_originais", mode="before")
    @classmethod
    def converter_batidas_originais(cls, valor: object) -> list[str]:
        if valor in (None, ""):
            return []
        if isinstance(valor, list):
            return [str(item) for item in valor]
        if isinstance(valor, str):
            try:
                decodificado = json.loads(valor)
            except json.JSONDecodeError:
                return []
            if isinstance(decodificado, list):
                return [str(item) for item in decodificado]
        return []
