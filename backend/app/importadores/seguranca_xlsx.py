"""Limites do contêiner antes de qualquer descompressão pelo openpyxl."""
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile
from fastapi import HTTPException

def validar(caminho):
    try:
        with ZipFile(caminho) as arquivo:
            itens = arquivo.infolist()
            if len(itens)>4096 or sum(i.file_size for i in itens)>100*1024*1024:
                raise ValueError("XLSX excede o limite de conteúdo descompactado.")
            nomes={i.filename for i in itens}
            if not {"[Content_Types].xml", "xl/workbook.xml"}.issubset(nomes):
                raise ValueError("Conteúdo não corresponde a uma planilha XLSX.")
            for item in itens:
                nome=PurePosixPath(item.filename.replace("\\", "/"))
                if nome.is_absolute() or ".." in nome.parts or item.flag_bits & 1 or ":" in item.filename:
                    raise ValueError("XLSX contém entrada inválida ou criptografada.")
                if item.file_size>20*1024*1024 or item.file_size>max(1024*1024,item.compress_size*200):
                    raise ValueError("XLSX excede o limite por entrada ou a razão de compressão.")
    except (BadZipFile, ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
