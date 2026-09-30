"""Liberação de arquivos temporários após encerrar subprocessos no Windows."""
import tempfile
import time


class TemporaryDirectory(tempfile.TemporaryDirectory):
    def cleanup(self):
        for tentativa in range(20):
            try:
                return super().cleanup()
            except PermissionError as exc:
                if getattr(exc, "winerror", None) != 32 or tentativa == 19:
                    raise
                time.sleep(0.1)


def preparar_fechamento_valido(db, competencia):
    """Fixture explícita para testes de snapshot/imutabilidade, sem burlar validação.

    Calendário vazio recebe folga fictícia; registros com batidas são preservados.
    Ocorrências existentes continuam sendo interpretadas pelo motor real.
    """
    from app.apuracao.service import gerar_dias_faltantes
    from app.database.models import MarcacaoPonto
    gerar_dias_faltantes(db, competencia)
    for m in db.query(MarcacaoPonto).filter_by(competencia_id=competencia.id):
        if not any((m.entrada, m.saida_almoco, m.retorno_almoco, m.saida)) and m.status_dia == 'normal':
            m.status_dia = 'folga'
        m.conferido = True
    db.commit()
