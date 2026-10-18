"""Reproduz os três contratos do CI usando um alias 8.3 real do Windows."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name == 'nt', 'Aliases 8.3 são específicos do Windows.')
class CaminhosWindowsTest(unittest.TestCase):
    def test_backup_upload_e_restore_com_raiz_temporaria_8dot3(self):
        import ctypes
        with tempfile.TemporaryDirectory(prefix='onponto-caminho-longo-ficticio-') as temp:
            obter_curto = ctypes.windll.kernel32.GetShortPathNameW
            obter_curto.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
            obter_curto.restype = ctypes.c_uint
            tamanho = obter_curto(temp, None, 0)
            self.assertGreater(tamanho, 0)
            buffer = ctypes.create_unicode_buffer(tamanho)
            self.assertGreater(obter_curto(temp, buffer, tamanho), 0)
            curto = buffer.value
            if Path(curto) == Path(temp).resolve():
                self.skipTest('Volume sem aliases 8.3 disponíveis.')
            self.assertTrue(Path(curto).samefile(temp))
            nomes = [
                'test_backup_automatico.BackupAutomaticoTest.test_pre_migracao_preserva_versao_dados_e_integridade',
                'test_evidencias_propostas.EvidenciasPropostasTest.test_upload_generico_valida_conteudo_hash_download_e_caminho',
                'test_recuperacao_conjunto.RecuperacaoConjuntoTest.test_restore_portatil_preserva_evidencia_e_migracao_repetida',
                'test_recuperacao_conjunto.RecuperacaoConjuntoTest.test_restore_falha_apos_copia_limpa_apenas_destino_novo',
            ]
            with patch.object(tempfile, 'tempdir', curto):
                resultado = unittest.TestResult()
                unittest.defaultTestLoader.loadTestsFromNames(nomes).run(resultado)
            self.assertEqual(resultado.testsRun, 4)
            self.assertTrue(resultado.wasSuccessful(), '\n'.join(tb for _, tb in resultado.errors + resultado.failures))
