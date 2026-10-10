(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoScreenImportacao=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var asArray=deps.asArray;
    var closedCompetenceNotice=deps.closedCompetenceNotice;
    var collection=deps.collection;
    var companyName=deps.companyName;
    var competenceBreadcrumbs=deps.competenceBreadcrumbs;
    var competenceIsClosed=deps.competenceIsClosed;
    var competencyAreaNavigation=deps.competencyAreaNavigation;
    var component=deps.component;
    var demoBanner=deps.demoBanner;
    var employeeName=deps.employeeName;
    var emptyState=deps.emptyState;
    var escapeHtml=deps.escapeHtml;
    var filesForCompetence=deps.filesForCompetence;
    var filterButton=deps.filterButton;
    var formatCompetence=deps.formatCompetence;
    var formatDate=deps.formatDate;
    var idOf=deps.idOf;
    var idsEqual=deps.idsEqual;
    var missingContextScreen=deps.missingContextScreen;
    var normalizeArgs=deps.normalizeArgs;
    var pageHeader=deps.pageHeader;
    var selectOptions=deps.selectOptions;
    var selectedEntities=deps.selectedEntities;
    var statusChip=deps.statusChip;
    var statusKey=deps.statusKey;
    var valueOf=deps.valueOf;
  function importAnalysisCard(context, analysis) {
    if (!analysis) return "";
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    return [
      '<section class="import-preview import-analysis-result" aria-labelledby="analysisTitle">',
      '<div class="section-heading"><div><span class="eyebrow">' + (online ? "Análise concluída" : "Análise de demonstração concluída") + '</span><h2 id="analysisTitle">' + escapeHtml(valueOf(analysis, ["fileName", "nomeArquivo"], "Arquivo de ponto")) + "</h2></div>" + statusChip(context.components, "analisado", "Pronto para prévia") + "</div>",
      '<dl class="summary-grid">',
      summaryItem("Formato detectado", valueOf(analysis, ["detectedFormat", "formatoDetectado"], "—")),
      summaryItem("Linhas válidas", valueOf(analysis, ["validLineCount", "totalLinhasValidas"], valueOf(analysis, ["recordCount"], 0))),
      summaryItem("Funcionários", valueOf(analysis, ["employeeCount", "totalFuncionarios"], 0)),
      summaryItem("Batidas", valueOf(analysis, ["punchCount", "totalBatidas"], 0)),
      summaryItem("Dias", valueOf(analysis, ["dayCount", "totalDias"], 0)),
      summaryItem("Pendências", valueOf(analysis, ["pendingCount", "totalPendencias"], 0)),
      "</dl>",
      '<div class="button-row"><button class="button button--primary" type="button" data-route="import-preview" data-action="open-import-preview">Ver prévia</button><button class="button button--ghost" type="button" data-action="discard-import">Descartar</button></div>',
      "</section>",
    ].join("");
  }
  function summaryItem(label, value) {
    return "<div><dt>" + escapeHtml(label) + "</dt><dd>" + escapeHtml(value == null || value === "" ? "—" : value) + "</dd></div>";
  }
  function renderImports(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Importações", "Selecione uma empresa e uma competência antes de adicionar arquivos.", true);
    var analysis = valueOf(context.state, ["importAnalysis", "analiseImportacao", "analysisResult"], undefined);
    if (analysis === undefined && valueOf(context.state, ["showImportAnalysis", "analysisVisible", "analiseVisivel"], false)) {
      analysis = valueOf(context.data, ["importAnalysis", "analiseImportacao"], null);
    }
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    var loading = valueOf(context.state, ["importLoading"], false) === true;
    var closed = competenceIsClosed(entities.competence);
    var importError = valueOf(context.state, ["importError"], "");
    var dropzone = component(context.components, ["ImportDropzone", "importDropzone"], {
      id: "importFile",
      inputId: "importFile",
      action: "select-import-file",
      accept: ".txt,.xlsx,text/plain,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      disabled: loading || closed,
      file: valueOf(context.state, ["selectedImportFile", "arquivoSelecionado"], null),
      title: "Arraste o arquivo aqui",
      description: "ou escolha um arquivo do computador",
    }, function () {
      return '<label class="import-dropzone' + (loading || closed ? " is-disabled" : "") + '" for="importFile" data-action="open-file-picker"><span class="import-dropzone__icon" aria-hidden="true">⇧</span><strong>Arraste o arquivo aqui</strong><span>ou escolha um arquivo do computador</span><small>TXT ou XLSX de ponto · o formato é detectado automaticamente</small><input id="importFile" name="importFile" type="file" accept=".txt,.xlsx,text/plain,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" data-action="select-import-file"' + (loading || closed ? " disabled" : "") + "></label>";
    });

    return [
      '<section class="screen screen--imports" data-screen="imports">', demoBanner(),
      pageHeader(context.components, { title: "Importações", subtitle: companyName(entities.company) + " · " + formatCompetence(entities.competence), breadcrumbs: competenceBreadcrumbs(entities, "Importações") }),
      competencyAreaNavigation("imports"),
      closedCompetenceNotice(entities.competence),
      '<section class="work-card competency-hero"><div>' + statusChip(context.components, entities.competence.status, entities.competence.statusLabel) + '</div><dl class="summary-grid summary-grid--four">' + summaryItem("Empresa", companyName(entities.company)) + summaryItem("Competência", formatCompetence(entities.competence)) + summaryItem("Arquivos recebidos", valueOf(entities.competence, ["fileCount", "quantidadeArquivos"], "—")) + summaryItem("Pendências", valueOf(entities.competence, ["pendingCount", "quantidadePendencias"], "—")) + "</dl></section>",
      '<div class="content-grid content-grid--form">',
      '<form class="work-card import-form" data-form="import" data-action="analyze-import"' + (closed ? ' aria-disabled="true"' : "") + ">",
      dropzone,
      '<div class="form-footer"><p class="helper-text">' + (closed ? "Reabra a competência para analisar novos arquivos." : online ? "A análise salva o arquivo original, mas só cria marcações depois da sua confirmação." : "A API está offline; a análise usará dados de demonstração e não enviará o arquivo.") + '</p><button class="button button--primary" type="submit" data-action="analyze-import"' + (loading || closed ? " disabled" : "") + ">" + (loading ? "Analisando..." : "Analisar arquivo") + "</button></div>",
      "</form>",
      '<aside class="context-note"><strong>Como funciona</strong><ol><li>O original é preservado.</li><li>O sistema sugere uma interpretação.</li><li>Você confere e corrige.</li><li>Só então confirma o resultado.</li></ol></aside>',
      "</div>",
      importError ? '<div class="inline-feedback inline-feedback--error" role="alert"><strong>Erro na importação</strong><span>' + escapeHtml(importError) + "</span></div>" : "",
      importAnalysisCard(context, analysis),
      importPendingControls(context, entities),
      "</section>",
    ].join("");
  }
  function importPendingRecord(file, record) {
    return '<li>' + escapeHtml(record.data ? formatDate(record.data, true) : "Sem data") + ' · ' + escapeHtml(record.mensagem || "Registro pendente") +
      ' <button class="text-button" type="button" data-action="discard-import-record" data-file-id="' + escapeHtml(file.id) + '" data-record-id="' + escapeHtml(record.registro_id) + '">Excluir só este</button></li>';
  }
  function importPendingGroups(file, groups) {
    return '<ul class="import-pending-groups">' + groups.map(function (group, index) {
      var records = asArray(group.registros);
      var found = group.funcionario_encontrado !== false;
      // A falta de cadastro já aparece no selo; o texto mostra só os demais motivos.
      var reasons = [];
      records.forEach(function (record) {
        String(record.mensagem || "").split(/;\s*/).forEach(function (reason) {
          if (reason && reasons.indexOf(reason) === -1 && (found || !/não cadastrado/i.test(reason))) reasons.push(reason);
        });
      });
      return '<li class="import-pending-group">' +
        '<div class="import-pending-group__who"><strong>' + escapeHtml(group.nome_origem || "Pessoa sem nome no arquivo") + '</strong>' +
        (group.codigo_origem ? '<small>Código no relógio: ' + escapeHtml(group.codigo_origem) + '</small>' : "") +
        (!found ? '<span class="preview-warning preview-warning--danger">Não cadastrado no OnPonto</span>' : "") + '</div>' +
        '<p class="import-pending-group__what">' + records.length + (records.length === 1 ? " registro pendente" : " registros pendentes") + (reasons.length ? " · " + escapeHtml(reasons.slice(0, 2).join(" / ")) : "") + '</p>' +
        '<div class="import-pending-group__actions">' +
        (!found ? '<button class="button button--primary" type="button" data-action="ignore-import-person" data-file-id="' + escapeHtml(file.id) + '" data-group-index="' + index + '">Ignorar nas importações</button>' : "") +
        '<button class="button button--secondary" type="button" data-action="discard-import-group" data-file-id="' + escapeHtml(file.id) + '" data-group-index="' + index + '">Excluir ' + records.length + ' deste arquivo</button></div>' +
        '<details class="import-pending-group__days"><summary>Ver dias</summary><ul>' + records.map(function (record) { return importPendingRecord(file, record); }).join("") + '</ul></details></li>';
    }).join("") + '</ul>';
  }
  function importIgnoredPeople(context, entities) {
    var rules = asArray((valueOf(context.data, ["ignoredPeople"], {}) || {})[String(idOf(entities.company))]);
    if (!rules.length) return "";
    return '<details class="work-card import-ignored"><summary>Pessoas ignoradas nas importações desta empresa (' + rules.length + ')</summary><ul>' + rules.map(function (rule) {
      // O backend grava em UTC sem fuso; a data exibida segue o horário local.
      var created = rule.criada_em ? new Date(String(rule.criada_em).replace(/(Z|[+-]\d{2}:\d{2})?$/, function (zone) { return zone || "Z"; })) : null;
      var since = created && !isNaN(created.getTime()) ? " · desde " + created.toLocaleDateString("pt-BR") : "";
      return '<li><div><strong>' + escapeHtml(rule.nome_origem || "Pessoa sem nome") + '</strong>' + (rule.codigo_origem ? '<small>Código no relógio: ' + escapeHtml(rule.codigo_origem) + '</small>' : "") +
        '<small>' + escapeHtml(rule.justificativa) + escapeHtml(since) + '</small></div>' +
        '<button class="text-button" type="button" data-action="unignore-import-person" data-rule-id="' + escapeHtml(rule.id) + '">Voltar a considerar</button></li>';
    }).join("") + '</ul></details>';
  }
  function importPendingControls(context, entities) {
    if (competenceIsClosed(entities.competence)) return "";
    var files = filesForCompetence(context, entities.competence);
    var groupsByFile = valueOf(context.data, ["importGroups"], {}) || {};
    var cards = files.map(function(file){
      var c = file.controle_importacao;
      var pending = asArray(c && c.pendencias);
      if (c && c.estado === "confirmada" && !pending.length) return "";
      var cached = groupsByFile[String(file.id)];
      var body = !pending.length ? "" : cached && cached.groups ? importPendingGroups(file, cached.groups)
        : cached && cached.error ? '<p class="muted-text">Não foi possível agrupar por pessoa: ' + escapeHtml(cached.error) + '</p><ul class="import-pending-flat">' + pending.map(function (p) { return importPendingRecord(file, p); }).join("") + '</ul>'
        : '<p class="muted-text" role="status">Agrupando pendências por pessoa…</p>';
      return '<article class="work-card import-pending-file"><header class="import-pending-file__header"><div><h2>' + escapeHtml(file.name || file.nome_original) + '</h2>' +
        (pending.length ? '<p class="helper-text">' + pending.length + (pending.length === 1 ? " registro pendente impede" : " registros pendentes impedem") + ' o fechamento da competência.</p>' : "") +
        '</div><button class="button button--secondary" type="button" data-action="resume-import" data-file-id="' + escapeHtml(file.id) + '">Retomar análise</button></header>' + body + '</article>';
    }).join("");
    return (cards ? '<section class="import-pending" aria-label="Importações a resolver">' + cards + '</section>' : "") + importIgnoredPeople(context, entities);
  }
  function rowSuggestion(row) {
    var explicit = valueOf(row, ["interpretacaoSugerida", "suggestedLabel", "suggestionLabel"], "");
    if (explicit) return explicit;
    var suggestion = valueOf(row, ["suggestion", "suggested", "interpretacaoSugerida"], {}) || {};
    return [
      valueOf(suggestion, ["entry", "entrada"], null),
      valueOf(suggestion, ["breakStart", "breakOut", "saidaIntervalo", "saida_intervalo", "saida_almoco"], null),
      valueOf(suggestion, ["breakEnd", "breakIn", "retorno", "retorno_intervalo", "retorno_almoco"], null),
      valueOf(suggestion, ["exit", "saida"], null),
    ].map(function (time) { return time || "—"; }).join(" / ");
  }
  function originalPunchValues(item) {
    var original = valueOf(item, ["originalPunches", "batidasOriginais"], null);
    if (!original) {
      var nested = valueOf(item, ["original", "originalData", "dadosOriginais"], {}) || {};
      original = valueOf(nested, ["punches", "batidas"], []);
    }
    return asArray(original).map(function (punch) {
      return typeof punch === "object" ? valueOf(punch, ["value", "time", "horario"], "") : punch;
    }).filter(Boolean);
  }
  function renderImportPreview(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Prévia da importação", "Selecione uma empresa e uma competência antes de revisar a importação.", true);
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    var closed = competenceIsClosed(entities.competence);
    var stateAnalysis = valueOf(context.state, ["importAnalysis", "analiseImportacao", "analysisResult"], null);
    var analysis = stateAnalysis || (!online ? valueOf(context.data, ["importAnalysis", "analiseImportacao"], {}) : {}) || {};
    var analysisCompanyId = valueOf(analysis, ["companyId", "empresaId", "empresa_id"], null);
    var analysisCompetenceId = valueOf(analysis, ["competenceId", "competenciaId", "competencia_id"], null);
    if (!idsEqual(analysisCompanyId, idOf(entities.company)) || !idsEqual(analysisCompetenceId, idOf(entities.competence))) analysis = {};
    var rows = asArray(valueOf(context.state, ["importPreviewRows", "linhasPrevia"], null));
    if (!rows.length) rows = asArray(valueOf(analysis, ["rows", "linhas"], null));
    if (!rows.length && !online) rows = collection(context.data, ["importPreviewRows", "linhasPrevia"]);
    rows = rows.filter(function (row) {
      return idsEqual(valueOf(row, ["companyId", "empresaId", "empresa_id"], null), idOf(entities.company)) &&
        idsEqual(valueOf(row, ["competenceId", "competenciaId", "competencia_id"], null), idOf(entities.competence));
    });
    var filter = statusKey(valueOf(context.state, ["importPreviewFilter", "previewFilter", "filtroPrevia"], "all"));
    filter = { todos: "all", pendencias: "pending", somente_pendencias: "pending" }[filter] || filter;
    var employeeFilter = valueOf(context.state, ["importPreviewEmployeeId", "previewEmployeeId", "funcionarioPreviaId"], "");
    var visibleRows = rows.filter(function (row) {
      if (filter === "pending" && !valueOf(row, ["hasPendingIssue", "temPendencia"], false)) return false;
      if (employeeFilter && !idsEqual(valueOf(row, ["employeeId", "funcionario_id"], null), employeeFilter)) return false;
      return true;
    });
    var fileName = valueOf(analysis, ["fileName", "nomeArquivo"], "Nenhum arquivo analisado");
    var hasAnalysis = Boolean(valueOf(analysis, ["fileName", "nomeArquivo"], ""));
    var analysisSaved = valueOf(analysis, ["saved", "salva", "confirmada"], false) === true;
    var selectedIds = asArray(valueOf(context.state, ["selectedImportRowIds", "registrosImportacaoSelecionados"], []));
    var confirming = valueOf(context.state, ["importConfirming"], false) === true;
    var conflicts = asArray(valueOf(context.state, ["importConflicts", "conflitosImportacao"], []));
    var selectedCount = rows.filter(function (row) { return selectedIds.some(function (id) { return idsEqual(id, idOf(row)); }); }).length;
    var visibleSelectable = visibleRows.filter(function (row) { return valueOf(row, ["employeeFound", "funcionarioEncontrado"], true) !== false; });
    var visibleSelectedCount = visibleSelectable.filter(function (row) { return selectedIds.some(function (id) { return idsEqual(id, idOf(row)); }); }).length;
    var allVisibleSelected = visibleSelectable.length > 0 && visibleSelectedCount === visibleSelectable.length;
    var mixedVisibleSelection = visibleSelectedCount > 0 && !allVisibleSelected;

    var table = visibleRows.length ? [
      '<div class="table-frame table-frame--tall"><table class="data-table import-preview-table">',
      '<thead><tr><th class="selection-cell"><input type="checkbox" data-action="toggle-all-import-rows" aria-label="Selecionar todos os registros importáveis visíveis"' + (allVisibleSelected ? " checked" : "") + (mixedVisibleSelection ? ' aria-checked="mixed" data-indeterminate="true"' : "") + (closed ? " disabled" : "") + '></th><th>Funcionário</th><th>Data</th><th>Batidas originais</th><th>Interpretação sugerida</th><th>Status</th><th>Pendências</th></tr></thead><tbody>',
      visibleRows.map(function (row) {
        var punches = originalPunchValues(row);
        var rowId = idOf(row);
        var employeeFound = valueOf(row, ["employeeFound", "funcionarioEncontrado"], true) !== false;
        var outsideCompetence = valueOf(row, ["outsideCompetence", "foraDaCompetencia", "fora_da_competencia"], false) === true;
        var selected = selectedIds.some(function (id) { return idsEqual(id, rowId); });
        var issues = asArray(valueOf(row, ["issues", "pendencias"], [])).map(function (issue) {
          return typeof issue === "string" ? issue : valueOf(issue, ["message", "mensagem", "detail"], "Revisão necessária.");
        });
        var observation = valueOf(row, ["observation", "observacao"], "") || issues.join(" ");
        var sourceName = valueOf(row, ["employeeSourceName", "nomeFuncionarioOrigem", "employeeName", "funcionario", "nomeFuncionario"], "—");
        var registeredName = valueOf(row, ["employeeRegisteredName", "nomeFuncionarioCadastrado"], "");
        return [
          '<tr class="preview-row' + (!employeeFound ? " has-unmatched-employee" : "") + (outsideCompetence ? " is-outside-competence" : "") + '" data-preview-row-id="' + escapeHtml(rowId) + '">',
          '<td class="selection-cell"><input type="checkbox" data-action="toggle-import-row" data-preview-row-id="' + escapeHtml(rowId) + '" aria-label="Selecionar registro de ' + escapeHtml(sourceName) + '"' + (selected ? " checked" : "") + (!employeeFound || closed ? " disabled" : "") + "></td>",
          "<td><strong>" + escapeHtml(registeredName || sourceName) + "</strong>" + (registeredName && registeredName !== sourceName ? "<small>Origem: " + escapeHtml(sourceName) + "</small>" : "") + (row.ignorado ? '<span class="preview-warning" title="' + escapeHtml(row.ignorado.justificativa || "") + '">Ignorado nas importações</span>' : !employeeFound ? '<span class="preview-warning preview-warning--danger">Funcionário não cadastrado</span>' : "") + "</td>",
          "<td>" + escapeHtml(formatDate(valueOf(row, ["date", "data"], null), true)) + (outsideCompetence ? '<span class="preview-warning">Data fora da competência</span>' : "") + "</td>",
          '<td><span class="original-data">' + escapeHtml(punches.length ? punches.join(", ") : "Sem batidas") + "</span></td>",
          '<td><span class="suggested-data">' + escapeHtml(rowSuggestion(row)) + "</span></td>",
          "<td>" + statusChip(context.components, valueOf(row, ["status", "situacao"], "conferir"), valueOf(row, ["statusLabel"], "")) + "</td>",
          '<td class="preview-issues">' + escapeHtml(observation || "—") + "</td>",
          "</tr>",
        ].join("");
      }).join(""),
      "</tbody></table></div>",
    ].join("") : emptyState(context.components, hasAnalysis ? "Nenhum registro neste filtro" : "Nenhuma análise disponível", hasAnalysis ? "Altere os filtros para visualizar outras linhas da prévia." : "Volte para Importações e analise um arquivo desta competência.", hasAnalysis ? null : { label: "Voltar para Importações", route: "imports", action: "navigate" });

    return [
      '<section class="screen screen--import-preview" data-screen="import-preview">', demoBanner(),
      pageHeader(context.components, {
        title: "Prévia da importação",
        subtitle: "O que o sistema entendeu deste arquivo?",
        breadcrumbs: competenceBreadcrumbs(entities, "Importações", "Prévia"),
      }),
      competencyAreaNavigation("imports"),
      closedCompetenceNotice(entities.competence),
      '<section class="work-card import-summary"><div class="section-heading"><div><span class="eyebrow">Arquivo analisado</span><h2>' + escapeHtml(fileName) + "</h2></div>" + (analysisSaved ? statusChip(context.components, "confirmed", "Importação confirmada") : '<span class="unsaved-badge">Não salvo</span>') + "</div>",
      '<dl class="summary-grid summary-grid--four">',
      summaryItem("Empresa", valueOf(analysis, ["companyName", "empresaNome"], companyName(entities.company))),
      summaryItem("Competência", valueOf(analysis, ["competenceLabel", "competenciaLabel"], formatCompetence(entities.competence))),
      summaryItem("Formato", valueOf(analysis, ["detectedFormat", "formatoDetectado"], "—")),
      summaryItem("Funcionários", valueOf(analysis, ["employeeCount", "totalFuncionarios"], 0)),
      summaryItem("Registros", valueOf(analysis, ["recordCount", "totalRegistros"], rows.length)),
      summaryItem("Pendências", valueOf(analysis, ["pendingCount", "totalPendencias"], rows.filter(function (row) { return row.hasPendingIssue; }).length)),
      summaryItem("Não cadastrados", valueOf(analysis, ["unmatchedEmployeeCount", "totalFuncionariosNaoCadastrados"], rows.filter(function (row) { return row.employeeFound === false; }).length)),
      summaryItem("Fora da competência", valueOf(analysis, ["outsideCompetenceCount", "totalForaDaCompetencia"], rows.filter(function (row) { return row.outsideCompetence; }).length)),
      "</dl></section>",
      '<div class="toolbar toolbar--sticky"><div class="filter-group" role="group" aria-label="Filtrar prévia">',
      filterButton("Todos", "all", filter, "preview"), filterButton("Somente pendências", "pending", filter, "preview"),
      '</div><span class="preview-selection-count"><strong>' + escapeHtml(selectedCount) + "</strong> de " + escapeHtml(rows.length) + ' registros selecionados</span><label class="compact-field"><span>Funcionário</span><select data-action="filter-preview-employee"><option value="">Todos</option>' + selectOptions(entities.companyEmployees, employeeFilter, employeeName) + "</select></label></div>",
      conflicts.length ? '<div class="inline-feedback inline-feedback--warning" role="alert"><strong>Conflitos encontrados</strong><ul>' + conflicts.map(function (conflict) { return "<li>" + escapeHtml(conflict) + "</li>"; }).join("") + "</ul></div>" : "",
      table,
      '<footer class="screen-actions screen-actions--sticky"><button class="button button--ghost" type="button" data-route="imports" data-action="navigate"' + (confirming ? " disabled" : "") + '>Voltar</button><div><button class="button button--danger-ghost" type="button" data-action="discard-import"' + (hasAnalysis && !confirming ? "" : " disabled") + '><span>Descartar</span></button><button class="button button--primary" type="button" data-action="save-import-start-review" data-route="review"' + (selectedCount && !confirming && !analysisSaved && !closed ? "" : " disabled") + ">" + (confirming ? "Salvando importação..." : closed ? "Competência fechada" : analysisSaved ? "Importação confirmada" : "Salvar importação e iniciar conferência") + "</button></div></footer>",
      "</section>",
    ].join("");
  }
    return Object.freeze({importAnalysisCard:importAnalysisCard,summaryItem:summaryItem,renderImports:renderImports,importPendingRecord:importPendingRecord,importPendingGroups:importPendingGroups,importIgnoredPeople:importIgnoredPeople,importPendingControls:importPendingControls,rowSuggestion:rowSuggestion,originalPunchValues:originalPunchValues,renderImportPreview:renderImportPreview});
  }
  return Object.freeze({create:create});
});
