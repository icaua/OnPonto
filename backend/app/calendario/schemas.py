from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoEvento = Literal["FERIADO", "DATA_COMEMORATIVA"]
AbrangenciaEvento = Literal["NACIONAL", "ESTADUAL", "MUNICIPAL", "EMPRESA"]
UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())


class EventoCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    nome: str = Field(min_length=1, max_length=180)
    data: date
    tipo: TipoEvento
    descricao: str | None = Field(default=None, max_length=5000)
    abrangencia: AbrangenciaEvento
    uf: str | None = None
    municipio: str | None = Field(default=None, max_length=120)
    empresa_id: int | None = Field(default=None, gt=0)
    recorrente: bool = False
    ativo: bool = True

    @model_validator(mode="after")
    def validar_abrangencia(self):
        self.uf = self.uf.upper() if self.uf else None
        if self.abrangencia in {"ESTADUAL", "MUNICIPAL"} and self.uf not in UFS:
            raise ValueError("Informe uma UF válida para esta abrangência.")
        if self.abrangencia == "MUNICIPAL" and not self.municipio:
            raise ValueError("Informe o município.")
        if self.abrangencia == "EMPRESA" and not self.empresa_id:
            raise ValueError("Informe a empresa.")
        if self.abrangencia not in {"ESTADUAL", "MUNICIPAL"}:
            self.uf = None
        if self.abrangencia != "MUNICIPAL":
            self.municipio = None
        if self.abrangencia != "EMPRESA":
            self.empresa_id = None
        return self


class EventoUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    nome: str | None = Field(default=None, min_length=1, max_length=180)
    data: date | None = None
    tipo: TipoEvento | None = None
    descricao: str | None = Field(default=None, max_length=5000)
    abrangencia: AbrangenciaEvento | None = None
    uf: str | None = None
    municipio: str | None = Field(default=None, max_length=120)
    empresa_id: int | None = Field(default=None, gt=0)
    recorrente: bool | None = None
    ativo: bool | None = None


class EventoRead(EventoCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
