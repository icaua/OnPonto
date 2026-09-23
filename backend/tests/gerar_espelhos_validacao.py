"""Gera HTMLs fictícios, sem acessar o banco real, para medir layout no navegador."""
from pathlib import Path
from datetime import time

import test_espelho_ponto as fixtures
from app.database.models import Funcionario, MarcacaoPonto
from app.relatorios.routes import espelho_ponto_lote


def gerar():
    raiz = Path(__file__).resolve().parents[2]
    destino = raiz / 'logs'
    destino.mkdir(exist_ok=True)
    harness = (raiz / 'frontend/tests/medir-espelho.js').read_text(encoding='utf-8')

    def salvar(nome, html):
        html = html.replace('</body>', '<script>' + harness + '</script></body>')
        (destino / nome).write_text(html, encoding='utf-8')

    f = fixtures.EspelhoPontoTest()
    f.setUp()
    try:
        f.competencia.mes = 7
        for nome in ('Bruno Teste', 'Carla Teste'):
            f.db.add(Funcionario(empresa_id=f.empresa.id, nome=nome, codigo=nome[:3],
                                escala_id=f.escala.id, cargo='Analista'))
        f.db.commit()
        fixtures.apurar_competencia(f.db, f.competencia.id)
        for m in f.db.query(MarcacaoPonto).all():
            m.conferido = True
            m.origem = 'manual'
            if m.data.weekday() < 5:
                m.status_dia = 'normal'
                m.entrada, m.saida_almoco, m.retorno_almoco, m.saida = time(8), time(12), time(13), time(17)
            if m.data.day in (3, 14, 28):
                m.observacoes = 'Registro conferido com o funcionário; horário confirmado pelo responsável do departamento.'
        f.db.commit()
        salvar('espelho-retrato-31dias.html', f.html().text)
        salvar('espelhos-lote-31dias.html', espelho_ponto_lote(f.competencia.id, f.db).body.decode())
        m = f.db.query(MarcacaoPonto).filter_by(funcionario_id=f.funcionario.id).order_by(MarcacaoPonto.data).first()
        m.observacoes = ('Observação completa, com detalhes da conferência e justificativas do responsável. ' * 160) + 'FIM DA NOTA LONGA'
        f.db.commit()
        salvar('espelho-retrato-notas-longas.html', f.html().text)
    finally:
        f.doCleanups()


if __name__ == '__main__':
    gerar()
