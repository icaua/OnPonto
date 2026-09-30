const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
function extract(name) {
  const a=source.indexOf('  function '+name+'('), b=source.indexOf('\n  function ',a+1);
  assert.ok(a>=0); return source.slice(a,b);
}
function setup() {
  const c={URLSearchParams, localStorage:{getItem:()=>null}}; c.window=c;
  vm.createContext(c);
  for (const file of ['mocks','utils','components','screens']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+file+'.js'),'utf8'),c);
  vm.runInContext(source.replace('\n  init();','\n  root.testApp={state,data,normalizeEmployee,applyApurationDetails};'),c);
  return c;
}
test('identidade usa fallback e personalizacao sem perder nome ou codigo original',()=>{
  const c=setup(), normalize=c.testApp.normalizeEmployee;
  const raw={id:1,nome:'JOAO FICTICIO',codigo:'000894512'};
  assert.equal(normalize(raw).name,raw.nome); assert.equal(normalize(raw).code,raw.codigo);
  const custom=normalize({...raw,nome_exibicao:'João Fictício',codigo_exibicao:'047'});
  assert.equal(custom.name,'João Fictício'); assert.equal(custom.code,'047');
  assert.equal(custom.nome,raw.nome); assert.equal(custom.codigo,raw.codigo);
});
test('busca local encontra as quatro identidades sem acentos',()=>{
  const c=setup(), e={nome:'ORIGINAL FICTICIO',codigo:'000894512',nome_exibicao:'João Fictício',codigo_exibicao:'047'};
  for(const q of ['joao','047','original','000894512']) assert.ok(c.OnPontoUtils.employeeMatches(e,q),q);
  assert.equal(c.OnPontoUtils.employeeMatches(e,'inexistente'),false);
});
test('proximo com problema pula limpos e nao retorna ao inicio',()=>{
  const c=setup(), staff=[{id:1},{id:2},{id:3},{id:4}], rows=[{employeeId:1,pending:2},{employeeId:2,pending:0,awaiting:20},{employeeId:3,pending:1},{employeeId:4,pending:0}];
  assert.equal(c.OnPontoUtils.nextProblemEmployee(staff,rows,1).id,3);
  assert.equal(c.OnPontoUtils.nextProblemEmployee(staff,rows,3),null);
  assert.equal(c.OnPontoUtils.nextProblemEmployee(staff,[],1),null);
});
test('seletor da conferencia usa contagem do backend e identidade personalizada',()=>{
  const c=setup(), a=c.testApp, e=a.data.employees[0];
  e.nome_exibicao='Pessoa Exibição'; e.codigo_exibicao='047';
  Object.assign(a.state,{route:'review',selectedCompanyId:e.companyId,selectedCompetenceId:1001,selectedEmployeeId:e.id,apiMode:'online'});
  a.data.competenceSummaries={1001:{rows:[{employeeId:e.id,pending:3,awaiting:17}]}};
  const html=c.OnPontoScreens.render('review',a.state,a.data,c.OnPontoComponents);
  assert.match(html,/Pessoa Exibição · 047 · 3 problemas/);
  assert.match(html,/Identificação no ponto/);
});
test('dia com problema nao recebe Normal e motivo antecede horarios',()=>{
  const c=setup(), day={id:1,date:'2026-09-08',status:'normal',problema:true,problemLabel:'Batida ímpar',pendingReason:'Intervalo incompleto.',current:{entry:'08:00',exit:'17:00'}};
  const html=c.OnPontoComponents.AttendanceTable({days:[day]});
  assert.match(html,/has-problem/); assert.match(html,/Batida ímpar/); assert.doesNotMatch(html,/>Normal</);
  assert.ok(html.indexOf('class="problem-cell"')<html.indexOf('data-action="edit-time"'));
  assert.doesNotMatch(c.OnPontoComponents.DayDetailsPanel({day}),/>Normal</);
});
test('painel oferece atribuicao so para batidas livres e edicao aberta',()=>{
  const c=setup(), day={id:1,date:'2026-09-08',originalPunches:['08:00:00','12:00:00','17:00:00'],current:{entry:'08:00'}};
  const html=c.OnPontoComponents.DayDetailsPanel({day});
  assert.equal((html.match(/data-action="assign-original-punch"/g)||[]).length,2);
  assert.match(html,/Já atribuída/);
  assert.doesNotMatch(c.OnPontoComponents.DayDetailsPanel({day,readonly:true}),/assign-original-punch/);
  assert.doesNotMatch(c.OnPontoComponents.DayDetailsPanel({day:{...day,confirmed:true}}),/assign-original-punch/);
});
function assignment() {
  const c=setup(), day={id:9,originalPunches:Object.freeze(['08:00:00','12:00:00','17:00:00']),current:{entry:'',breakStart:'',breakEnd:'',exit:''}}, saved=[];
  Object.assign(c,{Utils:c.OnPontoUtils,state:{undoStack:[]},findDay:()=>day,ensureCompetencyWritable:()=>true,dayIsConfirmed:d=>!!d.confirmed,currentSlots:d=>({...d.current}),applySlot:(d,k,v)=>{d.current[k]=v;},fieldLabel:x=>x,addHistory(){},queueAutosave:d=>saved.push({...d.current}),render(){},showToast(){}});
  vm.runInContext(extract('assignOriginalPunch'),c); vm.runInContext(extract('undoLastChange'),c);
  return {c,day,saved};
}
test('atribuicao usa autosave e undo preservando batidas originais',()=>{
  const {c,day,saved}=assignment(); c.assignOriginalPunch(9,0,'entry');
  assert.equal(day.current.entry,'08:00'); assert.equal(saved.length,1); assert.equal(c.state.undoStack.length,1);
  c.undoLastChange(); assert.equal(day.current.entry,''); assert.equal(saved.length,2);
  assert.deepEqual(day.originalPunches,['08:00:00','12:00:00','17:00:00']);
});
test('atribuicao rejeita duplicacao, campo ocupado, ordem invalida e dia conferido',()=>{
  const {c,day,saved}=assignment(); c.assignOriginalPunch(9,0,'entry');
  c.assignOriginalPunch(9,0,'exit'); c.assignOriginalPunch(9,1,'entry');
  assert.equal(saved.length,1);
  c.assignOriginalPunch(9,2,'breakStart'); c.assignOriginalPunch(9,1,'exit');
  assert.equal(saved.length,2); assert.equal(day.current.exit,'');
  day.confirmed=true; c.assignOriginalPunch(9,1,'breakEnd'); assert.equal(saved.length,2);
});

test('navegar ao proximo problema limpa busca e seleciona funcionario real',()=>{
  const c=setup(), staff=[{id:1},{id:2},{id:3}];let selected;
  Object.assign(c,{Utils:c.OnPontoUtils,state:{selectedCompetenceId:7,selectedEmployeeId:1,employeeSearch:'Ana'},data:{competenceSummaries:{7:{rows:[{employeeId:2,pending:0},{employeeId:3,pending:1}]}}},companyEmployees:()=>staff,selectEmployee:id=>{selected=id;},showToast(){}});
  vm.runInContext(extract('moveToProblemEmployee'),c);c.moveToProblemEmployee();
  assert.equal(selected,3);assert.equal(c.state.employeeSearch,'');assert.equal(c.state.reviewFilter,'pending');
});
