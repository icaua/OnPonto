from datetime import date,datetime,time
from typing import Literal
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict, Field, model_validator


from app.banco_horas.regras import PoliticaHoras


ModoApuracao = Literal["carga_horaria", "horario_fixo"]
RegimeSabado = Literal["trabalha", "compensado", "nao_trabalha"]
RegimeDomingo = Literal["trabalha", "nao_trabalha"]
TipoIntervalo = Literal["fixo", "flexivel", "sem_intervalo"]
RegistroIntervalo = Literal["batidas", "pre_assinalado"]


class PoliticaDSR(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: Literal[1] = 1
    dia_descanso: int = Field(default=6, ge=0, le=6)
    descontar_feriados: bool = True
    referencia: str | None = Field(default=None, max_length=240)


def _validar_intervalo(dados):
    tipo = getattr(dados, "tipo_intervalo", None)
    registro = getattr(dados, "registro_intervalo", None)
    duracao = getattr(dados, "duracao_intervalo_minutos", None)
    if tipo is None:
        if registro is not None or duracao is not None:
            raise ValueError("Escolha o tipo de intervalo antes de configurar seu registro/duração.")
        return
    if registro is None:
        raise ValueError("Informe como o intervalo será registrado.")
    if tipo == "sem_intervalo":
        if registro == "pre_assinalado" or duracao not in (None, 0):
            raise ValueError("Sem intervalo não admite pré-assinalação ou duração positiva.")
        if getattr(dados,"horario_saida_almoco_prevista",None) or getattr(dados,"horario_retorno_almoco_prevista",None):
            raise ValueError("Jornada sem intervalo deve deixar os horários previstos de almoço vazios.")
        return
    if duracao is None or duracao <= 0:
        raise ValueError("Informe a duração positiva do intervalo.")
    inicio = getattr(dados, "horario_saida_almoco_prevista", None)
    fim = getattr(dados, "horario_retorno_almoco_prevista", None)
    if tipo == "fixo" or registro == "pre_assinalado":
        if not inicio or not fim:
            raise ValueError("Intervalo fixo/pré-assinalado exige início e fim previstos.")
    if inicio and fim and (fim.hour*60+fim.minute-inicio.hour*60-inicio.minute) != duracao:
        raise ValueError("Duração de intervalo deve corresponder aos horários previstos.")


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


def _validar_duracao_diaria(dados):
    if dados.horario_entrada_prevista is None:
        return
    def minuto(t): return t.hour*60+t.minute
    duracao=minuto(dados.horario_saida_prevista)-minuto(dados.horario_entrada_prevista)
    if dados.horario_saida_almoco_prevista:
        duracao-=minuto(dados.horario_retorno_almoco_prevista)-minuto(dados.horario_saida_almoco_prevista)
    elif dados.tipo_intervalo == "flexivel":
        duracao-=dados.duracao_intervalo_minutos
    if duracao != dados.jornada_minutos:
        raise ValueError("Horários próprios devem corresponder à jornada diária em minutos.")


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
    politica_horas: PoliticaHoras | None = None
    jornadas_semana: dict[str,"JornadaDia"] | None = None
    tipo_intervalo: TipoIntervalo | None = None
    registro_intervalo: RegistroIntervalo | None = None
    duracao_intervalo_minutos: int | None = Field(default=None, ge=0, le=1440)
    politica_dsr: PoliticaDSR | None = None

    @model_validator(mode="after")
    def validar_configuracao(self) -> "EscalaBase":
        _validar_horarios(self)
        _validar_intervalo(self)
        for dia,jornada in (self.jornadas_semana or {}).items():
            if dia not in {str(n) for n in range(7)}:
                raise ValueError("Dias da semana: 0=segunda até 6=domingo.")
            if self.modo_apuracao=="horario_fixo" and jornada.jornada_minutos and not jornada.horario_entrada_prevista:
                raise ValueError("Jornada diária de horário fixo exige horários próprios.")
            if jornada.jornada_minutos:
                dados=jornada.model_dump()
                for campo in ("tipo_intervalo","registro_intervalo","duracao_intervalo_minutos"):
                    if dados[campo] is None: dados[campo]=getattr(self,campo)
                efetiva=SimpleNamespace(**dados)
                _validar_intervalo(efetiva)
                _validar_duracao_diaria(efetiva)
        if self.politica_horas is not None:
            self.usa_banco_horas = self.politica_horas.percentual_banco > 0
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


class JornadaDia(BaseModel):
    model_config=ConfigDict(extra="forbid")
    jornada_minutos: int = Field(ge=0,le=1440)
    horario_entrada_prevista: time | None = None
    horario_saida_almoco_prevista: time | None = None
    horario_retorno_almoco_prevista: time | None = None
    horario_saida_prevista: time | None = None
    tipo_intervalo: TipoIntervalo | None = None
    registro_intervalo: RegistroIntervalo | None = None
    duracao_intervalo_minutos: int | None = Field(default=None, ge=0, le=1440)

    @model_validator(mode="after")
    def validar(self):
        _validar_horarios(self)
        _validar_intervalo(self)
        # Sem tipo próprio, a duração depende do intervalo herdado da escala.
        if self.tipo_intervalo is not None:
            _validar_duracao_diaria(self)
        return self


class EscalaCreate(EscalaBase):
    vigente_desde: date | None = None


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
    politica_horas: PoliticaHoras | None = None
    jornadas_semana: dict[str,JornadaDia] | None = None
    vigente_desde: date | None = None
    tipo_intervalo: TipoIntervalo | None = None
    registro_intervalo: RegistroIntervalo | None = None
    duracao_intervalo_minutos: int | None = Field(default=None, ge=0, le=1440)
    politica_dsr: PoliticaDSR | None = None


class EscalaRead(EscalaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
