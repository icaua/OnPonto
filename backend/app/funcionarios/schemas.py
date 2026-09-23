from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DatasVinculo(BaseModel):
    data_admissao: date | None = None
    data_demissao: date | None = None

    @model_validator(mode="after")
    def validar_datas_vinculo(self):
        if self.data_admissao and self.data_demissao and self.data_demissao < self.data_admissao:
            raise ValueError("A data de demissão não pode ser anterior à data de admissão.")
        return self


class FuncionarioBase(DatasVinculo):
    empresa_id: int
    codigo: str | None = None
    nome: str = Field(..., min_length=1, max_length=180)
    cargo: str | None = None
    ativo: bool = True
    escala_id: int | None = None
    observacoes: str | None = None


class FuncionarioCreate(FuncionarioBase):
    pass


class FuncionarioUpdate(DatasVinculo):
    empresa_id: int | None = None
    codigo: str | None = None
    nome: str | None = Field(default=None, min_length=1, max_length=180)
    cargo: str | None = None
    ativo: bool | None = None
    escala_id: int | None = None
    observacoes: str | None = None


class FuncionarioRead(FuncionarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
