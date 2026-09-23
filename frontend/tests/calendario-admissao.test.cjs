const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
function extract(name) {
  const start=source.indexOf('  function '+name+'('), end=source.indexOf('\n  function ',start+1);
  assert.ok(start>=0,name); return source.slice(start,end);
}
function modules() {
  const ctx={URLSearchParams}; ctx.window=ctx; vm.createContext(ctx);
  for (const file of ['utils','components','screens','calendario']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+file+'.js'),'utf8'),ctx);
  return ctx;
}
test('resumo estrutura nome/codigo, aviso fechado, badge unico e indisponivel discreto',()=>{
  const ctx=modules();
  const data={companies:[{id:1,name:'Empresa'}],competencies:[{id:2,companyId:1,month:6,year:2026,status:'fechada',data_fechamento:'2026-09-10'}],
    employees:[],competenceSummaries:{2:{general:{},rows:[{employeeName:'gloria',employeeCode:3,processedDays:13,situation:'pendente'},
      {employeeName:'Pessoa',employeeCode:4,processedDays:30,situation:'conferido',delays:'00:00',extras:'00:00'},
      {employeeName:'Erro',situation:'bloqueado'}]}}};
  const html=ctx.OnPontoScreens.renderCompetencySummary({apiMode:'online',selectedCompanyId:1,selectedCompetenceId:2},data,ctx.OnPontoComponents);
  assert.match(html,/<div class="summary-employee"><strong>gloria<\/strong><small>Código 3<\/small><\/div>/);
  assert.match(html,/Competência fechada em 10\/09\/2026<\/strong><p>Os dados/);
  assert.match(html,/<span class="summary-unavailable">Indisponível<\/span>/);
  assert.equal((html.match(/data-status="closed"/g)||[]).length,1);
  assert.match(html,/tone-danger[^>]*>.*?Bloqueado/);
  assert.match(html,/tone-warning[^>]*>.*?Pendente/);
  assert.match(html,/tone-success[^>]*>.*?Conferido/);
});
test('rota calendario e global mesmo sem empresa cadastrada',()=>{
  const ctx={VIEWS:['companies','calendar'],COMPANY_VIEWS:[],COMPETENCY_VIEWS:[],emptyRoute:()=>({view:'companies',companyId:null,competenceId:null}),
    companies:()=>[],competencies:()=>[],asId:x=>x,safeDecode:decodeURIComponent};
  vm.createContext(ctx);
  for(const name of ['parseHashRoute','validateRoute','routeHash']) vm.runInContext(extract(name),ctx);
  const route=ctx.validateRoute(ctx.parseHashRoute('#/calendario'));
  assert.equal(route.view,'calendar'); assert.equal(route.companyId,null); assert.equal(route.competenceId,null);
  assert.equal(ctx.routeHash(route),'#/calendario');
});
test('cadastro e edicao enviam admissao opcional e permitem limpar',async()=>{
  for(const item of [null,{id:3,companyId:1,name:'Pessoa',data_admissao:'2026-06-18'}]) {
    let dialog,request;
    const ctx={companies:()=>[{id:1}],employees:()=>item?[item]:[],currentCompany:()=>({id:1}),state:{apiMode:'online'},
      loadedCompanyScales:{1:true},companyScales:()=>[],firstValue:(...xs)=>xs.find(x=>x!=null)??null,
      idsEqual:(a,b)=>a===b,asId:x=>x||null,showDialog:d=>dialog=d,UF_OPTIONS:[],
      apiRequest:async(url,config)=>{request={url,...config};return config.body;},upsertEntity(){},normalizeEmployee:x=>x,
      compareEntityNames(){},invalidateCompanyCompetenceData(){},render(){},showToast(){}};
    vm.createContext(ctx);vm.runInContext(extract('openSimpleEntityDialog'),ctx);
    ctx.openSimpleEntityDialog('employee',item?.id);
    const field=dialog.fields.find(f=>f.name==='data_admissao');
    assert.equal(field.value,item?.data_admissao||''); assert.equal(field.type,'date'); assert.ok(!field.required);
    await dialog.onConfirm({nome:'Pessoa',codigo:'1',data_admissao:'2026-06-18',ativo:'true'});
    assert.equal(request.body.data_admissao,'2026-06-18'); assert.equal(request.method,item?'PATCH':'POST');
    await dialog.onConfirm({nome:'Pessoa',codigo:'1',data_admissao:'',ativo:'true'});
    assert.equal(request.body.data_admissao,null);
  }
});
test('calendario lista recorrentes no ano do filtro e formulario envia abrangencia',async()=>{
  const ctx=modules();let dialog,request;
  ctx.OnPontoCalendario.configure({state:()=>({apiMode:'online'}),data:()=>({companies:[{id:1,name:'Empresa'}]}),
    api:async(url,config)=>{if(config){request={url,...config};return {};}
      return [{id:7,nome:'Evento <teste>',data:'2024-09-07',tipo:'FERIADO',abrangencia:'NACIONAL',ativo:true,recorrente:true}];},
    render(){},dialog:d=>dialog=d,invalidate(){},toast(){}});
  ctx.OnPontoCalendario.change('calendar-filter',{dataset:{filter:'ano'},value:'2027',checkValidity:()=>true});
  await ctx.OnPontoCalendario.load();
  const html=ctx.OnPontoCalendario.render({apiMode:'online'},{},ctx.OnPontoComponents);
  assert.match(html,/07\/09\/2027/);assert.match(html,/Evento &lt;teste&gt;/);
  ctx.OnPontoCalendario.action('calendar-new',{matches:()=>false,dataset:{}},{preventDefault(){}});
  assert.equal(dialog.fields.find(f=>f.name==='uf').visibleWhen({abrangencia:'NACIONAL'}),false);
  assert.equal(dialog.fields.find(f=>f.name==='municipio').visibleWhen({abrangencia:'MUNICIPAL'}),true);
  await dialog.onConfirm({nome:'Feriado',data:'2027-06-18',tipo:'FERIADO',abrangencia:'EMPRESA',empresa_id:'1',uf:'SP',municipio:'Cidade',ativo:'true',recorrente:'false'});
  assert.equal(request.body.empresa_id,1);assert.equal(request.body.uf,null);assert.equal(request.body.municipio,null);
  assert.equal(request.body.recorrente,false);assert.equal(request.method,'POST');
});
test('efeito calendario e admissao nao sobrescrevem status manual editavel',()=>{
  for(const detail of [{feriado_aplicado:true,status_dia:'feriado',feriados:['Feriado global']},
    {fora_vinculo:true,status_dia:'fora_vinculo',pendencia_motivo:'Marcação anterior à data de admissão'}]) {
    const day={id:1,competenceId:2,status:'normal',current:{status:'normal'}};
    const ctx={days:()=>[day],idsEqual:(a,b)=>a===b,firstValue:(...xs)=>xs.find(x=>x!=null)??null,
      statusFromBackend:x=>x,statusLabel:x=>x,DAY_STATUS_LABELS:{normal:'Normal',feriado:'Feriado'}};
    vm.createContext(ctx);vm.runInContext(extract('applyApurationDetails'),ctx);
    ctx.applyApurationDetails(2,[{id:1,status_original:'normal',jornada_prevista_minutos:0,horas_trabalhadas_minutos:0,
      atraso_minutos:0,extra_minutos:0,conferido:false,pendente_calculo:false,...detail}]);
    assert.equal(day.status,'normal');assert.equal(day.current.status,'normal');
    assert.equal(day.effectiveStatus,detail.status_dia);assert.ok(day.calendarNote);
    if(detail.fora_vinculo) assert.equal(day.pendingReason,'Marcação anterior à data de admissão');
  }
});
