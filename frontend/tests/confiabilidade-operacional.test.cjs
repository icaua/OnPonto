const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
function setup(){
  const c={URLSearchParams,localStorage:{getItem:()=>null}};c.window=c;vm.createContext(c);
  for(const file of ['mocks','utils','components','screens'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+file+'.js'),'utf8'),c);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../app.js'),'utf8').replace('\n  init();','\n root.testApi={state,data,normalizeCompetence,normalizeCompetenceSummary,dayHasProblem,visibleReviewDays};'),c);
  return c;
}
test('API ausente não vira zero; zero confirmado é preservado',()=>{
 const c=setup(),a=c.testApi;
 for(const key of ['pendingCount','fileCount','progress','confirmedEmployees','pendingEmployees']){
   assert.equal(a.normalizeCompetence({id:1,empresa_id:1,mes:9,ano:2026})[key],null,key);
   assert.equal(a.normalizeCompetence({id:1,empresa_id:1,mes:9,ano:2026,[key]:0})[key],0,key);
 }
 const x=a.normalizeCompetenceSummary({resumo:[{}, {extras_minutos:0,problemas:0,aguardando_conferencia:1}]});
 assert.equal(x.rows[0].extraMinutes,null);assert.equal(x.rows[1].extraMinutes,0);
 assert.equal(x.rows[1].pending,0);assert.equal(x.rows[1].awaiting,1);
});
test('lista, visão geral, competências e relatórios exibem ausência sem NaN',()=>{
 const c=setup(),a=c.testApi;
 const d={companies:[{id:1,name:'Empresa fictícia'}],employees:[],competencies:[a.normalizeCompetence({id:1,empresa_id:1,mes:9,ano:2026})]};
 const s={apiMode:'online',selectedCompanyId:1,selectedCompetenceId:1};
 for(const name of ['renderCompanies','renderCompanyOverview','renderCompanyCompetencies','renderCompanyReports']){
   const html=c.OnPontoScreens[name](s,d,c.OnPontoComponents);
   assert.doesNotMatch(html,/NaN|undefined|null/);assert.match(html,/—/);
 }
});
test('CTA acompanha decisão central e bloqueia fechamento sem autorização do backend',()=>{
 const c=setup(),a=c.testApi;
 const d={companies:[{id:1,name:'Empresa fictícia'}],employees:[],competencies:[{id:1,companyId:1,month:9,year:2026,status:'aberta'}],competenceSummaries:{}};
 const s={apiMode:'online',selectedCompanyId:1,selectedCompetenceId:1};
 for(const [key,label] of Object.entries({importar:'Importar arquivo',confirmar_importacao:'Confirmar importação',resolver_problemas:'Resolver problemas',revisar_banco:'Revisar saldo do banco',continuar_conferencia:'Continuar conferência',revisar_fechar:'Revisar e fechar',exportar:'Exportar'})){
   d.competenceSummaries['1']=a.normalizeCompetenceSummary({fechamento:{pode_fechar:key==='revisar_fechar',proxima_acao:key},resumo_geral:{},resumo:[]});
   const html=c.OnPontoScreens.renderCompetencySummary(s,d,c.OnPontoComponents);
   assert.ok(html.includes(label),label);
   if(key!=='revisar_fechar')assert.match(html,/data-action="request-close-competence"[^>]*disabled/);
 }
});
test('problema não inclui somente revisão pendente',()=>{
 const a=setup().testApi;
 assert.equal(a.dayHasProblem({conferido:false,pendingOperational:true,problema:false}),false);
 assert.equal(a.dayHasProblem({conferido:true,problema:true}),true);
});
