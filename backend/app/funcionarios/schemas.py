from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DatasVinculo(BaseModel):
    data_admissao: date | None = None
    data_demissao: date | None = None

    @model_validator(mode="after")
    def validar_datas_vinculo(self):
        if self.data_admissao and self.data_demissao and self.data_demissao < self.data_admissao:
            raise ValueError("A data de demissão não pode ser anterior à data de admissão.")
        return self


class IdentidadeExibicao(DatasVinculo):
    nome_exibicao: str | None = Field(default=None, max_length=180)
    codigo_exibicao: str | None = Field(default=None, max_length=50)

    @field_validator("nome_exibicao", "codigo_exibicao", mode="before")
    @classmethod
    def limpar_identidade(cls, valor):
        return valor.strip() or None if isinstance(valor, str) else valor


class FuncionarioBase(IdentidadeExibicao):
    empresa_id: int
    codigo: str | None = None
    nome: str = Field(..., min_length=1, max_length=180)
    cargo: str | None = None
    ativo: bool = True
    escala_id: int | None = None
    observacoes: str | None = None


class FuncionarioCreate(FuncionarioBase):
    pass


class FuncionarioUpdate(IdentidadeExibicao):
    empresa_id: int | None = None
    codigo: str | None = None
    nome: str | None = Field(default=None, min_length=1, max_length=180)
    cargo: str | None = None
    ativo: bool | None = None
    escala_id: int | None = None
    observacoes: str | None = None


class FuncionarioRead(FuncionarioBase):
    model_config = ConfigDict(from_attributes=True)

    nome_apresentacao: str
    codigo_apresentacao: str | None
    id: int
    created_at: datetime
    updated_at: datetime
