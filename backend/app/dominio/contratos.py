from dataclasses import dataclass, field
from datetime import date,time
from typing import Any, Literal


OrigemHorario=Literal["real","previsto","pre_assinalado","corrigido"]


@dataclass(frozen=True)
class RegraVigente:
    id: int
    modo_apuracao: str
    jornada_seg_sex_horas: float | None = None
    jornada_sabado_horas: float | None = None
    horario_entrada_prevista: time | None = None
    horario_saida_almoco_prevista: time | None = None
    horario_retorno_almoco_prevista: time | None = None
    horario_saida_prevista: time | None = None
    regime_sabado: str = "nao_trabalha"
    regime_domingo: str = "nao_trabalha"
    tolerancia_atraso_minutos: int = 0
    tolerancia_extra_minutos: int = 0
    tolerancia_intervalo_minutos: int | None = None
    usa_banco_horas: bool = False
    politica_horas: dict | None = None
    jornadas_semana: dict | None = None
    jornada_dia_minutos: int | None = None
    versao_id: int | None = None

    def para_dia(self,dia):
        from dataclasses import replace
        dados=(self.jornadas_semana or {}).get(str(dia.weekday()))
        if dados is None: return self
        horarios={campo:time.fromisoformat(dados[campo]) if dados.get(campo) else None for campo in
            ("horario_entrada_prevista","horario_saida_almoco_prevista","horario_retorno_almoco_prevista","horario_saida_prevista")}
        return replace(self,jornada_dia_minutos=dados["jornada_minutos"],**horarios)


@dataclass(frozen=True)
class MarcacoesDoDia:
    id: int
    data: date
    entrada: time | None = None
    saida_almoco: time | None = None
    retorno_almoco: time | None = None
    saida: time | None = None
    status_dia: str = "normal"
    origem: str = "manual"
    conferido: bool = False
    observacoes: str | None = None
    batidas_originais: str | None = None
    batidas_desconsideradas_json: str | None = None
    historico_json: str | None = None
    arquivo_origem_id: int | None = None

    @property
    def batidas_desconsideradas(self):
        import json
        return json.loads(self.batidas_desconsideradas_json or "[]")


@dataclass(frozen=True)
class FuncionarioDoDia:
    id: int
    nome: str
    escala: RegraVigente | None
    nome_exibicao: str | None = None
    data_admissao: date | None = None
    data_demissao: date | None = None


@dataclass(frozen=True)
class ContextoCalendario:
    feriados: tuple[str,...] = ()


@dataclass(frozen=True)
class Ocorrencia:
    id: int
    tipo: str
    data_inicio: date
    data_fim: date | None = None
    hora_inicio: time | None = None
    hora_fim: time | None = None


@dataclass(frozen=True)
class OcorrenciasDoDia:
    itens: tuple[Ocorrencia,...] = ()


@dataclass(frozen=True)
class ResultadoDia:
    disponibilidade: Literal["completo","incompleto","indisponivel"]
    trabalhados_minutos: int | None
    previstos_minutos: int | None
    atraso_minutos: int | None
    extra_minutos: int | None
    pendencia: str | None
    # Payload legado é entregue pelo adaptador; zeros antigos não são usados
    # para representar disponibilidade no contrato do núcleo.
    dados_legados: dict[str,Any] = field(repr=False)

    def para_api_legada(self):
        from copy import deepcopy
        return deepcopy(self.dados_legados)
