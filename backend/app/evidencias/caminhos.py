"""Resolução portátil de referências antigas sem editar evidências imutáveis."""
import json
from pathlib import Path

def resolver_referencia(referencia,uploads,backend):
    raiz=Path(uploads).resolve()
    caminho=Path(referencia)
    caminho=(caminho if caminho.is_absolute() else Path(backend)/caminho).resolve()
    if caminho.is_relative_to(raiz): return caminho
    mapa=raiz.parent/'restauracao.json'
    if mapa.is_file():
        dados=json.loads(mapa.read_text(encoding='utf-8'))
        relativo=dados.get('referencias',{}).get(str(referencia))
        if relativo:
            traduzido=(raiz/relativo).resolve()
            if traduzido.is_relative_to(raiz):return traduzido
    raise ValueError('Referência fora da raiz de evidências.')
