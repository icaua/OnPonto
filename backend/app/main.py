from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.arquivos.routes import router as arquivos_router
from app.apuracao.routes import router as apuracao_router
from app.competencias.routes import router as competencias_router
from app.database.migrations import aplicar_migracoes_compativeis
from app.database.session import Base, engine
from app.empresas.routes import router as empresas_router
from app.escalas.routes import router as escalas_router
from app.funcionarios.routes import router as funcionarios_router
from app.importadores.routes import router as importadores_router
from app.marcacoes.routes import router as marcacoes_router
from app.relatorios.routes import router as relatorios_router
from app.database import models  # noqa: F401
from app.competencias.preservacao import preservar_fechamentos_legados
from app.ocorrencias.routes import router as ocorrencias_router
from app.calendario.routes import router as calendario_router
from app.banco_horas.routes import router as banco_horas_router


app = FastAPI(
    title="On Ponto API",
    description="MVP para conferência e apuração de ponto recebido por escritório contábil.",
    version="1.0.0-rc.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.on_event("startup")
def criar_tabelas() -> None:
    Base.metadata.create_all(bind=engine)
    aplicar_migracoes_compativeis(engine)
    preservar_fechamentos_legados(engine)


@app.get("/")
def raiz() -> dict[str, str]:
    return {
        "nome": "On Ponto API",
        "status": "online",
        "docs": "/docs",
    }


app.include_router(empresas_router)
app.include_router(escalas_router)
app.include_router(funcionarios_router)
app.include_router(competencias_router)
app.include_router(arquivos_router)
app.include_router(importadores_router)
app.include_router(marcacoes_router)
app.include_router(apuracao_router)
app.include_router(relatorios_router)
app.include_router(ocorrencias_router)
app.include_router(calendario_router)
app.include_router(banco_horas_router)
