from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArquivoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    competencia_id: int
    nome_original: str
    caminho_arquivo: str
    tipo_arquivo: str
    observacoes: str | None
    created_at: datetime
