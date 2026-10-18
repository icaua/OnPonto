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
    falta: "Falta injustificada",
    falta_justificada: "Falta justificada",
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
  var reviewDaySequences = Object.create(null);
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
  var deferredRender = false;
  var contextSwitchPending = false;
  var tentativaApiTimer = null;
  var conexaoApiPendente = null;

  function apiFeature() {
    return globalThis.OnPontoApi.create({
      configuredApiBase:typeof configuredApiBase === "undefined" ? undefined : configuredApiBase,
      data:typeof data === "undefined" ? undefined : data,
      root:typeof root === "undefined" ? undefined : root
    });
  }

  function navigationFeature() {
    return globalThis.OnPontoNavigation.create({
      COMPANY_VIEWS:typeof COMPANY_VIEWS === "undefined" ? undefined : COMPANY_VIEWS,
      COMPETENCY_VIEWS:typeof COMPETENCY_VIEWS === "undefined" ? undefined : COMPETENCY_VIEWS,
      ROUTE_ALIASES:typeof ROUTE_ALIASES === "undefined" ? undefined : ROUTE_ALIASES,
      VIEWS:typeof VIEWS === "undefined" ? undefined : VIEWS,
      asId:typeof asId === "undefined" ? undefined : asId,
      companies:typeof companies === "undefined" ? undefined : companies,
      competencies:typeof competencies === "undefined" ? undefined : competencies,
      employees:typeof employees === "undefined" ? undefined : employees,
      files:typeof files === "undefined" ? undefined : files,
      idsEqual:typeof idsEqual === "undefined" ? undefined : idsEqual,
      scales:typeof scales === "undefined" ? undefined : scales,
      state:typeof state === "undefined" ? undefined : state
    });
  }

  function importacaoFeature() {
    return globalThis.OnPontoImportacao.create({
      Utils:typeof Utils === "undefined" ? undefined : Utils,
      currentCompany:typeof currentCompany === "undefined" ? undefined : currentCompany,
      currentCompetency:typeof currentCompetency === "undefined" ? undefined : currentCompetency,
      data:typeof data === "undefined" ? undefined : data,
      firstValue:typeof firstValue === "undefined" ? undefined : firstValue,
      normalizeIssues:typeof normalizeIssues === "undefined" ? undefined : normalizeIssues,
      normalizeOriginalPunches:typeof normalizeOriginalPunches === "undefined" ? undefined : normalizeOriginalPunches,
      normalizedTime:typeof normalizedTime === "undefined" ? undefined : normalizedTime,
      state:typeof state === "undefined" ? undefined : state,
      statusFromBackend:typeof statusFromBackend === "undefined" ? undefined : statusFromBackend,
      statusLabel:typeof statusLabel === "undefined" ? undefined : statusLabel
    });
  }

  function storeFeature() {
    return globalThis.OnPontoStore.create({
      data:typeof data === "undefined" ? undefined : data,
      employees:typeof employees === "undefined" ? undefined : employees
    });
  }

  function conferenciaFeature() {
    return globalThis.OnPontoConferencia.create({
      Utils:typeof Utils === "undefined" ? undefined : Utils,
      currentSlots:typeof currentSlots === "undefined" ? undefined : currentSlots,
      state:typeof state === "undefined" ? undefined : state
    });
  }

  function relatoriosFeature() {
    return globalThis.OnPontoRelatorios.create({
      apiErrorMessage:typeof apiErrorMessage === "undefined" ? undefined : apiErrorMessage
    });
  }

  function escalasFeature() {
    return globalThis.OnPontoEscalas.create({
      data:typeof data === "undefined" ? undefined : data
    });
  }

  function demonstracaoSolicitada() {
    return Boolean(root.location && new URLSearchParams(root.location.search || "").get("demo") === "1");
  }

  function marcarApiIndisponivel(error) {
    state.apiMode = "indisponivel";
    state.apiError = error && error.message || "API indisponível.";
    data = {};
    state.ocr = {};
  }

  function conectarApi() {
    if (conexaoApiPendente) return conexaoApiPendente;
    root.clearTimeout(tentativaApiTimer);
    tentativaApiTimer = null;
    conexaoApiPendente = bootstrapApiData().then(function () {
      if (state.apiMode === "indisponivel") {
        render();
        tentativaApiTimer = root.setTimeout(conectarApi, 5000);
        return;
      }
      return syncRouteFromLocation();
    }).finally(function () {
      conexaoApiPendente = null;
    });
    return conexaoApiPendente;
  }

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
    var base=String(configured || DEFAULT_API_BASE).trim().replace(/\/+$/, "");
    if(root.location && /^(localhost|127\.0\.0\.1)$/.test(root.location.hostname || "")) {
      base=base.replace(/^http:\/\/(localhost|127\.0\.0\.1)(?=:)/,"http://"+root.location.hostname);
    }
    return base;
  }

  function apiErrorMessage(payload, fallback) {
    return apiFeature().apiErrorMessage(payload,fallback);
  }

  function isClosedCompetenceError(error) {
    return apiFeature().isClosedCompetenceError(error);
  }

  function isRevisionConflictError(error) {
    return apiFeature().isRevisionConflictError(error);
  }

  function apiRequest(path, options) {
    return apiFeature().apiRequest(path,options);
  }

  function apiCollection(payload, aliases) {
    return apiFeature().apiCollection(payload,aliases);
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
      name: source.nome_exibicao || source.nome || source.name || "Funcionário",
      nome: source.nome || source.name || "Funcionário",
      code: source.codigo_exibicao || (source.codigo !== undefined ? source.codigo : source.code),
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
      pendingCount: source.pendingCount !== undefined ? source.pendingCount : null,
      fileCount: source.fileCount !== undefined ? source.fileCount : null,
      progress: source.progress !== undefined ? source.progress : null,
      confirmedEmployees: source.confirmedEmployees !== undefined ? source.confirmedEmployees : null,
      pendingEmployees: source.pendingEmployees !== undefined ? source.pendingEmployees : null,
      updatedAt: source.updatedAt || source.updated_at || null,
      receivedAt: source.receivedAt || source.data_recebimento || null,
      closedAt: source.closedAt || source.data_fechamento || null,
    });
  }

  function emptyRoute() {
    return navigationFeature().emptyRoute();
  }

  function safeDecode(value) {
    return navigationFeature().safeDecode(value);
  }

  function parseHashRoute(hash) {
    return navigationFeature().parseHashRoute(hash);
  }

  function validateRoute(route) {
    return navigationFeature().validateRoute(route);
  }

  function routeHash(route) {
    return navigationFeature().routeHash(route);
  }

  function routeView(route) {
    return navigationFeature().routeView(route);
  }

  function navigationTarget(route) {
    return navigationFeature().navigationTarget(route);
  }

  function normalizeRoute(route) {
    return navigationFeature().normalizeRoute(route);
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
    return importacaoFeature().normalizePreviewRow(item,index,analysisSource);
  }

  function normalizeImportAnalysis(payload) {
    return importacaoFeature().normalizeImportAnalysis(payload);
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
    var nonWorkingStatus = ["atestado", "folga", "feriado", "falta", "falta_justificada", "afastamento", "domingo", "sem_expediente"].indexOf(normalizedStatus) !== -1;
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

  function replaceAttendanceForCompetence(competenceId, markings, employeeId) {
    var remaining = days().filter(function (day) { return !idsEqual(day.competenceId || day.competencia_id, competenceId) || (employeeId != null && !idsEqual(day.employeeId || day.funcionario_id,employeeId)); });
    var merged = remaining.concat(markings.map(function (marking) {
      var key = String(marking.id);
      var current=findDay(marking.id);
      if (pendingDaySaves[key] || activeDaySaves[key] || (current && Number(current.revisao)>Number(marking.revisao))) return current || marking;
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
    return storeFeature().valueFromAliases(source,aliases);
  }

  function normalizeCompetenceSummary(payload) {
    return storeFeature().normalizeCompetenceSummary(payload);
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
      if (typeof activeDaySaves !== "undefined" && activeDaySaves[String(day.id)]) return;
      var detail = byId[String(day.id)];
      if (!detail || (detail.revisao != null && Number(detail.revisao)<Number(day.revisao))) return;
      day.calculoProvisorio = false;
      if (detail.revisao !== undefined) day.revisao = detail.revisao;
      day.intervalo_aplicado = detail.intervalo_aplicado;
      day.origens_horarios_calculo = detail.origens_horarios_calculo;
      day.dsr = detail.dsr;
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
      day.problema = detail.problema === true;
      day.problemLabel = detail.problema_rotulo;
      day.bloqueante = detail.bloqueante === true;
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
      day.issues = day.pendencias = [];
      if (pendingReason && (pendingCalculation || detail.problema)) {
        var issueList = [];
        if (!issueList.some(function (issue) { return issue && (issue.message || issue.mensagem) === pendingReason; })) {
          issueList.push({ id: "issue-apuration-" + day.id, type: pendingType || "review", severity: "warning", message: pendingReason, resolved: false });
        }
        day.issues = issueList;
        day.pendencias = issueList;
      }
    });

  }

  function invalidateAttendance(competenceId) {
    var prefix=String(competenceId);
    Object.keys(loadedCompetenceDays).forEach(function(key){if(key===prefix || key.indexOf(prefix+":")===0) delete loadedCompetenceDays[key];});
    Object.keys(reviewDaySequences).forEach(function(key){if(key.indexOf(prefix+":")===0) reviewDaySequences[key]+=1;});
  }

  function loadReviewDays(competenceId,employeeId,settings) {
    if(state.apiMode!=="online") return Promise.resolve([]);
    var key=String(competenceId)+":"+String(employeeId);
    if(loadedCompetenceDays[key] && !(settings && settings.force)) return Promise.resolve(employeeDays(employeeId));
    var sequence=(reviewDaySequences[key] || 0)+1;reviewDaySequences[key]=sequence;
    state.reviewLoading=true;
    return apiRequest("/apuracao/dias?competencia_id="+encodeURIComponent(competenceId)+"&funcionario_id="+encodeURIComponent(employeeId),{timeout:30000}).then(function(payload){
      if(reviewDaySequences[key]!==sequence) return [];
      var markings=apiCollection(payload,["registros"]).map(normalizeMarking);
      replaceAttendanceForCompetence(competenceId,markings,employeeId);
      applyApurationDetails(competenceId,payload.marcacoes);
      loadedCompetenceDays[key]=true;
      if(idsEqual(state.selectedCompetenceId,competenceId) && idsEqual(state.selectedEmployeeId,employeeId)) ensureReviewSelection();
      return markings;
    }).finally(function(){
      if(reviewDaySequences[key]===sequence && idsEqual(state.selectedCompetenceId,competenceId) && idsEqual(state.selectedEmployeeId,employeeId)) state.reviewLoading=false;
    });
  }

  function loadAttendanceForCompetence(competenceId, options) {
    if (state.apiMode !== "online" || competenceId === null || competenceId === undefined) return Promise.resolve([]);
    var settings = options || {};
    if ((settings.employeeId != null || state.route === "review") && (settings.employeeId != null || state.selectedEmployeeId != null)) return loadReviewDays(competenceId,settings.employeeId || state.selectedEmployeeId,settings);
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
    if (loadedCompetenceSummaries[key] && !settings.force && (data.competenceSummaries[key].summaryMode === (state.route === "review" ? "triagem" : "resumo"))) {
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
    var endpoint = state.route === "review" ? "/apuracao/triagem" : "/apuracao/resumo";
    var summaryMode = state.route === "review" ? "triagem" : "resumo";
    return apiRequest(endpoint + "?competencia_id=" + encodeURIComponent(competenceId), { timeout: 60000 }).then(function (payload) {
      if (competenceSummarySequences[key] !== sequence) return null;
      var summary = normalizeCompetenceSummary(payload);
      summary.apurationDetailed = Array.isArray(payload.marcacoes);
      summary.summaryMode = summaryMode;
      if (summary.competence) updateCompetenceFromPayload(competenceId, summary.competence);
      data.competenceSummaries[key] = summary;
      var competence = competencies().find(function(c){return idsEqual(c.id, competenceId);});
      if (competence && summary.operational) {
        competence.pendingCount = summary.operational.problemas;
        competence.fileCount = summary.operational.total_arquivos;
        competence.progress = summary.operational.total > 0 ? Math.round(100 * summary.operational.conferidos / summary.operational.total) : null;
        competence.confirmedEmployees = summary.general.confirmed;
        competence.pendingEmployees = summary.general.pending;
      }
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
    // Apuração e marcações são consultas; o calendário nasce da importação ou de ação explícita.
    return summaryPromise.then(function (summary) {
      return Promise.all([
        state.route === "review" || state.route === "competency-history" ? loadAttendanceForCompetence(competenceId, settings) : Promise.resolve([]),
        state.route === "competency-summary" ? Promise.resolve([]) : loadFilesForCompetence(competenceId, settings),
      ]).then(function (results) {
        if (summary) applyApurationDetails(competenceId, summary.markings);
    if (idsEqual(state.selectedCompetenceId, competenceId) && !state.reviewFilterInitialized) {
      state.reviewFilter = summary && summary.rows.some(function (d) { return Number(d.pending)>0; }) ? "pending" : "all";
      state.reviewFilterInitialized = true;
    }
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
    if (demonstracaoSolicitada()) {
      state.apiMode = "offline";
      state.apiError = "";
      return Promise.resolve(false);
    }
    if (state.apiMode !== "indisponivel") state.apiMode = "loading";
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
      marcarApiIndisponivel(error);
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
    state.reviewFilterInitialized = false;
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
    if (!scopedEmployees.some(function (item) { return idsEqual(item.id, state.selectedEmployeeId); })) {
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
        var attendanceRequest = (state.route === "review" || options && options.reloadAttendance)
          ? loadAttendanceForCompetence(competenceId, { force: true })
          : Promise.resolve(null);
        return attendanceRequest.then(function (markings) {
          if (summary) applyApurationDetails(competenceId, summary.markings);
    if (idsEqual(state.selectedCompetenceId, competenceId) && !state.reviewFilterInitialized) {
      state.reviewFilter = summary && summary.rows.some(function (d) { return Number(d.pending)>0; }) ? "pending" : "all";
      state.reviewFilterInitialized = true;
    }
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
    return conferenciaFeature().dayIsConfirmed(day);
  }

  function dayHasProblem(day) {
    return conferenciaFeature().dayHasProblem(day);
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
      if (state.reviewFilter === "pending") return dayHasProblem(day);
      if (state.reviewFilter === "unconfirmed") return !dayIsConfirmed(day);
      if (state.reviewFilter === "absences") return ["falta", "falta_justificada", "atestado", "folga", "afastamento"].indexOf(status) !== -1;
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
    var inCompetence = COMPETENCY_VIEWS.indexOf(state.route) !== -1;
    return {
      active: inCompetence ? "company-competencies" : state.route,
      primary: [
        { id: "companies", label: "Empresas", icon: "briefcase" },
        { id: "calendar", label: "Calendário", icon: "calendar" },
      ],
      secondary: company ? [
        { id: "company-overview", label: "Visão geral", icon: "dashboard" },
        { id: "company-competencies", label: "Competências", icon: "folder", current: inCompetence ? "location" : "page" },
        { label: "Cadastros", children: [
          { id: "company-employees", label: "Funcionários", icon: "users" },
          { id: "company-scales", label: "Escalas", icon: "clock" },
          { id: "company-ocorrencias", label: "Ocorrências / Afastamentos", icon: "calendar" },
          { id: "company-banco-horas", label: "Banco de horas", icon: "clock" },
        ] },
        { id: "company-reports", label: "Relatórios", icon: "report" },
        { id: "company-settings", label: "Configurações", icon: "settings" },
      ] : [],
      companyName: company ? company.name || company.nome : "",
    };
  }

  function unresolvedCount() {
    return employeeDays(state.selectedEmployeeId).filter(function (day) {
      return dayIsOperationallyPending(day);
    }).length;
  }

  function contextCompetencies(companyId) {
    return competencies().filter(function (item) {
      return idsEqual(item.companyId || item.empresa_id, companyId);
    }).sort(function (a, b) {
      return Number(b.year || b.ano) - Number(a.year || a.ano) || Number(b.month || b.mes) - Number(a.month || a.mes) || String(b.id).localeCompare(String(a.id), undefined, { numeric: true });
    });
  }

  function quickContextTarget(kind, value) {
    var id = asId(value);
    if (id === null) return null;
    var area = COMPETENCY_VIEWS.indexOf(state.route) !== -1 ? state.route : "competency-summary";
    // Prévias e leituras pertencem ao arquivo e à competência de origem.
    if (area === "import-preview" || area === "ocr") area = "imports";
    if (kind === "competence") {
      var selected = contextCompetencies(state.selectedCompanyId).find(function (item) { return idsEqual(item.id, id); });
      if (!selected || idsEqual(id, state.selectedCompetenceId)) return null;
      return { view: area, companyId: state.selectedCompanyId, competenceId: selected.id };
    }
    if (kind !== "company" || idsEqual(id, state.selectedCompanyId) || !companies().some(function (item) { return idsEqual(item.id, id); })) return null;
    if (COMPETENCY_VIEWS.indexOf(state.route) === -1) {
      return { view: COMPANY_VIEWS.indexOf(state.route) !== -1 ? state.route : "company-overview", companyId: id, competenceId: null };
    }
    var current = currentCompetency();
    var available = contextCompetencies(id);
    var next = available.find(function (item) {
      return current && Number(item.month || item.mes) === Number(current.month || current.mes) && Number(item.year || item.ano) === Number(current.year || current.ano);
    }) || available.find(function (item) { return !competencyIsClosed(item); }) || available[0];
    return { view: next ? area : "company-competencies", companyId: id, competenceId: next ? next.id : null };
  }

  function contextSwitchBlocked() {
    return contextSwitchPending || state.apiMode === "loading" || state.importConfirming || state.competenceLifecycleLoading;
  }

  function renderContextSelectors() {
    var companySelect = byId("contextCompany");
    var competenceSelect = byId("contextCompetence");
    var company = currentCompany();
    var competence = currentCompetency();
    var companyItems = companies().slice().sort(function (a, b) { return (a.name || a.nome).localeCompare(b.name || b.nome, "pt-BR"); });
    var competenceItems = contextCompetencies(state.selectedCompanyId);
    function update(select, items, placeholder, value, label) {
      var html = '<option value="" disabled>' + Utils.escapeHtml(placeholder) + '</option>' + items.map(function (item) {
        return '<option value="' + Utils.escapeHtml(item.id) + '">' + Utils.escapeHtml(label(item)) + '</option>';
      }).join("");
      // Preserva os nós e o foco dos seletores durante renders do autosave.
      if (select.dataset.optionsMarkup !== html) {
        select.innerHTML = html;
        select.dataset.optionsMarkup = html;
      }
      select.value = value == null ? "" : String(value);
      select.disabled = Boolean(contextSwitchBlocked() || !items.length);
      select.title = select.selectedOptions[0] ? select.selectedOptions[0].textContent : placeholder;
    }
    update(companySelect, companyItems, state.apiMode === "loading" ? "Carregando empresas…" : companyItems.length ? "Selecionar empresa" : "Nenhuma empresa", state.selectedCompanyId, function (item) { return item.name || item.nome; });
    update(competenceSelect, competenceItems, !company ? "Selecione uma empresa" : competenceItems.length ? "Selecionar competência" : "Sem competências", state.selectedCompetenceId, function (item) {
      var status = Components.statusMeta[Components.statusAliases[item.status] || item.status];
      return (item.label || Utils.formatCompetence(item)) + " · " + (status ? status.label : item.statusLabel || "Não informado");
    });
    byId("topbarContext").setAttribute("aria-busy", String(Boolean(contextSwitchPending)));
    byId("contextSwitchStatus").textContent = contextSwitchPending ? "Salvando alterações antes de trocar o contexto…" : company ? (company.name || company.nome) + (competence ? " · " + (competence.label || Utils.formatCompetence(competence)) : "") : "Nenhuma empresa selecionada";
  }

  function switchQuickContext(kind, value) {
    var next = quickContextTarget(kind, value);
    renderContextSelectors();
    if (!next || contextSwitchBlocked()) return Promise.resolve(false);
    if (editSession && !finishEditing({ move: null })) return Promise.resolve(false);
    var hasPending = Boolean(autosaveFlushPromise || Object.keys(pendingDaySaves).length);
    if (state.apiMode === "online" && hasPending && !state.settings.autosave) {
      showToast("Salve as alterações antes de trocar de empresa ou competência.", "warning", "O autosave está desativado. Use Salvar agora e tente novamente.");
      return Promise.resolve(false);
    }
    if (state.apiMode !== "online" || !hasPending) {
      navigate(next);
      return Promise.resolve(true);
    }
    var origin = routeHash({ view: state.route, companyId: state.selectedCompanyId, competenceId: state.selectedCompetenceId });
    contextSwitchPending = true;
    renderContextSelectors();
    return flushPendingDaySaves().then(function (results) {
      // Uma navegação realizada durante o salvamento tem prioridade sobre esta troca.
      if (root.location.hash !== origin) return false;
      if (editSession || autosaveFlushPromise || Object.keys(pendingDaySaves).length || state.autosaveStatus === "error" || results.some(function (result) { return !result.ok; })) {
        showToast("A troca foi interrompida para preservar suas alterações.", "warning", "Revise o salvamento e tente novamente.");
        return false;
      }
      navigate(next);
      return true;
    }).catch(function (error) {
      showToast("Não foi possível concluir o salvamento antes da troca.", "error", error && error.message);
      return false;
    }).finally(function () {
      contextSwitchPending = false;
      renderContextSelectors();
    });
  }

  // Atualização em segundo plano (ex.: depois do salvamento automático) não pode destruir
  // um horário sendo digitado nem tirar o foco da célula selecionada.
  function renderInBackground() {
    if (editSession) {
      deferredRender = true;
      return;
    }
    var active = document.activeElement;
    var cell = active && active.closest && active.closest(".editable-time-cell");
    render(cell && cell.dataset.dayId ? { focus: { dayId: cell.dataset.dayId, field: cell.dataset.field } } : undefined);
  }

  function render(options) {
    var settings = options || {};
    deferredRender = false;
    var main = byId("mainContent");
    var semConexao = state.apiMode === "indisponivel" || state.apiMode === "loading" && !demonstracaoSolicitada();
    byId("topbarContext").hidden = semConexao;
    var acoesTopo = document.querySelector(".topbar__actions");
    if (acoesTopo) acoesTopo.hidden = semConexao;
    if (semConexao) {
      byId("appSidebar").innerHTML = "";
      byId("sidebarExpandButton").hidden = true;
      var contexto = document.querySelector(".topbar__context .eyebrow");
      if (contexto) contexto.textContent = "Conexão com o On Ponto";
      main.dataset.route = "api-indisponivel";
      main.dataset.reviewKey = "";
      main.innerHTML = '<section class="screen"><section class="work-card" role="status">' + Components.EmptyState({
        icon: "alert",
        title: state.apiMode === "loading" ? "Conectando ao On Ponto" : "O On Ponto não está conectado",
        description: "Abra o On Ponto pelo atalho ou pelo iniciar_onponto.bat e mantenha aberta a janela 'On Ponto API'",
        action: { action: "tentar-conexao-api", label: "Tentar de novo", variant: "primary", disabled: state.apiMode === "loading" },
      }) + '<p class="helper-text">A conexão será tentada novamente a cada 5 segundos.</p></section></section>';
      document.title = "Conexão · On Ponto";
      return;
    }
    var reviewKey = state.route === "review" ? JSON.stringify([state.selectedCompanyId, state.selectedCompetenceId, state.selectedEmployeeId, state.reviewFilter]) : "";
    var scroll = captureReviewScroll(main, reviewKey);
    if (state.route === "review") ensureReviewSelection();

    var app = byId("app");
    app.classList.toggle("is-sidebar-collapsed", state.sidebarCollapsed);
    app.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);

    var navigation = sidebarNavigation();
    byId("appSidebar").innerHTML = Components.Sidebar({
      active: navigation.active,
      collapsed: state.sidebarCollapsed,
      primaryItems: navigation.primary,
      secondaryItems: navigation.secondary,
      companyName: navigation.companyName,
    });

    var expandButton = byId("sidebarExpandButton");
    expandButton.hidden = !state.sidebarCollapsed;
    expandButton.innerHTML = Components.Icon("panel_left");

    var environmentLabel = document.querySelector(".topbar__context .eyebrow");
    if (environmentLabel) {
      environmentLabel.textContent = state.apiMode === "online" ? "Ambiente integrado" : state.apiMode === "loading" ? "Conectando à API" : "Ambiente de demonstração";
    }
    renderContextSelectors();

    var sameReview=state.route === "review" && main.dataset.reviewKey===reviewKey && main.dataset.route === "review";
    main.dataset.route = state.route;
    main.dataset.reviewKey = reviewKey;
    var markup=state.route === "calendar" ? root.OnPontoCalendario.render(state,data,Components) : Screens.render(state.route,state,data,Components);
    if(main._renderedMarkup!==markup) {
      if(sameReview) globalThis.OnPontoConferencia.patchReview(main,markup);
      else main.innerHTML=markup;
      main._renderedMarkup=markup;
    }
    restoreReviewScroll(main, scroll);
    document.title = screenTitle() + " · On Ponto";

    Array.prototype.forEach.call(main.querySelectorAll('[data-indeterminate="true"]'), function (checkbox) {
      checkbox.indeterminate = true;
    });
    if (state.route === "imports") ensureImportPendingData();

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
    return conferenciaFeature().captureReviewScroll(main,key);
  }

  function restoreReviewScroll(main, positions) {
    return conferenciaFeature().restoreReviewScroll(main,positions);
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
        var navigationSequence=++routeLoadSequence;
        loading.then(function () {
          if(navigationSequence!==routeLoadSequence) return;
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
      // help pode ser uma função dos valores atuais; o texto é refeito a cada digitação.
      var dynamicHelp = typeof field.help === "function";
      label.innerHTML = '<span>' + Utils.escapeHtml(field.label || "Valor") + "</span>" + dialogFieldMarkup(field, fieldId) + (field.help ? '<small class="dialog-field-help"' + (dynamicHelp ? ' aria-live="polite"' : "") + ">" + (dynamicHelp ? "" : Utils.escapeHtml(field.help)) + "</small>" : "");
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
    dialog.addEventListener("input", function () { refreshConditionalDialogFields(pendingDialog); });
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
      var help = typeof field.help === "function" && wrapper && wrapper.querySelector(".dialog-field-help");
      if (help) help.textContent = visible ? field.help(values) || "" : "";
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
    return importacaoFeature().importConflictMessages(payload);
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
    state.reviewFilterInitialized = false;
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
          revisao_previa: analysis.revisao_previa,
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
            invalidateAttendance(confirmationCompetenceId);
            showToast(
              "Importação confirmada.",
              conflicts.length ? "warning" : "success",
              "Os dados foram salvos na competência " + (competence ? competence.label || Utils.formatCompetence(competence) : confirmationCompetenceId) + "."
            );
            return;
          }

          return loadAttendanceForCompetence(confirmationCompetenceId, { force: true,employeeId:(analysis.rows.find(function(r){return selectedIds.some(function(id){return idsEqual(id,r.id);});}) || {}).employeeId }).then(function (markings) {
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
    state.reviewFilterInitialized = false;
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
    var employee=companyEmployees().find(function(item){return idsEqual(item.id,id);});
    if(!employee) return Promise.resolve(false);
    if(editSession && !finishEditing({move:null})) return Promise.resolve(false);
    var competenceId=state.selectedCompetenceId;
    var pending=autosaveFlushPromise || Object.keys(pendingDaySaves).length;
    if(pending && state.settings.autosave===false) {
      showToast("Salve as alterações antes de trocar de funcionário.","warning");return Promise.resolve(false);
    }
    return (pending ? ensureAutosaveFlushedForLifecycle() : Promise.resolve()).then(function(){
      if(!idsEqual(state.selectedCompetenceId,competenceId)) return false;
      state.selectedEmployeeId=employee.id;state.selectedDayIds=[];state.selectedDayId=null;
      if(state.apiMode!=="online") {ensureReviewSelection();render();return true;}
      render();
      return loadReviewDays(competenceId,employee.id).then(function(){
        if(idsEqual(state.selectedCompetenceId,competenceId) && idsEqual(state.selectedEmployeeId,employee.id)) {ensureReviewSelection();render();}
        return true;
      });
    }).catch(function(error){showToast("A troca de funcionário foi interrompida.","error",error.message);return false;});
  }

  function moveToProblemEmployee() {
    var summary = (data.competenceSummaries || {})[String(state.selectedCompetenceId)];
    var next = Utils.nextProblemEmployee(companyEmployees(), summary && summary.rows, state.selectedEmployeeId);
    if (!next) return showToast("Não há próximo funcionário com problema nesta ordem.", "info");
    state.employeeSearch = "";
    state.reviewFilter = "pending";
    selectEmployee(next.id);
  }

  function assignOriginalPunch(dayId, index, field) {
    if (!ensureCompetencyWritable("A atribuição de batidas")) return;
    var day = findDay(dayId);
    if (!day || dayIsConfirmed(day)) return showToast("Reabra a conferência antes de atribuir uma batida.", "warning");
    var fields = ["entry", "breakStart", "breakEnd", "exit"];
    if (fields.indexOf(field) < 0) return;
    var punches = day.originalPunches || [];
    var punch = punches[index];
    var value = typeof punch === "object" && punch ? punch.value || punch.time || punch.horario : punch;
    var parsed = Utils.validateTimeInput(value || "");
    if (!parsed.valid || !parsed.normalized) return;
    var slots = currentSlots(day);
    if (slots[field] || Object.values(slots).includes(parsed.normalized)) return showToast("A batida já está atribuída ou o campo está ocupado. Corrija ou desfaça antes de atribuir.", "warning");
    var proposed = Object.assign({}, slots); proposed[field] = parsed.normalized;
    var ordered = fields.map(function (key) { return proposed[key]; }).filter(Boolean);
    if (ordered.some(function (time, i) { return i && time <= ordered[i - 1]; })) return showToast("Esta atribuição deixaria os horários fora de ordem.", "warning");
    applySlot(day, field, parsed.normalized);
    state.undoStack.push({ type: "time", dayId: day.id, field: field, previous: slots[field], next: parsed.normalized });
    addHistory(day, "Batida original atribuída a " + fieldLabel(field) + ": " + parsed.normalized + ".", "Operador local");
    queueAutosave(day);
    render();
  }

  function updateDayFromMarking(day, marking) {
    if (marking.revisao !== undefined) day.revisao = marking.revisao;
    day.batidas_desconsideradas = marking.batidas_desconsideradas || [];
    if (Array.isArray(marking.historico)) {
      day.history = marking.historico;
      day.historico = marking.historico;
    }
  }

  function originalPunchDecision(dayId, request, successMessage) {
    var day = findDay(dayId);
    if (!day || state.apiMode !== "online") return Promise.reject(new Error("A decisão sobre batidas exige a API conectada."));
    var competenceId = day.competenceId || day.competencia_id || state.selectedCompetenceId;
    // Salvamentos pendentes (ex.: reabertura do dia) precisam chegar antes da decisão.
    return flushPendingDaySaves().then(function (results) {
      if (results.some(function (result) { return !result.ok; }) || state.autosaveStatus === "error" ||
          autosaveFlushPromise || Object.keys(pendingDaySaves).length) {
        throw new Error("Não foi possível salvar todos os horários. Revise o salvamento e tente novamente antes de alterar o destino da batida.");
      }
      return request();
    }).then(function (marking) {
      updateDayFromMarking(day, marking || {});
      return refreshAffectedCompetence(competenceId);
    }).then(function () {
      render();
      showToast(successMessage, "success", "A batida original continua preservada no arquivo e no registro do dia.");
    });
  }

  function discardOriginalPunch(dayId, index) {
    if (!ensureCompetencyWritable("A desconsideração de batidas")) return;
    var day = findDay(dayId);
    if (!day || dayIsConfirmed(day)) return showToast("Reabra a conferência antes de desconsiderar uma batida.", "warning");
    var value = (day.originalPunches || [])[index];
    showDialog({
      title: "Desconsiderar batida " + (value || "") + "?",
      description: "Use para batidas duplicadas ou sem efeito. A batida deixa de exigir atribuição, mas continua preservada e o motivo fica no histórico.",
      confirmLabel: "Desconsiderar batida",
      fields: [{ name: "justificativa", label: "Justificativa", type: "textarea", required: true, maxlength: 1000, placeholder: "Ex.: batida duplicada no mesmo minuto.",
        validate: function (text) { return String(text || "").trim().length < 10 ? "Informe uma justificativa com ao menos dez caracteres." : ""; } }],
      onConfirm: function (values) {
        return originalPunchDecision(dayId, function () {
          return apiRequest("/marcacoes/" + encodeURIComponent(day.id) + "/batidas-desconsideradas", { method: "POST", body: { indice: index, justificativa: String(values.justificativa).trim(), revisao: day.revisao } });
        }, "Batida desconsiderada.");
      },
    });
  }

  function restoreOriginalPunch(dayId, index) {
    if (!ensureCompetencyWritable("A restauração de batidas")) return;
    var day = findDay(dayId);
    if (!day || dayIsConfirmed(day)) return showToast("Reabra a conferência antes de restaurar uma batida.", "warning");
    originalPunchDecision(dayId, function () {
      return apiRequest("/marcacoes/" + encodeURIComponent(day.id) + "/batidas-desconsideradas/" + encodeURIComponent(index) + "?revisao=" + encodeURIComponent(day.revisao), { method: "DELETE" });
    }, "Batida restaurada.").catch(function (error) {
      showToast("Não foi possível restaurar a batida.", "error", error && error.message);
    });
  }

  function moveEmployee(direction) {
    var list = companyEmployees();
    var index = list.findIndex(function (item) { return idsEqual(item.id, state.selectedEmployeeId); });
    var nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= list.length) {
      showToast(direction < 0 ? "Este é o primeiro funcionário." : "Este é o último funcionário.", "info");
      return;
    }
    state.employeeSearch = "";
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
    } else if (["atestado", "folga", "feriado", "falta", "falta_justificada", "afastamento", "domingo", "sem_expediente"].indexOf(status) !== -1) {
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
    if (state.apiMode === "online") return confirmDaysOnServer([day]);
    if (dayHasProblem(day)) { showToast("Resolva os problemas antes de conferir.", "warning"); return false; }
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
    if(state.apiMode==="online") {
      var competenceId=day.competenceId || day.competencia_id || state.selectedCompetenceId;
      return ensureAutosaveFlushedForLifecycle().then(function(){
        return apiRequest("/marcacoes/"+encodeURIComponent(day.id),{method:"PATCH",body:{conferido:false,revisao:day.revisao}});
      }).then(function(){return refreshAffectedCompetence(competenceId,{reloadAttendance:true});}).then(function(){
        render();showToast("Conferência reaberta.","success");
      }).catch(function(error){showToast("Não foi possível reabrir o dia.","error",error.message);return false;});
    }
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
    return conferenciaFeature().recalculateDay(day);
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
      revisao: day.revisao,
      entrada: slots.entry || null,
      saida_almoco: slots.breakStart || null,
      retorno_almoco: slots.breakEnd || null,
      saida: slots.exit || null,
      status_dia: statusToBackend(day.status_dia || day.status || day.current && day.current.status),
      conferido: dayIsConfirmed(day),
      observacoes: day.observation || day.observacao || day.current && (day.current.observation || day.current.observacao) || null,
    };
  }

  function resolveDaySaveConflict(entry) {
    return apiRequest("/marcacoes/" + encodeURIComponent(entry.id)).then(function (server) {
      var local = pendingDaySaves[String(entry.id)] || entry;
      var fields = ["entrada", "saida_almoco", "retorno_almoco", "saida", "status_dia", "conferido", "observacoes"];
      var labels = {entrada: "Entrada", saida_almoco: "Saída para almoço", retorno_almoco: "Retorno do almoço", saida: "Saída", status_dia: "Situação", conferido: "Conferido", observacoes: "Observação"};
      var rows = fields.map(function (field) {
        return "<tr><th>" + Utils.escapeHtml(labels[field]) + "</th><td>" + Utils.escapeHtml(String(server[field] == null ? "—" : server[field])) +
          "</td><td>" + Utils.escapeHtml(String(local.payload[field] == null ? "—" : local.payload[field])) + "</td></tr>";
      }).join("");
      showDialog({title: "Este dia foi alterado em outra janela", confirmLabel: "Aplicar escolha", cancelLabel: "Continuar revisando",
        description: "Sua edição está preservada e o envio foi suspenso. Compare os valores antes de continuar.",
        html: "<table><thead><tr><th>Campo</th><th>Salvo no servidor</th><th>Sua edição</th></tr></thead><tbody>" + rows + "</tbody></table>",
        field: {type: "select", label: "Como resolver", value: "server", options: [
          {value: "server", label: "Usar os valores salvos no servidor"},
          {value: "local", label: "Salvar minha edição após esta revisão"}]},
        onConfirm: function (choice) {
          var key = String(entry.id);
          var current = pendingDaySaves[key] || local;
          if (choice === "local") {
            current.payload.revisao = server.revisao;
            delete current.conflict;
            pendingDaySaves[key] = current;
            var day = findDay(entry.id);
            if (day) day.revisao = server.revisao;
            return flushPendingDaySaves().then(function (results) {
              if (results.some(function (r) { return !r.ok; })) throw new Error("O salvamento ainda exige revisão.");
            });
          }
          delete pendingDaySaves[key];
          state.undoStack = (state.undoStack || []).filter(function (item) { return !idsEqual(item.dayId, entry.id); });
          return refreshAffectedCompetence(entry.competenceId, {reloadAttendance: true}).then(function () {
            state.autosaveStatus = Object.keys(pendingDaySaves).length ? "unsaved" : "saved";
            render();
          });
        }});
    }).catch(function (error) { showToast("Não foi possível carregar o dia para revisão.", "error", error.message); });
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
        if (entry.conflict) return results.concat({ok: false, entry: entry, error: entry.conflict});
        return apiRequest("/marcacoes/" + encodeURIComponent(entry.id), {
          method: "PATCH",
          body: entry.payload,
          timeout: 12000,
          keepalive: true,
        }).then(function (response) {
          var day = findDay(entry.id);
          if (response.revisao !== undefined) {
            if (day && (day.revisao == null || day.revisao <= response.revisao)) day.revisao = response.revisao;
            var newer = pendingDaySaves[key];
            if (newer && newer.payload.revisao === entry.payload.revisao) newer.payload.revisao = response.revisao;
          }
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
        if (isRevisionConflictError(result.error)) pendingDaySaves[key].conflict = result.error;
      });
      if (failed.length) {
        state.autosaveStatus = "error";
        updateAutosaveIndicator();
        var conflict = failed.find(function (result) { return isRevisionConflictError(result.error); });
        if (conflict) resolveDaySaveConflict(pendingDaySaves[String(conflict.entry.id)] || conflict.entry);
        if (closedFailures.length) {
          showToast("A competência foi fechada antes do salvamento.", "error", "As alterações recusadas não serão reenviadas automaticamente. Reabra a competência antes de editar.");
        } else {
          showToast("Não foi possível salvar todas as alterações.", "error", failed[0].error && failed[0].error.message || "Tente novamente.");
        }
      } else if (!Object.keys(pendingDaySaves).length) {
        state.autosaveStatus = "saved";
        updateAutosaveIndicator();
      }
      results.forEach(function(r){if(r.ok) delete activeDaySaves[String(r.entry.id)];});
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
        if (Object.keys(competencesToRefresh).some(function (key) { return idsEqual(key, state.selectedCompetenceId); })) renderInBackground();
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
      var existingConflict = pendingDaySaves[String(day.id)] && pendingDaySaves[String(day.id)].conflict;
      pendingDaySaves[String(day.id)] = {
        id: day.id,
        competenceId: day.competenceId || day.competencia_id || state.selectedCompetenceId,
        payload: daySavePayload(day),
        syncCompetence: true,
        conflict: existingConflict,
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
    // Horário inválido descartado não é falha de salvamento: retoma o que estava agendado.
    if (state.autosaveStatus === "error" && !autosaveFlushPromise && !competencyIsClosed()) {
      if (Object.keys(pendingDaySaves).length) queueAutosave(null);
      else {
        state.autosaveStatus = "saved";
        updateAutosaveIndicator();
      }
    }
    if (deferredRender) {
      renderFocus = { dayId: session.dayId, field: session.field };
      render();
    }
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
      if (deferredRender) {
        renderFocus = movementTarget(session.dayId, session.field, move) || { dayId: session.dayId, field: session.field };
        render();
      } else if (move) moveFromCell(session.dayId, session.field, move);
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
    showToast(state.apiMode==="online" ? "Última alteração desfeita localmente." : "Última alteração desfeita.", state.apiMode==="online" ? "info" : "success");
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
      showToast(state.apiMode==="online" ? "Observação alterada localmente; aguarde o salvamento." : "Observação salva.", state.apiMode==="online" ? "info" : "success");
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
        showToast("Observação alterada em " + targets.length + " registro(s).", state.apiMode==="online" ? "info" : "success",state.apiMode==="online" ? "Alteração local; aguarde o salvamento." : "");
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
        showToast("Situação alterada em " + targets.length + " registro(s).", state.apiMode==="online" ? "info" : "success",state.apiMode==="online" ? "Alteração local; aguarde o salvamento." : "");
      },
    });
  }

  function confirmDaysOnServer(targets) {
    var competenceId = state.selectedCompetenceId;
    return ensureAutosaveFlushedForLifecycle().then(function () {
      var revisoes = {};
      targets.forEach(function (d) { revisoes[d.id] = (findDay(d.id) || d).revisao; });
      return apiRequest("/marcacoes/conferir-lote", {method: "POST", body: {competencia_id: competenceId, marcacoes_ids: targets.map(function(d){return d.id;}), revisoes: revisoes}});
    }).then(function (result) {
      return refreshAffectedCompetence(competenceId, {reloadAttendance: true}).then(function () {
        state.selectedDayIds = [];
        render();
        showToast(result.total_conferidos + " dias marcados como conferidos. " + result.total_problemas + " permaneceram com problemas.", result.total_problemas ? "warning" : "success");
        return result;
      });
    }).catch(function(error){ showToast("Não foi possível conferir.", "error", error.message); return false; });
  }

  var importGroupRequests = Object.create(null);
  var ignoredPeopleRequests = Object.create(null);

  function importPendingKey(file) {
    var control = file && file.controle_importacao;
    return (control && control.pendencias || []).map(function (item) { return item.registro_id; }).join(",");
  }

  // Pendências agrupadas por pessoa do relógio; só recarrega quando a lista do arquivo muda.
  function ensureImportPendingData() {
    if (state.apiMode !== "online" || state.route !== "imports" || state.selectedCompetenceId == null) return;
    data.importGroups = data.importGroups || Object.create(null);
    files().forEach(function (file) {
      if (!idsEqual(file.competenceId || file.competencia_id, state.selectedCompetenceId)) return;
      var fileKey = String(file.id);
      var key = importPendingKey(file);
      var cached = data.importGroups[fileKey];
      if (!key || (cached && cached.key === key) || importGroupRequests[fileKey] === key) return;
      importGroupRequests[fileKey] = key;
      apiRequest("/importadores/" + encodeURIComponent(file.id) + "/pendencias-agrupadas", { timeout: 15000 }).then(function (groups) {
        data.importGroups[fileKey] = { key: key, groups: Array.isArray(groups) ? groups : [] };
      }).catch(function (error) {
        data.importGroups[fileKey] = { key: key, groups: null, error: error && error.message };
      }).then(function () {
        if (importGroupRequests[fileKey] === key) delete importGroupRequests[fileKey];
        if (state.route === "imports") render();
      });
    });
    data.ignoredPeople = data.ignoredPeople || Object.create(null);
    var companyKey = String(state.selectedCompanyId);
    if (state.selectedCompanyId != null && !data.ignoredPeople[companyKey] && !ignoredPeopleRequests[companyKey]) {
      ignoredPeopleRequests[companyKey] = true;
      apiRequest("/importadores/ignorados?empresa_id=" + encodeURIComponent(state.selectedCompanyId)).then(function (list) {
        data.ignoredPeople[companyKey] = Array.isArray(list) ? list : [];
      }).catch(function () {
        data.ignoredPeople[companyKey] = [];
      }).then(function () {
        delete ignoredPeopleRequests[companyKey];
        if (state.route === "imports") render();
      });
    }
  }

  function importGroup(fileId, index) {
    var cached = data.importGroups && data.importGroups[String(fileId)];
    return cached && cached.groups ? cached.groups[index] || null : null;
  }

  function importPersonLabel(group) {
    return (group.nome_origem || "Pessoa sem nome") + (group.codigo_origem ? " (código " + group.codigo_origem + " no relógio)" : "");
  }

  // A decisão vale para a empresa: todas as competências abertas são recarregadas.
  function refreshImportsAfterDecision(companyId) {
    competencies().forEach(function (competence) {
      if (!idsEqual(competence.companyId || competence.empresa_id, companyId)) return;
      delete loadedCompetenceFiles[String(competence.id)];
      delete loadedCompetenceSummaries[String(competence.id)];
    });
    if (data.ignoredPeople) delete data.ignoredPeople[String(companyId)];
    return loadCompetenceData(state.selectedCompetenceId, { force: true, summaryForce: true }).then(function () { render(); });
  }

  var IMPORT_JUSTIFICATION_FIELD = { name: "justificativa", label: "Justificativa", type: "textarea", required: true, maxlength: 1000,
    validate: function (text) { return String(text || "").trim().length < 10 ? "Informe uma justificativa com ao menos dez caracteres." : ""; } };

  function ignoreImportPerson(fileId, index) {
    if (!ensureCompetencyWritable("A decisão sobre importações")) return;
    var group = importGroup(fileId, index);
    if (!group) return;
    var companyId = state.selectedCompanyId;
    var days = (group.registros || []).length;
    // Quem bate ponto quase todo dia provavelmente é funcionário sem cadastro, não gestão.
    var frequentWarning = days >= 5 ? " Atenção: são " + days + " dias com batidas neste arquivo. Se for funcionário, cadastre-o em vez de ignorar." : "";
    showDialog({
      title: "Ignorar " + (group.nome_origem || "esta pessoa") + " nas importações?",
      description: importPersonLabel(group) + " deixa de compor a apuração desta empresa, agora e nas próximas importações. Os registros ficam excluídos com esta justificativa, o arquivo original é preservado e a decisão pode ser desfeita. Se a pessoa for cadastrada no OnPonto, o cadastro prevalece." + frequentWarning,
      confirmLabel: "Ignorar nas importações",
      fields: [Object.assign({}, IMPORT_JUSTIFICATION_FIELD, { placeholder: "Ex.: Diretoria, não controla jornada no ponto." })],
      onConfirm: function (values) {
        return apiRequest("/importadores/ignorados", { method: "POST", timeout: 30000, body: {
          empresa_id: companyId, codigo_origem: group.codigo_origem || null, nome_origem: group.nome_origem || null,
          justificativa: String(values.justificativa).trim(),
        } }).then(function (result) {
          return refreshImportsAfterDecision(companyId).then(function () {
            showToast(importPersonLabel(group) + " será ignorada nas importações.", "success", (result.registros_excluidos || 0) + " registro(s) excluído(s) da apuração nas competências abertas.");
          });
        });
      },
    });
  }

  function discardImportGroup(fileId, index) {
    if (!ensureCompetencyWritable("A exclusão de registros")) return;
    var group = importGroup(fileId, index);
    if (!group) return;
    var ids = group.registros.map(function (item) { return item.registro_id; });
    showDialog({
      title: "Excluir " + ids.length + " registro(s) da apuração?",
      description: importPersonLabel(group) + ": os registros desta pessoa neste arquivo não comporão a competência. O arquivo original é preservado. Para que as próximas importações também ignorem a pessoa, use “Ignorar nas importações”.",
      confirmLabel: "Registrar exclusão",
      fields: [IMPORT_JUSTIFICATION_FIELD],
      onConfirm: function (values) {
        return apiRequest("/importadores/" + encodeURIComponent(fileId) + "/descartar-pendencias", { method: "POST", body: { registros_ids: ids, justificativa: String(values.justificativa).trim() } })
          .then(function () { return refreshImportsAfterDecision(state.selectedCompanyId); });
      },
    });
  }

  function unignoreImportPerson(ruleId) {
    if (!ensureCompetencyWritable("A decisão sobre importações")) return;
    var companyId = state.selectedCompanyId;
    var rule = ((data.ignoredPeople || {})[String(companyId)] || []).find(function (item) { return idsEqual(item.id, ruleId); });
    if (!rule) return;
    showDialog({
      title: "Voltar a considerar " + (rule.nome_origem || "esta pessoa") + "?",
      description: "Os registros excluídos por esta regra nas competências abertas voltam a ser pendências de importação. Competências fechadas não são alteradas.",
      confirmLabel: "Voltar a considerar",
      onConfirm: function () {
        return apiRequest("/importadores/ignorados/" + encodeURIComponent(ruleId), { method: "DELETE", timeout: 30000 }).then(function (result) {
          return refreshImportsAfterDecision(companyId).then(function () {
            showToast("Regra desativada.", "success", (result.registros_restaurados || 0) + " registro(s) voltaram a ser pendências.");
          });
        }).catch(function (error) {
          showToast("Não foi possível desativar a regra.", "error", error && error.message);
        });
      },
    });
  }

  function resumeImport(fileId) {
    var id = state.selectedCompetenceId;
    return loadFilesForCompetence(id, {force:true}).then(function(list){
      var file = (fileId && list.find(function(f){return idsEqual(f.id,fileId);})) || list.find(function(f){return !f.controle_importacao || f.controle_importacao.estado !== "confirmada";}) || list[0];
      if (!file) return navigate("imports");
      return apiRequest("/importadores/" + file.id + "/reanalisar", {method:"POST"}).then(function(payload){
        state.importAnalysis = normalizeImportAnalysis(payload);
        state.selectedImportRowIds = state.importAnalysis.rows.filter(function(r){return r.selected;}).map(function(r){return r.id;});
        navigate("import-preview");
      });
    }).catch(function(e){showToast("Não foi possível retomar a análise.", "error", e.message);});
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
        if (state.apiMode === "online") return confirmDaysOnServer(targets);
        var valid = targets.filter(function(day){ return !dayHasProblem(day); });
        valid.forEach(function (day) { confirmDay(day, { silent: true }); });
        state.selectedDayIds = [];
        render();
        showToast(valid.length + " registros conferidos; " + (targets.length - valid.length) + " com problemas.", "info");
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
    showToast("Interpretação selecionada.", "info", "Aguarde o salvamento e a apuração; o dia ainda precisa ser conferido.");
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
    return relatoriosFeature().exportFilename(response,competence,company);
  }

  function exportResponseError(response) {
    return relatoriosFeature().exportResponseError(response);
  }

  function exportErrorDetail(error) {
    return relatoriosFeature().exportErrorDetail(error);
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
    return apiFeature().authenticatedFetch("/relatorios/excel?competencia_id=" + encodeURIComponent(competenceId), requestOptions).then(function (response) {
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
    if (!demonstracaoSolicitada()) {
      showToast("Leitura simulada disponível apenas na demonstração.", "warning");
      return;
    }
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
      if(editSession || autosaveFlushPromise || Object.keys(pendingDaySaves).length || state.autosaveStatus==="error") {
        throw new Error("Há alterações novas ou pendentes. Conclua o salvamento antes de continuar.");
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
      if (lifecycleContextIsActive(competenceId)) state.competenceLifecycleError = error && error.message || "Não foi possível atualizar a competência.";
      throw error;
    }).finally(function () {
      if (lifecycleContextIsActive(competenceId)) setLifecycleState(competenceId, false, "", state.competenceLifecycleError);
    });
  }

  function showCloseCompetencyDialog(competenceId, summary) {
    var warnings = summary && Array.isArray(summary.linkWarnings) ? summary.linkWarnings : [];
    var notice = warnings.length ? " Atenção: " + warnings.length + " vínculo(s) histórico(s) incompleto(s). Revise as datas de admissão e demissão no cadastro. Dias ausentes não foram presumidos." : "";
    showDialog({title: "Fechar esta competência?", description: "A apuração será preservada e novas alterações exigirão reabertura." + notice,
      confirmLabel: "Fechar competência", busyLabel: "Fechando...", destructive: true,
      onConfirm: function(){return persistCompetenceLifecycle(competenceId, "fechar", false);}});
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
      var demoPending = demoDays.filter(function (day) { return !dayIsConfirmed(day) || dayHasProblem(day); }).length;
      if (demoPending || !demoDays.length) { showToast("Conclua a conferência e resolva os problemas antes de fechar.", "warning"); return; }
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
      if (!summary.closing || summary.closing.pode_fechar !== true) {
        throw new Error(summary.closing && summary.closing.motivo_bloqueio || "A API não confirmou que a competência pode ser fechada.");
      }
      setLifecycleState(competenceId, false, "", "");
      showCloseCompetencyDialog(competenceId, summary);
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
    if (!demonstracaoSolicitada()) return;
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
      invalidateAttendance(key);
      delete loadedCompetenceSummaries[key];
      if (data.competenceSummaries) delete data.competenceSummaries[key];
    });
  }

  function dialogTimeMinutes(value) {
    return escalasFeature().dialogTimeMinutes(value);
  }

  function nullableDialogNumber(value) {
    return escalasFeature().nullableDialogNumber(value);
  }

  function hourPolicyFields(entity) {
    return escalasFeature().hourPolicyFields(entity);
  }

  function hourPolicyPayload(v) {
    return escalasFeature().hourPolicyPayload(v);
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
        { name: "vigente_desde", type: "date", label: "Início da vigência da regra", value: "", fullWidth: true, help: entity ? "Informe a data da nova regra. Em branco, usa a próxima vigência futura disponível. Dias abertos afetados precisam de nova conferência." : "Se a vigência histórica for desconhecida, deixe em branco; essa limitação será preservada." },
        { name: "modo_apuracao", type: "select", label: "Modo de apuração", value: mode, required: true, fullWidth: true, options: [{ value: "carga_horaria", label: "Carga horária" }, { value: "horario_fixo", label: "Horário fixo" }] },
        { name: "jornada_seg_sex_horas", type: "number", label: "Jornada de segunda a sexta (horas)", value: entity && entity.jornada_seg_sex_horas !== null && entity.jornada_seg_sex_horas !== undefined ? entity.jornada_seg_sex_horas : "8", required: true, min: 0, max: 24, step: 0.01, visibleWhen: isWorkload },
        { name: "jornada_sabado_horas", type: "number", label: "Jornada de sábado (horas)", value: entity && entity.jornada_sabado_horas !== null && entity.jornada_sabado_horas !== undefined ? entity.jornada_sabado_horas : "", min: 0, max: 24, step: 0.01, visibleWhen: isWorkload },
        { name: "horario_entrada_prevista", type: "time", label: "Entrada prevista", value: entity ? normalizedTime(entity.horario_entrada_prevista) : "", required: true, visibleWhen: isFixed },
        { name: "horario_saida_prevista", type: "time", label: "Saída prevista", value: entity ? normalizedTime(entity.horario_saida_prevista) : "", required: true, visibleWhen: isFixed },
        { name: "horario_saida_almoco_prevista", type: "time", label: "Saída para almoço prevista", value: entity ? normalizedTime(entity.horario_saida_almoco_prevista) : "", visibleWhen: function(v){return isFixed(v) || v.tipo_intervalo==="fixo" || v.registro_intervalo==="pre_assinalado";} },
        { name: "horario_retorno_almoco_prevista", type: "time", label: "Retorno do almoço previsto", value: entity ? normalizedTime(entity.horario_retorno_almoco_prevista) : "", visibleWhen: function(v){return isFixed(v) || v.tipo_intervalo==="fixo" || v.registro_intervalo==="pre_assinalado";} },
        { name: "tipo_intervalo", type: "select", label: "Tipo de intervalo", value: entity && entity.tipo_intervalo || "legado", options: [{value:"legado",label:"Preservar regra anterior"},{value:"fixo",label:"Fixo"},{value:"flexivel",label:"Flexível"},{value:"sem_intervalo",label:"Sem intervalo"}], help:"Nova configuração passa a valer na vigência informada." },
        { name: "registro_intervalo", type: "select", label: "Registro do intervalo", value: entity && entity.registro_intervalo || "batidas", options:[{value:"batidas",label:"Batidas reais"},{value:"pre_assinalado",label:"Pré-assinalado explicitamente"}], visibleWhen:function(v){return v.tipo_intervalo!=="legado";} },
        { name: "duracao_intervalo_minutos", type: "number", label: "Duração do intervalo (min)", value: entity && entity.duracao_intervalo_minutos!=null ? entity.duracao_intervalo_minutos : 60, min:1,max:1440,step:1,visibleWhen:function(v){return v.tipo_intervalo==="fixo" || v.tipo_intervalo==="flexivel";} },
        { name: "regime_sabado", type: "select", label: "Regime de sábado", value: entity ? entity.regime_sabado : "nao_trabalha", required: true, options: [{ value: "trabalha", label: "Trabalha" }, { value: "compensado", label: "Compensado" }, { value: "nao_trabalha", label: "Não trabalha" }] },
        { name: "regime_domingo", type: "select", label: "Regime de domingo", value: entity ? entity.regime_domingo : "nao_trabalha", required: true, options: [{ value: "trabalha", label: "Trabalha" }, { value: "nao_trabalha", label: "Não trabalha" }] },
        { name: "sabado_proprio", type:"select",label:"Horários próprios de sábado",value:entity && entity.jornadas_semana && entity.jornadas_semana["5"] ? "preservar":"false",options:[{value:"preservar",label:"Manter jornada diária salva"},{value:"false",label:"Usar jornada da escala"},{value:"true",label:"Informar entrada e saída sem almoço"}],visibleWhen:function(v){return v.regime_sabado==="trabalha";} },
        { name: "sabado_entrada",type:"time",label:"Entrada de sábado",value:entity && entity.jornadas_semana && entity.jornadas_semana["5"] && entity.jornadas_semana["5"].horario_entrada_prevista || "08:00",visibleWhen:function(v){return v.regime_sabado==="trabalha" && v.sabado_proprio==="true";} },
        { name: "sabado_saida",type:"time",label:"Saída de sábado",value:entity && entity.jornadas_semana && entity.jornadas_semana["5"] && entity.jornadas_semana["5"].horario_saida_prevista || "12:00",visibleWhen:function(v){return v.regime_sabado==="trabalha" && v.sabado_proprio==="true";} },
        { name:"dsr_modo",type:"select",label:"Desconto de DSR",value:entity && entity.politica_dsr ? "falta":"legado",options:[{value:"legado",label:"Preservar regra anterior, sem desconto"},{value:"falta",label:"Descontar por falta injustificada"}],help:"Nos seis dias anteriores ao descanso: uma ou mais faltas injustificadas causam perda de um descanso semanal. Justificadas, atestados, abonos e atrasos não causam perda." },
        { name:"dsr_dia",type:"select",label:"Dia do descanso semanal",value:entity && entity.politica_dsr ? String(entity.politica_dsr.dia_descanso):"6",options:["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"].map(function(d,i){return {value:String(i),label:d};}),visibleWhen:function(v){return v.dsr_modo==="falta";} },
        { name:"dsr_feriados",type:"select",label:"Descontar feriados do período",value:entity && entity.politica_dsr && entity.politica_dsr.descontar_feriados===false ? "false":"true",options:[{value:"true",label:"Sim"},{value:"false",label:"Não"}],visibleWhen:function(v){return v.dsr_modo==="falta";} },
        { name: "tolerancia_atraso_minutos", type: "number", label: "Tolerância de atraso (min)", value: entity ? entity.tolerancia_atraso_minutos : 0, required: true, min: 0, max: 1440, step: 1 },
        { name: "tolerancia_extra_minutos", type: "number", label: "Tolerância de extra (min)", value: entity ? entity.tolerancia_extra_minutos : 0, required: true, min: 0, max: 1440, step: 1 },
        { name: "tolerancia_intervalo_minutos", type: "number", label: "Tolerância de intervalo (min)", value: entity && entity.tolerancia_intervalo_minutos != null ? entity.tolerancia_intervalo_minutos : "", help: "Deixe em branco para usar a mesma tolerância de atraso da escala.", min: 0, max: 1440, step: 1 },
        { name: "usa_banco_horas", type: "select", label: "Banco de horas", value: entity && entity.usa_banco_horas ? "true" : "false", options: [{value:"false",label:"Desabilitado"},{value:"true",label:"Habilitado"}], help: "Configuração anterior: usa o prazo de compensação cadastrado na empresa.", visibleWhen:function(v){return v.politica_modo === "legado";} },
        ...hourPolicyFields(entity),
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
          politica_horas: hourPolicyPayload(values),
          usa_banco_horas: values.politica_modo === "legado" ? values.usa_banco_horas === "true" : values.politica_modo !== "folha",
          ativa: values.ativa === "true",
          tipo_intervalo: values.tipo_intervalo && values.tipo_intervalo!=="legado" ? values.tipo_intervalo:null,
          registro_intervalo: values.tipo_intervalo && values.tipo_intervalo!=="legado" ? values.registro_intervalo:null,
          duracao_intervalo_minutos: values.tipo_intervalo==="sem_intervalo" ? 0 : values.tipo_intervalo && values.tipo_intervalo!=="legado" ? nullableDialogNumber(values.duracao_intervalo_minutos):null,
          politica_dsr: values.dsr_modo==="falta" ? {versao:1,dia_descanso:Number(values.dsr_dia),descontar_feriados:values.dsr_feriados!=="false",referencia:entity && entity.politica_dsr && entity.politica_dsr.referencia || "Política definida pelo operador"}:null,
        };
        if (values.tipo_intervalo && values.tipo_intervalo!=="legado") {
          payload.horario_saida_almoco_prevista = values.tipo_intervalo==="sem_intervalo" ? null:values.horario_saida_almoco_prevista || null;
          payload.horario_retorno_almoco_prevista = values.tipo_intervalo==="sem_intervalo" ? null:values.horario_retorno_almoco_prevista || null;
        }
        if (values.sabado_proprio!==undefined) {
          payload.jornadas_semana=Object.assign({},entity && entity.jornadas_semana || {});
          if (values.sabado_proprio==="true") {
            payload.jornadas_semana["5"]={jornada_minutos:dialogTimeMinutes(values.sabado_saida)-dialogTimeMinutes(values.sabado_entrada),horario_entrada_prevista:values.sabado_entrada,horario_saida_prevista:values.sabado_saida,tipo_intervalo:"sem_intervalo",registro_intervalo:"batidas",duracao_intervalo_minutos:0};
          } else if (values.sabado_proprio==="false") delete payload.jornadas_semana["5"];
        }
        if (values.vigente_desde) payload.vigente_desde = values.vigente_desde;
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
      { name: "nome", type: "text", label: "Nome original no ponto", value: entity ? entity.nome || entity.name : "", required: true, maxlength: 180, autocomplete: "name" },
      { name: "codigo", type: "text", label: "Código original no ponto", value: entity ? entity.codigo || "" : "", required: true, maxlength: 50, autocomplete: "off" },
      { name: "nome_exibicao", type: "text", label: "Nome de exibição no OnPonto", value: entity && entity.nome_exibicao || "", maxlength: 180, help: "Opcional. Vazio usa o nome original." },
      { name: "codigo_exibicao", type: "text", label: "ID de exibição no OnPonto", value: entity && entity.codigo_exibicao || "", maxlength: 50, help: "Opcional. Não vincula registros de importação." },
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
            String(employee.codigo || "").trim() === code;
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
          nome_exibicao: String(values.nome_exibicao || "").trim() || null,
          codigo_exibicao: String(values.codigo_exibicao || "").trim() || null,
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
    if (action === "tentar-conexao-api") {
      event.preventDefault();
      return conectarApi();
    }
    if (state.apiMode === "indisponivel") return;

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
    if (action === "search-companies" || action === "search-employees") return;
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
    if (action === "next-problem-employee") return moveToProblemEmployee();
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
    if (action === "initialize-calendar") {
      var calendarCompetenceId = state.selectedCompetenceId;
      return showDialog({title:"Inicializar calendário?", description:"Criar os dias ausentes dos vínculos conhecidos nesta competência para conferência manual. Marcações existentes serão preservadas.", confirmLabel:"Inicializar", onConfirm:function(){return apiRequest("/competencias/"+calendarCompetenceId+"/inicializar-calendario",{method:"POST"}).then(function(){return loadCompetenceData(calendarCompetenceId,{force:true,summaryForce:true});}).then(function(){render();});}});
    }
    if (action === "resume-import") return resumeImport(element.dataset.fileId);
    if (action === "discard-original-punch") return discardOriginalPunch(element.dataset.dayId, Number(element.dataset.punchIndex));
    if (action === "restore-original-punch") return restoreOriginalPunch(element.dataset.dayId, Number(element.dataset.punchIndex));
    if (action === "ignore-import-person") return ignoreImportPerson(element.dataset.fileId, Number(element.dataset.groupIndex));
    if (action === "discard-import-group") return discardImportGroup(element.dataset.fileId, Number(element.dataset.groupIndex));
    if (action === "unignore-import-person") return unignoreImportPerson(asId(element.dataset.ruleId));
    if (action === "discard-import-record") {
      var fileId = element.dataset.fileId, recordId = element.dataset.recordId, competenceId = state.selectedCompetenceId;
      return showDialog({title:"Excluir registro da apuração?", description:"O arquivo original será preservado. Justifique por que este registro não deve compor a competência.", confirmLabel:"Registrar exclusão", fields:[{name:"justificativa", label:"Justificativa", type:"textarea", required:true}],
        onConfirm:function(values){return apiRequest("/importadores/" + fileId + "/descartar-pendencias", {method:"POST",body:{registros_ids:[recordId],justificativa:values.justificativa}}).then(function(){return loadCompetenceData(competenceId,{force:true,summaryForce:true});}).then(function(){render();});}});
    }
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
    if (action === "select-context-company") return switchQuickContext("company", element.value);
    if (action === "select-context-competence") return switchQuickContext("competence", element.value);
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
    if (action === "assign-original-punch") return assignOriginalPunch(element.dataset.dayId, Number(element.dataset.punchIndex), element.value);
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
    var employeeInput = event.target.closest && event.target.closest('[data-action="search-employees"]');
    if (employeeInput) {
      var selectionStart = employeeInput.selectionStart;
      var selectionEnd = employeeInput.selectionEnd;
      state.employeeSearch = employeeInput.value;
      render();
      var replacement = document.querySelector('[data-action="search-employees"]');
      if (replacement) {
        replacement.focus({preventScroll:true});
        if (selectionStart !== null) replacement.setSelectionRange(selectionStart, selectionEnd);
      }
      return;
    }
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
    if (state.apiMode === "indisponivel") return;
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
    // Alt + seta deve abrir/operar o seletor nativo, sem trocar funcionário.
    if (event.altKey && (target.id === "contextCompany" || target.id === "contextCompetence")) return;
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
      if (!editSession || document.activeElement === editSession.input) return;
      // Campo removido por um redesenho: um horário digitado pela metade (ex.: "12")
      // nunca deve ser gravado; o valor salvo continua o anterior.
      if (!editSession.input.isConnected) {
        editSession = null;
        return;
      }
      finishEditing({ move: null });
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
    if (state.apiMode === "indisponivel") {
      render(options);
      return Promise.resolve();
    }
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
    if(state.apiMode==="online" && !(options && options.flushed) &&
        (!optionalIdsEqual(state.selectedCompanyId,route.companyId) || !optionalIdsEqual(state.selectedCompetenceId,route.competenceId)) &&
        (autosaveFlushPromise || Object.keys(pendingDaySaves).length)) {
      var previousHash=routeHash({view:state.route,companyId:state.selectedCompanyId,competenceId:state.selectedCompetenceId});
      if (!state.settings.autosave && Object.keys(pendingDaySaves).length) {
        root.history.replaceState(null,"",previousHash);
        showToast("Salve as alterações antes de mudar de contexto.","warning");
        return Promise.resolve();
      }
      return ensureAutosaveFlushedForLifecycle().then(function(){
        if(sequence===routeLoadSequence) return syncRouteFromLocation(Object.assign({},options,{flushed:true}));
      }).catch(function(error){
        if(sequence===routeLoadSequence) root.history.replaceState(null,"",previousHash);
        showToast("A navegação foi interrompida para preservar suas alterações.","error",error.message);
      });
    }
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
    if (!demonstracaoSolicitada()) render();
    conectarApi().catch(function (error) {
      showToast("Não foi possível carregar esta tela.", "error", error && error.message);
    });
  }

  init();
})(window);
