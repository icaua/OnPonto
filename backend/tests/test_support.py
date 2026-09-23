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
