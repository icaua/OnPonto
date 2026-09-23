(function (root) {
  "use strict";
  var labels = { ATESTADO: "Atestado", DECLARACAO: "Declaração de horas", FERIAS: "Férias", AFASTAMENTO: "Afastamento", FOLGA_COMPENSATORIA: "Folga compensatória" };
  var ctx, items = [], companyId = null, sequence = 0, loading = false, error = "";
  var filters = {};
  function esc(value) { return root.OnPontoUtils.escapeHtml(value == null ? "" : value); }
  function button(action, label, id, disabled) {
    return '<button type="button" class="button ' + (action === 'new' ? 'button--primary' : 'button--secondary') + '" data-action="ocorrencia-' + action + '" data-oc-id="' + esc(id || "") + '"' + (disabled ? " disabled" : "") + '>' + esc(label) + '</button>';
  }
  function option(value, label, selected) {
    return '<option value="' + esc(value) + '"' + (String(value) === String(selected) ? " selected" : "") + '>' + esc(label) + '</option>';
  }
  function field(label, content) { return '<label class="dialog-field"><span>' + esc(label) + '</span>' + content + '</label>'; }
  function employees(state, data) { return (data.employees || data.funcionarios || []).filter(function (e) { return String(e.companyId || e.empresa_id) === String(state.selectedCompanyId); }); }
  function load() {
    var state = ctx.state();
    if (String(companyId) !== String(state.selectedCompanyId)) { companyId = state.selectedCompanyId; filters = {}; items = []; }
    var request = ++sequence;
    if (state.apiMode !== "online") { items = []; loading = false; error = "Ligue a API para cadastrar e consultar ocorrências."; ctx.render(); return Promise.resolve(); }
    var params = new URLSearchParams({ empresa_id: companyId });
    Object.keys(filters).forEach(function (k) { if (filters[k]) params.set(k, filters[k]); });
    loading = true; error = ""; ctx.render();
    return ctx.api("/ocorrencias?" + params).then(function (result) { if (request === sequence) items = result; })
      .catch(function (err) { if (request === sequence) { error = err.message; items = []; } })
      .finally(function () { if (request === sequence) { loading = false; ctx.render(); } });
  }
  function render(state, data, components) {
    var staff = employees(state, data), online = state.apiMode === "online";
    var companies = data.companies || data.empresas || [];
    var competencies = (data.competencies || data.competencias || []).filter(function (c) { return String(c.companyId || c.empresa_id) === String(state.selectedCompanyId); });
    var company = companies.find(function (c) { return String(c.id) === String(state.selectedCompanyId); });
    var rows = items.map(function (o) {
      var employee = staff.find(function (e) { return e.id === o.funcionario_id; });
      var dateLabel = root.OnPontoUtils.formatDate(o.data_inicio) + " até " + (o.data_fim ? root.OnPontoUtils.formatDate(o.data_fim) : "em aberto");
      var hours = o.hora_inicio ? '<small>' + esc(o.hora_inicio.slice(0, 5)) + "–" + esc(o.hora_fim.slice(0, 5)) + '</small>' : '';
      var actions = button("history", "Histórico", o.id);
      if (!o.excluido_em) actions = button("edit", "Editar", o.id) + button("delete", "Excluir", o.id) + actions +
        '<label class="button button--secondary">Anexar<input class="sr-only" type="file" accept=".pdf,.png,.jpg,.jpeg" data-action="ocorrencia-attachment" data-oc-id="' + o.id + '"></label>' +
        (o.anexo_nome ? button("download", "Baixar anexo", o.id) : '');
      return '<tr><td><strong>' + esc(employee && (employee.name || employee.nome) || "Funcionário #" + o.funcionario_id) + '</strong></td><td><span class="occurrence-type occurrence-type--' + o.tipo.toLowerCase() + '">' + esc(labels[o.tipo]) + '</span>' + (o.excluido_em ? '<small>Excluída</small>' : '') + '</td><td>' + esc(dateLabel) + hours + '</td><td>' + esc(o.observacao || "—") + (o.anexo_nome ? '<small>' + esc(o.anexo_nome) + '</small>' : '') + '</td><td><div class="occurrence-actions">' + actions + '</div></td></tr>';
    }).join('');
    return '<section class="screen" data-screen="company-ocorrencias">' + components.PageHeader({title: "Ocorrências / Afastamentos", subtitle: company && (company.name || company.nome) || "Selecione uma empresa", actions: []}) +
      '<section class="work-card"><div class="occurrence-filters">' +
      field("Empresa", '<select data-action="ocorrencia-company">' + companies.map(function (c) { return option(c.id, c.name || c.nome, state.selectedCompanyId); }).join('') + '</select>') +
      field("Funcionário", '<select data-action="ocorrencia-filter" data-filter="funcionario_id">' + option('', 'Todos', filters.funcionario_id) + staff.map(function (e) { return option(e.id, e.name || e.nome, filters.funcionario_id); }).join('') + '</select>') +
      field("Competência", '<select data-action="ocorrencia-filter" data-filter="competencia_id">' + option('', 'Período livre', filters.competencia_id) + competencies.map(function (c) { return option(c.id, c.label || c.period || ((c.mes || c.month) + '/' + (c.ano || c.year)), filters.competencia_id); }).join('') + '</select>') +
      field("De", '<input type="date" data-action="ocorrencia-filter" data-filter="data_inicio" value="' + esc(filters.data_inicio) + '"' + (filters.competencia_id ? ' disabled' : '') + '>') +
      field("Até", '<input type="date" data-action="ocorrencia-filter" data-filter="data_fim" value="' + esc(filters.data_fim) + '"' + (filters.competencia_id ? ' disabled' : '') + '>') +
      field("Excluídas", '<select data-action="ocorrencia-filter" data-filter="incluir_excluidas">' + option('', 'Ocultar', filters.incluir_excluidas) + option('true', 'Mostrar no histórico', filters.incluir_excluidas) + '</select>') + '</div>' +
      '<div class="form-footer"><p class="helper-text">Períodos que atingem competências fechadas exigem reabertura. Abonos parciais automáticos requerem escala de horário fixo.</p>' + button('new', 'Adicionar ocorrência', '', !online || !staff.length || loading) + '</div></section>' +
      (error ? '<p class="inline-feedback inline-feedback--error" role="alert">' + esc(error) + '</p>' : '') +
      '<section class="work-card" aria-busy="' + loading + '">' + (loading ? '<p role="status">Carregando ocorrências…</p>' : rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Funcionário</th><th>Tipo</th><th>Período</th><th>Observação / anexo</th><th>Ações</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<p>Nenhuma ocorrência neste filtro.</p>') + '</section></section>';
  }
  function historyMarkup(event) {
    var fieldLabels = {funcionario_id:"Funcionário",tipo:"Tipo",data_inicio:"Data inicial",data_fim:"Data final",hora_inicio:"Hora inicial",hora_fim:"Hora final",observacao:"Observação",anexo_nome:"Anexo",excluido_em:"Excluída em"};
    var before = event.antes || {}, after = event.depois || {};
    function display(key, value) {
      if (value === null || value === undefined || value === "") return "—";
      if (key === "tipo") return labels[value] || value;
      if (key === "funcionario_id") {
        var person = employees(ctx.state(), ctx.data()).find(function(e){return e.id === value;});
        return person ? person.name || person.nome : "#" + value;
      }
      return value;
    }
    var rows = Object.keys(fieldLabels).filter(function(key){return before[key] !== after[key];}).map(function(key){
      return '<tr><th>' + esc(fieldLabels[key]) + '</th><td>' + esc(display(key,before[key])) + '</td><td>' + esc(display(key,after[key])) + '</td></tr>';
    }).join('');
    var actionLabel = {criacao:"Criação",alteracao:"Alteração",exclusao:"Exclusão",anexo:"Anexo"}[event.acao] || event.acao;
    var at = new Date(event.at).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'});
    return '<details><summary>' + esc(actionLabel) + ' · ' + esc(at) + ' · ' + esc(event.actor) + '</summary><div class="table-frame"><table class="data-table"><thead><tr><th>Campo</th><th>Antes</th><th>Depois</th></tr></thead><tbody>' + rows + '</tbody></table></div></details>';
  }
  function changed() { ctx.invalidate(); return load(); }
  function openForm(item, options) {
    var settings = options || {};
    var staff = employees(ctx.state(), ctx.data()), o = item || settings.defaults || {};
    var partial = function (v) { return v.tipo === "DECLARACAO" || (["ATESTADO", "FOLGA_COMPENSATORIA"].indexOf(v.tipo) !== -1 && v.periodo === "parcial"); };
    ctx.dialog({title: item ? "Editar ocorrência" : "Adicionar ocorrência", wide: true, fieldLayout: "grid", confirmLabel: "Salvar ocorrência",
      fields: [
        {name:"funcionario_id", label:"Funcionário", type:"select", required:true, value:o.funcionario_id, options:staff.map(function(e){return {value:e.id,label:e.name || e.nome};})},
        {name:"tipo",label:"Tipo",type:"select",value:o.tipo || "ATESTADO",options:Object.keys(labels).map(function(t){return {value:t,label:labels[t]};})},
        {name:"periodo",label:"Cobertura da ocorrência",type:"select",value:o.hora_inicio ? "parcial" : "integral",options:[{value:"integral",label:"Dia(s) integral(is)"},{value:"parcial",label:"Período por horário"}],visibleWhen:function(v){return ["ATESTADO", "FOLGA_COMPENSATORIA"].indexOf(v.tipo) !== -1;}},
        {name:"data_inicio",label:"Data inicial",type:"date",required:true,value:o.data_inicio || ""},
        {name:"data_fim",label:"Data final",type:"date",value:o.data_fim || "",help:"Obrigatória, exceto para afastamento em aberto.",visibleWhen:function(v){return !partial(v);}},
        {name:"hora_inicio",label:"Hora inicial",type:"time",required:true,value:o.hora_inicio && o.hora_inicio.slice(0,5),visibleWhen:partial},
        {name:"hora_fim",label:"Hora final",type:"time",required:true,value:o.hora_fim && o.hora_fim.slice(0,5),visibleWhen:partial},
        {name:"observacao",label:"Observação / motivo",type:"textarea",value:o.observacao || "",maxlength:5000,fullWidth:true}
      ], onConfirm:function(v){
        var payload = {funcionario_id:Number(v.funcionario_id),tipo:v.tipo,data_inicio:v.data_inicio,data_fim:partial(v) ? v.data_inicio : v.data_fim || null,
                       hora_inicio:partial(v) ? v.hora_inicio : null,hora_fim:partial(v) ? v.hora_fim : null,observacao:v.observacao || null};
        return Promise.resolve().then(function () { if (settings.beforeSave) return settings.beforeSave(); })
          .then(function () { return ctx.api('/ocorrencias' + (item ? '/' + item.id : ''), {method:item ? 'PATCH' : 'POST',body:payload}); })
          .then(function (saved) {
            if (!settings.onSaved) return changed();
            ctx.invalidate();
            return saved;
          });
      }, onSaved:settings.onSaved});
  }
  function action(action, element, event) {
    if (action.indexOf('ocorrencia-') !== 0) return false;
    if (element.matches('input,select')) return true;
    event.preventDefault();
    var item = items.find(function(o){return String(o.id) === element.dataset.ocId;});
    if (action === 'ocorrencia-new') openForm();
    if (action === 'ocorrencia-edit' && item) openForm(item);
    if (action === 'ocorrencia-delete' && item) ctx.dialog({title:'Excluir ocorrência',description:'O registro deixará de afetar a apuração. Seu histórico será preservado.',confirmLabel:'Excluir',destructive:true,onConfirm:function(){return ctx.api('/ocorrencias/'+item.id,{method:'DELETE'}).then(changed).catch(function(err){ctx.toast(err.message,'error');});}});
    if (action === 'ocorrencia-download' && item) root.open(ctx.apiBase()+'/ocorrencias/'+item.id+'/anexo','_blank','noopener,noreferrer');
    if (action === 'ocorrencia-history' && item) ctx.api('/ocorrencias/'+item.id+'/historico').then(function(events){
      ctx.dialog({title:'Histórico da ocorrência #'+item.id,wide:true,confirmLabel:'Fechar',html:events.map(historyMarkup).join('')});
    }).catch(function(err){ctx.toast(err.message,'error');});
    return true;
  }
  function change(action, element) {
    if (action.indexOf('ocorrencia-') !== 0) return false;
    if (action === 'ocorrencia-company') ctx.navigate({view:'company-ocorrencias',companyId:Number(element.value),competenceId:null});
    if (action === 'ocorrencia-filter') { filters[element.dataset.filter] = element.value; load(); }
    if (action === 'ocorrencia-attachment' && element.files[0]) {
      var form = new FormData(); form.append('arquivo',element.files[0]);
      ctx.api('/ocorrencias/'+element.dataset.ocId+'/anexo',{method:'POST',body:form,timeout:30000}).then(changed).catch(function(err){ctx.toast(err.message,'error');});
    }
    return true;
  }
  root.OnPontoOcorrencias = {configure:function(context){ctx=context;},render:render,load:load,action:action,change:change,
    create:function(defaults, options){openForm(null, Object.assign({}, options, {defaults:defaults}));}};
})(window);
