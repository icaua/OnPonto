"""Políticas explícitas, versionadas e sem identificação automática de convenções.

Arredondamento acumulado por funcionário/política na competência: metade para cima
na parcela da folha; o banco recebe o complemento inteiro. O fator é aplicado em
um acumulador separado por tipo de dia. Assim frações não somem a cada dia.
"""
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegraDia(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fator_banco: Decimal = Field(default=Decimal(1), gt=0, le=10, decimal_places=4)
    base_fator: Literal["parcela_banco", "extra_integral", "decidir"] = "decidir"
    adicional_folha_percentual: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=2)


class PoliticaHoras(BaseModel):
    model_config = ConfigDict(extra="forbid")
    versao: Literal[1] = 1
    referencia: str | None = Field(default=None, max_length=240)
    modo: Literal["folha", "banco", "misto"]
    percentual_folha: Decimal = Field(ge=0, le=100, decimal_places=4)
    percentual_banco: Decimal = Field(ge=0, le=100, decimal_places=4)
    adicional_folha_percentual: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=2)
    debitar_atrasos: bool = True
    permite_saldo_negativo: bool = True
    ciclo_dias: int | None = Field(default=None, ge=1, le=3660)
    inicio_ciclo: date | None = None
    fim_ciclo_credor: Literal["decidir", "pagar"] = "decidir"
    adicional_saldo_percentual: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=2)
    fim_ciclo_devedor: Literal["decidir", "transportar"] = "decidir"
    desligamento_credor: Literal["decidir", "pagar"] = "decidir"
    desligamento_devedor: Literal["decidir", "descontar", "dispensar"] = "decidir"
    normal: RegraDia = Field(default_factory=RegraDia)
    sabado: RegraDia = Field(default_factory=RegraDia)
    domingo: RegraDia = Field(default_factory=RegraDia)
    feriado: RegraDia = Field(default_factory=RegraDia)

    @model_validator(mode="after")
    def validar(self):
        if self.percentual_folha + self.percentual_banco != 100:
            raise ValueError("Os percentuais de folha e banco devem somar 100%.")
        if ((self.modo == "folha" and self.percentual_folha != 100)
                or (self.modo == "banco" and self.percentual_banco != 100)
                or (self.modo == "misto" and not 0 < self.percentual_folha < 100)):
            raise ValueError("Os percentuais devem corresponder ao modo escolhido.")
        if self.percentual_banco and (not self.ciclo_dias or not self.inicio_ciclo):
            raise ValueError("Informe a duração e a data inicial dos ciclos do banco.")
        return self


CAMPOS_DISTRIBUICAO = ("extra_apurada_minutos", "extra_folha_minutos", "extra_banco_base_minutos",
                       "extra_banco_minutos", "debito_banco_minutos")


def politica_da_escala(escala):
    dados = getattr(escala, "politica_horas", None)
    return PoliticaHoras.model_validate(dados) if dados else None


def ciclo(politica, referencia):
    if not politica.percentual_banco:
        return None, None
    # O marco define ciclos contíguos também para datas anteriores a ele.
    numero = (referencia - politica.inicio_ciclo).days // politica.ciclo_dias
    inicio = politica.inicio_ciclo + timedelta(days=numero * politica.ciclo_dias)
    return inicio, inicio + timedelta(days=politica.ciclo_dias - 1)


def inteiro(valor):
    return int(valor.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def acumular(acumuladores, chave, valor):
    anterior = acumuladores.get(chave, Decimal(0))
    acumuladores[chave] = anterior + valor
    return inteiro(anterior + valor) - inteiro(anterior)


def extra_bruta(dia, escala, marcacao):
    if dia.get("fora_vinculo"):
        return 0
    if dia.get("feriado_aplicado") or dia["status_dia"] == "feriado":
        return dia.get("horas_feriado_minutos", 0)
    if escala.modo_apuracao == "horario_fixo" and dia["status_dia"] == "normal":
        from app.ocorrencias.interpretacao import intervalos, minutos_cobertos
        realizados = intervalos(marcacao.entrada, marcacao.saida_almoco, marcacao.retorno_almoco, marcacao.saida)
        previstos = intervalos(escala.horario_entrada_prevista, escala.horario_saida_almoco_prevista,
                              escala.horario_retorno_almoco_prevista, escala.horario_saida_prevista)
        if realizados is not None and previstos is not None:
            exigidos = minutos_cobertos(previstos) if dia["jornada_prevista_minutos"] else set()
            minutos = len(minutos_cobertos(realizados) - exigidos)
            return 0 if minutos <= escala.tolerancia_extra_minutos else minutos
    return dia["extra_minutos"]


def distribuir_dia(dia, escala, marcacao, empresa, acumuladores):
    politica = politica_da_escala(escala)
    if politica is None:
        # Compatibilidade: não muda a apuração nem a opção antiga de feriados.
        bruto = dia["extra_minutos"]
        banco = bool(escala and escala.usa_banco_horas)
        credito = bruto + (dia.get("horas_feriado_minutos", 0) if banco and empresa.feriado_entra_banco else 0)
        dia.update(extra_apurada_minutos=credito if banco else bruto,
                   extra_folha_minutos=0 if banco else bruto, extra_banco_base_minutos=credito if banco else 0,
                   extra_banco_minutos=credito if banco else 0,
                   debito_banco_minutos=(dia["atraso_minutos"] + dia.get("minutos_folga_compensatoria", 0)) if banco else 0,
                   adicional_folha_percentual=None, politica_horas_aplicada=None)
        if dia.get("pendente_calculo"):
            dia.update({campo: None for campo in CAMPOS_DISTRIBUICAO})
        return
    regra_json = politica.model_dump(mode="json")
    dia["politica_horas_aplicada"] = {"escala_id": escala.id, "politica": regra_json,
        "arredondamento": "acumulado_por_funcionario_politica_competencia_metade_para_cima_v1"}
    tipo = "feriado" if dia.get("feriado_aplicado") or dia["status_dia"] == "feriado" else (
        "domingo" if marcacao.data.weekday() == 6 else "sabado" if marcacao.data.weekday() == 5 else "normal")
    regra = getattr(politica, tipo)
    adicional = regra.adicional_folha_percentual if regra.adicional_folha_percentual is not None else politica.adicional_folha_percentual
    inicio, fim = ciclo(politica, marcacao.data)
    dia.update(tipo_dia_politica=tipo, ciclo_inicio=inicio.isoformat() if inicio else None,
               ciclo_fim=fim.isoformat() if fim else None,
               adicional_folha_percentual=str(adicional) if adicional is not None else None)
    dia.update({campo: None for campo in CAMPOS_DISTRIBUICAO})
    if dia.get("pendente_calculo"):
        return
    bruto = extra_bruta(dia, escala, marcacao)
    dia["extra_apurada_minutos"] = bruto
    if bruto and politica.percentual_banco and regra.fator_banco != 1 and regra.base_fator == "decidir":
        dia.update(pendente_calculo=True, pendencia_tipo="politica_requer_decisao",
                   pendencia_motivo=f"Defina a base do fator de banco para {tipo}: parcela do banco ou HE integral.")
        return
    if bruto and politica.percentual_folha and adicional is None:
        dia.update(pendente_calculo=True, pendencia_tipo="politica_requer_decisao",
                   pendencia_motivo=f"Informe o adicional de folha aplicável a {tipo} na política da escala.")
        return
    chave = (dia["funcionario_id"], escala.id, json.dumps(regra_json, sort_keys=True))
    folha_exata = Decimal(bruto) * politica.percentual_folha / 100
    folha = acumular(acumuladores, (*chave, "folha"), folha_exata)
    base = bruto - folha
    incidencia = bruto if regra.base_fator == "extra_integral" else base
    credito_exato = Decimal(incidencia) * regra.fator_banco if politica.percentual_banco else Decimal(0)
    credito = acumular(acumuladores, (*chave, "fator", tipo), credito_exato)
    dia.update(extra_folha_minutos=folha, extra_banco_base_minutos=base, extra_banco_minutos=credito,
               debito_banco_minutos=((dia["atraso_minutos"] if politica.debitar_atrasos else 0)
                   + dia.get("minutos_folga_compensatoria", 0)) if politica.percentual_banco else 0,
               distribuicao_auditoria={"folha_exata_minutos": str(folha_exata), "credito_exato_minutos": str(credito_exato),
                   "efeito_fator_arredondado_minutos": credito - base, "base_fator": regra.base_fator})
    # O campo histórico passa a exibir a HE bruta somente em políticas explícitas.
    if tipo != "feriado":
        dia["extra_minutos"] = bruto
        dia["extra"] = f"{bruto // 60:02d}:{bruto % 60:02d}"


def resumir_distribuicao(resumo, dias):
    for item in resumo:
        registros = [d for d in dias if d["funcionario_id"] == item["funcionario_id"] and not d.get("fora_vinculo")]
        for campo in CAMPOS_DISTRIBUICAO:
            valores = [d.get(campo) for d in registros]
            item[campo] = sum(valores) if valores and all(v is not None for v in valores) else None
        adicionais = {}
        politicas = []
        for dia in registros:
            adicional = dia.get("adicional_folha_percentual")
            if dia.get("extra_folha_minutos") is not None:
                adicionais[adicional] = adicionais.get(adicional, 0) + dia["extra_folha_minutos"]
            aplicada = dia.get("politica_horas_aplicada")
            if aplicada and aplicada not in politicas:
                politicas.append(aplicada)
        item["adicionais_folha"] = ([{"percentual": p, "minutos": m} for p, m in adicionais.items() if m]
                                   if item["extra_folha_minutos"] is not None else None)
        item["politicas_horas_aplicadas"] = politicas
