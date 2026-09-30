const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const ctx = {URLSearchParams, localStorage: {getItem: () => null}};
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const file of ['mocks', 'utils', 'components', 'screens']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/' + file + '.js'), 'utf8'), ctx);
  }
  // Exerce o roteador e os dados reais do frontend sem iniciar DOM/requisições.
  const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
  assert.match(source, /\n  init\(\);/);
  vm.runInContext(source.replace('\n  init();', '\n  root.navigationTest = {state, data, sidebarNavigation, parseHashRoute, validateRoute, routeHash, COMPETENCY_VIEWS};'), ctx);
  const app = ctx.navigationTest;
  function sidebar(collapsed = false) {
    const nav = app.sidebarNavigation();
    return ctx.OnPontoComponents.Sidebar({active: nav.active, primaryItems: nav.primary,
      secondaryItems: nav.secondary, companyName: nav.companyName, collapsed});
  }
  function select(view) {
    Object.assign(app.state, {route: view, selectedCompanyId: 1, selectedCompetenceId: 1001, apiMode: 'offline'});
  }
  return {ctx, app, sidebar, select};
}

test('sidebar global apresenta Trabalho sem empresa ou competência inventada', () => {
  const {sidebar} = setup();
  const html = sidebar();
  assert.match(html, /aria-label="Trabalho"/);
  assert.match(html, /data-route="companies"/);
  assert.match(html, /data-route="calendar"/);
  assert.doesNotMatch(html, /Empresa atual|Cadastros|company-overview|competency-summary/);
});

test('todas as áreas da competência mantêm a sidebar da empresa sem duplicar etapas', () => {
  const {app, sidebar, select} = setup();
  for (const route of app.COMPETENCY_VIEWS) {
    select(route);
    const html = sidebar();
    assert.match(html, /Empresa atual/);
    assert.match(html, /sidebar-company-name[^>]*>Queen/);
    assert.match(html, /data-route="company-competencies"[^>]*aria-current="location"/);
    assert.equal((html.match(/aria-current=/g) || []).length, 1);
    for (const internal of app.COMPETENCY_VIEWS) assert.ok(!html.includes('data-route="' + internal + '"'), internal);
    assert.doesNotMatch(html, /sidebar-badge/);
  }
});

test('Cadastros agrupa quatro rotas independentes e mantém acesso com menu recolhido', () => {
  const {sidebar, select} = setup();
  const routes = ['company-employees', 'company-scales', 'company-ocorrencias', 'company-banco-horas'];
  for (const route of routes) {
    select(route);
    for (const collapsed of [false, true]) {
      const html = sidebar(collapsed);
      const group = html.match(/<ul class="sidebar-group-items"[^>]*>(.*?)<\/ul>/s)[1];
      assert.equal((group.match(/data-route=/g) || []).length, 4);
      for (const child of routes) assert.ok(group.includes('data-route="' + child + '"'));
      assert.match(group, new RegExp('data-route="' + route + '"[^>]*aria-current="page"'));
      assert.equal((group.match(/aria-label=/g) || []).length, 4);
      assert.match(html, new RegExp('data-action="toggle-sidebar" aria-expanded="' + !collapsed + '"'));
    }
  }
});

test('sidebar distingue lista de competências de uma competência aberta e escapa a empresa', () => {
  const {app, sidebar, select} = setup();
  select('company-competencies');
  app.data.companies.find(c => c.id === 1).name = 'Queen <img src=x onerror=alert(1)>';
  const html = sidebar();
  assert.match(html, /data-route="company-competencies"[^>]*aria-current="page"/);
  assert.match(html, /Queen &lt;img/);
  assert.doesNotMatch(html, /Queen <img/);
});

test('URLs anteriores continuam resolvendo e gerando o mesmo endereço', () => {
  const {app} = setup();
  const company = '#/empresas/1';
  const competence = company + '/competencias/1001';
  const routes = ['#/empresas', '#/calendario', company,
    ...['funcionarios', 'escalas', 'ocorrencias', 'banco-horas', 'competencias', 'relatorios', 'configuracoes'].map(p => company + '/' + p),
    competence, ...['importacoes', 'conferencia', 'arquivos', 'historico', 'exportacoes', 'importacoes/previa', 'importacoes/leitura'].map(p => competence + '/' + p)];
  for (const hash of routes) assert.equal(app.routeHash(app.parseHashRoute(hash)), hash);
});

test('telas da competência separam as quatro etapas dos dois recursos auxiliares', () => {
  const {ctx, app, select} = setup();
  for (const route of app.COMPETENCY_VIEWS) {
    select(route);
    const html = ctx.OnPontoScreens.render(route, app.state, app.data, ctx.OnPontoComponents);
    const steps = html.match(/<nav class="tabs competency-tabs"[^>]*>(.*?)<\/nav>/s)?.[1];
    const resources = html.match(/<nav class="competency-resources"[^>]*>(.*?)<\/nav>/s)?.[1];
    assert.ok(steps, route); assert.ok(resources, route);
    assert.deepEqual([...steps.matchAll(/data-route="([^"]+)"/g)].map(m => m[1]), ['competency-summary', 'imports', 'review', 'competency-exports']);
    for (const label of ['Resumo', 'Importar', 'Conferir', 'Exportar']) assert.ok(steps.includes('>' + label + '</button>'));
    assert.deepEqual([...resources.matchAll(/data-route="([^"]+)"/g)].map(m => m[1]), ['competency-files', 'competency-history']);
    const active = ['import-preview', 'ocr'].includes(route) ? 'imports' : route;
    assert.match(steps + resources, new RegExp('data-route="' + active + '" aria-current="page"'));
    assert.equal(((steps + resources).match(/aria-current=/g) || []).length, 1);
  }
});

test('Conferir mantém navegação de funcionários e leitura de competência fechada em API e demo', () => {
  const {ctx, app, select} = setup();
  select('review');
  for (const mode of ['online', 'offline']) {
    app.state.apiMode = mode;
    app.data.competencies.find(c => c.id === 1001).status = 'fechada';
    const html = ctx.OnPontoScreens.render('review', app.state, app.data, ctx.OnPontoComponents);
    assert.match(html, /data-action="previous-employee"/);
    assert.match(html, /data-action="next-employee"/);
    assert.match(html, /Somente leitura/);
    assert.match(html, /data-action="save-now"[^>]*disabled/);
    assert.match(html, /aria-label="Etapas da competência"/);
  }
});
