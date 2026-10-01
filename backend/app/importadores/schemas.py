from pydantic import BaseModel, Field, field_validator, model_validator


class ConfirmacaoImportacao(BaseModel):
    empresa_id: int
    competencia_id: int
    arquivo_id: int
    registros_ids: list[str] = Field(default_factory=list)


class DescartePendencias(BaseModel):
    registros_ids: list[str] = Field(min_length=1)
    justificativa: str = Field(min_length=10, max_length=1000)


class IdentificacaoIgnoradaCreate(BaseModel):
    empresa_id: int
    codigo_origem: str | None = Field(default=None, max_length=50)
    nome_origem: str | None = Field(default=None, max_length=180)
    justificativa: str = Field(min_length=10, max_length=1000)

    @field_validator("codigo_origem", "nome_origem", "justificativa", mode="before")
    @classmethod
    def limpar(cls, valor):
        return valor.strip() or None if isinstance(valor, str) else valor

    @model_validator(mode="after")
    def exigir_identidade(self):
        if not self.codigo_origem and not self.nome_origem:
            raise ValueError("Informe o código ou o nome da pessoa no relógio.")
        return self
