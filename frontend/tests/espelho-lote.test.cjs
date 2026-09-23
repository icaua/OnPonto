const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
const screens = fs.readFileSync(path.join(__dirname, '../js/screens.js'), 'utf8');

function extract(source, name) {
  const start = source.indexOf('  function ' + name + '(');
  assert.ok(start >= 0, name);
  const end = source.indexOf('\n  function ', start + 1);
  return source.slice(start, end < 0 ? undefined : end);
}

test('lote abre nova aba sem funcionario_id e respeita todas as guardas de emissao', () => {
  for (const overrides of [{}, {pendingDaySaves:{1:{}}}, {autosaveFlushPromise:Promise.resolve()},
    {state:{apiMode:'demo'}}, {currentCompetency:()=>null}]) {
    const clicked = [], messages = [];
    const context = {currentCompetency:()=>({id:7}), state:{apiMode:'online'},
      configuredApiBase:()=> 'http://localhost:8000', pendingDaySaves:{}, autosaveFlushPromise:null,
      showToast:(...args)=>messages.push(args), document:{body:{appendChild(){}}, createElement:()=>({
        click(){clicked.push({href:this.href,target:this.target,rel:this.rel});},remove(){}
      })}, ...overrides};
    vm.createContext(context);
    vm.runInContext(extract(app,'openCompetencePrintReport'), context);
    context.openCompetencePrintReport(null, true);
    if (Object.keys(overrides).length) {
      assert.equal(clicked.length,0);
      assert.equal(messages.length,1);
    } else {
      assert.deepEqual(clicked,[{href:'http://localhost:8000/relatorios/espelho-ponto-lote?competencia_id=7',
        target:'_blank',rel:'noopener noreferrer'}]);
    }
  }
});

test('Exportacoes apresenta quarto cartao com acao ligada ao lote', () => {
  const cards = [];
  const context = {valueOf:(obj, keys, fallback)=>obj[keys[0]] ?? fallback,
    reportCard:(...args)=>{cards.push(args);return args[0];}, statusChip:()=>'', summaryItem:()=>'',
    companyName:()=>'', formatCompetence:()=>''};
  vm.createContext(context);
  vm.runInContext(extract(screens, 'competencyExportContent'), context);
  const html = context.competencyExportContent({state:{apiMode:'demo'}}, {competence:{},company:{}});
  assert.equal(cards.length,4);
  assert.deepEqual(cards[3],['Espelhos de ponto (todos os funcionários)',
    'Um espelho por funcionário, pronto para impressão e assinatura.', 'Abrir espelhos', 'open-espelhos-lote']);
  assert.ok(html.includes('Espelhos de ponto'));
  const handler = app.match(/if \(action === "open-espelhos-lote"\) return [^;]+;/)[0];
  let args;
  vm.runInNewContext('(function(){' + handler + '})()', {action:'open-espelhos-lote',
    openCompetencePrintReport:(...values)=>{args=values;}});
  assert.deepEqual(args,[null,true]);
});

test('cadastro e edicao mantem campo opcional vazio para null e preservam zero literal', async () => {
  for (const scenario of [{entity:null,input:'',expected:null},
    {entity:{id:2,tolerancia_intervalo_minutos:null},input:'0',expected:0},
    {entity:{id:2,tolerancia_intervalo_minutos:0},input:'',expected:null},
    {entity:{id:2,tolerancia_intervalo_minutos:7},input:'7',expected:7}]) {
    let dialog, saved;
    const context = {currentCompany:()=>({id:1}),state:{apiMode:'online'},loadedCompanyScales:{1:true},
      companyScales:()=>[scenario.entity], idsEqual:(a,b)=>a===b, normalizedTime:x=>x||'',
      showDialog:config=>{dialog=config;},apiRequest:async(endpoint,options)=>{saved={endpoint,...options};return options.body;},
      upsertEntity(){},scales:()=>[],normalizeScale:x=>x,compareEntityNames(){},
      invalidateCompanyCompetenceData(){},render(){},showToast(){}};
    vm.createContext(context);
    vm.runInContext(extract(app,'nullableDialogNumber') + extract(app,'openScaleDialog'),context);
    context.openScaleDialog(scenario.entity?.id);
    const field = dialog.fields.find(f=>f.name==='tolerancia_intervalo_minutos');
    assert.equal(field.value, scenario.entity?.tolerancia_intervalo_minutos ?? '');
    assert.ok(!field.required);
    assert.match(field.help,/Deixe em branco/);
    const values = Object.fromEntries(dialog.fields.map(f=>[f.name,f.value]));
    values.tolerancia_intervalo_minutos=scenario.input;
    await dialog.onConfirm(values);
    assert.equal(saved.body.tolerancia_intervalo_minutos,scenario.expected);
    assert.equal(saved.method,scenario.entity?'PUT':'POST');
    assert.equal(JSON.parse(JSON.stringify(saved.body)).tolerancia_intervalo_minutos,scenario.expected);
  }
});
