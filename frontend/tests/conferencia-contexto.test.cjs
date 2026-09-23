const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
function extract(name, text = source) {
  const start = text.indexOf('  function ' + name + '(');
  assert.ok(start >= 0, name);
  const end = text.indexOf('\n  function ', start + 1);
  return text.slice(start, end < 0 ? undefined : end);
}
function context(values, names) {
  const c = vm.createContext(values);
  for (const name of names) vm.runInContext(extract(name), c);
  return c;
}
function selection(visible) {
  const day = n => ({id:n, date:`2026-09-${String(n).padStart(2,'0')}`});
  return context({state:{selectedDayId:18,selectedDayIds:[18,21]},
    findDay:() => day(18), visibleReviewDays:() => visible.map(day), idsEqual:(a,b) => a===b}, ['ensureReviewSelection']);
}
test('dia removido do filtro seleciona o proximo cronologico mesmo com lista desordenada', () => {
  const c=selection([25,1,21,17]); c.ensureReviewSelection();
  assert.equal(c.state.selectedDayId,21); assert.deepEqual([...c.state.selectedDayIds],[21]);
});
test('sem proximo seleciona anterior imediato; lista vazia limpa selecao', () => {
  const c=selection([17,1]); c.ensureReviewSelection(); assert.equal(c.state.selectedDayId,17);
  c.visibleReviewDays=()=>[]; c.ensureReviewSelection(); assert.equal(c.state.selectedDayId,null);
});
test('selecao ainda visivel e preservada e ausencia de referencia usa primeiro item', () => {
  const c=selection([1,18,21]); c.ensureReviewSelection(); assert.equal(c.state.selectedDayId,18);
  c.state.selectedDayId=null; c.findDay=()=>null; c.ensureReviewSelection(); assert.equal(c.state.selectedDayId,1);
});
test('preserva rolagem vertical e horizontal da tabela e do contexto apos recriacao', () => {
  let nodes={'.attendance-table-wrap':{scrollTop:740,scrollLeft:360},'.review-context':{scrollTop:190,scrollLeft:20}};
  const main={dataset:{reviewKey:'contexto'},querySelector:s=>nodes[s]};
  const c=context({},['captureReviewScroll','restoreReviewScroll']);
  const saved=c.captureReviewScroll(main,'contexto');
  nodes={'.attendance-table-wrap':{scrollTop:0,scrollLeft:0},'.review-context':{scrollTop:0,scrollLeft:0}};
  c.restoreReviewScroll(main,saved);
  assert.equal(nodes['.attendance-table-wrap'].scrollTop,740);
  assert.equal(nodes['.attendance-table-wrap'].scrollLeft,360);
  assert.equal(nodes['.review-context'].scrollTop,190);
  assert.equal(nodes['.review-context'].scrollLeft,20);
  assert.equal(c.captureReviewScroll(main,'outro funcionario, competencia ou filtro'),null);
  assert.equal(c.captureReviewScroll(main,''),null);
});
function occurrences(api = async()=>({id:7})) {
  const calls=[], events=[]; let dialog;
  const window={OnPontoUtils:{escapeHtml:String}};
  const c=vm.createContext({window,URLSearchParams,Promise});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/ocorrencias.js'),'utf8'),c);
  const module=window.OnPontoOcorrencias;
  module.configure({state:()=>({selectedCompanyId:1,apiMode:'online'}),data:()=>({employees:[{id:5,companyId:1,name:'João'}]}),
    dialog:config=>{dialog=config;},api:async(url,options)=>{calls.push({url,options});return api(url,options);},
    invalidate:()=>events.push('invalidate'),render:()=>events.push('render')});
  return {module,calls,events,get dialog(){return dialog;}};
}
const defaults={funcionario_id:5,tipo:'ATESTADO',data_inicio:'2026-09-18',data_fim:'2026-09-18'};
test('cadastro reutilizado preenche integral e envia POST real apos salvar batidas pendentes', async()=>{
  const c=occurrences();
  c.module.create(defaults,{beforeSave:()=>c.events.push('flush'),onSaved:()=>c.events.push('refresh')});
  const values=Object.fromEntries(c.dialog.fields.map(f=>[f.name,f.value]));
  assert.equal(values.funcionario_id,5); assert.equal(values.periodo,'integral');
  assert.equal(values.data_inicio,'2026-09-18'); assert.equal(values.data_fim,'2026-09-18');
  const saved=await c.dialog.onConfirm(values);
  assert.equal(c.calls[0].url,'/ocorrencias'); assert.equal(c.calls[0].options.method,'POST');
  assert.equal(c.calls[0].options.body.hora_inicio,null); assert.equal(saved.id,7);
  assert.deepEqual(c.events,['flush','invalidate']);
  await c.dialog.onSaved(saved); assert.equal(c.events.at(-1),'refresh');
});
test('parcial envia horas e data final igual a inicial',async()=>{
  const c=occurrences(); c.module.create(defaults,{onSaved(){}});
  await c.dialog.onConfirm({...defaults,periodo:'parcial',hora_inicio:'13:00',hora_fim:'18:00',data_fim:'2026-09-30',observacao:'Consulta'});
  const payload=c.calls[0].options.body;
  assert.equal(payload.hora_inicio,'13:00'); assert.equal(payload.hora_fim,'18:00');
  assert.equal(payload.data_fim,defaults.data_inicio); assert.equal(payload.observacao,'Consulta');
});
test('falha ao salvar batidas impede criar ocorrencia e erro da API permite corrigir formulario',async()=>{
  const c=occurrences(); c.module.create(defaults,{beforeSave(){throw Error('Falha ao salvar batidas');},onSaved(){}});
  await assert.rejects(c.dialog.onConfirm({...defaults,periodo:'integral'}),/batidas/); assert.equal(c.calls.length,0);
  const rejected=occurrences(async()=>{throw Error('Sobreposição');}); rejected.module.create(defaults,{onSaved(){}});
  await assert.rejects(rejected.dialog.onConfirm({...defaults,periodo:'integral'}),/Sobreposição/);
  assert.deepEqual(rejected.events,[]);
});
test('tela original de Ocorrencias continua criando, carregando e editando via PATCH',async()=>{
  const item={id:7,...defaults};
  const c=occurrences(async(url,options)=>options ? item : [item]);
  const element={matches:()=>false,dataset:{ocId:'7'}};
  c.module.action('ocorrencia-new',element,{preventDefault(){}});
  await c.dialog.onConfirm({...defaults,periodo:'integral'});
  assert.equal(c.calls[0].options.method,'POST'); assert.match(c.calls[1].url,/^\/ocorrencias\?/);
  c.module.action('ocorrencia-edit',element,{preventDefault(){}});
  assert.equal(c.dialog.title,'Editar ocorrência');
  await c.dialog.onConfirm({...defaults,periodo:'integral'});
  assert.equal(c.calls[2].url,'/ocorrencias/7'); assert.equal(c.calls[2].options.method,'PATCH');
});
test('conferencia recarrega marcacoes e apuracao sem mudar funcionario, filtro ou competencia',async()=>{
  let initial,hooks;const events=[];
  const state={selectedCompetenceId:9,selectedEmployeeId:5,selectedDayId:18,reviewFilter:'pending',apiMode:'online'};
  const c=context({state,ensureCompetencyWritable:()=>true,dayIsConfirmed:d=>d.confirmed,
    root:{OnPontoOcorrencias:{create:(values,options)=>{initial=values;hooks=options;}}},
    ensureAutosaveFlushedForLifecycle:async()=>{},refreshAffectedCompetence:async(id,options)=>{events.push([id,options.reloadAttendance]);return {summary:{}};},
    render:()=>events.push('render'),showToast:()=>{}},['addReviewCertificate']);
  const before=JSON.stringify(state);c.addReviewCertificate({id:18,employeeId:5,date:'2026-09-18'});
  assert.equal(initial.funcionario_id,5);await hooks.onSaved();
  assert.deepEqual(events,[[9,true],'render']);assert.equal(JSON.stringify(state),before);
  c.refreshAffectedCompetence=async()=>({summary:null});
  await assert.rejects(hooks.onSaved(),/apuração não foi carregada/);
  for(const blocked of ['confirmed','closed','offline']){
    initial=null; c.ensureCompetencyWritable=()=>blocked!=='closed';state.apiMode=blocked==='offline'?'demo':'online';
    c.addReviewCertificate({confirmed:blocked==='confirmed'});assert.equal(initial,null);
  }
});
test('dialogo fecha antes de atualizar apuracao; falha de atualizacao nao permite duplicar POST',async()=>{
  const events=[];const current={config:{fields:[],onConfirm:async()=>({id:7}),onSaved:async()=>{events.push('refresh');throw Error('Sem rede');}}};
  const c=context({pendingDialog:current,clearDialogError(){},dialogValues:()=>({}),validateDialog:()=>null,
    setDialogBusy(){},setDialogError:()=>assert.fail('Nao deve reabrir formulario ja salvo'),
    closeDialog:()=>{events.push('close');c.pendingDialog=null;},showToast:message=>events.push(message)},['confirmDialog']);
  c.confirmDialog();await new Promise(setImmediate);
  assert.deepEqual(events.slice(0,2),['close','refresh']);assert.match(events[2],/Registro salvo/);
});
test('painel e fallback oferecem atestado com batidas e preservam bloqueio de dia conferido',()=>{
  for(const [file,name,extra] of [
    ['components.js','defaultDayActions',{reviewState:d=>d.confirmed?'confirmed':'normal',resolveStatus:v=>({key:v}),dayStatus:()=> 'normal',array:v=>v||[]}],
    ['screens.js','contextActions',{originalPunchValues:()=>['09:00','12:00'],normalizeStatus:v=>v,dayStatus:()=> 'normal',dayConfirmed:d=>d.confirmed}]
  ]){
    const c=vm.createContext(extra);vm.runInContext(extract(name,fs.readFileSync(path.join(__dirname,'../js',file),'utf8')),c);
    assert.ok(c[name]({},['09:00','12:00']).some(a=>a.action==='set-day-certificate'));
    assert.ok(!c[name]({confirmed:true},['09:00','12:00']).some(a=>a.action==='set-day-certificate'));
  }
});

test('painel mostra abono retornado pela API e oculta acoes em competencia fechada',()=>{
  const c=vm.createContext({window:{},Intl,Date});
  for(const file of ['utils.js','components.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../js',file),'utf8'),c);
  const html=c.window.OnPontoComponents.DayDetailsPanel({readonly:true,
    day:{id:22,date:'2026-09-22',status:'normal',occurrenceLabel:'ATESTADO',excusedMinutes:300,originalPunches:['09:00','12:00']}});
  assert.match(html,/ATESTADO/);assert.match(html,/Abono calculado: 300 min/);
  assert.doesNotMatch(html,/data-action="set-day-certificate"/);
});
