const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function preparar({search = '', hash = '#/empresas', semLocation = false} = {}) {
  const nodes = {}, eventos = {}, timers = new Map(), requests = [], historicoHtml = [];
  let numeroTimer = 0, responder = () => Promise.reject(new Error('API desligada'));
  function node(id) {
    if (!nodes[id]) nodes[id] = {
      dataset: {}, classList: {toggle() {}, add() {}, remove() {}}, hidden: false,
      querySelectorAll: () => [], querySelector: () => null, addEventListener() {},
      setAttribute() {}, focus() {}, value: '', selectedOptions: [],
      set innerHTML(html) { this.html = html; historicoHtml.push(html); },
      get innerHTML() { return this.html || ''; },
    };
    return nodes[id];
  }
  const c = {URLSearchParams, localStorage: {getItem: () => null},
    document: {getElementById: node, querySelector: node, addEventListener: (nome, fn) => {eventos[nome] = fn;}},
    addEventListener(nome, fn) { eventos[nome] = fn; },
    setTimeout(fn, delay) { const id = ++numeroTimer; timers.set(id, {fn, delay}); return id; },
    clearTimeout(id) { timers.delete(id); }, requestAnimationFrame(fn) { fn(); },
    fetch(url) { requests.push(url); return responder(url); },
  };
  if (!semLocation) {
    c.location = {search, hash};
    c.history = {replaceState(_a, _b, rota) { c.location.hash = rota; }};
  }
  c.window = c;
  vm.createContext(c);
  for (const file of ['mocks', 'utils', 'components', 'screens', 'calendario', 'ocorrencias', 'banco-horas']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../js/' + file + '.js'), 'utf8'), c);
  }
  let source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
  if (semLocation) source = source.replace('\n  init();', '\n  root.teste = {bootstrapApiData, getData: () => data, getState: () => state};');
  vm.runInContext(source, c);
  const app = c.OnPontoApp || c.teste;
  const sucesso = url => Promise.resolve({ok: true, text: async () => JSON.stringify(
    url.endsWith('/empresas') ? [{id: 1, nome: 'Empresa real da API', ativa: true}] : []
  )});
  return {c, app, nodes, requests, timers, historicoHtml,
    ligar() { responder = sucesso; }, responder(fn) { responder = fn; },
    clicar() { return eventos.click({target: {closest: () => ({dataset: {action: 'tentar-conexao-api'}})}, preventDefault() {}}); },
    automatico() {
      const [id, timer] = [...timers.entries()].find(([, t]) => t.delay === 5000);
      timers.delete(id);
      return timer.fn();
    },
  };
}

const concluir = () => new Promise(resolve => setImmediate(resolve));

test('falha sem demo esvazia os dados e nunca desenha telas simuladas', async () => {
  const t = preparar();
  await concluir();
  assert.equal(t.app.getState().apiMode, 'indisponivel');
  assert.equal(JSON.stringify(t.app.getData()), '{}');
  assert.equal(JSON.stringify(t.app.getState().ocr), '{}');
  assert.match(t.nodes.mainContent.innerHTML, /O On Ponto não está conectado/);
  assert.match(t.nodes.mainContent.innerHTML, /iniciar_onponto.bat/);
  assert.match(t.nodes.mainContent.innerHTML, /Tentar de novo/);
  assert.doesNotMatch(t.historicoHtml.join(''), /Queen|demonstração|Juliana|dados simulados/);
  assert.equal(t.nodes.topbarContext.hidden, true);
  assert.equal(t.nodes.appSidebar.innerHTML, '');
  assert.equal(t.timers.size, 1);
  assert.equal(t.c.location.hash, '#/empresas');
});

test('demo explicita conserva mocks e modo offline', async () => {
  const t = preparar({search: '?demo=1'});
  await concluir();
  assert.equal(t.app.getState().apiMode, 'offline');
  assert.ok(t.app.getData().companies.length > 0);
  assert.match(t.nodes.mainContent.innerHTML, /Modo demonstração/);
  assert.equal(t.requests.length, 0);
  assert.equal(t.timers.size, 0);
});

test('Tentar de novo chama bootstrap e recupera a rota atual sem recarregar', async () => {
  const t = preparar({hash: '#/empresas/1/escalas'});
  await concluir();
  assert.equal(t.c.location.hash, '#/empresas/1/escalas');
  t.ligar();
  await t.clicar();
  assert.equal(t.app.getState().apiMode, 'online');
  assert.equal(t.requests.filter(url => url.endsWith('/empresas')).length, 2);
  assert.equal(t.app.getState().route, 'company-scales');
  assert.equal(t.app.getData().companies[0].name, 'Empresa real da API');
  assert.equal(t.c.location.hash, '#/empresas/1/escalas');
  assert.equal(t.nodes.topbarContext.hidden, false);
  assert.equal(t.timers.size, 0);
});

test('tentativa automatica em 5 segundos recupera API e cancela repeticao', async () => {
  const t = preparar();
  await concluir();
  assert.equal([...t.timers.values()][0].delay, 5000);
  t.ligar();
  await t.automatico();
  assert.equal(t.app.getState().apiMode, 'online');
  assert.equal(t.requests.length, 6);
  assert.match(t.nodes.mainContent.innerHTML, /Empresa real da API/);
  assert.equal(t.timers.size, 0);
});

test('falhas repetidas mantem uma tentativa e demo=0 nao ativa mocks', async () => {
  const t = preparar({search: '?demo=0'});
  await concluir();
  await t.automatico();
  assert.equal(t.app.getState().apiMode, 'indisponivel');
  assert.equal(t.timers.size, 1);
  assert.equal(t.requests.length, 6);
});

test('cliques durante a reconexao compartilham a tentativa em andamento', async () => {
  const t = preparar();
  await concluir();
  let liberar;
  const espera = new Promise(resolve => { liberar = resolve; });
  t.responder(() => espera.then(() => ({ok: true, text: async () => '[]'})));
  const primeira = t.clicar(), segunda = t.clicar();
  assert.equal(primeira, segunda);
  assert.equal(t.requests.length, 6);
  assert.equal(t.app.getState().apiMode, 'indisponivel');
  assert.doesNotMatch(t.nodes.mainContent.innerHTML, /Modo demonstração/);
  liberar();
  await primeira;
  assert.equal(t.app.getState().apiMode, 'online');
});

test('vm sem window.location mantem inicializacao dos mocks e trata falha como indisponivel', async () => {
  const t = preparar({semLocation: true});
  assert.ok(t.app.getData().companies.length > 0);
  await t.app.bootstrapApiData();
  assert.equal(t.app.getState().apiMode, 'indisponivel');
  assert.equal(JSON.stringify(t.app.getData()), '{}');
});
