const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const app=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
function extract(name){const start=app.indexOf('  function '+name+'(');assert.ok(start>=0);return app.slice(start,app.indexOf('\n  function ',start+1));}
function modules(){const ctx={};ctx.window=ctx;vm.createContext(ctx);for(const f of ['utils','components','screens'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+f+'.js'),'utf8'),ctx);return ctx;}
test('demissao opcional no formulario valida intervalo e envia null ao limpar',async()=>{
  let dialog,request;
  const person={id:3,companyId:1,name:'Pessoa',data_admissao:'2026-06-10',data_demissao:'2026-06-15'};
  const ctx={companies:()=>[{id:1}],employees:()=>[person],currentCompany:()=>({id:1}),state:{apiMode:'online'},
    loadedCompanyScales:{1:true},companyScales:()=>[],firstValue:(...xs)=>xs.find(x=>x!=null)??null,
    idsEqual:(a,b)=>a===b,asId:x=>x||null,showDialog:d=>dialog=d,UF_OPTIONS:[],
    apiRequest:async(url,config)=>{request=config;return config.body;},upsertEntity(){},normalizeEmployee:x=>x,
    compareEntityNames(){},invalidateCompanyCompetenceData(){},render(){},showToast(){}};
  vm.createContext(ctx);vm.runInContext(extract('openSimpleEntityDialog'),ctx);ctx.openSimpleEntityDialog('employee',3);
  const field=dialog.fields.find(f=>f.name==='data_demissao');assert.equal(field.value,'2026-06-15');assert.equal(field.type,'date');assert.ok(!field.required);
  assert.equal(dialog.validate({data_admissao:'2026-06-10',data_demissao:'2026-06-09'}).field,'data_demissao');
  await dialog.onConfirm({nome:'Pessoa',codigo:'1',ativo:'true',data_admissao:'2026-06-10',data_demissao:'2026-06-15'});
  assert.equal(request.body.data_demissao,'2026-06-15');
  await dialog.onConfirm({nome:'Pessoa',codigo:'1',ativo:'true',data_demissao:''});assert.equal(request.body.data_demissao,null);
});
test('resumo normaliza snapshots antigos para zero e preserva feriado indisponivel',()=>{
  const ctx={apiCollection:(obj,keys)=>keys.map(k=>obj[k]).find(Array.isArray)||[],
    valueFromAliases:(obj,keys)=>keys.map(k=>obj?.[k]).find(v=>v!==undefined&&v!==null)??null};
  vm.createContext(ctx);vm.runInContext(extract('normalizeCompetenceSummary'),ctx);
  for(const [record,expected] of [[{},0],[{horas_feriado_minutos:240},240],[{horas_feriado_minutos:null},null]]) {
    assert.equal(ctx.normalizeCompetenceSummary({resumo:[record]}).rows[0].holidayMinutes,expected);
  }
});
test('resumo exibe horas 100 separadas e cadastro lista demissao',()=>{
  const ctx=modules();const data={companies:[{id:1,name:'Empresa'}],employees:[{id:3,companyId:1,name:'Pessoa',data_admissao:'2026-06-10',data_demissao:'2026-06-15'}],
    competencies:[{id:2,companyId:1,month:6,year:2026,status:'aberta'}],competenceSummaries:{2:{general:{},rows:[{employeeName:'Pessoa',delays:'00:00',extras:'00:00',holidayMinutes:240,situation:'conferido'}]}}};
  const state={apiMode:'online',selectedCompanyId:1,selectedCompetenceId:2};
  const html=ctx.OnPontoScreens.renderCompetencySummary(state,data,ctx.OnPontoComponents);
  assert.match(html,/>Horas 100% \(feriado\)</);assert.match(html,/<td>04:00<\/td>/);
  const cadastro=ctx.OnPontoScreens.renderCompanyEmployees(state,data,ctx.OnPontoComponents);
  assert.match(cadastro,/<th>Demissão<\/th>/);assert.match(cadastro,/15\/06\/2026/);
});
