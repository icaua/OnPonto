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
 let api;
 const base='http://127.0.0.1:'+port;
 const server=http.createServer((req,res)=>{const url=new URL(req.url,'http://localhost');const target=path.resolve(root,'frontend','.'+url.pathname);if(!target.startsWith(path.join(root,'frontend')+path.sep)){res.writeHead(403).end();return;}fs.readFile(target,(err,data)=>{if(err){res.writeHead(404).end();return;}res.setHeader('Content-Type',target.endsWith('.js')?'text/javascript':target.endsWith('.css')?'text/css':target.endsWith('.svg')?'image/svg+xml':'text/html');res.end(data);});});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 api=spawn(python,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(port),'--log-level','warning'],{cwd:path.join(root,'backend'),env:{...env,ONPONTO_FRONTEND_ORIGINS:'http://127.0.0.1:'+server.address().port},windowsHide:true,stdio:'ignore'});
 let nodeSession;
 async function apiFetch(endpoint,options={}){
  if(!nodeSession)nodeSession=fetch(base+'/sessao/local').then(async r=>({cookie:r.headers.get('set-cookie').split(';')[0],csrf:(await r.json()).csrf}));
  const session=await nodeSession;
  return fetch(base+endpoint,{...options,headers:{...options.headers,Cookie:session.cookie,'X-OnPonto-CSRF':session.csrf}});
 }
 let browser;
 try{
  for(let i=0;i<100;i++){try{if((await fetch(base)).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({headless:true, channel:process.env.ONPONTO_BROWSER_CHANNEL || (process.platform==='win32' ? 'chrome' : undefined)});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(apiBase=>localStorage.setItem('onponto.apiBase',apiBase),base);
  const reviewRequests=[];page.on('request',r=>{if(r.url().startsWith(base))reviewRequests.push(r.url());});
  await page.goto('http://127.0.0.1:'+server.address().port+'/index.html#/empresas/1/competencias/1/conferencia');
  await page.locator('[data-action="select-review-employee"] option').filter({hasText:'Ana de Teste · 047 · 1 problema'}).waitFor({state:'attached'});
  assert.ok(reviewRequests.some(u=>u.includes('/apuracao/triagem?')));
  assert.equal(reviewRequests.some(u=>/\/apuracao\?/.test(u) || u.includes('/marcacoes?')),false);
  const all=page.getByRole('button',{name:'Todos os dias',exact:true});await all.click();
  const measures=[];
  for(const [width,height] of [[1366,768],[1920,1080]]){
   await page.setViewportSize({width,height});await page.locator('.attendance-row').first().waitFor();
   const m=await page.evaluate(()=>{const grid=document.querySelector('.review-grid').getBoundingClientRect();const reason=document.querySelector('.has-problem .problem-cell').getBoundingClientRect();const rows=[...document.querySelectorAll('.attendance-row')];return {top:grid.top,bottom:grid.bottom,visibleRows:rows.filter(r=>{let b=r.getBoundingClientRect();return b.top>=grid.top&&b.bottom<=Math.min(grid.bottom,innerHeight);}).length,reasonVisible:reason.left>=grid.left&&reason.right<=grid.right,overflow:document.documentElement.scrollWidth>innerWidth};});
   assert.ok(m.reasonVisible,JSON.stringify(m));assert.ok(m.visibleRows>=9,JSON.stringify(m));assert.equal(m.overflow,false);
   await page.screenshot({path:path.join(out,`conferencia-${width}x${height}.png`)});measures.push({width,height,...m});
  }
  await page.evaluate(()=>{
    const cell=document.querySelector('.editable-time-cell');window.testPreservedCell=cell;cell.focus();
    document.querySelector('.attendance-table-wrap').scrollTop=120;
    window.testScroll=document.querySelector('.attendance-table-wrap').scrollTop;
    window.OnPontoApp.getState().autosaveStatus='unsaved';window.OnPontoApp.render();
  });
  assert.equal(await page.evaluate(()=>window.testPreservedCell===document.querySelector('.editable-time-cell')),true);
  assert.equal(await page.evaluate(()=>document.activeElement===window.testPreservedCell),true);
  assert.equal(await page.evaluate(()=>document.querySelector('.attendance-table-wrap').scrollTop===window.testScroll),true);
  await page.evaluate(()=>{document.querySelector('.attendance-table-wrap').scrollTop=0;window.OnPontoApp.getState().autosaveStatus='saved';window.OnPontoApp.render();});
  await page.locator('[data-action="search-employees"]').fill('000894511');
  assert.equal(await page.locator('[data-action="select-review-employee"] option').count(),2);
  await page.locator('[data-action="search-employees"]').fill('');
  await page.locator('[data-action="next-problem-employee"]').click();
  assert.equal(await page.locator('[data-action="select-review-employee"]').inputValue(),'3');
  assert.equal(await page.locator('[data-action="next-problem-employee"]').isDisabled(),true);
  await page.locator('[data-action="select-review-employee"]').selectOption('1');
  await page.locator('[data-action="assign-original-punch"][data-punch-index="0"]').selectOption('entry');
  await page.waitForFunction(()=>document.querySelector('.autosave-indicator')?.textContent.includes('salvas'));
  let rows=await(await apiFetch('/marcacoes?competencia_id=1&funcionario_id=1')).json();let day=rows.find(d=>d.data==='2026-09-08');
  assert.equal(day.entrada,'08:00:00');assert.deepEqual(day.batidas_originais,['08:00:00','12:00:00','17:00:00']);assert.ok(day.historico.length);
  await page.keyboard.press('Escape');await page.locator('.day-select-button').first().focus();await page.keyboard.press('Control+z');
  await page.waitForFunction(()=>document.querySelector('.autosave-indicator')?.textContent.includes('salvas'));
  rows=await(await apiFetch('/marcacoes?competencia_id=1&funcionario_id=1')).json();day=rows.find(d=>d.data==='2026-09-08');assert.equal(day.entrada,null);
  const page2=await browser.newPage();page2.on('pageerror',e=>errors.push(e.message));
  await page2.addInitScript(apiBase=>localStorage.setItem('onponto.apiBase',apiBase),base);
  await page2.goto(page.url());
  await page2.locator('[data-action="assign-original-punch"][data-punch-index="0"]').waitFor();
  await page2.locator('[data-action="assign-original-punch"][data-punch-index="0"]').selectOption('entry');
  await page2.waitForFunction(()=>document.querySelector('.autosave-indicator')?.textContent.includes('salvas'));
  const saved=await(await apiFetch('/marcacoes/'+day.id)).json();
  await page.locator('[data-action="assign-original-punch"][data-punch-index="0"]').selectOption('entry');
  await page.getByText('Este dia foi alterado em outra janela',{exact:true}).waitFor();
  assert.deepEqual(await(await apiFetch('/marcacoes/'+day.id)).json(),saved);
  await page.locator('#dialogField').selectOption('server');
  await page.getByRole('button',{name:'Aplicar escolha',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.autosave-indicator')?.textContent.includes('salvas'));
  assert.deepEqual(await(await apiFetch('/marcacoes/'+day.id)).json(),saved);
  await page2.close();
  const summaryRequests=[];page.on('request',r=>{if(r.url().startsWith(base))summaryRequests.push(r.url());});
  await page.evaluate(()=>window.OnPontoApp.navigate('competency-summary'));
  await page.getByRole('heading',{name:'Resumo por funcionário',exact:true}).waitFor();
  assert.ok(summaryRequests.some(u=>u.includes('/apuracao/resumo?')));
  assert.equal(summaryRequests.some(u=>u.includes('/marcacoes?') || /\/apuracao\?/.test(u)),false);
  for(const [width,height] of [[1366,768],[1920,1080]]){
   await page.setViewportSize({width,height});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.screenshot({path:path.join(out,`resumo-${width}x${height}.png`)});
  }
  const cycles=[];
  async function post(endpoint,payload){const response=await apiFetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});assert.ok(response.ok,await response.clone().text());return response.json();}
  for(const [width,height] of [[1366,768],[1920,1080]]){
   const company=await post('/empresas',{nome:'Empresa Fictícia Ciclo '+width});
   const scale=await post('/escalas',{empresa_id:company.id,nome:'Escala Fictícia Ciclo',jornada_seg_sex_horas:8});
   const employee=await post('/funcionarios',{empresa_id:company.id,escala_id:scale.id,codigo:'X004',nome:'CICLO FICTICIO',data_admissao:'2026-09-01',data_demissao:'2026-09-01'});
   const competence=await post('/competencias',{empresa_id:company.id,ano:2026,mes:9});
   await page.setViewportSize({width,height});
   await page.goto('http://127.0.0.1:'+server.address().port+'/index.html?ciclo='+width+'#/empresas/'+company.id+'/competencias/'+competence.id+'/importacoes');
   await page.waitForLoadState('networkidle');
   await page.locator('[data-action="select-import-file"]').waitFor({state:'attached',timeout:10000}).catch(async e=>{console.error({errors,state:await page.evaluate(()=>window.OnPontoApp?.getState()),text:(await page.locator('body').innerText()).slice(-2500)});throw e;});
   await page.locator('[data-action="select-import-file"]').setInputFiles({name:'ciclo-ficticio.txt',mimeType:'text/plain',buffer:Buffer.from('ID\tNome\tTempo\n'+['08:00','12:00','13:00','17:00'].map(h=>'X004\tCICLO FICTICIO\t01/09/2026 '+h+':00\n').join(''))});
   await page.waitForFunction(()=>window.OnPontoApp.getState().selectedImportFile?.file,{},{timeout:5000}).catch(async e=>{console.error({errors,state:await page.evaluate(()=>({file:window.OnPontoApp.getState().selectedImportFile,loading:window.OnPontoApp.getState().importLoading})),files:await page.locator('#importFile').evaluate(e=>[...e.files].map(f=>f.name))});throw e;});
   await page.getByRole('button',{name:'Analisar arquivo',exact:true}).click();
   await page.getByRole('button',{name:'Ver prévia',exact:true}).waitFor({timeout:10000}).catch(async e=>{console.error({errors,text:(await page.locator('body').innerText()).slice(-3500),analysis:await page.evaluate(()=>window.OnPontoApp.getState().importError)});throw e;});
   await page.getByRole('button',{name:'Ver prévia',exact:true}).click();
   await page.locator('[data-action="save-import-start-review"]').waitFor();
   await page.locator('[data-action="save-import-start-review"]').click();
   await page.getByRole('button',{name:'Salvar e conferir',exact:true}).click();
   await page.locator('.attendance-row').waitFor();
   await page.locator('[data-action="toggle-all-days"]').check();
   await page.locator('[data-action="bulk-confirm"]').click();
   await page.locator('#dialogRoot').getByRole('button',{name:'Marcar como conferidos',exact:true}).click();
   await page.waitForFunction(()=>document.querySelector('.attendance-row')?.classList.contains('is-confirmed'));
   await page.evaluate(()=>window.OnPontoApp.navigate('competency-summary'));
   await page.getByRole('button',{name:'Fechar competência',exact:true}).click();
   await page.locator('#dialogRoot').getByRole('button',{name:'Fechar competência',exact:true}).click();
   await page.getByRole('button',{name:'Reabrir competência',exact:true}).waitFor();
   assert.equal((await(await apiFetch('/competencias/'+competence.id)).json()).status,'fechada');
   await page.evaluate(()=>window.OnPontoApp.navigate('competency-exports'));
   const downloadPromise=page.waitForEvent('download');
   await page.getByRole('button',{name:'Exportar Excel',exact:true}).click();
   const download=await downloadPromise;assert.match(download.suggestedFilename(),/\.xlsx$/);await download.saveAs(path.join(out,'ciclo-'+width+'.xlsx'));
   await page.evaluate(()=>window.OnPontoApp.navigate('competency-summary'));
   await page.getByRole('button',{name:'Reabrir competência',exact:true}).click();
   await page.locator('#dialogRoot').getByRole('button',{name:'Reabrir competência',exact:true}).click();
   await page.getByRole('button',{name:'Fechar competência',exact:true}).waitFor();
   assert.notEqual((await(await apiFetch('/competencias/'+competence.id)).json()).status,'fechada');
   const history=await(await apiFetch('/competencias/'+competence.id+'/fechamentos')).json();assert.ok(history.length);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.screenshot({path:path.join(out,'ciclo-'+width+'.png')});cycles.push({width,height,companyId:company.id,competenceId:competence.id,employeeId:employee.id});
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({out,measures,cycles,checks:'identity, original-code search, next problem, assisted assignment, autosave, persisted audit, undo, two windows and explicit 409 resolution, no browser errors'},null,2));
 }finally{if(browser)await browser.close();await new Promise(r=>server.close(r));api.kill();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
