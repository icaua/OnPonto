const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
function setup(){
  const c={URLSearchParams,localStorage:{getItem:()=>null}};c.window=c;vm.createContext(c);
  for(const f of ['mocks','utils','components','screens','banco-horas']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+f+'.js'),'utf8'),c);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../app.js'),'utf8').replace('\n  init();','\n root.testApi={hourPolicyFields,hourPolicyPayload,normalizeCompetenceSummary};'),c);
  return c;
}
test('formulário preserva política salva e não escolhe composição ambígua',()=>{
 const a=setup().testApi;
 const p={modo:'misto',percentual_folha:'50',percentual_banco:'50',adicional_folha_percentual:'50',inicio_ciclo:'2026-09-01',ciclo_dias:180,
  domingo:{fator_banco:'1.5',base_fator:'decidir'},fim_ciclo_credor:'pagar',permite_saldo_negativo:true};
 const fields=a.hourPolicyFields({politica_horas:p});
 const values=Object.fromEntries(fields.map(f=>[f.name,f.value]));
 const out=a.hourPolicyPayload(values);
 assert.equal(out.percentual_banco,50);assert.equal(out.percentual_folha,50);
 assert.equal(out.domingo.base_fator,'decidir');assert.equal(out.domingo.fator_banco,1.5);
 assert.equal(out.ciclo_dias,180);assert.equal(out.fim_ciclo_credor,'pagar');
 assert.equal(fields.find(f=>f.name==='politica_ciclo_dias').visibleWhen({politica_modo:'folha'}),false);
 assert.equal(a.hourPolicyPayload({politica_modo:'legado'}),null);
 for(const [modo,folha] of [['folha',100],['banco',0]]){
   const x=a.hourPolicyPayload({...values,politica_modo:modo});assert.equal(x.percentual_folha,folha);assert.equal(x.percentual_banco,100-folha);
 }
});
test('resumo exibe HE bruta, folha, fator e débitos sem converter ausência em zero',()=>{
 const c=setup(),a=c.testApi;
 const summary=a.normalizeCompetenceSummary({resumo:[{funcionario_id:1,funcionario:'Pessoa fictícia',extra_apurada_minutos:120,extra_folha_minutos:60,
  extra_banco_base_minutos:60,extra_banco_minutos:90,debito_banco_minutos:null,adicionais_folha:[{percentual:'50',minutos:60}],politicas_horas_aplicadas:[{politica:{modo:'misto'}}]}]});
 const data={companies:[{id:1,name:'Empresa fictícia'}],competencies:[{id:1,companyId:1,month:9,year:2026}],competenceSummaries:{1:summary}};
 const html=c.OnPontoScreens.renderCompetencySummary({apiMode:'online',selectedCompanyId:1,selectedCompetenceId:1},data,c.OnPontoComponents);
 assert.match(html,/Distribuição das horas extras/);assert.match(html,/02:00/);assert.match(html,/01:30/);assert.match(html,/50%/);
 assert.doesNotMatch(html,/NaN|undefined|null/);assert.equal(summary.rows[0].distribution.debit,null);
 assert.equal(c.OnPontoBancoHoras.duration(null),'—');assert.equal(c.OnPontoBancoHoras.duration(0),'00:00');
});
