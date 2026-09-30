(function (root) {
  "use strict";
  var ctx, companyId = null, employeeId = "", cutoff = "", sequence = 0;
  var loading = false, error = "", summary = [], warnings = {}, statement = null;
  var origins = { apuracao: "Apuração", ajuste_manual: "Ajuste manual", folga_compensatoria: "Folga compensatória" };
  function esc(value) { return root.OnPontoUtils.escapeHtml(value == null ? "" : value); }
  function duration(value, signed) {
    if (value === null || value === undefined || value === "") return "—";
    var n = Number(value), a = Math.abs(n);
    return (n < 0 ? "−" : signed && n > 0 ? "+" : "") + String(Math.floor(a / 60)).padStart(2, "0") + ":" + String(a % 60).padStart(2, "0");
  }
  function date(value) { return value ? root.OnPontoUtils.formatDate(value.slice(0, 10)) : "—"; }
  function staff(state, data) { return (data.employees || []).filter(function (e) { return String(e.companyId || e.empresa_id) === String(state.selectedCompanyId); }); }
  function button(action, label, id, disabled) {
    return '<button type="button" class="button button--secondary" data-action="bank-' + action + '" data-bank-id="' + esc(id) + '"' + (disabled ? ' disabled' : '') + '>' + esc(label) + '</button>';
  }
  function load() {
    var state = ctx.state();
    if (String(companyId) !== String(state.selectedCompanyId)) {
      companyId = state.selectedCompanyId; employeeId = ""; cutoff = ""; summary = []; warnings = {}; statement = null;
    }
    var request = ++sequence;
    if (state.apiMode !== "online") {
      error = "Conecte a API para consultar o banco de horas."; loading = false; summary = []; statement = null; warnings = {}; ctx.render();
      return Promise.resolve();
    }
    loading = true; error = ""; ctx.render();
    return Promise.all([ctx.api('/banco-horas/resumo?empresa_id=' + companyId), ctx.api('/banco-horas/alertas?empresa_id=' + companyId)])
      .then(function (values) {
        if (request !== sequence) return;
        summary = values[0]; warnings = values[1];
        if (!employeeId && summary.length) employeeId = String(summary[0].funcionario_id);
        if (!employeeId) { statement = null; return; }
        return ctx.api('/banco-horas/extrato?funcionario_id=' + encodeURIComponent(employeeId) + (cutoff ? '&data_limite=' + encodeURIComponent(cutoff) : ''))
          .then(function (value) { if (request === sequence) statement = value; });
      }).catch(function (err) { if (request === sequence) { error = err.message; statement = null; summary = []; warnings = {}; } })
      .finally(function () { if (request === sequence) { loading = false; ctx.render(); } });
  }
  function render(state, data, components) {
    var employees = staff(state, data), online = state.apiMode === "online";
    var company = (data.companies || []).find(function (c) { return String(c.id) === String(state.selectedCompanyId); });
    var rows = summary.map(function (item) {
      var termination = item.data_demissao ? '<strong>Desligamento em ' + esc(date(item.data_demissao)) + ': ' + duration(item.saldo_demissao_minutos, true) + '</strong>' : '—';
      return '<tr><th scope="row">' + esc(item.funcionario) + '</th><td class="bank-amount">' + duration(item.saldo_minutos, true) + '</td><td>' + termination + '</td><td>' + button('employee', 'Ver extrato', item.funcionario_id, loading) + '</td></tr>';
    }).join('');
    var alertHtml = [['vencidos', 'Créditos vencidos'], ['proximos_do_vencimento', 'Vencem nos próximos 30 dias'], ['folgas_sem_cobertura', 'Folgas que precisam de revisão']].map(function (category) {
      var items = warnings[category[0]] || [];
      if (!items.length) return '';
      return '<section class="work-card bank-alert"><h2>' + category[1] + '</h2><p>' + (category[0] === 'folgas_sem_cobertura' ? 'Um estorno posterior deixou estas folgas sem cobertura. Revise os lançamentos relacionados.' : 'O crédito permanece no saldo até uma decisão registrada pelo operador.') + '</p><ul>' + items.map(function (item) {
        return '<li>' + esc(item.funcionario) + ' · ' + duration(item.minutos_restantes) + ' · ' + esc(date(item.data_vencimento || item.data_referencia)) + ' ' + button('employee', 'Ver extrato', item.funcionario_id, loading) + '</li>';
      }).join('') + '</ul></section>';
    }).join('');
    var options = '<option value="">Selecione o funcionário</option>' + employees.map(function (e) {
      return '<option value="' + esc(e.id) + '"' + (String(e.id) === employeeId ? ' selected' : '') + '>' + esc(e.name || e.nome) + '</option>';
    }).join('');
    var entries = statement ? statement.lancamentos.map(function (item) {
      return '<tr' + (item.status === 'estornado' ? ' class="bank-reversed"' : '') + '><td>' + esc(date(item.data_referencia)) + '<small>Lançado em ' + esc(date(item.data_lancamento)) + ' · #' + item.id + '</small></td>' +
        '<td>' + esc(origins[item.origem] || item.origem) + '<small>' + (item.natureza === 'credito' ? 'Crédito' : 'Débito') + ' · ' + esc(item.status) + '</small></td>' +
        '<td class="bank-amount">' + duration(item.minutos * (item.natureza === 'credito' ? 1 : -1), true) + '</td><td>' + duration(item.minutos_compensados) + '</td><td>' + duration(item.minutos_restantes) + '</td><td class="bank-amount">' + duration(item.saldo_acumulado_minutos, true) + '</td>' +
        '<td>' + (item.competencia_origem_id ? 'Competência #' + item.competencia_origem_id + ' · versão ' + item.versao_fechamento : 'Ajuste manual') + '<small>Escala: ' + esc(item.escala_origem_id || '—') + ' · Vence: ' + esc(date(item.data_vencimento)) + '</small>' + (item.ciclo_inicio ? '<small>Ciclo: ' + esc(date(item.ciclo_inicio)) + ' a ' + esc(date(item.ciclo_fim)) + '</small>' : '') + '</td>' +
        '<td>' + esc(item.observacao || '—') + (item.lancamento_referencia_id ? '<small>Ajuste no ciclo do lançamento #' + esc(item.lancamento_referencia_id) + '</small>' : '') + (item.motivo_estorno ? '<small>Estorno: ' + esc(item.motivo_estorno) + ' · ' + esc(date(item.estornado_em)) + '</small>' : '') +
        (item.origem === 'ajuste_manual' && item.status === 'ativo' ? button('reverse', 'Estornar', item.id, loading || !online) : '') + '</td></tr>';
    }).join('') : '';
    var treatments = statement && statement.tratamentos_pendentes && statement.tratamentos_pendentes.length ? '<section class="bank-alert"><h3>Tratamentos pendentes de confirmação</h3><p>Indicações da política. O saldo permanece no extrato até um ajuste justificado; não há baixa ou transporte automático.</p><ul>' + statement.tratamentos_pendentes.map(function(t){
      return '<li>'+esc(t.evento === 'desligamento' ? 'Desligamento' : 'Fim de ciclo')+' · '+esc(date(t.ciclo_inicio))+' a '+esc(date(t.ciclo_fim))+' · '+duration(t.minutos)+' '+esc(t.natureza)+' · '+esc(t.tratamento)+' · adicional '+(t.adicional_percentual == null ? 'a definir' : esc(t.adicional_percentual)+'%')+'</li>';
    }).join('')+'</ul></section>' : '';
    var matches = statement && statement.compensacoes.length ? '<details class="bank-matches"><summary>Como os créditos compensaram os débitos</summary><div class="table-frame"><table class="data-table"><thead><tr><th>Crédito</th><th>Débito</th><th>Tempo utilizado</th><th>Status</th><th>Motivo do estorno</th></tr></thead><tbody>' + statement.compensacoes.map(function (c) {
      return '<tr><td>#' + c.credito_id + '</td><td>#' + c.debito_id + '</td><td>' + duration(c.minutos) + '</td><td>' + esc(c.status) + '</td><td>' + esc(c.motivo_estorno || '—') + '</td></tr>';
    }).join('') + '</tbody></table></div></details>' : '';
    return '<section class="screen" data-screen="company-banco-horas">' + components.PageHeader({ title: 'Banco de horas', subtitle: company && (company.name || company.nome) || '', actions: [] }) +
      '<section class="work-card"><div class="section-heading"><div><h2>Saldos consolidados</h2><p>As horas da apuração entram no banco ao fechar a competência.</p></div>' + button('adjust', 'Registrar ajuste', '', !online || loading || !employees.length) + '</div>' +
      (rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Funcionário</th><th>Saldo atual</th><th>Saldo no desligamento</th><th>Ações</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<p>Nenhum funcionário com banco de horas nesta empresa. Configure uma política de horas na escala.</p>') + '</section>' + alertHtml +
      '<section class="work-card" aria-busy="' + loading + '"><div class="section-heading"><h2>Extrato por funcionário</h2>' + button('refresh', 'Atualizar', '', !online || loading) + '</div><div class="toolbar">' +
      '<label class="compact-field"><span>Funcionário</span><select data-action="bank-select">' + options + '</select></label><label class="compact-field"><span>Data de referência até</span><input type="date" data-action="bank-cutoff" value="' + esc(cutoff) + '"></label></div>' +
      (error ? '<p class="inline-feedback inline-feedback--error" role="alert">' + esc(error) + '</p>' : '') +
      (loading ? '<p role="status">Carregando banco de horas…</p>' : statement ? '<p class="bank-total">Saldo no período: <strong>' + duration(statement.saldo_minutos, true) + '</strong></p>' +
      (statement.data_demissao ? '<p class="bank-alert"><strong>Saldo do banco na data do desligamento (' + esc(date(statement.data_demissao)) + '): ' + duration(statement.saldo_demissao_minutos, true) + '</strong></p>' : '') +
      (entries ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Referência</th><th>Lançamento</th><th>Tempo</th><th>Compensado</th><th>Restante</th><th>Saldo</th><th>Origem / vencimento</th><th>Observação / ação</th></tr></thead><tbody>' + entries + '</tbody></table></div>' : '<p>Nenhum lançamento no período.</p>') + treatments + matches : '<p>Selecione um funcionário para consultar o extrato.</p>') + '</section></section>';
  }
  function action(action, element) {
    if (!action || action.indexOf('bank-') !== 0) return false;
    if (action === 'bank-refresh') { load(); return true; }
    if (action === 'bank-employee') { employeeId = String(element.getAttribute('data-bank-id')); cutoff = ''; load(); return true; }
    if (ctx.state().apiMode !== 'online') return true;
    if (action === 'bank-adjust') {
      var employees = staff(ctx.state(), ctx.data());
      ctx.dialog({ title: 'Registrar ajuste no banco de horas', description: 'Registre crédito ou débito com o motivo da correção. O histórico será preservado.', confirmLabel: 'Registrar ajuste', fields: [
        { name:'funcionario_id', label:'Funcionário', type:'select', required:true, value:employeeId, options:employees.map(function(e){return {value:e.id,label:e.name || e.nome};}) },
        { name:'natureza', label:'Natureza', type:'select', required:true, options:[{value:'credito',label:'Crédito'},{value:'debito',label:'Débito'}] },
        { name:'minutos', label:'Quantidade de minutos', type:'number', min:1, step:1, required:true },
        { name:'data_referencia', label:'Data de referência', type:'date', required:true },
        { name:'lancamento_referencia_id', label:'Ciclo do ajuste', type:'select', value:'',
          help:'Escolha um lançamento para corrigir seu ciclo original. A data de referência precisa pertencer a esse ciclo.',
          visibleWhen:function(v){return statement && String(v.funcionario_id) === String(statement.funcionario_id);},
          options:[{value:'',label:'Conforme a política atual e a data informada'}].concat(statement ? statement.lancamentos.filter(function(i){return i.status === 'ativo';}).map(function(i){return {value:i.id,label:'#'+i.id+' · '+(i.ciclo_inicio ? date(i.ciclo_inicio)+' a '+date(i.ciclo_fim) : 'Saldo anterior sem ciclo')};}) : []) },
        { name:'observacao', label:'Motivo do ajuste', type:'textarea', required:true, maxlength:5000 }
      ], onConfirm:function(v){return ctx.api('/banco-horas/ajustes',{method:'POST',body:{funcionario_id:Number(v.funcionario_id),natureza:v.natureza,minutos:Number(v.minutos),data_referencia:v.data_referencia,observacao:v.observacao,
        lancamento_referencia_id:statement && String(v.funcionario_id) === String(statement.funcionario_id) && v.lancamento_referencia_id ? Number(v.lancamento_referencia_id) : null}}).then(function(){employeeId=String(v.funcionario_id);ctx.invalidate();return load();});} });
    } else if (action === 'bank-reverse') {
      var id = element.getAttribute('data-bank-id');
      ctx.dialog({title:'Estornar ajuste #' + id,description:'O lançamento e suas compensações permanecerão no histórico. O saldo será recalculado.',confirmLabel:'Estornar ajuste',fields:[{name:'motivo',label:'Motivo do estorno',type:'textarea',required:true,maxlength:5000}],onConfirm:function(v){return ctx.api('/banco-horas/lancamentos/'+encodeURIComponent(id)+'/estornar',{method:'POST',body:{motivo:v.motivo}}).then(function(){ctx.invalidate();return load();});}});
    }
    return true;
  }
  function change(action, element) {
    if (action === 'bank-select') { employeeId = element.value; statement = null; load(); return true; }
    if (action === 'bank-cutoff') { cutoff = element.value; load(); return true; }
    return false;
  }
  root.OnPontoBancoHoras = {configure:function(value){ctx=value;},load:load,render:render,action:action,change:change,duration:duration};
})(typeof window !== 'undefined' ? window : globalThis);
