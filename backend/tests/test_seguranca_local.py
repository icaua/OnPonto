import json,os,socket,subprocess,sys,time,unittest,sqlite3,zlib,struct
from pathlib import Path
from urllib.request import Request,urlopen as anonimo
from urllib.error import HTTPError
from unittest.mock import patch
from io import BytesIO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_support import TemporaryDirectory
from app.seguranca.arquivos import validar_conteudo
from fastapi import HTTPException

class SegurancaHTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=TemporaryDirectory(prefix='onponto-seguranca-ficticio-');cls.root=Path(cls.temp.name)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        cls.base=f'http://127.0.0.1:{port}'
        env={**os.environ,'ONPONTO_DATABASE_URL':'sqlite:///'+str(cls.root/'ficticio.db'),'ONPONTO_UPLOADS_DIR':str(cls.root/'uploads')}
        cls.processo=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--log-level','warning'],cwd=Path(__file__).resolve().parents[1],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with anonimo(cls.base,timeout=.5):return
            except OSError:time.sleep(.05)
        cls.processo.terminate();cls.processo.wait();cls.temp.cleanup();raise RuntimeError('API fictícia não iniciou.')
    @classmethod
    def tearDownClass(cls):cls.processo.terminate();cls.processo.wait(timeout=10);cls.temp.cleanup()
    def req(self,caminho='/',metodo='GET',headers=None,body=None):
        try:
            with anonimo(Request(self.base+caminho,method=metodo,headers=headers or {},data=body),timeout=5) as r:return r.status,dict(r.headers),r.read()
        except HTTPError as r:return r.code,dict(r.headers),r.read()
    def iniciar(self):
        codigo,cabecalho,body=self.req('/sessao/local',headers={'Origin':'http://127.0.0.1:5500'})
        self.assertEqual(codigo,200)
        cookie=cabecalho['set-cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=strict',cookie)
        self.assertEqual(cabecalho['access-control-allow-origin'],'http://127.0.0.1:5500')
        return {'Cookie':cookie.split(';')[0],'X-OnPonto-CSRF':json.loads(body)['csrf'],'Content-Type':'application/json'}
    def test_leitura_e_operacao_sem_sessao_recusadas(self):
        for caminho in ('/empresas','/funcionarios','/arquivos/1/download','/ocorrencias/1/anexo','/relatorios/excel?competencia_id=1'):
            self.assertEqual(self.req(caminho)[0],401)
        self.assertEqual(self.req('/empresas','POST',body=b'{}')[0],401)
        codigo,headers,body=self.req();self.assertEqual(codigo,200);self.assertEqual(json.loads(body)['status'],'online')
        self.assertEqual(headers['cache-control'],'no-store');self.assertEqual(headers['x-content-type-options'],'nosniff')
    def test_origem_host_e_preflight(self):
        for origem in ('https://invasor.example','null','http://127.0.0.1:9999'):
            self.assertEqual(self.req('/sessao/local',headers={'Origin':origem})[0],403)
        self.assertEqual(self.req(headers={'Host':'invasor.example'})[0],403)
        self.assertEqual(self.req('/empresas','OPTIONS',headers={'Origin':'https://invasor.example','Access-Control-Request-Method':'POST'})[0],403)
        codigo,headers,_=self.req('/empresas','OPTIONS',headers={'Origin':'http://127.0.0.1:5500','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'x-onponto-csrf'})
        self.assertEqual(codigo,200);self.assertEqual(headers['access-control-allow-credentials'],'true')
        self.assertEqual(self.req('/sessao/local',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
    def test_csrf_obrigatorio_associado_a_sessao(self):
        headers=self.iniciar();body=b'{"nome":"FICTICIA SEGURANCA"}'
        sem={k:v for k,v in headers.items() if k!='X-OnPonto-CSRF'}
        self.assertEqual(self.req('/empresas','POST',headers=sem,body=body)[0],403)
        self.assertEqual(self.req('/empresas','POST',headers={**headers,'X-OnPonto-CSRF':'invalido'},body=body)[0],403)
        segunda=self.iniciar();self.assertNotEqual(headers['X-OnPonto-CSRF'],segunda['X-OnPonto-CSRF'])
        self.assertEqual(self.req('/empresas','POST',headers={**headers,'Cookie':segunda['Cookie']},body=body)[0],403)
        self.assertEqual(self.req('/empresas','POST',headers=headers,body=body)[0],201)
        codigo,_,body=self.req('/empresas',headers=headers);self.assertEqual(codigo,200);self.assertEqual(len(json.loads(body)),1)
    def test_requisicao_excessiva_recusada_antes_do_parser(self):
        headers=self.iniciar()
        self.assertEqual(self.req('/arquivos','POST',headers={**headers,'Content-Length':str(27*1024*1024)},body=b'x')[0],413)

class ConteudoAdversarialTest(unittest.TestCase):
    def test_pdf_bomba_pagina_ativo_e_extensao_falsa(self):
        bomba=zlib.compress(b'A'*(21*1024*1024))
        casos=[('.pdf',b'<html>falso</html>'),('.pdf',b'%PDF-1.4\n/Count 999999\n%%EOF'),('.pdf',b'%PDF-1.4\n/JavaScript (x)\n%%EOF'),('.pdf',b'%PDF-1.4\n<< /Filter /FlateDecode >>\nstream\n'+bomba+b'\nendstream\n%%EOF'),('.png',b'\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR'+struct.pack('>II',100000,100000)+b'IEND'),('.txt',b'MZ\x00binario')]
        with TemporaryDirectory(prefix='onponto-bomba-') as temp:
            for extensao,dados in casos:
                caminho=Path(temp)/('ficticio'+extensao);caminho.write_bytes(dados)
                with self.assertRaises(HTTPException):validar_conteudo(caminho,extensao)
    def test_sessao_expirada_nao_e_aceita(self):
        from app.seguranca.sessao import SESSOES,chave,sessao,COOKIE
        from types import SimpleNamespace
        token='FICTICIO';SESSOES[chave(token)]={'csrf':'FICTICIO','expira':100}
        try:
            with patch('app.seguranca.sessao.time.monotonic',return_value=101):self.assertIsNone(sessao(SimpleNamespace(cookies={COOKIE:token})))
        finally:SESSOES.pop(chave(token),None)

    def test_xlsx_entidade_e_compressao_nao_suportada(self):
        from zipfile import ZipFile,ZIP_STORED,ZIP_LZMA
        with TemporaryDirectory(prefix='onponto-xml-ficticio-') as temp:
            caminho=Path(temp)/'ficticio.xlsx'
            for compressao,xml in ((ZIP_STORED,b'<!DOCTYPE x [<!ENTITY a "b">]><x/>'),(ZIP_LZMA,b'<x/>')):
                with ZipFile(caminho,'w',compression=compressao) as z:
                    z.writestr('[Content_Types].xml',xml);z.writestr('xl/workbook.xml',b'<x/>')
                with self.assertRaises(HTTPException):validar_conteudo(caminho,'.xlsx')
