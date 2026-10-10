"""Limites do contêiner antes de qualquer descompressão pelo openpyxl."""
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile, ZIP_STORED, ZIP_DEFLATED
from fastapi import HTTPException

def validar(caminho):
    try:
        with ZipFile(caminho) as arquivo:
            itens = arquivo.infolist()
            if len(itens)>4096 or sum(i.file_size for i in itens)>100*1024*1024:
                raise ValueError("XLSX excede o limite de conteúdo descompactado.")
            nomes={i.filename for i in itens}
            if len(nomes)!=len(itens):raise ValueError('XLSX contém entradas duplicadas.')
            if not {"[Content_Types].xml", "xl/workbook.xml"}.issubset(nomes):
                raise ValueError("Conteúdo não corresponde a uma planilha XLSX.")
            for item in itens:
                if item.compress_type not in (ZIP_STORED,ZIP_DEFLATED):raise ValueError('Compressão XLSX não suportada.')
                nome=PurePosixPath(item.filename.replace("\\", "/"))
                if nome.is_absolute() or ".." in nome.parts or item.flag_bits & 1 or ":" in item.filename:
                    raise ValueError("XLSX contém entrada inválida ou criptografada.")
                if item.file_size>20*1024*1024 or item.file_size>max(1024*1024,item.compress_size*200):
                    raise ValueError("XLSX excede o limite por entrada ou a razão de compressão.")
            for item in itens:
                if item.filename.lower().endswith(('.xml','.rels')):
                    xml=arquivo.read(item).replace(b'\x00',b'').upper()
                    if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:raise ValueError('XLSX com DTD/entidades não permitido.')
    except (BadZipFile, ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
