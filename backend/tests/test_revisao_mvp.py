import itertools
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import date

import test_espelho_ponto as fixtures
from app.importadores.txt_generico import parse_txt_generico, ErroImportacaoTxtGenerico
from app.marcacoes.routes import atualizar_marcacao
from app.marcacoes.schemas import MarcacaoUpdate
from pydantic import ValidationError


class RevisaoTxtTest(unittest.TestCase):
    def parse(self, texto, encoding='utf-8', funcionarios=()):
        return parse_txt_generico(texto.encode(encoding), arquivo_nome='original.txt',
                                  mes=8, ano=2026, funcionarios=funcionarios)

    def test_matriz_encodings_separadores_datas_e_aliases(self):
        formatos = ['2026-08-01 08:00:00', '01/08/2026 08:00', '01-08-2026 08:00']
        aliases = [('ID','Nome','DateTime'), ('Código','Funcionário','Tempo'),
                   ('Matrícula','Name','Data e Hora'), ('EnNo','Employee','Timestamp'),
                   ('Employee ID','Nome','Horário'), ('PIN','Nome','Marcação')]
        for encoding, sep, data, nomes in itertools.product(['utf-8','utf-16','cp1252'], ['\t',';','|',','], formatos, aliases):
            with self.subTest(encoding=encoding, sep=sep, data=data, nomes=nomes):
                r = self.parse(sep.join(nomes)+'\n'+sep.join(['007','João Silva',data]), encoding)
                item = r['registros'][0]
                self.assertEqual(item['funcionario']['codigo_origem'],'007')
                self.assertEqual(item['funcionario']['nome_origem'],'João Silva')
                self.assertEqual(item['batidas_originais'],['08:00:00'])

    def test_nao_associa_id_divergente_nome_conflitante_ou_homonimos(self):
        funcionarios = [{'id':1,'codigo':'007','nome':'Ana'}, {'id':2,'codigo':'008','nome':'Bia'}]
        for codigo,nome in [('999','Ana'),('007','Bia')]:
            r=self.parse(f'ID;Nome;Timestamp\n{codigo};{nome};2026-08-01 08:00',funcionarios=funcionarios)
            item=r['registros'][0]
            self.assertFalse(item['selecionado'])
            self.assertFalse(item['funcionario']['encontrado'])
            self.assertTrue(item['pendencias'])
        r=self.parse('Nome;Timestamp\nAna;2026-08-01 08:00',funcionarios=[{'id':1,'nome':'Ana'},{'id':2,'nome':'Ana'}])
        self.assertFalse(r['registros'][0]['funcionario']['encontrado'])

    def test_preserva_repeticoes_ordem_segundos_e_identidade_inconsistente(self):
        r=self.parse('ID;Nome;Timestamp\n7;Ana;2026-08-01 17:00:32\n7;Ana;2026-08-01 08:00:21\n7;Bia;2026-08-01 08:00:21')
        item=r['registros'][0]
        self.assertEqual(item['batidas_originais'],['17:00:32','08:00:21','08:00:21'])
        self.assertEqual(item['batidas_normalizadas'],['08:00:21','08:00:21','17:00:32'])
        self.assertFalse(item['selecionado'])
        self.assertIn('duplicadas', ' '.join(item['pendencias']))
        self.assertIn('nomes diferentes', ' '.join(item['pendencias']))

    def test_vazio_cabecalho_sem_registros_e_data_sem_horario_nao_inventam_batida(self):
        for texto in ['', 'ID;Nome;Timestamp\n', 'ID;Nome;Timestamp\n7;Ana;2026-08-01',
                      'ID;Nome;Timestamp\n7;Ana;2026-08-01 25:70']:
            with self.subTest(texto=texto), self.assertRaises(ErroImportacaoTxtGenerico): self.parse(texto)

    def test_linha_invalida_e_horario_parcial_sao_sinalizados(self):
        r=self.parse('ID;Nome;Data;Entrada;Saída\n7;Ana;01/08/2026;08:00;25:00\nlinha inválida')
        self.assertEqual(r['total_linhas_ignoradas'],1)
        self.assertTrue(r['linhas_rejeitadas'])
        self.assertIn('horário inválido',' '.join(r['registros'][0]['pendencias']))
        self.assertIsNone(r['registros'][0]['interpretacao']['saida'])

    def test_sem_nome_ou_sem_id_so_associa_identificador_unico(self):
        funcionarios=[{'id':1,'codigo':'007','nome':'Ana'}]
        for texto in ['ID;Timestamp\n007;2026-08-01 08:00','Nome;Timestamp\nAna;2026-08-01 08:00']:
            self.assertTrue(self.parse(texto,funcionarios=funcionarios)['registros'][0]['funcionario']['encontrado'])
        self.assertFalse(self.parse('ID;Timestamp\n999;2026-08-01 08:00')['registros'][0]['selecionado'])

    def test_menos_e_mais_de_quatro_batidas_sem_adivinhar_slots(self):
        for quantidade in (1,2,3,4,5,6):
            texto='ID;Nome;Timestamp\n'+'\n'.join(f'7;Ana;2026-08-01 {8+i:02d}:00' for i in range(quantidade))
            item=self.parse(texto)['registros'][0]
            self.assertEqual(len(item['batidas_originais']),quantidade)
            if quantidade in (3,5,6):
                self.assertTrue(all(v is None for v in item['interpretacao'].values()))
            if quantidade != 4:
                self.assertEqual(item['status'],'conferir')


class RevisaoIntegridadeTest(unittest.TestCase):
    def test_adapter_conhecido_sinaliza_divergencia_sem_selecionar_automaticamente(self):
        from app.importadores import routes
        from app.database.models import ArquivoRecebido
        f=fixtures.EspelhoPontoTest();f.setUp();self.addCleanup(f.doCleanups)
        with TemporaryDirectory() as tmp, patch.object(routes,'UPLOADS_DIR',Path(tmp)):
            arquivo=Path(tmp)/'relogio.txt'
            arquivo.write_text('EnNo\tName\tDateTime\n007\tOutro Nome\t2026-09-01 08:00:00\n',encoding='utf-8')
            registro=ArquivoRecebido(competencia_id=f.competencia.id,nome_original='relogio.txt',
                                    caminho_arquivo=str(arquivo),tipo_arquivo='txt')
            f.db.add(registro);f.db.commit()
            analise=routes.analisar_arquivo_salvo(f.db,f.competencia,registro)
            self.assertEqual(analise['tipo_detectado'],'txt_log_relogio')
            item=analise['preview'][0]
            self.assertFalse(item['selecionado'])
            self.assertEqual(item['status'],'conferir')
            self.assertIn('diverge do cadastro',' '.join(item['pendencias']))

    def test_importacao_preserva_arquivo_batidas_e_auditoria_apos_edicao_e_reimportacao(self):
        from app.importadores import routes
        from app.importadores.schemas import ConfirmacaoImportacao
        from app.database.models import ArquivoRecebido, MarcacaoPonto
        f=fixtures.EspelhoPontoTest();f.setUp();self.addCleanup(f.doCleanups)
        f.competencia.mes=8;f.db.commit()
        texto='ID;Nome;Timestamp\n'+'\n'.join('007;Ana Teste;2026-08-01 '+h for h in ['17:00:01','08:00:02','12:00:03','13:00:04','13:00:04'])
        conteudo=texto.encode('utf-16')
        with TemporaryDirectory() as tmp, patch.object(routes,'UPLOADS_DIR',Path(tmp)):
            arquivo=Path(tmp)/'origem.txt';arquivo.write_bytes(conteudo)
            registro=ArquivoRecebido(competencia_id=f.competencia.id,nome_original='origem.txt',
                                    caminho_arquivo=str(arquivo),tipo_arquivo='txt')
            f.db.add(registro);f.db.commit()
            analise=routes.analisar_arquivo_salvo(f.db,f.competencia,registro)
            payload=ConfirmacaoImportacao(empresa_id=f.empresa.id,competencia_id=f.competencia.id,
                                          arquivo_id=registro.id,registros_ids=[analise['preview'][0]['id']])
            self.assertEqual(routes.confirmar_importacao(payload,f.db)['total_importados'],1)
            m=f.db.query(MarcacaoPonto).filter_by(arquivo_origem_id=registro.id).one()
            originais=m.batidas_originais
            self.assertEqual(json.loads(originais),['17:00:01','08:00:02','12:00:03','13:00:04','13:00:04'])
            atualizar_marcacao(m.id,MarcacaoUpdate(observacoes='Conferência humana'),f.db)
            self.assertEqual(m.batidas_originais,originais)
            self.assertTrue(m.historico)
            resultado=routes.confirmar_importacao(payload,f.db)
            self.assertEqual(resultado['total_importados'],0)
            self.assertEqual(resultado['total_conflitos'],1)
            self.assertEqual(arquivo.read_bytes(),conteudo)
            self.assertIn('1 importados',registro.observacoes)
            self.assertIn('0 importados',registro.observacoes)

    def test_patch_nao_move_dia_para_fora_da_competencia(self):
        f=fixtures.EspelhoPontoTest();f.setUp();self.addCleanup(f.doCleanups)
        f.calendario_conferido();m=f.dia(1)
        with self.assertRaises(ValidationError):
            MarcacaoUpdate(data=date(2026,8,1))
        self.assertEqual(m.data,date(2026,9,1))

    def test_assinaturas_identificam_pessoa_e_empresa(self):
        f=fixtures.EspelhoPontoTest();f.setUp();self.addCleanup(f.doCleanups)
        html=f.html().text
        self.assertIn('<div class="assinatura">Ana Teste<span',html)
        self.assertIn('<div class="assinatura">Empresa teste<span',html)
        self.assertNotIn('Responsável DP/Contabilidade',html)
