"""Cliente de integração autentica pela sessão real; testes negativos usam urllib puro."""
import json,threading
from http.cookiejar import CookieJar
from urllib.request import Request,build_opener,HTTPCookieProcessor
from urllib.parse import urlsplit
_clientes={};_trava=threading.RLock()
def urlopen(request,timeout=None):
    if isinstance(request,str):request=Request(request)
    partes=urlsplit(request.full_url);base=f'{partes.scheme}://{partes.netloc}'
    with _trava:
        if base not in _clientes:
            opener=build_opener(HTTPCookieProcessor(CookieJar()))
            with opener.open(base+'/sessao/local',timeout=timeout or 5) as resposta:csrf=json.load(resposta)['csrf']
            _clientes[base]=(opener,csrf)
        opener,csrf=_clientes[base]
    if request.get_method() not in ('GET','HEAD'):request.add_header('X-OnPonto-Csrf',csrf)
    return opener.open(request,timeout=timeout)
