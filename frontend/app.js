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
    "calendar",
    "companies",
    "company-overview",
    "company-employees",
    "company-scales",
    "company-ocorrencias",
    "company-banco-horas",
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
    "company-scales",
    "company-ocorrencias",
    "company-banco-horas",
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
    calendar: "calendar",
    calendario: "calendar",
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
    "company-scales": "company-scales",
    scales: "company-scales",
    escalas: "company-scales",
    ocorrencias: "company-ocorrencias",
    "company-ocorrencias": "company-ocorrencias",
    "company-banco-horas": "company-banco-horas",
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

  var DAY_STATUS_LABELS = {
    normal: "Normal",
    falta: "Falta",
    atestado: "Atestado",
    folga: "Folga",
    feriado: "Feriado",
    domingo: "Domingo",
    sem_expediente: "Sem expediente",
    trabalho_externo: "Trabalho externo",
    afastamento: "Afastamento",
  };

  var STATUS_LABELS = Object.assign({
    conferir: "Conferir",
    inconsistente: "Inconsistente",
  }, DAY_STATUS_LABELS);

  var UF_OPTIONS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];

  var SLOT_ALIASES = {
    entry: ["entry", "entrada"],
    breakStart: ["breakStart", "breakOut", "intervalOut", "saidaIntervalo", "saida_intervalo"],
    breakEnd: ["breakEnd", "breakIn", "intervalIn", "retorno", "retornoIntervalo", "retorno_intervalo"],
    exit: ["exit", "saida"],
  };

  var CLOSED_COMPETENCE_ACTIONS = {
    "analyze-import": true,
    "save-import-start-review": true,
    "edit-time": true,
    "choose-situation": true,
    "edit-observation": true,
    "focus-observation": true,
    "confirm-day": true,
    "reopen-day": true,
    "set-day-absence": true,
    "set-day-certificate": true,
    "set-day-dayoff": true,
    "set-day-no-schedule": true,
    "focus-first-time": true,
    "keep-interpretation": true,
    "bulk-confirm": true,
    "bulk-set-status": true,
    "bulk-add-observation": true,
    "save-now": true,
    "retry-save": true,
    "accept-ocr-preview": true,
  };

  var DEFAULT_API_BASE = "http://127.0.0.1:8000";

  var data = Mocks.getFreshData();
  var state = createInitialState();
  var autosaveTimer = null;
  var autosaveFlushPromise = null;
  var pendingDaySaves = Object.create(null);
  var activeDaySaves = Object.create(null);
  var loadedCompetenceDays = Object.create(null);
  var loadedCompetenceFiles = Object.create(null);
  var loadedCompetenceSummaries = Object.create(null);
  var loadedCompanyScales = Object.create(null);
  var companyScaleLoadSequences = Object.create(null);
  var competenceSummarySequences = Object.create(null);
  var importAnalysisSequence = 0;
  var routeLoadSequence = 0;
  var exportExcelSequence = 0;
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

  function configuredApiBase() {
    var configured = "";
    try {
      configured = localStorage.getItem("onponto.apiBase") || "";
    } catch (error) {
      configured = "";
    }
    return String(configured || DEFAULT_API_BASE).trim().replace(/\/+$/, "");
  }

  function apiErrorMessage(payload, fallback) {
    var detail = payload && (payload.detail || payload.message || payload.erro || payload.error);
    if (Array.isArray(detail)) {
      detail = detail.map(function (item) {
        return typeof item === "string" ? item : item && (item.msg || item.message) || "Dados inválidos.";
      }).join(" ");
    }
    if (detail && typeof detail === "object") detail = detail.message || detail.mensagem || detail.msg || JSON.stringify(detail);
    return String(detail || fallback || "Não foi possível concluir a operação.");
  }

  function isClosedCompetenceError(error) {
    if (!error || error.status !== 409) return false;
    var detail = error.payload && error.payload.detail;
    return /compet[eê]ncia[^.]*fechad|competencia_fechada/i.test(typeof detail === "string" ? detail : JSON.stringify(detail || {}));
  }

  function apiRequest(path, options) {
    var settings = options || {};
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timeout = root.setTimeout(function () {
      if (controller) controller.abort();
    }, settings.timeout || 8000);
    var requestOptions = Object.assign({}, settings);
    delete requestOptions.timeout;
    if (controller) requestOptions.signal = controller.signal;
    requestOptions.headers = Object.assign({ Accept: "application/json" }, requestOptions.headers || {});
    if (requestOptions.body && typeof FormData !== "undefined" && requestOptions.body instanceof FormData) {
      delete requestOptions.headers["Content-Type"];
    } else if (requestOptions.body && typeof requestOptions.body !== "string") {
      requestOptions.headers["Content-Type"] = "application/json";
      requestOptions.body = JSON.stringify(requestOptions.body);
    }

    return root.fetch(configuredApiBase() + path, requestOptions).then(function (response) {
      return response.text().then(function (textValue) {
        var payload = null;
        if (textValue) {
          try { payload = JSON.parse(textValue); }
          catch (error) { payload = { detail: textValue }; }
        }
        if (!response.ok) {
          var requestError = new Error(apiErrorMessage(payload, "A API respondeu com erro " + response.status + "."));
          requestError.status = response.status;
          requestError.payload = payload;
          throw requestError;
        }
        return payload;
      });
    }).catch(function (error) {
      if (error && error.name === "AbortError") throw new Error("A API demorou mais que o esperado para responder.");
      throw error;
    }).finally(function () {
      root.clearTimeout(timeout);
    });
  }

  function apiCollection(payload, aliases) {
    if (Array.isArray(payload)) return payload;
    var source = payload && payload.data && typeof payload.data === "object" ? payload.data : payload || {};
    for (var index = 0; index < aliases.length; index += 1) {
      if (Array.isArray(source[aliases[index]])) return source[aliases[index]];
    }
    if (Array.isArray(source.items)) return source.items;
    return [];
  }

  function statusFromBackend(value) {
    var key = String(value || "conferir").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
    return {
      pendente: "conferir",
      pendente_conferencia: "conferir",
      nao_conferido: "conferir",
      needs_review: "conferir",
      inconsistency: "inconsistente",
    }[key] || key || "conferir";
  }

  function statusToBackend(value) {
    var key = statusFromBackend(value);
    return Object.prototype.hasOwnProperty.call(DAY_STATUS_LABELS, key) ? key : "normal";
  }

  function statusLabel(value) {
    var normalized = statusFromBackend(value);
    return STATUS_LABELS[normalized] || normalized;
  }

  function normalizeCompany(item) {
    var source = item || {};
    return Object.assign({}, source, {
      id: source.id,
      name: source.name || source.nome || "Empresa",
      nome: source.nome || source.name || "Empresa",
      legalName: source.legalName || source.razao_social || source.razaoSocial || source.nome || source.name || "Empresa",
      city: source.city !== undefined ? source.city : source.cidade,
      cidade: source.cidade !== undefined ? source.cidade : source.city,
      uf: source.uf ? String(source.uf).toUpperCase() : null,
      active: source.active !== undefined ? source.active : source.ativa !== false,
      ativa: source.ativa !== undefined ? source.ativa : source.active !== false,
      updatedAt: source.updatedAt || source.updated_at || null,
    });
  }

  function normalizeEmployee(item) {
    var source = item || {};
    return Object.assign({}, source, {
      id: source.id,
      companyId: source.companyId !== undefined ? source.companyId : source.empresa_id,
      empresa_id: source.empresa_id !== undefined ? source.empresa_id : source.companyId,
      name: source.name || source.nome || "Funcionário",
      nome: source.nome || source.name || "Funcionário",
      code: source.code !== undefined ? source.code : source.codigo,
      codigo: source.codigo !== undefined ? source.codigo : source.code,
      role: source.role || source.cargo || "",
      cargo: source.cargo || source.role || "",
      scaleId: source.scaleId !== undefined ? source.scaleId : source.escala_id,
      escala_id: source.escala_id !== undefined ? source.escala_id : source.scaleId,
      active: source.active !== undefined ? source.active : source.ativo !== false,
      ativo: source.ativo !== undefined ? source.ativo : source.active !== false,
    });
  }

  function normalizeScale(item) {
    var source = item || {};
    var companyId = source.companyId !== undefined ? source.companyId : source.empresa_id;
    return Object.assign({}, source, {
      id: source.id,
      companyId: companyId,
      empresa_id: companyId,
      name: source.name || source.nome || "Escala",
      nome: source.nome || source.name || "Escala",
      mode: source.mode || source.modo_apuracao || "carga_horaria",
      modo_apuracao: source.modo_apuracao || source.mode || "carga_horaria",
      active: source.active !== undefined ? source.active : source.ativa !== false,
      ativa: source.ativa !== undefined ? source.ativa : source.active !== false,
    });
  }

  function normalizeCompetence(item, employeeList) {
    var source = item || {};
    var companyId = source.companyId !== undefined ? source.companyId : source.empresa_id;
    var month = Number(source.month !== undefined ? source.month : source.mes);
    var year = Number(source.year !== undefined ? source.year : source.ano);
    var count = (employeeList || []).filter(function (employee) { return idsEqual(employee.companyId || employee.empresa_id, companyId); }).length;
    return Object.assign({}, source, {
      id: source.id,
      companyId: companyId,
      empresa_id: companyId,
      month: month,
      mes: month,
      year: year,
      ano: year,
      label: source.label || (String(month).padStart(2, "0") + "/" + year),
      status: statusFromBackend(source.status || "aberta"),
      statusLabel: source.statusLabel || ({ aberta: "Aberta", em_conferencia: "Em conferência", conferida: "Conferida", fechada: "Fechada" }[source.status] || source.status || "Aberta"),
      employeeCount: source.employeeCount !== undefined ? source.employeeCount : count,
      pendingCount: source.pendingCount !== undefined ? source.pendingCount : 0,
      fileCount: source.fileCount !== undefined ? source.fileCount : 0,
      progress: source.progress !== undefined ? source.progress : 0,
      confirmedEmployees: source.confirmedEmployees !== undefined ? source.confirmedEmployees : 0,
      pendingEmployees: source.pendingEmployees !== undefined ? source.pendingEmployees : count,
      updatedAt: source.updatedAt || source.updated_at || null,
      receivedAt: source.receivedAt || source.data_recebimento || null,
      closedAt: source.closedAt || source.data_fechamento || null,
    });
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
    if (segments.length === 1 && segments[0].toLowerCase() === "calendario") return { view: "calendar", companyId: null, competenceId: null };
    if (segments.length === 1 && segments[0].toLowerCase() === "empresas") return emptyRoute();
    if (segments.length < 2 || segments[0].toLowerCase() !== "empresas") return emptyRoute();

    var companyId = asId(segments[1]);
    if (segments.length === 2) return { view: "company-overview", companyId: companyId, competenceId: null };
    if (segments.length === 3) {
      var companyChild = {
        funcionarios: "company-employees",
        escalas: "company-scales",
        ocorrencias: "company-ocorrencias",
        "banco-horas": "company-banco-horas",
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
    if (view === "calendar") return { view: "calendar", companyId: null, competenceId: null };
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
    if (descriptor.view === "calendar") return "#/calendario";
    if (descriptor.view === "companies") return "#/empresas";
    var base = "#/empresas/" + encodeURIComponent(descriptor.companyId);
    var companySuffix = {
      "company-overview": "",
      "company-employees": "/funcionarios",
      "company-scales": "/escalas",
      "company-ocorrencias": "/ocorrencias",
      "company-banco-horas": "/banco-horas",
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
      apiMode: "loading",
      apiBase: configuredApiBase(),
      apiError: "",
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
      importLoading: false,
      importConfirming: false,
      importError: "",
      importConflicts: [],
      importPreviewFilter: "all",
      importPreviewEmployeeId: "",
      selectedImportRowIds: [],
      reviewLoading: false,
      competenceSummaryLoading: false,
      competenceSummaryError: "",
      scalesLoading: false,
      scalesError: "",
      exportExcelLoading: false,
      competenceLifecycleLoading: false,
      competenceLifecycleAction: "",
      competenceLifecycleError: "",
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

  function scales() {
    return data.scales || data.escalas || [];
  }

  function days() {
    return data.attendanceDays || data.dias || [];
  }

  function files() {
    return data.files || data.arquivos || [];
  }

  function firstValue() {
    for (var index = 0; index < arguments.length; index += 1) {
      if (arguments[index] !== undefined && arguments[index] !== null) return arguments[index];
    }
    return null;
  }

  function normalizedTime(value) {
    if (value === null || value === undefined || value === "" || value === "?") return "";
    var match = String(value).match(/^(\d{1,2}):(\d{2})/);
    return match ? String(match[1]).padStart(2, "0") + ":" + match[2] : String(value);
  }

  function normalizeOriginalPunches(value) {
    var punches = value;
    if (typeof punches === "string") {
      try { punches = JSON.parse(punches); }
      catch (error) { punches = punches.split(/\s*[,;]\s*/).filter(Boolean); }
    }
    if (!Array.isArray(punches)) return [];
    return punches.map(function (punch) {
      if (punch && typeof punch === "object") return String(firstValue(punch.value, punch.time, punch.horario, punch.raw, ""));
      return String(punch == null ? "" : punch);
    }).filter(Boolean);
  }

  function normalizeIssues(value) {
    var source = value;
    if (typeof source === "string") {
      try { source = JSON.parse(source); }
      catch (error) { source = [source]; }
    }
    if (!Array.isArray(source)) return [];
    return source.map(function (issue, index) {
      if (typeof issue === "string") return { id: "issue-api-" + index, type: "review", severity: "warning", message: issue, resolved: false };
      return Object.assign({}, issue, {
        id: issue.id || "issue-api-" + index,
        message: issue.message || issue.mensagem || issue.detail || "Revisão necessária.",
        severity: issue.severity || issue.gravidade || "warning",
        resolved: issue.resolved === true || issue.resolvida === true,
      });
    });
  }

  function normalizePreviewRow(item, index, analysisSource) {
    var source = item || {};
    var employee = source.funcionario || source.employee || {};
    var interpretation = source.interpretacao || source.suggestion || source.suggested || {};
    var origin = source.origem || {};
    var employeeFound = employee.encontrado !== undefined ? employee.encontrado === true : firstValue(employee.id, source.funcionario_id, source.employeeId) !== null;
    var outsideCompetence = source.fora_da_competencia === true || source.outsideCompetence === true;
    var rowId = firstValue(source.id, source.registro_id, source.preview_id, "preview-api-" + index);
    var originalPunches = normalizeOriginalPunches(firstValue(source.batidas_originais, source.originalPunches, []));
    var issues = normalizeIssues(firstValue(source.pendencias, source.issues, []));
    var rawStatus = source.status || source.status_dia || (issues.length ? "conferir" : "nao_conferido");
    var rawStatusKey = String(rawStatus).trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
    var normalizedStatus = rawStatusKey === "nao_conferido" ? "nao_conferido" : statusFromBackend(rawStatus);
    var selected = source.selecionado !== undefined ? source.selecionado === true : employeeFound && !outsideCompetence;
    var employeeId = firstValue(employee.id, source.funcionario_id, source.employeeId);
    var employeeName = firstValue(employee.nome_cadastrado, employee.nome_origem, employee.nome, source.funcionario_nome, source.employeeName, "Funcionário não identificado");
    return Object.assign({}, source, {
      id: rowId,
      companyId: firstValue(source.empresa_id, source.companyId, analysisSource && analysisSource.companyId, state.selectedCompanyId),
      empresa_id: firstValue(source.empresa_id, source.companyId, analysisSource && analysisSource.companyId, state.selectedCompanyId),
      competenceId: firstValue(source.competencia_id, source.competenceId, analysisSource && analysisSource.competenceId, state.selectedCompetenceId),
      competencia_id: firstValue(source.competencia_id, source.competenceId, analysisSource && analysisSource.competenceId, state.selectedCompetenceId),
      employeeId: employeeId,
      funcionario_id: employeeId,
      employeeName: employeeName,
      funcionario: employeeName,
      employeeCode: firstValue(employee.codigo_origem, employee.codigo, source.codigo_origem, ""),
      employeeSourceName: firstValue(employee.nome_origem, employeeName),
      employeeRegisteredName: firstValue(employee.nome_cadastrado, employee.nome, ""),
      employeeFound: employeeFound,
      funcionarioEncontrado: employeeFound,
      date: source.data || source.date,
      data: source.data || source.date,
      originalPunches: originalPunches,
      batidasOriginais: originalPunches,
      suggestion: {
        entry: normalizedTime(firstValue(interpretation.entrada, interpretation.entry)),
        breakStart: normalizedTime(firstValue(interpretation.saida_intervalo, interpretation.saida_almoco, interpretation.breakStart, interpretation.breakOut)),
        breakEnd: normalizedTime(firstValue(interpretation.retorno_intervalo, interpretation.retorno_almoco, interpretation.breakEnd, interpretation.breakIn)),
        exit: normalizedTime(firstValue(interpretation.saida, interpretation.exit)),
      },
      status: normalizedStatus,
      statusLabel: rawStatusKey === "nao_conferido" ? "Não conferido" : statusLabel(normalizedStatus),
      issues: issues,
      pendencias: issues,
      observation: issues.map(function (issue) { return issue.message; }).join(" ") || source.observacao || source.observation || "",
      hasPendingIssue: issues.length > 0 || normalizedStatus === "conferir" || normalizedStatus === "inconsistente" || !employeeFound || outsideCompetence,
      outsideCompetence: outsideCompetence,
      foraDaCompetencia: outsideCompetence,
      selected: selected,
      selecionado: selected,
      source: {
        fileId: firstValue(origin.arquivo_id, origin.fileId, analysisSource && analysisSource.fileId),
        fileName: firstValue(origin.arquivo, origin.fileName, analysisSource && analysisSource.fileName),
        type: firstValue(origin.tipo, origin.type, "txt_log_relogio"),
        sourceLines: firstValue(origin.linhas, origin.sourceLines, []),
      },
    });
  }

  function normalizeImportAnalysis(payload) {
    var source = payload && payload.data && typeof payload.data === "object" ? payload.data : payload || {};
    var file = source.arquivo && typeof source.arquivo === "object" ? source.arquivo : {};
    var fileId = firstValue(source.arquivo_id, source.fileId, file.id);
    var fileName = firstValue(source.nome_arquivo, source.fileName, file.nome_original, file.nome, file.name, state.selectedImportFile && state.selectedImportFile.name, "Arquivo TXT");
    var rawRows = firstValue(source.preview, source.rows, source.registros, []);
    if (!Array.isArray(rawRows)) rawRows = [];
    var analysisContext = {
      fileId: fileId,
      fileName: fileName,
      companyId: firstValue(source.empresa_id, source.companyId, state.selectedCompanyId),
      competenceId: firstValue(source.competencia_id, source.competenceId, state.selectedCompetenceId),
    };
    var rows = rawRows.map(function (row, index) { return normalizePreviewRow(row, index, analysisContext); });
    var foundEmployees = {};
    rows.forEach(function (row) { if (row.employeeFound && row.employeeId !== null) foundEmployees[String(row.employeeId)] = true; });
    var unmatchedValue = firstValue(source.total_funcionarios_nao_cadastrados, source.funcionarios_nao_encontrados, source.unmatchedEmployeeCount);
    var unmatched = unmatchedValue === null || unmatchedValue === "" ? NaN : Number(unmatchedValue);
    if (!Number.isFinite(unmatched)) unmatched = rows.filter(function (row) { return !row.employeeFound; }).length;
    var outsideValue = firstValue(source.total_fora_da_competencia, source.registros_fora_da_competencia, source.registros_fora_competencia, source.outsideCompetenceCount);
    var outside = outsideValue === null || outsideValue === "" ? NaN : Number(outsideValue);
    if (!Number.isFinite(outside)) outside = rows.filter(function (row) { return row.outsideCompetence; }).length;
    var punchCountValue = firstValue(source.total_batidas, source.punchCount);
    var punchCount = punchCountValue === null || punchCountValue === "" ? NaN : Number(punchCountValue);
    if (!Number.isFinite(punchCount)) punchCount = rows.reduce(function (sum, row) { return sum + row.originalPunches.length; }, 0);
    var pendingCountValue = firstValue(source.total_pendencias, source.pendingCount);
    var pendingCount = pendingCountValue === null || pendingCountValue === "" ? NaN : Number(pendingCountValue);
    if (!Number.isFinite(pendingCount)) pendingCount = rows.filter(function (row) { return row.hasPendingIssue; }).length;
    return Object.assign({}, source, {
      id: firstValue(source.id, source.analise_id, source.importacao_id),
      analysisId: firstValue(source.analise_id, source.importacao_id, source.id),
      fileId: fileId,
      arquivoId: fileId,
      fileName: fileName,
      companyId: firstValue(source.empresa_id, source.companyId, state.selectedCompanyId),
      companyName: firstValue(source.empresa_nome, source.companyName, currentCompany() && (currentCompany().name || currentCompany().nome)),
      competenceId: firstValue(source.competencia_id, source.competenceId, state.selectedCompetenceId),
      competenceLabel: firstValue(source.competencia_label, source.competenceLabel, currentCompetency() && (currentCompetency().label || Utils.formatCompetence(currentCompetency()))),
      requestedType: "txt_clock",
      detectedType: "txt_clock",
      detectedFormat: ({
        txt_log_relogio: "TXT · log do relógio",
        txt_id_tempo_maquina: "TXT · ID/Tempo/Máquina",
        txt_generico: "TXT · detecção flexível",
        xlsx_ponto_generico: "XLSX · ponto genérico",
        xlsx_cartao_ponto: "XLSX · cartão de ponto",
      }[firstValue(source.tipo_detectado, source.formato_detectado, source.detectedFormat)] || firstValue(source.tipo_detectado, source.formato_detectado, source.detectedFormat, "Arquivo de ponto")),
      validLineCount: Number(firstValue(source.total_linhas_validas, source.validLineCount, rows.length)) || 0,
      employeeCount: Number(firstValue(source.total_funcionarios_encontrados, source.employeeCount, Object.keys(foundEmployees).length)) || 0,
      unmatchedEmployeeCount: unmatched,
      punchCount: punchCount,
      dayCount: Number(firstValue(source.total_dias, source.dayCount, rows.length)) || 0,
      recordCount: Number(firstValue(source.total_registros, source.recordCount, rows.length)) || 0,
      pendingCount: pendingCount,
      outsideCompetenceCount: outside,
      rows: rows,
      linhas: rows,
      saved: false,
    });
  }

  function normalizeMarking(item) {
    var source = item || {};
    var interpretation = source.interpretacao || source.current || source.interpretacao_atual || {};
    var competenceId = firstValue(source.competencia_id, source.competenceId);
    var employeeId = firstValue(source.funcionario_id, source.employeeId);
    var competence = competencies().find(function (entry) { return idsEqual(entry.id, competenceId); }) || {};
    var employee = employees().find(function (entry) { return idsEqual(entry.id, employeeId); }) || {};
    var originalPunches = normalizeOriginalPunches(firstValue(source.batidas_originais, source.originalPunches, []));
    var sourceLines = firstValue(source.linhas_origem, source.sourceLines, []);
    if (!Array.isArray(sourceLines)) sourceLines = [];
    var fileId = firstValue(source.arquivo_origem_id, source.origem_arquivo_id, source.fileId);
    var originType = firstValue(source.origem, "txt_log_relogio");
    var fileName = firstValue(
      source.arquivo_origem_nome,
      source.nome_arquivo_origem,
      source.fileName,
      source.arquivo_nome,
      originType === "calendario" ? "Calendário da competência" : "Arquivo TXT"
    );
    var current = {
      entry: normalizedTime(firstValue(interpretation.entrada, interpretation.entry, source.entrada)),
      breakStart: normalizedTime(firstValue(interpretation.saida_intervalo, interpretation.saida_almoco, interpretation.breakStart, source.saida_intervalo, source.saida_almoco)),
      breakEnd: normalizedTime(firstValue(interpretation.retorno_intervalo, interpretation.retorno_almoco, interpretation.breakEnd, source.retorno_intervalo, source.retorno_almoco)),
      exit: normalizedTime(firstValue(interpretation.saida, interpretation.exit, source.saida)),
    };
    var rawDayStatus = firstValue(source.status_dia, source.status, interpretation.status, "normal");
    var rawDayStatusKey = String(rawDayStatus || "normal").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
    var legacyPendingStatus = rawDayStatusKey === "pendente" || rawDayStatusKey === "pendente_conferencia" || rawDayStatusKey === "conferir" || rawDayStatusKey === "inconsistente";
    var normalizedStatus = statusFromBackend(rawDayStatus);
    if (!Object.prototype.hasOwnProperty.call(DAY_STATUS_LABELS, normalizedStatus)) normalizedStatus = "normal";
    current.situation = normalizedStatus;
    current.status = normalizedStatus;
    current.observation = firstValue(source.observacoes, source.observacao, source.observation, "");
    var dateValue = source.data || source.date;
    var backendExpected = firstValue(source.jornada_prevista_minutos, source.expectedMinutes);
    var expectedMinutes = backendExpected !== null ? Number(backendExpected) : null;
    if (!Number.isFinite(expectedMinutes)) expectedMinutes = null;
    var calculatedJourney = Utils.calculateJourney(current, expectedMinutes);
    var backendWorked = firstValue(source.jornada_apurada_minutos, source.workedMinutes);
    var backendBalance = firstValue(source.saldo_minutos, source.balanceMinutes);
    var workedMinutes = backendWorked !== null && Number.isFinite(Number(backendWorked)) ? Number(backendWorked) : calculatedJourney.workedMinutes;
    var balanceMinutes = backendBalance !== null && Number.isFinite(Number(backendBalance)) ? Number(backendBalance) : (workedMinutes == null || expectedMinutes == null ? null : workedMinutes - expectedMinutes);
    var confirmed = source.conferido === true || source.confirmed === true;
    var nonWorkingStatus = ["atestado", "folga", "feriado", "falta", "afastamento", "domingo", "sem_expediente"].indexOf(normalizedStatus) !== -1;
    var scaleMissing = employee && employee.id !== undefined && firstValue(employee.escala_id, employee.scaleId) === null;
    var incompleteCalculation = !nonWorkingStatus && (!current.entry || !current.exit || Boolean(current.breakStart) !== Boolean(current.breakEnd));
    var pendingCalculationValue = firstValue(source.pendente_calculo, source.pendingCalculation);
    var pendingCalculation = pendingCalculationValue === null ? (scaleMissing || incompleteCalculation) : pendingCalculationValue === true;
    var pendingOperationalValue = firstValue(source.pendente_operacional, source.pendingOperational, source.pendente);
    var pendingOperational = pendingOperationalValue === null
      ? (legacyPendingStatus || pendingCalculation || !confirmed)
      : pendingOperationalValue === true;
    var pendingReason = firstValue(source.pendencia_motivo, source.pendingReason, source.motivo_pendencia);
    var pendingType = firstValue(source.pendencia_tipo, source.pendingType);
    var issues = normalizeIssues(firstValue(source.pendencias, source.issues, []));
    if (pendingReason && !issues.some(function (issue) { return issue.message === pendingReason; })) {
      issues.push({
        id: "issue-api-mark-" + source.id,
        type: pendingType || (scaleMissing ? "escala_nao_cadastrada" : "review"),
        severity: "warning",
        message: pendingReason,
        resolved: false,
      });
    }
    if (scaleMissing && !issues.some(function (issue) { return issue.type === "escala_nao_cadastrada"; })) {
      issues.push({
        id: "issue-scale-mark-" + source.id,
        type: "escala_nao_cadastrada",
        severity: "warning",
        message: "Funcionário sem escala cadastrada.",
        resolved: false,
      });
    }
    var details = originalPunches.map(function (punch, index) {
      return { id: "mark-" + source.id + "-punch-" + index, time: punch, horario: punch, sourceLine: sourceLines[index], fileId: fileId };
    });
    var origin = {
      fileId: fileId,
      fileName: fileName,
      arquivo: fileName,
      importedAt: firstValue(source.importado_em, source.created_at, source.createdAt),
      sourceLines: sourceLines,
      linhasOrigem: sourceLines,
      type: originType,
      canOpenOriginal: Boolean(fileId),
      canOpenRegion: false,
    };
    return Object.assign({}, source, {
      id: source.id,
      companyId: firstValue(source.empresa_id, source.companyId, competence.companyId, competence.empresa_id),
      empresa_id: firstValue(source.empresa_id, source.companyId, competence.companyId, competence.empresa_id),
      competenceId: competenceId,
      competencia_id: competenceId,
      employeeId: employeeId,
      funcionario_id: employeeId,
      employeeName: firstValue(source.funcionario_nome, source.employeeName, employee.name, employee.nome, "Funcionário"),
      funcionario: firstValue(source.funcionario_nome, source.employeeName, employee.name, employee.nome, "Funcionário"),
      date: dateValue,
      data: dateValue,
      originalPunches: Object.freeze(originalPunches.slice()),
      batidasOriginais: Object.freeze(originalPunches.slice()),
      originalPunchDetails: Object.freeze(details),
      original: Object.freeze({ punches: Object.freeze(originalPunches.slice()), punchDetails: Object.freeze(details.slice()), source: origin }),
      suggestion: Object.assign({}, current),
      current: current,
      currentInterpretation: current,
      interpretacaoAtual: current,
      status: normalizedStatus,
      status_dia: normalizedStatus,
      statusLabel: statusLabel(normalizedStatus),
      pendingOperational: pendingOperational,
      pendente_operacional: pendingOperational,
      pendingCalculation: pendingCalculation,
      pendente_calculo: pendingCalculation,
      pendingReason: pendingReason,
      pendencia_motivo: pendingReason,
      pendingType: pendingType,
      pendencia_tipo: pendingType,
      confirmed: confirmed,
      conferido: confirmed,
      reviewState: confirmed ? "confirmed" : "suggested",
      review: { state: confirmed ? "confirmed" : "suggested", status: normalizedStatus, confirmed: confirmed, issues: issues },
      observation: current.observation,
      observacao: current.observation,
      issues: issues,
      pendencias: issues,
      source: origin,
      origem: origin,
      history: Array.isArray(source.historico) ? source.historico : Array.isArray(source.history) ? source.history : [],
      historico: Array.isArray(source.historico) ? source.historico : Array.isArray(source.history) ? source.history : [],
      expectedMinutes: expectedMinutes,
      jornadaPrevistaMinutos: expectedMinutes,
      workedMinutes: workedMinutes,
      jornadaApuradaMinutos: workedMinutes,
      balanceMinutes: balanceMinutes,
      saldoMinutos: balanceMinutes,
    });
  }

  function replaceAttendanceForCompetence(competenceId, markings) {
    var remaining = days().filter(function (day) { return !idsEqual(day.competenceId || day.competencia_id, competenceId); });
    var merged = remaining.concat(markings.map(function (marking) {
      var key = String(marking.id);
      if (pendingDaySaves[key] || activeDaySaves[key]) return findDay(marking.id) || marking;
      return marking;
    }));
    data.attendanceDays = merged;
    data.dias = merged;
  }

  function normalizeReceivedFile(item) {
    var source = item || {};
    var name = firstValue(source.nome_original, source.name, source.nome, "Arquivo");
    var type = firstValue(source.tipo_arquivo, source.type, source.tipo, "arquivo");
    return Object.assign({}, source, {
      id: source.id,
      competenceId: firstValue(source.competencia_id, source.competenceId),
      competencia_id: firstValue(source.competencia_id, source.competenceId),
      name: name,
      nome: name,
      type: type,
      tipo: type,
      typeLabel: ({
        txt_log_relogio: "TXT estruturado",
        txt_id_tempo_maquina: "TXT ID/Tempo",
        txt_generico: "TXT flexível",
      }[type] || String(type).toUpperCase()),
      detectedFormat: ({
        txt_log_relogio: "TXT estruturado",
        txt_id_tempo_maquina: "TXT ID/Tempo",
        txt_generico: "TXT flexível",
      }[type] || String(type).toUpperCase()),
      uploadedAt: firstValue(source.created_at, source.uploadedAt, source.createdAt),
      createdAt: firstValue(source.created_at, source.createdAt, source.uploadedAt),
      observation: firstValue(source.observacoes, source.observation, ""),
    });
  }

  function replaceFilesForCompetence(competenceId, receivedFiles) {
    var remaining = files().filter(function (file) {
      return !idsEqual(file.competenceId || file.competencia_id, competenceId);
    });
    var merged = remaining.concat(receivedFiles);
    data.files = merged;
    data.arquivos = merged;
  }

  function valueFromAliases(source, aliases) {
    var object = source && typeof source === "object" ? source : {};
    for (var index = 0; index < aliases.length; index += 1) {
      if (object[aliases[index]] !== undefined) return object[aliases[index]];
    }
    return null;
  }

  function normalizeCompetenceSummary(payload) {
    var source = payload && payload.data && typeof payload.data === "object" ? payload.data : payload || {};
    var generalSource = valueFromAliases(source, ["resumo_geral", "resumoGeral", "general_summary", "generalSummary", "general"]);
    var summaryRows = valueFromAliases(source, ["resumo", "summary", "funcionarios", "employees", "items"]);
    if (!generalSource || typeof generalSource !== "object" || Array.isArray(generalSource)) generalSource = {};
    if (!Array.isArray(summaryRows)) summaryRows = [];
    var pendingRecordsSource = valueFromAliases(source, ["pendencias", "pending_records", "pendingRecords"]);
    var pendingRecords = Array.isArray(pendingRecordsSource)
      ? pendingRecordsSource.length
      : valueFromAliases(generalSource, ["registros_pendentes", "pending_records", "pendingRecords"]);
    var processedRecordsSource = valueFromAliases(source, ["marcacoes", "records", "markings"]);
    var processedRecords = Array.isArray(processedRecordsSource)
      ? processedRecordsSource.length
      : valueFromAliases(generalSource, ["registros_processados", "processed_records", "processedRecords"]);
    return {
      company: valueFromAliases(source, ["empresa", "company"]),
      competence: valueFromAliases(source, ["competencia", "competence"]),
      generatedAt: valueFromAliases(source, ["gerado_em", "geradoEm", "generated_at", "generatedAt"]),
      pendingRecords: pendingRecords,
      processedRecords: processedRecords,
      markings: Array.isArray(processedRecordsSource) ? processedRecordsSource : [],
      general: {
        employees: valueFromAliases(generalSource, ["funcionarios", "total_funcionarios", "employees", "employee_count"]),
        confirmed: valueFromAliases(generalSource, ["conferidos", "funcionarios_conferidos", "confirmed", "confirmed_employees"]),
        pending: valueFromAliases(generalSource, ["pendentes", "funcionarios_pendentes", "pending", "pending_employees"]),
        pendingDays: valueFromAliases(generalSource, ["dias_com_pendencia", "dias_pendentes", "pending_days"]),
        totalFiles: valueFromAliases(generalSource, ["total_arquivos", "arquivos", "total_files", "file_count"]),
      },
      rows: summaryRows.map(function (item) {
        return {
          employeeId: valueFromAliases(item, ["funcionario_id", "employee_id", "id"]),
          employeeName: valueFromAliases(item, ["funcionario", "funcionario_nome", "nome", "employee", "employee_name"]),
          employeeCode: valueFromAliases(item, ["codigo", "funcionario_codigo", "code", "employee_code"]),
          bank: item.banco_horas || null,
          processedDays: valueFromAliases(item, ["dias_processados", "processed_days", "day_count"]),
          delays: valueFromAliases(item, ["atrasos", "atraso", "total_atrasos", "delays"]),
          delayMinutes: valueFromAliases(item, ["atrasos_minutos", "atraso_minutos", "delay_minutes"]),
          extras: valueFromAliases(item, ["extras", "horas_extras", "total_extras", "overtime"]),
          extraMinutes: valueFromAliases(item, ["extras_minutos", "extra_minutos", "overtime_minutes"]),
          holidayMinutes: Object.prototype.hasOwnProperty.call(item, "horas_feriado_minutos") ? item.horas_feriado_minutos : 0,
          absences: valueFromAliases(item, ["faltas", "absences"]),
          certificates: valueFromAliases(item, ["atestados", "certificates", "medical_certificates"]),
          pending: valueFromAliases(item, ["pendencias", "pending", "issues"]),
          situation: valueFromAliases(item, ["situacao", "situation", "status"]),
        };
      }),
    };
  }

  function applyApurationDetails(competenceId, details) {
    if (!Array.isArray(details) || !details.length) return;
    var byId = Object.create(null);
    details.forEach(function (detail) {
      if (detail && detail.id !== undefined && detail.id !== null) byId[String(detail.id)] = detail;
    });
    days().forEach(function (day) {
      if (!idsEqual(day.competenceId || day.competencia_id, competenceId)) return;
      if (typeof pendingDaySaves !== "undefined" && pendingDaySaves[String(day.id)]) return;
      var detail = byId[String(day.id)];
      if (!detail) return;
      day.occurrences = detail.ocorrencias || [];
      day.occurrenceLabel = detail.ocorrencias_rotulo || "";
      day.calendarNote = detail.fora_vinculo ? "Fora do vínculo" : (detail.feriados || []).join(", ");
      day.effectiveStatus = detail.fora_vinculo ? "fora_vinculo" : detail.feriado_aplicado ? "feriado" : null;
      day.excusedMinutes = detail.minutos_abonados || 0;
      // Keep editable statuses separate from the engine's occurrence overlay.
      var normalizedStatus = statusFromBackend((day.occurrences.length || detail.feriado_aplicado || detail.fora_vinculo) ? firstValue(detail.status_original, day.status) : firstValue(detail.status_dia, detail.status, day.status, "normal"));
      if (!Object.prototype.hasOwnProperty.call(DAY_STATUS_LABELS, normalizedStatus)) normalizedStatus = "normal";
      var expected = firstValue(detail.jornada_exigida_minutos, detail.jornada_prevista_minutos, detail.expectedMinutes);
      var worked = firstValue(detail.jornada_apurada_minutos, detail.horas_trabalhadas_minutos, detail.workedMinutes);
      expected = expected !== null && Number.isFinite(Number(expected)) ? Number(expected) : null;
      worked = worked !== null && Number.isFinite(Number(worked)) ? Number(worked) : null;
      var balance = firstValue(detail.saldo_minutos, detail.balanceMinutes);
      var delay = firstValue(detail.atraso_minutos);
      var extra = firstValue(detail.extra_minutos);
      balance = balance !== null && Number.isFinite(Number(balance)) ? Number(balance)
        : (delay !== null && extra !== null && Number.isFinite(Number(delay)) && Number.isFinite(Number(extra)) ? Number(extra) - Number(delay) : null);
      var confirmed = detail.conferido === true || detail.confirmed === true;
      var pendingCalculation = firstValue(detail.pendente_calculo, detail.pendingCalculation) === true;
      if (pendingCalculation) balance = null;
      var pendingOperationalValue = firstValue(detail.pendente_operacional, detail.pendingOperational, detail.pendente);
      var pendingOperational = pendingOperationalValue === null ? pendingCalculation || !confirmed : pendingOperationalValue === true;
      var pendingReason = firstValue(detail.pendencia_motivo, detail.pendingReason, detail.motivo_pendencia);
      var pendingType = firstValue(detail.pendencia_tipo, detail.pendingType);

      day.status = normalizedStatus;
      day.status_dia = normalizedStatus;
      day.statusLabel = statusLabel(normalizedStatus);
      day.expectedMinutes = expected;
      day.jornadaPrevistaMinutos = expected;
      day.workedMinutes = worked;
      day.jornadaApuradaMinutos = worked;
      day.balanceMinutes = balance;
      day.saldoMinutos = balance;
      day.confirmed = confirmed;
      day.conferido = confirmed;
      day.pendingCalculation = pendingCalculation;
      day.pendente_calculo = pendingCalculation;
      day.pendingOperational = pendingOperational;
      day.pendente_operacional = pendingOperational;
      day.pendingReason = pendingReason;
      day.pendencia_motivo = pendingReason;
      day.pendingType = pendingType;
      day.pendencia_tipo = pendingType;
      if (day.current) {
        day.current.status = normalizedStatus;
        day.current.situation = normalizedStatus;
        day.current.situacao = normalizedStatus;
      }
      if (day.review) {
        day.review.status = normalizedStatus;
        day.review.confirmed = confirmed;
        day.review.state = confirmed ? "confirmed" : "suggested";
      }
      if (pendingReason) {
        var issueList = day.issues || day.pendencias || [];
        if (!issueList.some(function (issue) { return issue && (issue.message || issue.mensagem) === pendingReason; })) {
          issueList.push({ id: "issue-apuration-" + day.id, type: pendingType || "review", severity: "warning", message: pendingReason, resolved: false });
        }
        day.issues = issueList;
        day.pendencias = issueList;
      }
    });
  }

  function loadAttendanceForCompetence(competenceId, options) {
    if (state.apiMode !== "online" || competenceId === null || competenceId === undefined) return Promise.resolve([]);
    var settings = options || {};
    var key = String(competenceId);
    if (settings.force) delete loadedCompetenceDays[key];
    if (loadedCompetenceDays[key] && !settings.force) {
      return Promise.resolve(days().filter(function (day) { return idsEqual(day.competenceId || day.competencia_id, competenceId); }));
    }
    state.reviewLoading = true;
    return apiRequest("/marcacoes?competencia_id=" + encodeURIComponent(competenceId)).then(function (payload) {
      var markings = apiCollection(payload, ["marcacoes", "items"]).map(normalizeMarking);
      replaceAttendanceForCompetence(competenceId, markings);
      loadedCompetenceDays[key] = true;
      if (idsEqual(state.selectedCompetenceId, competenceId) && markings.length && !employeeDays(state.selectedEmployeeId).length) {
        state.selectedEmployeeId = markings[0].employeeId || markings[0].funcionario_id;
        var firstEmployeeDay = employeeDays(state.selectedEmployeeId)[0];
        state.selectedDayId = firstEmployeeDay ? firstEmployeeDay.id : markings[0].id;
        state.selectedDayIds = [];
      }
      return markings;
    }).finally(function () {
      state.reviewLoading = false;
    });
  }

  function loadFilesForCompetence(competenceId, options) {
    if (state.apiMode !== "online" || competenceId === null || competenceId === undefined) return Promise.resolve([]);
    var settings = options || {};
    var key = String(competenceId);
    if (settings.force) delete loadedCompetenceFiles[key];
    if (loadedCompetenceFiles[key] && !settings.force) {
      return Promise.resolve(files().filter(function (file) {
        return idsEqual(file.competenceId || file.competencia_id, competenceId);
      }));
    }
    return apiRequest("/arquivos?competencia_id=" + encodeURIComponent(competenceId)).then(function (payload) {
      var receivedFiles = apiCollection(payload, ["arquivos", "files", "items"]).map(normalizeReceivedFile);
      replaceFilesForCompetence(competenceId, receivedFiles);
      loadedCompetenceFiles[key] = true;
      return receivedFiles;
    });
  }

  function loadCompetenceSummary(competenceId, options) {
    if (state.apiMode !== "online" || competenceId === null || competenceId === undefined) return Promise.resolve(null);
    var settings = options || {};
    var key = String(competenceId);
    if (!data.competenceSummaries || typeof data.competenceSummaries !== "object") {
      data.competenceSummaries = Object.create(null);
      data.resumosCompetencia = data.competenceSummaries;
    }
    if (settings.force) {
      delete loadedCompetenceSummaries[key];
      delete data.competenceSummaries[key];
    }
    if (loadedCompetenceSummaries[key] && !settings.force) {
      if (idsEqual(state.selectedCompetenceId, competenceId)) {
        state.competenceSummaryLoading = false;
        state.competenceSummaryError = "";
      }
      return Promise.resolve(data.competenceSummaries[key] || null);
    }

    var sequence = (competenceSummarySequences[key] || 0) + 1;
    competenceSummarySequences[key] = sequence;
    if (idsEqual(state.selectedCompetenceId, competenceId)) {
      state.competenceSummaryLoading = true;
      state.competenceSummaryError = "";
    }
    return apiRequest("/apuracao?competencia_id=" + encodeURIComponent(competenceId)).then(function (payload) {
      if (competenceSummarySequences[key] !== sequence) return null;
      var summary = normalizeCompetenceSummary(payload);
      if (summary.competence) updateCompetenceFromPayload(competenceId, summary.competence);
      data.competenceSummaries[key] = summary;
      loadedCompetenceSummaries[key] = true;
      if (idsEqual(state.selectedCompetenceId, competenceId)) state.competenceSummaryError = "";
      return summary;
    }).catch(function (error) {
      if (competenceSummarySequences[key] !== sequence) return null;
      delete loadedCompetenceSummaries[key];
      delete data.competenceSummaries[key];
      if (idsEqual(state.selectedCompetenceId, competenceId)) {
        state.competenceSummaryError = error && error.message || "Não foi possível carregar a apuração desta competência.";
      }
      return null;
    }).finally(function () {
      if (competenceSummarySequences[key] === sequence && idsEqual(state.selectedCompetenceId, competenceId)) {
        state.competenceSummaryLoading = false;
      }
    });
  }

  function loadCompetenceData(competenceId, options) {
    var settings = options || {};
    var summaryPromise = loadCompetenceSummary(competenceId, { force: settings.summaryForce === true });
    if (settings.summaryForce === true) {
      summaryPromise.then(function () {
        if (idsEqual(state.selectedCompetenceId, competenceId) && state.route === "competency-summary") render();
      });
    }
    // A apuração materializa o calendário. Aguarde seu commit antes de buscar
    // /marcacoes para que a Conferência receba também os dias recém-gerados.
    return summaryPromise.then(function (summary) {
      return Promise.all([
        loadAttendanceForCompetence(competenceId, settings),
        loadFilesForCompetence(competenceId, settings),
      ]).then(function (results) {
        if (summary) applyApurationDetails(competenceId, summary.markings);
        return { markings: results[0], files: results[1], summary: summary };
      });
    });
  }

  function companyScales(companyId) {
    var targetId = companyId !== undefined ? companyId : state.selectedCompanyId;
    if (targetId === null || targetId === undefined) return [];
    return scales().filter(function (item) {
      return idsEqual(item.companyId || item.empresa_id, targetId);
    });
  }

  function replaceScalesForCompany(companyId, items) {
    var remaining = scales().filter(function (item) {
      return !idsEqual(item.companyId || item.empresa_id, companyId);
    });
    var merged = remaining.concat(items).sort(compareEntityNames);
    data.scales = merged;
    data.escalas = merged;
    return items;
  }

  function loadScalesForCompany(companyId, options) {
    if (companyId === null || companyId === undefined) return Promise.resolve([]);
    if (state.apiMode !== "online") return Promise.resolve(companyScales(companyId));
    var settings = options || {};
    var key = String(companyId);
    if (settings.force) delete loadedCompanyScales[key];
    if (loadedCompanyScales[key] && !settings.force) return Promise.resolve(companyScales(companyId));

    var sequence = (companyScaleLoadSequences[key] || 0) + 1;
    companyScaleLoadSequences[key] = sequence;
    if (idsEqual(state.selectedCompanyId, companyId)) {
      state.scalesLoading = true;
      state.scalesError = "";
    }
    return apiRequest("/escalas?empresa_id=" + encodeURIComponent(companyId)).then(function (payload) {
      if (companyScaleLoadSequences[key] !== sequence) return companyScales(companyId);
      var items = apiCollection(payload, ["escalas", "scales"]).map(normalizeScale);
      replaceScalesForCompany(companyId, items);
      loadedCompanyScales[key] = true;
      return items;
    }).catch(function (error) {
      if (companyScaleLoadSequences[key] === sequence && idsEqual(state.selectedCompanyId, companyId)) {
        state.scalesError = error && error.message || "Não foi possível carregar as escalas.";
      }
      throw error;
    }).finally(function () {
      if (companyScaleLoadSequences[key] === sequence && idsEqual(state.selectedCompanyId, companyId)) {
        state.scalesLoading = false;
      }
    });
  }

  function bootstrapApiData() {
    state.apiMode = "loading";
    state.apiError = "";
    return Promise.all([
      apiRequest("/empresas", { timeout: 5000 }),
      apiRequest("/funcionarios", { timeout: 5000 }),
      apiRequest("/competencias", { timeout: 5000 }),
    ]).then(function (responses) {
      var companyList = apiCollection(responses[0], ["empresas", "companies"]).map(normalizeCompany);
      var employeeList = apiCollection(responses[1], ["funcionarios", "employees"]).map(normalizeEmployee);
      var competenceList = apiCollection(responses[2], ["competencias", "competencies"]).map(function (item) { return normalizeCompetence(item, employeeList); });
      data.companies = companyList;
      data.empresas = companyList;
      data.employees = employeeList;
      data.funcionarios = employeeList;
      data.competencies = competenceList;
      data.competencias = competenceList;
      data.scales = [];
      data.escalas = data.scales;
      data.attendanceDays = [];
      data.dias = data.attendanceDays;
      data.files = [];
      data.arquivos = data.files;
      loadedCompetenceDays = Object.create(null);
      loadedCompetenceFiles = Object.create(null);
      loadedCompetenceSummaries = Object.create(null);
      competenceSummarySequences = Object.create(null);
      loadedCompanyScales = Object.create(null);
      companyScaleLoadSequences = Object.create(null);
      data.competenceSummaries = Object.create(null);
      data.resumosCompetencia = data.competenceSummaries;
      data.importPreviewRows = [];
      data.linhasPrevia = data.importPreviewRows;
      data.importAnalysis = null;
      data.analiseImportacao = null;
      data.employeeProgress = [];
      data.progressoFuncionarios = data.employeeProgress;
      data.pendingIssues = [];
      data.pendencias = data.pendingIssues;
      data.activityTimeline = [];
      data.historicoCompetencia = data.activityTimeline;
      data.dashboard = {
        indicators: {
          open: competenceList.filter(function (item) { return item.status === "aberta"; }).length,
          inReview: competenceList.filter(function (item) { return item.status === "em_conferencia"; }).length,
          withPendingIssues: competenceList.filter(function (item) { return Number(item.pendingCount) > 0; }).length,
          closedThisMonth: competenceList.filter(function (item) { return item.status === "fechada"; }).length,
        },
        recentCompetencies: competenceList.slice(),
      };
      data.ocr = { document: { fileName: "", page: 1, pageCount: 1, zoom: 100, rotation: 0, contrast: 100 }, extractedRows: [] };
      state.ocr = Utils.safeClone(data.ocr);
      data.fileTypeOptions = [
        { value: "auto", label: "Detectar automaticamente" },
        { value: "txt_clock", label: "TXT estruturado" },
      ];
      state.apiMode = "online";
      state.apiError = "";
      return true;
    }).catch(function (error) {
      state.apiMode = "offline";
      state.apiError = error && error.message || "API indisponível.";
      return false;
    });
  }

  function optionalIdsEqual(left, right) {
    if ((left === null || left === undefined) && (right === null || right === undefined)) return true;
    return idsEqual(left, right);
  }

  function resetCompetencyTransientState() {
    importAnalysisSequence += 1;
    if (state.apiMode === "online" && state.settings.autosave && Object.keys(pendingDaySaves).length) flushPendingDaySaves();
    else root.clearTimeout(autosaveTimer);
    autosaveTimer = null;
    state.selectedEmployeeId = null;
    state.selectedDayId = null;
    state.selectedDayIds = [];
    state.reviewFilter = "all";
    state.competencyTab = "summary";
    state.importType = "auto";
    state.selectedImportFile = null;
    state.importAnalysis = false;
    state.importLoading = false;
    state.importConfirming = false;
    state.importError = "";
    state.importConflicts = [];
    state.importPreviewFilter = "all";
    state.importPreviewEmployeeId = "";
    state.selectedImportRowIds = [];
    state.reviewLoading = false;
    state.competenceSummaryLoading = false;
    state.competenceSummaryError = "";
    state.exportExcelLoading = false;
    state.competenceLifecycleLoading = false;
    state.competenceLifecycleAction = "";
    state.competenceLifecycleError = "";
    state.autosaveStatus = autosaveFlushPromise
      ? "saving"
      : Object.keys(pendingDaySaves).length ? "unsaved" : "saved";
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
    var competenceDays = days().filter(function (day) { return idsEqual(day.competenceId || day.competencia_id, descriptor.competenceId); });
    var selectedEmployeeHasDays = competenceDays.some(function (day) { return idsEqual(day.employeeId || day.funcionario_id, state.selectedEmployeeId); });
    if (!scopedEmployees.some(function (item) { return idsEqual(item.id, state.selectedEmployeeId); }) || (!selectedEmployeeHasDays && competenceDays.length)) {
      var firstDayEmployeeId = competenceDays[0] && (competenceDays[0].employeeId || competenceDays[0].funcionario_id);
      var firstEmployeeWithDays = scopedEmployees.find(function (item) { return idsEqual(item.id, firstDayEmployeeId); });
      state.selectedEmployeeId = firstEmployeeWithDays ? firstEmployeeWithDays.id : scopedEmployees[0] ? scopedEmployees[0].id : null;
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

  function competencyIsClosed(competence) {
    var target = competence || currentCompetency();
    return Boolean(target) && statusFromBackend(target.status) === "fechada";
  }

  function closedCompetencyWarning(actionLabel) {
    showToast(
      "Competência fechada.",
      "warning",
      (actionLabel || "Esta ação") + " fica disponível depois que a competência for reaberta."
    );
  }

  function ensureCompetencyWritable(actionLabel) {
    if (!competencyIsClosed()) return true;
    closedCompetencyWarning(actionLabel);
    return false;
  }

  function updateCompetenceFromPayload(competenceId, payload) {
    var existing = competencies().find(function (item) { return idsEqual(item.id, competenceId); });
    if (!existing) return null;
    var source = valueFromAliases(payload, ["competencia", "competence"]);
    if (!source || typeof source !== "object" || Array.isArray(source)) source = payload || {};
    var merged = Object.assign({}, existing, source, { id: existing.id });
    if (Object.prototype.hasOwnProperty.call(source, "status") && !Object.prototype.hasOwnProperty.call(source, "statusLabel")) {
      delete merged.statusLabel;
    }
    if (Object.prototype.hasOwnProperty.call(source, "data_fechamento")) {
      merged.closedAt = source.data_fechamento;
    }
    var normalized = normalizeCompetence(merged, employees());
    Object.keys(existing).forEach(function (key) { delete existing[key]; });
    Object.assign(existing, normalized);
    return existing;
  }

  function refreshAffectedCompetence(competenceId, options) {
    return apiRequest("/competencias/" + encodeURIComponent(competenceId)).then(function (payload) {
      return updateCompetenceFromPayload(competenceId, payload);
    }).then(function (competence) {
      return loadCompetenceSummary(competenceId, { force: true }).then(function (summary) {
        var attendanceRequest = options && options.reloadAttendance
          ? loadAttendanceForCompetence(competenceId, { force: true })
          : Promise.resolve(null);
        return attendanceRequest.then(function (markings) {
          if (summary) applyApurationDetails(competenceId, summary.markings);
          return { competence: competence, summary: summary, markings: markings };
        });
      });
    });
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

  function dayIsOperationallyPending(day) {
    if (!day) return false;
    if (day.pendingOperational !== undefined || day.pendente_operacional !== undefined) {
      return day.pendingOperational === true || day.pendente_operacional === true;
    }
    var unresolved = (day.issues || day.pendencias || []).some(function (issue) {
      return !issue || issue.resolved !== true;
    });
    return day.pendingCalculation === true || day.pendente_calculo === true || !dayIsConfirmed(day) || unresolved;
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
      var status = day.status || day.status_dia || (day.current && (day.current.situation || day.current.status)) || "normal";
      if (state.reviewFilter === "pending") return dayIsOperationallyPending(day);
      if (state.reviewFilter === "unconfirmed") return !dayIsConfirmed(day);
      if (state.reviewFilter === "absences") return ["falta", "atestado", "folga", "afastamento"].indexOf(status) !== -1;
      return true;
    });
  }

  function ensureReviewSelection() {
    var visible = visibleReviewDays();
    if (!visible.some(function (day) { return idsEqual(day.id, state.selectedDayId); })) {
      var current = findDay(state.selectedDayId);
      var date = current && (current.date || current.data);
      var ordered = visible.slice().sort(function (a, b) { return String(a.date || a.data).localeCompare(String(b.date || b.data)); });
      var next = date && ordered.find(function (day) { return (day.date || day.data) > date; });
      var previous = date && ordered.filter(function (day) { return (day.date || day.data) < date; }).pop();
      var selected = next || previous || visible[0];
      state.selectedDayId = selected ? selected.id : null;
    }
    state.selectedDayIds = state.selectedDayIds.filter(function (id) {
      return visible.some(function (day) { return idsEqual(day.id, id); });
    });
  }

  function sidebarNavigation() {
    var company = currentCompany();
    var competence = currentCompetency();
    var primary = [{ id: "companies", label: "Todas as empresas", icon: "briefcase" }, { id: "calendar", label: "Calendário", icon: "calendar" }];
    if (!company) return { primary: primary, secondary: [], secondaryLabel: "" };

    primary = primary.concat([
      { id: "company-overview", label: "Visão geral", icon: "dashboard" },
      { id: "company-employees", label: "Funcionários", icon: "users" },
      { id: "company-scales", label: "Escalas", icon: "clock" },
      { id: "company-ocorrencias", label: "Ocorrências / Afastamentos", icon: "calendar" },
      { id: "company-banco-horas", label: "Banco de horas", icon: "clock" },
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
      return dayIsOperationallyPending(day);
    }).length;
  }

  function render(options) {
    var settings = options || {};
    var main = byId("mainContent");
    var reviewKey = state.route === "review" ? JSON.stringify([state.selectedCompanyId, state.selectedCompetenceId, state.selectedEmployeeId, state.reviewFilter]) : "";
    var scroll = captureReviewScroll(main, reviewKey);
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
    var environmentLabel = document.querySelector(".topbar__context .eyebrow");
    if (environmentLabel) {
      environmentLabel.textContent = state.apiMode === "online" ? "Ambiente integrado" : state.apiMode === "loading" ? "Conectando à API" : "Ambiente de demonstração";
    }
    byId("topbarContext").textContent = !company
      ? (state.route === "calendar" ? "Calendário geral" : "Todas as empresas")
      : (company.name || company.nome) + (competency ? " · " + (competency.label || Utils.formatCompetence(competency)) : "");

    main.dataset.route = state.route;
    main.dataset.reviewKey = reviewKey;
    main.innerHTML = state.route === "calendar" ? root.OnPontoCalendario.render(state, data, Components) : Screens.render(state.route, state, data, Components);
    restoreReviewScroll(main, scroll);
    document.title = screenTitle() + " · On Ponto";

    Array.prototype.forEach.call(main.querySelectorAll('[data-indeterminate="true"]'), function (checkbox) {
      checkbox.indeterminate = true;
    });

    var target = settings.focus || renderFocus;
    renderFocus = null;
    if (target) {
      root.requestAnimationFrame(function () {
        if (main.dataset.reviewKey === reviewKey) focusCell(target.dayId, target.field, Boolean(scroll));
      });
    } else if (settings.focusMain) {
      root.requestAnimationFrame(function () { main.focus({ preventScroll: true }); });
    }
  }

  function captureReviewScroll(main, key) {
    if (!key || main.dataset.reviewKey !== key) return null;
    return [".attendance-table-wrap", ".review-context"].map(function (selector) {
      var element = main.querySelector(selector);
      return { selector: selector, top: element ? element.scrollTop : 0, left: element ? element.scrollLeft : 0 };
    });
  }

  function restoreReviewScroll(main, positions) {
    (positions || []).forEach(function (position) {
      var element = main.querySelector(position.selector);
      if (element) { element.scrollTop = position.top; element.scrollLeft = position.left; }
    });
  }

  function screenTitle() {
    return {
      companies: "Empresas",
      "company-overview": "Visão geral",
      "company-employees": "Funcionários",
      "company-scales": "Escalas",
      "company-ocorrencias": "Ocorrências / Afastamentos",
      "company-banco-horas": "Banco de horas",
      calendar: "Calendário",
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
      if (next.view === "calendar") return root.OnPontoCalendario.load();
      if (next.view === "company-ocorrencias") return root.OnPontoOcorrencias.load();
      if (next.view === "company-banco-horas") return root.OnPontoBancoHoras.load();
      var summaryRequested = next.view === "competency-summary";
      if (state.apiMode === "online" && next.competenceId && (summaryRequested || !loadedCompetenceDays[String(next.competenceId)] || !loadedCompetenceFiles[String(next.competenceId)])) {
        var loading = loadCompetenceData(next.competenceId, { summaryForce: summaryRequested });
        render();
        loading.then(function () {
          applyRouteContext(next);
          render({ focusMain: !(options && options.keepFocus) });
        }).catch(function (error) {
          state.reviewLoading = false;
          render({ focusMain: !(options && options.keepFocus) });
          showToast("Não foi possível carregar os dados da competência.", "error", error && error.message);
        });
      } else if (state.apiMode === "online" && next.companyId && ["company-employees", "company-scales", "company-settings"].indexOf(next.view) !== -1 && !loadedCompanyScales[String(next.companyId)]) {
        var scalesLoading = loadScalesForCompany(next.companyId);
        render();
        scalesLoading.then(function () {
          if (idsEqual(state.selectedCompanyId, next.companyId)) render({ focusMain: !(options && options.keepFocus) });
        }).catch(function (error) {
          if (!idsEqual(state.selectedCompanyId, next.companyId)) return;
          render({ focusMain: !(options && options.keepFocus) });
          showToast("Não foi possível carregar as escalas da empresa.", "error", error && error.message);
        });
      } else render({ focusMain: !(options && options.keepFocus) });
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
    closeDialog(undefined, true);
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
    if (config.wide) dialog.classList.add("confirmation-dialog--wide");
    var bodyAnchor = dialog.querySelector(".dialog-actions");
    var fields = Array.isArray(config.fields) ? config.fields : config.field ? [config.field] : [];
    var fieldsHost = bodyAnchor.parentNode;
    if (config.fieldLayout === "grid" && fields.length) {
      fieldsHost = document.createElement("div");
      fieldsHost.className = "dialog-fields-grid";
      bodyAnchor.parentNode.insertBefore(fieldsHost, bodyAnchor);
    }
    fields.forEach(function (field, index) {
      var fieldId = config.field && !Array.isArray(config.fields) ? "dialogField" : "dialogField-" + String(field.name || index).replace(/[^A-Za-z0-9_-]/g, "-");
      var label = document.createElement("label");
      label.className = "dialog-field" + (field.fullWidth ? " dialog-field--full" : "");
      label.dataset.dialogFieldWrap = field.name || "value";
      label.htmlFor = fieldId;
      label.innerHTML = '<span>' + Utils.escapeHtml(field.label || "Valor") + "</span>" + dialogFieldMarkup(field, fieldId) + (field.help ? '<small class="dialog-field-help">' + Utils.escapeHtml(field.help) + "</small>" : "");
      if (fieldsHost === bodyAnchor.parentNode) fieldsHost.insertBefore(label, bodyAnchor);
      else fieldsHost.appendChild(label);
    });
    if (config.html) {
      var details = document.createElement("div");
      details.className = "dialog-rich-content";
      details.innerHTML = config.html;
      bodyAnchor.parentNode.insertBefore(details, bodyAnchor);
    }
    if (fields.length) {
      var error = document.createElement("div");
      error.className = "inline-feedback inline-feedback--error dialog-form-error";
      error.id = "dialogFormError";
      error.setAttribute("role", "alert");
      error.hidden = true;
      bodyAnchor.parentNode.insertBefore(error, bodyAnchor);
    }
    pendingDialog = { dialog: dialog, config: config, fields: fields, trigger: trigger, busy: false };
    refreshConditionalDialogFields(pendingDialog);
    dialog.addEventListener("change", function () { refreshConditionalDialogFields(pendingDialog); });
    dialog.addEventListener("cancel", function (event) {
      event.preventDefault();
      closeDialog();
    });
    var form = dialog.querySelector("form");
    if (form) form.addEventListener("submit", function (event) {
      event.preventDefault();
      confirmDialog();
    });
    dialog.showModal();
    var first = dialog.querySelector("input, textarea, select") || dialog.querySelector('[data-action="confirm-current-dialog"]');
    if (first) root.requestAnimationFrame(function () { first.focus(); });
  }

  function dialogFieldMarkup(field, fieldId) {
    var value = field.value === undefined || field.value === null ? "" : field.value;
    var common = ' id="' + Utils.escapeHtml(fieldId) + '" name="' + Utils.escapeHtml(field.name || "dialogField") + '" data-dialog-field="' + Utils.escapeHtml(field.name || "value") + '"' +
      (field.required ? " required" : "") +
      (field.autocomplete ? ' autocomplete="' + Utils.escapeHtml(field.autocomplete) + '"' : "") +
      (field.min !== undefined ? ' min="' + Utils.escapeHtml(field.min) + '"' : "") +
      (field.max !== undefined ? ' max="' + Utils.escapeHtml(field.max) + '"' : "") +
      (field.step !== undefined ? ' step="' + Utils.escapeHtml(field.step) + '"' : "") +
      (field.maxlength !== undefined ? ' maxlength="' + Utils.escapeHtml(field.maxlength) + '"' : "");
    if (field.type === "select") {
      return "<select" + common + ">" + (field.options || []).map(function (item) {
        var optionValue = typeof item === "string" ? item : item.value;
        var label = typeof item === "string" ? (STATUS_LABELS[item] || item) : item.label;
        return '<option value="' + Utils.escapeHtml(optionValue) + '"' + (String(optionValue) === String(value) ? " selected" : "") + ">" + Utils.escapeHtml(label) + "</option>";
      }).join("") + "</select>";
    }
    if (field.type === "textarea") {
      return "<textarea" + common + ' rows="' + Utils.escapeHtml(field.rows || 3) + '" placeholder="' + Utils.escapeHtml(field.placeholder || "") + '">' + Utils.escapeHtml(value) + "</textarea>";
    }
    if (field.type === "checkbox") {
      return "<input" + common + ' type="checkbox" value="' + Utils.escapeHtml(value || "true") + '"' + (field.checked ? " checked" : "") + ">";
    }
    return "<input" + common + ' type="' + Utils.escapeHtml(field.type || "text") + '" value="' + Utils.escapeHtml(value) + '" placeholder="' + Utils.escapeHtml(field.placeholder || "") + '">';
  }

  function refreshConditionalDialogFields(current) {
    if (!current) return;
    var values = dialogValues(current);
    current.fields.forEach(function (field) {
      var name = field.name || "value";
      var wrapper = current.dialog.querySelector('[data-dialog-field-wrap="' + String(name).replace(/"/g, '\\"') + '"]');
      var element = current.dialog.querySelector('[data-dialog-field="' + String(name).replace(/"/g, '\\"') + '"]');
      var visible = typeof field.visibleWhen !== "function" || field.visibleWhen(values);
      if (wrapper) wrapper.hidden = !visible;
      if (element) {
        element.disabled = !visible || current.busy;
        element.required = Boolean(field.required && visible);
      }
    });
  }

  function setDialogError(current, message, fieldName) {
    if (!current || pendingDialog !== current) return;
    current.dialog.querySelectorAll("[data-dialog-field]").forEach(function (element) {
      element.removeAttribute("aria-invalid");
    });
    if (fieldName) {
      var invalid = current.dialog.querySelector('[data-dialog-field="' + String(fieldName).replace(/"/g, '\\"') + '"]');
      if (invalid) {
        invalid.setAttribute("aria-invalid", "true");
        invalid.focus();
      }
    }
    var error = current.dialog.querySelector("#dialogFormError");
    if (!error) {
      showToast(message, "error");
      return;
    }
    error.textContent = message;
    error.hidden = false;
  }

  function clearDialogError(current) {
    if (!current) return;
    current.dialog.querySelectorAll("[data-dialog-field]").forEach(function (element) {
      element.removeAttribute("aria-invalid");
    });
    var error = current.dialog.querySelector("#dialogFormError");
    if (error) {
      error.textContent = "";
      error.hidden = true;
    }
  }

  function setDialogBusy(current, busy) {
    if (!current || pendingDialog !== current) return;
    current.busy = busy;
    current.dialog.setAttribute("aria-busy", busy ? "true" : "false");
    current.dialog.querySelectorAll("input, textarea, select, button").forEach(function (element) {
      element.disabled = busy;
    });
    var confirmButton = current.dialog.querySelector('[data-action="confirm-current-dialog"]');
    if (confirmButton) {
      if (!confirmButton.dataset.idleLabel) confirmButton.dataset.idleLabel = confirmButton.textContent;
      var label = confirmButton.querySelector(".button-label");
      if (label) label.textContent = busy ? current.config.busyLabel || "Salvando..." : confirmButton.dataset.idleLabel;
      else confirmButton.textContent = busy ? current.config.busyLabel || "Salvando..." : confirmButton.dataset.idleLabel;
    }
    if (!busy) refreshConditionalDialogFields(current);
  }

  function dialogValues(current) {
    var values = {};
    current.fields.forEach(function (field) {
      var name = field.name || "value";
      var element = current.dialog.querySelector('[data-dialog-field="' + String(name).replace(/"/g, '\\"') + '"]');
      values[name] = element && element.type === "checkbox" ? element.checked : element ? element.value : undefined;
    });
    return values;
  }

  function validateDialog(current, values) {
    for (var index = 0; index < current.fields.length; index += 1) {
      var field = current.fields[index];
      var name = field.name || "value";
      if (typeof field.visibleWhen === "function" && !field.visibleWhen(values)) continue;
      var rawValue = values[name];
      var comparable = typeof rawValue === "string" ? rawValue.trim() : rawValue;
      var element = current.dialog.querySelector('[data-dialog-field="' + String(name).replace(/"/g, '\\"') + '"]');
      if (field.required && (comparable === "" || comparable === undefined || comparable === null || comparable === false)) {
        return { message: field.requiredMessage || "Preencha " + String(field.label || "o campo").toLowerCase() + ".", field: name };
      }
      if (element && typeof element.checkValidity === "function" && !element.checkValidity()) {
        return { message: field.invalidMessage || "Informe um valor válido para " + String(field.label || "o campo").toLowerCase() + ".", field: name };
      }
      if (typeof field.validate === "function") {
        var fieldResult = field.validate(rawValue, values);
        if (fieldResult) return typeof fieldResult === "string" ? { message: fieldResult, field: name } : fieldResult;
      }
    }
    if (typeof current.config.validate === "function") {
      var result = current.config.validate(values);
      if (result) return typeof result === "string" ? { message: result } : result;
    }
    return null;
  }

  function confirmDialog() {
    if (!pendingDialog) return;
    var current = pendingDialog;
    if (current.busy) return;
    if (Array.isArray(current.config.fields)) {
      clearDialogError(current);
      var values = dialogValues(current);
      var validation = validateDialog(current, values);
      if (validation) {
        setDialogError(current, validation.message || "Revise os campos informados.", validation.field);
        return;
      }
      var result;
      try {
        result = typeof current.config.onConfirm === "function" ? current.config.onConfirm(values) : undefined;
      } catch (error) {
        setDialogError(current, error && error.message || "Não foi possível concluir a operação.");
        return;
      }
      if (result && typeof result.then === "function") {
        setDialogBusy(current, true);
        Promise.resolve(result).then(function (saved) {
          if (pendingDialog !== current) return;
          closeDialog(false, true);
          if (typeof current.config.onSaved === "function") return current.config.onSaved(saved);
        }).catch(function (error) {
          if (pendingDialog !== current) {
            showToast("Registro salvo, mas não foi possível atualizar a tela.", "error", error && error.message);
            return;
          }
          setDialogBusy(current, false);
          setDialogError(current, error && error.message || "Não foi possível salvar os dados.");
        });
        return;
      }
      closeDialog(false, true);
      return;
    }
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

  function closeDialog(restoreFocus, force) {
    if (!pendingDialog) {
      byId("dialogRoot").innerHTML = "";
      return;
    }
    if (pendingDialog.busy && !force) return;
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
      { keys: "N / F / A / C", label: "Alterar ou confirmar o dia selecionado" },
    ];
    shortcuts = shortcuts.filter(function (shortcut) { return shortcut.action !== "status_review" && String(shortcut.keys || "").toUpperCase() !== "R"; });
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

  function analyzeDemoImport() {
    if (!ensureCompetencyWritable("A importação")) return;
    if (!state.selectedImportFile) {
      state.selectedImportFile = { name: "ALOG_001.txt", size: 68420, type: "text/plain", demo: true };
      showToast("Arquivo de demonstração selecionado.", "info", "A API está indisponível; nenhum arquivo será enviado.");
    }
    state.importLoading = true;
    render();
    var analysisCompanyId = state.selectedCompanyId;
    var analysisCompetenceId = state.selectedCompetenceId;
    var analysisSequence = ++importAnalysisSequence;
    root.setTimeout(function () {
      if (analysisSequence !== importAnalysisSequence || !idsEqual(analysisCompanyId, state.selectedCompanyId) || !idsEqual(analysisCompetenceId, state.selectedCompetenceId)) return;
      var result = contextualizeImportAnalysis(Utils.safeClone(data.importAnalysis || data.analiseImportacao));
      result.fileName = state.selectedImportFile.name;
      result.requestedType = state.importType;
      result.detectedType = "txt_clock";
      result.detectedFormat = "TXT estruturado · demonstração";
      result.saved = false;
      (result.rows || []).forEach(function (row) {
        row.selected = true;
        row.selecionado = true;
        row.employeeFound = true;
        row.outsideCompetence = false;
      });
      state.importAnalysis = result;
      state.selectedImportRowIds = (result.rows || []).map(function (row) { return row.id; });
      state.importPreviewFilter = "all";
      state.importPreviewEmployeeId = "";
      state.importLoading = false;
      state.importError = "";
      render();
      showToast("Análise de demonstração concluída.", "success", result.pendingCount + " pendências encontradas; nada foi salvo.");
    }, 420);
  }

  function analyzeImport() {
    if (state.importLoading) return;
    if (!ensureCompetencyWritable("A importação")) return;
    if (state.apiMode !== "online") {
      analyzeDemoImport();
      return;
    }
    if (!state.selectedImportFile || !state.selectedImportFile.file) {
      showToast("Selecione um arquivo TXT ou XLSX para analisar.", "warning");
      return;
    }
    var fileName = String(state.selectedImportFile.name || "");
    if (!/\.(txt|xlsx)$/i.test(fileName)) {
      showToast("Formato não suportado nesta etapa.", "error", "Selecione somente um arquivo .txt ou .xlsx.");
      return;
    }
    var competence = currentCompetency();
    if (!competence) {
      showToast("Selecione uma competência antes de analisar o arquivo.", "warning");
      return;
    }
    var analysisCompanyId = state.selectedCompanyId;
    var analysisCompetenceId = state.selectedCompetenceId;
    var analysisFile = state.selectedImportFile.file;
    var analysisSequence = ++importAnalysisSequence;
    function analysisContextIsActive() {
      return analysisSequence === importAnalysisSequence &&
        idsEqual(state.selectedCompanyId, analysisCompanyId) &&
        idsEqual(state.selectedCompetenceId, analysisCompetenceId) &&
        state.selectedImportFile && state.selectedImportFile.file === analysisFile;
    }
    var formData = new FormData();
    formData.append("empresa_id", String(analysisCompanyId));
    formData.append("competencia_id", String(analysisCompetenceId));
    formData.append("mes", String(competence.month || competence.mes));
    formData.append("ano", String(competence.year || competence.ano));
    formData.append("arquivo", analysisFile, fileName);
    state.importLoading = true;
    state.importError = "";
    state.importConflicts = [];
    render();
    apiRequest("/importadores/analisar", { method: "POST", body: formData, timeout: 30000 }).then(function (payload) {
      if (!analysisContextIsActive()) return;
      var result = normalizeImportAnalysis(payload);
      state.importAnalysis = result;
      state.selectedImportRowIds = result.rows.filter(function (row) { return row.selected && row.employeeFound; }).map(function (row) { return row.id; });
      state.importPreviewFilter = "all";
      state.importPreviewEmployeeId = "";
      loadFilesForCompetence(analysisCompetenceId, { force: true }).catch(function () {
        /* O arquivo continuará disponível ao recarregar a aba Arquivos. */
      });
      showToast("Análise concluída.", "success", result.recordCount + " dias encontrados; confira a prévia antes de salvar.");
    }).catch(function (error) {
      if (!analysisContextIsActive()) return;
      state.importAnalysis = false;
      state.selectedImportRowIds = [];
      state.importError = error && error.message || "Não foi possível analisar o TXT.";
      showToast("Não foi possível analisar o arquivo.", "error", state.importError);
    }).finally(function () {
      if (!analysisContextIsActive()) return;
      state.importLoading = false;
      render();
    });
  }

  function discardImport() {
    showDialog({
      title: "Descartar esta análise?",
      description: "A prévia e o arquivo selecionado serão removidos deste protótipo. Nenhum dado original será alterado.",
      confirmLabel: "Descartar análise",
      destructive: true,
      onConfirm: function () {
        importAnalysisSequence += 1;
        state.importAnalysis = false;
        state.selectedImportFile = null;
        state.selectedImportRowIds = [];
        state.importConflicts = [];
        state.importError = "";
        state.importPreviewFilter = "all";
        state.importPreviewEmployeeId = "";
        navigate("imports");
        showToast("Análise descartada.", "success");
      },
    });
  }

  function importConflictMessages(payload) {
    var source = payload || {};
    var conflicts = firstValue(source.conflitos, source.conflicts, source.erros, []);
    if (!Array.isArray(conflicts)) conflicts = conflicts ? [conflicts] : [];
    return conflicts.map(function (conflict) {
      if (typeof conflict === "string") return conflict;
      return conflict.message || conflict.mensagem || conflict.detail || "Registro não importado.";
    });
  }

  function saveDemoImportAndReview() {
    if (!ensureCompetencyWritable("A confirmação da importação")) return;
    if (state.importAnalysis && typeof state.importAnalysis === "object") state.importAnalysis.saved = true;
    var competence = currentCompetency();
    if (competence) {
      competence.status = "em_conferencia";
      competence.statusLabel = "Em conferência";
    }
    var selectedRows = (state.importAnalysis.rows || []).filter(function (row) {
      return state.selectedImportRowIds.some(function (id) { return idsEqual(id, row.id); });
    });
    var importedEmployeeId = selectedRows[0] && selectedRows[0].employeeId;
    var employee = companyEmployees().find(function (item) { return idsEqual(item.id, importedEmployeeId); }) || currentEmployee() || companyEmployees()[0] || null;
    state.selectedEmployeeId = employee ? employee.id : null;
    var firstDay = employee ? employeeDays(employee.id)[0] : null;
    state.selectedDayId = firstDay ? firstDay.id : null;
    state.reviewFilter = "all";
    state.selectedDayIds = [];
    navigate("review");
    showToast("Importação salva como prévia de demonstração.", "success", "A conferência continua pendente.");
  }

  function saveImportAndReview() {
    if (state.importConfirming) return;
    if (!ensureCompetencyWritable("A confirmação da importação")) return;
    if (!state.importAnalysis || typeof state.importAnalysis !== "object" || !(state.importAnalysis.rows || []).length) {
      showToast("Analise um arquivo desta competência antes de iniciar a conferência.", "warning");
      navigate("imports");
      return;
    }
    var analysis = state.importAnalysis;
    var confirmationCompanyId = state.selectedCompanyId;
    var confirmationCompetenceId = state.selectedCompetenceId;
    var confirmationFileId = analysis.fileId || analysis.arquivoId;
    var selectedIds = state.selectedImportRowIds.filter(function (id) {
      var row = analysis.rows.find(function (candidate) { return idsEqual(candidate.id, id); });
      return row && row.employeeFound;
    });
    if (!selectedIds.length) {
      showToast("Selecione ao menos um registro importável.", "warning", "Funcionários não cadastrados não podem ser confirmados.");
      return;
    }
    showDialog({
      title: "Salvar importação e iniciar conferência?",
      description: selectedIds.length + " registro" + (selectedIds.length === 1 ? " será adicionado" : "s serão adicionados") + " à competência. As batidas originais continuarão preservadas.",
      count: selectedIds.length,
      confirmLabel: "Salvar e conferir",
      icon: "check_circle",
      tone: "info",
      onConfirm: function () {
        function confirmationContextIsActive() {
          return idsEqual(state.selectedCompanyId, confirmationCompanyId) &&
            idsEqual(state.selectedCompetenceId, confirmationCompetenceId) &&
            state.importAnalysis === analysis;
        }
        if (!confirmationContextIsActive()) {
          showToast("A confirmação foi cancelada.", "warning", "A empresa ou a competência ativa mudou; revise a importação novamente.");
          return;
        }
        if (state.apiMode !== "online") {
          saveDemoImportAndReview();
          return;
        }
        state.importConfirming = true;
        state.importConflicts = [];
        render();
        var payload = {
          empresa_id: confirmationCompanyId,
          competencia_id: confirmationCompetenceId,
          arquivo_id: confirmationFileId,
          registros_ids: selectedIds,
        };
        var confirmationPersisted = false;
        apiRequest("/importadores/confirmar", { method: "POST", body: payload, timeout: 30000 }).then(function (response) {
          confirmationPersisted = true;
          var conflicts = importConflictMessages(response);
          var importedMarkingIds = firstValue(response && response.marcacoes_ids, response && response.markingIds, []);
          if (!Array.isArray(importedMarkingIds)) importedMarkingIds = [];
          var importedCountValue = firstValue(response && response.total_importados, response && response.importedCount);
          var importedCount = importedCountValue === null ? selectedIds.length - conflicts.length : Number(importedCountValue);
          if (!Number.isFinite(importedCount)) importedCount = 0;
          analysis.saved = importedCount > 0;
          var competence = competencies().find(function (item) {
            return idsEqual(item.id, confirmationCompetenceId) &&
              idsEqual(item.companyId || item.empresa_id, confirmationCompanyId);
          });
          if (competence && importedCount > 0) {
            competence.status = "em_conferencia";
            competence.statusLabel = "Em conferência";
          }
          if (confirmationContextIsActive()) state.importConflicts = conflicts;
          if (!importedCount) {
            if (confirmationContextIsActive()) {
              render();
              showToast("Nenhum registro foi importado.", "warning", conflicts.join(" ") || "Revise a seleção e tente novamente.");
            }
            return;
          }

          if (!confirmationContextIsActive()) {
            delete loadedCompetenceDays[String(confirmationCompetenceId)];
            showToast(
              "Importação confirmada.",
              conflicts.length ? "warning" : "success",
              "Os dados foram salvos na competência " + (competence ? competence.label || Utils.formatCompetence(competence) : confirmationCompetenceId) + "."
            );
            return;
          }

          return loadAttendanceForCompetence(confirmationCompetenceId, { force: true }).then(function (markings) {
            if (!confirmationContextIsActive()) {
              showToast(
                "Importação confirmada.",
                conflicts.length ? "warning" : "success",
                "Os dados foram salvos na competência " + (competence ? competence.label || Utils.formatCompetence(competence) : confirmationCompetenceId) + "."
              );
              return;
            }
            var firstImportedMarking = markings.find(function (marking) {
              return importedMarkingIds.some(function (id) { return idsEqual(id, marking.id); });
            });
            var selectedEmployeeId = firstImportedMarking && firstImportedMarking.employeeId || markings[0] && markings[0].employeeId;
            state.selectedEmployeeId = selectedEmployeeId || state.selectedEmployeeId;
            var firstDay = employeeDays(state.selectedEmployeeId)[0] || markings[0] || null;
            state.selectedDayId = firstDay ? firstDay.id : null;
            state.reviewFilter = "all";
            state.selectedDayIds = [];
            navigate("review");
            showToast("Importação confirmada.", conflicts.length ? "warning" : "success", conflicts.length ? importedCount + " importados. " + conflicts.join(" ") : importedCount + " registros importados e disponíveis na Conferência.");
          });
        }).catch(function (error) {
          if (confirmationPersisted) {
            if (confirmationContextIsActive()) {
              state.importError = "A importação foi confirmada, mas a Conferência não pôde ser recarregada agora.";
              render();
            }
            showToast(
              "Importação confirmada.",
              "warning",
              "Os dados foram salvos. Abra a Conferência novamente para recarregá-los. " + (error && error.message || "")
            );
            return;
          }
          if (!confirmationContextIsActive()) return;
          state.importError = error && error.message || "Não foi possível confirmar a importação.";
          showToast("Não foi possível confirmar a importação.", "error", state.importError);
        }).finally(function () {
          if (!confirmationContextIsActive()) return;
          state.importConfirming = false;
          if (state.route === "import-preview") render();
        });
      },
    });
  }

  function setSelectedFile(file) {
    if (!file) return;
    if (!ensureCompetencyWritable("A seleção de arquivo para importação")) return;
    if (state.importLoading || state.importConfirming) return;
    if (!/\.(txt|xlsx)$/i.test(String(file.name || ""))) {
      importAnalysisSequence += 1;
      state.selectedImportFile = null;
      state.importAnalysis = false;
      state.selectedImportRowIds = [];
      render();
      showToast("Formato não suportado nesta etapa.", "error", "Selecione somente um arquivo TXT ou XLSX.");
      return;
    }
    importAnalysisSequence += 1;
    state.selectedImportFile = { name: file.name, size: file.size, type: file.type, lastModified: file.lastModified, file: file };
    state.importAnalysis = false;
    state.selectedImportRowIds = [];
    state.importConflicts = [];
    state.importError = "";
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

  function previewRowsForSelection() {
    if (!state.importAnalysis || !Array.isArray(state.importAnalysis.rows)) return [];
    return state.importAnalysis.rows.filter(function (row) {
      if (!row.employeeFound) return false;
      if (state.importPreviewFilter === "pending" && !row.hasPendingIssue) return false;
      if (state.importPreviewEmployeeId && !idsEqual(row.employeeId, state.importPreviewEmployeeId)) return false;
      return true;
    });
  }

  function toggleImportRowSelection(rowId, checked) {
    var row = state.importAnalysis && state.importAnalysis.rows && state.importAnalysis.rows.find(function (item) { return idsEqual(item.id, rowId); });
    if (!row || !row.employeeFound) return;
    var exists = state.selectedImportRowIds.some(function (id) { return idsEqual(id, row.id); });
    if (checked && !exists) state.selectedImportRowIds.push(row.id);
    if (!checked && exists) state.selectedImportRowIds = state.selectedImportRowIds.filter(function (id) { return !idsEqual(id, row.id); });
    row.selected = checked;
    row.selecionado = checked;
    render();
  }

  function toggleAllImportRows(checked) {
    var visibleIds = previewRowsForSelection().map(function (row) { return row.id; });
    if (checked) {
      visibleIds.forEach(function (rowId) {
        if (!state.selectedImportRowIds.some(function (id) { return idsEqual(id, rowId); })) state.selectedImportRowIds.push(rowId);
      });
    } else {
      state.selectedImportRowIds = state.selectedImportRowIds.filter(function (id) {
        return !visibleIds.some(function (rowId) { return idsEqual(id, rowId); });
      });
    }
    if (state.importAnalysis && Array.isArray(state.importAnalysis.rows)) {
      state.importAnalysis.rows.forEach(function (row) {
        row.selected = state.selectedImportRowIds.some(function (id) { return idsEqual(id, row.id); });
        row.selecionado = row.selected;
      });
    }
    render();
  }

  function setDayStatus(day, status, options) {
    if (!day) return;
    if (!ensureCompetencyWritable("A alteração da situação do dia")) return;
    if (dayIsConfirmed(day) && !(options && options.allowConfirmed)) {
      showToast("Reabra a conferência antes de alterar este dia.", "warning");
      return;
    }
    var previous = day.status;
    day.status = status;
    day.status_dia = status;
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
    var employee = employees().find(function (item) {
      return idsEqual(item.id, day.employeeId || day.funcionario_id);
    });
    var employeeScaleId = employee ? firstValue(employee.escala_id, employee.scaleId) : null;
    if (employee && employeeScaleId === null) {
      day.pendingCalculation = true;
      day.pendente_calculo = true;
      day.pendingType = "escala_nao_cadastrada";
      day.pendencia_tipo = "escala_nao_cadastrada";
      day.pendingReason = "Escala não cadastrada para o funcionário.";
      day.pendencia_motivo = day.pendingReason;
    } else if (["atestado", "folga", "feriado", "falta", "afastamento", "domingo", "sem_expediente"].indexOf(status) !== -1) {
      day.pendingCalculation = false;
      day.pendente_calculo = false;
    }
    day.pendingOperational = !dayIsConfirmed(day) || day.pendingCalculation === true || day.pendente_calculo === true;
    day.pendente_operacional = day.pendingOperational;
    if (!(options && options.noUndo)) {
      state.undoStack.push({ type: "status", dayId: day.id, previous: previous, next: status });
    }
    addHistory(day, "Situação alterada de " + (STATUS_LABELS[previous] || previous || "não informada") + " para " + day.statusLabel + ".", "Operador local");
    queueAutosave(day);
    render();
  }

  function setStatusForSelected(status) {
    var day = findDay(state.selectedDayId);
    if (day) setDayStatus(day, status);
  }

  function addReviewCertificate(day) {
    if (!day || !ensureCompetencyWritable("O cadastro de atestado")) return;
    if (dayIsConfirmed(day)) {
      showToast("Reabra a conferência antes de alterar este dia.", "warning");
      return;
    }
    if (state.apiMode !== "online") {
      showToast("Ligue a API para cadastrar ocorrências.", "warning");
      return;
    }
    var competenceId = state.selectedCompetenceId;
    root.OnPontoOcorrencias.create({funcionario_id: day.employeeId || day.funcionario_id,
      tipo: "ATESTADO", data_inicio: day.date || day.data, data_fim: day.date || day.data}, {
      beforeSave: ensureAutosaveFlushedForLifecycle,
      onSaved: function () {
        return refreshAffectedCompetence(competenceId, { reloadAttendance: true }).then(function (result) {
          if (!result.summary) throw new Error("A apuração não foi carregada. Recarregue a Conferência para consultar o registro salvo.");
          render();
          showToast("Atestado cadastrado e apuração atualizada.", "success");
        });
      }
    });
  }

  function confirmDay(day, options) {
    if (!day || dayIsConfirmed(day)) return;
    if (!ensureCompetencyWritable("A confirmação do dia")) return;
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
    var unresolved = (day.issues || day.pendencias || []).some(function (issue) { return !issue || issue.resolved !== true; });
    day.pendingOperational = day.pendingCalculation === true || day.pendente_calculo === true || unresolved;
    day.pendente_operacional = day.pendingOperational;
    addHistory(day, "Dia marcado como conferido.", "Operador local");
    updateEmployeeProgress(day.employeeId || day.funcionario_id);
    queueAutosave(day, false, { syncCompetence: true });
    if (!(options && options.silent)) showToast("Dia conferido.", "success", "Salvar e conferir continuam sendo ações independentes.");
  }

  function reopenDay(day) {
    if (!day || !dayIsConfirmed(day)) return;
    if (!ensureCompetencyWritable("A reabertura do dia")) return;
    day.confirmed = false;
    day.conferido = false;
    day.reviewState = "reopened";
    if (day.review) {
      day.review.state = "reopened";
      day.review.confirmed = false;
      day.review.reopenedAt = new Date().toISOString();
    }
    day.pendingOperational = true;
    day.pendente_operacional = true;
    addHistory(day, "Conferência reaberta para ajustes.", "Operador local");
    updateEmployeeProgress(day.employeeId || day.funcionario_id);
    queueAutosave(day, false, { syncCompetence: true });
    render();
    showToast("Conferência reaberta.", "success", "As batidas originais permanecem intactas e os horários atuais podem ser ajustados.");
  }

  function updateEmployeeProgress(employeeId) {
    var progressList = data.employeeProgress || data.progressoFuncionarios || [];
    var item = progressList.find(function (progress) { return idsEqual(progress.employeeId || progress.funcionario_id, employeeId); });
    if (!item) return;
    var employeeDayList = employeeDays(employeeId);
    item.confirmedDayCount = employeeDayList.filter(dayIsConfirmed).length;
    item.pendingCount = employeeDayList.filter(dayIsOperationallyPending).length;
    item.progress = item.eligibleDayCount ? Math.round(item.confirmedDayCount / item.eligibleDayCount * 100) : 0;
  }

  function addHistory(day, description, actor) {
    if (state.apiMode === "online") return;
    var history = day.history || day.historico || [];
    var now = new Date();
    history.push({
      id: "history-ui-" + now.getTime() + "-" + history.length,
      at: now.toISOString(),
      timeLabel: now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
      actor: actor || "Operador local",
      description: description,
      title: description,
      type: "manual",
    });
    day.history = history;
    day.historico = history;
  }

  function recalculateDay(day) {
    var result = Utils.calculateJourney(currentSlots(day), day.expectedMinutes || day.jornadaPrevistaMinutos);
    // O saldo definitivo depende das tolerâncias e ocorrências apuradas na API.
    if (state.apiMode === "online") result.balanceMinutes = null;
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

  function daySavePayload(day) {
    var slots = currentSlots(day);
    return {
      entrada: slots.entry || null,
      saida_almoco: slots.breakStart || null,
      retorno_almoco: slots.breakEnd || null,
      saida: slots.exit || null,
      status_dia: statusToBackend(day.status_dia || day.status || day.current && day.current.status),
      conferido: dayIsConfirmed(day),
      observacoes: day.observation || day.observacao || day.current && (day.current.observation || day.current.observacao) || null,
    };
  }

  function flushPendingDaySaves() {
    root.clearTimeout(autosaveTimer);
    autosaveTimer = null;
    if (state.apiMode !== "online") return Promise.resolve([]);
    if (autosaveFlushPromise) {
      return autosaveFlushPromise.then(function () {
        return Object.keys(pendingDaySaves).length ? flushPendingDaySaves() : [];
      });
    }
    var keys = Object.keys(pendingDaySaves);
    if (!keys.length) {
      state.autosaveStatus = "saved";
      updateAutosaveIndicator();
      return Promise.resolve([]);
    }
    var batch = pendingDaySaves;
    activeDaySaves = batch;
    pendingDaySaves = Object.create(null);
    state.autosaveStatus = "saving";
    updateAutosaveIndicator();
    autosaveFlushPromise = keys.reduce(function (chain, key) {
      return chain.then(function (results) {
        var entry = batch[key];
        return apiRequest("/marcacoes/" + encodeURIComponent(entry.id), {
          method: "PATCH",
          body: entry.payload,
          timeout: 12000,
          keepalive: true,
        }).then(function (response) {
          var day = findDay(entry.id);
          if (day && Array.isArray(response.historico)) {
            day.history = response.historico;
            day.historico = response.historico;
          }
          return { ok: true, entry: entry, response: response };
        }).catch(function (error) {
          return { ok: false, entry: entry, error: error };
        }).then(function (result) { return results.concat(result); });
      });
    }, Promise.resolve([])).then(function (results) {
      var failed = results.filter(function (result) { return !result.ok; });
      var closedFailures = failed.filter(function (result) { return isClosedCompetenceError(result.error); });
      var retryableFailures = failed.filter(function (result) { return !isClosedCompetenceError(result.error); });
      retryableFailures.forEach(function (result) {
        var key = String(result.entry.id);
        if (!pendingDaySaves[key]) pendingDaySaves[key] = result.entry;
      });
      if (failed.length) {
        state.autosaveStatus = "error";
        updateAutosaveIndicator();
        if (closedFailures.length) {
          showToast("A competência foi fechada antes do salvamento.", "error", "As alterações recusadas não serão reenviadas automaticamente. Reabra a competência antes de editar.");
        } else {
          showToast("Não foi possível salvar todas as alterações.", "error", failed[0].error && failed[0].error.message || "Tente novamente.");
        }
      } else if (!Object.keys(pendingDaySaves).length) {
        state.autosaveStatus = "saved";
        updateAutosaveIndicator();
      }
      var competencesToRefresh = Object.create(null);
      results.forEach(function (result) {
        if ((result.ok && result.entry.syncCompetence) || (!result.ok && isClosedCompetenceError(result.error))) {
          if (result.entry.competenceId !== null && result.entry.competenceId !== undefined) {
            var competenceKey = String(result.entry.competenceId);
            if (!competencesToRefresh[competenceKey]) {
              competencesToRefresh[competenceKey] = {
                id: result.entry.competenceId,
                reloadAttendance: false,
              };
            }
            if (!result.ok && isClosedCompetenceError(result.error)) {
              competencesToRefresh[competenceKey].reloadAttendance = true;
            }
          }
        }
      });
      return Promise.all(Object.keys(competencesToRefresh).map(function (key) {
        var refresh = competencesToRefresh[key];
        return refreshAffectedCompetence(refresh.id, { reloadAttendance: refresh.reloadAttendance }).catch(function (error) {
          showToast("O status da competência não pôde ser atualizado.", "warning", error && error.message || "Abra a competência novamente para sincronizar.");
          return null;
        });
      })).then(function () {
        if (Object.keys(competencesToRefresh).some(function (key) { return idsEqual(key, state.selectedCompetenceId); })) render();
        return results;
      });
    }).finally(function () {
      autosaveFlushPromise = null;
      activeDaySaves = Object.create(null);
      if (state.autosaveStatus !== "error" && Object.keys(pendingDaySaves).length && state.settings.autosave) {
        autosaveTimer = root.setTimeout(flushPendingDaySaves, 120);
      }
    });
    return autosaveFlushPromise;
  }

  function queueAutosave(day, force, options) {
    if (competencyIsClosed()) {
      root.clearTimeout(autosaveTimer);
      autosaveTimer = null;
      return Promise.resolve([]);
    }
    state.autosaveRevision += 1;
    var revision = state.autosaveRevision;
    if (state.apiMode === "online" && day && day.id !== null && day.id !== undefined) {
      pendingDaySaves[String(day.id)] = {
        id: day.id,
        competenceId: day.competenceId || day.competencia_id || state.selectedCompetenceId,
        payload: daySavePayload(day),
        syncCompetence: true,
      };
    }
    if (!state.settings.autosave && !force) {
      state.autosaveStatus = Object.keys(pendingDaySaves).length ? "unsaved" : "saved";
      updateAutosaveIndicator();
      return Promise.resolve([]);
    }
    state.autosaveStatus = "saving";
    updateAutosaveIndicator();
    if (state.apiMode === "online") {
      root.clearTimeout(autosaveTimer);
      if (force) return flushPendingDaySaves();
      autosaveTimer = root.setTimeout(flushPendingDaySaves, 680);
      return Promise.resolve([]);
    }
    root.clearTimeout(autosaveTimer);
    autosaveTimer = root.setTimeout(function () {
      if (revision !== state.autosaveRevision) return;
      state.autosaveStatus = "saved";
      updateAutosaveIndicator();
    }, force ? 280 : 680);
    return Promise.resolve([]);
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
    if (!ensureCompetencyWritable("O salvamento")) return Promise.resolve([]);
    if (document.querySelector('.time-cell-input[aria-invalid="true"]')) {
      setAutosaveError();
      showToast("Corrija o horário inválido antes de salvar.", "error");
      return;
    }
    queueAutosave(null, true).then(function (results) {
      if (!results.some(function (result) { return result && result.ok === false; })) showToast("Alterações salvas.", "success");
    });
  }

  function cellSelector(dayId, field) {
    return '.editable-time-cell[data-day-id="' + cssEscape(dayId) + '"][data-field="' + cssEscape(field) + '"]';
  }

  function cssEscape(value) {
    return root.CSS && typeof root.CSS.escape === "function" ? root.CSS.escape(String(value)) : String(value).replace(/(["\\])/g, "\\$1");
  }

  function focusCell(dayId, field, preventScroll) {
    var cell = document.querySelector(cellSelector(dayId, field));
    if (!cell) return;
    document.querySelectorAll(".editable-time-cell.is-active").forEach(function (item) { item.classList.remove("is-active"); item.tabIndex = -1; });
    cell.classList.add("is-active");
    cell.tabIndex = 0;
    cell.focus({ preventScroll: preventScroll === true });
  }

  function beginEditing(cell, seed) {
    if (!cell || editSession) return;
    if (!ensureCompetencyWritable("A edição de horários")) return;
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
    addHistory(day, fieldLabel(session.field) + " alterada de " + (session.original || "—") + " para " + (normalized || "—") + ".", "Operador local");
    queueAutosave(day);
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
    if (!ensureCompetencyWritable("A reversão de alterações")) return;
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
      addHistory(day, "Alteração desfeita: " + fieldLabel(change.field) + " restaurada para " + (change.previous || "—") + ".", "Operador local");
      renderFocus = { dayId: day.id, field: change.field };
    } else if (change.type === "status") {
      setDayStatus(day, change.previous, { noUndo: true });
      return;
    } else if (change.type === "observation") {
      setObservation(day, change.previous, { noUndo: true, silent: true });
    }
    queueAutosave(day);
    render();
    showToast("Última alteração desfeita.", "success");
  }

  function setObservation(day, value, options) {
    if (!ensureCompetencyWritable("A edição da observação")) return;
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
    addHistory(day, value ? "Observação adicionada ou atualizada." : "Observação removida.", "Operador local");
    queueAutosave(day);
    if (!(options && options.silent)) {
      render();
      showToast("Observação salva.", "success");
    }
  }

  function openObservationDialog(day, bulk) {
    if (!ensureCompetencyWritable("A edição da observação")) return;
    var targets = bulk ? state.selectedDayIds.map(findDay).filter(Boolean) : [day];
    showDialog({
      title: bulk ? "Adicionar observação em massa" : "Observação do dia",
      description: bulk ? "A mesma observação será adicionada aos registros selecionados. As batidas originais não serão alteradas." : "A observação será salva no registro do dia sem alterar as batidas originais.",
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
    if (!ensureCompetencyWritable("A alteração da situação do dia")) return;
    var targets = bulk ? state.selectedDayIds.map(findDay).filter(Boolean) : [day];
    showDialog({
      title: bulk ? "Definir situação em massa" : "Alterar situação do dia",
      description: "A situação é independente da confirmação. Batidas originais nunca serão modificadas.",
      count: bulk ? targets.length : undefined,
      confirmLabel: "Aplicar situação",
      field: { type: "select", label: "Situação", value: day ? day.status_dia || day.status : "normal", options: Object.keys(DAY_STATUS_LABELS).map(function (key) { return { value: key, label: DAY_STATUS_LABELS[key] }; }) },
      onConfirm: function (value) {
        targets.forEach(function (target) { setDayStatus(target, value, { noUndo: true }); });
        state.selectedDayIds = bulk ? [] : state.selectedDayIds;
        render();
        showToast("Situação aplicada a " + targets.length + " registro" + (targets.length === 1 ? "" : "s") + ".", "success");
      },
    });
  }

  function confirmSelectedDays() {
    if (!ensureCompetencyWritable("A confirmação dos dias")) return;
    var targets = state.selectedDayIds.map(findDay).filter(Boolean);
    showDialog({
      title: "Marcar dias como conferidos?",
      description: "Os horários atuais serão marcados como conferidos. As batidas originais permanecerão intactas.",
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
    if (!ensureCompetencyWritable("A confirmação da interpretação")) return;
    if (!day || dayIsConfirmed(day)) return;
    (day.issues || []).forEach(function (issue) { issue.resolved = true; issue.resolution = "Interpretação mantida pelo usuário"; });
    setDayStatus(day, "normal", { noUndo: true });
    addHistory(day, "Interpretação atual mantida pelo operador.", "Operador local");
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
    if (state.apiMode === "online") {
      if (!fileId) {
        showToast("Arquivo original indisponível.", "warning");
        return;
      }
      var opened = root.open(configuredApiBase() + "/arquivos/" + encodeURIComponent(fileId) + "/download", "_blank", "noopener,noreferrer");
      if (!opened) showToast("O navegador bloqueou a nova aba.", "warning", "Permita pop-ups para abrir o arquivo original.");
      return;
    }
    var file = findFile(fileId);
    if (file && (file.extension === "jpg" || file.extension === "png" || file.sourceType === "image")) {
      navigate("ocr");
      return;
    }
    showToast("Arquivo original aberto em modo somente leitura.", "info", file ? file.name : "A visualização é simulada neste protótipo.");
  }

  function openCompetencePrintReport(employeeId, lote) {
    var competence = currentCompetency();
    if (!competence) {
      showToast("Não foi possível abrir o relatório.", "error", "Selecione uma competência e tente novamente.");
      return;
    }
    if (state.apiMode !== "online") {
      showToast("Relatório indisponível no modo demonstração.", "info", "Ligue a API para abrir a versão real para impressão.");
      return;
    }
    if (autosaveFlushPromise || Object.keys(pendingDaySaves).length) {
      showToast("Salve as alterações antes de emitir o relatório.", "warning", "Use Salvar agora e aguarde a confirmação do salvamento para imprimir os dados atualizados.");
      return;
    }
    var link = document.createElement("a");
    link.href = configuredApiBase() + (lote ? "/relatorios/espelho-ponto-lote" : employeeId ? "/relatorios/espelho-ponto" : "/relatorios/impressao") + "?competencia_id=" + encodeURIComponent(competence.id)
      + (!lote && employeeId ? "&funcionario_id=" + encodeURIComponent(employeeId) : "");
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.hidden = true;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function exportFilename(response, competence, company) {
    var disposition = response && response.headers && response.headers.get("Content-Disposition") || "";
    var encodedMatch = disposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
    var plainMatch = disposition.match(/filename\s*=\s*"?([^";]+)"?/i);
    var name = encodedMatch ? encodedMatch[1] : plainMatch ? plainMatch[1] : "";
    if (name) {
      try { name = decodeURIComponent(name.trim()); }
      catch (error) { name = name.trim(); }
    }
    if (!name) {
      var companyName = company && (company.name || company.nome) || "empresa";
      var companySlug = String(companyName).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "empresa";
      var month = Number(competence && (competence.month || competence.mes));
      var year = Number(competence && (competence.year || competence.ano));
      var period = Number.isFinite(year) && Number.isFinite(month) ? year + "-" + String(month).padStart(2, "0") : "competencia";
      name = "on_ponto_" + companySlug + "_" + period + ".xlsx";
    }
    name = String(name).replace(/[\\/:*?"<>|\r\n]+/g, "_").trim();
    return /\.xlsx$/i.test(name) ? name : name + ".xlsx";
  }

  function exportResponseError(response) {
    return response.text().then(function (textValue) {
      var payload = null;
      if (textValue) {
        try { payload = JSON.parse(textValue); }
        catch (error) { payload = { detail: textValue }; }
      }
      var requestError = new Error(apiErrorMessage(payload, "A API respondeu com erro " + response.status + "."));
      requestError.status = response.status;
      throw requestError;
    });
  }

  function exportErrorDetail(error) {
    if (error && error.name === "AbortError") return "A geração da planilha demorou mais que o esperado. Tente novamente.";
    if (error && error.status) return error.message;
    if (error && /fetch|network|rede|conex[aã]o/i.test(String(error.message || ""))) {
      return "Não foi possível conectar à API para gerar a planilha.";
    }
    return error && error.message || "A planilha não pôde ser gerada.";
  }

  function exportCompetenceExcel() {
    var competenceId = state.selectedCompetenceId;
    var competence = currentCompetency();
    var company = currentCompany();
    if (!competence) {
      showToast("Não foi possível exportar a planilha.", "error", "Selecione uma competência e tente novamente.");
      return Promise.resolve(false);
    }
    if (state.apiMode !== "online") {
      showToast("Exportação simulada no modo demonstração.", "info", "Nenhum arquivo real foi gerado.");
      return Promise.resolve(false);
    }
    if (state.exportExcelLoading) return Promise.resolve(false);

    var sequence = ++exportExcelSequence;
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timeout = root.setTimeout(function () {
      if (controller) controller.abort();
    }, 30000);
    state.exportExcelLoading = true;
    render();

    var requestOptions = {
      headers: { Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
    };
    if (controller) requestOptions.signal = controller.signal;
    return root.fetch(configuredApiBase() + "/relatorios/excel?competencia_id=" + encodeURIComponent(competenceId), requestOptions).then(function (response) {
      if (!response.ok) return exportResponseError(response);
      var filename = exportFilename(response, competence, company);
      return response.blob().then(function (blob) {
        if (!blob || !blob.size) throw new Error("A API retornou uma planilha vazia.");
        return { blob: blob, filename: filename };
      });
    }).then(function (result) {
      if (sequence !== exportExcelSequence || state.apiMode !== "online" || !idsEqual(state.selectedCompetenceId, competenceId)) return false;
      var urlApi = root.URL || root.webkitURL;
      if (!urlApi || typeof urlApi.createObjectURL !== "function") throw new Error("Este navegador não oferece suporte ao download da planilha.");
      var objectUrl = urlApi.createObjectURL(result.blob);
      var link = document.createElement("a");
      link.href = objectUrl;
      link.download = result.filename;
      link.hidden = true;
      document.body.appendChild(link);
      link.click();
      link.remove();
      root.setTimeout(function () { urlApi.revokeObjectURL(objectUrl); }, 1000);
      showToast("Download da planilha iniciado.", "success", result.filename);
      return true;
    }).catch(function (error) {
      showToast("Não foi possível exportar a planilha.", "error", exportErrorDetail(error));
      return false;
    }).finally(function () {
      root.clearTimeout(timeout);
      if (sequence !== exportExcelSequence) return;
      state.exportExcelLoading = false;
      if (state.route === "competency-exports" && idsEqual(state.selectedCompetenceId, competenceId)) render();
    });
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
    if (!ensureCompetencyWritable("A confirmação da leitura")) return;
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

  function lifecycleContextIsActive(competenceId) {
    return idsEqual(state.selectedCompetenceId, competenceId) && Boolean(currentCompetency());
  }

  function localIsoDate(value) {
    var dateValue = value || new Date();
    return dateValue.getFullYear() + "-" + String(dateValue.getMonth() + 1).padStart(2, "0") + "-" + String(dateValue.getDate()).padStart(2, "0");
  }

  function setLifecycleState(competenceId, loading, action, error) {
    if (!lifecycleContextIsActive(competenceId)) return;
    state.competenceLifecycleLoading = loading === true;
    state.competenceLifecycleAction = loading ? action || "" : "";
    state.competenceLifecycleError = error || "";
    render();
  }

  function ensureAutosaveFlushedForLifecycle() {
    return flushPendingDaySaves().then(function (results) {
      var failed = results.filter(function (result) { return result && result.ok === false; });
      if (failed.length) {
        throw new Error(failed.length + (failed.length === 1 ? " alteração não pôde" : " alterações não puderam") + " ser salva antes de continuar.");
      }
      return results;
    });
  }

  function persistCompetenceLifecycle(competenceId, action, exceptional) {
    if (state.apiMode !== "online") return Promise.resolve(false);
    if (!lifecycleContextIsActive(competenceId)) return Promise.reject(new Error("A competência selecionada mudou. Inicie a ação novamente."));
    setLifecycleState(competenceId, true, action, "");
    var path = "/competencias/" + encodeURIComponent(competenceId) + "/" + action;
    var requestOptions = action === "fechar"
      ? { method: "POST", body: { confirmar_pendencias: exceptional === true }, timeout: 15000 }
      : { method: "POST", timeout: 15000 };
    var responsePayload = null;
    return apiRequest(path, requestOptions).then(function (payload) {
      responsePayload = payload || {};
      updateCompetenceFromPayload(competenceId, responsePayload);
      state.selectedDayIds = [];
      return loadCompetenceSummary(competenceId, { force: true });
    }).then(function (summary) {
      if (lifecycleContextIsActive(competenceId)) {
        state.competenceLifecycleError = summary ? "" : "O status foi atualizado, mas a apuração não pôde ser recarregada agora.";
      }
      showToast(
        responsePayload && responsePayload.mensagem || (action === "fechar" ? "Competência fechada." : "Competência reaberta."),
        summary ? "success" : "warning",
        summary ? "A apuração desta competência foi atualizada." : "Abra o resumo novamente para tentar recarregar a apuração."
      );
      return true;
    }).catch(function (error) {
      var detail = error && error.payload && error.payload.detail;
      var conflictCode = detail && typeof detail === "object" ? detail.codigo : "";
      if (action === "fechar" && exceptional !== true && error && error.status === 409 && [
        "competencia_com_pendencias", "competencia_sem_registros", "competencia_nao_conferida",
      ].indexOf(conflictCode) !== -1) {
        var conflictPending = Number(detail.total_pendencias);
        if (!Number.isFinite(conflictPending)) conflictPending = 0;
        if (lifecycleContextIsActive(competenceId)) {
          state.competenceLifecycleError = "";
          showCloseCompetencyDialog(competenceId, conflictPending, conflictCode === "competencia_sem_registros" ? 0 : 1, true);
        }
        return false;
      }
      if (lifecycleContextIsActive(competenceId)) state.competenceLifecycleError = error && error.message || "Não foi possível atualizar a competência.";
      throw error;
    }).finally(function () {
      if (lifecycleContextIsActive(competenceId)) setLifecycleState(competenceId, false, "", state.competenceLifecycleError);
    });
  }

  function showCloseCompetencyDialog(competenceId, pendingCount, processedCount, forceExceptional) {
    var exceptional = forceExceptional === true || pendingCount > 0 || processedCount === 0;
    var pendingMessage = pendingCount > 0
      ? pendingCount + (pendingCount === 1 ? " registro ainda precisa" : " registros ainda precisam") + " de conferência."
      : processedCount === 0 ? "A competência não possui registros processados para fechamento." : "A competência ainda não está conferida.";
    showDialog({
      title: exceptional ? "Fechar competência excepcionalmente?" : "Fechar esta competência?",
      description: exceptional
        ? pendingMessage + " O fechamento excepcional preserva marcações e arquivos e bloqueia novas alterações até uma reabertura."
        : "Todos os registros processados estão conferidos. A competência continuará visível e disponível para exportação.",
      confirmLabel: pendingCount > 0
        ? "Fechar mesmo com " + pendingCount + " pendência" + (pendingCount === 1 ? "" : "s")
        : exceptional ? (processedCount === 0 ? "Fechar sem registros" : "Fechar excepcionalmente") : "Fechar competência",
      busyLabel: "Fechando...",
      destructive: true,
      fields: exceptional ? [{
        name: "confirmarExcecao",
        type: "checkbox",
        label: pendingCount > 0
          ? "Confirmo o fechamento excepcional mesmo com registros ainda não conferidos."
          : processedCount === 0 ? "Confirmo o fechamento excepcional sem registros processados." : "Confirmo o fechamento excepcional desta competência ainda não conferida.",
        value: "true",
        required: true,
        requiredMessage: "Confirme explicitamente o fechamento excepcional para continuar.",
      }] : [],
      onConfirm: function () {
        return persistCompetenceLifecycle(competenceId, "fechar", exceptional);
      },
    });
  }

  function closeCompetency() {
    var competency = currentCompetency();
    if (!competency || state.competenceLifecycleLoading) return;
    if (competencyIsClosed(competency)) return reopenCompetency();
    if (editSession && !finishEditing({ move: null })) {
      showToast("Corrija o horário inválido antes de fechar a competência.", "error");
      return;
    }
    var competenceId = competency.id;
    if (state.apiMode !== "online") {
      var demoDays = days().filter(function (day) { return idsEqual(day.competenceId || day.competencia_id, competenceId); });
      var demoPending = demoDays.filter(function (day) { return !dayIsConfirmed(day); }).length;
      showDialog({
        title: demoPending ? "Fechar competência de demonstração excepcionalmente?" : "Fechar competência de demonstração?",
        description: demoPending ? demoPending + (demoPending === 1 ? " registro ainda precisa" : " registros ainda precisam") + " de conferência. Esta alteração existirá somente nesta sessão." : "Esta alteração existirá somente nesta sessão de demonstração.",
        confirmLabel: demoPending ? "Fechar mesmo com " + demoPending + " pendência" + (demoPending === 1 ? "" : "s") : "Fechar competência",
        destructive: true,
        fields: demoPending ? [{ name: "confirmarExcecao", type: "checkbox", label: "Confirmo o fechamento excepcional no modo demonstração.", value: "true", required: true }] : [],
        onConfirm: function () {
          competency.status = "fechada";
          competency.statusLabel = "Fechada";
          competency.closedAt = localIsoDate();
          state.selectedDayIds = [];
          render();
          showToast("Competência fechada no modo demonstração.", "success", "Nenhuma alteração foi enviada à API.");
        },
      });
      return;
    }

    setLifecycleState(competenceId, true, "validar", "");
    ensureAutosaveFlushedForLifecycle().then(function () {
      if (!lifecycleContextIsActive(competenceId)) throw new Error("A competência selecionada mudou. Inicie o fechamento novamente.");
      if (competencyIsClosed()) throw new Error("A competência já está fechada.");
      return loadCompetenceSummary(competenceId, { force: true });
    }).then(function (summary) {
      if (!summary) throw new Error(state.competenceSummaryError || "Não foi possível revalidar a apuração antes do fechamento.");
      var pendingCount = summary.pendingRecords === null || summary.pendingRecords === undefined ? NaN : Number(summary.pendingRecords);
      var processedCount = summary.processedRecords === null || summary.processedRecords === undefined ? NaN : Number(summary.processedRecords);
      if (!Number.isFinite(pendingCount) || !Number.isFinite(processedCount)) {
        throw new Error("A API não informou a contagem de registros necessária para validar o fechamento.");
      }
      setLifecycleState(competenceId, false, "", "");
      showCloseCompetencyDialog(competenceId, pendingCount, processedCount);
    }).catch(function (error) {
      if (!lifecycleContextIsActive(competenceId)) return;
      setLifecycleState(competenceId, false, "", error && error.message || "Não foi possível validar o fechamento.");
      showToast("Não foi possível preparar o fechamento.", "error", error && error.message || "Tente novamente.");
    });
  }

  function reopenCompetency() {
    var competency = currentCompetency();
    if (!competency || state.competenceLifecycleLoading) return;
    if (!competencyIsClosed(competency)) {
      showToast("A competência não está fechada.", "info");
      return;
    }
    var competenceId = competency.id;
    showDialog({
      title: state.apiMode === "online" ? "Reabrir esta competência?" : "Reabrir competência de demonstração?",
      description: "Importações, edições e confirmações voltarão a ficar disponíveis. Marcações e arquivos serão preservados.",
      confirmLabel: "Reabrir competência",
      busyLabel: "Reabrindo...",
      fields: [],
      onConfirm: function () {
        if (state.apiMode !== "online") {
          var hasDays = days().some(function (day) { return idsEqual(day.competenceId || day.competencia_id, competenceId); });
          competency.status = hasDays ? "em_conferencia" : "aberta";
          competency.statusLabel = hasDays ? "Em conferência" : "Aberta";
          competency.closedAt = null;
          render();
          showToast("Competência reaberta no modo demonstração.", "success", "Nenhuma alteração foi enviada à API.");
          return;
        }
        return ensureAutosaveFlushedForLifecycle().then(function () {
          return persistCompetenceLifecycle(competenceId, "reabrir", false);
        });
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
        autosaveTimer = null;
        pendingDaySaves = Object.create(null);
        loadedCompetenceDays = Object.create(null);
        loadedCompetenceFiles = Object.create(null);
        loadedCompetenceSummaries = Object.create(null);
        competenceSummarySequences = Object.create(null);
        loadedCompanyScales = Object.create(null);
        companyScaleLoadSequences = Object.create(null);
        importAnalysisSequence += 1;
        data = Mocks.reset();
        var collapsed = state.sidebarCollapsed;
        state = createInitialState();
        state.sidebarCollapsed = collapsed;
        state.apiMode = "offline";
        state.apiError = "API indisponível; usando dados de demonstração.";
        navigate("companies");
        showToast("Dados simulados restaurados.", "success");
      },
    });
  }

  function nextLocalId(list) {
    return list.reduce(function (highest, item) {
      return Math.max(highest, Number(item.id) || 0);
    }, 0) + 1;
  }

  function upsertEntity(list, entity, sorter) {
    var index = list.findIndex(function (item) { return idsEqual(item.id, entity.id); });
    if (index === -1) list.push(entity);
    else list.splice(index, 1, entity);
    if (typeof sorter === "function") list.sort(sorter);
    return entity;
  }

  function compareEntityNames(left, right) {
    return String(left.name || left.nome || "").localeCompare(String(right.name || right.nome || ""), "pt-BR", { sensitivity: "base" });
  }

  function compareCompetences(left, right) {
    return (Number(right.year || right.ano) * 100 + Number(right.month || right.mes)) -
      (Number(left.year || left.ano) * 100 + Number(left.month || left.mes));
  }

  function invalidateCompanyCompetenceData(companyId) {
    competencies().forEach(function (competence) {
      if (!idsEqual(competence.companyId || competence.empresa_id, companyId)) return;
      var key = String(competence.id);
      delete loadedCompetenceDays[key];
      delete loadedCompetenceSummaries[key];
      if (data.competenceSummaries) delete data.competenceSummaries[key];
    });
  }

  function dialogTimeMinutes(value) {
    var match = String(value || "").match(/^(\d{2}):(\d{2})$/);
    if (!match) return null;
    return Number(match[1]) * 60 + Number(match[2]);
  }

  function nullableDialogNumber(value) {
    return value === "" || value === null || value === undefined ? null : Number(value);
  }

  function openScaleDialog(id, options) {
    var company = currentCompany();
    if (!company) {
      showToast("Selecione uma empresa antes de cadastrar uma escala.", "warning");
      navigate("companies");
      return;
    }
    var online = state.apiMode === "online";
    if (online && !(options && options.scalesLoaded) && !loadedCompanyScales[String(company.id)]) {
      return loadScalesForCompany(company.id).then(function () {
        return openScaleDialog(id, { scalesLoaded: true });
      }).catch(function (error) {
        showToast("Não foi possível abrir o cadastro de escala.", "error", error && error.message);
      });
    }
    var hasId = id !== undefined && id !== null && id !== "";
    var entity = hasId ? companyScales(company.id).find(function (item) { return idsEqual(item.id, id); }) : null;
    if (hasId && !entity) {
      showToast("Escala não encontrada nesta empresa.", "error");
      return;
    }
    var mode = entity ? entity.modo_apuracao || entity.mode : "carga_horaria";
    var isWorkload = function (values) { return values.modo_apuracao === "carga_horaria"; };
    var isFixed = function (values) { return values.modo_apuracao === "horario_fixo"; };
    showDialog({
      title: entity ? "Editar escala" : "Nova escala",
      description: "Defina a jornada e as regras desta escala. Nenhum funcionário será vinculado automaticamente.",
      confirmLabel: entity ? "Salvar alterações" : "Adicionar escala",
      busyLabel: "Salvando...",
      wide: true,
      fieldLayout: "grid",
      fields: [
        { name: "nome", type: "text", label: "Nome da escala", value: entity ? entity.name || entity.nome : "", required: true, maxlength: 120, fullWidth: true },
        { name: "modo_apuracao", type: "select", label: "Modo de apuração", value: mode, required: true, fullWidth: true, options: [{ value: "carga_horaria", label: "Carga horária" }, { value: "horario_fixo", label: "Horário fixo" }] },
        { name: "jornada_seg_sex_horas", type: "number", label: "Jornada de segunda a sexta (horas)", value: entity && entity.jornada_seg_sex_horas !== null && entity.jornada_seg_sex_horas !== undefined ? entity.jornada_seg_sex_horas : "8", required: true, min: 0, max: 24, step: 0.01, visibleWhen: isWorkload },
        { name: "jornada_sabado_horas", type: "number", label: "Jornada de sábado (horas)", value: entity && entity.jornada_sabado_horas !== null && entity.jornada_sabado_horas !== undefined ? entity.jornada_sabado_horas : "", min: 0, max: 24, step: 0.01, visibleWhen: isWorkload },
        { name: "horario_entrada_prevista", type: "time", label: "Entrada prevista", value: entity ? normalizedTime(entity.horario_entrada_prevista) : "", required: true, visibleWhen: isFixed },
        { name: "horario_saida_prevista", type: "time", label: "Saída prevista", value: entity ? normalizedTime(entity.horario_saida_prevista) : "", required: true, visibleWhen: isFixed },
        { name: "horario_saida_almoco_prevista", type: "time", label: "Saída para almoço", value: entity ? normalizedTime(entity.horario_saida_almoco_prevista) : "", visibleWhen: isFixed },
        { name: "horario_retorno_almoco_prevista", type: "time", label: "Retorno do almoço", value: entity ? normalizedTime(entity.horario_retorno_almoco_prevista) : "", visibleWhen: isFixed },
        { name: "regime_sabado", type: "select", label: "Regime de sábado", value: entity ? entity.regime_sabado : "nao_trabalha", required: true, options: [{ value: "trabalha", label: "Trabalha" }, { value: "compensado", label: "Compensado" }, { value: "nao_trabalha", label: "Não trabalha" }] },
        { name: "regime_domingo", type: "select", label: "Regime de domingo", value: entity ? entity.regime_domingo : "nao_trabalha", required: true, options: [{ value: "trabalha", label: "Trabalha" }, { value: "nao_trabalha", label: "Não trabalha" }] },
        { name: "tolerancia_atraso_minutos", type: "number", label: "Tolerância de atraso (min)", value: entity ? entity.tolerancia_atraso_minutos : 0, required: true, min: 0, max: 1440, step: 1 },
        { name: "tolerancia_extra_minutos", type: "number", label: "Tolerância de extra (min)", value: entity ? entity.tolerancia_extra_minutos : 0, required: true, min: 0, max: 1440, step: 1 },
        { name: "tolerancia_intervalo_minutos", type: "number", label: "Tolerância de intervalo (min)", value: entity && entity.tolerancia_intervalo_minutos != null ? entity.tolerancia_intervalo_minutos : "", help: "Deixe em branco para usar a mesma tolerância de atraso da escala.", min: 0, max: 1440, step: 1 },
        { name: "usa_banco_horas", type: "select", label: "Banco de horas", value: entity && entity.usa_banco_horas ? "true" : "false", options: [{value:"false",label:"Desabilitado"},{value:"true",label:"Habilitado"}], help: "Configure primeiro o prazo de compensação no cadastro da empresa." },
        { name: "ativa", type: "select", label: "Situação", value: entity && (entity.active === false || entity.ativa === false) ? "false" : "true", required: true, options: [{ value: "true", label: "Ativa" }, { value: "false", label: "Inativa" }] },
      ],
      validate: function (values) {
        if (values.modo_apuracao === "carga_horaria") {
          if (values.regime_sabado === "trabalha" && values.jornada_sabado_horas === "") {
            return { message: "Informe a jornada de sábado quando esse dia é trabalhado.", field: "jornada_sabado_horas" };
          }
          return null;
        }
        var hasLunchOut = Boolean(values.horario_saida_almoco_prevista);
        var hasLunchReturn = Boolean(values.horario_retorno_almoco_prevista);
        if (hasLunchOut !== hasLunchReturn) {
          return { message: "Informe os dois horários de almoço ou deixe ambos vazios.", field: hasLunchOut ? "horario_retorno_almoco_prevista" : "horario_saida_almoco_prevista" };
        }
        var orderedFields = ["horario_entrada_prevista"];
        if (hasLunchOut) orderedFields.push("horario_saida_almoco_prevista", "horario_retorno_almoco_prevista");
        orderedFields.push("horario_saida_prevista");
        for (var index = 0; index < orderedFields.length - 1; index += 1) {
          if (dialogTimeMinutes(values[orderedFields[index]]) >= dialogTimeMinutes(values[orderedFields[index + 1]])) {
            return { message: "A ordem deve ser entrada, saída para almoço, retorno do almoço e saída.", field: orderedFields[index + 1] };
          }
        }
        return null;
      },
      onConfirm: function (values) {
        var workload = values.modo_apuracao === "carga_horaria";
        var payload = {
          empresa_id: company.id,
          nome: String(values.nome || "").trim(),
          modo_apuracao: values.modo_apuracao,
          jornada_seg_sex_horas: workload ? nullableDialogNumber(values.jornada_seg_sex_horas) : null,
          jornada_sabado_horas: workload ? nullableDialogNumber(values.jornada_sabado_horas) : null,
          horario_entrada_prevista: workload ? null : values.horario_entrada_prevista || null,
          horario_saida_almoco_prevista: workload ? null : values.horario_saida_almoco_prevista || null,
          horario_retorno_almoco_prevista: workload ? null : values.horario_retorno_almoco_prevista || null,
          horario_saida_prevista: workload ? null : values.horario_saida_prevista || null,
          regime_sabado: values.regime_sabado,
          regime_domingo: values.regime_domingo,
          tolerancia_atraso_minutos: Number(values.tolerancia_atraso_minutos),
          tolerancia_extra_minutos: Number(values.tolerancia_extra_minutos),
          tolerancia_intervalo_minutos: nullableDialogNumber(values.tolerancia_intervalo_minutos),
          usa_banco_horas: values.usa_banco_horas === "true",
          ativa: values.ativa === "true",
        };
        if (online) {
          var endpoint = "/escalas" + (entity ? "/" + encodeURIComponent(entity.id) : "");
          return apiRequest(endpoint, { method: entity ? "PUT" : "POST", body: payload }).then(function (response) {
            upsertEntity(scales(), normalizeScale(response), compareEntityNames);
            loadedCompanyScales[String(company.id)] = true;
            invalidateCompanyCompetenceData(company.id);
            render();
            showToast(entity ? "Escala atualizada." : "Escala cadastrada.", "success");
          });
        }
        var saved = normalizeScale(Object.assign({}, entity || {}, payload, { id: entity ? entity.id : nextLocalId(scales()) }));
        if (!data.scales) {
          data.scales = scales();
          data.escalas = data.scales;
        }
        upsertEntity(scales(), saved, compareEntityNames);
        invalidateCompanyCompetenceData(company.id);
        render();
        showToast("Escala salva no modo demonstração.", "success");
      },
    });
  }

  function deactivateScale(id) {
    var company = currentCompany();
    var scale = company && companyScales(company.id).find(function (item) { return idsEqual(item.id, id); });
    if (!company || !scale) {
      showToast("Escala não encontrada nesta empresa.", "error");
      return;
    }
    var linkedCount = employees().filter(function (employee) { return idsEqual(employee.escala_id || employee.scaleId, scale.id); }).length;
    showDialog({
      title: "Desativar escala?",
      description: linkedCount
        ? linkedCount + " funcionário" + (linkedCount === 1 ? " permanece" : "s permanecem") + " vinculado" + (linkedCount === 1 ? "" : "s") + ". A escala deixará de aparecer para novos vínculos."
        : "A escala não possui funcionários vinculados e poderá ser removida definitivamente.",
      confirmLabel: "Desativar escala",
      destructive: true,
      busyLabel: "Desativando...",
      onConfirm: function () {
        if (state.apiMode === "online") {
          return apiRequest("/escalas/" + encodeURIComponent(scale.id), { method: "DELETE" }).then(function () {
            return loadScalesForCompany(company.id, { force: true });
          }).then(function () {
            invalidateCompanyCompetenceData(company.id);
            render();
            showToast(linkedCount ? "Escala desativada." : "Escala removida.", "success");
          });
        }
        var list = scales();
        var index = list.findIndex(function (item) { return idsEqual(item.id, scale.id); });
        if (linkedCount) {
          scale.active = false;
          scale.ativa = false;
        } else if (index !== -1) list.splice(index, 1);
        invalidateCompanyCompetenceData(company.id);
        render();
        showToast(linkedCount ? "Escala desativada no modo demonstração." : "Escala removida do modo demonstração.", "success");
      },
    });
  }

  function openSimpleEntityDialog(kind, id, options) {
    var isCompany = kind === "company";
    var list = isCompany ? companies() : employees();
    var hasId = id !== undefined && id !== null && id !== "";
    var entity = hasId ? list.find(function (item) { return idsEqual(item.id, id); }) : null;
    var noun = isCompany ? "empresa" : "funcionário";
    var company = isCompany ? null : entity
      ? companies().find(function (item) { return idsEqual(item.id, entity.companyId || entity.empresa_id); })
      : currentCompany();
    if (!isCompany && !company) {
      showToast("Selecione uma empresa antes de cadastrar um funcionário.", "warning");
      navigate("companies");
      return;
    }
    var online = state.apiMode === "online";
    if (!isCompany && online && !(options && options.scalesLoaded) && !loadedCompanyScales[String(company.id)]) {
      return loadScalesForCompany(company.id).then(function () {
        return openSimpleEntityDialog(kind, id, { scalesLoaded: true });
      }).catch(function (error) {
        showToast("Não foi possível abrir o cadastro do funcionário.", "error", error && error.message || "Falha ao carregar as escalas da empresa.");
      });
    }
    var currentScaleId = entity ? firstValue(entity.escala_id, entity.scaleId) : null;
    var availableScales = isCompany ? [] : companyScales(company.id).filter(function (scale) {
      return scale.active !== false && scale.ativa !== false || idsEqual(scale.id, currentScaleId);
    });
    var scaleOptions = [{ value: "", label: "Sem escala — pendência de cadastro" }].concat(availableScales.map(function (scale) {
      var inactive = scale.active === false || scale.ativa === false;
      return { value: String(scale.id), label: (scale.name || scale.nome) + (inactive ? " (inativa)" : "") };
    }));
    var fields = isCompany ? [
      { name: "nome", type: "text", label: "Nome da empresa", value: entity ? entity.name || entity.nome : "", required: true, maxlength: 180, autocomplete: "organization", fullWidth: true },
      { name: "cnpj", type: "text", label: "CNPJ", value: entity ? entity.cnpj || "" : "", maxlength: 32, autocomplete: "off" },
      { name: "prazo_compensacao_banco_horas_dias", type: "number", label: "Prazo do banco de horas (dias)", value: entity && entity.prazo_compensacao_banco_horas_dias || "", min: 1, step: 1, help: "Prazo definido para a empresa. Necessário para habilitar banco em uma escala." },
      { name: "feriado_entra_banco", type: "select", label: "Horas de feriado entram no banco?", value: entity && entity.feriado_entra_banco ? "true" : "false", options: [{value:"false",label:"Não"},{value:"true",label:"Sim"}] },
      { name: "cidade", type: "text", label: "Cidade", value: entity ? entity.city || entity.cidade || "" : "", maxlength: 120, autocomplete: "address-level2" },
      { name: "uf", type: "select", label: "UF", value: entity ? entity.uf || "" : "", options: [{ value: "", label: "Não informada" }].concat(UF_OPTIONS.map(function (uf) { return { value: uf, label: uf }; })) },
      { name: "ativa", type: "select", label: "Situação", value: entity && (entity.active === false || entity.ativa === false) ? "false" : "true", options: [{ value: "true", label: "Ativa" }, { value: "false", label: "Inativa" }] },
    ] : [
      { name: "nome", type: "text", label: "Nome do funcionário", value: entity ? entity.name || entity.nome : "", required: true, maxlength: 180, autocomplete: "name" },
      { name: "codigo", type: "text", label: "Código", value: entity ? entity.code || entity.codigo || "" : "", required: true, maxlength: 50, autocomplete: "off" },
      { name: "cargo", type: "text", label: "Cargo", value: entity ? entity.role || entity.cargo || "" : "", maxlength: 120, autocomplete: "organization-title" },
      { name: "data_admissao", type: "date", label: "Data de admissão", value: entity && entity.data_admissao || "", help: "Opcional. Dias anteriores ficam fora da apuração; batidas existentes continuam disponíveis para conferência." },
      { name: "data_demissao", type: "date", label: "Data de demissão", value: entity && entity.data_demissao || "", help: "Opcional. O dia da demissão ainda pertence ao vínculo; dias posteriores ficam fora da apuração." },
      { name: "ativo", type: "select", label: "Situação", value: entity && (entity.active === false || entity.ativo === false) ? "false" : "true", options: [{ value: "true", label: "Ativo" }, { value: "false", label: "Inativo" }] },
      { name: "escala_id", type: "select", label: "Escala", value: currentScaleId === null ? "" : String(currentScaleId), options: scaleOptions, fullWidth: true, help: availableScales.length ? "A escala define jornada, horários, fins de semana e tolerâncias." : "Nenhuma escala ativa cadastrada. O funcionário ficará com uma pendência visível." },
    ];
    showDialog({
      title: (entity ? "Editar " : "Novo ") + noun,
      description: online
        ? (entity ? "Atualize os dados e salve as alterações na API." : "Preencha os dados para criar o cadastro na API.")
        : "Modo demonstração: o cadastro ficará somente nesta sessão do navegador.",
      confirmLabel: entity ? "Salvar alterações" : "Adicionar " + noun,
      busyLabel: "Salvando...",
      wide: true,
      fieldLayout: "grid",
      fields: fields,
      validate: function (values) {
        if (isCompany) return null;
        if (values.data_admissao && values.data_demissao && values.data_demissao < values.data_admissao) return {message:"A data de demissão não pode ser anterior à data de admissão.",field:"data_demissao"};
        var code = String(values.codigo || "").trim();
        var duplicate = employees().some(function (employee) {
          return (!entity || !idsEqual(employee.id, entity.id)) &&
            idsEqual(employee.companyId || employee.empresa_id, company.id) &&
            String(employee.code || employee.codigo || "").trim() === code;
        });
        if (duplicate) return { message: "Código já usado nesta empresa.", field: "codigo" };
        var selectedScaleId = asId(values.escala_id);
        if (selectedScaleId !== null && !companyScales(company.id).some(function (scale) { return idsEqual(scale.id, selectedScaleId); })) {
          return { message: "Selecione uma escala desta empresa.", field: "escala_id" };
        }
        return null;
      },
      onConfirm: function (values) {
        var payload = isCompany ? {
          nome: String(values.nome || "").trim(),
          cnpj: String(values.cnpj || "").trim() || null,
          prazo_compensacao_banco_horas_dias: nullableDialogNumber(values.prazo_compensacao_banco_horas_dias),
          feriado_entra_banco: values.feriado_entra_banco === "true",
          cidade: String(values.cidade || "").trim() || null,
          uf: String(values.uf || "").trim().toUpperCase() || null,
          ativa: values.ativa === "true",
        } : {
          empresa_id: company.id,
          nome: String(values.nome || "").trim(),
          codigo: String(values.codigo || "").trim(),
          cargo: String(values.cargo || "").trim() || null,
          data_admissao: values.data_admissao || null,
          data_demissao: values.data_demissao || null,
          ativo: values.ativo === "true",
          escala_id: asId(values.escala_id),
        };
        if (online) {
          var endpoint = isCompany ? "/empresas" : "/funcionarios";
          if (entity) endpoint += "/" + encodeURIComponent(entity.id);
          return apiRequest(endpoint, { method: entity ? "PATCH" : "POST", body: payload }).then(function (response) {
            var saved = isCompany ? normalizeCompany(response) : normalizeEmployee(response);
            upsertEntity(list, saved, compareEntityNames);
            if (!isCompany) invalidateCompanyCompetenceData(company.id);
            render();
            showToast(entity ? "Alteração salva." : (isCompany ? "Empresa cadastrada." : "Funcionário cadastrado."), "success");
          });
        }

        var localId = entity ? entity.id : nextLocalId(list);
        var local = isCompany
          ? normalizeCompany(Object.assign({}, entity || {}, payload, { id: localId }))
          : normalizeEmployee(Object.assign({}, entity || {}, payload, { id: localId }));
        upsertEntity(list, local, compareEntityNames);
        if (!isCompany) invalidateCompanyCompetenceData(company.id);
        render();
        showToast((isCompany ? "Empresa" : "Funcionário") + " salvo no modo demonstração.", "success");
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
    var online = state.apiMode === "online";
    var now = new Date();
    var monthOptions = [];
    for (var month = 1; month <= 12; month += 1) {
      monthOptions.push({ value: String(month), label: String(month).padStart(2, "0") });
    }
    showDialog({
      title: "Nova competência",
      description: online ? "Crie a competência mensal para esta empresa." : "Modo demonstração: a competência ficará somente nesta sessão do navegador.",
      confirmLabel: "Criar competência",
      busyLabel: "Criando...",
      fields: [
        { name: "mes", type: "select", label: "Mês", value: String(now.getMonth() + 1), required: true, options: monthOptions },
        { name: "ano", type: "number", label: "Ano", value: String(now.getFullYear()), required: true, min: 2000, max: 2100, step: 1 },
      ],
      validate: function (values) {
        var monthValue = Number(values.mes);
        var yearValue = Number(values.ano);
        var duplicate = competencies().some(function (item) {
          return idsEqual(item.companyId || item.empresa_id, company.id) && Number(item.month || item.mes) === monthValue && Number(item.year || item.ano) === yearValue;
        });
        return duplicate ? { message: "Competência já cadastrada para esta empresa.", field: "mes" } : null;
      },
      onConfirm: function (values) {
        var payload = { empresa_id: company.id, mes: Number(values.mes), ano: Number(values.ano) };
        if (online) {
          return apiRequest("/competencias", { method: "POST", body: payload }).then(function (response) {
            var saved = normalizeCompetence(response, employees());
            upsertEntity(competencies(), saved, compareCompetences);
            showToast("Competência criada.", "success");
            navigate({ view: "competency-summary", companyId: company.id, competenceId: saved.id });
          });
        }

        var local = normalizeCompetence(Object.assign({}, payload, { status: "aberta", id: nextLocalId(competencies()), updated_at: new Date().toISOString() }), employees());
        upsertEntity(competencies(), local, compareCompetences);
        showToast("Competência criada no modo demonstração.", "success");
        navigate({ view: "competency-summary", companyId: company.id, competenceId: local.id });
      },
    });
  }

  function handleClick(event) {
    var element = event.target.closest("[data-action]");
    if (!element) return;
    var action = element.dataset.action;

    if (root.OnPontoOcorrencias.action(action, element, event)) return;
    if (root.OnPontoBancoHoras && root.OnPontoBancoHoras.action(action, element, event)) return;
    if (root.OnPontoCalendario.action(action, element, event)) return;
    // Form actions belong to submit events; preserve native label activation.
    if (element.tagName === "FORM") return;
    if (action === "open-file-picker") {
      if (element.tagName === "LABEL") return;
      event.preventDefault();
      var fileInput = document.getElementById(element.getAttribute("aria-controls"));
      if (!element.disabled && fileInput && !fileInput.disabled && !competencyIsClosed()) fileInput.click();
      return;
    }
    if (action === "search-companies") return;
    if (element.matches('input[type="checkbox"], input[type="radio"], input[type="file"], select, input[type="range"]')) return;
    if (action === "analyze-import" && element.type === "submit") return;
    if (action !== "edit-time") event.preventDefault();
    if (competencyIsClosed() && CLOSED_COMPETENCE_ACTIONS[action]) {
      event.preventDefault();
      closedCompetencyWarning();
      return;
    }

    if (action === "navigate") return navigate(element.dataset.route || element.dataset.view);
    if (action === "retry-competence-summary") {
      var retryCompetenceId = state.selectedCompetenceId;
      if (!retryCompetenceId || state.apiMode !== "online") return;
      var retry = loadCompetenceSummary(retryCompetenceId, { force: true });
      render();
      return retry.then(function () {
        if (idsEqual(state.selectedCompetenceId, retryCompetenceId)) render();
      });
    }
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
      return navigate("import-preview");
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
    if (action === "set-day-certificate") return addReviewCertificate(findDay(element.dataset.dayId || state.selectedDayId));
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
    if (action === "request-reopen-competence") return reopenCompetency();
    if (action === "export-competence") return navigate("competency-exports");
    if (action === "preview-summary-report") return navigate("competency-summary");
    if (action === "export-excel") return exportCompetenceExcel();
    if (action === "open-espelhos-lote") return openCompetencePrintReport(null, true);
    if (action === "open-print-report") return openCompetencePrintReport();
    if (action === "open-employee-timesheet") return openCompetencePrintReport(element.getAttribute("data-employee-id"));
    if (action === "new-company") return openSimpleEntityDialog("company");
    if (action === "edit-company") return openSimpleEntityDialog("company", element.dataset.companyId || element.dataset.id || state.selectedCompanyId);
    if (action === "new-employee") return openSimpleEntityDialog("employee");
    if (action === "edit-employee") return openSimpleEntityDialog("employee", element.dataset.employeeId || element.dataset.id);
    if (action === "new-scale") return openScaleDialog();
    if (action === "edit-scale") return openScaleDialog(element.dataset.scaleId || element.dataset.id);
    if (action === "deactivate-scale") return deactivateScale(element.dataset.scaleId || element.dataset.id);
    if (action === "new-competence") return newCompetency();
    if (action === "reset-demo-data") return resetDemo();
  }

  function handleChange(event) {
    var element = event.target.closest("[data-action]");
    if (!element) return;
    var action = element.dataset.action;
    if (root.OnPontoOcorrencias.change(action, element)) return;
    if (root.OnPontoBancoHoras && root.OnPontoBancoHoras.change(action, element)) return;
    if (root.OnPontoCalendario.change(action, element)) return;
    if (competencyIsClosed() && [
      "select-import-file", "select-import-type", "toggle-import-row", "toggle-all-import-rows",
      "toggle-day-selection", "toggle-all-days", "edit-ocr-time", "edit-ocr-observation",
    ].indexOf(action) !== -1) {
      event.preventDefault();
      closedCompetencyWarning();
      render();
      return;
    }
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
    if (action === "toggle-import-row") return toggleImportRowSelection(asId(element.dataset.previewRowId), element.checked);
    if (action === "toggle-all-import-rows") return toggleAllImportRows(element.checked);
    if (action === "toggle-day-selection") return toggleDaySelection(element.dataset.dayId, element.checked);
    if (action === "toggle-all-days") return toggleAllDays(element.checked);
    if (action === "select-report-company") return openCompany(asId(element.value), "company-reports");
    if (action === "select-settings-company") return openCompany(asId(element.value), "company-settings");
    if (action === "select-report-competence") return openCompetencyArea(asId(element.value), "competency-exports");
    if (action === "toggle-autosave") {
      state.settings.autosave = element.checked;
      if (element.checked && Object.keys(pendingDaySaves).length) queueAutosave(null, true);
      return showToast(element.checked ? "Autosave ativado." : "Autosave desativado.", "info");
    }
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
    if (competencyIsClosed() && state.route === "review") {
      var closedShortcut = (event.ctrlKey || event.metaKey) && ["s", "z"].indexOf(event.key.toLowerCase()) !== -1;
      var closedCell = target.classList && target.classList.contains("time-cell-input") || target.closest && target.closest(".editable-time-cell");
      var closedSingleKey = state.settings.singleKeyShortcuts && !isTextEditingTarget(target) && !event.ctrlKey && !event.altKey && !event.metaKey && ["n", "f", "a", "c"].indexOf(event.key.toLowerCase()) !== -1;
      if (closedShortcut || closedCell || closedSingleKey) {
        event.preventDefault();
        closedCompetencyWarning();
        return;
      }
    }
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
    if (competencyIsClosed()) {
      closedCompetencyWarning("A colagem de horários");
      return;
    }
    beginEditing(cell, event.clipboardData.getData("text/plain").trim());
    finishEditing({ move: "down" });
  }

  function bindDragAndDrop() {
    document.addEventListener("dragover", function (event) {
      var dropzone = event.target.closest && event.target.closest(".import-dropzone");
      if (!dropzone) return;
      event.preventDefault();
      if (competencyIsClosed()) return;
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
      if (competencyIsClosed()) {
        closedCompetencyWarning("O envio de arquivos");
        return;
      }
      var file = event.dataTransfer && event.dataTransfer.files[0];
      if (file) setSelectedFile(file);
    });
  }

  function guardUnsavedPageExit(event) {
    if (state.apiMode !== "online") return;
    if (editSession || autosaveFlushPromise || Object.keys(pendingDaySaves).length) {
      event.preventDefault();
      event.returnValue = "";
    }
  }

  function flushAutosaveBeforePageExit() {
    if (state.apiMode !== "online" || !state.settings.autosave) return;
    if (editSession && !finishEditing({ move: null })) return;
    if (Object.keys(pendingDaySaves).length) flushPendingDaySaves();
  }

  function syncRouteFromLocation(options) {
    if (state.apiMode === "loading") return Promise.resolve();
    if (editSession && !finishEditing({ move: null })) {
      root.history.replaceState(null, "", routeHash({
        view: state.route,
        companyId: state.selectedCompanyId,
        competenceId: state.selectedCompetenceId,
      }));
      return Promise.resolve();
    }
    var sequence = ++routeLoadSequence;
    var route = validateRoute(parseHashRoute(root.location.hash));
    var canonicalHash = routeHash(route);
    if (root.location.hash !== canonicalHash) root.history.replaceState(null, "", canonicalHash);
    applyRouteContext(route);
    if (route.view === "calendar") return root.OnPontoCalendario.load();
    if (route.view === "company-ocorrencias") return root.OnPontoOcorrencias.load();
    if (route.view === "company-banco-horas") return root.OnPontoBancoHoras.load();
    if (state.apiMode === "online" && route.companyId && ["company-employees", "company-scales", "company-settings"].indexOf(route.view) !== -1 && !loadedCompanyScales[String(route.companyId)]) {
      var scalesLoading = loadScalesForCompany(route.companyId);
      render(options);
      return scalesLoading.then(function () {
        if (sequence !== routeLoadSequence) return;
        applyRouteContext(route);
        render(options);
      }).catch(function (error) {
        if (sequence !== routeLoadSequence) return;
        render(options);
        showToast("Não foi possível carregar as escalas da empresa.", "error", error && error.message);
      });
    }
    if (state.apiMode !== "online" || !route.competenceId) {
      render(options);
      return Promise.resolve();
    }
    var summaryRequested = route.view === "competency-summary";
    var loading = loadCompetenceData(route.competenceId, { summaryForce: summaryRequested });
    render(options);
    return loading.then(function () {
      if (sequence !== routeLoadSequence) return;
      applyRouteContext(route);
      render(options);
    }).catch(function (error) {
      if (sequence !== routeLoadSequence) return;
      state.reviewLoading = false;
      render(options);
      showToast("Não foi possível carregar os dados desta competência.", "error", error && error.message);
    });
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
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") flushAutosaveBeforePageExit();
    });
    root.addEventListener("pagehide", flushAutosaveBeforePageExit);
    root.addEventListener("beforeunload", guardUnsavedPageExit);
    byId("sidebarExpandButton").addEventListener("click", toggleSidebar);
    root.addEventListener("hashchange", function () {
      syncRouteFromLocation({ focusMain: true });
    });
    bindDragAndDrop();
  }

  function init() {
    if (root.OnPontoBancoHoras) root.OnPontoBancoHoras.configure({state:function(){return state;},data:function(){return data;},api:apiRequest,
      render:render,dialog:showDialog,invalidate:function(){
        loadedCompetenceSummaries = Object.create(null); data.competenceSummaries = {};
      }});
    root.OnPontoCalendario.configure({state:function(){return state;},data:function(){return data;},api:apiRequest,
      render:render,dialog:showDialog,toast:showToast,invalidate:function(){
        loadedCompetenceDays = Object.create(null); loadedCompetenceSummaries = Object.create(null); data.competenceSummaries = {};
      }});
    root.OnPontoOcorrencias.configure({state:function(){return state;},data:function(){return data;},api:apiRequest,apiBase:configuredApiBase,
      render:render,navigate:navigate,dialog:showDialog,toast:showToast,invalidate:function(){
        loadedCompetenceDays = Object.create(null); loadedCompetenceSummaries = Object.create(null); data.competenceSummaries = {};
      }});
    bindEvents();
    root.OnPontoApp = {
      getState: function () { return state; },
      getData: function () { return data; },
      navigate: navigate,
      render: render,
      routeHash: routeHash,
      reset: resetDemo,
      reloadAttendance: loadAttendanceForCompetence,
      apiBase: configuredApiBase,
    };
    bootstrapApiData().then(function (online) {
      return syncRouteFromLocation().then(function () {
        if (!online) showToast("API indisponível: usando dados de demonstração.", "warning", state.apiError + " Configure onponto.apiBase para alterar o endereço da API.");
      });
    }).catch(function (error) {
      state.apiMode = "offline";
      state.apiError = error && error.message || "API indisponível.";
      syncRouteFromLocation();
    });
  }

  init();
})(window);
