(function (root) {
  "use strict";

  var Mocks = root.OnPontoMocks;
  var Utils = root.OnPontoUtils;
  var Components = root.OnPontoComponents;
  var Screens = root.OnPontoScreens;

  if (!Mocks || !Utils || !Components || !Screens) {
    throw new Error("Não foi possível iniciar o On Ponto: módulos do frontend ausentes.");
  }

  var VIEWS = [
    "companies",
    "company-overview",
    "company-employees",
    "company-competencies",
    "competency-summary",
    "imports",
    "import-preview",
    "ocr",
    "review",
    "competency-files",
    "competency-history",
    "competency-exports",
    "company-reports",
    "company-settings",
  ];

  var COMPANY_VIEWS = [
    "company-overview",
    "company-employees",
    "company-competencies",
    "company-reports",
    "company-settings",
  ];

  var COMPETENCY_VIEWS = [
    "competency-summary",
    "imports",
    "import-preview",
    "ocr",
    "review",
    "competency-files",
    "competency-history",
    "competency-exports",
  ];

  var ROUTE_ALIASES = {
    companies: "companies",
    empresas: "companies",
    registrations: "companies",
    cadastros: "companies",
    dashboard: "company-overview",
    painel: "company-overview",
    "company-overview": "company-overview",
    "company-employees": "company-employees",
    employees: "company-employees",
    funcionarios: "company-employees",
    "company-competencies": "company-competencies",
    competencies: "company-competencies",
    competencias: "company-competencies",
    "competency-summary": "competency-summary",
    "competency-detail": "competency-summary",
    "competency_detail": "competency-summary",
    competencia: "competency-summary",
    summary: "competency-summary",
    resumo: "competency-summary",
    imports: "imports",
    importacoes: "imports",
    "import-preview": "import-preview",
    "import_preview": "import-preview",
    preview: "import-preview",
    previa: "import-preview",
    ocr: "ocr",
    leitura: "ocr",
    review: "review",
    conference: "review",
    conferencia: "review",
    "competency-files": "competency-files",
    files: "competency-files",
    arquivos: "competency-files",
    "competency-history": "competency-history",
    history: "competency-history",
    historico: "competency-history",
    "competency-exports": "competency-exports",
    exports: "competency-exports",
    exportacoes: "competency-exports",
    "company-reports": "company-reports",
    reports: "company-reports",
    relatorios: "company-reports",
    "company-settings": "company-settings",
    settings: "company-settings",
    configuracoes: "company-settings",
  };

  var STATUS_LABELS = {
    normal: "Normal",
    conferir: "Conferir",
    inconsistente: "Inconsistente",
    falta: "Falta",
    atestado: "Atestado",
    folga: "Folga",
    feriado: "Feriado",
    domingo: "Domingo",
    sem_expediente: "Sem expediente",
    trabalho_externo: "Trabalho externo",
    afastamento: "Afastamento",
  };

  var SLOT_ALIASES = {
    entry: ["entry", "entrada"],
    breakStart: ["breakStart", "breakOut", "intervalOut", "saidaIntervalo", "saida_intervalo"],
    breakEnd: ["breakEnd", "breakIn", "intervalIn", "retorno", "retornoIntervalo", "retorno_intervalo"],
    exit: ["exit", "saida"],
  };

  var data = Mocks.getFreshData();
  var state = createInitialState();
  var autosaveTimer = null;
  var toastSequence = 0;
  var pendingDialog = null;
  var editSession = null;
  var renderFocus = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function asId(value) {
    if (value === null || value === undefined || value === "") return null;
    return /^\d+$/.test(String(value)) ? Number(value) : String(value);
  }

  function idsEqual(left, right) {
    return left !== null && left !== undefined && right !== null && right !== undefined && String(left) === String(right);
  }

  function emptyRoute() {
    return { view: "companies", companyId: null, competenceId: null };
  }

  function safeDecode(value) {
    try {
      return decodeURIComponent(value);
    } catch (error) {
      return value;
    }
  }

  function parseHashRoute(hash) {
    var raw = String(hash || "")
      .replace(/^#/, "")
      .split("?")[0]
      .replace(/^\/+|\/+$/g, "");
    var segments = raw ? raw.split("/").filter(Boolean).map(safeDecode) : [];
    if (segments.length === 1 && segments[0].toLowerCase() === "empresas") return emptyRoute();
    if (segments.length < 2 || segments[0].toLowerCase() !== "empresas") return emptyRoute();

    var companyId = asId(segments[1]);
    if (segments.length === 2) return { view: "company-overview", companyId: companyId, competenceId: null };
    if (segments.length === 3) {
      var companyChild = {
        funcionarios: "company-employees",
        competencias: "company-competencies",
        relatorios: "company-reports",
        configuracoes: "company-settings",
      }[segments[2].toLowerCase()];
      return companyChild ? { view: companyChild, companyId: companyId, competenceId: null } : emptyRoute();
    }
    if (segments.length < 4 || segments[2].toLowerCase() !== "competencias") return emptyRoute();

    var competenceId = asId(segments[3]);
    if (segments.length === 4) return { view: "competency-summary", companyId: companyId, competenceId: competenceId };
    if (segments.length === 5) {
      var competenceChild = {
        importacoes: "imports",
        conferencia: "review",
        arquivos: "competency-files",
        historico: "competency-history",
        exportacoes: "competency-exports",
      }[segments[4].toLowerCase()];
      return competenceChild ? { view: competenceChild, companyId: companyId, competenceId: competenceId } : emptyRoute();
    }
    if (segments.length === 6 && segments[4].toLowerCase() === "importacoes") {
      var importChild = { previa: "import-preview", leitura: "ocr" }[segments[5].toLowerCase()];
      return importChild ? { view: importChild, companyId: companyId, competenceId: competenceId } : emptyRoute();
    }
    return emptyRoute();
  }

  function validateRoute(route) {
    var descriptor = route || emptyRoute();
    var view = VIEWS.indexOf(descriptor.view) === -1 ? "companies" : descriptor.view;
    if (view === "companies") return emptyRoute();

    var companyId = asId(descriptor.companyId);
    var company = companies().find(function (item) { return idsEqual(item.id, companyId); });
    if (!company) return emptyRoute();
    if (COMPANY_VIEWS.indexOf(view) !== -1) {
      return { view: view, companyId: company.id, competenceId: null };
    }

    var competenceId = asId(descriptor.competenceId);
    var competence = competencies().find(function (item) {
      return idsEqual(item.id, competenceId) && idsEqual(item.companyId || item.empresa_id, company.id);
    });
    if (!competence || COMPETENCY_VIEWS.indexOf(view) === -1) return emptyRoute();
    return { view: view, companyId: company.id, competenceId: competence.id };
  }

  function routeHash(route) {
    var descriptor = validateRoute(route);
    if (descriptor.view === "companies") return "#/empresas";
    var base = "#/empresas/" + encodeURIComponent(descriptor.companyId);
    var companySuffix = {
      "company-overview": "",
      "company-employees": "/funcionarios",
      "company-competencies": "/competencias",
      "company-reports": "/relatorios",
      "company-settings": "/configuracoes",
    }[descriptor.view];
    if (companySuffix !== undefined) return base + companySuffix;

    var competenceBase = base + "/competencias/" + encodeURIComponent(descriptor.competenceId);
    return competenceBase + ({
      "competency-summary": "",
      imports: "/importacoes",
      "import-preview": "/importacoes/previa",
      ocr: "/importacoes/leitura",
      review: "/conferencia",
      "competency-files": "/arquivos",
      "competency-history": "/historico",
      "competency-exports": "/exportacoes",
    }[descriptor.view] || "");
  }

  function routeView(route) {
    var key = String(route || "")
      .replace(/^#\/?/, "")
      .split("?")[0]
      .trim()
      .toLowerCase();
    return ROUTE_ALIASES[key] || key;
  }

  function navigationTarget(route) {
    if (route && typeof route === "object") {
      return validateRoute({
        view: routeView(route.view || route.route),
        companyId: Object.prototype.hasOwnProperty.call(route, "companyId") ? route.companyId : state.selectedCompanyId,
        competenceId: Object.prototype.hasOwnProperty.call(route, "competenceId") ? route.competenceId : state.selectedCompetenceId,
      });
    }

    var raw = String(route || "").trim();
    if (/^#|^\//.test(raw) || /^empresas(?:\/|$)/i.test(raw)) return validateRoute(parseHashRoute(raw));
    return validateRoute({ view: routeView(raw), companyId: state.selectedCompanyId, competenceId: state.selectedCompetenceId });
  }

  function normalizeRoute(route) {
    return navigationTarget(route).view;
  }

  function createInitialState() {
    var savedCollapsed = false;
    try {
      savedCollapsed = localStorage.getItem("onponto.sidebarCollapsed") === "true";
    } catch (error) {
      savedCollapsed = false;
    }

    return {
      route: "companies",
      sidebarCollapsed: savedCollapsed,
      selectedCompanyId: null,
      selectedCompetenceId: null,
      selectedEmployeeId: null,
      selectedDayId: null,
      selectedDayIds: [],
      companySearch: "",
      reviewFilter: "all",
      competenciesCompanyId: "",
      competenciesStatusFilter: "all",
      competencyTab: "summary",
      registrationsTab: "companies",
      importType: "auto",
      selectedImportFile: null,
      importAnalysis: false,
      importPreviewFilter: "all",
      importPreviewEmployeeId: "",
      autosaveStatus: "saved",
      autosaveRevision: 0,
      undoStack: [],
      ocr: Utils.safeClone(data.ocr),
      settings: {
        autosave: true,
        unusualTimeAlerts: true,
        singleKeyShortcuts: true,
      },
    };
  }

  function companies() {
    return data.companies || data.empresas || [];
  }

  function competencies() {
    return data.competencies || data.competencias || [];
  }

  function employees() {
    return data.employees || data.funcionarios || [];
  }

  function days() {
    return data.attendanceDays || data.dias || [];
  }

  function files() {
    return data.files || data.arquivos || [];
  }

  function optionalIdsEqual(left, right) {
    if ((left === null || left === undefined) && (right === null || right === undefined)) return true;
    return idsEqual(left, right);
  }

  function resetCompetencyTransientState() {
    root.clearTimeout(autosaveTimer);
    autosaveTimer = null;
    state.selectedEmployeeId = null;
    state.selectedDayId = null;
    state.selectedDayIds = [];
    state.reviewFilter = "all";
    state.competencyTab = "summary";
    state.importType = "auto";
    state.selectedImportFile = null;
    state.importAnalysis = false;
    state.importPreviewFilter = "all";
    state.importPreviewEmployeeId = "";
    state.autosaveStatus = "saved";
    state.autosaveRevision = 0;
    state.undoStack = [];
    state.ocr = Utils.safeClone(data.ocr);
    editSession = null;
    renderFocus = null;
  }

  function resetCompanyTransientState() {
    resetCompetencyTransientState();
    state.companySearch = "";
    state.competenciesCompanyId = "";
    state.competenciesStatusFilter = "all";
    state.registrationsTab = "companies";
  }

  function competencyTabForView(view) {
    return {
      "competency-summary": "summary",
      imports: "imports",
      "import-preview": "imports",
      ocr: "imports",
      review: "review",
      "competency-files": "files",
      "competency-history": "history",
      "competency-exports": "exports",
    }[view] || "summary";
  }

  function applyRouteContext(route) {
    var descriptor = validateRoute(route);
    var companyChanged = !optionalIdsEqual(state.selectedCompanyId, descriptor.companyId);
    var competenceChanged = !optionalIdsEqual(state.selectedCompetenceId, descriptor.competenceId);
    if (companyChanged) resetCompanyTransientState();
    else if (competenceChanged) resetCompetencyTransientState();

    state.selectedCompanyId = descriptor.companyId;
    state.selectedCompetenceId = descriptor.competenceId;
    state.route = descriptor.view;
    state.competenciesCompanyId = descriptor.companyId || "";
    state.competencyTab = competencyTabForView(descriptor.view);

    if (!descriptor.competenceId) {
      state.selectedEmployeeId = null;
      state.selectedDayId = null;
      state.selectedDayIds = [];
      return descriptor;
    }

    var scopedEmployees = companyEmployees();
    if (!scopedEmployees.some(function (item) { return idsEqual(item.id, state.selectedEmployeeId); })) {
      state.selectedEmployeeId = scopedEmployees[0] ? scopedEmployees[0].id : null;
    }
    var scopedDays = employeeDays(state.selectedEmployeeId);
    if (!scopedDays.some(function (item) { return idsEqual(item.id, state.selectedDayId); })) {
      state.selectedDayId = scopedDays[0] ? scopedDays[0].id : null;
    }
    state.selectedDayIds = state.selectedDayIds.filter(function (dayId) {
      return scopedDays.some(function (day) { return idsEqual(day.id, dayId); });
    });
    return descriptor;
  }

  function currentCompany() {
    return companies().find(function (item) { return idsEqual(item.id, state.selectedCompanyId); }) || null;
  }

  function currentCompetency() {
    return competencies().find(function (item) {
      return idsEqual(item.id, state.selectedCompetenceId) && idsEqual(item.companyId || item.empresa_id, state.selectedCompanyId);
    }) || null;
  }

  function currentEmployee() {
    return companyEmployees().find(function (item) { return idsEqual(item.id, state.selectedEmployeeId); }) || null;
  }

  function companyEmployees() {
    if (state.selectedCompanyId === null || state.selectedCompanyId === undefined) return [];
    return employees().filter(function (item) { return idsEqual(item.companyId || item.empresa_id, state.selectedCompanyId); });
  }

  function employeeDays(employeeId) {
    if (!employeeId || state.selectedCompetenceId === null || state.selectedCompetenceId === undefined) return [];
    return days().filter(function (day) {
      return idsEqual(day.employeeId || day.funcionario_id, employeeId) && idsEqual(day.competenceId || day.competencia_id, state.selectedCompetenceId);
    });
  }

  function findDay(dayId) {
    return days().find(function (day) { return idsEqual(day.id, dayId); }) || null;
  }

  function findFile(fileId) {
    return files().find(function (file) { return idsEqual(file.id, fileId); }) || null;
  }

  function dayIsConfirmed(day) {
    if (!day) return false;
    return day.confirmed === true || day.conferido === true || day.reviewState === "confirmed" || (day.review && day.review.state === "confirmed");
  }

  function currentSlots(day) {
    var current = day && (day.current || day.currentInterpretation || day.interpretacaoAtual) || {};
    return {
      entry: current.entry || current.entrada || "",
      breakStart: current.breakStart || current.breakOut || current.saidaIntervalo || current.saida_intervalo || "",
      breakEnd: current.breakEnd || current.breakIn || current.retorno || current.retorno_intervalo || "",
      exit: current.exit || current.saida || "",
    };
  }

  function visibleReviewDays() {
    return employeeDays(state.selectedEmployeeId).filter(function (day) {
      var status = day.status || (day.current && (day.current.situation || day.current.status)) || "conferir";
      var unresolved = (day.issues || []).some(function (issue) { return !issue || issue.resolved !== true; });
      if (state.reviewFilter === "pending") return status === "conferir" || status === "inconsistente" || unresolved;
      if (state.reviewFilter === "unconfirmed") return !dayIsConfirmed(day);
      if (state.reviewFilter === "absences") return ["falta", "atestado", "folga", "afastamento"].indexOf(status) !== -1;
      return true;
    });
  }

  function ensureReviewSelection() {
    var visible = visibleReviewDays();
    if (!visible.some(function (day) { return idsEqual(day.id, state.selectedDayId); })) {
      state.selectedDayId = visible[0] ? visible[0].id : null;
    }
    state.selectedDayIds = state.selectedDayIds.filter(function (id) {
      return visible.some(function (day) { return idsEqual(day.id, id); });
    });
  }

  function sidebarNavigation() {
    var company = currentCompany();
    var competence = currentCompetency();
    var primary = [{ id: "companies", label: "Todas as empresas", icon: "briefcase" }];
    if (!company) return { primary: primary, secondary: [], secondaryLabel: "" };

    primary = primary.concat([
      { id: "company-overview", label: "Visão geral", icon: "dashboard" },
      { id: "company-employees", label: "Funcionários", icon: "users" },
      { id: "company-competencies", label: "Competências", icon: "folder" },
      { id: "company-reports", label: "Relatórios", icon: "report" },
      { id: "company-settings", label: "Configurações", icon: "settings" },
    ]);
    if (!competence) return { primary: primary, secondary: [], secondaryLabel: company.name || company.nome };

    return {
      primary: primary,
      secondary: [
        { id: "competency-summary", label: "Resumo", icon: "dashboard" },
        { id: "imports", label: "Importações", icon: "upload" },
        { id: "review", label: "Conferência", icon: "check_square", badge: unresolvedCount() },
        { id: "competency-files", label: "Arquivos", icon: "file" },
        { id: "competency-history", label: "Histórico", icon: "clock" },
        { id: "competency-exports", label: "Exportações", icon: "report" },
      ],
      secondaryLabel: competence.label || Utils.formatCompetence(competence),
    };
  }

  function unresolvedCount() {
    return employeeDays(state.selectedEmployeeId).filter(function (day) {
      return (day.issues || []).some(function (issue) { return !issue || issue.resolved !== true; }) && !dayIsConfirmed(day);
    }).length;
  }

  function render(options) {
    var settings = options || {};
    if (state.route === "review") ensureReviewSelection();

    var app = byId("app");
    app.classList.toggle("is-sidebar-collapsed", state.sidebarCollapsed);
    app.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);

    var navigation = sidebarNavigation();
    byId("appSidebar").innerHTML = Components.Sidebar({
      active: state.route === "import-preview" || state.route === "ocr" ? "imports" : state.route,
      collapsed: state.sidebarCollapsed,
      primaryItems: navigation.primary,
      secondaryItems: navigation.secondary,
      secondaryLabel: navigation.secondaryLabel,
    });

    var expandButton = byId("sidebarExpandButton");
    expandButton.hidden = !state.sidebarCollapsed;
    expandButton.innerHTML = Components.Icon("panel_left");

    var company = currentCompany();
    var competency = currentCompetency();
    byId("topbarContext").textContent = !company
      ? "Todas as empresas"
      : (company.name || company.nome) + (competency ? " · " + (competency.label || Utils.formatCompetence(competency)) : "");

    var main = byId("mainContent");
    main.dataset.route = state.route;
    main.innerHTML = Screens.render(state.route, state, data, Components);
    document.title = screenTitle() + " · On Ponto";

    Array.prototype.forEach.call(main.querySelectorAll('[data-indeterminate="true"]'), function (checkbox) {
      checkbox.indeterminate = true;
    });

    var target = settings.focus || renderFocus;
    renderFocus = null;
    if (target) {
      root.requestAnimationFrame(function () { focusCell(target.dayId, target.field); });
    } else if (settings.focusMain) {
      root.requestAnimationFrame(function () { main.focus({ preventScroll: true }); });
    }
  }

  function screenTitle() {
    return {
      companies: "Empresas",
      "company-overview": "Visão geral",
      "company-employees": "Funcionários",
      "company-competencies": "Competências",
      "competency-summary": "Resumo da competência",
      imports: "Importações",
      "import-preview": "Prévia da importação",
      review: "Conferência",
      ocr: "Comparação de imagem",
      "competency-files": "Arquivos",
      "competency-history": "Histórico",
      "competency-exports": "Exportações",
      "company-reports": "Relatórios",
      "company-settings": "Configurações",
    }[state.route] || "On Ponto";
  }

  function navigate(route, options) {
    var next = navigationTarget(route);
    if (editSession && !finishEditing({ move: null })) return;
    var hash = routeHash(next);
    if (root.location.hash !== hash) {
      root.location.hash = hash;
    } else {
      applyRouteContext(next);
      render({ focusMain: !(options && options.keepFocus) });
    }
  }

  function toggleSidebar() {
    state.sidebarCollapsed = !state.sidebarCollapsed;
    try {
      localStorage.setItem("onponto.sidebarCollapsed", String(state.sidebarCollapsed));
    } catch (error) {
      /* A preferência continua válida durante a sessão. */
    }
    render();
  }

  function showToast(message, tone, detail) {
    var region = byId("toastRegion");
    var id = "toast-" + (++toastSequence);
    var icon = tone === "error" ? "×" : tone === "warning" ? "!" : tone === "success" ? "✓" : "i";
    var toast = document.createElement("div");
    toast.id = id;
    toast.className = "toast toast--" + (tone || "info");
    toast.setAttribute("role", tone === "error" ? "alert" : "status");
    toast.innerHTML = '<span class="toast__icon" aria-hidden="true">' + icon + '</span><p><strong>' + Utils.escapeHtml(message) + "</strong>" + (detail ? "<small>" + Utils.escapeHtml(detail) + "</small>" : "") + '</p><button type="button" class="toast__close" data-action="dismiss-toast" aria-label="Fechar aviso" data-toast-id="' + id + '">×</button>';
    region.appendChild(toast);
    root.setTimeout(function () {
      if (toast.isConnected) toast.remove();
    }, tone === "error" ? 6500 : 4200);
  }

  function showDialog(config) {
    closeDialog();
    var trigger = document.activeElement;
    var rootElement = byId("dialogRoot");
    rootElement.innerHTML = Components.ConfirmationDialog({
      id: "confirmationDialog",
      title: config.title,
      description: config.description,
      count: config.count,
      singular: config.singular,
      plural: config.plural,
      confirmLabel: config.confirmLabel || "Confirmar",
      cancelLabel: config.cancelLabel || "Cancelar",
      confirmAction: "confirm-current-dialog",
      destructive: Boolean(config.destructive),
      icon: config.icon,
      tone: config.tone,
    });
    var dialog = byId("confirmationDialog");
    var bodyAnchor = dialog.querySelector(".dialog-actions");
    if (config.field) {
      var label = document.createElement("label");
      label.className = "dialog-field";
      label.innerHTML = '<span>' + Utils.escapeHtml(config.field.label || "Valor") + "</span>" + dialogFieldMarkup(config.field);
      bodyAnchor.parentNode.insertBefore(label, bodyAnchor);
    }
    if (config.html) {
      var details = document.createElement("div");
      details.className = "dialog-rich-content";
      details.innerHTML = config.html;
      bodyAnchor.parentNode.insertBefore(details, bodyAnchor);
    }
    pendingDialog = { dialog: dialog, config: config, trigger: trigger };
    dialog.addEventListener("cancel", function (event) {
      event.preventDefault();
      closeDialog();
    });
    dialog.showModal();
    var first = dialog.querySelector("input, textarea, select") || dialog.querySelector('[data-action="confirm-current-dialog"]');
    if (first) root.requestAnimationFrame(function () { first.focus(); });
  }

  function dialogFieldMarkup(field) {
    if (field.type === "select") {
      return '<select id="dialogField" name="dialogField">' + (field.options || []).map(function (item) {
        var value = typeof item === "string" ? item : item.value;
        var label = typeof item === "string" ? (STATUS_LABELS[item] || item) : item.label;
        return '<option value="' + Utils.escapeHtml(value) + '"' + (String(value) === String(field.value || "") ? " selected" : "") + ">" + Utils.escapeHtml(label) + "</option>";
      }).join("") + "</select>";
    }
    if (field.type === "textarea") {
      return '<textarea id="dialogField" name="dialogField" rows="3" placeholder="' + Utils.escapeHtml(field.placeholder || "") + '">' + Utils.escapeHtml(field.value || "") + "</textarea>";
    }
    return '<input id="dialogField" name="dialogField" type="' + Utils.escapeHtml(field.type || "text") + '" value="' + Utils.escapeHtml(field.value || "") + '" placeholder="' + Utils.escapeHtml(field.placeholder || "") + '"' + (field.required ? " required" : "") + ">";
  }

  function confirmDialog() {
    if (!pendingDialog) return;
    var current = pendingDialog;
    var field = byId("dialogField");
    if (field && field.required && !field.value.trim()) {
      field.setAttribute("aria-invalid", "true");
      field.focus();
      showToast("Preencha o campo para continuar.", "error");
      return;
    }
    var value = field ? field.value : undefined;
    closeDialog(false);
    if (typeof current.config.onConfirm === "function") current.config.onConfirm(value);
  }

  function closeDialog(restoreFocus) {
    if (!pendingDialog) {
      byId("dialogRoot").innerHTML = "";
      return;
    }
    var current = pendingDialog;
    pendingDialog = null;
    if (current.dialog.open) current.dialog.close();
    byId("dialogRoot").innerHTML = "";
    if (restoreFocus !== false && current.trigger && current.trigger.focus) current.trigger.focus();
  }

  function showShortcuts() {
    var shortcuts = data.keyboardShortcuts || [
      { keys: "Ctrl + S", label: "Salvar imediatamente" },
      { keys: "Ctrl + Z", label: "Desfazer" },
      { keys: "Alt + ↑ / ↓", label: "Trocar funcionário" },
      { keys: "N / F / A / R / C", label: "Alterar o dia selecionado" },
    ];
    var html = '<ul class="shortcut-list">' + shortcuts.map(function (shortcut) {
      return "<li><span>" + Utils.escapeHtml(shortcut.label || shortcut.description || shortcut.acao || "Atalho") + "</span><kbd>" + Utils.escapeHtml(shortcut.keys || shortcut.key || shortcut.teclas || "—") + "</kbd></li>";
    }).join("") + "</ul>";
    showDialog({ title: "Atalhos de teclado", description: "Os atalhos de uma tecla ficam desativados enquanto você edita um campo.", confirmLabel: "Entendi", cancelLabel: "Fechar", html: html, onConfirm: function () {} });
  }

  function contextualizeImportAnalysis(result) {
    var company = currentCompany();
    var competence = currentCompetency();
    if (!result || !company || !competence) return result;
    var sourceRows = result.rows || result.linhas || [];
    var scopedRows = sourceRows.filter(function (row) {
      return idsEqual(row.companyId || row.empresa_id, company.id) && idsEqual(row.competenceId || row.competencia_id, competence.id);
    });
    var scopedEmployees = {};
    var scopedDates = {};
    var punchCount = 0;
    scopedRows.forEach(function (row) {
      if (row.employeeId !== undefined && row.employeeId !== null) scopedEmployees[String(row.employeeId)] = true;
      if (row.date || row.data) scopedDates[String(row.date || row.data)] = true;
      punchCount += (row.originalPunches || row.batidasOriginais || []).length;
    });
    result.companyId = company.id;
    result.companyName = company.name || company.nome;
    result.competenceId = competence.id;
    result.competenceLabel = competence.label || Utils.formatCompetence(competence);
    result.rows = scopedRows;
    result.linhas = scopedRows;
    result.employeeCount = Object.keys(scopedEmployees).length;
    result.recordCount = scopedRows.length;
    result.dayCount = Object.keys(scopedDates).length;
    result.punchCount = punchCount;
    result.pendingCount = scopedRows.filter(function (row) { return row.hasPendingIssue || row.temPendencia; }).length;
    return result;
  }

  function analyzeImport() {
    if (!state.selectedImportFile) {
      state.selectedImportFile = { name: "ALOG_001.txt", size: 68420, type: "text/plain", demo: true };
      showToast("Arquivo de demonstração selecionado.", "info", "ALOG_001.txt não será enviado.");
      render();
    }
    var button = document.querySelector('[data-action="analyze-import"][type="submit"]');
    if (button) {
      button.disabled = true;
      button.textContent = "Analisando...";
    }
    var analysisCompanyId = state.selectedCompanyId;
    var analysisCompetenceId = state.selectedCompetenceId;
    root.setTimeout(function () {
      if (!idsEqual(analysisCompanyId, state.selectedCompanyId) || !idsEqual(analysisCompetenceId, state.selectedCompetenceId)) return;
      var result = contextualizeImportAnalysis(Utils.safeClone(data.importAnalysis || data.analiseImportacao));
      result.fileName = state.selectedImportFile.name;
      result.requestedType = state.importType;
      var extension = String(state.selectedImportFile.name || "").split(".").pop().toLowerCase();
      var detectedType = state.importType === "auto"
        ? ({ txt: "txt_clock", xls: "xls_legacy", xlsx: "xlsx", pdf: "scanned", png: "scanned", jpg: "scanned", jpeg: "scanned" }[extension] || "txt_clock")
        : state.importType;
      result.detectedType = detectedType;
      result.detectedFormat = {
        txt_clock: "TXT AFD",
        xls_legacy: "XLS legado",
        xlsx: "XLSX",
        scanned: "Imagem ou PDF · leitura sugerida",
      }[detectedType] || result.detectedFormat;
      if (detectedType === "scanned") {
        result.employeeCount = 1;
        result.punchCount = 11;
        result.recordCount = 3;
        result.dayCount = 3;
        result.pendingCount = 2;
      }
      result.saved = false;
      state.importAnalysis = result;
      state.importPreviewFilter = "all";
      state.importPreviewEmployeeId = "";
      render();
      showToast("Análise simulada concluída.", "success", result.pendingCount + " pendências encontradas; nada foi salvo.");
    }, 720);
  }

  function discardImport() {
    showDialog({
      title: "Descartar esta análise?",
      description: "A prévia e o arquivo selecionado serão removidos deste protótipo. Nenhum dado original será alterado.",
      confirmLabel: "Descartar análise",
      destructive: true,
      onConfirm: function () {
        state.importAnalysis = false;
        state.selectedImportFile = null;
        state.importPreviewFilter = "all";
        state.importPreviewEmployeeId = "";
        navigate("imports");
        showToast("Análise descartada.", "success");
      },
    });
  }

  function saveImportAndReview() {
    if (!state.importAnalysis || typeof state.importAnalysis !== "object" || !(state.importAnalysis.rows || []).length) {
      showToast("Analise um arquivo desta competência antes de iniciar a conferência.", "warning");
      navigate("imports");
      return;
    }
    showDialog({
      title: "Salvar importação e iniciar conferência?",
      description: "A interpretação sugerida será adicionada à competência como uma versão ainda não conferida. As batidas originais continuarão preservadas.",
      confirmLabel: "Salvar e conferir",
      icon: "check_circle",
      tone: "info",
      onConfirm: function () {
        if (state.importAnalysis && typeof state.importAnalysis === "object") state.importAnalysis.saved = true;
        var competence = currentCompetency();
        if (competence) {
          competence.status = "em_conferencia";
          competence.statusLabel = "Em conferência";
        }
        var importedEmployeeId = state.importAnalysis.rows[0] && state.importAnalysis.rows[0].employeeId;
        var employee = companyEmployees().find(function (item) { return idsEqual(item.id, importedEmployeeId); }) || currentEmployee() || companyEmployees()[0] || null;
        state.selectedEmployeeId = employee ? employee.id : null;
        var firstDay = employee ? employeeDays(employee.id)[0] : null;
        state.selectedDayId = firstDay ? firstDay.id : null;
        state.reviewFilter = "all";
        state.selectedDayIds = [];
        navigate("review");
        showToast("Importação salva como prévia.", "success", "A conferência continua pendente.");
      },
    });
  }

  function setSelectedFile(file) {
    if (!file) return;
    state.selectedImportFile = { name: file.name, size: file.size, type: file.type, lastModified: file.lastModified, file: file };
    state.importAnalysis = false;
    render();
  }

  function selectCompetency(id, openDetail) {
    var competency = competencies().find(function (item) { return idsEqual(item.id, id); });
    if (!competency) return;
    navigate({
      view: openDetail === false ? "company-competencies" : "competency-summary",
      companyId: competency.companyId || competency.empresa_id,
      competenceId: openDetail === false ? null : competency.id,
    });
  }

  function openCompetencyArea(id, requestedView) {
    var competency = competencies().find(function (item) { return idsEqual(item.id, id); });
    if (!competency) return navigate("companies");
    var view = routeView(requestedView || "competency-summary");
    if (COMPETENCY_VIEWS.indexOf(view) === -1) view = "competency-summary";
    navigate({
      view: view,
      companyId: competency.companyId || competency.empresa_id,
      competenceId: competency.id,
    });
  }

  function openCompany(id, requestedView) {
    var company = companies().find(function (item) { return idsEqual(item.id, id); });
    if (!company) return navigate("companies");
    var view = routeView(requestedView || "company-overview");
    if (COMPANY_VIEWS.indexOf(view) === -1) view = "company-overview";
    navigate({ view: view, companyId: company.id, competenceId: null });
  }

  function selectEmployee(id) {
    var employee = companyEmployees().find(function (item) { return idsEqual(item.id, id); });
    if (!employee) return;
    state.selectedEmployeeId = employee.id;
    state.selectedDayIds = [];
    var visible = visibleReviewDays();
    state.selectedDayId = visible[0] ? visible[0].id : null;
    render();
  }

  function moveEmployee(direction) {
    var list = companyEmployees();
    var index = list.findIndex(function (item) { return idsEqual(item.id, state.selectedEmployeeId); });
    var nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= list.length) {
      showToast(direction < 0 ? "Este é o primeiro funcionário." : "Este é o último funcionário.", "info");
      return;
    }
    selectEmployee(list[nextIndex].id);
  }

  function selectDay(dayId, shouldRender) {
    if (!findDay(dayId)) return;
    state.selectedDayId = dayId;
    if (shouldRender !== false) render();
  }

  function toggleDaySelection(dayId, checked) {
    var exists = state.selectedDayIds.some(function (id) { return idsEqual(id, dayId); });
    if (checked && !exists) state.selectedDayIds.push(dayId);
    if (!checked && exists) state.selectedDayIds = state.selectedDayIds.filter(function (id) { return !idsEqual(id, dayId); });
    render();
  }

  function toggleAllDays(checked) {
    state.selectedDayIds = checked ? visibleReviewDays().map(function (day) { return day.id; }) : [];
    render();
  }

  function setDayStatus(day, status, options) {
    if (!day) return;
    if (dayIsConfirmed(day) && !(options && options.allowConfirmed)) {
      showToast("Reabra a conferência antes de alterar este dia.", "warning");
      return;
    }
    var previous = day.status;
    day.status = status;
    day.statusLabel = STATUS_LABELS[status] || status;
    if (day.current) {
      day.current.situation = status;
      day.current.status = status;
      day.current.situacao = status;
    }
    if (day.review) {
      day.review.status = status;
      day.review.statusLabel = day.statusLabel;
    }
    if (!(options && options.noUndo)) {
      state.undoStack.push({ type: "status", dayId: day.id, previous: previous, next: status });
    }
    addHistory(day, "Situação alterada de " + (STATUS_LABELS[previous] || previous || "não informada") + " para " + day.statusLabel + ".", "Marina Souza");
    queueAutosave();
    render();
  }

  function setStatusForSelected(status) {
    var day = findDay(state.selectedDayId);
    if (day) setDayStatus(day, status);
  }

  function confirmDay(day, options) {
    if (!day || dayIsConfirmed(day)) return;
    day.confirmed = true;
    day.conferido = true;
    day.reviewState = "confirmed";
    day.confirmedAt = new Date().toISOString();
    day.confirmedResult = Utils.safeClone(day.current);
    day.resultadoConferido = day.confirmedResult;
    if (day.review) {
      day.review.state = "confirmed";
      day.review.confirmed = true;
      day.review.confirmedAt = day.confirmedAt;
      day.review.lastConfirmedSnapshot = day.confirmedResult;
    }
    addHistory(day, "Dia marcado como conferido.", "Marina Souza");
    updateEmployeeProgress(day.employeeId || day.funcionario_id);
    queueAutosave();
    if (!(options && options.silent)) showToast("Dia conferido.", "success", "Salvar e conferir continuam sendo ações independentes.");
  }

  function reopenDay(day) {
    if (!day || !dayIsConfirmed(day)) return;
    day.confirmed = false;
    day.conferido = false;
    day.reviewState = "reopened";
    if (day.review) {
      day.review.state = "reopened";
      day.review.confirmed = false;
      day.review.reopenedAt = new Date().toISOString();
    }
    addHistory(day, "Conferência reaberta para ajustes.", "Marina Souza");
    updateEmployeeProgress(day.employeeId || day.funcionario_id);
    queueAutosave();
    render();
    showToast("Conferência reaberta.", "success", "O último resultado conferido foi preservado no histórico.");
  }

  function updateEmployeeProgress(employeeId) {
    var progressList = data.employeeProgress || data.progressoFuncionarios || [];
    var item = progressList.find(function (progress) { return idsEqual(progress.employeeId || progress.funcionario_id, employeeId); });
    if (!item) return;
    var employeeDayList = employeeDays(employeeId);
    item.confirmedDayCount = employeeDayList.filter(dayIsConfirmed).length;
    item.pendingCount = employeeDayList.filter(function (day) { return !dayIsConfirmed(day) && (day.status === "conferir" || day.status === "inconsistente" || (day.issues || []).some(function (issue) { return issue.resolved !== true; })); }).length;
    item.progress = item.eligibleDayCount ? Math.round(item.confirmedDayCount / item.eligibleDayCount * 100) : 0;
  }

  function addHistory(day, description, actor) {
    var history = day.history || day.historico || [];
    var now = new Date();
    history.push({
      id: "history-ui-" + now.getTime() + "-" + history.length,
      at: now.toISOString(),
      timeLabel: now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
      actor: actor || "Marina Souza",
      description: description,
      title: description,
      type: "manual",
    });
    day.history = history;
    day.historico = history;
  }

  function recalculateDay(day) {
    var result = Utils.calculateJourney(currentSlots(day), day.expectedMinutes || day.jornadaPrevistaMinutos);
    day.workedMinutes = result.workedMinutes;
    day.jornadaApuradaMinutos = result.workedMinutes;
    day.balanceMinutes = result.balanceMinutes;
    day.saldoMinutos = result.balanceMinutes;
    if (day.current) {
      day.current.workedMinutes = result.workedMinutes;
      day.current.expectedMinutes = result.expectedMinutes;
      day.current.balanceMinutes = result.balanceMinutes;
    }
  }

  function applySlot(day, field, value) {
    if (!day.current) day.current = {};
    (SLOT_ALIASES[field] || [field]).forEach(function (alias) { day.current[alias] = value; });
    day.currentInterpretation = day.current;
    day.interpretacaoAtual = day.current;
    day.userEdition = Utils.safeClone(day.current);
    day.edited = day.userEdition;
    day.edicaoUsuario = day.userEdition;
    recalculateDay(day);
  }

  function queueAutosave(force) {
    root.clearTimeout(autosaveTimer);
    state.autosaveRevision += 1;
    var revision = state.autosaveRevision;
    if (!state.settings.autosave && !force) {
      state.autosaveStatus = "saved";
      updateAutosaveIndicator();
      return;
    }
    state.autosaveStatus = "saving";
    updateAutosaveIndicator();
    autosaveTimer = root.setTimeout(function () {
      if (revision !== state.autosaveRevision) return;
      state.autosaveStatus = "saved";
      updateAutosaveIndicator();
    }, force ? 280 : 680);
  }

  function setAutosaveError() {
    root.clearTimeout(autosaveTimer);
    state.autosaveRevision += 1;
    state.autosaveStatus = "error";
    updateAutosaveIndicator();
  }

  function updateAutosaveIndicator() {
    var current = document.querySelector('[data-component="autosave-indicator"]');
    if (current) current.outerHTML = Components.AutosaveIndicator({ state: state.autosaveStatus });
  }

  function saveNow() {
    if (document.querySelector('.time-cell-input[aria-invalid="true"]')) {
      setAutosaveError();
      showToast("Corrija o horário inválido antes de salvar.", "error");
      return;
    }
    queueAutosave(true);
    root.setTimeout(function () { showToast("Alterações salvas.", "success"); }, 320);
  }

  function cellSelector(dayId, field) {
    return '.editable-time-cell[data-day-id="' + cssEscape(dayId) + '"][data-field="' + cssEscape(field) + '"]';
  }

  function cssEscape(value) {
    return root.CSS && typeof root.CSS.escape === "function" ? root.CSS.escape(String(value)) : String(value).replace(/(["\\])/g, "\\$1");
  }

  function focusCell(dayId, field) {
    var cell = document.querySelector(cellSelector(dayId, field));
    if (!cell) return;
    document.querySelectorAll(".editable-time-cell.is-active").forEach(function (item) { item.classList.remove("is-active"); item.tabIndex = -1; });
    cell.classList.add("is-active");
    cell.tabIndex = 0;
    cell.focus({ preventScroll: false });
  }

  function beginEditing(cell, seed) {
    if (!cell || editSession) return;
    var day = findDay(cell.dataset.dayId);
    if (!day) return;
    state.selectedDayId = day.id;
    if (dayIsConfirmed(day) || cell.classList.contains("is-disabled")) {
      showToast("Este dia está conferido.", "warning", "Use “Reabrir conferência” antes de editar horários.");
      return;
    }
    var original = cell.dataset.value || "";
    var value = seed !== undefined && seed !== null ? seed : original;
    var editorLabel = cell.getAttribute("aria-label") || "horário";
    cell.classList.add("is-editing");
    cell.tabIndex = -1;
    cell.innerHTML = '<input class="time-cell-input cell-editor" type="text" inputmode="numeric" autocomplete="off" spellcheck="false" aria-label="Editar ' + Utils.escapeHtml(editorLabel) + '" value="' + Utils.escapeHtml(value) + '">';
    var input = cell.querySelector("input");
    editSession = { cell: cell, input: input, dayId: day.id, field: cell.dataset.field, original: original, canceled: false, committing: false };
    input.focus();
    if (seed === undefined || seed === null) input.select();
    else input.setSelectionRange(input.value.length, input.value.length);
  }

  function cancelEditing() {
    if (!editSession) return;
    var session = editSession;
    session.canceled = true;
    editSession = null;
    restoreCell(session.cell, session.original);
    session.cell.focus();
  }

  function restoreCell(cell, value) {
    if (!cell || !cell.isConnected) return;
    cell.classList.remove("is-editing", "is-invalid", "has-warning");
    cell.dataset.value = value || "";
    cell.tabIndex = 0;
    cell.removeAttribute("aria-invalid");
    cell.innerHTML = '<span class="time-cell-value">' + (value ? Utils.escapeHtml(value) : '<span class="empty-value" aria-hidden="true">—</span><span class="sr-only">Sem horário</span>') + "</span>";
  }

  function finishEditing(options) {
    if (!editSession || editSession.committing) return true;
    var session = editSession;
    session.committing = true;
    var parsed = Utils.validateTimeInput(session.input.value);
    if (!parsed.valid) {
      session.committing = false;
      session.input.setAttribute("aria-invalid", "true");
      session.cell.classList.add("is-invalid");
      var oldMessage = session.cell.querySelector(".cell-message");
      if (oldMessage) oldMessage.remove();
      var message = document.createElement("span");
      var messageId = session.cell.id + "-runtime-error";
      message.id = messageId;
      message.className = "cell-message is-error";
      message.textContent = parsed.error;
      session.cell.appendChild(message);
      session.input.setAttribute("aria-describedby", messageId);
      setAutosaveError();
      session.input.focus();
      showToast("Horário impossível.", "error", parsed.error);
      return false;
    }

    var normalized = parsed.normalized;
    var day = findDay(session.dayId);
    var move = options && options.move;
    editSession = null;
    if (normalized === session.original) {
      restoreCell(session.cell, normalized);
      if (move) moveFromCell(session.dayId, session.field, move);
      return true;
    }

    applySlot(day, session.field, normalized);
    state.undoStack.push({ type: "time", dayId: day.id, field: session.field, previous: session.original, next: normalized });
    if (!(day.issues || []).some(function (issue) { return issue.type === "manual_change" && issue.resolved !== true; })) {
      var issue = { id: "issue-manual-" + day.id, dayId: day.id, type: "manual_change", severity: "warning", message: "Horário alterado manualmente.", resolved: false };
      day.issues.push(issue);
    }
    addHistory(day, fieldLabel(session.field) + " alterada de " + (session.original || "—") + " para " + (normalized || "—") + ".", "Marina Souza");
    queueAutosave();
    if (parsed.unusual && state.settings.unusualTimeAlerts) {
      showToast("Horário incomum aceito.", "warning", parsed.warning);
    }
    renderFocus = movementTarget(session.dayId, session.field, move);
    render();
    return true;
  }

  function fieldLabel(field) {
    return { entry: "Entrada", breakStart: "Saída do intervalo", breakEnd: "Retorno", exit: "Saída" }[field] || "Horário";
  }

  function gridCells() {
    return Array.prototype.slice.call(document.querySelectorAll(".attendance-table .editable-time-cell:not(.is-disabled)"));
  }

  function movementTarget(dayId, field, movement) {
    if (!movement) return null;
    var cells = gridCells();
    var currentIndex = cells.findIndex(function (cell) { return idsEqual(cell.dataset.dayId, dayId) && cell.dataset.field === field; });
    if (currentIndex < 0) return null;
    var target = null;
    if (movement === "next") target = cells[currentIndex + 1];
    if (movement === "previous") target = cells[currentIndex - 1];
    if (movement === "down" || movement === "up") {
      var direction = movement === "down" ? 1 : -1;
      var rows = visibleReviewDays();
      var rowIndex = rows.findIndex(function (day) { return idsEqual(day.id, dayId); });
      var nextDay = rows[rowIndex + direction];
      if (nextDay) target = cells.find(function (cell) { return idsEqual(cell.dataset.dayId, nextDay.id) && cell.dataset.field === field; });
    }
    return target ? { dayId: target.dataset.dayId, field: target.dataset.field } : { dayId: dayId, field: field };
  }

  function moveFromCell(dayId, field, movement) {
    var target = movementTarget(dayId, field, movement);
    if (target) focusCell(target.dayId, target.field);
  }

  function undoLastChange() {
    var change = state.undoStack.pop();
    if (!change) {
      showToast("Não há alterações para desfazer.", "info");
      return;
    }
    var day = findDay(change.dayId);
    if (!day) return;
    if (dayIsConfirmed(day)) {
      state.undoStack.push(change);
      showToast("Reabra a conferência antes de desfazer.", "warning");
      return;
    }
    if (change.type === "time") {
      applySlot(day, change.field, change.previous);
      addHistory(day, "Alteração desfeita: " + fieldLabel(change.field) + " restaurada para " + (change.previous || "—") + ".", "Marina Souza");
      renderFocus = { dayId: day.id, field: change.field };
    } else if (change.type === "status") {
      setDayStatus(day, change.previous, { noUndo: true });
      return;
    } else if (change.type === "observation") {
      setObservation(day, change.previous, { noUndo: true, silent: true });
    }
    queueAutosave();
    render();
    showToast("Última alteração desfeita.", "success");
  }

  function setObservation(day, value, options) {
    if (!day || dayIsConfirmed(day)) {
      showToast("Reabra a conferência antes de editar a observação.", "warning");
      return;
    }
    var previous = day.observation || day.observacao || (day.current && day.current.observation) || "";
    day.observation = value;
    day.observacao = value;
    if (day.current) {
      day.current.observation = value;
      day.current.observacao = value;
    }
    if (!(options && options.noUndo)) state.undoStack.push({ type: "observation", dayId: day.id, previous: previous, next: value });
    addHistory(day, value ? "Observação adicionada ou atualizada." : "Observação removida.", "Marina Souza");
    queueAutosave();
    if (!(options && options.silent)) {
      render();
      showToast("Observação salva.", "success");
    }
  }

  function openObservationDialog(day, bulk) {
    var targets = bulk ? state.selectedDayIds.map(findDay).filter(Boolean) : [day];
    showDialog({
      title: bulk ? "Adicionar observação em massa" : "Observação do dia",
      description: bulk ? "A mesma observação será adicionada aos registros selecionados. As batidas originais não serão alteradas." : "A observação faz parte da interpretação atual e ficará registrada no histórico.",
      count: bulk ? targets.length : undefined,
      confirmLabel: "Salvar observação",
      field: { type: "textarea", label: "Observação", value: bulk ? "" : (day.observation || day.observacao || ""), placeholder: "Descreva o ajuste ou a decisão tomada" },
      onConfirm: function (value) {
        targets.forEach(function (target) { setObservation(target, value.trim(), { silent: true }); });
        state.selectedDayIds = bulk ? [] : state.selectedDayIds;
        render();
        showToast("Observação aplicada a " + targets.length + " registro" + (targets.length === 1 ? "" : "s") + ".", "success");
      },
    });
  }

  function openStatusDialog(day, bulk) {
    var targets = bulk ? state.selectedDayIds.map(findDay).filter(Boolean) : [day];
    showDialog({
      title: bulk ? "Definir situação em massa" : "Alterar situação do dia",
      description: "A situação é independente da confirmação. Batidas originais nunca serão modificadas.",
      count: bulk ? targets.length : undefined,
      confirmLabel: "Aplicar situação",
      field: { type: "select", label: "Situação", value: day ? day.status : "normal", options: Object.keys(STATUS_LABELS).map(function (key) { return { value: key, label: STATUS_LABELS[key] }; }) },
      onConfirm: function (value) {
        targets.forEach(function (target) { setDayStatus(target, value, { noUndo: true }); });
        state.selectedDayIds = bulk ? [] : state.selectedDayIds;
        render();
        showToast("Situação aplicada a " + targets.length + " registro" + (targets.length === 1 ? "" : "s") + ".", "success");
      },
    });
  }

  function confirmSelectedDays() {
    var targets = state.selectedDayIds.map(findDay).filter(Boolean);
    showDialog({
      title: "Marcar dias como conferidos?",
      description: "Será criado um resultado conferido para cada registro. As batidas originais e a sugestão permanecerão intactas.",
      count: targets.length,
      confirmLabel: "Marcar como conferidos",
      icon: "check_circle",
      onConfirm: function () {
        targets.forEach(function (day) { confirmDay(day, { silent: true }); });
        state.selectedDayIds = [];
        render();
        showToast(targets.length + " registros marcados como conferidos.", "success");
      },
    });
  }

  function keepInterpretation(day) {
    if (!day || dayIsConfirmed(day)) return;
    (day.issues || []).forEach(function (issue) { issue.resolved = true; issue.resolution = "Interpretação mantida pelo usuário"; });
    setDayStatus(day, "normal", { noUndo: true });
    addHistory(day, "Interpretação sugerida mantida pelo usuário.", "Marina Souza");
    render();
    showToast("Interpretação mantida.", "success", "O dia ainda precisa ser marcado como conferido.");
  }

  function focusFirstTime(dayId) {
    var day = findDay(dayId || state.selectedDayId);
    if (!day) return;
    if (dayIsConfirmed(day)) {
      showToast("Reabra a conferência antes de editar.", "warning");
      return;
    }
    focusCell(day.id, "entry");
  }

  function openOriginal(fileId) {
    var file = findFile(fileId);
    if (file && (file.extension === "jpg" || file.extension === "png" || file.sourceType === "image")) {
      navigate("ocr");
      return;
    }
    showToast("Arquivo original aberto em modo somente leitura.", "info", file ? file.name : "A visualização é simulada neste protótipo.");
  }

  function updateOcr(action, element) {
    var documentData = state.ocr.document;
    if (action === "ocr-zoom-in") documentData.zoom = Math.min(180, documentData.zoom + 10);
    if (action === "ocr-zoom-out") documentData.zoom = Math.max(50, documentData.zoom - 10);
    if (action === "ocr-rotate") documentData.rotation = (documentData.rotation + 90) % 360;
    if (action === "ocr-next-page") documentData.page = Math.min(documentData.pageCount, documentData.page + 1);
    if (action === "ocr-previous-page") documentData.page = Math.max(1, documentData.page - 1);
    if (action === "ocr-contrast" && element) documentData.contrast = Number(element.value);
    render();
  }

  function acceptOcrPreview() {
    var company = currentCompany();
    var competence = currentCompetency();
    var sourceFile = findFile(state.ocr && state.ocr.fileId);
    var sourceMatchesContext = sourceFile && company && competence &&
      idsEqual(sourceFile.companyId || sourceFile.empresa_id, company.id) &&
      idsEqual(sourceFile.competenceId || sourceFile.competencia_id, competence.id);
    var extractedRows = state.ocr && (state.ocr.extractedRows || state.ocr.linhasExtraidas) || [];
    if (!sourceMatchesContext || !extractedRows.length) {
      showToast("Não há leitura simulada disponível para esta competência.", "warning", "Volte para Importações e selecione outro arquivo.");
      navigate("imports");
      return;
    }

    var previewRows = extractedRows.map(function (row) {
      var employee = companyEmployees().find(function (item) {
        return String(item.name || item.nome || "").toLowerCase() === String(row.employeeName || row.funcionario || "").toLowerCase();
      }) || currentEmployee();
      var suggestion = {
        entry: row.entry || row.entrada || null,
        breakStart: row.breakStart || row.saidaIntervalo || null,
        breakEnd: row.breakEnd || row.retorno || null,
        exit: row.exit || row.saida || null,
      };
      var hasUnknown = Object.keys(suggestion).some(function (key) { return suggestion[key] === "?"; });
      var suggestedStatus = row.suggestedStatus || row.statusSugerido || (hasUnknown ? "inconsistente" : "conferir");
      return {
        id: "preview-" + row.id,
        fileId: sourceFile.id,
        companyId: company.id,
        competenceId: competence.id,
        employeeId: employee ? employee.id : null,
        employeeName: row.employeeName || row.funcionario || (employee && (employee.name || employee.nome)) || "Não identificado",
        date: row.date || row.data,
        originalPunches: [],
        suggestion: suggestion,
        status: suggestedStatus,
        statusLabel: STATUS_LABELS[suggestedStatus] || suggestedStatus,
        observation: row.observation || row.observacao || "Leitura sugerida a partir da imagem.",
        hasPendingIssue: suggestedStatus === "conferir" || suggestedStatus === "inconsistente" || hasUnknown,
        source: { fileId: sourceFile.id, fileName: sourceFile.name || sourceFile.nome, importedAt: sourceFile.uploadedAt },
      };
    });
    var employeeIds = {};
    var punchCount = 0;
    previewRows.forEach(function (row) {
      if (row.employeeId !== null) employeeIds[String(row.employeeId)] = true;
      Object.keys(row.suggestion).forEach(function (key) {
        if (row.suggestion[key] && row.suggestion[key] !== "?") punchCount += 1;
      });
    });
    state.importAnalysis = {
      id: "analysis-ocr-" + sourceFile.id,
      fileId: sourceFile.id,
      fileName: state.selectedImportFile ? state.selectedImportFile.name : (state.ocr.document && state.ocr.document.fileName) || sourceFile.name,
      companyId: company.id,
      companyName: company.name || company.nome,
      competenceId: competence.id,
      competenceLabel: competence.label || Utils.formatCompetence(competence),
      requestedType: "scanned",
      detectedType: "scanned",
      detectedFormat: "Imagem ou PDF · leitura sugerida",
      employeeCount: Object.keys(employeeIds).length,
      punchCount: punchCount,
      dayCount: previewRows.length,
      recordCount: previewRows.length,
      pendingCount: previewRows.filter(function (row) { return row.hasPendingIssue; }).length,
      analyzedAt: new Date().toISOString(),
      saved: false,
      rows: previewRows,
    };
    state.importPreviewFilter = "all";
    state.importPreviewEmployeeId = "";
    navigate("import-preview");
  }

  function closeCompetency() {
    var competency = currentCompetency();
    showDialog({
      title: "Fechar esta competência?",
      description: "O fechamento não é automático. Neste protótipo, a situação será alterada somente após sua confirmação.",
      confirmLabel: "Fechar competência",
      destructive: true,
      onConfirm: function () {
        competency.status = "fechada";
        competency.statusLabel = "Fechada";
        competency.closedAt = new Date().toISOString();
        competency.progress = 100;
        render();
        showToast("Competência fechada no protótipo.", "success");
      },
    });
  }

  function resetDemo() {
    showDialog({
      title: "Restaurar dados simulados?",
      description: "Todas as edições desta sessão serão descartadas e os mocks voltarão ao estado inicial.",
      confirmLabel: "Restaurar demonstração",
      destructive: true,
      onConfirm: function () {
        root.clearTimeout(autosaveTimer);
        data = Mocks.reset();
        var collapsed = state.sidebarCollapsed;
        state = createInitialState();
        state.sidebarCollapsed = collapsed;
        navigate("companies");
        showToast("Dados simulados restaurados.", "success");
      },
    });
  }

  function openSimpleEntityDialog(kind, id) {
    var isCompany = kind === "company";
    var list = isCompany ? companies() : employees();
    var entity = id ? list.find(function (item) { return idsEqual(item.id, id); }) : null;
    var noun = isCompany ? "empresa" : "funcionário";
    showDialog({
      title: (entity ? "Editar " : "Novo ") + noun,
      description: "Cadastro local para demonstrar a interface. Nenhum dado será enviado ao backend.",
      confirmLabel: entity ? "Salvar alterações" : "Adicionar " + noun,
      field: { type: "text", label: isCompany ? "Nome da empresa" : "Nome do funcionário", value: entity ? (entity.name || entity.nome) : "", required: true },
      onConfirm: function (value) {
        if (entity) {
          entity.name = value.trim();
          entity.nome = value.trim();
        } else {
          var nextId = Math.max.apply(null, list.map(function (item) { return Number(item.id) || 0; })) + 1;
          if (isCompany) {
            list.push({ id: nextId, name: value.trim(), nome: value.trim(), legalName: value.trim() + " Ltda.", cnpj: "Não informado", active: true, ativa: true });
          } else {
            list.push({ id: nextId, companyId: state.selectedCompanyId, empresa_id: state.selectedCompanyId, name: value.trim(), nome: value.trim(), code: String(nextId), codigo: String(nextId), role: "Não informado", cargo: "Não informado", active: true, ativo: true });
          }
        }
        render();
        showToast((isCompany ? "Empresa" : "Funcionário") + " salvo no protótipo.", "success");
      },
    });
  }

  function newCompetency() {
    var company = currentCompany();
    if (!company) {
      showToast("Selecione uma empresa antes de criar a competência.", "warning");
      navigate("companies");
      return;
    }
    showDialog({
      title: "Nova competência",
      description: "Crie uma pasta digital simulada para a empresa selecionada.",
      confirmLabel: "Criar competência",
      field: { type: "text", label: "Competência", value: "08/2026", placeholder: "MM/AAAA", required: true },
      onConfirm: function (value) {
        if (!/^\d{2}\/\d{4}$/.test(value.trim())) {
          showToast("Use a competência no formato MM/AAAA.", "error");
          return;
        }
        var parts = value.trim().split("/");
        var nextId = Math.max.apply(null, competencies().map(function (item) { return Number(item.id) || 0; })) + 1;
        var item = { id: nextId, companyId: company.id, empresa_id: company.id, month: Number(parts[0]), mes: Number(parts[0]), year: Number(parts[1]), ano: Number(parts[1]), label: value.trim(), status: "aberta", statusLabel: "Aberta", employeeCount: companyEmployees().length, pendingCount: 0, fileCount: 0, progress: 0, confirmedEmployees: 0, pendingEmployees: companyEmployees().length, inconsistentDays: 0, updatedAt: new Date().toISOString() };
        competencies().push(item);
        navigate({ view: "competency-summary", companyId: company.id, competenceId: nextId });
        showToast("Competência criada no protótipo.", "success");
      },
    });
  }

  function handleClick(event) {
    var element = event.target.closest("[data-action]");
    if (!element) return;
    var action = element.dataset.action;

    if (action === "search-companies") return;
    if (element.matches('input[type="checkbox"], input[type="radio"], input[type="file"], select, input[type="range"]')) return;
    if (action === "analyze-import" && element.type === "submit") return;
    if (action !== "edit-time") event.preventDefault();

    if (action === "navigate") return navigate(element.dataset.route || element.dataset.view);
    if (action === "open-company") return openCompany(element.dataset.companyId, element.dataset.route);
    if (action === "switch-company") return navigate("companies");
    if (action === "toggle-sidebar") return toggleSidebar();
    if (action === "show-shortcuts") return showShortcuts();
    if (action === "show-notifications") {
      var notificationCompany = currentCompany();
      var notificationCompetence = currentCompetency();
      return showToast(
        notificationCompetence ? (notificationCompetence.pendingCount || 0) + " itens merecem atenção." : "Nenhuma competência selecionada.",
        notificationCompetence && notificationCompetence.pendingCount ? "warning" : "info",
        notificationCompany && notificationCompetence ? "Pendências em " + (notificationCompany.name || notificationCompany.nome) + " · " + (notificationCompetence.label || Utils.formatCompetence(notificationCompetence)) + "." : "Selecione uma empresa e uma competência para ver as pendências."
      );
    }
    if (action === "dismiss-toast") return byId(element.dataset.toastId) && byId(element.dataset.toastId).remove();
    if (action === "cancel-confirmation") return closeDialog();
    if (action === "confirm-current-dialog") return confirmDialog();
    if (action === "open-import-preview") {
      return navigate(state.importAnalysis && state.importAnalysis.detectedType === "scanned" ? "ocr" : "import-preview");
    }
    if (action === "discard-import" || action === "clear-import-file") return discardImport();
    if (action === "save-import-start-review") return saveImportAndReview();
    if (action === "back-from-import-preview") return navigate("imports");
    if (action === "open-competence") return selectCompetency(element.dataset.competenceId);
    if (action === "open-competence-area") return openCompetencyArea(element.dataset.competenceId, element.dataset.route || element.dataset.view);
    if (action === "open-employee-review") {
      var reviewEmployee = companyEmployees().find(function (item) { return idsEqual(item.id, element.dataset.employeeId); });
      if (!reviewEmployee || !currentCompetency()) return navigate("companies");
      state.selectedEmployeeId = reviewEmployee.id;
      var reviewDay = employeeDays(reviewEmployee.id)[0];
      state.selectedDayId = reviewDay ? reviewDay.id : null;
      state.selectedDayIds = [];
      return navigate("review");
    }
    if (action === "set-competency-tab") {
      var tabView = routeView(element.dataset.tab);
      if (tabView === "company-employees") return navigate(tabView);
      return navigate(COMPETENCY_VIEWS.indexOf(tabView) === -1 ? "competency-summary" : tabView);
    }
    if (action === "set-registrations-tab") { state.registrationsTab = element.dataset.tab; return render(); }
    if (action === "set-filter") {
      var scope = element.dataset.filterScope;
      if (scope === "review") { state.reviewFilter = element.dataset.filter; ensureReviewSelection(); }
      if (scope === "preview") state.importPreviewFilter = element.dataset.filter;
      if (scope === "competencies") state.competenciesStatusFilter = element.dataset.filter;
      return render();
    }
    if (action === "previous-employee") return moveEmployee(-1);
    if (action === "next-employee") return moveEmployee(1);
    if (action === "select-day") return selectDay(element.dataset.dayId);
    if (action === "edit-time") {
      var cell = element.closest(".editable-time-cell");
      if (!cell) return;
      if (!idsEqual(state.selectedDayId, cell.dataset.dayId)) {
        state.selectedDayId = cell.dataset.dayId;
        renderFocus = { dayId: cell.dataset.dayId, field: cell.dataset.field };
        render();
        root.requestAnimationFrame(function () { beginEditing(document.querySelector(cellSelector(renderFocus ? renderFocus.dayId : cell.dataset.dayId, renderFocus ? renderFocus.field : cell.dataset.field))); });
      } else beginEditing(cell);
      return;
    }
    if (action === "choose-situation") return openStatusDialog(findDay(element.dataset.dayId), false);
    if (action === "edit-observation" || action === "focus-observation") return openObservationDialog(findDay(element.dataset.dayId || state.selectedDayId), false);
    if (action === "confirm-day") { confirmDay(findDay(element.dataset.dayId || state.selectedDayId)); return render(); }
    if (action === "reopen-day") return reopenDay(findDay(element.dataset.dayId || state.selectedDayId));
    if (action === "set-day-absence") return setDayStatus(findDay(element.dataset.dayId || state.selectedDayId), "falta");
    if (action === "set-day-certificate") return setDayStatus(findDay(element.dataset.dayId || state.selectedDayId), "atestado");
    if (action === "set-day-dayoff") return setDayStatus(findDay(element.dataset.dayId || state.selectedDayId), "folga");
    if (action === "set-day-no-schedule") return setDayStatus(findDay(element.dataset.dayId || state.selectedDayId), "sem_expediente");
    if (action === "focus-first-time") return focusFirstTime(element.dataset.dayId);
    if (action === "keep-interpretation") return keepInterpretation(findDay(element.dataset.dayId || state.selectedDayId));
    if (action === "bulk-confirm") return confirmSelectedDays();
    if (action === "bulk-set-status") return openStatusDialog(null, true);
    if (action === "bulk-add-observation") return openObservationDialog(null, true);
    if (action === "save-now" || action === "retry-save") return saveNow();
    if (action === "open-original-file") return openOriginal(element.dataset.fileId);
    if (action === "open-source-region") return navigate("ocr");
    if (action.indexOf("ocr-") === 0) return updateOcr(action, element);
    if (action === "accept-ocr-preview") return acceptOcrPreview();
    if (action === "request-close-competence") return closeCompetency();
    if (action === "export-competence") return navigate("competency-exports");
    if (action === "preview-summary-report") return navigate("competency-summary");
    if (action === "export-excel") return showToast("Planilha preparada em modo demonstração.", "success", "A exportação real dependerá do backend de relatórios.");
    if (action === "open-print-report") return showToast("Prévia de impressão preparada.", "success", "Use a versão integrada ao backend para gerar o relatório definitivo.");
    if (action === "new-company") return openSimpleEntityDialog("company");
    if (action === "edit-company") return openSimpleEntityDialog("company", element.dataset.companyId);
    if (action === "new-employee") return openSimpleEntityDialog("employee");
    if (action === "edit-employee") return openSimpleEntityDialog("employee", element.dataset.employeeId);
    if (action === "new-competence") return newCompetency();
    if (action === "reset-demo-data") return resetDemo();
  }

  function handleChange(event) {
    var element = event.target.closest("[data-action]");
    if (!element) return;
    var action = element.dataset.action;
    if (action === "search-companies") return updateCompanySearch(element, false);
    if (action === "select-import-file" && element.files) return setSelectedFile(element.files[0]);
    if (action === "select-import-company") {
      var importCompanyId = asId(element.value);
      var first = competencies().find(function (item) { return idsEqual(item.companyId || item.empresa_id, importCompanyId); });
      return first ? openCompetencyArea(first.id, "imports") : openCompany(importCompanyId);
    }
    if (action === "select-import-competence") return openCompetencyArea(asId(element.value), "imports");
    if (action === "select-import-type") { state.importType = element.value; return; }
    if (action === "filter-preview-employee" || action === "filter-import-employee") { state.importPreviewEmployeeId = asId(element.value) || ""; return render(); }
    if (action === "filter-competencies-company") {
      return element.value ? openCompany(asId(element.value), "company-competencies") : navigate("companies");
    }
    if (action === "select-review-employee") return selectEmployee(asId(element.value));
    if (action === "toggle-day-selection") return toggleDaySelection(element.dataset.dayId, element.checked);
    if (action === "toggle-all-days") return toggleAllDays(element.checked);
    if (action === "select-report-company") return openCompany(asId(element.value), "company-reports");
    if (action === "select-settings-company") return openCompany(asId(element.value), "company-settings");
    if (action === "select-report-competence") return openCompetencyArea(asId(element.value), "competency-exports");
    if (action === "toggle-autosave") { state.settings.autosave = element.checked; return showToast(element.checked ? "Autosave ativado." : "Autosave desativado.", "info"); }
    if (action === "toggle-unusual-time-alert") { state.settings.unusualTimeAlerts = element.checked; return; }
    if (action === "toggle-single-key-shortcuts") { state.settings.singleKeyShortcuts = element.checked; return; }
    if (action === "ocr-contrast") return updateOcr(action, element);
    if (action === "edit-ocr-time") {
      var row = state.ocr.extractedRows.find(function (item) { return idsEqual(item.id, element.dataset.ocrRowId); });
      var parsed = Utils.validateTimeInput(element.value);
      if (!parsed.valid) { element.setAttribute("aria-invalid", "true"); showToast("Horário inválido na leitura sugerida.", "error", parsed.error); return; }
      row[element.dataset.field] = parsed.normalized;
      element.value = parsed.normalized;
      showToast("Campo da leitura sugerida atualizado.", "success");
      return;
    }
    if (action === "edit-ocr-observation") {
      var ocrRow = state.ocr.extractedRows.find(function (item) { return idsEqual(item.id, element.dataset.ocrRowId); });
      if (ocrRow) ocrRow.observation = element.value;
    }
  }

  function updateCompanySearch(element, preserveFocus) {
    var value = element ? element.value : "";
    if (state.companySearch === value && !preserveFocus) return;
    var selectionStart = element && element.selectionStart;
    var selectionEnd = element && element.selectionEnd;
    state.companySearch = value;
    render();
    if (!preserveFocus) return;
    root.requestAnimationFrame(function () {
      var input = document.querySelector('[data-action="search-companies"]');
      if (!input) return;
      input.focus({ preventScroll: true });
      if (typeof input.setSelectionRange === "function" && selectionStart !== null) {
        input.setSelectionRange(selectionStart, selectionEnd);
      }
    });
  }

  function handleInput(event) {
    var element = event.target.closest && event.target.closest('[data-action="search-companies"]');
    if (element) updateCompanySearch(element, true);
  }

  function handleSubmit(event) {
    var form = event.target.closest('form[data-action="analyze-import"]');
    if (!form) return;
    event.preventDefault();
    analyzeImport();
  }

  function isTextEditingTarget(target) {
    if (!target) return false;
    return target.matches("input, textarea, select, [contenteditable='true']") || Boolean(target.closest("dialog"));
  }

  function handleKeydown(event) {
    var target = event.target;
    if (target.classList && target.classList.contains("time-cell-input")) {
      if (event.key === "Escape") { event.preventDefault(); cancelEditing(); return; }
      if (event.key === "Enter") { event.preventDefault(); finishEditing({ move: "down" }); return; }
      if (event.key === "Tab") { event.preventDefault(); finishEditing({ move: event.shiftKey ? "previous" : "next" }); return; }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); if (finishEditing({ move: null })) saveNow(); return; }
      return;
    }

    var cell = target.closest && target.closest(".editable-time-cell");
    if (cell && !isTextEditingTarget(target)) {
      if (event.key === "Enter" || event.key === "F2") { event.preventDefault(); beginEditing(cell); return; }
      if (event.key === "ArrowUp") { event.preventDefault(); moveFromCell(cell.dataset.dayId, cell.dataset.field, "up"); return; }
      if (event.key === "ArrowDown") { event.preventDefault(); moveFromCell(cell.dataset.dayId, cell.dataset.field, "down"); return; }
      if (event.key === "ArrowLeft") { event.preventDefault(); moveFromCell(cell.dataset.dayId, cell.dataset.field, "previous"); return; }
      if (event.key === "ArrowRight") { event.preventDefault(); moveFromCell(cell.dataset.dayId, cell.dataset.field, "next"); return; }
      if (event.key === "Tab") { event.preventDefault(); moveFromCell(cell.dataset.dayId, cell.dataset.field, event.shiftKey ? "previous" : "next"); return; }
      if (event.key.length === 1 && /[0-9:]/.test(event.key)) { event.preventDefault(); beginEditing(cell, event.key); return; }
    }

    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveNow();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !isTextEditingTarget(target)) {
      event.preventDefault();
      undoLastChange();
      return;
    }
    if (state.route === "review" && event.altKey && event.key === "ArrowUp") { event.preventDefault(); moveEmployee(-1); return; }
    if (state.route === "review" && event.altKey && event.key === "ArrowDown") { event.preventDefault(); moveEmployee(1); return; }
    if (state.route !== "review" || !state.settings.singleKeyShortcuts || isTextEditingTarget(target) || event.ctrlKey || event.altKey || event.metaKey) return;
    var key = event.key.toLowerCase();
    if (key === "n") { event.preventDefault(); setStatusForSelected("normal"); }
    if (key === "f") { event.preventDefault(); setStatusForSelected("falta"); }
    if (key === "a") { event.preventDefault(); setStatusForSelected("atestado"); }
    if (key === "r") { event.preventDefault(); setStatusForSelected("conferir"); }
    if (key === "c") {
      event.preventDefault();
      var day = findDay(state.selectedDayId);
      if (dayIsConfirmed(day)) showToast("Este dia já está conferido.", "info", "Use a ação “Reabrir conferência” para fazer novos ajustes.");
      else { confirmDay(day); render(); }
    }
  }

  function handleBlur(event) {
    if (!editSession || event.target !== editSession.input) return;
    root.setTimeout(function () {
      if (editSession && document.activeElement !== editSession.input) finishEditing({ move: null });
    }, 0);
  }

  function handleCopy(event) {
    var cell = event.target.closest && event.target.closest(".editable-time-cell");
    if (!cell || event.target.classList.contains("time-cell-input")) return;
    event.preventDefault();
    event.clipboardData.setData("text/plain", cell.dataset.value || "");
  }

  function handlePaste(event) {
    var cell = event.target.closest && event.target.closest(".editable-time-cell");
    if (!cell || event.target.classList.contains("time-cell-input")) return;
    event.preventDefault();
    beginEditing(cell, event.clipboardData.getData("text/plain").trim());
    finishEditing({ move: "down" });
  }

  function bindDragAndDrop() {
    document.addEventListener("dragover", function (event) {
      var dropzone = event.target.closest && event.target.closest(".import-dropzone");
      if (!dropzone) return;
      event.preventDefault();
      dropzone.classList.add("is-dragging");
    });
    document.addEventListener("dragleave", function (event) {
      var dropzone = event.target.closest && event.target.closest(".import-dropzone");
      if (dropzone) dropzone.classList.remove("is-dragging");
    });
    document.addEventListener("drop", function (event) {
      var dropzone = event.target.closest && event.target.closest(".import-dropzone");
      if (!dropzone) return;
      event.preventDefault();
      dropzone.classList.remove("is-dragging");
      var file = event.dataTransfer && event.dataTransfer.files[0];
      if (file) setSelectedFile(file);
    });
  }

  function syncRouteFromLocation(options) {
    if (editSession && !finishEditing({ move: null })) {
      root.history.replaceState(null, "", routeHash({
        view: state.route,
        companyId: state.selectedCompanyId,
        competenceId: state.selectedCompetenceId,
      }));
      return;
    }
    var route = validateRoute(parseHashRoute(root.location.hash));
    var canonicalHash = routeHash(route);
    if (root.location.hash !== canonicalHash) root.history.replaceState(null, "", canonicalHash);
    applyRouteContext(route);
    render(options);
  }

  function bindEvents() {
    document.addEventListener("click", handleClick);
    document.addEventListener("change", handleChange);
    document.addEventListener("input", handleInput);
    document.addEventListener("submit", handleSubmit);
    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("blur", handleBlur, true);
    document.addEventListener("copy", handleCopy);
    document.addEventListener("paste", handlePaste);
    byId("sidebarExpandButton").addEventListener("click", toggleSidebar);
    root.addEventListener("hashchange", function () {
      syncRouteFromLocation({ focusMain: true });
    });
    bindDragAndDrop();
  }

  function init() {
    bindEvents();
    syncRouteFromLocation();
    root.OnPontoApp = {
      getState: function () { return state; },
      getData: function () { return data; },
      navigate: navigate,
      render: render,
      routeHash: routeHash,
      reset: resetDemo,
    };
  }

  init();
})(window);
