const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function setup(payload) {
  const c = {URLSearchParams, localStorage:{getItem:()=>null}}; c.window=c;
  require('./module-loader.cjs').context(c);
  for (const f of ['mocks','utils','components','screens']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+f+'.js'),'utf8'),c);
  const summary=c.OnPontoStore.create().normalizeCompetenceSummary(payload);
  const data={companies:[{id:1,name:'Empresa fictícia'}],employees:[{id:7,companyId:1,name:'Legado <fictício>'}],
    competencies:[{id:2,companyId:1,month:6,year:2026,status:'conferida'}],competenceSummaries:{2:summary}};
  const state={apiMode:'online',selectedCompanyId:1,selectedCompetenceId:2,selectedEmployeeId:7};
  return {c,data,state,summary};
}
const aviso='Vínculo histórico incompleto: revise as datas de admissão e demissão no cadastro. Dias ausentes não foram presumidos.';
const payload={resumo:[{funcionario_id:7,funcionario:'Legado <fictício>',observacoes:aviso,dias_processados:0,situacao:'indisponivel'}],
  avisos_vinculo:[{funcionario_id:7,codigo:'vinculo_historico_incompleto',mensagem:aviso}],
  fechamento:{pode_fechar:true,proxima_acao:'revisar_fechar'},resumo_geral:{}};

test('aviso da API chega ao operador no resumo e na conferência, mesmo sem marcações',()=>{
  const {c,data,state,summary}=setup(payload);
  assert.equal(summary.linkWarnings.length,1);
  assert.equal(summary.rows[0].observations,aviso);
  for(const route of ['competency-summary','review']) {
    const html=c.OnPontoScreens.render(route,state,data,c.OnPontoComponents);
    assert.match(html,/Vínculos históricos incompletos/);
    assert.match(html,/Dias ausentes não foram presumidos/);
    assert.match(html,/Legado &lt;fictício&gt;/);
    assert.doesNotMatch(html,/<fictício>/);
    assert.match(html,/data-route="company-employees"/);
  }
  const html=c.OnPontoScreens.render('competency-summary',state,data,c.OnPontoComponents);
  assert.doesNotMatch(html,/data-action="request-close-competence"[^>]*disabled/);
});

test('contratos antigos e vínculos completos não recebem aviso inventado',()=>{
  const {c,data,state,summary}=setup({...payload,avisos_vinculo:undefined,resumo:[{funcionario_id:7,funcionario:'Completo',observacoes:''}]});
  assert.equal(summary.linkWarnings.length,0);
  assert.doesNotMatch(c.OnPontoScreens.render('competency-summary',state,data,c.OnPontoComponents),/Vínculos históricos incompletos/);
});

test('snapshot fechado mantém os avisos recebidos e os textos são escapados',()=>{
  const {c,data,state}=setup({...payload,avisos_vinculo:[{...payload.avisos_vinculo[0],mensagem:aviso+' <script>invalido</script>'}]});
  data.competencies[0].status='fechada';
  const html=c.OnPontoScreens.render('competency-summary',state,data,c.OnPontoComponents);
  assert.match(html,/Vínculos históricos incompletos/);
  assert.match(html,/&lt;script&gt;invalido&lt;\/script&gt;/);
  assert.doesNotMatch(html,/<script>/);
});

test('confirmação de fechamento alerta sobre vínculos incompletos sem alterar a decisão da API',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
  const start=source.indexOf('  function showCloseCompetencyDialog(');
  const end=source.indexOf('\n  function ',start+1);
  let dialog;
  const c=vm.createContext({showDialog:d=>{dialog=d;},persistCompetenceLifecycle:()=>true});
  vm.runInContext(source.slice(start,end),c);
  c.showCloseCompetencyDialog(2,{linkWarnings:payload.avisos_vinculo});
  assert.match(dialog.description,/vínculo.*incompleto/i);
  assert.match(dialog.description,/Dias ausentes não foram presumidos/);
  assert.equal(dialog.confirmLabel,'Fechar competência');
  c.showCloseCompetencyDialog(2,{});
  assert.doesNotMatch(dialog.description,/incompleto/);
});
