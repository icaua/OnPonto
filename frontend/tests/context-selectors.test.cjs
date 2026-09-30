const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const nodes = {};
  for (const id of ['contextCompany', 'contextCompetence', 'topbarContext', 'contextSwitchStatus']) {
    nodes[id] = {dataset: {}, selectedOptions: [], value: '', disabled: false, updates: 0,
      setAttribute(name, value) { this[name] = value; },
      set innerHTML(value) { this.html = value; this.updates++; }, get innerHTML() { return this.html; }};
  }
  const ctx = {URLSearchParams, localStorage: {getItem: () => null},
    document: {getElementById: id => nodes[id]}, location: {hash: '#/empresas/1/competencias/11/conferencia'}};
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const file of ['mocks', 'utils', 'components', 'screens'])
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/' + file + '.js'), 'utf8'), ctx);
  const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
  vm.runInContext(source.replace('\n  init();', `
    root.quickTest = {state, data, quickContextTarget, renderContextSelectors, switchQuickContext, handleKeydown,
      setQueues(pending, saving, editing) { pendingDaySaves = pending; autosaveFlushPromise = saving; editSession = editing; },
      effects(e) { navigate = e.navigate; showToast = e.toast; flushPendingDaySaves = e.flush; finishEditing = e.finish; if (e.moveEmployee) moveEmployee = e.moveEmployee; }
    };`), ctx);
  const app = ctx.quickTest, calls = [], toasts = [];
  app.data.companies = [{id: 1, name: 'Queen'}, {id: 2, name: 'Outra <empresa>'}, {id: 3, name: 'Sem competências'}];
  app.data.competencies = [
    {id: 11, companyId: 1, year: 2026, month: 9, status: 'em_conferencia'},
    {id: 12, companyId: 1, year: 2026, month: 8, status: 'fechada'},
    {id: 21, companyId: 2, year: 2026, month: 9, status: 'fechada'},
    {id: 22, companyId: 2, year: 2026, month: 10, status: 'aberta'},
    {id: 23, companyId: 2, year: 2027, month: 1, status: 'fechada'},
  ];
  Object.assign(app.state, {route: 'review', selectedCompanyId: 1, selectedCompetenceId: 11, apiMode: 'online'});
  const effects = {navigate: r => calls.push(r), toast: (...args) => toasts.push(args),
    flush: async () => { app.setQueues({}, null, null); return [{ok: true}]; }, finish: () => true};
  app.effects(effects);
  return {ctx, app, nodes, calls, toasts, effects};
}

test('trocar competência preserva área, inclusive consulta de fechada, sem aceitar outro empregador', () => {
  const {app} = setup();
  for (const area of ['review', 'imports', 'competency-summary', 'competency-files', 'competency-history', 'competency-exports']) {
    app.state.route = area;
    assert.equal(app.quickContextTarget('competence', '12').view, area);
    assert.equal(app.quickContextTarget('competence', '12').companyId, 1);
  }
  assert.equal(app.quickContextTarget('competence', '21'), null);
  assert.equal(app.quickContextTarget('competence', '11'), null);
  assert.equal(app.quickContextTarget('company', '999'), null);
  assert.equal(app.quickContextTarget('company', ''), null);
});

test('trocar empresa prioriza mesmo mês, depois aberta mais recente, depois fechada mais recente', () => {
  const {app} = setup();
  assert.equal(app.quickContextTarget('company', 2).competenceId, 21);
  app.data.competencies = app.data.competencies.filter(c => c.id !== 21);
  assert.equal(app.quickContextTarget('company', 2).competenceId, 22);
  app.data.competencies = app.data.competencies.filter(c => c.id !== 22);
  assert.equal(app.quickContextTarget('company', 2).competenceId, 23);
  assert.equal(app.quickContextTarget('company', 2).view, 'review');
  const empty = app.quickContextTarget('company', 3);
  assert.equal(empty.view, 'company-competencies'); assert.equal(empty.competenceId, null);
});

test('trocar empresa mantém cadastro e relatórios; selecionar competência nesses contextos abre resumo', () => {
  const {app} = setup();
  for (const area of ['company-employees', 'company-scales', 'company-ocorrencias', 'company-banco-horas', 'company-reports', 'company-settings', 'company-competencies']) {
    app.state.route = area; app.state.selectedCompetenceId = null;
    assert.equal(app.quickContextTarget('company', 2).view, area);
    assert.equal(app.quickContextTarget('company', 2).competenceId, null);
    assert.equal(app.quickContextTarget('competence', 12).view, 'competency-summary');
  }
  app.state.route = 'calendar';
  assert.equal(app.quickContextTarget('company', 2).view, 'company-overview');
});

test('prévia e leitura não são transportadas para outra competência', () => {
  const {app} = setup();
  for (const view of ['import-preview', 'ocr']) {
    app.state.route = view;
    assert.equal(app.quickContextTarget('company', 2).view, 'imports');
    assert.equal(app.quickContextTarget('competence', 12).view, 'imports');
  }
});

test('seletores escapam nomes, ordenam competências e mantêm opções entre renders sem mudança', () => {
  const {app, nodes} = setup();
  app.renderContextSelectors();
  assert.match(nodes.contextCompany.innerHTML, /Outra &lt;empresa&gt;/);
  assert.equal(nodes.contextCompany.value, '1'); assert.equal(nodes.contextCompetence.value, '11');
  assert.ok(nodes.contextCompetence.innerHTML.indexOf('09/2026') < nodes.contextCompetence.innerHTML.indexOf('08/2026'));
  assert.match(nodes.contextCompetence.innerHTML, /Fechada/);
  app.renderContextSelectors();
  assert.equal(nodes.contextCompany.updates, 1); assert.equal(nodes.contextCompetence.updates, 1);
  app.state.selectedCompanyId = 3; app.state.selectedCompetenceId = null;
  app.renderContextSelectors(); assert.ok(nodes.contextCompetence.disabled); assert.match(nodes.contextCompetence.innerHTML, /Sem competências/);
  app.state.apiMode = 'loading'; app.renderContextSelectors(); assert.ok(nodes.contextCompany.disabled);
  app.state.apiMode = 'online'; app.data.companies = []; app.renderContextSelectors(); assert.ok(nodes.contextCompany.disabled);
});

test('troca com autosave desativado preserva contexto e exige salvar antes', async () => {
  const {app, calls, nodes, toasts} = setup();
  app.state.settings.autosave = false; app.setQueues({4: {}}, null, null);
  nodes.contextCompany.value = '2';
  assert.equal(await app.switchQuickContext('company', 2), false);
  assert.equal(calls.length, 0); assert.equal(nodes.contextCompany.value, '1');
  assert.match(toasts[0][0], /Salve as alterações/);
});

test('troca aguarda o salvamento e impede outra troca enquanto aguarda', async () => {
  const {app, calls, nodes, effects} = setup();
  let complete;
  effects.flush = () => new Promise(resolve => { complete = () => {app.setQueues({}, null, null); resolve([{ok: true}]);}; });
  app.effects(effects); app.setQueues({4: {}}, null, null);
  const pending = app.switchQuickContext('competence', 12);
  assert.equal(calls.length, 0); assert.ok(nodes.contextCompany.disabled);
  assert.match(nodes.contextSwitchStatus.textContent, /Salvando alterações/);
  assert.equal(await app.switchQuickContext('company', 2), false);
  complete(); assert.equal(await pending, true);
  assert.equal(calls.length, 1); assert.equal(calls[0].competenceId, 12);
  assert.equal(nodes.contextCompany.disabled, false);
});

test('falha ou edição nova durante o salvamento impede sair do contexto', async () => {
  for (const problem of ['failure', 'new-edit', 'rejection']) {
    const {app, effects, calls, nodes, toasts} = setup();
    effects.flush = async () => {
      if (problem === 'rejection') throw new Error('Conexão interrompida');
      app.setQueues({}, null, problem === 'new-edit' ? {} : null);
      return [{ok: problem !== 'failure'}];
    };
    app.effects(effects); app.setQueues({4: {}}, null, null);
    assert.equal(await app.switchQuickContext('company', 2), false);
    assert.equal(calls.length, 0); assert.equal(nodes.contextCompany.value, '1');
    assert.equal(nodes.contextCompany.disabled, false); assert.equal(toasts.length, 1);
  }
});

test('outra navegação durante o salvamento não é sobrescrita pela resposta atrasada', async () => {
  const {app, effects, calls, ctx} = setup();
  effects.flush = async () => {app.setQueues({}, null, null); ctx.location.hash = '#/empresas'; return [{ok: true}];};
  app.effects(effects); app.setQueues({4: {}}, null, null);
  assert.equal(await app.switchQuickContext('company', 2), false);
  assert.equal(calls.length, 0);
});

test('edição inválida e operações de confirmação impedem a troca; modo demo mantém navegação', async () => {
  const {app, effects, calls} = setup();
  effects.finish = () => false; app.effects(effects); app.setQueues({}, null, {});
  assert.equal(await app.switchQuickContext('company', 2), false); assert.equal(calls.length, 0);
  app.setQueues({}, null, null);
  for (const key of ['importConfirming', 'competenceLifecycleLoading']) {
    app.state[key] = true;
    assert.equal(await app.switchQuickContext('company', 2), false); app.state[key] = false;
  }
  app.state.apiMode = 'offline';
  assert.equal(await app.switchQuickContext('company', 2), true); assert.equal(calls[0].competenceId, 21);
});

test('Alt + seta opera seletores e continua trocando funcionário fora deles', () => {
  const {app, effects} = setup();
  let moved = 0, prevented = 0;
  effects.moveEmployee = delta => moved += delta; app.effects(effects);
  const event = {key: 'ArrowDown', altKey: true, preventDefault() { prevented++; },
    target: {id: 'contextCompany', closest: () => null, matches: () => true}};
  app.handleKeydown(event);
  event.target.id = 'contextCompetence'; app.handleKeydown(event);
  assert.equal(moved, 0); assert.equal(prevented, 0);
  event.target.id = 'mainContent'; app.handleKeydown(event);
  assert.equal(moved, 1); assert.equal(prevented, 1);
});
