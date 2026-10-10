(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoScreenRelatorios=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var asArray=deps.asArray;
    var availableSummaryValue=deps.availableSummaryValue;
    var companyBreadcrumbs=deps.companyBreadcrumbs;
    var companyName=deps.companyName;
    var competenceBreadcrumbs=deps.competenceBreadcrumbs;
    var competenceSummaryFor=deps.competenceSummaryFor;
    var competenciesForCompany=deps.competenciesForCompany;
    var competencyAreaNavigation=deps.competencyAreaNavigation;
    var demoBanner=deps.demoBanner;
    var emptyState=deps.emptyState;
    var escapeHtml=deps.escapeHtml;
    var formatCompetence=deps.formatCompetence;
    var formatDateTime=deps.formatDateTime;
    var idOf=deps.idOf;
    var missingContextScreen=deps.missingContextScreen;
    var normalizeArgs=deps.normalizeArgs;
    var normalizeStatus=deps.normalizeStatus;
    var pageHeader=deps.pageHeader;
    var selectedEntities=deps.selectedEntities;
    var statusChip=deps.statusChip;
    var statusKey=deps.statusKey;
    var summaryItem=deps.summaryItem;
    var valueOf=deps.valueOf;
  function competencyExportContent(context, entities) {
    var competence = entities.competence;
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    var exporting = valueOf(context.state, ["exportExcelLoading"], false) === true;
    var summary = online ? competenceSummaryFor(context, competence) : null;
    var general = summary && summary.general || {};
    var pendingValue = online ? availableSummaryValue(general.pending) : Number(valueOf(competence, ["pendingCount", "quantidadePendencias"], "—"));
    var employeeTotal = online && general.employees !== null && general.employees !== undefined && general.employees !== "" ? Number(general.employees) : null;
    var confirmedTotal = online && general.confirmed !== null && general.confirmed !== undefined && general.confirmed !== "" ? Number(general.confirmed) : null;
    var pendingTotal = online && general.pending !== null && general.pending !== undefined && general.pending !== "" ? Number(general.pending) : Number(pendingValue);
    var progress = online
      ? (Number.isFinite(employeeTotal) && employeeTotal > 0 && Number.isFinite(confirmedTotal) ? Math.round((confirmedTotal / employeeTotal) * 100) + "%" : "Indisponível")
      : valueOf(competence, ["progress", "progresso"], "—") + "%";
    var hasUnavailableRows = online && summary && asArray(summary.rows).some(function (row) {
      var situation = statusKey(row.situation);
      return !situation || situation === "indisponivel" || situation === "unavailable";
    });
    var readinessStatus = online
      ? (!summary || progress === "Indisponível" || !Number.isFinite(pendingTotal) || hasUnavailableRows
        ? statusChip(context.components, "sem_expediente", "Apuração indisponível")
        : statusChip(context.components, pendingTotal > 0 ? "conferir" : "normal", pendingTotal > 0 ? "Revisão recomendada" : "Pronto para exportar"))
      : statusChip(context.components, pendingValue ? "conferir" : "normal", pendingValue ? "Revisão recomendada" : "Pronto para exportar");
    return [
      '<div class="report-grid">',
      reportCard("Resumo da competência", "Visão consolidada de saldo, ausências e pendências por funcionário.", "Abrir prévia", "preview-summary-report"),
      reportCard("Planilha de conferência", "Exportação operacional com as marcações e o resultado atual da conferência.", exporting ? "Gerando..." : "Exportar Excel", "export-excel", { disabled: exporting, busy: exporting }),
      reportCard("Relatório para impressão", "Layout limpo para imprimir ou salvar como PDF no navegador.", "Abrir impressão", "open-print-report"),
      reportCard("Espelhos de ponto (todos os funcionários)", "Um espelho por funcionário, pronto para impressão e assinatura.", "Abrir espelhos", "open-espelhos-lote"),
      "</div>",
      '<section class="work-card report-readiness"><div class="section-heading"><div><h2>Prontidão para exportação</h2><p>' + (online ? "Indicadores da apuração mais recente desta competência." : "Os indicadores abaixo são simulados.") + "</p></div>" + readinessStatus + '</div><dl class="summary-grid summary-grid--four">' + summaryItem("Empresa", companyName(entities.company)) + summaryItem("Competência", formatCompetence(competence)) + summaryItem("Progresso", progress) + summaryItem("Pendências", pendingValue) + "</dl></section>",
    ].join("");
  }
  function renderCompetencyExports(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Exportações", "Selecione uma empresa e uma competência antes de exportar.", true);
    return '<section class="screen screen--competency-exports" data-screen="competency-exports">' + demoBanner() + pageHeader(context.components, {
      title: "Exportações",
      subtitle: companyName(entities.company) + " · " + formatCompetence(entities.competence),
      breadcrumbs: competenceBreadcrumbs(entities, "Exportações"),
    }) + competencyAreaNavigation("competency-exports") + competencyExportContent(context, entities) + "</section>";
  }
  function renderCompanyReports(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company) return missingContextScreen(context, "Relatórios", "Abra uma empresa para visualizar seus relatórios.", false);
    var competencies = competenciesForCompany(entities, entities.company);
    var totalPending = competencies.reduce(function (total, competence) { return total + Number(valueOf(competence, ["pendingCount", "quantidadePendencias"], "—")); }, 0);
    var rows = competencies.map(function (competence) {
      return '<tr><td><strong>' + escapeHtml(formatCompetence(competence)) + "</strong></td><td>" + statusChip(context.components, competence.status, competence.statusLabel) + "</td><td>" + escapeHtml(valueOf(competence, ["progress", "progresso"], "—")) + "%</td><td>" + escapeHtml(valueOf(competence, ["pendingCount", "quantidadePendencias"], "—")) + "</td><td>" + escapeHtml(formatDateTime(valueOf(competence, ["updatedAt", "updated_at"], null))) + '</td><td><button class="table-link" type="button" data-action="open-competence-area" data-competence-id="' + escapeHtml(idOf(competence)) + '" data-route="competency-exports">Abrir exportações</button></td></tr>';
    }).join("");
    return '<section class="screen screen--company-reports" data-screen="company-reports">' + demoBanner() + pageHeader(context.components, {
      title: "Relatórios",
      subtitle: companyName(entities.company),
      breadcrumbs: companyBreadcrumbs(entities.company, "Relatórios"),
    }) + '<section class="work-card competency-hero"><dl class="summary-grid">' + summaryItem("Competências", competencies.length) + summaryItem("Em conferência", competencies.filter(function (item) { return normalizeStatus(item.status) === "em_conferencia"; }).length) + summaryItem("Conferidas", competencies.filter(function (item) { return normalizeStatus(item.status) === "conferida"; }).length) + summaryItem("Fechadas", competencies.filter(function (item) { return normalizeStatus(item.status) === "fechada"; }).length) + summaryItem("Problemas", Number.isFinite(totalPending) ? totalPending : "—") + '</dl></section><section class="work-card"><div class="section-heading"><div><h2>Relatórios por competência</h2><p>Escolha uma competência para gerar suas saídas.</p></div></div>' + (rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Competência</th><th>Status</th><th>Progresso</th><th>Pendências</th><th>Atualização</th><th><span class="sr-only">Ação</span></th></tr></thead><tbody>' + rows + "</tbody></table></div>" : emptyState(context.components, "Nenhuma competência", "Crie uma competência antes de gerar relatórios.", { label: "Criar competência", action: "new-competence" })) + "</section></section>";
  }
  function renderReports(state, data, components) {
    return renderCompanyReports(state, data, components);
  }
  function reportCard(title, description, label, action, options) {
    var settings = options || {};
    return '<article class="report-card"><span class="report-card__icon" aria-hidden="true">▤</span><h2>' + escapeHtml(title) + "</h2><p>" + escapeHtml(description) + '</p><button class="button button--secondary" type="button" data-action="' + escapeHtml(action) + '"' + (settings.busy ? ' aria-busy="true"' : "") + (settings.disabled ? " disabled" : "") + ">" + escapeHtml(label) + "</button></article>";
  }
    return Object.freeze({competencyExportContent:competencyExportContent,renderCompetencyExports:renderCompetencyExports,renderCompanyReports:renderCompanyReports,renderReports:renderReports,reportCard:reportCard});
  }
  return Object.freeze({create:create});
});
