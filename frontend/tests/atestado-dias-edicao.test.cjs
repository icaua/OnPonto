const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function ocorrencias() {
  const c={URLSearchParams}; c.window=c;
  require('./module-loader.cjs').context(c);
  for (const file of ['utils','ocorrencias']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+file+'.js'),'utf8'),c);
  const dialogs=[],requests=[];
  c.OnPontoOcorrencias.configure({state:()=>({selectedCompanyId:1,apiMode:'online'}),
    data:()=>({employees:[{id:7,companyId:1,name:'Pessoa Fictícia'}]}),dialog:config=>dialogs.push(config),
    api:(url,options)=>{requests.push({url,options});return Promise.resolve({id:1});},invalidate(){},render(){}});
  return {c,dialogs,requests};
}
const campo=(config,nome)=>config.fields.find(f=>f.name===nome);
const visivel=(config,nome,valores)=>{const f=campo(config,nome);return !f.visibleWhen||f.visibleWhen(valores);};

test('atestado integral usa quantidade de dias e calcula o termino presumido',async()=>{
  const {c,dialogs,requests}=ocorrencias();
  c.OnPontoOcorrencias.create({funcionario_id:7,tipo:'ATESTADO',data_inicio:'2026-09-10',data_fim:'2026-09-10'},{onSaved(){}});
  const config=dialogs[0], v={funcionario_id:'7',tipo:'ATESTADO',periodo:'integral',data_inicio:'2026-09-10',dias:'3',observacao:''};
  assert.equal(campo(config,'dias').value,1);
  assert.ok(visivel(config,'dias',v)); assert.ok(!visivel(config,'data_fim',v));
  assert.match(campo(config,'dias').help(v),/12\/09\/2026.*retorno em 13\/09\/2026/);
  await config.onConfirm(v);
  assert.equal(requests[0].options.method,'POST');
  assert.equal(requests[0].options.body.data_fim,'2026-09-12');
});

test('dias atravessam o fim do mes e do ano sem erro de fuso',async()=>{
  const {c,dialogs,requests}=ocorrencias();
  c.OnPontoOcorrencias.create({funcionario_id:7,tipo:'ATESTADO'},{onSaved(){}});
  await dialogs[0].onConfirm({funcionario_id:'7',tipo:'ATESTADO',periodo:'integral',data_inicio:'2026-12-30',dias:'5',observacao:''});
  assert.equal(requests[0].options.body.data_fim,'2027-01-03');
});

test('edicao de atestado traz a quantidade de dias; parcial e ferias seguem por data',()=>{
  const {c,dialogs}=ocorrencias();
  c.OnPontoOcorrencias.create({funcionario_id:7,tipo:'ATESTADO',data_inicio:'2026-09-01',data_fim:'2026-09-15'},{onSaved(){}});
  const config=dialogs[0];
  assert.equal(campo(config,'dias').value,15);
  const parcial={tipo:'ATESTADO',periodo:'parcial'};
  assert.ok(!visivel(config,'dias',parcial)); assert.ok(visivel(config,'hora_inicio',parcial));
  const ferias={tipo:'FERIAS',periodo:'integral',data_inicio:'2026-09-10',data_fim:'2026-10-09'};
  assert.ok(!visivel(config,'dias',ferias)); assert.ok(visivel(config,'data_fim',ferias));
  assert.match(campo(config,'data_fim').help(ferias),/30 dias de férias; retorno em 10\/10\/2026.*não a data de retorno/);
  assert.match(campo(config,'data_fim').help({tipo:'AFASTAMENTO',data_inicio:'2026-09-10',data_fim:''}),/em aberto/);
});

const source=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
function extract(name){const a=source.indexOf('  function '+name+'(');assert.ok(a>=0,name);const b=source.indexOf('\n  function ',a+1);return source.slice(a,b);}

test('salvamento em segundo plano espera a edicao e devolve o foco a celula',()=>{
  const renders=[];
  const c={editSession:{},deferredRender:false,render:options=>renders.push(options),
    document:{activeElement:{closest:()=>({dataset:{dayId:'5',field:'breakStart'}})}}};
  require('./module-loader.cjs').context(c);vm.runInContext(extract('renderInBackground'),c);
  c.renderInBackground();
  assert.equal(renders.length,0); assert.equal(c.deferredRender,true);
  c.editSession=null; c.renderInBackground();
  assert.deepEqual(JSON.parse(JSON.stringify(renders[0])),{focus:{dayId:'5',field:'breakStart'}});
});

test('descartar horario invalido retoma salvamento agendado em vez de manter erro',()=>{
  const agendados=[];
  const cell={focus(){}};
  const base=()=>({editSession:{cell,dayId:5,field:'breakStart',original:'12:32'},deferredRender:false,autosaveFlushPromise:null,
    state:{autosaveStatus:'error'},restoreCell(){},competencyIsClosed:()=>false,updateAutosaveIndicator(){},
    queueAutosave:d=>agendados.push(d),render(){}});
  const pendente=Object.assign(base(),{pendingDaySaves:{5:{id:5}}});
  require('./module-loader.cjs').context(pendente);vm.runInContext(extract('cancelEditing'),pendente);
  pendente.cancelEditing();
  assert.deepEqual(agendados,[null]);
  const vazio=Object.assign(base(),{pendingDaySaves:{}});
  require('./module-loader.cjs').context(vazio);vm.runInContext(extract('cancelEditing'),vazio);
  vazio.cancelEditing();
  assert.equal(vazio.state.autosaveStatus,'saved'); assert.equal(agendados.length,1);
});

test('campo removido por redesenho nao grava horario digitado pela metade',()=>{
  const finished=[];
  const input={isConnected:false};
  const c={editSession:{input},finishEditing:o=>finished.push(o),document:{activeElement:null},
    root:{setTimeout:fn=>fn()}};
  require('./module-loader.cjs').context(c);vm.runInContext(extract('handleBlur'),c);
  c.handleBlur({target:input});
  assert.equal(finished.length,0); assert.equal(c.editSession,null);
  const conectado={isConnected:true}; c.editSession={input:conectado};
  c.handleBlur({target:conectado});
  assert.equal(finished.length,1);
});
