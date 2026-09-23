const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8');
// Execute the production functions with browser/API boundaries replaced by test doubles.
function extract(name) {
  const start = source.indexOf('  function ' + name + '(');
  assert.ok(start >= 0, name);
  const end = source.indexOf('\n  function ', start + 1);
  return source.slice(start, end < 0 ? undefined : end);
}
function printing(overrides = {}) {
  const clicked = [], messages = [];
  const context = {
    currentCompetency: () => ({ id: 7 }), state: { apiMode: 'online' },
    configuredApiBase: () => 'http://localhost:8000',
    showToast: (...args) => messages.push(args),
    pendingDaySaves: {}, autosaveFlushPromise: null,
    document: { body: { appendChild() {} }, createElement: () => ({
      click() { clicked.push({ href: this.href, target: this.target, rel: this.rel }); }, remove() {},
    }) }, ...overrides,
  };
  vm.createContext(context);
  vm.runInContext(extract('openCompetencePrintReport'), context);
  return { context, clicked, messages };
}
test('emite pessoa e competencia corretas em nova aba, mantendo relatorio da empresa', () => {
  const { context, clicked } = printing();
  context.openCompetencePrintReport('23');
  context.openCompetencePrintReport();
  assert.equal(clicked[0].href, 'http://localhost:8000/relatorios/espelho-ponto?competencia_id=7&funcionario_id=23');
  assert.equal(clicked[0].target, '_blank');
  assert.equal(clicked[0].rel, 'noopener noreferrer');
  assert.equal(clicked[1].href, 'http://localhost:8000/relatorios/impressao?competencia_id=7');
});
test('nao emite com edicao ainda na fila ou salvamento em andamento', () => {
  for (const overrides of [{ pendingDaySaves: { 1: {} } }, { autosaveFlushPromise: Promise.resolve() }]) {
    const { context, clicked, messages } = printing(overrides);
    context.openCompetencePrintReport('23');
    assert.equal(clicked.length, 0);
    assert.ok(messages.length);
  }
});
test('nao emite no modo demo ou sem competencia', () => {
  for (const overrides of [{ state: { apiMode: 'demo' } }, { currentCompetency: () => null }]) {
    const { context, clicked, messages } = printing(overrides);
    context.openCompetencePrintReport('23');
    assert.equal(clicked.length, 0);
    assert.ok(messages.length);
  }
});
function apuration(detail) {
  const day = { id: 1, competenceId: 7, status: 'normal' };
  const context = { days: () => [day], idsEqual: (a,b) => String(a) === String(b),
    firstValue: (...values) => values.find(v => v !== null && v !== undefined) ?? null,
    statusFromBackend: x => x, statusLabel: x => x, DAY_STATUS_LABELS: { normal: 'Normal' },
  };
  vm.createContext(context); vm.runInContext(extract('applyApurationDetails'), context);
  context.applyApurationDetails(7, [{ id: 1, status_dia: 'normal', jornada_prevista_minutos: 480,
    horas_trabalhadas_minutos: 480, atraso_minutos: 30, extra_minutos: 0, conferido: true,
    pendente_calculo: false, ...detail }]);
  return day;
}
test('saldo da conferencia segue atraso e extra do motor como o Excel', () => {
  assert.equal(apuration({}).balanceMinutes, -30);
  assert.equal(apuration({ atraso_minutos: 0, extra_minutos: 45 }).balanceMinutes, 45);
  assert.equal(apuration({ atraso_minutos: 0, extra_minutos: 0, horas_trabalhadas_minutos: 475 }).balanceMinutes, 0);
});
test('saldo pendente nao aparece como numero valido', () => {
  assert.equal(apuration({ pendente_calculo: true }).balanceMinutes, null);
});
test('edicao de horario agenda atualizacao da apuracao depois de salvar', () => {
  const context = { state: { apiMode: 'online', settings: { autosave: false }, autosaveRevision: 0 },
    pendingDaySaves: {}, competencyIsClosed: () => false, daySavePayload: () => ({ entrada: '08:30' }),
    updateAutosaveIndicator() {},
  };
  vm.createContext(context); vm.runInContext(extract('queueAutosave'), context);
  context.queueAutosave({ id: 1, competenceId: 7 });
  assert.equal(context.pendingDaySaves[1].syncCompetence, true);
});
test('edicao local online nao inventa saldo antes da apuracao', () => {
  const context = { state: { apiMode: 'online' }, currentSlots: () => ({}),
    Utils: { calculateJourney: () => ({ workedMinutes: 480, expectedMinutes: 480, balanceMinutes: 0 }) },
  };
  vm.createContext(context); vm.runInContext(extract('recalculateDay'), context);
  const day = { expectedMinutes: 480, current: {} };
  context.recalculateDay(day);
  assert.equal(day.balanceMinutes, null);
  assert.equal(day.current.balanceMinutes, null);
});
