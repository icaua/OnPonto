const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
function extract(name){const a=source.indexOf('  function '+name+'(');assert.ok(a>=0);const b=source.indexOf('\n  function ',a+1);return source.slice(a,b);}
function setup(extra={}){
  const c={root:{clearTimeout(){},setTimeout(){}},autosaveTimer:null,autosaveFlushPromise:null,
    pendingDaySaves:{1:{id:1,payload:{entrada:'08:00'}}},activeDaySaves:{},
    state:{apiMode:'online',settings:{autosave:true}},updateAutosaveIndicator(){},findDay(){return null;},
    isClosedCompetenceError:()=>false,showToast(){},refreshAffectedCompetence:async()=>{},render(){},
    idsEqual:(a,b)=>String(a)===String(b),...extra};
  vm.createContext(c);vm.runInContext(extract('flushPendingDaySaves'),c);return c;
}
test('salva sequencialmente e so indica salvo apos todas as respostas',async()=>{
  const callbacks=[],calls=[];
  const c=setup({apiRequest:(url)=>{calls.push(url);return new Promise(resolve=>callbacks.push(resolve));}});
  c.pendingDaySaves[2]={id:2,payload:{entrada:'09:00'}};
  const work=c.flushPendingDaySaves();await new Promise(setImmediate);
  assert.equal(calls.length,1);assert.equal(c.state.autosaveStatus,'saving');
  callbacks.shift()({});await new Promise(setImmediate);
  assert.equal(calls.length,2);assert.equal(c.state.autosaveStatus,'saving');
  callbacks.shift()({});await work;assert.equal(c.state.autosaveStatus,'saved');
});
test('falha nao descarta edicao mais recente e nova tentativa envia ultimo valor',async()=>{
  let reject;const payloads=[];
  const c=setup({apiRequest:(url,options)=>{payloads.push(options.body);return new Promise((r,j)=>{reject=j;});}});
  const work=c.flushPendingDaySaves();await new Promise(setImmediate);
  c.pendingDaySaves[1]={id:1,payload:{entrada:'08:35'}};
  reject(new Error('Sem conexão'));await work;
  assert.equal(c.state.autosaveStatus,'error');assert.equal(c.pendingDaySaves[1].payload.entrada,'08:35');
  c.apiRequest=async(url,options)=>{payloads.push(options.body);return {};};
  await c.flushPendingDaySaves();assert.equal(payloads[1].entrada,'08:35');assert.equal(c.state.autosaveStatus,'saved');
});
test('recarregar competencia preserva edicoes pendentes e em envio',()=>{
  const local=[{id:1,competenceId:7,entrada:'08:35'},{id:2,competenceId:7,entrada:'09:15'}];
  const c=setup({data:{},days:()=>local,findDay:id=>local.find(d=>d.id===id),activeDaySaves:{2:{}}});
  vm.runInContext(extract('replaceAttendanceForCompetence'),c);
  c.replaceAttendanceForCompetence(7,[{id:1,entrada:'08:00'},{id:2,entrada:'09:00'}]);
  assert.equal(c.data.dias[0].entrada,'08:35');assert.equal(c.data.dias[1].entrada,'09:15');
});
test('saida de pagina avisa inclusive com autosave desligado ou envio em curso',()=>{
  const c=setup({editSession:null});vm.runInContext(extract('guardUnsavedPageExit'),c);
  for(const scenario of [{pending:{1:{}},active:null,edit:null},{pending:{},active:Promise.resolve(),edit:null},{pending:{},active:null,edit:{}}]){
    c.pendingDaySaves=scenario.pending;c.autosaveFlushPromise=scenario.active;c.editSession=scenario.edit;
    c.state.settings.autosave=false;let stopped=false;const event={preventDefault(){stopped=true;}};
    c.guardUnsavedPageExit(event);assert.ok(stopped);assert.equal(event.returnValue,'');
  }
  c.pendingDaySaves={};c.autosaveFlushPromise=null;c.editSession=null;
  c.guardUnsavedPageExit({preventDefault(){assert.fail('Nao deve bloquear pagina salva');}});
});
test('resposta de apuracao antiga nao sobrescreve status de nova edicao pendente',()=>{
  const day={id:1,competenceId:7,status:'falta'};
  const c=setup({days:()=>[day]});vm.runInContext(extract('applyApurationDetails'),c);
  c.applyApurationDetails(7,[{id:1,status_dia:'normal'}]);assert.equal(day.status,'falta');
});

function setupDecision(extra={}) {
  const day={id:1,competenceId:7,history:[],batidas_desconsideradas:[]};
  const c=setup({findDay:()=>day,...extra});
  vm.runInContext(extract('updateDayFromMarking')+'\n'+extract('originalPunchDecision'),c);
  return {c,day};
}

for (const operation of ['desconsiderar','restaurar']) {
  test(operation+' interrompe apos falha de PATCH e preserva edicao para nova tentativa',async()=>{
    const calls=[],toasts=[];
    const {c,day}=setupDecision({apiRequest:async()=>{throw new Error('Sem conexão');},
      showToast:(...args)=>toasts.push(args),refreshAffectedCompetence:async()=>calls.push('refresh')});
    await assert.rejects(c.originalPunchDecision(1,async()=>{calls.push('decision');return {};},'Sucesso'),/salvar todos os horários/);
    assert.deepEqual(calls,[]);
    assert.equal(c.pendingDaySaves[1].payload.entrada,'08:00');
    assert.equal(day.history.length,0);
    assert.ok(!toasts.some(t=>t[1]==='success'));
    c.apiRequest=async()=>{calls.push('patch');return {};};
    await c.originalPunchDecision(1,async()=>{calls.push('decision');return {batidas_desconsideradas:[{indice:1}]};},'Sucesso');
    assert.deepEqual(calls,['patch','decision','refresh']);
    assert.equal(day.batidas_desconsideradas[0].indice,1);
    assert.ok(toasts.some(t=>t[1]==='success'));
  });
}

test('decisao aguarda salvamento e recusa edicao nova ainda pendente',async()=>{
  let complete;let decided=false;
  const {c}=setupDecision({apiRequest:()=>new Promise(resolve=>{complete=resolve;})});
  const work=c.originalPunchDecision(1,async()=>{decided=true;return {};},'Sucesso');
  await new Promise(setImmediate);
  assert.equal(decided,false);
  c.pendingDaySaves[1]={id:1,payload:{entrada:'08:35'}};
  complete({});
  await assert.rejects(work,/salvar todos os horários/);
  assert.equal(decided,false);
  assert.equal(c.pendingDaySaves[1].payload.entrada,'08:35');
});

test('decisao aguarda PATCH bem sucedido antes de atualizar historico e mostrar sucesso',async()=>{
  let complete;const calls=[];
  const {c,day}=setupDecision({apiRequest:()=>new Promise(resolve=>{complete=resolve;}),
    refreshAffectedCompetence:async()=>calls.push('refresh'),showToast:(text,type)=>calls.push(type)});
  const work=c.originalPunchDecision(1,async()=>{calls.push('decision');return {historico:[{title:'Batida restaurada'}]};},'Sucesso');
  await new Promise(setImmediate);
  assert.deepEqual(calls,[]);
  complete({});await work;
  assert.deepEqual(calls,['decision','refresh','success']);
  assert.equal(day.history[0].title,'Batida restaurada');
});

test('falha do PATCH por competencia fechada tambem interrompe decisao sem fila de repeticao',async()=>{
  let decided=false;
  const {c}=setupDecision({apiRequest:async()=>{throw new Error('Fechada');},isClosedCompetenceError:()=>true});
  await assert.rejects(c.originalPunchDecision(1,async()=>{decided=true;},'Sucesso'),/salvar todos os horários/);
  assert.equal(decided,false);
  assert.equal(Object.keys(c.pendingDaySaves).length,0);
});
