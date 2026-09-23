(function (root) {
  "use strict";

  var Utils = root.OnPontoUtils;
  if (!Utils || typeof Utils.escapeHtml !== "function") {
    throw new Error("OnPontoComponents requer OnPontoUtils carregado anteriormente.");
  }

  var escapeHtml = Utils.escapeHtml;
  var hasOwn = Object.prototype.hasOwnProperty;

  function array(value) {
    return Array.isArray(value) ? value : value == null ? [] : [value];
  }

  function valueOf() {
    for (var index = 0; index < arguments.length; index += 1) {
      if (arguments[index] !== undefined && arguments[index] !== null) return arguments[index];
    }
    return null;
  }

  function text(value, fallback) {
    var resolved = valueOf(value, fallback, "");
    return escapeHtml(resolved);
  }

  function token(value, fallback) {
    var normalized = Utils.statusKey(value || fallback || "item");
    return normalized || fallback || "item";
  }

  function sameId(left, right) {
    return left != null && right != null && String(left) === String(right);
  }

  function containsId(collection, id) {
    if (collection instanceof Set) return collection.has(id) || collection.has(String(id));
    return array(collection).some(function (candidate) { return sameId(candidate, id); });
  }

  function attr(name, value) {
    return value === undefined || value === null || value === "" ? "" : " " + name + "=\"" + text(value) + "\"";
  }

  function boolAttr(name, enabled) {
    return enabled ? " " + name : "";
  }

  function srOnly(content) {
    return '<span class="sr-only">' + text(content) + "</span>";
  }

  var ICONS = {
    dashboard: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    upload: '<path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
    folder: '<path d="M3 6a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    check_square: '<path d="M9 11l3 3 7-7"/><rect x="3" y="3" width="18" height="18" rx="2"/>',
    report: '<path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5M9 13h6M9 17h6"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.09A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3v-4h.09A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.09A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.16.36.37.7.6 1 .28.32.66.5 1.1.5h.1v4h-.09A1.7 1.7 0 0 0 19.4 15Z"/>',
    panel_left: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    check_circle: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    alert: '<path d="M10.3 3.6 2.4 18a2 2 0 0 0 1.75 3h15.7a2 2 0 0 0 1.75-3L13.7 3.6a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
    x_circle: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    minus_circle: '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    calendar_off: '<path d="M3 10h14M8 3v3M16 3v2M4 4l16 16M6 5H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 1.7-.94"/>',
    heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5 1.1-1.1a5.5 5.5 0 0 0-.1-7.8Z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42"/>',
    moon: '<path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2Z"/>',
    briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2"/>',
    file: '<path d="M6 2h9l4 4v16H6z"/><path d="M14 2v5h5"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
    chevron_left: '<path d="m15 18-6-6 6-6"/>',
    chevron_right: '<path d="m9 18 6-6-6-6"/>',
    chevron_down: '<path d="m6 9 6 6 6-6"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 10v7M14 10v7"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    note: '<path d="M4 3h16v18H4zM8 8h8M8 12h8M8 16h5"/>',
    arrow_right: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  };

  function Icon(name, options) {
    var settings = options || {};
    var key = token(name, "info");
    var markup = ICONS[key] || ICONS.info;
    var label = settings.label;
    var accessibility = label
      ? ' role="img" aria-label="' + text(label) + '"'
      : ' aria-hidden="true" focusable="false"';
    return '<svg class="icon icon-' + text(key) + (settings.className ? " " + text(settings.className) : "") + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"' + accessibility + ">" + markup + "</svg>";
  }

  var STATUS_ALIASES = {
    conferir: "needs_review", pendente: "needs_review", pendente_conferencia: "needs_review", pending: "needs_review", pending_review: "needs_review", revisar: "needs_review", review: "needs_review",
    normal: "normal",
    inconsistente: "inconsistent", inconsistencia: "inconsistent", inconsistent: "inconsistent", error: "inconsistent", erro: "inconsistent",
    falta: "absence", ausente: "absence", absence: "absence", absent: "absence",
    atestado: "medical_leave", medical_leave: "medical_leave", sick_note: "medical_leave",
    folga: "day_off", day_off: "day_off",
    feriado: "holiday", holiday: "holiday",
    domingo: "sunday", sunday: "sunday",
    sem_expediente: "off_schedule", no_schedule: "off_schedule", off_schedule: "off_schedule",
    trabalho_externo: "external_work", external_work: "external_work",
    afastamento: "leave", leave: "leave",
    conferido: "confirmed", confirmed: "confirmed", concluido: "confirmed", done: "confirmed",
    salvando: "saving", saving: "saving",
    salvo: "saved", saved: "saved", alteracoes_salvas: "saved",
    nao_salvo: "unsaved", unsaved: "unsaved", pending_save: "unsaved",
    erro_ao_salvar: "save_error", save_error: "save_error",
    aberta: "open", aberto: "open", open: "open",
    em_conferencia: "in_review", in_review: "in_review",
    conferida: "ready", pronta: "ready", ready: "ready",
    fechada: "closed", fechado: "closed", closed: "closed",
    atencao: "warning", warning: "warning",
  };

  var STATUS_META = {
    normal: { label: "Normal", tone: "success", icon: "check_circle" },
    needs_review: { label: "Conferir", tone: "warning", icon: "alert" },
    inconsistent: { label: "Inconsistente", tone: "danger", icon: "x_circle" },
    absence: { label: "Falta", tone: "warning", icon: "minus_circle" },
    medical_leave: { label: "Atestado", tone: "neutral", icon: "heart" },
    day_off: { label: "Folga", tone: "neutral", icon: "calendar" },
    holiday: { label: "Feriado", tone: "neutral", icon: "calendar" },
    sunday: { label: "Domingo", tone: "neutral", icon: "sun" },
    fora_vinculo: { label: "Fora do vínculo", tone: "neutral", icon: "calendar_off" },
    off_schedule: { label: "Sem expediente", tone: "neutral", icon: "calendar_off" },
    external_work: { label: "Trabalho externo", tone: "neutral", icon: "briefcase" },
    leave: { label: "Afastamento", tone: "neutral", icon: "clock" },
    confirmed: { label: "Conferido", tone: "success", icon: "check_circle" },
    saving: { label: "Salvando...", tone: "neutral", icon: "clock" },
    saved: { label: "Alterações salvas", tone: "success", icon: "check" },
    unsaved: { label: "Alterações não salvas", tone: "warning", icon: "alert" },
    save_error: { label: "Erro ao salvar", tone: "danger", icon: "x_circle" },
    open: { label: "Aberta", tone: "neutral", icon: "folder" },
    in_review: { label: "Em conferência", tone: "warning", icon: "alert" },
    ready: { label: "Conferida", tone: "success", icon: "check_circle" },
    closed: { label: "Fechada", tone: "success", icon: "check_circle" },
    warning: { label: "Atenção", tone: "warning", icon: "alert" },
    unknown: { label: "Não informado", tone: "neutral", icon: "info" },
  };

  function resolveStatus(value) {
    var key = token(value, "unknown");
    var canonical = STATUS_ALIASES[key] || key;
    return { key: canonical, meta: STATUS_META[canonical] || { label: value || "Não informado", tone: "neutral", icon: "info" } };
  }

  function StatusChip(input, overrides) {
    var settings = typeof input === "object" && input !== null ? input : { status: input };
    if (overrides) settings = Object.assign({}, settings, overrides);
    var resolved = resolveStatus(valueOf(settings.status, settings.value, settings.situation, settings.situacao));
    var label = valueOf(settings.label, resolved.meta.label);
    var tone = token(valueOf(settings.tone, resolved.meta.tone), "neutral");
    var compact = settings.compact ? " status-chip-compact" : "";
    var requestedIcon = token(settings.icon, "");
    var icon = hasOwn.call(ICONS, requestedIcon) ? requestedIcon : resolved.meta.icon;
    return '<span class="status-chip status-' + text(resolved.key) + " tone-" + text(tone) + " status-chip--" + text(resolved.key) + " status-chip--" + text(tone) + compact + '" data-status="' + text(resolved.key) + '">' +
      Icon(icon) + '<span>' + text(label) + "</span></span>";
  }

  function actionButton(action, label, options) {
    var settings = options || {};
    var requestedVariant = String(settings.variant || "secondary");
    var variant = requestedVariant.replace(/^button--?/, "").replace(/_/g, "-");
    var classes = "button button--" + token(variant).replace(/_/g, "-") + " button-" + token(variant).replace(/_/g, "-");
    if (settings.className) classes += " " + settings.className;
    var icon = settings.icon ? Icon(settings.icon) : "";
    return '<button type="button" class="' + text(classes) + '" data-action="' + text(action) + '"' +
      attr("data-id", settings.id) + attr("data-day-id", settings.dayId) + attr("data-file-id", settings.fileId) + attr("data-value", settings.value) + attr("data-route", settings.route) + attr("aria-label", settings.ariaLabel) +
      boolAttr("disabled", settings.disabled) + (settings.pressed == null ? "" : ' aria-pressed="' + (settings.pressed ? "true" : "false") + '"') + ">" +
      icon + '<span class="button-label">' + text(label) + "</span></button>";
  }

  var DEFAULT_PRIMARY_NAV = [
    { id: "dashboard", label: "Painel", icon: "dashboard" },
    { id: "imports", label: "Importações", icon: "upload" },
    { id: "competencies", label: "Competências", icon: "folder" },
    { id: "conference", label: "Conferência", icon: "check_square" },
    { id: "reports", label: "Relatórios", icon: "report" },
  ];

  var DEFAULT_SECONDARY_NAV = [
    { id: "registrations", label: "Cadastros", icon: "users" },
    { id: "settings", label: "Configurações", icon: "settings" },
  ];

  function navItem(item, active, collapsed) {
    var id = valueOf(item.id, item.view, item.route);
    var isActive = sameId(id, active);
    return '<li class="sidebar-item"><button type="button" class="sidebar-link' + (isActive ? " is-active" : "") + '" data-action="navigate" data-view="' + text(id) + '" data-route="' + text(id) + '"' +
      (isActive ? ' aria-current="page"' : "") + attr("title", collapsed ? item.label : null) + boolAttr("disabled", item.disabled) + ">" +
      Icon(item.icon || "folder") + '<span class="sidebar-link-label">' + text(item.label) + "</span>" +
      (item.badge == null ? "" : '<span class="sidebar-badge" aria-label="' + text(item.badge + " pendências") + '">' + text(item.badge) + "</span>") +
      "</button></li>";
  }

  function Sidebar(props) {
    var settings = props || {};
    var collapsed = Boolean(valueOf(settings.collapsed, settings.isCollapsed, false));
    var active = valueOf(settings.active, settings.activeView, settings.activeRoute, settings.route);
    var primary = settings.primaryItems || DEFAULT_PRIMARY_NAV;
    var secondary = settings.secondaryItems || DEFAULT_SECONDARY_NAV;
    var secondaryMarkup = secondary.length ? '<div class="sidebar-secondary"><span class="sidebar-section-label">' + text(settings.secondaryLabel || "Administração") + '</span><nav aria-label="Navegação secundária"><ul>' + secondary.map(function (item) { return navItem(item, active, collapsed); }).join("") + "</ul></nav></div>" : "";
    return '<div class="op-sidebar' + (collapsed ? " is-collapsed" : "") + '" data-component="sidebar">' +
      '<div class="sidebar-brand"><img class="sidebar-brand-logo" src="brand/on-ponto-logo-white.svg" alt="On Ponto" width="190" height="47"><img class="sidebar-brand-symbol" src="brand/on-ponto-symbol-white.svg" alt="On Ponto" width="36" height="36"></div>' +
      '<nav class="sidebar-nav" aria-label="Navegação principal"><ul>' + primary.map(function (item) { return navItem(item, active, collapsed); }).join("") + "</ul></nav>" +
      secondaryMarkup +
      '<button type="button" class="sidebar-collapse" data-action="toggle-sidebar" aria-expanded="' + (collapsed ? "false" : "true") + '" aria-label="' + text(collapsed ? "Expandir menu" : "Recolher menu") + '">' +
      Icon(collapsed ? "chevron_right" : "chevron_left") + '<span class="sidebar-link-label">' + text(collapsed ? "Expandir" : "Recolher") + "</span></button></div>";
  }

  function PageHeader(props) {
    var settings = props || {};
    var actions = array(settings.actions).map(function (action) {
      return actionButton(action.action || action.id || (action.route ? "navigate" : "action"), action.label, action);
    }).join("");
    var eyebrow = settings.eyebrow ? '<p class="page-eyebrow">' + text(settings.eyebrow) + "</p>" : "";
    var subtitle = settings.subtitle ? '<p class="page-subtitle">' + text(settings.subtitle) + "</p>" : "";
    var breadcrumbs = array(settings.breadcrumbs).length ? '<nav class="breadcrumbs" aria-label="Navegação estrutural">' + array(settings.breadcrumbs).map(function (crumb, index) {
      var separator = index ? '<span aria-hidden="true">›</span>' : "";
      if (crumb.route) return separator + '<button type="button" data-action="navigate" data-route="' + text(crumb.route) + '">' + text(crumb.label) + "</button>";
      return separator + '<span aria-current="page">' + text(crumb.label) + "</span>";
    }).join("") + "</nav>" : "";
    var meta = settings.meta ? '<div class="page-header-meta">' + array(settings.meta).map(function (item) {
      return '<span class="page-meta-item">' + (item.icon ? Icon(item.icon) : "") + text(valueOf(item.label, item)) + "</span>";
    }).join("") + "</div>" : "";
    return '<header class="op-page-header" data-component="page-header"><div class="page-header-copy op-page-header__copy">' + breadcrumbs + eyebrow + '<div class="page-title-row"><h1 id="' + text(settings.headingId || "page-title") + '">' + text(settings.title) + "</h1>" + (settings.titleStatus ? StatusChip(settings.titleStatus) : "") + '</div>' + subtitle + meta + "</div>" +
      (actions ? '<div class="page-header-actions op-page-header__actions">' + actions + "</div>" : "") + "</header>";
  }

  function ProgressIndicator(props) {
    var settings = props || {};
    var current = Number(valueOf(settings.current, settings.completed));
    var total = Number(settings.total);
    var rawValue = Number(settings.value);
    var percentage = Number.isFinite(current) && Number.isFinite(total) && total > 0 ? current / total * 100 : rawValue;
    if (Number.isFinite(percentage) && Math.abs(percentage) <= 1) percentage *= 100;
    if (!Number.isFinite(percentage)) percentage = 0;
    percentage = Math.max(0, Math.min(100, percentage));
    var valueLabel = settings.valueLabel || (Number.isFinite(current) && Number.isFinite(total) ? current + " de " + total : Utils.formatPercentage(percentage, { fraction: false }));
    var label = settings.label || "Progresso";
    return '<div class="progress-indicator' + (settings.compact ? " is-compact" : "") + '" data-component="progress-indicator">' +
      '<div class="progress-copy progress-indicator__meta"><span class="progress-label">' + text(label) + '</span><span class="progress-value">' + text(valueLabel) + "</span></div>" +
      '<div class="progress-track progress-indicator__track" role="progressbar" aria-label="' + text(label) + '" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + text(Math.round(percentage)) + '" aria-valuetext="' + text(valueLabel) + '"><span class="progress-fill" style="width:' + text(percentage.toFixed(2)) + '%"></span></div></div>';
  }

  function getSlots(day) {
    var current = day && valueOf(day.current, day.interpretation, day.interpretacaoAtual, day.interpretacao_atual) || {};
    var slots = valueOf(current.slots, current.times, current.horarios, day && day.slots, day && day.horarios) || current;
    return {
      entry: valueOf(slots.entry, slots.entrada, ""),
      breakOut: valueOf(slots.breakOut, slots.breakStart, slots.saidaIntervalo, slots.saida_intervalo, slots.intervalo, ""),
      breakIn: valueOf(slots.breakIn, slots.breakEnd, slots.retorno, slots.retornoIntervalo, slots.retorno_intervalo, ""),
      exit: valueOf(slots.exit, slots.saida, slots.saidaFinal, slots.saida_final, ""),
    };
  }

  function EditableTimeCell(props) {
    var settings = props || {};
    var dayId = valueOf(settings.dayId, settings.rowId, settings.id);
    var field = settings.field || "entry";
    var editAction = settings.action || "edit-time";
    var fieldLabel = settings.label || field;
    var value = valueOf(settings.value, "");
    var cellId = "time-" + token(dayId, "day") + "-" + token(field, "field");
    var messageId = cellId + "-message";
    var classes = "editable-time-cell";
    if (settings.active) classes += " is-active";
    if (settings.editing) classes += " is-editing";
    if (settings.invalid || settings.error) classes += " is-invalid";
    if (settings.warning) classes += " has-warning";
    if (settings.disabled || settings.readonly) classes += " is-disabled";
    var display = value === "" ? '<span class="empty-value" aria-hidden="true">—</span>' + srOnly("Sem horário") : text(value);
    var message = settings.error || settings.warning;
    var input = '<input class="time-cell-input" type="text" inputmode="numeric" autocomplete="off" spellcheck="false" value="' + text(value) + '" data-action="' + text(editAction) + '" data-day-id="' + text(dayId) + '" data-field="' + text(field) + '" aria-label="' + text(fieldLabel) + '"' +
      (message ? ' aria-describedby="' + text(messageId) + '"' : "") + (settings.invalid || settings.error ? ' aria-invalid="true"' : "") + boolAttr("disabled", settings.disabled) + boolAttr("readonly", settings.readonly) + ">";
    return '<td id="' + text(cellId) + '" class="' + text(classes) + '" tabindex="' + text(settings.editing ? -1 : valueOf(settings.tabIndex, -1)) + '" data-action="' + text(editAction) + '" data-day-id="' + text(dayId) + '" data-field="' + text(field) + '" data-value="' + text(value) + '" aria-label="' + text(fieldLabel + ": " + (value || "sem horário")) + '"' +
      (settings.disabled || settings.readonly ? ' aria-readonly="true"' : ' aria-readonly="false"') + (settings.invalid || settings.error ? ' aria-invalid="true"' : "") + ">" +
      (settings.editing ? input : '<span class="time-cell-value">' + display + "</span>") +
      (message ? '<span id="' + text(messageId) + '" class="cell-message' + (settings.error ? " is-error" : " is-warning") + '">' + text(message) + "</span>" : "") + "</td>";
  }

  function dayCurrent(day) {
    return day && valueOf(day.current, day.interpretation, day.interpretacaoAtual, day.interpretacao_atual) || {};
  }

  function dayStatus(day) {
    var current = dayCurrent(day);
    return valueOf(current.situation, current.situacao, current.status, day && day.situation, day && day.situacao, day && day.status, "needs_review");
  }

  function reviewState(day) {
    var review = day && valueOf(day.review, day.conference, day.conferencia) || {};
    return valueOf(review.state, review.status, day && day.reviewState, day && day.conferido === true ? "confirmed" : null, "pending");
  }

  function metricMinutes(current, aliases, formattedAliases) {
    var numeric = null;
    aliases.some(function (alias) {
      if (current[alias] !== undefined && current[alias] !== null && Number.isFinite(Number(current[alias]))) {
        numeric = Number(current[alias]);
        return true;
      }
      return false;
    });
    if (numeric !== null) return numeric;
    for (var index = 0; index < formattedAliases.length; index += 1) {
      if (current[formattedAliases[index]] !== undefined && current[formattedAliases[index]] !== null) return current[formattedAliases[index]];
    }
    return null;
  }

  function formatMinutesOrValue(value, balance) {
    if (value == null || value === "") return "—";
    return typeof value === "number" ? (balance ? Utils.formatBalance(value) : Utils.formatDuration(value)) : String(value);
  }

  function AttendanceTable(props) {
    var settings = props || {};
    var readonly = settings.readonly === true || settings.disabled === true;
    var selectable = settings.selectable !== false && !readonly;
    var days = array(valueOf(settings.days, settings.rows, settings.records));
    var selectedIds = valueOf(settings.selectedIds, settings.bulkSelection, []);
    var selectedDayId = valueOf(settings.selectedDayId, settings.activeDayId);
    var activeCell = settings.activeCell || {};
    var editingCell = settings.editingCell || {};
    var fields = [
      { key: "entry", slot: "entry", label: "Entrada" },
      { key: "breakStart", slot: "breakOut", label: "Saída intervalo" },
      { key: "breakEnd", slot: "breakIn", label: "Retorno" },
      { key: "exit", slot: "exit", label: "Saída" },
    ];
    var rows = days.map(function (day, rowIndex) {
      var dayId = valueOf(day.id, day.dayId, day.data);
      var current = dayCurrent(day);
      var metricSource = Object.assign({}, day, current);
      var slots = getSlots(day);
      var isSelected = sameId(dayId, selectedDayId);
      var isBulkSelected = containsId(selectedIds, dayId);
      var confirmed = resolveStatus(reviewState(day)).key === "confirmed";
      var worked = metricMinutes(metricSource, ["workedMinutes", "worked_minutes", "jornadaApuradaMinutos", "jornadaMinutos", "jornada_minutos"], ["worked", "jornada"]);
      var balance = metricMinutes(metricSource, ["balanceMinutes", "balance_minutes", "saldoMinutos", "saldo_minutos"], ["balance", "saldo"]);
      var date = valueOf(day.date, day.data);
      var editableCells = fields.map(function (column, columnIndex) {
        var active = sameId(activeCell.dayId, dayId) && (activeCell.field === column.key || activeCell.field === column.slot);
        if (!activeCell.dayId && rowIndex === 0 && columnIndex === 0) active = true;
        var editing = sameId(editingCell.dayId, dayId) && (editingCell.field === column.key || editingCell.field === column.slot);
        var validation = day.validation && (day.validation[column.key] || day.validation[column.slot]) || {};
        return EditableTimeCell({
          dayId: dayId,
          field: column.key,
          label: column.label + " de " + Utils.formatDate(date),
          value: slots[column.slot],
          active: active,
          editing: editing,
          tabIndex: readonly ? -1 : active ? 0 : -1,
          disabled: readonly || (confirmed && settings.lockConfirmed !== false),
          invalid: validation.valid === false,
          error: validation.error,
          warning: validation.warning,
        });
      }).join("");
      var note = valueOf(current.observation, current.observacao, day.observation, day.observacao, "");
      return '<tr class="attendance-row' + (isSelected ? " is-selected" : "") + (confirmed ? " is-confirmed" : "") + '" data-day-id="' + text(dayId) + '">' +
        (selectable ? '<td class="selection-cell"><input type="checkbox" data-action="toggle-day-selection" data-day-id="' + text(dayId) + '" aria-label="Incluir ' + text(Utils.formatDate(date)) + ' nas ações em massa"' + boolAttr("checked", isBulkSelected) + "></td>" : "") +
        '<th scope="row" class="day-cell"><button type="button" class="day-select-button" data-action="select-day" data-day-id="' + text(dayId) + '" aria-controls="day-details-panel" aria-label="Ver detalhes de ' + text(Utils.formatDate(date)) + (confirmed ? ", dia conferido" : "") + '"' + (isSelected ? ' aria-current="date"' : "") + '><span class="day-number">' + text(Utils.formatDayLabel(date)) + "</span>" + (confirmed ? Icon("check_circle", { label: "Dia conferido" }) : "") + "</button></th>" +
        editableCells + '<td class="journey-cell">' + text(formatMinutesOrValue(worked, false)) + '</td><td class="balance-cell' + (Number(balance) > 0 ? " is-positive" : Number(balance) < 0 ? " is-negative" : "") + '">' + text(formatMinutesOrValue(balance, true)) + "</td>" +
        '<td class="situation-cell"><button type="button" class="chip-button" data-action="choose-situation" data-day-id="' + text(dayId) + '" aria-label="Situação de ' + text(Utils.formatDate(date)) + ": " + text(resolveStatus(day.effectiveStatus || dayStatus(day)).meta.label) + (readonly ? '" disabled' : '. Alterar situação"') + ">" + StatusChip(day.effectiveStatus || dayStatus(day), { compact: true }) + "</button>" + (day.occurrenceLabel ? '<small class="occurrence-type">' + text(day.occurrenceLabel) + "</small>" : "") + (day.calendarNote ? '<small class="calendar-day-note">' + text(day.calendarNote) + "</small>" : "") + "</td>" +
        '<td class="observation-cell"><button type="button" class="observation-button' + (note ? " has-content" : "") + '" data-action="edit-observation" data-day-id="' + text(dayId) + '" aria-label="' + text((readonly ? "Observação de " : note ? "Editar observação de " : "Adicionar observação em ") + Utils.formatDate(date) + (note ? ": " + note : "")) + '"' + boolAttr("disabled", readonly) + ">" + (note ? Icon("note") + '<span class="observation-text">' + text(note) + "</span>" : '<span class="empty-value">—</span>') + "</button></td></tr>";
    }).join("");
    var columnCount = selectable ? 10 : 9;
    var selectedCount = days.filter(function (day) { return containsId(selectedIds, valueOf(day.id, day.dayId, day.data)); }).length;
    var allSelected = days.length > 0 && selectedCount === days.length;
    var mixed = selectedCount > 0 && !allSelected;
    var selectionHead = selectable ? '<th scope="col" class="selection-cell"><input type="checkbox" data-action="toggle-all-days" aria-label="Selecionar todos os dias visíveis"' + boolAttr("checked", allSelected) + (mixed ? ' aria-checked="mixed" data-indeterminate="true"' : "") + "></th>" : "";
    return '<div class="attendance-table-wrap" data-component="attendance-table"><table class="attendance-table" data-density="compact" aria-label="' + text(settings.ariaLabel || "Conferência dos dias do funcionário") + '"><caption class="sr-only">' + text(settings.caption || "Horários interpretados, jornada, saldo e situação por dia") + "</caption><thead><tr>" +
      selectionHead + '<th scope="col" class="attendance-table__day-heading">Dia</th><th scope="col" class="attendance-table__time-heading">Entrada</th><th scope="col" class="attendance-table__time-heading">Saída intervalo</th><th scope="col" class="attendance-table__time-heading">Retorno</th><th scope="col" class="attendance-table__time-heading">Saída</th><th scope="col" class="attendance-table__number-heading">Jornada</th><th scope="col" class="attendance-table__number-heading">Saldo</th><th scope="col">Situação</th><th scope="col">Observação</th></tr></thead><tbody>' +
      (rows || '<tr><td colspan="' + columnCount + '">' + EmptyState({ compact: true, title: settings.emptyTitle || "Nenhum dia encontrado", description: settings.emptyDescription || "Ajuste os filtros para ver outros registros." }) + "</td></tr>") + "</tbody></table></div>";
  }

  function normalizeOriginalPunches(input) {
    var source = Array.isArray(input) ? input : valueOf(input && input.punches, input && input.batidas, input && input.originalPunches, []);
    return array(source).map(function (punch) {
      return typeof punch === "object" && punch !== null ? punch : { value: punch };
    });
  }

  function OriginalPunchesList(input) {
    var settings = Array.isArray(input) ? { punches: input } : input || {};
    var punches = normalizeOriginalPunches(settings);
    var items = punches.map(function (punch, index) {
      var value = valueOf(punch.value, punch.time, punch.horario, punch.raw, "—");
      var source = [];
      if (punch.line != null || punch.linha != null || punch.sourceLine != null || punch.linhaOrigem != null) source.push("linha " + valueOf(punch.line, punch.linha, punch.sourceLine, punch.linhaOrigem));
      if (punch.page != null || punch.pagina != null) source.push("página " + valueOf(punch.page, punch.pagina));
      return '<li class="original-punch"><span class="punch-order" aria-hidden="true">' + text(index + 1) + '</span><time class="punch-time">' + text(value) + "</time>" +
        (source.length ? '<span class="punch-source">' + text(source.join(" · ")) + "</span>" : "") + "</li>";
    }).join("");
    return '<div class="original-punches-list" data-component="original-punches-list"><h3>' + text(settings.title || "Batidas originais") + ' <span class="readonly-label">Somente leitura</span></h3>' +
      (items ? '<ol aria-label="Batidas originais em ordem">' + items + "</ol>" : EmptyState({ compact: true, icon: "clock", title: "Nenhuma batida original", description: "O arquivo não contém marcações para este dia." })) + "</div>";
  }

  function ActivityTimeline(input) {
    var settings = Array.isArray(input) ? { items: input } : input || {};
    var items = array(valueOf(settings.items, settings.events, settings.history, settings.historico)).map(function (event) {
      var dateTime = valueOf(event.at, event.date, event.timestamp, event.createdAt, event.dataHora);
      var time = valueOf(event.time, event.hora, dateTime ? Utils.formatDateTime(dateTime) : null, "");
      var title = valueOf(event.title, event.titulo, event.label, event.acao, "");
      var description = valueOf(event.description, event.message, event.descricao, title || "Atividade registrada");
      return '<li class="timeline-item"><span class="timeline-marker activity-timeline__marker" aria-hidden="true"></span><div class="timeline-content">' +
        (time ? '<time class="timeline-time"' + attr("datetime", dateTime) + ">" + text(time) + "</time>" : "") + (title ? '<strong class="timeline-title">' + text(title) + "</strong>" : "") + '<p>' + text(description) + "</p>" +
        (event.actor || event.autor ? '<span class="timeline-actor">' + text(valueOf(event.actor, event.autor)) + "</span>" : "") + "</div></li>";
    }).join("");
    return '<section class="activity-timeline" data-component="activity-timeline"><h3>' + text(settings.title || "Histórico do dia") + "</h3>" +
      (items ? '<ol>' + items + "</ol>" : '<p class="muted-text">Nenhuma atividade registrada.</p>') + "</section>";
  }

  function detailRow(label, value, className) {
    return '<div class="detail-row' + (className ? " " + text(className) : "") + '"><dt>' + text(label) + "</dt><dd>" + text(value == null || value === "" ? "—" : value) + "</dd></div>";
  }

  function defaultDayActions(day, punches) {
    var confirmed = resolveStatus(reviewState(day)).key === "confirmed";
    if (confirmed) return [{ action: "reopen-day", label: "Reabrir conferência", icon: "edit", variant: "secondary" }];
    if (!punches.length) return [
      { action: "set-day-absence", label: "Registrar falta", variant: "secondary" },
      { action: "set-day-certificate", label: "Adicionar atestado", variant: "secondary" },
      { action: "set-day-dayoff", label: "Registrar folga", variant: "secondary" },
      { action: "focus-first-time", label: "Inserir horários manualmente", variant: "secondary" },
      { action: "set-day-no-schedule", label: "Marcar como sem expediente", variant: "ghost" },
    ];
    if (resolveStatus(dayStatus(day)).key === "needs_review" || array(day.issues || day.pendencias).length) return [
      { action: "set-day-certificate", label: "Adicionar atestado", variant: "secondary" },
      { action: "focus-first-time", label: "Corrigir marcações", variant: "secondary" },
      { action: "keep-interpretation", label: "Manter interpretação", variant: "secondary" },
      { action: "focus-observation", label: "Adicionar observação", variant: "ghost" },
      { action: "confirm-day", label: "Marcar como conferido", icon: "check", variant: "primary" },
    ];
    return [{ action: "set-day-certificate", label: "Adicionar atestado", variant: "secondary" },
      { action: "confirm-day", label: "Marcar dia como conferido", icon: "check", variant: "primary" }];
  }

  function DayDetailsPanel(props) {
    var settings = props || {};
    var readonly = settings.readonly === true || settings.disabled === true;
    var day = settings.day || settings.record;
    if (!day) {
      return '<aside id="day-details-panel" class="day-details-panel is-empty" data-component="day-details-panel" aria-label="Detalhes do dia">' + EmptyState({ icon: "calendar", title: "Selecione um dia", description: "As batidas originais, pendências e atividades desta sessão aparecerão aqui." }) + "</aside>";
    }
    var dayId = valueOf(day.id, day.dayId, day.data);
    var date = valueOf(day.date, day.data);
    var current = dayCurrent(day);
    var metricSource = Object.assign({}, day, current);
    var slots = getSlots(day);
    var original = valueOf(day.original, day.originalData, day.dadosOriginais, {}) || {};
    var source = valueOf(day.source, day.origem, original.source, original.origem, {}) || {};
    var punches = normalizeOriginalPunches(valueOf(day.originalPunchDetails, day.detalhesBatidasOriginais, original.punchDetails, original.detalhesBatidas, original.punches, original.batidas, day.originalPunches, []));
    var issues = array(valueOf(day.issues, day.pendencias)).map(function (issue) {
      var message = typeof issue === "object" && issue !== null ? valueOf(issue.message, issue.description, issue.mensagem, issue.descricao) : issue;
      var severity = typeof issue === "object" && issue !== null ? valueOf(issue.severity, issue.gravidade, "warning") : "warning";
      return '<li class="issue-item severity-' + text(token(severity, "warning")) + '">' + Icon(severity === "error" ? "x_circle" : "alert") + "<span>" + text(message) + "</span></li>";
    }).join("");
    var expected = metricMinutes(metricSource, ["expectedMinutes", "expected_minutes", "jornadaPrevistaMinutos"], ["expected", "jornadaPrevista", "jornada_prevista"]);
    var worked = metricMinutes(metricSource, ["workedMinutes", "worked_minutes", "jornadaApuradaMinutos"], ["worked", "jornadaApurada", "jornada_apurada", "jornada"]);
    var balance = metricMinutes(metricSource, ["balanceMinutes", "balance_minutes", "saldoMinutos"], ["balance", "saldo"]);
    var file = settings.file || {};
    var sourceFile = valueOf(file.name, file.nome, source.fileName, source.nomeArquivo, source.arquivo, original.fileName, original.arquivo, source.fileId, original.fileId, day.fileName, "—");
    var importedAt = valueOf(file.importedAt, file.uploadedAt, file.importadoEm, source.importedAt, source.importadoEm, original.importedAt, original.importadoEm);
    var sourceLines = valueOf(source.sourceLines, source.linhasOrigem, original.lines, original.linhas, punches.map(function (punch) { return valueOf(punch.line, punch.linha, punch.sourceLine, punch.linhaOrigem); }).filter(function (line) { return line != null; }));
    var hasRegion = Boolean(valueOf(source.region, source.regiao, original.region, original.regiao, punches.some(function (punch) { return punch.region || punch.regiao; })));
    var actions = readonly ? [] : valueOf(settings.actions, defaultDayActions(day, punches));
    return '<aside id="day-details-panel" class="day-details-panel" data-component="day-details-panel" data-day-id="' + text(dayId) + '" aria-labelledby="day-details-title">' +
      '<header class="details-header day-details-panel__header"><div><p class="details-eyebrow">' + text(Utils.formatWeekday(date, { long: true })) + '</p><h2 id="day-details-title">' + text(Utils.formatDate(date)) + "</h2></div>" + StatusChip(day.effectiveStatus || dayStatus(day)) + "</header>" + (day.calendarNote ? '<p class="context-note">' + text(day.calendarNote) + "</p>" : "") +
      (day.occurrenceLabel ? '<p class="context-note"><strong>' + text(day.occurrenceLabel) + '</strong> · Abono calculado: ' + text(day.excusedMinutes || 0) + ' min. As batidas permanecem preservadas.</p>' : "") +
      OriginalPunchesList({ punches: punches }) +
      '<section class="details-section current-interpretation"><h3>Interpretação atual</h3><dl>' + detailRow("Entrada", slots.entry) + detailRow("Saída intervalo", slots.breakOut) + detailRow("Retorno", slots.breakIn) + detailRow("Saída", slots.exit) + detailRow("Jornada prevista", formatMinutesOrValue(expected, false)) + detailRow("Jornada apurada", formatMinutesOrValue(worked, false)) + detailRow("Saldo", formatMinutesOrValue(balance, true), Number(balance) > 0 ? "is-positive" : Number(balance) < 0 ? "is-negative" : "") + "</dl>" +
      (valueOf(current.differenceReason, current.motivoDiferenca, day.differenceReason, day.motivoDiferenca) ? '<p class="difference-reason"><strong>Motivo:</strong> ' + text(valueOf(current.differenceReason, current.motivoDiferenca, day.differenceReason, day.motivoDiferenca)) + "</p>" : "") + "</section>" +
      '<section class="details-section issues-section"><h3>Pendências <span class="count-badge">' + text(array(valueOf(day.issues, day.pendencias)).length) + "</span></h3>" + (issues ? '<ul class="issues-list">' + issues + "</ul>" : '<p class="muted-text">Nenhuma pendência identificada.</p>') + "</section>" +
      '<section class="details-section origin-section"><h3>Origem</h3><dl>' + detailRow("Arquivo", sourceFile) + detailRow("Importado em", importedAt ? Utils.formatDateTime(importedAt) : "—") + detailRow("Linhas de origem", array(sourceLines).join(", ") || "—") + '</dl><div class="context-buttons">' +
      actionButton("open-original-file", "Ver arquivo original", { icon: "file", variant: "secondary", fileId: valueOf(file.id, source.fileId, original.fileId), disabled: sourceFile === "—" }) +
      actionButton("open-source-region", "Ver região de origem", { icon: "eye", variant: "ghost", fileId: valueOf(file.id, source.fileId, original.fileId), disabled: !hasRegion }) + "</div></section>" +
      ActivityTimeline({ items: valueOf(day.history, day.historico, []), title: "Histórico de alterações" }) +
      '<footer class="details-actions" aria-label="Ações para o dia">' + (readonly
        ? '<p class="muted-text" role="note">Competência fechada: este dia está disponível somente para consulta.</p>'
        : array(actions).map(function (action) { return actionButton(action.action || action.id, action.label, Object.assign({}, action, { dayId: dayId })); }).join("")) + "</footer></aside>";
  }

  function ImportDropzone(props) {
    var settings = props || {};
    var inputId = settings.inputId || "point-file-input";
    var file = settings.file || null;
    var accept = settings.accept || ".txt,.xls,.xlsx,.pdf,.png,.jpg,.jpeg";
    return '<div class="import-dropzone' + (settings.dragging ? " is-dragging" : "") + (settings.disabled ? " is-disabled" : "") + '" data-component="import-dropzone" data-drop-action="select-import-file">' +
      '<input class="sr-only dropzone-input" id="' + text(inputId) + '" type="file" tabindex="-1" data-action="select-import-file" accept="' + text(accept) + '"' + boolAttr("disabled", settings.disabled) + ">" +
      '<label for="' + text(inputId) + '" class="dropzone-label">' + '<span class="import-dropzone__icon">' + Icon(file ? "file" : "upload") + '</span><span class="dropzone-title">' + text(file ? valueOf(file.name, file.nome) : settings.title || "Arraste o arquivo ou escolha no computador") + "</span>" +
      '<span class="dropzone-description">' + text(file ? (file.size != null ? Utils.formatFileSize(file.size) : "Arquivo pronto para análise") : settings.description || "TXT, XLS, XLSX, PDF, PNG ou JPG") + "</span>" +
      '</label><button type="button" class="button button-secondary" data-action="open-file-picker" aria-controls="' + text(inputId) + '"' + boolAttr("disabled", settings.disabled) + '>' + text(file ? "Trocar arquivo" : "Escolher arquivo") + "</button>" +
      (file ? actionButton("clear-import-file", "Remover arquivo", { icon: "trash", variant: "ghost", ariaLabel: "Remover " + valueOf(file.name, file.nome, "arquivo") }) : "") + "</div>";
  }

  function MetricCard(props) {
    var settings = props || {};
    return '<article class="metric-card' + (settings.tone ? " tone-" + text(token(settings.tone)) : "") + '" data-component="metric-card">' +
      (settings.icon ? '<span class="metric-card__icon" aria-hidden="true">' + Icon(settings.icon) + "</span>" : '<span class="metric-card__icon" aria-hidden="true">#</span>') +
      '<div class="metric-card__copy"><span class="metric-card__label">' + text(settings.label) + '</span><strong class="metric-card__value">' + text(valueOf(settings.value, "—")) + "</strong>" +
      (settings.description ? '<span class="metric-card__meta">' + text(settings.description) + "</span>" : "") + "</div></article>";
  }

  function importPreviewRow(row) {
    var originals = valueOf(row.originalPunches, row.punches, row.batidasOriginais, row.batidas_originais, []);
    var suggested = valueOf(row.suggested, row.suggestion, row.interpretation, row.interpretacaoSugerida, row.interpretacao_sugerida, {});
    var suggestedSlots = getSlots({ current: suggested });
    var suggestedLabel = [suggestedSlots.entry, suggestedSlots.breakOut, suggestedSlots.breakIn, suggestedSlots.exit].filter(Boolean).join(" / ") || "—";
    return '<tr><td>' + text(valueOf(row.employeeName, row.funcionarioNome, row.funcionario, "—")) + "</td><td>" + text(Utils.formatDate(valueOf(row.date, row.data), { short: true })) + '</td><td class="original-data">' + text(normalizeOriginalPunches(originals).map(function (punch) { return valueOf(punch.value, punch.time, punch.horario); }).join(", ") || "—") + '</td><td class="suggested-data">' + text(suggestedLabel) + "</td><td>" + StatusChip(valueOf(row.status, row.situation, row.situacao, suggested.situation, suggested.situacao, "needs_review"), { compact: true }) + "</td><td>" + text(valueOf(row.observation, row.observacao, suggested.observation, suggested.observacao, "—")) + "</td></tr>";
  }

  function ImportPreview(props) {
    var settings = props || {};
    if (settings.analysis) {
      var analysis = settings.analysis;
      var analysisMetrics = [
        { label: "Formato detectado", value: valueOf(analysis.detectedFormat, analysis.formatoDetectado, "—"), icon: "file" },
        { label: "Funcionários", value: valueOf(analysis.employeeCount, analysis.totalFuncionarios, 0), icon: "users" },
        { label: "Batidas", value: valueOf(analysis.punchCount, analysis.totalBatidas, 0), icon: "clock" },
        { label: "Dias", value: valueOf(analysis.dayCount, analysis.totalDias, 0), icon: "calendar" },
        { label: "Pendências", value: valueOf(analysis.pendingCount, analysis.totalPendencias, 0), icon: "alert", tone: "warning" },
      ].map(MetricCard).join("");
      return '<section class="import-preview import-analysis-result" data-component="import-preview" aria-labelledby="analysis-title"><header class="import-preview-header"><div><p class="page-eyebrow">Análise simulada concluída</p><h2 id="analysis-title">' + text(valueOf(analysis.fileName, analysis.nomeArquivo, "Arquivo de ponto")) + "</h2></div>" + StatusChip({ status: "confirmed", label: "Pronto para prévia" }) + "</header><div class=\"import-summary\">" + analysisMetrics + '</div><div class="button-row">' + actionButton("open-import-preview", "Ver prévia", { variant: "primary", route: "import-preview" }) + actionButton("discard-import", "Descartar", { variant: "ghost" }) + "</div></section>";
    }
    var draft = settings.draft || settings.importDraft || settings.result || settings;
    var summary = draft.summary || draft.resumo || {};
    var rows = array(valueOf(draft.previewRows, draft.rows, draft.registros));
    var file = settings.file || draft.file || {};
    var metrics = [
      { label: "Funcionários", value: valueOf(summary.employees, summary.employeeCount, summary.funcionarios, 0), icon: "users" },
      { label: "Registros", value: valueOf(summary.punches, summary.records, summary.registros, summary.batidas, 0), icon: "clock" },
      { label: "Dias", value: valueOf(summary.days, summary.dias, 0), icon: "calendar" },
      { label: "Pendências", value: valueOf(summary.issues, summary.pending, summary.pendencias, 0), icon: "alert", tone: "warning" },
    ].map(MetricCard).join("");
    var tableRows = rows.map(importPreviewRow).join("");
    return '<section class="import-preview" data-component="import-preview" aria-labelledby="import-preview-title"><header class="import-preview-header"><div><p class="page-eyebrow">Prévia da importação</p><h2 id="import-preview-title">O que o sistema entendeu deste arquivo?</h2></div>' + StatusChip(valueOf(draft.state, draft.status, "needs_review"), { label: draft.state === "analyzed" || draft.state === "analisado" ? "Análise concluída" : null }) + "</header>" +
      '<dl class="import-metadata">' + detailRow("Arquivo", valueOf(file.name, file.nome, draft.fileName, draft.nomeArquivo, "—")) + detailRow("Empresa", valueOf(settings.companyName, draft.companyName, draft.empresaNome, "—")) + detailRow("Competência", valueOf(settings.competencyLabel, draft.competencyLabel, draft.competencia, "—")) + detailRow("Formato detectado", String(valueOf(draft.detectedFormat, draft.formatoDetectado, draft.formato_detectado, "—")).toUpperCase()) + "</dl>" +
      '<div class="import-summary">' + metrics + "</div>" +
      '<div class="preview-toolbar" aria-label="Filtros da prévia"><div class="filter-group" role="group" aria-label="Filtrar registros">' +
      actionButton("filter-import-preview", "Todos", { value: "all", variant: settings.filter === "all" || !settings.filter ? "filter-active" : "filter", pressed: settings.filter === "all" || !settings.filter }) +
      actionButton("filter-import-preview", "Somente pendências", { value: "pending", variant: settings.filter === "pending" || settings.filter === "issues" ? "filter-active" : "filter", pressed: settings.filter === "pending" || settings.filter === "issues" }) +
      '</div><label class="compact-field"><span>Funcionário</span><select data-action="filter-import-employee"><option value="">Todos</option>' + array(settings.employees).map(function (employee) { var id = valueOf(employee.id, employee.value); return '<option value="' + text(id) + '"' + boolAttr("selected", sameId(id, settings.employeeId)) + ">" + text(valueOf(employee.name, employee.nome, employee.label)) + "</option>"; }).join("") + "</select></label></div>" +
      '<div class="import-preview-table-wrap"><table class="import-preview-table"><caption class="sr-only">Dados originais e interpretação sugerida da importação</caption><thead><tr><th scope="col">Funcionário</th><th scope="col">Data</th><th scope="col">Batidas originais</th><th scope="col">Interpretação sugerida</th><th scope="col">Status</th><th scope="col">Observação</th></tr></thead><tbody>' +
      (tableRows || '<tr><td colspan="6">' + EmptyState({ compact: true, title: "Nenhum registro na prévia", description: "Ajuste os filtros ou analise outro arquivo." }) + "</td></tr>") + "</tbody></table></div>" +
      '<footer class="import-preview-actions">' + actionButton("back-from-import-preview", "Voltar", { icon: "chevron_left", variant: "ghost" }) + '<div class="actions-right">' + actionButton("discard-import", "Descartar", { icon: "trash", variant: "danger-ghost" }) + actionButton("save-import-start-review", "Salvar importação e iniciar conferência", { icon: "arrow_right", variant: "primary", disabled: !rows.length }) + "</div></footer></section>";
  }

  function AutosaveIndicator(input) {
    var settings = typeof input === "string" ? { state: input } : input || {};
    var rawState = valueOf(settings.state, settings.status, "saved");
    var saveKey = token(rawState);
    if (["error", "erro", "failed", "failure"].indexOf(saveKey) !== -1) rawState = "save_error";
    if (["idle", "clean", "success"].indexOf(saveKey) !== -1) rawState = "saved";
    var resolved = resolveStatus(rawState);
    var label = valueOf(settings.label, settings.message, resolved.meta.label);
    var live = resolved.key === "saving" ? "polite" : "assertive";
    return '<div class="autosave-indicator state-' + text(resolved.key) + " autosave-indicator--" + text(resolved.key) + '" data-component="autosave-indicator" data-save-state="' + text(resolved.key) + '" role="status" aria-live="' + live + '" aria-atomic="true">' + Icon(resolved.meta.icon) + '<span>' + text(label) + "</span>" +
      (resolved.key === "save_error" ? actionButton("retry-save", "Tentar novamente", { variant: "link" }) : "") + "</div>";
  }

  function EmptyState(props) {
    var settings = props || {};
    return '<div class="empty-state' + (settings.compact ? " is-compact" : "") + '" data-component="empty-state">' +
      '<div class="empty-state-icon">' + Icon(settings.icon || "search") + "</div><div><h3>" + text(settings.title || "Nada por aqui") + "</h3>" +
      (settings.description ? "<p>" + text(settings.description) + "</p>" : "") +
      (settings.action ? actionButton(settings.action.action || settings.action.id, settings.action.label, settings.action) : "") + "</div></div>";
  }

  function ConfirmationDialog(props) {
    var settings = props || {};
    var dialogId = settings.id || "confirmation-dialog";
    var descriptionId = dialogId + "-description";
    var titleId = dialogId + "-title";
    var countMessage = settings.count != null ? '<p class="dialog-count"><strong>' + text(settings.count) + "</strong> " + text(settings.count === 1 ? settings.singular || "registro será alterado" : settings.plural || "registros serão alterados") + ".</p>" : "";
    return '<dialog id="' + text(dialogId) + '" class="confirmation-dialog" data-component="confirmation-dialog" aria-labelledby="' + text(titleId) + '" aria-describedby="' + text(descriptionId) + '"' + boolAttr("open", settings.open) + '><form method="dialog"><header class="dialog-header"><span class="dialog-icon tone-' + text(token(settings.tone, "warning")) + '">' + Icon(settings.icon || "alert") + '</span><div><h2 id="' + text(titleId) + '">' + text(settings.title || "Confirmar ação") + "</h2><p id=\"" + text(descriptionId) + "\">" + text(settings.description || "Revise as informações antes de continuar.") + "</p></div>" +
      '<button type="button" class="icon-button dialog-close" data-action="cancel-confirmation" aria-label="Fechar diálogo">' + Icon("close") + "</button></header>" + countMessage +
      (settings.details ? '<div class="dialog-details">' + text(settings.details) + "</div>" : "") + '<footer class="dialog-actions">' + actionButton("cancel-confirmation", settings.cancelLabel || "Cancelar", { variant: "secondary" }) + actionButton(settings.confirmAction || "confirm-dialog", settings.confirmLabel || "Confirmar", { variant: settings.destructive ? "danger" : "primary", value: settings.value, disabled: settings.busy }) + "</footer></form></dialog>";
  }

  function Tabs(props) {
    var settings = props || {};
    return '<div class="tabs" data-component="tabs"><div class="tab-list" role="tablist" aria-label="' + text(settings.label || "Seções") + '">' + array(settings.items).map(function (item) {
      var id = valueOf(item.id, item.value);
      var active = sameId(id, settings.active);
      return '<button type="button" role="tab" class="tab-button' + (active ? " is-active" : "") + '" data-action="select-tab" data-tab="' + text(id) + '" aria-selected="' + (active ? "true" : "false") + '" tabindex="' + (active ? "0" : "-1") + '">' + text(item.label) + (item.count == null ? "" : '<span class="tab-count">' + text(item.count) + "</span>") + "</button>";
    }).join("") + "</div></div>";
  }

  root.OnPontoComponents = Object.freeze({
    Icon: Icon,
    Sidebar: Sidebar,
    PageHeader: PageHeader,
    StatusChip: StatusChip,
    ProgressIndicator: ProgressIndicator,
    EditableTimeCell: EditableTimeCell,
    AttendanceTable: AttendanceTable,
    DayDetailsPanel: DayDetailsPanel,
    OriginalPunchesList: OriginalPunchesList,
    ImportDropzone: ImportDropzone,
    ImportPreview: ImportPreview,
    ActivityTimeline: ActivityTimeline,
    AutosaveIndicator: AutosaveIndicator,
    EmptyState: EmptyState,
    ConfirmationDialog: ConfirmationDialog,
    MetricCard: MetricCard,
    Tabs: Tabs,
    statusAliases: Object.freeze(Object.assign({}, STATUS_ALIASES)),
    statusMeta: Object.freeze(Object.assign({}, STATUS_META)),
  });
})(typeof window !== "undefined" ? window : globalThis);
