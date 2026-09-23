const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function setup() {
  const ctx = {URLSearchParams}; ctx.window = ctx; vm.createContext(ctx);
  for (const name of ['utils','components','screens','banco-horas','ocorrencias'])
    vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+name+'.js'),'utf8'),ctx);
  const state={selectedCompanyId:1,apiMode:'online'};
  const data={companies:[{id:1,name:'Empresa'}],employees:[{id:7,companyId:1,name:'Pessoa <teste>'}]};
  const requests=[],dialogs=[];
  const summary=[{funcionario_id:7,funcionario:'Pessoa <teste>',saldo_minutos:90,data_demissao:'2026-09-10',saldo_demissao_minutos:120}];
  const statement={funcionario_id:7,saldo_minutos:90,lancamentos:[{id:1,natureza:'credito',origem:'ajuste_manual',minutos:120,minutos_compensados:30,minutos_restantes:90,saldo_acumulado_minutos:120,status:'ativo',observacao:'<script>teste</script>',data_referencia:'2026-09-01',data_lancamento:'2026-09-22',data_vencimento:'2026-11-30'}],compensacoes:[{id:1,credito_id:1,debito_id:2,minutos:30,status:'ativo'}]};
  ctx.OnPontoBancoHoras.configure({state:()=>state,data:()=>data,render(){},invalidate(){},dialog:d=>dialogs.push(d),
    api:async(url,config)=>{requests.push({url,config});return url.includes('/resumo')?summary:url.includes('/alertas')?{vencidos:[],proximos_do_vencimento:[]}:url.includes('/extrato')?statement:{id:4};}});
  return {ctx,state,data,requests,dialogs};
}
test('extrato exibe saldo, compensações e escapa texto recebido',async()=>{
  const {ctx,state,data}=setup(); await ctx.OnPontoBancoHoras.load();
  const html=ctx.OnPontoBancoHoras.render(state,data,ctx.OnPontoComponents);
  assert.match(html,/Pessoa &lt;teste&gt;/);assert.match(html,/&lt;script&gt;/);
  assert.doesNotMatch(html,/<script>teste/);assert.match(html,/\+01:30/);
  assert.match(html,/Como os créditos compensaram os débitos/);assert.match(html,/Desligamento em/);
});
test('corte do extrato é enviado ao backend',async()=>{
  const {ctx,requests}=setup();await ctx.OnPontoBancoHoras.load();
  ctx.OnPontoBancoHoras.change('bank-cutoff',{value:'2026-09-10'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(requests.some(r=>r.url.includes('data_limite=2026-09-10')));
});
test('ajuste manual envia natureza, minutos e motivo explícitos',async()=>{
  const {ctx,dialogs,requests}=setup();await ctx.OnPontoBancoHoras.load();
  ctx.OnPontoBancoHoras.action('bank-adjust',{});
  const d=dialogs[0];assert.ok(d.fields.find(f=>f.name==='observacao').required);
  await d.onConfirm({funcionario_id:'7',natureza:'debito',minutos:'30',data_referencia:'2026-09-01',observacao:'Correção documentada'});
  const req=requests.find(r=>r.url==='/banco-horas/ajustes');
  assert.equal(req.config.method,'POST');assert.equal(req.config.body.minutos,30);
  assert.equal(req.config.body.natureza,'debito');assert.equal(req.config.body.observacao,'Correção documentada');
});
test('modo offline limpa saldos e não envia ajustes',async()=>{
  const {ctx,state,data,requests}=setup();await ctx.OnPontoBancoHoras.load();
  state.apiMode='offline';await ctx.OnPontoBancoHoras.load();const before=requests.length;
  ctx.OnPontoBancoHoras.action('bank-adjust',{});
  assert.equal(requests.length,before);
  const html=ctx.OnPontoBancoHoras.render(state,data,ctx.OnPontoComponents);
  assert.match(html,/Conecte a API/);assert.doesNotMatch(html,/\+01:30/);
});
test('resumo mantém banco em bloco próprio somente para participantes',()=>{
  const {ctx,state,data}=setup();state.selectedCompetenceId=2;
  data.competencies=[{id:2,companyId:1,month:9,year:2026,status:'fechada'}];
  data.competenceSummaries={2:{general:{},rows:[{employeeName:'Pessoa',bank:{consolidado:true,saldo_anterior_minutos:120,creditos_competencia_minutos:60,debitos_competencia_minutos:30,saldo_final_minutos:150}},{employeeName:'Fora do banco'}]}};
  const html=ctx.OnPontoScreens.renderCompetencySummary(state,data,ctx.OnPontoComponents);
  assert.match(html,/<h2>Banco de horas<\/h2>/);assert.match(html,/\+02:30/);
  assert.equal((html.match(/Saldo anterior/g)||[]).length,1);
  data.competenceSummaries[2].rows[0].bank=null;
  assert.doesNotMatch(ctx.OnPontoScreens.renderCompetencySummary(state,data,ctx.OnPontoComponents),/<h2>Banco de horas<\/h2>/);
});
