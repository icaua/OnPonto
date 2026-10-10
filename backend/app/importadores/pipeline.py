import unicodedata
from datetime import date, time
from pathlib import Path
from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy.orm import Session
from app.database.models import ArquivoRecebido, Competencia, Funcionario
from app.database.session import BACKEND_DIR, UPLOADS_DIR
from app.importadores.deteccao import (
    ADAPTADORES_TXT,
    ADAPTADORES_XLSX,
    detectar_adaptadores_txt,
    detectar_adaptadores_xlsx,
)
from app.importadores import ignorados
from app.importadores.schemas import ConfirmacaoImportacao, IdentificacaoIgnoradaCreate
from app.importadores.txt_generico import parse_txt_generico
from app.importadores.txt_id_tempo_maquina import parse_txt_id_tempo_maquina
from app.importadores.txt_log_relogio import parse_txt_log_relogio
from app.importadores.xlsx_cartao_ponto import parse_xlsx_cartao_ponto
from app.importadores.xlsx_ponto_generico import parse_xlsx_ponto_generico


EXTENSOES_SUPORTADAS = (".txt", ".xlsx")
NOMES_ADAPTADORES = {adaptador.NOME_ADAPTER for adaptador in (*ADAPTADORES_TXT, *ADAPTADORES_XLSX)}
FUNCOES_PARSE = {
    "txt_log_relogio": parse_txt_log_relogio,
    "txt_id_tempo_maquina": parse_txt_id_tempo_maquina,
    "txt_generico": parse_txt_generico,
    ADAPTADORES_XLSX[0].NOME_ADAPTER: parse_xlsx_ponto_generico,
    ADAPTADORES_XLSX[1].NOME_ADAPTER: parse_xlsx_cartao_ponto,
}


def caminho_arquivo_recebido(registro: ArquivoRecebido, uploads_dir=UPLOADS_DIR) -> Path:
    caminho = Path(registro.caminho_arquivo)
    if not caminho.is_absolute():
        caminho = BACKEND_DIR / caminho
    caminho = caminho.resolve()
    if not caminho.is_relative_to(uploads_dir.resolve()):
        raise HTTPException(status_code=400, detail="Caminho do arquivo de origem inválido.")
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail="Arquivo original não encontrado.")
    return caminho


def detectar_adaptador(caminho: Path, extensao: str) -> tuple[object, bytes | str]:
    """Detecta qual adaptador reconhece o arquivo. Devolve o módulo do
    adaptador e o argumento já preparado para chamar sua função de parse.
    Levanta HTTPException(400) se nenhum ou mais de um adaptador reconhecer."""

    if extensao == ".txt":
        conteudo = caminho.read_bytes()
        encontrados = detectar_adaptadores_txt(conteudo)
        argumento_parse: bytes | str = conteudo
    elif extensao == ".xlsx":
        from app.importadores.seguranca_xlsx import validar
        validar(caminho)
        try:
            workbook = load_workbook(caminho, data_only=True)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Não foi possível ler o arquivo XLSX enviado.") from exc
        try:
            encontrados = detectar_adaptadores_xlsx(workbook)
        finally:
            workbook.close()
        argumento_parse = str(caminho)
    else:
        raise HTTPException(status_code=400, detail="Envie um arquivo .txt ou .xlsx.")

    if not encontrados:
        raise HTTPException(
            status_code=400,
            detail="Formato de arquivo não reconhecido. Nenhum adaptador soube interpretar este arquivo.",
        )
    if len(encontrados) > 1:
        raise HTTPException(
            status_code=400,
            detail="Mais de um adaptador reconheceu este arquivo. Revise o conteúdo antes de importar.",
        )
    return encontrados[0], argumento_parse


def gerar_previa(db: Session, competencia: Competencia, registro: ArquivoRecebido, uploads_dir=UPLOADS_DIR) -> tuple[object, dict]:
    """Interpreta o arquivo salvo sem gravar nada."""
    caminho = caminho_arquivo_recebido(registro, uploads_dir)
    extensao = Path(registro.nome_original).suffix.lower()
    funcionarios = db.query(Funcionario).filter(Funcionario.empresa_id == competencia.empresa_id).all()

    adaptador, argumento_parse = detectar_adaptador(caminho, extensao)

    try:
        resultado = FUNCOES_PARSE[adaptador.NOME_ADAPTER](
            argumento_parse,
            arquivo_nome=registro.nome_original,
            mes=competencia.mes,
            ano=competencia.ano,
            funcionarios=funcionarios,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    preview = resultado["registros"]
    from app.funcionarios.historico_escalas import ResolvedorEscalas
    from app.apuracao import adaptadores
    from app.dominio.contratos import MarcacoesDoDia
    from app.dominio.apuracao import apurar_dia
    from dataclasses import replace
    resolvedor = ResolvedorEscalas(db,competencia.empresa_id)
    # Preserva os adapters homologados, mas sinaliza associações divergentes
    # antes da seleção automática na prévia operacional.
    por_id = {f.id: f for f in funcionarios}
    def nome_comparavel(valor):
        texto = unicodedata.normalize("NFKD", str(valor or ""))
        return " ".join("".join(c for c in texto if not unicodedata.combining(c)).casefold().split())
    for item in preview:
        info = item["funcionario"]
        candidato = por_id.get(info.get("id"))
        if candidato and not item["fora_da_competencia"] and len(item["batidas_originais"])==2:
            dia = date.fromisoformat(item["data"])
            regra = resolvedor.regra_no_dia(candidato,dia)
            if regra and regra.tipo_intervalo is not None:
                interpretacao=item["interpretacao"]
                m=MarcacoesDoDia(0,dia,entrada=hora_interpretada(interpretacao.get("entrada")),
                    saida=hora_interpretada(interpretacao.get("saida")))
                calculo=apurar_dia(replace(adaptadores.funcionario(candidato),escala=regra),m)
                item["avaliacao_escala"]={"disponibilidade":calculo.disponibilidade,"trabalhados_minutos":calculo.trabalhados_minutos,
                    "intervalo":calculo.dados_legados.get("intervalo_aplicado"),"pendencia":calculo.pendencia}
        if candidato and adaptador.NOME_ADAPTER.startswith("txt_"):
            codigo = info.get("codigo_origem")
            nome = info.get("nome_origem")
            divergente = (codigo and str(codigo) != str(candidato.codigo or "")) or (
                nome and nome_comparavel(nome) != nome_comparavel(candidato.nome)
            )
            if divergente:
                item["selecionado"] = False
                item["status"] = "conferir"
                item["pendencias"].append("ID ou nome diverge do cadastro sugerido; confirme a associação antes de selecionar este registro.")
    return adaptador, resultado



def hora_interpretada(valor):
    return time.fromisoformat(valor) if valor else None
