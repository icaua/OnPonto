"""Autorização local por origem, cookie efêmero e CSRF; sem contas remotas."""
import hashlib,ipaddress,os,secrets,time,logging
from urllib.parse import urlsplit
from fastapi import APIRouter,Request,HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

ORIGENS={'http://127.0.0.1:5500','http://localhost:5500'}
for origem in filter(None,os.getenv('ONPONTO_FRONTEND_ORIGINS','').split(',')):
    partes=urlsplit(origem.strip())
    if partes.scheme!='http' or partes.hostname not in ('127.0.0.1','localhost') or partes.path not in ('','/') or partes.query or partes.fragment or partes.username:
        raise RuntimeError('Origem adicional deve ser HTTP de loopback com porta explícita.')
    if not partes.port:raise RuntimeError('Origem adicional exige porta.')
    ORIGENS.add(origem.strip().rstrip('/'))
COOKIE='onponto_local'
SESSOES={}
TTL=8*60*60
router=APIRouter()
def chave(token):return hashlib.sha256(token.encode()).hexdigest()
def sessao(request):
    token=request.cookies.get(COOKIE,'')
    dados=SESSOES.get(chave(token)) if token else None
    return dados if dados and dados['expira']>time.monotonic() else None
def origem_local(request):
    try:
        if request.url.hostname not in ('127.0.0.1','localhost') or not request.url.port:return False
        if not request.client or not ipaddress.ip_address(request.client.host).is_loopback:return False
        origem=request.headers.get('origin')
        propria=f'{request.url.scheme}://{request.headers.get("host","")}'
        if origem is not None:return origem in ORIGENS or origem==propria
        return request.headers.get('sec-fetch-site','') not in ('cross-site',)
    except (ValueError,TypeError):return False

class ProtecaoLocal(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        async def executar():
            try:return await call_next(request)
            except Exception as exc:
                logging.getLogger('onponto.seguranca').error('Falha interna da API (%s); dados da requisição omitidos.',type(exc).__name__)
                return JSONResponse({'detail':'Falha interna; operação não concluída.'},status_code=500)
        limite=26*1024*1024
        try:grande=int(request.headers.get('content-length','0'))>limite
        except ValueError:grande=True
        receber=request._receive;total=0
        async def limitado():
            nonlocal total
            mensagem=await receber();total+=len(mensagem.get('body',b''))
            if total>limite:raise HTTPException(413,'Requisição acima do limite de upload.')
            return mensagem
        request._receive=limitado
        if not origem_local(request):response=JSONResponse({'detail':'Origem ou endereço local não autorizado.'},status_code=403)
        elif grande:response=JSONResponse({'detail':'Requisição acima do limite de upload.'},status_code=413)
        elif request.method=='OPTIONS' or request.url.path in ('/','/sessao/local','/docs','/docs/oauth2-redirect','/openapi.json','/redoc'):
            response=await executar()
        else:
            dados=sessao(request)
            if not dados:response=JSONResponse({'detail':'Sessão local ausente ou expirada.'},status_code=401)
            elif request.method not in ('GET','HEAD') and not secrets.compare_digest(request.headers.get('x-onponto-csrf','').encode(),dados['csrf'].encode()):
                response=JSONResponse({'detail':'Verificação de sessão da operação inválida.'},status_code=403)
            else:response=await executar()
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Cache-Control']='no-store'
        if request.url.path not in ('/docs','/redoc'):
            response.headers['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        return response

@router.get('/sessao/local')
def iniciar_sessao(request:Request):
    dados=sessao(request)
    if dados:return JSONResponse({'csrf':dados['csrf']})
    agora=time.monotonic()
    for id in [id for id,v in SESSOES.items() if v['expira']<=agora]:SESSOES.pop(id,None)
    if len(SESSOES)>=2048:SESSOES.pop(next(iter(SESSOES)))
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
    SESSOES[chave(token)]={'csrf':csrf,'expira':agora+TTL}
    resposta=JSONResponse({'csrf':csrf})
    resposta.set_cookie(COOKIE,token,httponly=True,samesite='strict',max_age=TTL,path='/')
    return resposta
