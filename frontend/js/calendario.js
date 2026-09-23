(function (root) {
  "use strict";
  var ctx, items = [], loading = false, error = "", sequence = 0;
  var filters = {ano: String(new Date().getFullYear()), tipo: "", abrangencia: ""};
  var types = {FERIADO: "Feriado", DATA_COMEMORATIVA: "Data comemorativa"};
  var scopes = {NACIONAL: "Nacional", ESTADUAL: "Estadual", MUNICIPAL: "Municipal", EMPRESA: "Empresa"};
  var ufs = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
  function esc(v) { return root.OnPontoUtils.escapeHtml(v == null ? "" : v); }
  function companies() { var d = ctx.data(); return d.companies || d.empresas || []; }
  function options(map, selected, all) {
    return (all ? '<option value="">' + esc(all) + '</option>' : '') + Object.keys(map).map(function(k){
      return '<option value="' + esc(k) + '"' + (String(selected) === k ? ' selected' : '') + '>' + esc(map[k]) + '</option>';
    }).join('');
  }
  function button(action, label, id, disabled) {
    return '<button type="button" class="button button--' + (action === 'new' ? 'primary' : 'secondary') + '" data-action="calendar-' + action + '" data-event-id="' + esc(id || '') + '"' + (disabled ? ' disabled' : '') + '>' + esc(label) + '</button>';
  }
  function load() {
    var ticket = ++sequence;
    if (ctx.state().apiMode !== 'online') { items = []; loading = false; error = 'Conecte a API para consultar e cadastrar as datas do calendário.'; ctx.render(); return Promise.resolve(); }
    loading = true; error = ''; ctx.render();
    var params = new URLSearchParams(filters);
    if (!filters.tipo) params.delete('tipo');
    if (!filters.abrangencia) params.delete('abrangencia');
    return ctx.api('/calendario?' + params.toString()).then(function(result){
      if (ticket === sequence) items = result;
    }).catch(function(err){ if (ticket === sequence) { error = err.message; items = []; } }).finally(function(){
      if (ticket === sequence) { loading = false; ctx.render(); }
    });
  }
  function field(label, input) { return '<label class="dialog-field"><span>' + esc(label) + '</span>' + input + '</label>'; }
  function render(state, data, components) {
    var online = state.apiMode === 'online';
    var rows = items.map(function(e){
      var date = e.data.split('-');
      var dateLabel = date[2] + '/' + date[1] + '/' + (e.recorrente ? filters.ano : date[0]);
      var company = companies().find(function(c){return String(c.id) === String(e.empresa_id);});
      var place = e.abrangencia === 'EMPRESA' ? company && (company.name || company.nome) || 'Empresa #' + e.empresa_id : [e.municipio, e.uf].filter(Boolean).join(' / ');
      return '<tr><td>' + esc(dateLabel) + (e.recorrente ? '<small>Recorrente anual</small>' : '') + '</td><th scope="row"><strong>' + esc(e.nome) + '</strong>' + (e.descricao ? '<small>' + esc(e.descricao) + '</small>' : '') + '</th><td>' + esc(types[e.tipo]) + '</td><td>' + esc(scopes[e.abrangencia]) + '<small>' + esc(place) + '</small></td><td>' + components.StatusChip({status:e.ativo ? 'normal' : 'sem_expediente',label:e.ativo ? 'Ativo' : 'Inativo'}) + '</td><td><div class="table-actions">' + button('edit','Editar',e.id,!online || loading) + (e.ativo ? button('deactivate','Desativar',e.id,!online || loading) : '') + '</div></td></tr>';
    }).join('');
    return '<section class="screen" data-screen="calendar">' + components.PageHeader({title:'Calendário',subtitle:'Feriados e datas comemorativas de todas as empresas.'}) +
      '<section class="work-card"><div class="calendar-filters">' +
      field('Ano','<input type="number" min="1" max="9999" step="1" data-action="calendar-filter" data-filter="ano" value="' + esc(filters.ano) + '">') +
      field('Tipo','<select data-action="calendar-filter" data-filter="tipo">' + options(types,filters.tipo,'Todos') + '</select>') +
      field('Abrangência','<select data-action="calendar-filter" data-filter="abrangencia">' + options(scopes,filters.abrangencia,'Todas') + '</select>') + button('new','+ Nova data','',!online || loading) + '</div>' +
      '<p class="helper-text">Datas comemorativas são apenas informativas. A recorrência anual repete o mesmo dia e mês; cadastre feriados móveis separadamente em cada ano.</p>' +
      '<p class="helper-text">Alterações afetam a próxima apuração de competências abertas. Competências fechadas preservam o resultado do fechamento.</p></section>' +
      (error ? '<div class="inline-feedback inline-feedback--error" role="alert">' + esc(error) + ' ' + button('reload','Tentar novamente') + '</div>' : '') +
      '<section class="work-card" aria-busy="' + loading + '">' + (loading ? '<p role="status">Carregando calendário…</p>' : rows ? '<div class="table-frame"><table class="data-table"><caption class="sr-only">Datas do ano selecionado</caption><thead><tr><th>Data</th><th>Nome</th><th>Tipo</th><th>Abrangência</th><th>Situação</th><th>Ações</th></tr></thead><tbody>' + rows + '</tbody></table></div>' : '<p>Nenhuma data neste filtro.</p>') + '</section></section>';
  }
  function changed() { ctx.invalidate(); return load(); }
  function openForm(item) {
    var e = item || {};
    var selectOptions = function(map){return Object.keys(map).map(function(k){return {value:k,label:map[k]};});};
    var hasUf = function(v){return v.abrangencia === 'ESTADUAL' || v.abrangencia === 'MUNICIPAL';};
    ctx.dialog({title:item ? 'Editar data' : 'Nova data',wide:true,fieldLayout:'grid',confirmLabel:'Salvar data',fields:[
      {name:'nome',label:'Nome',type:'text',required:true,maxlength:180,value:e.nome || ''},
      {name:'data',label:'Data',type:'date',required:true,value:e.data || ''},
      {name:'tipo',label:'Tipo',type:'select',value:e.tipo || 'FERIADO',options:selectOptions(types)},
      {name:'abrangencia',label:'Abrangência',type:'select',value:e.abrangencia || 'NACIONAL',options:selectOptions(scopes)},
      {name:'uf',label:'UF',type:'select',required:true,value:e.uf || '',visibleWhen:hasUf,options:[{value:'',label:'Selecione'}].concat(ufs.map(function(uf){return {value:uf,label:uf};}))},
      {name:'municipio',label:'Município',type:'text',required:true,maxlength:120,value:e.municipio || '',visibleWhen:function(v){return v.abrangencia === 'MUNICIPAL';},help:'Use o município cadastrado na empresa.'},
      {name:'empresa_id',label:'Empresa',type:'select',required:true,value:e.empresa_id || '',visibleWhen:function(v){return v.abrangencia === 'EMPRESA';},options:[{value:'',label:'Selecione'}].concat(companies().map(function(c){return {value:c.id,label:c.name || c.nome};}))},
      {name:'recorrente',label:'Recorrência',type:'select',value:e.recorrente ? 'true' : 'false',options:[{value:'false',label:'Somente nesta data'},{value:'true',label:'Anual, no mesmo dia e mês'}],help:'Feriados móveis devem ser cadastrados com a data correta de cada ano, sem recorrência.'},
      {name:'ativo',label:'Situação',type:'select',value:e.ativo === false ? 'false' : 'true',options:[{value:'true',label:'Ativo'},{value:'false',label:'Inativo'}]},
      {name:'descricao',label:'Descrição',type:'textarea',maxlength:5000,fullWidth:true,value:e.descricao || ''}
    ],onConfirm:function(v){
      var payload = {nome:v.nome,data:v.data,tipo:v.tipo,abrangencia:v.abrangencia,uf:hasUf(v) ? v.uf : null,
        municipio:v.abrangencia === 'MUNICIPAL' ? v.municipio : null,empresa_id:v.abrangencia === 'EMPRESA' ? Number(v.empresa_id) : null,
        recorrente:v.recorrente === 'true',ativo:v.ativo === 'true',descricao:v.descricao || null};
      return ctx.api('/calendario' + (item ? '/' + item.id : ''),{method:item ? 'PATCH' : 'POST',body:payload}).then(changed);
    }});
  }
  function action(action, element, event) {
    if (action.indexOf('calendar-') !== 0) return false;
    if (element.matches('input,select')) return true;
    event.preventDefault();
    var item = items.find(function(e){return String(e.id) === element.dataset.eventId;});
    if (action === 'calendar-new') openForm();
    if (action === 'calendar-edit' && item) openForm(item);
    if (action === 'calendar-reload') load();
    if (action === 'calendar-deactivate' && item) ctx.api('/calendario/' + item.id,{method:'PATCH',body:{ativo:false}}).then(changed).catch(function(err){ctx.toast(err.message,'error');});
    return true;
  }
  function change(action, element) {
    if (action !== 'calendar-filter') return false;
    if (!element.checkValidity()) { element.reportValidity(); return true; }
    if (element.dataset.filter === 'ano' && !element.value) return true;
    filters[element.dataset.filter] = element.value; load(); return true;
  }
  root.OnPontoCalendario = {configure:function(context){ctx=context;},render:render,load:load,action:action,change:change};
})(window);
