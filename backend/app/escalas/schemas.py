from datetime import datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ModoApuracao = Literal["carga_horaria", "horario_fixo"]
RegimeSabado = Literal["trabalha", "compensado", "nao_trabalha"]
RegimeDomingo = Literal["trabalha", "nao_trabalha"]


def _validar_horarios(dados: object) -> object:
    saida_almoco = getattr(dados, "horario_saida_almoco_prevista", None)
    retorno_almoco = getattr(dados, "horario_retorno_almoco_prevista", None)
    if bool(saida_almoco) != bool(retorno_almoco):
        raise ValueError("Os dois horários de almoço devem ser informados juntos.")

    entrada = getattr(dados, "horario_entrada_prevista", None)
    saida = getattr(dados, "horario_saida_prevista", None)
    if bool(entrada) != bool(saida):
        raise ValueError("Entrada e saída previstas devem ser informadas juntas.")

    horarios = [valor for valor in (entrada, saida_almoco, retorno_almoco, saida) if valor]
    if horarios and any(atual >= seguinte for atual, seguinte in zip(horarios, horarios[1:])):
        raise ValueError(
            "A ordem deve ser entrada, saída para almoço, retorno do almoço e saída."
        )
    return dados


class EscalaBase(BaseModel):
    empresa_id: int
    nome: str = Field(..., min_length=1, max_length=120)
    modo_apuracao: ModoApuracao = "carga_horaria"
    jornada_seg_sex_horas: float | None = Field(default=None, ge=0)
    jornada_sabado_horas: float | None = Field(default=None, ge=0)
    horario_entrada_prevista: time | None = None
    horario_saida_almoco_prevista: time | None = None
    horario_retorno_almoco_prevista: time | None = None
    horario_saida_prevista: time | None = None
    regime_sabado: RegimeSabado = "nao_trabalha"
    regime_domingo: RegimeDomingo = "nao_trabalha"
    tolerancia_atraso_minutos: int = Field(default=0, ge=0)
    tolerancia_extra_minutos: int = Field(default=0, ge=0)
    tolerancia_intervalo_minutos: int | None = Field(default=None, ge=0)
    ativa: bool = True
    usa_banco_horas: bool = False

    @model_validator(mode="after")
    def validar_configuracao(self) -> "EscalaBase":
        _validar_horarios(self)
        if self.modo_apuracao == "carga_horaria" and self.jornada_seg_sex_horas is None:
            raise ValueError("Informe a jornada de segunda a sexta para carga horária.")
        if (
            self.modo_apuracao == "carga_horaria"
            and self.regime_sabado == "trabalha"
            and self.jornada_sabado_horas is None
        ):
            raise ValueError("Informe a jornada de sábado quando esse dia é trabalhado.")
        if self.modo_apuracao == "horario_fixo" and (
            self.horario_entrada_prevista is None or self.horario_saida_prevista is None
        ):
            raise ValueError("Informe entrada e saída previstas para horário fixo.")
        return self


class EscalaCreate(EscalaBase):
    pass


class EscalaUpdate(BaseModel):
    empresa_id: int | None = None
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    modo_apuracao: ModoApuracao | None = None
    jornada_seg_sex_horas: float | None = Field(default=None, ge=0)
    jornada_sabado_horas: float | None = Field(default=None, ge=0)
    horario_entrada_prevista: time | None = None
    horario_saida_almoco_prevista: time | None = None
    horario_retorno_almoco_prevista: time | None = None
    horario_saida_prevista: time | None = None
    regime_sabado: RegimeSabado | None = None
    regime_domingo: RegimeDomingo | None = None
    tolerancia_atraso_minutos: int | None = Field(default=None, ge=0)
    tolerancia_extra_minutos: int | None = Field(default=None, ge=0)
    tolerancia_intervalo_minutos: int | None = Field(default=None, ge=0)
    ativa: bool | None = None
    usa_banco_horas: bool | None = None


class EscalaRead(EscalaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
