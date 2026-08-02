from html import escape
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.apuracao.service import apurar_competencia
from app.database.session import get_db


router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


def ajustar_larguras(ws) -> None:
    for coluna in ws.columns:
        tamanho = max(len(str(celula.value or "")) for celula in coluna)
        ws.column_dimensions[get_column_letter(coluna[0].column)].width = min(max(tamanho + 2, 12), 42)


def estilizar_cabecalho(ws) -> None:
    preenchimento = PatternFill("solid", fgColor="1F6F68")
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = preenchimento


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
            "Observações",
        ]
    )
    for item in resultado["resumo"]:
        ws_resumo.append(
            [
                resultado["empresa"]["nome"],
                resultado["competencia"]["label"],
                item["funcionario"],
                item["atrasos"],
                item["extras"],
                item["faltas"],
                item["atestados"],
                item["pendencias"],
                item["observacoes"],
            ]
        )
    estilizar_cabecalho(ws_resumo)
    ajustar_larguras(ws_resumo)

    ws_marcacoes = wb.create_sheet("Marcações")
    ws_marcacoes.append(
        [
            "Data",
            "Funcionário",
            "Entrada",
            "Saída Almoço",
            "Retorno Almoço",
            "Saída",
            "Status do Dia",
            "Horas Trabalhadas",
            "Atraso",
            "Extra",
            "Conferido",
            "Observações",
        ]
    )
    for item in resultado["marcacoes"]:
        ws_marcacoes.append(
            [
                item["data"],
                item["funcionario"],
                item["entrada"],
                item["saida_almoco"],
                item["retorno_almoco"],
                item["saida"],
                item["status_dia"],
                item["horas_trabalhadas"],
                item["atraso"],
                item["extra"],
                "Sim" if item["conferido"] else "Não",
                item["observacoes"],
            ]
        )
    estilizar_cabecalho(ws_marcacoes)
    ajustar_larguras(ws_marcacoes)

    arquivo = BytesIO()
    wb.save(arquivo)
    arquivo.seek(0)

    nome = f"apuracao_on_ponto_{resultado['competencia']['label'].replace('/', '-')}.xlsx"
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
          <td>{escape(item['atrasos'])}</td>
          <td>{escape(item['extras'])}</td>
          <td>{item['faltas']}</td>
          <td>{item['atestados']}</td>
          <td>{item['pendencias']}</td>
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
