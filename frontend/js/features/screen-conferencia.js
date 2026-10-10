(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoScreenConferencia=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var actionButton=deps.actionButton;
    var activityTimeline=deps.activityTimeline;
    var asArray=deps.asArray;
    var closedCompetenceNotice=deps.closedCompetenceNotice;
    var collection=deps.collection;
    var companyName=deps.companyName;
    var competenceBreadcrumbs=deps.competenceBreadcrumbs;
    var competenceIsClosed=deps.competenceIsClosed;
    var competenceSummaryFor=deps.competenceSummaryFor;
    var competencyAreaNavigation=deps.competencyAreaNavigation;
    var component=deps.component;
    var demoBanner=deps.demoBanner;
    var employeeName=deps.employeeName;
    var emptyState=deps.emptyState;
    var escapeHtml=deps.escapeHtml;
    var filterButton=deps.filterButton;
    var findById=deps.findById;
    var formatBalance=deps.formatBalance;
    var formatCompetence=deps.formatCompetence;
    var formatDate=deps.formatDate;
    var formatDateTime=deps.formatDateTime;
    var formatDuration=deps.formatDuration;
    var idOf=deps.idOf;
    var idsEqual=deps.idsEqual;
    var missingContextScreen=deps.missingContextScreen;
    var normalizeArgs=deps.normalizeArgs;
    var normalizeStatus=deps.normalizeStatus;
    var originalPunchValues=deps.originalPunchValues;
    var pageHeader=deps.pageHeader;
    var progressIndicator=deps.progressIndicator;
    var selectOptions=deps.selectOptions;
    var selectedEntities=deps.selectedEntities;
    var statusChip=deps.statusChip;
    var statusKey=deps.statusKey;
    var summaryItem=deps.summaryItem;
    var utils=deps.utils;
    var valueOf=deps.valueOf;
  function currentSlots(day) {
    var current = valueOf(day, ["currentInterpretation", "interpretacaoAtual"], null);
    if (!current) {
      var nestedCurrent = valueOf(day, ["current", "atual"], {}) || {};
      current = valueOf(nestedCurrent, ["slots", "horarios"], nestedCurrent);
    }
    if (!current) current = valueOf(day, ["suggestion", "suggested", "interpretacaoSugerida"], {}) || {};
    return {
      entry: valueOf(current, ["entry", "entrada"], ""),
      breakStart: valueOf(current, ["breakStart", "breakOut", "saidaIntervalo", "saida_intervalo", "saida_almoco"], ""),
      breakEnd: valueOf(current, ["breakEnd", "breakIn", "retorno", "retorno_intervalo", "retorno_almoco"], ""),
      exit: valueOf(current, ["exit", "saida"], ""),
    };
  }
  function dayDate(day) {
    return valueOf(day, ["date", "data"], "");
  }
  function dayStatus(day) {
    var current = valueOf(day, ["current", "atual"], {}) || {};
    return valueOf(current, ["situation", "status", "situacao"], valueOf(day, ["status", "situacao", "status_dia"], "conferir"));
  }
  function dayConfirmed(day) {
    var review = valueOf(day, ["review", "conferencia"], {}) || {};
    var reviewState = valueOf(review, ["state", "status"], valueOf(day, ["reviewState"], ""));
    return valueOf(day, ["confirmed", "conferido"], false) === true || ["confirmed", "conferido"].indexOf(statusKey(reviewState)) !== -1;
  }
  function dayMetric(day, keys, nestedKeys) {
    var direct = valueOf(day, keys, undefined);
    if (direct !== undefined) return direct;
    var current = valueOf(day, ["current", "atual"], {}) || {};
    return valueOf(current, nestedKeys || keys, null);
  }
  function reviewDays(context, entities) {
    var days = asArray(valueOf(context.state, ["reviewDays", "attendanceDays", "diasConferencia", "dias"], null));
    if (!days.length) days = collection(context.data, ["attendanceDays", "dias"]);
    var employeeId = entities.employee ? idOf(entities.employee) : null;
    var competenceId = entities.competence ? idOf(entities.competence) : null;
    if (!employeeId || !competenceId) return [];
    return days.filter(function (day) {
      var dayEmployeeId = valueOf(day, ["employeeId", "funcionario_id"], null);
      var dayCompetenceId = valueOf(day, ["competenceId", "competencia_id"], null);
      return idsEqual(dayEmployeeId, employeeId) && idsEqual(dayCompetenceId, competenceId);
    });
  }
  function editableTimeCell(context, day, field, value, label, readonly) {
    return '<input class="editable-time-cell" type="text" inputmode="numeric" autocomplete="off" spellcheck="false" value="' + escapeHtml(value || "") + '" placeholder="—" aria-label="' + escapeHtml(label + " de " + formatDate(dayDate(day), true)) + '" data-action="edit-time" data-day-id="' + escapeHtml(idOf(day)) + '" data-field="' + escapeHtml(field) + '"' + (readonly ? " disabled" : "") + ">";
  }
  function dayPresentation(context, day) {
    if (day.problema === true) return '<span class="day-problem"><span aria-hidden="true">⚠</span>' + escapeHtml(day.problemLabel || day.problema_rotulo || "Problema") + '</span>';
    return statusChip(context.components, day.effectiveStatus || dayStatus(day), day.effectiveStatus === "fora_vinculo" ? "Fora do vínculo" : day.effectiveStatus === "feriado" ? "Feriado" : valueOf(day, ["statusLabel"], ""));
  }
  function fallbackAttendanceTable(context, days, selectedDay, selectedIds, readonly) {
    if (!days.length) return emptyState(context.components, "Nenhum dia neste filtro", "Escolha outro filtro ou funcionário.");
    return [
      '<div class="attendance-table-wrap" tabindex="0"><table class="attendance-table" data-density="compact" aria-label="Conferência diária">',
      '<thead><tr>' + (readonly ? "" : '<th scope="col" class="select-column"><input type="checkbox" data-action="toggle-all-days" aria-label="Selecionar todos os dias visíveis"></th>') + '<th scope="col" class="attendance-table__day-heading">Dia</th><th scope="col">Atenção</th><th scope="col" class="attendance-table__time-heading">Entrada</th><th scope="col" class="attendance-table__time-heading">Saída intervalo</th><th scope="col" class="attendance-table__time-heading">Retorno</th><th scope="col" class="attendance-table__time-heading">Saída</th><th scope="col" class="attendance-table__number-heading">Jornada</th><th scope="col" class="attendance-table__number-heading">Saldo</th><th scope="col">Situação</th><th scope="col">Observação</th></tr></thead><tbody>',
      days.map(function (day) {
        var slots = currentSlots(day);
        var selected = selectedDay && idsEqual(idOf(day), idOf(selectedDay));
        var checked = selectedIds.some(function (id) { return idsEqual(id, idOf(day)); });
        var worked = dayMetric(day, ["workedMinutes", "jornadaApuradaMinutos"], ["workedMinutes", "apuradaMinutos"]);
        var balance = dayMetric(day, ["balanceMinutes", "saldoMinutos"], ["balanceMinutes", "saldoMinutos"]);
        return [
          '<tr class="attendance-row' + (selected ? " is-selected" : "") + (dayConfirmed(day) ? " is-confirmed" : "") + '" data-day-id="' + escapeHtml(idOf(day)) + '">',
          readonly ? "" : '<td class="select-column"><input type="checkbox" data-action="toggle-day-selection" data-day-id="' + escapeHtml(idOf(day)) + '" aria-label="Selecionar ' + escapeHtml(formatDate(dayDate(day), true)) + '"' + (checked ? " checked" : "") + "></td>",
          '<th scope="row"><button class="day-selector" type="button" data-action="select-day" data-day-id="' + escapeHtml(idOf(day)) + '" aria-controls="day-details-panel"' + (selected ? ' aria-current="date"' : "") + '><strong class="day-number">' + escapeHtml(valueOf(day, ["day"], String(dayDate(day)).slice(-2))) + "</strong><span>" + escapeHtml(valueOf(day, ["weekdayShort"], typeof utils.formatWeekday === "function" ? utils.formatWeekday(dayDate(day)) : "")) + "</span></button></th>",
          '<td class="problem-cell">' + (day.problema === true ? dayPresentation(context, day) : "") + "</td>",
          "<td>" + editableTimeCell(context, day, "entry", slots.entry, "Entrada", readonly) + "</td>",
          "<td>" + editableTimeCell(context, day, "breakStart", slots.breakStart, "Saída do intervalo", readonly) + "</td>",
          "<td>" + editableTimeCell(context, day, "breakEnd", slots.breakEnd, "Retorno do intervalo", readonly) + "</td>",
          "<td>" + editableTimeCell(context, day, "exit", slots.exit, "Saída", readonly) + "</td>",
          '<td class="duration-cell">' + escapeHtml(formatDuration(worked)) + "</td>",
          '<td class="balance-cell balance-cell--' + (Number(balance) > 0 ? "positive" : Number(balance) < 0 ? "negative" : "neutral") + '">' + escapeHtml(formatBalance(balance)) + "</td>",
          "<td>" + dayPresentation(context, day) + "</td>",
          '<td><input class="observation-cell" type="text" value="' + escapeHtml(valueOf(day, ["observation", "observacao"], "")) + '" aria-label="Observação de ' + escapeHtml(formatDate(dayDate(day), true)) + '" data-action="edit-observation" data-day-id="' + escapeHtml(idOf(day)) + '"' + (readonly ? " disabled" : "") + "></td>",
          "</tr>",
        ].join("");
      }).join(""),
      "</tbody></table></div>",
    ].join("");
  }
  function autosaveIndicator(context) {
    var status = valueOf(context.state, ["autosaveStatus", "saveStatus", "estadoSalvamento"], "saved");
    return component(context.components, ["AutosaveIndicator", "autosaveIndicator"], { status: status, state: status }, function () {
      var meta = {
        saving: { icon: "…", text: "Salvando..." },
        saved: { icon: "✓", text: "Alterações salvas" },
        unsaved: { icon: "!", text: "Alterações não salvas" },
        error: { icon: "×", text: "Erro ao salvar" },
      }[status] || { icon: "✓", text: "Alterações salvas" };
      return '<span class="autosave-indicator autosave-indicator--' + escapeHtml(status) + '" role="status"><span aria-hidden="true">' + meta.icon + "</span>" + meta.text + "</span>";
    });
  }
  function originalPunchesList(context, day) {
    var punches = originalPunchValues(day);
    var details = asArray(valueOf(day, ["originalPunchDetails", "detalhesBatidasOriginais"], null));
    return component(context.components, ["OriginalPunchesList", "originalPunchesList"], {
      day: day,
      punches: details.length ? details : punches,
      readonly: true,
    }, function () {
      if (!punches.length) return '<p class="muted-text">Nenhuma batida no arquivo original.</p>';
      return '<ol class="original-punches-list" aria-label="Batidas originais somente leitura">' + punches.map(function (punch, index) {
        var detail = details[index] || {};
        var line = valueOf(detail, ["sourceLine", "linhaOrigem", "line"], null);
        return '<li><time>' + escapeHtml(punch) + "</time>" + (line ? "<small>Linha " + escapeHtml(line) + "</small>" : "") + "</li>";
      }).join("") + "</ol>";
    });
  }
  function dayTimeline(context, day) {
    var history = asArray(valueOf(day, ["history", "historico"], null));
    return (day.occurrenceLabel ? '<p class="context-note"><strong>' + escapeHtml(day.occurrenceLabel) + '</strong> · Abono calculado: ' + escapeHtml(day.excusedMinutes || 0) + ' min. As batidas permanecem preservadas.</p>' : "") + activityTimeline(context, history.map(function (item) {
      return {
        title: valueOf(item, ["title", "description", "descricao"], "Atividade"),
        description: valueOf(item, ["description", "descricao"], ""),
        at: valueOf(item, ["at", "data"], null),
        actor: valueOf(item, ["actor", "autor"], ""),
      };
    }));
  }
  function contextActions(day) {
    var punches = originalPunchValues(day);
    var status = normalizeStatus(dayStatus(day));
    if (dayConfirmed(day)) {
      return [{ label: "Reabrir conferência", action: "reopen-day", variant: "button--secondary" }];
    }
    if (!punches.length) {
      return [
        { label: "Registrar falta", action: "set-day-absence" },
        { label: "Adicionar atestado", action: "set-day-certificate" },
        { label: "Registrar folga", action: "set-day-dayoff" },
        { label: "Inserir horários manualmente", action: "focus-first-time", variant: "button--secondary" },
        { label: "Marcar como sem expediente", action: "set-day-no-schedule", variant: "button--ghost" },
      ];
    }
    if (["conferir", "inconsistente"].indexOf(status) !== -1) {
      return [
        { label: "Adicionar atestado", action: "set-day-certificate" },
        { label: "Corrigir marcações", action: "focus-first-time" },
        { label: "Manter interpretação", action: "keep-interpretation" },
        { label: "Adicionar observação", action: "focus-observation", variant: "button--secondary" },
        { label: "Marcar como conferido", action: "confirm-day", variant: "button--primary" },
      ];
    }
    return [{ label: "Adicionar atestado", action: "set-day-certificate" },
      { label: "Marcar dia como conferido", action: "confirm-day", variant: "button--primary" }];
  }
  function fallbackDayDetailsPanel(context, day, readonly) {
    if (!day) return emptyState(context.components, "Selecione um dia", "Os detalhes e as batidas originais aparecerão aqui.");
    var slots = currentSlots(day);
    var source = valueOf(day, ["source", "origem"], {}) || {};
    var issues = asArray(valueOf(day, ["issues", "pendencias"], null));
    var expected = dayMetric(day, ["expectedMinutes", "jornadaPrevistaMinutos"], ["expectedMinutes", "previstaMinutos"]);
    var worked = dayMetric(day, ["workedMinutes", "jornadaApuradaMinutos"], ["workedMinutes", "apuradaMinutos"]);
    var balance = dayMetric(day, ["balanceMinutes", "saldoMinutos"], ["balanceMinutes", "saldoMinutos"]);
    return [
      '<aside id="day-details-panel" class="day-details-panel" aria-label="Detalhes do dia selecionado" data-day-id="' + escapeHtml(idOf(day)) + '">',
      '<header class="day-details-panel__header"><div><span class="eyebrow">' + escapeHtml(valueOf(day, ["weekday"], "Dia selecionado")) + '</span><h2>' + escapeHtml(formatDate(dayDate(day))) + "</h2></div>" + dayPresentation(context, day) + "</header>",
      (day.calendarNote ? '<p class="context-note">' + escapeHtml(day.calendarNote) + '</p>' : ''),
      '<section><h3>Batidas originais <span class="readonly-label">Somente leitura</span></h3>' + originalPunchesList(context, day) + "</section>",
      '<section><h3>Interpretação atual</h3><dl class="detail-grid">',
      summaryItem("Entrada", slots.entry || "—"), summaryItem("Saída intervalo", slots.breakStart || "—"), summaryItem("Retorno", slots.breakEnd || "—"), summaryItem("Saída", slots.exit || "—"),
      summaryItem("Jornada prevista", formatDuration(expected)), summaryItem("Jornada apurada", formatDuration(worked)), summaryItem("Saldo", formatBalance(balance)),
      "</dl><p class=\"difference-reason\"><strong>Motivo da diferença:</strong> " + escapeHtml(valueOf(day, ["differenceReason", "motivoDiferenca"], "Sem diferença relevante informada.") || "Sem diferença relevante informada.") + "</p></section>",
      '<section><h3>Pendências</h3>' + (issues.length ? '<ul class="issue-list">' + issues.map(function (issue) { return '<li class="issue-list__item"><span aria-hidden="true">!</span><span>' + escapeHtml(typeof issue === "string" ? issue : valueOf(issue, ["message", "mensagem"], "Revisão necessária.")) + "</span></li>"; }).join("") + "</ul>" : '<p class="muted-text">Nenhuma pendência ativa.</p>') + "</section>",
      '<section><h3>Origem</h3><dl class="source-details">' + summaryItem("Arquivo", valueOf(source, ["fileName", "arquivo", "nomeArquivo"], "—")) + summaryItem("Importado em", formatDateTime(valueOf(source, ["importedAt", "importadoEm"], null))) + summaryItem("Linhas de origem", asArray(valueOf(source, ["sourceLines", "linhasOrigem"], [])).join(", ") || "—") + '</dl><div class="button-row"><button class="button button--secondary" type="button" data-action="open-original-file" data-file-id="' + escapeHtml(valueOf(source, ["fileId"], "")) + '">Ver arquivo original</button><button class="button button--ghost" type="button" data-action="open-source-region">Ver região de origem</button></div></section>',
      '<section><h3>Histórico do dia</h3>' + dayTimeline(context, day) + "</section>",
      '<section class="context-actions"><h3>Ações</h3>' + (readonly
        ? '<p class="muted-text" role="note">Competência fechada: este dia está disponível somente para consulta.</p>'
        : '<div class="context-actions__buttons">' + contextActions(day).map(function (action) {
          return actionButton({ label: action.label, action: action.action, variant: action.variant || "button--secondary", attributes: ' data-day-id="' + escapeHtml(idOf(day)) + '"' });
        }).join("") + "</div>") + "</section>",
      "</aside>",
    ].join("");
  }
  function dayForComponents(day) {
    if (!day) return null;
    var source = valueOf(day, ["source", "origem"], {}) || {};
    var original = valueOf(day, ["original", "dadosOriginais"], {}) || {};
    var details = asArray(valueOf(day, ["originalPunchDetails", "detalhesBatidasOriginais"], []));
    var punches = details.length ? details.map(function (punch) {
      return Object.assign({}, punch, {
        value: valueOf(punch, ["value", "time", "horario"], ""),
        line: valueOf(punch, ["line", "sourceLine", "linhaOrigem"], null),
        page: valueOf(punch, ["page", "pagina"], null),
        region: valueOf(punch, ["region", "regiao"], null),
      });
    }) : originalPunchValues(day);
    var current = Object.assign({}, valueOf(day, ["current", "currentInterpretation", "interpretacaoAtual"], {}) || {}, currentSlots(day), {
      situation: dayStatus(day),
      observation: valueOf(day, ["observation", "observacao"], ""),
      expectedMinutes: dayMetric(day, ["expectedMinutes", "jornadaPrevistaMinutos"], ["expectedMinutes", "previstaMinutos"]),
      workedMinutes: dayMetric(day, ["workedMinutes", "jornadaApuradaMinutos"], ["workedMinutes", "apuradaMinutos"]),
      balanceMinutes: dayMetric(day, ["balanceMinutes", "saldoMinutos"], ["balanceMinutes", "saldoMinutos"]),
      differenceReason: valueOf(day, ["differenceReason", "motivoDiferenca"], ""),
    });
    return Object.assign({}, day, {
      current: current,
      original: Object.assign({}, original, source, {
        punches: punches,
        fileId: valueOf(source, ["fileId"], valueOf(original, ["fileId"], null)),
        fileName: valueOf(source, ["fileName", "arquivo", "nomeArquivo"], valueOf(original, ["fileName"], null)),
        importedAt: valueOf(source, ["importedAt", "importadoEm"], valueOf(original, ["importedAt"], null)),
        lines: asArray(valueOf(source, ["sourceLines", "linhasOrigem"], valueOf(original, ["lines"], []))),
        region: valueOf(source, ["region", "regiao"], valueOf(original, ["region"], null)) || (valueOf(source, ["canOpenRegion"], false) ? "Região de origem disponível" : null),
      }),
    });
  }
  function employeeSearchField(context) {
    return '<label class="employee-search"><span class="sr-only">Buscar funcionário por nome ou ID, de exibição ou original</span><input type="search" data-action="search-employees" placeholder="Buscar nome ou ID (OnPonto ou ponto)" value="' + escapeHtml(context.state.employeeSearch || "") + '"></label>';
  }
  function renderReview(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Conferência", "Selecione uma empresa e uma competência antes de abrir a conferência.", true);
    var closed = competenceIsClosed(entities.competence);
    var summary = competenceSummaryFor(context, entities.competence);
    var problemRows = summary && summary.rows || [];
    var nextProblem = utils.nextProblemEmployee(entities.companyEmployees, problemRows, entities.employee && idOf(entities.employee));
    var matchingEmployees = entities.companyEmployees.filter(function (employee) { return utils.employeeMatches(employee, context.state.employeeSearch); });
    function employeeOption(employee) {
      var row = problemRows.find(function (row) { return idsEqual(row.employeeId, idOf(employee)); });
      var count = row && row.pending;
      return employeeName(employee) + " · " + valueOf(employee, ["codigo_exibicao", "code", "codigo"], "—") + " · " +
        (count == null ? "problemas: —" : count + (Number(count) === 1 ? " problema" : " problemas"));
    }
    var allDays = reviewDays(context, entities);
    var filter = statusKey(valueOf(context.state, ["reviewFilter", "attendanceFilter", "filtroConferencia"], "all"));
    filter = {
      todos: "all",
      todos_os_dias: "all",
      pendencias: "pending",
      nao_conferidos: "unconfirmed",
      ausencias: "absences",
    }[filter] || filter;
    var days = allDays.filter(function (day) {
      var normalized = normalizeStatus(dayStatus(day));
      var issues = asArray(valueOf(day, ["issues", "pendencias"], []));
      if (filter === "pending") return day.problema !== undefined ? day.problema : day.pendingCalculation === true || issues.some(function(issue){return !issue.resolved && issue.type !== "review" && issue.type !== "manual_change";});
      if (filter === "unconfirmed") return !dayConfirmed(day);
      if (filter === "absences") return ["falta", "falta_justificada", "atestado", "folga", "afastamento"].indexOf(normalized) !== -1;
      return true;
    });
    var selectedDayId = valueOf(context.state, ["selectedDayId", "dayId", "diaSelecionadoId"], null);
    var selectedDay = findById(allDays, selectedDayId) || days[0] || allDays[0] || null;
    var selection = closed ? [] : asArray(valueOf(context.state, ["selectedDayIds", "bulkSelection", "diasSelecionados"], []));
    var progressItems = collection(context.data, ["employeeProgress", "progressoFuncionarios"]);
    var employeeProgress = progressItems.find(function (item) { return entities.employee && idsEqual(valueOf(item, ["employeeId", "funcionario_id"], null), idOf(entities.employee)); }) || {};
    var position = valueOf(employeeProgress, ["position", "posicao"], Math.max(1, entities.companyEmployees.indexOf(entities.employee) + 1));
    var totalEmployees = valueOf(employeeProgress, ["totalEmployees", "totalFuncionarios"], entities.companyEmployees.length);
    var confirmedDays = valueOf(employeeProgress, ["confirmedDayCount", "diasConferidos"], allDays.filter(dayConfirmed).length);
    var eligibleDays = valueOf(employeeProgress, ["eligibleDayCount", "totalDias"], allDays.length);
    var reviewLoading = valueOf(context.state, ["reviewLoading"], false) === true;
    var table = reviewLoading && !allDays.length ? '<div class="review-loading" role="status"><strong>Carregando marcações...</strong><span>Buscando os dados persistidos desta competência.</span></div>' : component(context.components, ["AttendanceTable", "attendanceTable"], {
      days: days,
      rows: days,
      selectedDayId: selectedDay ? idOf(selectedDay) : null,
      selectedIds: selection,
      bulkSelection: selection,
      selectable: !closed,
      readonly: closed,
    }, function () { return fallbackAttendanceTable(context, days, selectedDay, selection, closed); });
    var componentDay = dayForComponents(selectedDay);
    var panel = component(context.components, ["DayDetailsPanel", "dayDetailsPanel"], {
      day: componentDay,
      selectedDay: componentDay,
      readonly: closed,
      file: componentDay ? {
        id: valueOf(componentDay.original, ["fileId"], null),
        name: valueOf(componentDay.original, ["fileName"], null),
        importedAt: valueOf(componentDay.original, ["importedAt"], null),
      } : null,
    }, function () { return fallbackDayDetailsPanel(context, selectedDay, closed); });

    return [
      '<section class="screen screen--review" data-screen="review">', demoBanner(),
      pageHeader(context.components, {
        title: "Conferência",
        subtitle: companyName(entities.company) + " · " + formatCompetence(entities.competence),
        breadcrumbs: competenceBreadcrumbs(entities, "Conferência"),
        actions: [{ label: closed ? "Somente leitura" : "Salvar agora", action: "save-now", variant: "primary", disabled: closed }],
      }),
      competencyAreaNavigation("review"),
      closedCompetenceNotice(entities.competence),
      '<section class="review-toolbar work-card">',
      employeeSearchField(context),
      '<button class="button button--secondary next-problem" type="button" data-action="next-problem-employee"' + (!nextProblem ? ' disabled' : '') + '>' + (nextProblem ? 'Próximo com problema →' : 'Sem próximo com problema') + '</button>',

      '<div class="employee-navigation"><button class="icon-button" type="button" data-action="previous-employee" aria-label="Funcionário anterior" title="Funcionário anterior (Alt + ↑)">←</button><label><span class="sr-only">Funcionário</span><select data-action="select-review-employee">' + (context.state.employeeSearch ? '<option value="">Selecione um resultado (' + matchingEmployees.length + ')</option>' : "") + selectOptions(matchingEmployees, entities.employee ? idOf(entities.employee) : "", employeeOption) + '</select></label><button class="icon-button" type="button" data-action="next-employee" aria-label="Próximo funcionário" title="Próximo funcionário (Alt + ↓)">→</button><span class="position-label">' + escapeHtml(position) + " de " + escapeHtml(totalEmployees) + " funcionários</span></div>",
      '<button class="button button--secondary" type="button" data-action="open-employee-timesheet" data-employee-id="' + escapeHtml(entities.employee ? idOf(entities.employee) : "") + '"' + (!entities.employee || context.state.apiMode !== "online" ? " disabled" : "") + '>Emitir espelho</button>',
      '<details class="employee-origin"><summary>Identificação no ponto</summary><p>Nome original: ' + escapeHtml(entities.employee && entities.employee.nome || "—") + '<br>Código original: ' + escapeHtml(entities.employee && entities.employee.codigo || "—") + '</p></details>',
      '<div class="review-progress">' + progressIndicator(context.components, confirmedDays, eligibleDays, "Progresso") + (closed ? '<span class="autosave-indicator" role="status">Somente leitura</span>' : autosaveIndicator(context)) + "</div>",
      '<div class="filter-group review-filters" role="group" aria-label="Filtrar dias">' + filterButton("Todos os dias", "all", filter, "review") + filterButton("Problemas", "pending", filter, "review") + filterButton("Não conferidos", "unconfirmed", filter, "review") + filterButton("Ausências", "absences", filter, "review") + "</div>",
      "</section>",
      '<section class="bulk-actions' + (selection.length ? " is-active" : "") + '" aria-label="Ações em massa" aria-live="polite"><strong>' + (closed ? "Ações indisponíveis enquanto a competência estiver fechada" : selection.length + " registro" + (selection.length === 1 ? "" : "s") + " selecionado" + (selection.length === 1 ? "" : "s")) + '</strong><div><button class="button button--secondary" type="button" data-action="bulk-confirm" data-bulk-action="confirm"' + (closed || !selection.length ? " disabled" : "") + '>Marcar como conferidos</button><button class="button button--secondary" type="button" data-action="bulk-set-status" data-bulk-action="set_status"' + (closed || !selection.length ? " disabled" : "") + '>Definir situação</button><button class="button button--secondary" type="button" data-action="bulk-add-observation" data-bulk-action="add_observation"' + (closed || !selection.length ? " disabled" : "") + ">Adicionar observação</button></div><small>As batidas originais nunca serão alteradas.</small></section>",
      '<div class="review-layout"><section class="review-grid" aria-label="Tabela de conferência">' + table + '</section><div class="review-context">' + panel + "</div></div>",
      "</section>",
    ].join("");
  }
    return Object.freeze({currentSlots:currentSlots,dayDate:dayDate,dayStatus:dayStatus,dayConfirmed:dayConfirmed,dayMetric:dayMetric,reviewDays:reviewDays,editableTimeCell:editableTimeCell,dayPresentation:dayPresentation,fallbackAttendanceTable:fallbackAttendanceTable,autosaveIndicator:autosaveIndicator,originalPunchesList:originalPunchesList,dayTimeline:dayTimeline,contextActions:contextActions,fallbackDayDetailsPanel:fallbackDayDetailsPanel,dayForComponents:dayForComponents,employeeSearchField:employeeSearchField,renderReview:renderReview});
  }
  return Object.freeze({create:create});
});
