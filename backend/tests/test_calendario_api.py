import unittest

import test_cadastros_api as fixture


class CalendarioApiTest(unittest.TestCase):
    setUpClass = classmethod(fixture.CadastrosApiTest.setUpClass.__func__)
    encerrar_api = classmethod(fixture.CadastrosApiTest.encerrar_api.__func__)
    requisicao = fixture.CadastrosApiTest.requisicao
    criar_empresa = fixture.CadastrosApiTest.criar_empresa

    def novo_evento(self, **kwargs):
        return self.requisicao('POST','/calendario',dict(dict(nome='Data teste',data='2026-06-18',
            tipo='FERIADO',abrangencia='NACIONAL'),**kwargs))

    def test_crud_listagem_filtros_recorrencia_desativacao(self):
        status,e = self.novo_evento(nome='Recorrente API',data='2024-06-18',recorrente=True)
        self.assertEqual(status,201,e)
        self.assertIn('created_at',e)
        self.assertEqual(self.requisicao('GET',f'/calendario/{e["id"]}')[1],e)
        status,lista = self.requisicao('GET','/calendario?ano=2027&tipo=FERIADO&abrangencia=NACIONAL')
        self.assertEqual(status,200)
        self.assertIn(e['id'],[x['id'] for x in lista])
        self.assertNotIn(e['id'],[x['id'] for x in self.requisicao('GET','/calendario?ano=2027&tipo=DATA_COMEMORATIVA')[1]])
        status,atual = self.requisicao('PATCH',f'/calendario/{e["id"]}',{'ativo':False,'descricao':'Desativado'})
        self.assertEqual(status,200,atual)
        self.assertFalse(atual['ativo'])
        self.assertEqual(atual['nome'],e['nome'])
        self.assertEqual(self.requisicao('GET','/calendario/999999')[0],404)

    def test_validacoes_escopos_campos_obrigatorios_e_empresa(self):
        for dados in [{'abrangencia':'ESTADUAL'}, {'abrangencia':'MUNICIPAL','uf':'SP'},
            {'abrangencia':'MUNICIPAL','uf':'XX','municipio':'São Paulo'}, {'abrangencia':'EMPRESA'},
            {'abrangencia':'EMPRESA','empresa_id':999999}, {'tipo':'OUTRO'}, {'nome':'   '}, {'data':'2026-02-30'}]:
            status,result = self.novo_evento(**dados)
            self.assertEqual(status,422,(dados,result))
        empresa = self.criar_empresa('Empresa Calendário API')
        for dados in [{'abrangencia':'NACIONAL'}, {'abrangencia':'ESTADUAL','uf':'sp'},
            {'abrangencia':'MUNICIPAL','uf':'SP','municipio':'São Paulo'},
            {'abrangencia':'EMPRESA','empresa_id':empresa['id']}]:
            self.assertEqual(self.novo_evento(**dados)[0],201,dados)

    def test_patch_valida_estado_completo_sem_perder_campos(self):
        _,e = self.novo_evento(abrangencia='ESTADUAL',uf='SP')
        endpoint = f'/calendario/{e["id"]}'
        self.assertEqual(self.requisicao('PATCH',endpoint,{'abrangencia':'MUNICIPAL'})[0],422)
        self.assertEqual(self.requisicao('PATCH',endpoint,{'data':None})[0],422)
        self.assertEqual(self.requisicao('GET',endpoint)[1]['abrangencia'],'ESTADUAL')
        status,e = self.requisicao('PATCH',endpoint,{'abrangencia':'NACIONAL'})
        self.assertEqual(status,200,e)
        self.assertIsNone(e['uf'])
        self.assertIsNone(e['municipio'])
        self.assertIsNone(e['empresa_id'])

    def test_admissao_create_read_patch_limpar_data_invalida(self):
        empresa = self.criar_empresa('Admissão API')
        status,f = self.requisicao('POST','/funcionarios',{'empresa_id':empresa['id'],'nome':'Pessoa','data_admissao':'2026-06-18'})
        self.assertEqual(status,201,f)
        endpoint = f'/funcionarios/{f["id"]}'
        self.assertEqual(self.requisicao('GET',endpoint)[1]['data_admissao'],'2026-06-18')
        self.assertEqual(self.requisicao('PATCH',endpoint,{'cargo':'Cargo'})[1]['data_admissao'],'2026-06-18')
        self.assertEqual(self.requisicao('PATCH',endpoint,{'data_admissao':'2026-06-31'})[0],422)
        self.assertIsNone(self.requisicao('PATCH',endpoint,{'data_admissao':None})[1]['data_admissao'])

    def test_calendario_apuracao_api_desativar_nao_deixa_feriado_gravado(self):
        empresa = self.criar_empresa('Motor API isolado')
        _,escala = self.requisicao('POST','/escalas',{'empresa_id':empresa['id'],'nome':'Escala','modo_apuracao':'carga_horaria',
            'jornada_seg_sex_horas':8,'jornada_sabado_horas':4,'regime_sabado':'nao_trabalha','regime_domingo':'nao_trabalha'})
        _,f = self.requisicao('POST','/funcionarios',{'empresa_id':empresa['id'],'nome':'Pessoa','escala_id':escala['id'],'data_admissao':'2026-06-18'})
        _,c = self.requisicao('POST','/competencias',{'empresa_id':empresa['id'],'mes':6,'ano':2026})
        _,e = self.novo_evento(abrangencia='EMPRESA',empresa_id=empresa['id'])
        url = f'/apuracao?competencia_id={c["id"]}'
        status,r = self.requisicao('GET',url)
        self.assertEqual(status,200,r)
        self.assertEqual(r['resumo'][0]['dias_processados'],13)
        self.assertEqual(r['marcacoes'][0]['status_dia'],'feriado')
        raw = self.requisicao('GET',f'/marcacoes?competencia_id={c["id"]}')[1]
        self.assertEqual(len(raw),13)
        self.assertEqual(raw[0]['status_dia'],'normal')
        self.requisicao('PATCH',f'/calendario/{e["id"]}',{'ativo':False})
        self.assertEqual(self.requisicao('GET',url)[1]['marcacoes'][0]['status_dia'],'normal')
