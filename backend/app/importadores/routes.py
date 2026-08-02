import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database.models import ArquivoRecebido, Competencia, Empresa, Funcionario
from app.database.session import BACKEND_DIR, UPLOADS_DIR, get_db
from app.importadores.xlsx_ponto_generico import parse_xlsx_ponto_generico


router = APIRouter(prefix="/importadores", tags=["Importadores"])


def nome_seguro(nome: str) -> str:
    base = Path(nome).name.strip() or "arquivo.xlsx"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)


def chave_texto(valor: str | None) -> str:
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    texto = re.sub(r"\s+", " ", texto).strip().lower()
    return texto


def salvar_arquivo_original(
    db: Session,
    competencia: Competencia,
    arquivo: UploadFile,
) -> ArquivoRecebido:
    original = nome_seguro(arquivo.filename or "ponto.xlsx")
    extensao = Path(original).suffix.lower()
    if extensao != ".xlsx":
        raise HTTPException(status_code=400, detail="Envie um arquivo .xlsx.")

    pasta_destino = UPLOADS_DIR / f"empresa_{competencia.empresa_id}" / f"{competencia.ano}-{competencia.mes:02d}"
    pasta_destino.mkdir(parents=True, exist_ok=True)
    nome_final = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}_{original}"
    destino = pasta_destino / nome_final

    try:
        with destino.open("wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)
    finally:
        arquivo.file.close()

    registro = ArquivoRecebido(
        competencia_id=competencia.id,
        nome_original=arquivo.filename or original,
        caminho_arquivo=destino.relative_to(BACKEND_DIR).as_posix(),
        tipo_arquivo="xlsx",
        observacoes="Arquivo importado pelo importador XLSX genérico.",
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


def mapa_funcionarios(db: Session, empresa_id: int) -> tuple[dict[str, Funcionario], dict[str, Funcionario]]:
    funcionarios = db.query(Funcionario).filter(Funcionario.empresa_id == empresa_id).all()
    por_codigo = {str(funcionario.codigo).strip(): funcionario for funcionario in funcionarios if funcionario.codigo}
    por_nome = {chave_texto(funcionario.nome): funcionario for funcionario in funcionarios}
    return por_codigo, por_nome


def enriquecer_previa(
    parsed: list[dict],
    competencia: Competencia,
    db: Session,
) -> tuple[list[dict], list[dict]]:
    por_codigo, por_nome = mapa_funcionarios(db, competencia.empresa_id)
    funcionarios_preview = []
    marcacoes_preview = []

    for funcionario_parse in parsed:
        codigo = funcionario_parse.get("codigo")
        nome = funcionario_parse.get("nome")
        funcionario = None
        if codigo:
            funcionario = por_codigo.get(str(codigo).strip())
        if not funcionario:
            funcionario = por_nome.get(chave_texto(nome))

        funcionario_preview = {
            **funcionario_parse,
            "funcionario_id": funcionario.id if funcionario else None,
            "funcionario_encontrado": funcionario is not None,
        }
        funcionarios_preview.append(funcionario_preview)

        for marcacao in funcionario_parse["marcacoes"]:
            observacoes = marcacao.get("observacoes")
            if not funcionario:
                aviso = "Funcionário não cadastrado para esta empresa"
                observacoes = f"{observacoes}; {aviso}" if observacoes else aviso
            marcacoes_preview.append(
                {
                    "competencia_id": competencia.id,
                    "empresa_id": competencia.empresa_id,
                    "funcionario_id": funcionario.id if funcionario else None,
                    "funcionario_encontrado": funcionario is not None,
                    "funcionario": nome,
                    "codigo": codigo,
                    "data": marcacao["data"],
                    "entrada": marcacao["entrada"],
                    "saida_almoco": marcacao["saida_almoco"],
                    "retorno_almoco": marcacao["retorno_almoco"],
                    "saida": marcacao["saida"],
                    "status": marcacao["status"],
                    "status_dia": marcacao["status_dia"],
                    "origem": "xlsx_importado",
                    "conferido": False,
                    "observacoes": observacoes,
                    "horarios_extraidos": marcacao["horarios_extraidos"],
                }
            )

    return funcionarios_preview, marcacoes_preview


@router.post("/xlsx-ponto-generico", status_code=status.HTTP_201_CREATED)
def importar_xlsx_ponto_generico(
    competencia_id: int = Form(...),
    empresa_id: int = Form(...),
    mes: int = Form(...),
    ano: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    empresa = db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")

    competencia = db.get(Competencia, competencia_id)
    if not competencia:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")
    if competencia.empresa_id != empresa_id:
        raise HTTPException(status_code=400, detail="Competência não pertence à empresa informada.")
    if competencia.mes != mes or competencia.ano != ano:
        raise HTTPException(status_code=400, detail="Mês/ano não correspondem à competência informada.")

    registro = salvar_arquivo_original(db, competencia, arquivo)
    caminho_arquivo = BACKEND_DIR / registro.caminho_arquivo
    parsed = parse_xlsx_ponto_generico(str(caminho_arquivo), mes=mes, ano=ano, empresa_id=empresa_id)
    funcionarios_preview, marcacoes_preview = enriquecer_previa(parsed, competencia, db)

    return {
        "arquivo": {
            "id": registro.id,
            "nome_original": registro.nome_original,
            "caminho_arquivo": registro.caminho_arquivo,
        },
        "competencia_id": competencia.id,
        "empresa_id": empresa.id,
        "total_funcionarios": len(funcionarios_preview),
        "total_marcacoes": len(marcacoes_preview),
        "total_salvaveis": sum(1 for item in marcacoes_preview if item["funcionario_id"]),
        "funcionarios": funcionarios_preview,
        "marcacoes": marcacoes_preview,
    }
