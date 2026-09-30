// Execute manually: node frontend/tests/conferencia-browser.cjs
// Uses an isolated temporary SQLite database with fictional employees only.
const fs=require('node:fs'), path=require('node:path'), os=require('node:os'), http=require('node:http');
const {spawn,spawnSync}=require('node:child_process');
const assert=require('node:assert/strict');
const {chromium}=process.env.ONPONTO_NODE_MODULES ? require(path.join(process.env.ONPONTO_NODE_MODULES,'playwright')) : require('playwright');
const root=path.resolve(__dirname,'../..');
const python=process.env.ONPONTO_PYTHON || path.join(root,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
const out=fs.mkdtempSync(path.join(os.tmpdir(),'onponto-conferencia-ux-'));
const env={...process.env,ONPONTO_DATABASE_URL:'sqlite:///'+path.join(out,'ficticio.db'),ONPONTO_UPLOADS_DIR:path.join(out,'uploads')};
const seed=`
from datetime import date,time
from app.database.session import Base,engine,SessionLocal
from app.database.models import Empresa,Escala,Funcionario,Competencia,MarcacaoPonto
Base.metadata.create_all(engine)
with SessionLocal() as db:
 e=Empresa(nome='Empresa Fictícia UX');db.add(e);db.flush()
 s=Escala(empresa_id=e.id,nome='Escala Fictícia',jornada_seg_sex_horas=8);db.add(s);db.flush()
 c=Competencia(empresa_id=e.id,mes=9,ano=2026);db.add(c);db.flush()
 for i,(nome,exibicao) in enumerate([('ANA ORIGEM','Ana de Teste'),('BRUNO ORIGINAL','Bruno Limpo'),('CARLA ORIGINAL','Carla Problema')],1):
  f=Funcionario(empresa_id=e.id,escala_id=s.id,nome=nome,codigo='00089451'+str(i),nome_exibicao=exibicao,codigo_exibicao=str(46+i).zfill(3));db.add(f);db.flush()
  for n in range(1,31):
   problem=n==8 and i!=2
   m=MarcacaoPonto(competencia_id=c.id,funcionario_id=f.id,data=date(2026,9,n),entrada=None if problem else time(8),saida_almoco=None if problem else time(12),retorno_almoco=None if problem else time(13),saida=None if problem else time(17),origem='txt_id_tempo_maquina',batidas_originais='["08:00:00","12:00:00","17:00:00"]' if problem else '["08:00:00","12:00:00","13:00:00","17:00:00"]');db.add(m)
 db.commit()
`;
async function main(){
 const seeded=spawnSync(python,['-c',seed],{cwd:path.join(root,'backend'),env,encoding:'utf8',windowsHide:true});
 assert.equal(seeded.status,0,seeded.stderr);
 const reserve=http.createServer();await new Promise(r=>reserve.listen(0,'127.0.0.1',r));const port=reserve.address().port;await new Promise(r=>reserve.close(r));
 const api=spawn(python,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(port),'--log-level','warning'],{cwd:path.join(root,'backend'),env,windowsHide:true,stdio:'ignore'});
 const base='http://127.0.0.1:'+port;
 const server=http.createServer((req,res)=>{const url=new URL(req.url,'http://localhost');const target=path.resolve(root,'frontend','.'+url.pathname);if(!target.startsWith(path.join(root,'frontend')+path.sep)){res.writeHead(403).end();return;}fs.readFile(target,(err,data)=>{if(err){res.writeHead(404).end();return;}res.setHeader('Content-Type',target.endsWith('.js')?'text/javascript':target.endsWith('.css')?'text/css':target.endsWith('.svg')?'image/svg+xml':'text/html');res.end(data);});});
 let browser;
 try{
  for(let i=0;i<100;i++){try{if((await fetch(base)).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  browser=await chromium.launch({headless:true, channel:process.env.ONPONTO_BROWSER_CHANNEL || (process.platform==='win32' ? 'chrome' : undefined)});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(apiBase=>localStorage.setItem('onponto.apiBase',apiBase),base);
  await page.goto('http://127.0.0.1:'+server.address().port+'/index.html#/empresas/1/competencias/1/conferencia');
  await page.locator('[data-action="select-review-employee"] option').filter({hasText:'Ana de Teste · 047 · 1 problema'}).waitFor({state:'attached'});
  const all=page.getByRole('button',{name:'Todos os dias',exact:true});await all.click();
  const measures=[];
  for(const [width,height] of [[1366,768],[1920,1080]]){
   await page.setViewportSize({width,height});await page.locator('.attendance-row').first().waitFor();
   const m=await page.evaluate(()=>{const grid=document.querySelector('.review-grid').getBoundingClientRect();const reason=document.querySelector('.has-problem .problem-cell').getBoundingClientRect();const rows=[...document.querySelectorAll('.attendance-row')];return {top:grid.top,bottom:grid.bottom,visibleRows:rows.filter(r=>{let b=r.getBoundingClientRect();return b.top>=grid.top&&b.bottom<=Math.min(grid.bottom,innerHeight);}).length,reasonVisible:reason.left>=grid.left&&reason.right<=grid.right,overflow:document.documentElement.scrollWidth>innerWidth};});
   assert.ok(m.reasonVisible,JSON.stringify(m));assert.ok(m.visibleRows>=9,JSON.stringify(m));assert.equal(m.overflow,false);
   await page.screenshot({path:path.join(out,`conferencia-${width}x${height}.png`)});measures.push({width,height,...m});
  }
  await page.locator('[data-action="search-employees"]').fill('000894511');
  assert.equal(await page.locator('[data-action="select-review-employee"] option').count(),2);
  await page.locator('[data-action="search-employees"]').fill('');
  await page.locator('[data-action="next-problem-employee"]').click();
  assert.equal(await page.locator('[data-action="select-review-employee"]').inputValue(),'3');
  assert.equal(await page.locator('[data-action="next-problem-employee"]').isDisabled(),true);
  await page.locator('[data-action="select-review-employee"]').selectOption('1');
  await page.locator('[data-action="assign-original-punch"][data-punch-index="0"]').selectOption('entry');
  await page.waitForFunction(()=>document.querySelector('.autosave-indicator')?.textContent.includes('salvas'));
  let rows=await(await fetch(base+'/marcacoes?competencia_id=1&funcionario_id=1')).json();let day=rows.find(d=>d.data==='2026-09-08');
  assert.equal(day.entrada,'08:00:00');assert.deepEqual(day.batidas_originais,['08:00:00','12:00:00','17:00:00']);assert.ok(day.historico.length);
  await page.keyboard.press('Escape');await page.locator('.day-select-button').first().focus();await page.keyboard.press('Control+z');
  await page.waitForFunction(()=>document.querySelector('.autosave-indicator')?.textContent.includes('salvas'));
  rows=await(await fetch(base+'/marcacoes?competencia_id=1&funcionario_id=1')).json();day=rows.find(d=>d.data==='2026-09-08');assert.equal(day.entrada,null);
  assert.deepEqual(errors,[]);console.log(JSON.stringify({out,measures,checks:'identity, original-code search, next problem, assisted assignment, autosave, persisted audit, undo, no browser errors'},null,2));
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));api.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
