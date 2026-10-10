"""Validação limitada antes de armazenar/analisar; nunca executa PDF ou imagem."""
import re,struct,zlib
from pathlib import Path
from fastapi import HTTPException
from app.importadores.seguranca_xlsx import validar as validar_xlsx
LIMITE=25*1024*1024
def validar_conteudo(caminho,extensao):
    caminho=Path(caminho)
    if not 0<caminho.stat().st_size<=LIMITE:raise HTTPException(413 if caminho.stat().st_size>LIMITE else 400,'Arquivo vazio ou acima de 25 MB.')
    if extensao=='.xlsx':validar_xlsx(caminho);return
    dados=caminho.read_bytes()
    try:
        if extensao in ('.txt','.csv'):
            from app.importadores.txt_generico import _decodificar
            texto,_=_decodificar(dados)
            if any(ord(v)<9 or 13<ord(v)<32 for v in texto):raise ValueError('Conteúdo binário não corresponde ao arquivo de texto.')
        elif extensao=='.png':
            if not dados.startswith(b'\x89PNG\r\n\x1a\n') or dados[12:16]!=b'IHDR' or b'IEND' not in dados[-32:]:raise ValueError('PNG inválido.')
            largura,altura=struct.unpack('>II',dados[16:24]);validar_pixels(largura,altura)
        elif extensao in ('.jpg','.jpeg'):
            if not dados.startswith(b'\xff\xd8') or not dados.endswith(b'\xff\xd9'):raise ValueError('JPEG inválido.')
            pos=2;dimensoes=None
            while pos<len(dados)-3:
                if dados[pos]!=255:raise ValueError('Estrutura JPEG inválida.')
                while dados[pos]==255:pos+=1
                marcador=dados[pos];pos+=1
                if marcador in (0xD9,0xDA):break
                if marcador in (0x01,*range(0xD0,0xD9)):continue
                tamanho=int.from_bytes(dados[pos:pos+2],'big')
                if tamanho<2 or pos+tamanho>len(dados):raise ValueError('Segmento JPEG inválido.')
                if marcador in (0xC0,0xC1,0xC2):dimensoes=(int.from_bytes(dados[pos+5:pos+7],'big'),int.from_bytes(dados[pos+3:pos+5],'big'));break
                pos+=tamanho
            if not dimensoes:raise ValueError('JPEG sem dimensões válidas.')
            validar_pixels(*dimensoes)
        elif extensao=='.pdf':
            if not re.match(rb'%PDF-1\.[0-7]|%PDF-2\.0',dados[:8]) or b'%%EOF' not in dados[-2048:]:raise ValueError('PDF inválido.')
            if re.search(rb'/(JavaScript|JS|Launch|EmbeddedFile|Encrypt)\b',dados):raise ValueError('PDF com conteúdo ativo, incorporado ou criptografado não é permitido.')
            if len(re.findall(rb'/Type\s*/Page\b',dados))>512 or any(int(n)>512 for n in re.findall(rb'/Count\s+(\d+)\b',dados)):
                raise ValueError('PDF acima do limite de 512 páginas.')
            total=0;cursor=0;quantidade=0
            # Busca sequencial e janela limitada evitam regex com backtracking
            # sobre um documento inteiro. Não há interpretação/renderização PDF.
            while True:
                stream=re.compile(rb'\bstream\r?\n').search(dados,cursor)
                if stream is None:break
                inicio=stream.start();comeco=stream.end()
                fim=dados.find(b'endstream',comeco)
                if fim<0:raise ValueError('Stream PDF incompleto.')
                quantidade+=1
                if quantidade>4096:raise ValueError('PDF excede limite de streams.')
                cabecalho=dados[max(cursor,inicio-65536):inicio]
                cabecalho=cabecalho[cabecalho.rfind(b'<<'):]
                conteudo=dados[comeco:fim].rstrip(b'\r\n');cursor=fim+len(b'endstream')
                filtros=re.findall(rb'/([A-Za-z0-9]+Decode)\b',cabecalho)
                if filtros and filtros not in ([b'FlateDecode'],[b'DCTDecode']):raise ValueError('Filtro PDF não suportado para validação segura.')
                if filtros==[b'DCTDecode']:
                    largura=re.search(rb'/Width\s+(\d+)',cabecalho);altura=re.search(rb'/Height\s+(\d+)',cabecalho)
                    if not largura or not altura:raise ValueError('Imagem PDF sem dimensões válidas.')
                    validar_pixels(int(largura[1]),int(altura[1]))
                if filtros==[b'FlateDecode']:
                    descompressor=zlib.decompressobj();expandido=descompressor.decompress(conteudo,20*1024*1024+1)
                    if len(expandido)>20*1024*1024 or descompressor.unconsumed_tail or not descompressor.eof or len(expandido)>max(1024*1024,len(conteudo)*200):raise ValueError('PDF excede limites de descompressão.')
                    total+=len(expandido)
                    if total>100*1024*1024:raise ValueError('PDF excede limite total de descompressão.')
        else:raise ValueError('Extensão não permitida.')
    except (ValueError,UnicodeError,struct.error,zlib.error,IndexError) as exc:raise HTTPException(400,str(exc)) from exc

def validar_pixels(largura,altura):
    if min(largura,altura)<=0 or max(largura,altura)>20000 or largura*altura>40_000_000:raise ValueError('Imagem excede limite de dimensões/pixels.')

def nome_original(nome):
    nome=Path(str(nome or 'arquivo').replace('\\','/')).name
    return re.sub(r'[\x00-\x1f\x7f]','_',nome)[:255]

def verificar_hash(caminho,esperado):
    if esperado:
        from app.importadores.propostas import hash_arquivo
        if hash_arquivo(caminho)!=esperado:raise HTTPException(409,'Arquivo diverge da evidência preservada.')
