import unittest
import test_cadastros_api as fixture


class DemissaoApiTest(unittest.TestCase):
    setUpClass = classmethod(fixture.CadastrosApiTest.setUpClass.__func__)
    encerrar_api = classmethod(fixture.CadastrosApiTest.encerrar_api.__func__)
    requisicao = fixture.CadastrosApiTest.requisicao
    criar_empresa = fixture.CadastrosApiTest.criar_empresa

    def test_criar_editar_preservar_limpar_e_validar_intervalo_completo(self):
        e=self.criar_empresa('Demissão API')
        payload={'empresa_id':e['id'],'nome':'Pessoa','data_admissao':'2026-06-10','data_demissao':'2026-06-15'}
        self.assertEqual(self.requisicao('POST','/funcionarios',dict(payload,data_demissao='2026-06-09'))[0],422)
        status,f=self.requisicao('POST','/funcionarios',payload)
        self.assertEqual(status,201,f)
        url=f'/funcionarios/{f["id"]}'
        self.assertEqual(self.requisicao('PATCH',url,{'cargo':'Cargo'})[1]['data_demissao'],'2026-06-15')
        for invalido in [{'data_demissao':'2026-06-09'},{'data_admissao':'2026-06-16'},{'data_demissao':'2026-06-31'}]:
            self.assertEqual(self.requisicao('PATCH',url,invalido)[0],422,invalido)
        self.assertEqual(self.requisicao('GET',url)[1]['data_demissao'],'2026-06-15')
        self.assertIsNone(self.requisicao('PATCH',url,{'data_demissao':None})[1]['data_demissao'])
        self.assertEqual(self.requisicao('PATCH',url,{'data_admissao':'2026-06-16','data_demissao':'2026-06-16'})[0],200)
