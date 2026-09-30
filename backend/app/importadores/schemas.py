from pydantic import BaseModel, Field


class ConfirmacaoImportacao(BaseModel):
    empresa_id: int
    competencia_id: int
    arquivo_id: int
    registros_ids: list[str] = Field(default_factory=list)


class DescartePendencias(BaseModel):
    registros_ids: list[str] = Field(min_length=1)
    justificativa: str = Field(min_length=10, max_length=1000)
