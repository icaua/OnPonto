"""Política definida pelo usuário: perda por falta injustificada nos seis dias anteriores."""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DiaReferenciaDSR:
    data: date
    dentro_vinculo: bool
    marcacao_id: int | None
    revisao: int | None
    status: str | None
    conferido: bool
    problema: bool = False


def apurar_descanso(descanso, referencias):
    inicio = descanso - timedelta(days=6)
    dias = {d.data:d for d in referencias}
    ausentes, faltas, dependencias = [], [], []
    for n in range(6):
        data = inicio + timedelta(days=n)
        dia = dias.get(data)
        if dia is not None and not dia.dentro_vinculo:
            continue
        if dia is None or dia.marcacao_id is None or dia.problema or not dia.conferido:
            ausentes.append(data.isoformat())
            continue
        dependencias.append({"marcacao_id":dia.marcacao_id,"revisao":dia.revisao,"data":data.isoformat()})
        if dia.status == "falta":
            faltas.append(data.isoformat())
    return {"periodo_inicio":inicio.isoformat(),"periodo_fim":(descanso-timedelta(days=1)).isoformat(),
            "descanso_referencia":descanso.isoformat(),"faltas_injustificadas":faltas,
            "desconto_dias":None if ausentes else int(bool(faltas)),"dias_pendentes":ausentes,
            "dependencias":dependencias,"unidade":"dias"}
