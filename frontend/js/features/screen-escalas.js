(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoScreenEscalas=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var companyBreadcrumbs=deps.companyBreadcrumbs;
    var companyName=deps.companyName;
    var demoBanner=deps.demoBanner;
    var emptyState=deps.emptyState;
    var escapeHtml=deps.escapeHtml;
    var idOf=deps.idOf;
    var missingContextScreen=deps.missingContextScreen;
    var normalizeArgs=deps.normalizeArgs;
    var pageHeader=deps.pageHeader;
    var scaleName=deps.scaleName;
    var selectedEntities=deps.selectedEntities;
    var statusChip=deps.statusChip;
    var valueOf=deps.valueOf;
  function scaleTime(value) {
    return value ? String(value).slice(0, 5) : "—";
  }
  function scaleRegimeLabel(value) {
    return {
      trabalha: "Trabalha",
      compensado: "Compensado",
      nao_trabalha: "Não trabalha",
    }[value] || value || "—";
  }
  function scaleScheduleLabel(scale) {
    var mode = valueOf(scale, ["modo_apuracao", "mode"], "carga_horaria");
    if (mode === "horario_fixo") {
      var first = scaleTime(valueOf(scale, ["horario_entrada_prevista"], null));
      var last = scaleTime(valueOf(scale, ["horario_saida_prevista"], null));
      var lunchOut = scaleTime(valueOf(scale, ["horario_saida_almoco_prevista"], null));
      var lunchReturn = scaleTime(valueOf(scale, ["horario_retorno_almoco_prevista"], null));
      return first + "–" + last + (lunchOut !== "—" ? " · intervalo " + lunchOut + "–" + lunchReturn : "");
    }
    var weekday = valueOf(scale, ["jornada_seg_sex_horas"], null);
    var saturday = valueOf(scale, ["jornada_sabado_horas"], null);
    return (weekday == null ? "—" : weekday + " h seg–sex") + (saturday == null ? "" : " · " + saturday + " h sábado");
  }
  function renderCompanyScales(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    var company = entities.company;
    if (!company) return missingContextScreen(context, "Escalas", "Abra uma empresa para visualizar suas escalas.", false);
    var loading = valueOf(context.state, ["scalesLoading"], false) === true;
    var error = valueOf(context.state, ["scalesError"], "");
    var rows = entities.companyScales.map(function (scale) {
      var active = valueOf(scale, ["active", "ativa"], true) !== false;
      var mode = valueOf(scale, ["modo_apuracao", "mode"], "carga_horaria");
      var tolerances = [
        valueOf(scale, ["tolerancia_atraso_minutos"], 0) + " min atraso",
        valueOf(scale, ["tolerancia_extra_minutos"], 0) + " min extra",
        valueOf(scale, ["tolerancia_intervalo_minutos"], 0) + " min intervalo",
      ].join(" · ");
      return '<tr><td><strong>' + escapeHtml(scaleName(scale)) + '</strong></td><td>' + escapeHtml(mode === "horario_fixo" ? "Horário fixo" : "Carga horária") + '<small>' + escapeHtml(scaleScheduleLabel(scale)) + '</small></td><td>' + escapeHtml(scaleRegimeLabel(valueOf(scale, ["regime_sabado"], null))) + '</td><td>' + escapeHtml(scaleRegimeLabel(valueOf(scale, ["regime_domingo"], null))) + '</td><td><small>' + escapeHtml(tolerances) + '</small></td><td>' + statusChip(context.components, active ? "normal" : "sem_expediente", active ? "Ativa" : "Inativa") + '</td><td><div class="table-actions"><button class="table-link" type="button" data-action="edit-scale" data-scale-id="' + escapeHtml(idOf(scale)) + '">Editar</button><button class="table-link table-link--danger" type="button" data-action="deactivate-scale" data-scale-id="' + escapeHtml(idOf(scale)) + '">' + (active ? "Desativar" : "Remover") + '</button></div></td></tr>';
    }).join("");
    return [
      '<section class="screen screen--company-scales" data-screen="company-scales">', demoBanner(),
      pageHeader(context.components, { title: "Escalas", subtitle: companyName(company), breadcrumbs: companyBreadcrumbs(company, "Escalas"), actions: [{ label: "Nova escala", variant: "button--primary", action: "new-scale" }] }),
      error ? '<div class="inline-feedback inline-feedback--error" role="alert">' + escapeHtml(error) + '</div>' : "",
      '<section class="work-card"' + (loading ? ' aria-busy="true"' : "") + '>',
      rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Escala</th><th>Apuração e jornada</th><th>Sábado</th><th>Domingo</th><th>Tolerâncias</th><th>Status</th><th><span class="sr-only">Ações</span></th></tr></thead><tbody>' + rows + '</tbody></table></div>' : loading ? '<div class="empty-state"><p>Carregando escalas…</p></div>' : emptyState(context.components, "Nenhuma escala cadastrada", "Cadastre uma escala antes de vincular funcionários.", { label: "Cadastrar escala", action: "new-scale" }),
      '</section></section>',
    ].join("");
  }
    return Object.freeze({scaleTime:scaleTime,scaleRegimeLabel:scaleRegimeLabel,scaleScheduleLabel:scaleScheduleLabel,renderCompanyScales:renderCompanyScales});
  }
  return Object.freeze({create:create});
});
