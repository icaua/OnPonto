"""Pessoas do relógio que a empresa decidiu não apurar (ex.: gestão sem controle de ponto).

A regra nunca apaga batidas nem o arquivo original. Os registros correspondentes saem
da apuração como exclusões justificadas, com a regra de origem na trilha, e voltam a
ser pendências se a regra for desativada. Pessoa cadastrada no OnPonto sempre prevalece.
"""
import re
import unicodedata
from datetime import datetime, timezone

from app.database.models import IdentificacaoIgnorada


def normalizar_nome(valor) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().casefold()


def normalizar_codigo(valor) -> str:
    return "" if valor is None else str(valor).strip()


def corresponde(regra, codigo_origem, nome_origem) -> bool:
    """Código do relógio identifica a pessoa; o nome só decide quando falta código."""
    codigo_regra, codigo = normalizar_codigo(regra.codigo_origem), normalizar_codigo(codigo_origem)
    if codigo_regra and codigo:
        return codigo_regra == codigo
    nome_regra, nome = normalizar_nome(regra.nome_origem), normalizar_nome(nome_origem)
    return bool(nome_regra and nome and nome_regra == nome)


def regras_ativas(db, empresa_id) -> list[IdentificacaoIgnorada]:
    return db.query(IdentificacaoIgnorada).filter_by(empresa_id=empresa_id, ativa=True).order_by(IdentificacaoIgnorada.id).all()


def regra_do_registro(regras, item):
    info = item["funcionario"]
    if info.get("encontrado"):
        return None
    return next((r for r in regras if corresponde(r, info.get("codigo_origem"), info.get("nome_origem"))), None)


def pendencia_do_registro(item) -> dict:
    info = item["funcionario"]
    return {"registro_id": item["id"], "tipo": "aguardando_importacao",
            "mensagem": "; ".join(item["pendencias"]) or "Registro ainda não importado.", "data": item["data"],
            "codigo_origem": info.get("codigo_origem"), "nome_origem": info.get("nome_origem"),
            "funcionario_encontrado": bool(info.get("encontrado"))}


def aplicar_regras(controle: dict, previa: list[dict], regras) -> int:
    """Exclui com trilha os registros de pessoas ignoradas. Devolve quantos foram excluídos agora."""
    descartados = controle.setdefault("descartados", [])
    ja_resolvidos = {d["registro_id"] for d in descartados} | set(controle.get("importados", []))
    pendentes = {p["registro_id"]: p for p in controle.get("pendencias", [])}
    agora = datetime.now(timezone.utc).isoformat()
    novos = 0
    for item in previa:
        regra = regra_do_registro(regras, item)
        if regra is None:
            continue
        item["selecionado"] = False
        item["ignorado"] = {"regra_id": regra.id, "justificativa": regra.justificativa}
        if item["id"] in ja_resolvidos:
            continue
        base = {**pendencia_do_registro(item), **pendentes.get(item["id"], {})}
        descartados.append({**base, "justificativa": "Pessoa ignorada nas importações: " + regra.justificativa,
                            "regra_id": regra.id, "em": agora})
        ja_resolvidos.add(item["id"])
        novos += 1
    excluidos = {d["registro_id"] for d in descartados}
    controle["pendencias"] = [p for p in controle.get("pendencias", []) if p["registro_id"] not in excluidos]
    return novos


def restaurar_regra(controle: dict, regra_id: int) -> int:
    """Devolve às pendências o que a regra excluiu; exclusões manuais permanecem."""
    descartados = controle.get("descartados", [])
    voltam = [d for d in descartados if d.get("regra_id") == regra_id]
    if not voltam:
        return 0
    importados = set(controle.get("importados", []))
    controle["descartados"] = [d for d in descartados if d.get("regra_id") != regra_id]
    existentes = {p["registro_id"] for p in controle.get("pendencias", [])}
    controle.setdefault("pendencias", []).extend(
        {k: v for k, v in d.items() if k not in ("justificativa", "regra_id", "em")}
        for d in voltam if d["registro_id"] not in importados and d["registro_id"] not in existentes)
    return len(voltam)


def serializar(regra) -> dict:
    return {"id": regra.id, "empresa_id": regra.empresa_id, "codigo_origem": regra.codigo_origem,
            "nome_origem": regra.nome_origem, "justificativa": regra.justificativa, "ativa": regra.ativa,
            "criada_em": regra.created_at, "desativada_em": regra.desativada_em}
