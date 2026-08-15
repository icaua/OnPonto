from datetime import date, time, timedelta
from html import escape
from io import BytesIO
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.apuracao.service import apurar_competencia
from app.database.session import get_db


router = APIRouter(prefix="/relatorios", tags=["Relatórios"])

FORMATO_DATA_EXCEL = "dd/mm/yyyy"
FORMATO_HORA_EXCEL = "hh:mm"
FORMATO_DURACAO_EXCEL = "[h]:mm"

ROTULOS_SITUACAO = {
    "conferido": "Conferido",
    "pendente": "Pendente",
    "indisponivel": "Indisponível",
}

ROTULOS_STATUS_DIA = {
    "normal": "Normal",
    "falta": "Falta",
    "atestado": "Atestado",
    "folga": "Folga",
    "feriado": "Feriado",
    "domingo": "Domingo",
    "sem_expediente": "Sem expediente",
    "trabalho_externo": "Trabalho externo",
    "afastamento": "Afastamento",
    "pendente": "Pendente",
    "pendente_conferencia": "Pendente de conferência",
}


def texto_seguro_excel(valor: object) -> str | None:
    if valor is None:
        return None
    texto = str(valor)
    if not texto:
        return None
    if texto.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + texto
    return texto


def slug_nome_arquivo(valor: str) -> str:
    normalizado = unicodedata.normalize("NFKD", valor)
    ascii_seguro = normalizado.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_seguro).strip("_").lower()
    return slug[:80] or "empresa"


def data_excel(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def hora_excel(valor: str | None) -> time | None:
    if not valor:
        return None
    try:
        return time.fromisoformat(valor)
    except ValueError:
        return None


def duracao_excel(minutos: int | None) -> timedelta | None:
    return timedelta(minutes=minutos) if minutos is not None else None


def valor_calculado_excel(valor: object) -> object:
    return "Indisponível" if valor is None else valor


def saldo_excel(item: dict) -> timedelta | str | None:
    if item.get("pendente_calculo"):
        return None
    atraso = item.get("atraso_minutos")
    extra = item.get("extra_minutos")
    if atraso is None or extra is None:
        return None
    saldo_minutos = extra - atraso
    if saldo_minutos < 0:
        horas, minutos = divmod(abs(saldo_minutos), 60)
        return f"-{horas:02d}:{minutos:02d}"
    return duracao_excel(saldo_minutos)


def rotulo_situacao(valor: str | None) -> str:
    return ROTULOS_SITUACAO.get(valor or "", "Indisponível")


def rotulo_status_dia(valor: str | None) -> str:
    if valor in ROTULOS_STATUS_DIA:
        return ROTULOS_STATUS_DIA[valor]
    texto = str(valor or "").replace("_", " ").strip()
    return texto[:1].upper() + texto[1:] if texto else "Indisponível"


def ajustar_larguras(ws) -> None:
    for coluna in ws.columns:
        tamanho = max(len(str(celula.value or "")) for celula in coluna)
        ws.column_dimensions[get_column_letter(coluna[0].column)].width = min(max(tamanho + 2, 12), 42)


def estilizar_cabecalho(ws) -> None:
    preenchimento = PatternFill("solid", fgColor="16845B")
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = preenchimento


def finalizar_planilha(ws) -> None:
    estilizar_cabecalho(ws)
    alinhamento = Alignment(vertical="top", wrap_text=True)
    for linha in ws.iter_rows():
        for celula in linha:
            celula.alignment = alinhamento
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ajustar_larguras(ws)


@router.get("/excel")
def exportar_excel(
    competencia_id: int = Query(...),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    resultado = apurar_competencia(db, competencia_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")

    wb = Workbook()
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    ws_resumo.append(
        [
            "Empresa",
            "Competência",
            "Funcionário",
            "Atrasos",
            "Extras",
            "Faltas",
            "Atestados",
            "Pendências",
            "Situação",
            "Observações",
        ]
    )
    for item in resultado["resumo"]:
        ws_resumo.append(
            [
                texto_seguro_excel(resultado["empresa"]["nome"]),
                resultado["competencia"]["label"],
                texto_seguro_excel(item["funcionario"]),
                valor_calculado_excel(duracao_excel(item["atrasos_minutos"])),
                valor_calculado_excel(duracao_excel(item["extras_minutos"])),
                valor_calculado_excel(item["faltas"]),
                valor_calculado_excel(item["atestados"]),
                valor_calculado_excel(item["pendencias"]),
                rotulo_situacao(item.get("situacao")),
                texto_seguro_excel(item["observacoes"]),
            ]
        )
        ws_resumo.cell(ws_resumo.max_row, 4).number_format = FORMATO_DURACAO_EXCEL
        ws_resumo.cell(ws_resumo.max_row, 5).number_format = FORMATO_DURACAO_EXCEL
    finalizar_planilha(ws_resumo)

    ws_marcacoes = wb.create_sheet("Marcações")
    ws_marcacoes.append(
        [
            "Data",
            "Funcionário",
            "Entrada",
            "Saída intervalo",
            "Retorno",
            "Saída",
            "Jornada apurada",
            "Saldo",
            "Status",
            "Conferido",
            "Observações",
        ]
    )
    for item in resultado["marcacoes"]:
        ws_marcacoes.append(
            [
                data_excel(item["data"]),
                texto_seguro_excel(item["funcionario"]),
                hora_excel(item["entrada"]),
                hora_excel(item["saida_almoco"]),
                hora_excel(item["retorno_almoco"]),
                hora_excel(item["saida"]),
                (
                    "Indisponível"
                    if item.get("pendente_calculo")
                    else duracao_excel(item["horas_trabalhadas_minutos"])
                ),
                valor_calculado_excel(saldo_excel(item)),
                texto_seguro_excel(rotulo_status_dia(item.get("status_dia"))),
                "Sim" if item["conferido"] else "Não",
                texto_seguro_excel(item["observacoes"]),
            ]
        )
        linha = ws_marcacoes.max_row
        ws_marcacoes.cell(linha, 1).number_format = FORMATO_DATA_EXCEL
        for coluna in range(3, 7):
            ws_marcacoes.cell(linha, coluna).number_format = FORMATO_HORA_EXCEL
        ws_marcacoes.cell(linha, 7).number_format = FORMATO_DURACAO_EXCEL
        celula_saldo = ws_marcacoes.cell(linha, 8)
        celula_saldo.number_format = (
            FORMATO_DURACAO_EXCEL if isinstance(celula_saldo.value, timedelta) else "@"
        )
    finalizar_planilha(ws_marcacoes)

    arquivo = BytesIO()
    wb.save(arquivo)
    arquivo.seek(0)

    nome_empresa = slug_nome_arquivo(resultado["empresa"]["nome"])
    nome = (
        f"on_ponto_{nome_empresa}_"
        f"{resultado['competencia']['ano']:04d}-{resultado['competencia']['mes']:02d}.xlsx"
    )
    return StreamingResponse(
        arquivo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/impressao", response_class=HTMLResponse)
def relatorio_impressao(
    competencia_id: int = Query(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    resultado = apurar_competencia(db, competencia_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Competência não encontrada.")

    linhas_resumo = "\n".join(
        f"""
        <tr>
          <td>{escape(item['funcionario'])}</td>
          <td>{escape(str(item['atrasos'] if item['atrasos'] is not None else 'Indisponível'))}</td>
          <td>{escape(str(item['extras'] if item['extras'] is not None else 'Indisponível'))}</td>
          <td>{item['faltas'] if item['faltas'] is not None else 'Indisponível'}</td>
          <td>{item['atestados'] if item['atestados'] is not None else 'Indisponível'}</td>
          <td>{item['pendencias'] if item['pendencias'] is not None else 'Indisponível'}</td>
        </tr>
        """
        for item in resultado["resumo"]
    )

    if resultado["pendencias"]:
        linhas_pendencias = "\n".join(
            f"""
            <tr>
              <td>{escape(item['data'])}</td>
              <td>{escape(item['funcionario'])}</td>
              <td>{escape(item['pendencia_motivo'] or '')}</td>
              <td>{escape(item['observacoes'] or '')}</td>
            </tr>
            """
            for item in resultado["pendencias"]
        )
    else:
        linhas_pendencias = "<tr><td colspan='4'>Sem pendências.</td></tr>"

    html = f"""
    <!doctype html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Relatório On Ponto</title>
      <style>
        :root {{
          color: #1d252c;
          font-family: Arial, sans-serif;
        }}
        body {{
          margin: 0;
          background: #f4f7f6;
        }}
        main {{
          max-width: 980px;
          margin: 0 auto;
          padding: 32px;
          background: #fff;
          min-height: 100vh;
        }}
        header {{
          border-bottom: 2px solid #1f6f68;
          margin-bottom: 24px;
          padding-bottom: 16px;
        }}
        h1, h2 {{
          margin: 0 0 8px;
        }}
        .meta {{
          display: flex;
          gap: 18px;
          flex-wrap: wrap;
          color: #52616b;
          font-size: 14px;
        }}
        button {{
          border: 0;
          background: #1f6f68;
          color: #fff;
          border-radius: 6px;
          padding: 10px 14px;
          cursor: pointer;
          margin-bottom: 20px;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin: 12px 0 28px;
          font-size: 13px;
        }}
        th, td {{
          border: 1px solid #d7e0df;
          padding: 8px;
          text-align: left;
        }}
        th {{
          background: #e9f2f0;
        }}
        footer {{
          border-top: 1px solid #d7e0df;
          color: #52616b;
          font-size: 12px;
          padding-top: 12px;
        }}
        @media print {{
          body {{
            background: #fff;
          }}
          main {{
            padding: 0;
            max-width: none;
          }}
          button {{
            display: none;
          }}
        }}
      </style>
    </head>
    <body>
      <main>
        <button onclick="window.print()">Imprimir / Salvar PDF</button>
        <header>
          <h1>{escape(resultado['empresa']['nome'])}</h1>
          <div class="meta">
            <span>Competência: {escape(resultado['competencia']['label'])}</span>
            <span>Status: {escape(resultado['competencia']['status'])}</span>
            <span>Gerado em: {escape(resultado['gerado_em'])}</span>
          </div>
        </header>

        <section>
          <h2>Resumo por funcionário</h2>
          <table>
            <thead>
              <tr>
                <th>Funcionário</th>
                <th>Atrasos</th>
                <th>Extras</th>
                <th>Faltas</th>
                <th>Atestados</th>
                <th>Pendências</th>
              </tr>
            </thead>
            <tbody>{linhas_resumo}</tbody>
          </table>
        </section>

        <section>
          <h2>Pendências</h2>
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Funcionário</th>
                <th>Motivo</th>
                <th>Observações</th>
              </tr>
            </thead>
            <tbody>{linhas_pendencias}</tbody>
          </table>
        </section>

        <footer>On Ponto - relatório imprimível gerado pelo navegador.</footer>
      </main>
    </body>
    </html>
    """
    return HTMLResponse(html)
