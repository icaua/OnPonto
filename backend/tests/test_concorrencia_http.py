from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from urllib.error import HTTPError
from urllib.request import Request
from http_sessao import urlopen
import unittest

import test_cadastros_api as suporte


class ConcorrenciaHttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        suporte.CadastrosApiTest.setUpClass.__func__(cls)

    @classmethod
    def encerrar_api(cls):
        suporte.CadastrosApiTest.encerrar_api.__func__(cls)

    def enviar(self, metodo, caminho, payload=None, corpo=None, headers=None):
        if payload is not None:
            corpo = json.dumps(payload).encode()
            headers = {"Content-Type":"application/json"}
        request = Request(self.base_url + caminho, data=corpo, headers=headers or {}, method=metodo)
        try:
            with urlopen(request, timeout=15) as resposta:
                return resposta.status, json.load(resposta)
        except HTTPError as erro:
            return erro.code, json.load(erro)

    def cadastro(self, fechar=False):
        _, e = self.enviar("POST", "/empresas", {"nome":"FICTÍCIA concorrência"})
        _, s = self.enviar("POST", "/escalas", {"empresa_id":e["id"],"nome":"FICTÍCIA", "jornada_seg_sex_horas":8})
        _, f = self.enviar("POST", "/funcionarios", {"empresa_id":e["id"],"nome":"FICTÍCIO", "codigo":"F001", "escala_id":s["id"]})
        _, c = self.enviar("POST", "/competencias", {"empresa_id":e["id"],"mes":9,"ano":2026})
        marcacoes = []
        for n in range(1,31 if fechar else 2):
            status, m = self.enviar("POST", "/marcacoes", {"competencia_id":c["id"],"funcionario_id":f["id"],
                "data":f"2026-09-{n:02d}","status_dia":"folga", "conferido":fechar})
            self.assertEqual(status,201,m)
            marcacoes.append(m)
        return e,c,marcacoes

    def simultaneas(self, operacoes):
        barreira = Barrier(len(operacoes))
        def executar(operacao):
            barreira.wait(timeout=5)
            return operacao()
        with ThreadPoolExecutor(max_workers=len(operacoes)) as pool:
            return list(pool.map(executar, operacoes))

    def test_duas_janelas_patch_simultaneo_um_vence_outro_recebe_409(self):
        _,c,ms = self.cadastro()
        m = ms[0]
        rota = f'/marcacoes/{m["id"]}'
        respostas = self.simultaneas([
            lambda:self.enviar("PATCH",rota,{"observacoes":"janela A","revisao":m["revisao"]}),
            lambda:self.enviar("PATCH",rota,{"observacoes":"janela B","revisao":m["revisao"]})])
        self.assertEqual(sorted(r[0] for r in respostas),[200,409])
        vencedor = next(r[1] for r in respostas if r[0]==200)
        _,atual = self.enviar("GET",rota)
        self.assertEqual(atual["observacoes"],vencedor["observacoes"])
        self.assertGreater(atual["revisao"],m["revisao"])
        self.assertEqual(self.enviar("PATCH",rota,{"observacoes":"repetição", "revisao":m["revisao"]})[0],409)
        self.assertEqual(self.enviar("PATCH",rota,{"observacoes":"sem token"})[0],409)
        self.assertEqual(self.enviar("GET",rota)[1],atual)

    def test_patch_tardio_apos_fechamento_recusado(self):
        _,c,ms = self.cadastro(fechar=True)
        self.assertEqual(self.enviar("POST",f'/competencias/{c["id"]}/fechar',{})[0],200)
        m = ms[0]
        rota = f'/marcacoes/{m["id"]}'
        antes = self.enviar("GET",rota)[1]
        self.assertEqual(self.enviar("PATCH",rota,{"observacoes":"tardio","revisao":m["revisao"]})[0],409)
        self.assertEqual(self.enviar("GET",rota)[1],antes)
        self.assertEqual(self.enviar("POST",f'/competencias/{c["id"]}/fechar',{})[0],409)
        self.assertEqual(len(self.enviar("GET",f'/competencias/{c["id"]}/fechamentos')[1]),1)

    def test_lote_com_token_obsoleto_nao_confirma_outros_dias(self):
        _,c,ms = self.cadastro(fechar=True)
        for m in ms[:2]:
            status,atual = self.enviar("PATCH",f'/marcacoes/{m["id"]}',{"conferido":False,"revisao":m["revisao"]})
            self.assertEqual(status,200)
            m.update(atual)
        m = ms[0]
        self.enviar("PATCH",f'/marcacoes/{m["id"]}',{"observacoes":"nova revisão", "revisao":m["revisao"]})
        resposta = self.enviar("POST","/marcacoes/conferir-lote",{"competencia_id":c["id"],
            "marcacoes_ids":[m["id"] for m in ms[:2]], "revisoes":{m["id"]:m["revisao"] for m in ms[:2]}})
        self.assertEqual(resposta[0],409)
        for m in ms[:2]: self.assertFalse(self.enviar("GET",f'/marcacoes/{m["id"]}')[1]["conferido"])

    def test_fechamento_concorrente_upload_revalida_estado(self):
        e,c,ms = self.cadastro(fechar=True)
        boundary = "onponto-ficticio-concorrencia"
        partes = []
        for campo,valor in {"empresa_id":e["id"],"competencia_id":c["id"],"mes":9,"ano":2026}.items():
            partes.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{campo}"\r\n\r\n{valor}\r\n')
        partes.append(f'--{boundary}\r\nContent-Disposition: form-data; name="arquivo"; filename="ficticio.txt"\r\nContent-Type: text/plain\r\n\r\ncodigo;nome;data;hora\nF001;FICTÍCIO;2026-09-01;08:00\r\n--{boundary}--\r\n')
        body = "".join(partes).encode()
        respostas = self.simultaneas([
            lambda:self.enviar("POST",f'/competencias/{c["id"]}/fechar',{}),
            lambda:self.enviar("POST","/importadores/analisar",corpo=body,headers={"Content-Type":f"multipart/form-data; boundary={boundary}"})])
        self.assertIn([r[0] for r in respostas],([200,409],[409,201]))
        atual = self.enviar("GET",f'/marcacoes/{ms[0]["id"]}')[1]
        self.assertEqual(atual,ms[0])
