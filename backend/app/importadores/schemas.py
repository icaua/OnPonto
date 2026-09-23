from pydantic import BaseModel, Field


class ConfirmacaoImportacao(BaseModel):
    empresa_id: int
    competencia_id: int
    arquivo_id: int
    registros_ids: list[str] = Field(default_factory=list)
