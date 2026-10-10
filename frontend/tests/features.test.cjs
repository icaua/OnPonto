const {test}=require('node:test'),assert=require('node:assert/strict');
const Api=require('../js/features/api.js');
const Navigation=require('../js/features/navigation.js');
const Store=require('../js/features/store.js');
const Importacao=require('../js/features/importacao.js');
const Conferencia=require('../js/features/conferencia.js');
const Escalas=require('../js/features/escalas.js');
const Relatorios=require('../js/features/relatorios.js');

test('cliente exportado envia JSON e preserva detalhe e revisão em 409',async()=>{
 let options;
 const root={setTimeout,clearTimeout,fetch:async(url,o)=>{options=o;assert.equal(url,'http://127.0.0.1:8000/marcacoes/1');
   return {ok:false,status:409,text:async()=>JSON.stringify({detail:{codigo:'revisao_conflitante',mensagem:'Revise a edição'}})};}};
 const api=Api.create({root,configuredApiBase:()=> 'http://127.0.0.1:8000'});
 await assert.rejects(api.apiRequest('/marcacoes/1',{method:'PATCH',body:{revisao:4}}),error=>{
  assert.equal(error.message,'Revise a edição');assert.equal(error.status,409);assert.ok(api.isRevisionConflictError(error));return true;
 });
 assert.deepEqual(JSON.parse(options.body),{revisao:4});assert.equal(options.headers['Content-Type'],'application/json');
});

test('navegação exportada valida vínculo de competência e mantém URL existente',()=>{
 const navigation=Navigation.create({VIEWS:['companies','review'],COMPANY_VIEWS:[],COMPETENCY_VIEWS:['review'],
  ROUTE_ALIASES:{conferencia:'review'},asId:Number,idsEqual:(a,b)=>String(a)===String(b),
  companies:()=>[{id:1}],competencies:()=>[{id:2,empresa_id:1},{id:3,empresa_id:9}],state:{}});
 assert.equal(navigation.routeHash(navigation.parseHashRoute('#/empresas/1/competencias/2/conferencia')),'#/empresas/1/competencias/2/conferencia');
 assert.equal(navigation.validateRoute({view:'review',companyId:1,competenceId:3}).view,'companies');
});

test('store exportado preserva indisponível e número oficial sem recalcular',()=>{
 const store=Store.create();const summary=store.normalizeCompetenceSummary({resumo:[{funcionario_id:1,extras_minutos:null,atrasos_minutos:0,
  dsr_desconto_dias:null}],origem:'triagem_derivada'});
 assert.equal(summary.rows[0].extraMinutes,null);assert.equal(summary.rows[0].delayMinutes,0);assert.equal(summary.rows[0].dsrDiscount,null);
});

test('conferência exportada aguarda apuração oficial durante edição online',()=>{
 const confer=Conferencia.create({state:{apiMode:'online'},Utils:{calculateJourney:()=>({workedMinutes:480,balanceMinutes:0})},currentSlots:()=>({})});
 const day={current:{}};confer.recalculateDay(day);
 assert.equal(day.workedMinutes,null);assert.equal(day.balanceMinutes,null);assert.equal(day.calculoProvisorio,true);
});

test('importação exportada mantém conflitos explícitos e escalas não ativam política legada',()=>{
 const imports=Importacao.create({firstValue:(...v)=>v.find(x=>x!==undefined && x!==null)});
 assert.deepEqual(imports.importConflictMessages({conflitos:[{mensagem:'Pessoa não encontrada'}]}),['Pessoa não encontrada']);
 assert.equal(Escalas.create().hourPolicyPayload({politica_modo:'legado'}),null);
});

test('relatórios exportados sanitizam nome de download e preservam conteúdo oficial',()=>{
 const reports=Relatorios.create();const name=reports.exportFilename({headers:{get:()=> 'attachment; filename="../ficticio.xlsx"'}},{},{});
 assert.equal(name,'.._ficticio.xlsx');assert.ok(!name.includes('/'));
});
