import json
import sys
import unittest
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_confiabilidade_operacional as fixture
from test_support import TemporaryDirectory
from app.database.models import (ArquivoRecebido, BatidaOriginal, PreviaImportacao,
    ConfirmacaoImportacaoEvento, EventoAuditoria, MarcacaoPonto, DocumentoEvidencia)
from app.database.migrations import aplicar_migracoes_compativeis
from app.importadores import routes, propostas
from app.importadores.schemas import ConfirmacaoImportacao
from app.evidencias.inventario import verificar
from app.evidencias.ocr_contrato import PropostaDocumento

class EvidenciasPropostasTest(unittest.TestCase):
    def setUp(self):
        fixture.ConfiabilidadeOperacionalTest.setUp(self)
        self.f.codigo='001'; self.db.commit()
        self.temp=TemporaryDirectory(prefix='onponto-evidencias-ficticias-'); self.addCleanup(self.temp.cleanup)
        self.uploads=Path(self.temp.name)/'uploads'; self.uploads.mkdir()
        self.mock=patch.object(routes,'UPLOADS_DIR',self.uploads); self.mock.start(); self.addCleanup(self.mock.stop)
        self.conteudo=('ID\tNome\tTempo\n'+''.join(f'001\tPessoa Fictícia\t01/09/2026 {h}:00\n'
            for h in ('08:00','12:00','13:00','13:00','17:00'))).encode()

    def upload(self):
        return routes.analisar_importacao(self.c.id,self.f.empresa_id,9,2026,
            UploadFile(filename='ficticio.txt',file=BytesIO(self.conteudo)),self.db)

    def payload(self, previa):
        return ConfirmacaoImportacao(empresa_id=self.f.empresa_id,competencia_id=self.c.id,arquivo_id=previa['arquivo']['id'],
            registros_ids=[r['id'] for r in previa['preview']],revisao_previa=previa['revisao_previa'])

    def test_upload_falha_de_validacao_io_nao_deixa_arquivo(self):
        from app.arquivos.routes import enviar_arquivo
        with patch('app.arquivos.routes.UPLOADS_DIR', self.uploads), \
                patch('app.seguranca.arquivos.validar_conteudo', side_effect=OSError('caminho interno fictício')):
            with self.assertRaises(HTTPException) as erro:
                enviar_arquivo(self.c.id, None, UploadFile(filename='ficticio.txt', file=BytesIO(self.conteudo)), self.db)
        self.assertEqual(erro.exception.status_code, 500)
        self.assertNotIn('interno', str(erro.exception.detail))
        self.assertEqual(list(self.uploads.rglob('*.txt')), [])
        self.assertEqual(self.db.query(ArquivoRecebido).count(), 0)

    def test_upload_falha_de_commit_novo_e_reenvio_reverte_transacao(self):
        from app.arquivos.routes import enviar_arquivo
        for reenvio in (False, True):
            with self.subTest(reenvio=reenvio), patch('app.arquivos.routes.UPLOADS_DIR', self.uploads):
                if reenvio:
                    original = enviar_arquivo(self.c.id, None,
                        UploadFile(filename='ficticio.txt', file=BytesIO(self.conteudo)), self.db)
                arquivos_antes = sorted(p for p in self.uploads.rglob('*') if p.is_file())
                eventos_antes = self.db.query(EventoAuditoria).count()
                with patch.object(self.db, 'commit', side_effect=SQLAlchemyError('caminho interno fictício')):
                    with self.assertRaises(HTTPException) as erro:
                        enviar_arquivo(self.c.id, None,
                            UploadFile(filename='ficticio.txt', file=BytesIO(self.conteudo)), self.db)
                self.assertEqual(erro.exception.status_code, 500)
                self.assertNotIn('interno', str(erro.exception.detail))
                self.assertFalse(self.db.new)
                self.assertFalse(self.db.dirty)
                self.assertEqual(self.db.query(EventoAuditoria).count(), eventos_antes)
                self.assertEqual(sorted(p for p in self.uploads.rglob('*') if p.is_file()), arquivos_antes)
                self.assertEqual(self.db.query(ArquivoRecebido).count(), int(reenvio))
                if reenvio:
                    self.assertEqual(Path(original.caminho_arquivo).read_bytes(), self.conteudo)

    def test_download_recusa_fora_travessia_prefixo_e_ausente(self):
        from app.arquivos.routes import enviar_arquivo, baixar_arquivo
        from app.evidencias.caminhos import resolver_referencia
        fora = self.uploads.parent / 'uploads-vizinho'
        fora.mkdir()
        (fora / 'fora.txt').write_bytes(self.conteudo)
        with patch('app.arquivos.routes.UPLOADS_DIR', self.uploads):
            a = enviar_arquivo(self.c.id, None, UploadFile(filename='ficticio.txt', file=BytesIO(self.conteudo)), self.db)
            for referencia, codigo in (
                (fora / 'fora.txt', 400),
                (self.uploads / '..' / 'uploads-vizinho' / 'fora.txt', 400),
                (self.uploads / 'ausente.txt', 404),
            ):
                with self.subTest(referencia=referencia):
                    a.caminho_arquivo = str(referencia)
                    self.db.commit()
                    with self.assertRaises(HTTPException) as erro:
                        baixar_arquivo(a.id, self.db)
                    self.assertEqual(erro.exception.status_code, codigo)
                    self.assertNotIn(str(self.uploads.parent), str(erro.exception.detail))
                    if codigo == 400:
                        with self.assertRaises(ValueError):
                            resolver_referencia(str(referencia), self.uploads, self.uploads.parent)
        self.assertEqual((fora / 'fora.txt').read_bytes(), self.conteudo)

    def test_download_e_referencia_recusam_symlink_para_fora_da_raiz(self):
        from app.arquivos.routes import baixar_arquivo
        from app.evidencias.caminhos import resolver_referencia
        externo = self.uploads.parent / 'fora.txt'
        externo.write_bytes(self.conteudo)
        link = self.uploads / 'link.txt'
        try:
            link.symlink_to(externo)
        except OSError as exc:
            self.skipTest(f'Sistema sem permissão para symlink: {exc.errno}')
        a = ArquivoRecebido(competencia_id=self.c.id, nome_original='link.txt', tipo_arquivo='txt', caminho_arquivo=str(link))
        self.db.add(a)
        self.db.commit()
        with patch('app.arquivos.routes.UPLOADS_DIR', self.uploads):
            with self.assertRaises(HTTPException) as erro:
                baixar_arquivo(a.id, self.db)
            self.assertEqual(erro.exception.status_code, 400)
        with self.assertRaises(ValueError):
            resolver_referencia(str(link), self.uploads, self.uploads.parent)

    def test_upload_generico_valida_conteudo_hash_download_e_caminho(self):
        from app.arquivos.routes import enviar_arquivo,baixar_arquivo
        with patch('app.arquivos.routes.UPLOADS_DIR',self.uploads):
            with self.assertRaises(HTTPException):enviar_arquivo(self.c.id,None,UploadFile(filename='falso.pdf',file=BytesIO(b'<html>falso</html>')),self.db)
            self.assertEqual(list(self.uploads.rglob('*.pdf')),[])
            a=enviar_arquivo(self.c.id,None,UploadFile(filename='../../FICTICIO.txt',file=BytesIO(self.conteudo)),self.db)
            resposta=baixar_arquivo(a.id,self.db);caminho=Path(resposta.path)
            self.assertTrue(caminho.resolve().is_relative_to(self.uploads.resolve()));self.assertEqual(caminho.read_bytes(),self.conteudo)
            self.assertEqual(resposta.media_type,'application/octet-stream');self.assertEqual(a.nome_original,'FICTICIO.txt')
            self.assertTrue(a.sha256);self.assertEqual(self.db.query(DocumentoEvidencia).filter_by(arquivo_id=a.id).count(),1)
            caminho.write_bytes(b'ADULTERADO FICTICIO')
            with self.assertRaises(HTTPException) as erro:baixar_arquivo(a.id,self.db)
            self.assertEqual(erro.exception.status_code,409)
            a.caminho_arquivo=str(Path(self.temp.name)/'fora.txt')
            with self.assertRaises(HTTPException) as erro:baixar_arquivo(a.id,self.db)
            self.assertEqual(erro.exception.status_code,400)

    def test_colisao_de_nome_nunca_remove_original_existente(self):
        from types import SimpleNamespace
        from datetime import datetime
        with patch('app.importadores.armazenamento.uuid4',return_value=SimpleNamespace(hex='f'*32)),patch('app.importadores.armazenamento.datetime') as relogio:
            relogio.utcnow.return_value=datetime(2026,9,1,12)
            primeira=self.upload();arquivo=self.db.get(ArquivoRecebido,primeira['arquivo']['id']);caminho=Path(arquivo.caminho_arquivo)
            if not caminho.is_absolute():caminho=routes.BACKEND_DIR/caminho
            with self.assertRaises(HTTPException):self.upload()
            self.assertEqual(caminho.read_bytes(),self.conteudo)
            self.assertEqual(self.db.query(ArquivoRecebido).count(),1)

    def test_validacao_de_upload_preserva_utf16_com_e_sem_bom(self):
        texto=self.conteudo.decode()
        for codec in ('utf-16','utf-16-le','utf-16-be'):
            with self.subTest(codec=codec):
                previa=routes.analisar_importacao(self.c.id,self.f.empresa_id,9,2026,
                    UploadFile(filename='FICTICIO-'+codec+'.txt',file=BytesIO(texto.encode(codec))),self.db)
                self.assertEqual(len(previa['preview']),1)

    def test_confirmacao_sem_parser_idempotente_e_duplicidade_preservada(self):
        previa=self.upload(); payload=self.payload(previa)
        with patch.object(routes.pipeline,'gerar_previa',side_effect=AssertionError('não reinterpretar')):
            primeira=routes.confirmar_importacao(payload,self.db)
            segunda=routes.confirmar_importacao(payload,self.db)
        self.assertTrue(segunda['idempotente']); self.assertEqual(primeira['marcacoes_ids'],segunda['marcacoes_ids'])
        self.assertEqual(self.db.query(ConfirmacaoImportacaoEvento).count(),1)
        self.assertEqual(self.db.query(MarcacaoPonto).filter_by(arquivo_origem_id=payload.arquivo_id).count(),1)
        brutas=self.db.query(BatidaOriginal).order_by(BatidaOriginal.indice).all()
        self.assertEqual(len(brutas),5); self.assertEqual(brutas[2].valor_json,brutas[3].valor_json)
        self.assertTrue(all(b.marcacao_id==primeira['marcacoes_ids'][0] for b in brutas))
        self.assertEqual(len(list(self.uploads.rglob('*.txt'))),1)

    def test_dois_uploads_reutilizam_original_sem_sobrescrever_decisao(self):
        previa=self.upload(); resposta=routes.confirmar_importacao(self.payload(previa),self.db)
        m=self.db.get(MarcacaoPonto,resposta['marcacoes_ids'][0]); m.observacoes='Decisão humana preservada'; self.db.commit()
        segunda=self.upload()
        self.assertEqual(previa['arquivo']['id'],segunda['arquivo']['id'])
        r=routes.confirmar_importacao(self.payload(segunda),self.db)
        self.assertEqual(r['total_importados'],0); self.assertEqual(self.db.query(ArquivoRecebido).count(),1)
        self.assertEqual(self.db.query(BatidaOriginal).count(),5); self.assertEqual(m.observacoes,'Decisão humana preservada')
        self.assertEqual(len(list(self.uploads.rglob('*.txt'))),1)

    def test_revision_http_necessaria_e_antiga_recusada(self):
        previa=self.upload(); payload=self.payload(previa)
        payload.revisao_previa=None
        with self.assertRaises(HTTPException) as erro: routes.confirmar_importacao(payload,self.db,request=object())
        self.assertEqual(erro.exception.detail['codigo'],'revisao_previa_necessaria')
        payload.revisao_previa=previa['revisao_previa']; self.upload()
        with self.assertRaises(HTTPException) as erro: routes.confirmar_importacao(payload,self.db,request=object())
        self.assertEqual(erro.exception.detail['codigo'],'previa_obsoleta')

    def test_cadastro_regra_versao_adapter_e_hash_invalidam_sem_gravar(self):
        previa=self.upload(); payload=self.payload(previa)
        for campo,valor in [('nome','Outro nome fictício'),('codigo','002')]:
            anterior=getattr(self.f,campo); setattr(self.f,campo,valor); self.db.commit()
            with self.assertRaises(HTTPException): routes.confirmar_importacao(payload,self.db)
            setattr(self.f,campo,anterior); self.db.commit()
        adapter=previa['tipo_detectado']
        with patch.dict(propostas.VERSOES_ADAPTADORES,{adapter:'2'}):
            with self.assertRaises(HTTPException): routes.confirmar_importacao(payload,self.db)
        arquivo=self.db.get(ArquivoRecebido,payload.arquivo_id); caminho=Path(arquivo.caminho_arquivo)
        caminho.write_bytes(self.conteudo+b'alterado')
        with self.assertRaises(HTTPException): routes.confirmar_importacao(payload,self.db)
        self.assertEqual(self.db.query(ConfirmacaoImportacaoEvento).count(),0)
        self.assertEqual(self.db.query(MarcacaoPonto).count(),0)

    def test_falha_atomicamente_preserva_proposta_brutas_e_original(self):
        previa=self.upload(); payload=self.payload(previa); arquivo=self.db.get(ArquivoRecebido,payload.arquivo_id)
        controle=arquivo.controle_importacao_json
        with patch.object(self.db,'commit',side_effect=SQLAlchemyError('falha fictícia')):
            with self.assertRaises(HTTPException): routes.confirmar_importacao(payload,self.db)
        self.assertEqual(arquivo.controle_importacao_json,controle)
        self.assertEqual(self.db.query(MarcacaoPonto).count(),0)
        self.assertEqual(self.db.query(ConfirmacaoImportacaoEvento).count(),0)
        self.assertTrue(all(b.marcacao_id is None for b in self.db.query(BatidaOriginal)))
        self.assertEqual(Path(arquivo.caminho_arquivo).read_bytes(),self.conteudo)

    def test_migracao_repeat_preserva_json_indices_e_triggers(self):
        m=fixture.ConfiabilidadeOperacionalTest.dia(self,batidas_originais='["08:00", "08:00", "17:00"]',
            historico_json='[{"id":"legado","description":"Fictício"}]')
        original=(m.batidas_originais,m.historico_json)
        self.db.close()
        aplicar_migracoes_compativeis(self.engine); aplicar_migracoes_compativeis(self.engine)
        self.assertEqual(self.db.query(BatidaOriginal).count(),3)
        self.assertEqual(self.db.query(EventoAuditoria).count(),1)
        self.assertEqual((self.db.get(MarcacaoPonto,m.id).batidas_originais,self.db.get(MarcacaoPonto,m.id).historico_json),original)
        for tabela,campo,valor in [('batidas_originais','valor_json','"09:00"'),('eventos_auditoria','payload_json','{}')]:
            with self.assertRaises(IntegrityError): self.db.execute(text(f'UPDATE {tabela} SET {campo}=:valor'),{'valor':valor})
            self.db.rollback()
            with self.assertRaises(IntegrityError): self.db.execute(text(f'DELETE FROM {tabela}'))
            self.db.rollback()
        self.assertEqual(self.db.execute(text('PRAGMA integrity_check')).scalar(),'ok')
        self.assertEqual(self.db.execute(text('PRAGMA foreign_key_check')).all(),[])

    def test_inventario_orfao_adulterado_ausente_somente_leitura(self):
        previa=self.upload(); (self.uploads/'orfao.txt').write_text('fictício')
        r=verificar(self.db,self.uploads,routes.BACKEND_DIR)
        self.assertEqual(r['orfaos'],['orfao.txt']); self.assertFalse(r['ausentes'])
        arquivo=self.db.get(ArquivoRecebido,previa['arquivo']['id']); caminho=Path(arquivo.caminho_arquivo)
        caminho.write_text('adulteração fictícia')
        self.assertTrue(verificar(self.db,self.uploads,routes.BACKEND_DIR)['hash_divergente'])
        caminho.unlink()
        self.assertTrue(verificar(self.db,self.uploads,routes.BACKEND_DIR)['ausentes'])
        self.assertTrue((self.uploads/'orfao.txt').exists())

    def test_ocr_apenas_contrato_pagina_e_sugestao_pendente(self):
        p=PropostaDocumento(documento_id=1,funcionario_id=1,competencia_id=1,pagina=2,
            campos=[{'campo':'entrada','origem':'região ilegível','valor':None}])
        self.assertEqual(p.campos[0].revisao_humana,'pendente'); self.assertIsNone(p.campos[0].valor)
        self.assertFalse(any('ocr' in rota.path for rota in routes.router.routes))

    def test_reanalise_associacao_nao_duplica_eventos_brutos(self):
        self.f.codigo='002';self.f.nome='Sem associação';self.db.commit()
        previa=self.upload();self.assertFalse(previa['preview'][0]['funcionario']['encontrado'])
        self.f.codigo='001';self.f.nome='Pessoa Fictícia';self.db.commit()
        segunda=routes.reanalisar(previa['arquivo']['id'],self.db)
        self.assertNotEqual(previa['preview'][0]['id'],segunda['preview'][0]['id'])
        routes.confirmar_importacao(self.payload(segunda),self.db)
        self.assertEqual(self.db.query(BatidaOriginal).count(),5)

    def test_limites_xlsx_antes_do_parser(self):
        from zipfile import ZipFile, ZIP_DEFLATED
        from app.importadores.seguranca_xlsx import validar
        for nome,conteudo in [('xl/grande.xml',b'0'*(2*1024*1024)),('../escapar.xml',b'invalid')]:
            caminho=self.uploads/'adversarial.xlsx'
            with ZipFile(caminho,'w',ZIP_DEFLATED) as z:
                z.writestr('[Content_Types].xml',b'x');z.writestr('xl/workbook.xml',b'x');z.writestr(nome,conteudo)
            with self.assertRaises(HTTPException): validar(caminho)
