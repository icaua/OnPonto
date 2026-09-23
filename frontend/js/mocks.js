(function (root) {
  "use strict";

  var QUEEN_ID = 1;
  var QUEEN_JULY_ID = 1001;
  var JULY_YEAR = 2026;
  var JULY_MONTH = 7;
  var IMPORTED_AT = "2026-08-01T09:13:00-03:00";

  function deepFreeze(value, seen) {
    if (value === null || (typeof value !== "object" && typeof value !== "function")) return value;
    var visited = seen || new WeakSet();
    if (visited.has(value)) return value;
    visited.add(value);
    Reflect.ownKeys(value).forEach(function (key) {
      deepFreeze(value[key], visited);
    });
    return Object.freeze(value);
  }

  function clone(value, seen) {
    if (value === null || typeof value !== "object") return value;
    var visited = seen || new WeakMap();
    if (visited.has(value)) return visited.get(value);
    if (value instanceof Date) return new Date(value.getTime());
    var copy = Array.isArray(value) ? [] : {};
    visited.set(value, copy);
    Object.keys(value).forEach(function (key) {
      copy[key] = clone(value[key], visited);
    });
    return copy;
  }

  function pad2(value) {
    return String(value).padStart(2, "0");
  }

  function julyDate(day) {
    return JULY_YEAR + "-" + pad2(JULY_MONTH) + "-" + pad2(day);
  }

  function weekdayInfo(day) {
    var names = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];
    var shortNames = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
    var index = new Date(Date.UTC(JULY_YEAR, JULY_MONTH - 1, day)).getUTCDay();
    return { index: index, name: names[index], short: shortNames[index] };
  }

  function minutesFromTime(value) {
    if (!value) return null;
    var match = String(value).match(/^(\d{1,2}):(\d{2})/);
    if (!match) return null;
    return Number(match[1]) * 60 + Number(match[2]);
  }

  function basicWorkedMinutes(interpretation) {
    if (!interpretation || !interpretation.entry || !interpretation.exit) return null;
    var entry = minutesFromTime(interpretation.entry);
    var exit = minutesFromTime(interpretation.exit);
    if (entry == null || exit == null) return null;
    if (exit < entry) exit += 24 * 60;
    var total = exit - entry;
    if (interpretation.breakStart && interpretation.breakEnd) {
      var breakStart = minutesFromTime(interpretation.breakStart);
      var breakEnd = minutesFromTime(interpretation.breakEnd);
      if (breakStart == null || breakEnd == null || breakEnd < breakStart) return null;
      total -= breakEnd - breakStart;
    }
    return total;
  }

  function makeInterpretation(values) {
    var source = values || {};
    var entry = source.entry != null ? source.entry : source.entrada != null ? source.entrada : null;
    var breakStart = source.breakStart != null ? source.breakStart : source.saidaIntervalo != null ? source.saidaIntervalo : null;
    var breakEnd = source.breakEnd != null ? source.breakEnd : source.retorno != null ? source.retorno : null;
    var exit = source.exit != null ? source.exit : source.saida != null ? source.saida : null;
    return {
      entry: entry,
      breakStart: breakStart,
      breakEnd: breakEnd,
      exit: exit,
      intervalOut: breakStart,
      intervalIn: breakEnd,
      entrada: entry,
      saidaIntervalo: breakStart,
      saida_intervalo: breakStart,
      retorno: breakEnd,
      retornoIntervalo: breakEnd,
      retorno_intervalo: breakEnd,
      saida: exit,
    };
  }

  function makePunchDetails(times, lines, fileId) {
    return times.map(function (time, index) {
      return {
        id: fileId + "-line-" + lines[index],
        time: time,
        horario: time,
        sourceLine: lines[index],
        linhaOrigem: lines[index],
        fileId: fileId,
      };
    });
  }

  var statusDefinitions = [
    { id: "normal", label: "Normal", icon: "✓", tone: "success", requiresReview: false },
    { id: "falta", label: "Falta", icon: "!", tone: "danger", requiresReview: false },
    { id: "atestado", label: "Atestado", icon: "+", tone: "info", requiresReview: false },
    { id: "folga", label: "Folga", icon: "○", tone: "neutral", requiresReview: false },
    { id: "feriado", label: "Feriado", icon: "★", tone: "neutral", requiresReview: false },
    { id: "domingo", label: "Domingo", icon: "○", tone: "muted", requiresReview: false },
    { id: "sem_expediente", label: "Sem expediente", icon: "—", tone: "muted", requiresReview: false },
    { id: "trabalho_externo", label: "Trabalho externo", icon: "↗", tone: "info", requiresReview: false },
    { id: "afastamento", label: "Afastamento", icon: "‖", tone: "neutral", requiresReview: false },
  ];

  var statusById = {};
  statusDefinitions.forEach(function (status) {
    statusById[status.id] = status;
  });

  var companies = [
    {
      id: QUEEN_ID,
      name: "Queen",
      nome: "Queen",
      legalName: "Queen Serviços Administrativos Ltda.",
      cnpj: "12.345.678/0001-90",
      cidade: "São Paulo",
      uf: "SP",
      initials: "QU",
      active: true,
      ativa: true,
      color: "var(--brand-primary)",
    },
    {
      id: 2,
      name: "Jianbin Wu",
      nome: "Jianbin Wu",
      legalName: "Jianbin Wu Comércio de Alimentos Ltda.",
      cnpj: "23.456.789/0001-01",
      cidade: "São Paulo",
      uf: "SP",
      initials: "JW",
      active: true,
      ativa: true,
      color: "var(--brand-primary)",
    },
    {
      id: 3,
      name: "Empresa Exemplo",
      nome: "Empresa Exemplo",
      legalName: "Empresa Exemplo Tecnologia Ltda.",
      cnpj: "34.567.890/0001-12",
      cidade: "Campinas",
      uf: "SP",
      initials: "EE",
      active: true,
      ativa: true,
      color: "var(--brand-primary)",
    },
    {
      id: 4,
      name: "Loja Modelo",
      nome: "Loja Modelo",
      legalName: "Loja Modelo Varejo Ltda.",
      cnpj: "45.678.901/0001-23",
      cidade: "Santos",
      uf: "SP",
      initials: "LM",
      active: true,
      ativa: true,
      color: "var(--brand-primary)",
    },
  ];

  var scales = [
    {
      id: 10001, empresa_id: 1, companyId: 1, nome: "Comercial 44h", name: "Comercial 44h",
      modo_apuracao: "carga_horaria", jornada_seg_sex_horas: 8, jornada_sabado_horas: 4,
      horario_entrada_prevista: null, horario_saida_almoco_prevista: null,
      horario_retorno_almoco_prevista: null, horario_saida_prevista: null,
      regime_sabado: "trabalha", regime_domingo: "nao_trabalha",
      tolerancia_atraso_minutos: 10, tolerancia_extra_minutos: 10,
      tolerancia_intervalo_minutos: 10, ativa: true, active: true,
    },
    {
      id: 10002, empresa_id: 2, companyId: 2, nome: "Administrativo", name: "Administrativo",
      modo_apuracao: "horario_fixo", jornada_seg_sex_horas: null, jornada_sabado_horas: null,
      horario_entrada_prevista: "08:00", horario_saida_almoco_prevista: "12:00",
      horario_retorno_almoco_prevista: "13:00", horario_saida_prevista: "17:00",
      regime_sabado: "nao_trabalha", regime_domingo: "nao_trabalha",
      tolerancia_atraso_minutos: 10, tolerancia_extra_minutos: 10,
      tolerancia_intervalo_minutos: 10, ativa: true, active: true,
    },
    {
      id: 10003, empresa_id: 3, companyId: 3, nome: "Segunda a sexta", name: "Segunda a sexta",
      modo_apuracao: "carga_horaria", jornada_seg_sex_horas: 8, jornada_sabado_horas: null,
      horario_entrada_prevista: null, horario_saida_almoco_prevista: null,
      horario_retorno_almoco_prevista: null, horario_saida_prevista: null,
      regime_sabado: "compensado", regime_domingo: "nao_trabalha",
      tolerancia_atraso_minutos: 0, tolerancia_extra_minutos: 0,
      tolerancia_intervalo_minutos: 0, ativa: true, active: true,
    },
    {
      id: 10004, empresa_id: 4, companyId: 4, nome: "Varejo", name: "Varejo",
      modo_apuracao: "carga_horaria", jornada_seg_sex_horas: 7.33, jornada_sabado_horas: 6,
      horario_entrada_prevista: null, horario_saida_almoco_prevista: null,
      horario_retorno_almoco_prevista: null, horario_saida_prevista: null,
      regime_sabado: "trabalha", regime_domingo: "nao_trabalha",
      tolerancia_atraso_minutos: 5, tolerancia_extra_minutos: 5,
      tolerancia_intervalo_minutos: 5, ativa: true, active: true,
    },
  ];

  var competencies = [
    {
      id: QUEEN_JULY_ID,
      companyId: QUEEN_ID,
      empresa_id: QUEEN_ID,
      month: 7,
      mes: 7,
      year: 2026,
      ano: 2026,
      label: "07/2026",
      status: "em_conferencia",
      statusLabel: "Em conferência",
      employeeCount: 8,
      pendingCount: 12,
      fileCount: 3,
      progress: 73,
      confirmedEmployees: 5,
      pendingEmployees: 3,
      inconsistentDays: 9,
      receivedAt: "2026-08-01T09:13:00-03:00",
      updatedAt: "2026-08-01T14:25:00-03:00",
      closedAt: null,
    },
    {
      id: 1000,
      companyId: QUEEN_ID,
      empresa_id: QUEEN_ID,
      month: 6,
      mes: 6,
      year: 2026,
      ano: 2026,
      label: "06/2026",
      status: "fechada",
      statusLabel: "Fechada",
      employeeCount: 8,
      pendingCount: 0,
      fileCount: 2,
      progress: 100,
      confirmedEmployees: 8,
      pendingEmployees: 0,
      inconsistentDays: 0,
      receivedAt: "2026-07-01T08:42:00-03:00",
      updatedAt: "2026-07-05T17:30:00-03:00",
      closedAt: "2026-07-05T17:30:00-03:00",
    },
    {
      id: 2001,
      companyId: 2,
      empresa_id: 2,
      month: 7,
      mes: 7,
      year: 2026,
      ano: 2026,
      label: "07/2026",
      status: "aberta",
      statusLabel: "Aberta",
      employeeCount: 5,
      pendingCount: 4,
      fileCount: 1,
      progress: 28,
      confirmedEmployees: 1,
      pendingEmployees: 4,
      inconsistentDays: 3,
      receivedAt: "2026-08-01T10:08:00-03:00",
      updatedAt: "2026-08-01T10:22:00-03:00",
      closedAt: null,
    },
    {
      id: 3001,
      companyId: 3,
      empresa_id: 3,
      month: 7,
      mes: 7,
      year: 2026,
      ano: 2026,
      label: "07/2026",
      status: "em_conferencia",
      statusLabel: "Em conferência",
      employeeCount: 3,
      pendingCount: 2,
      fileCount: 2,
      progress: 61,
      confirmedEmployees: 1,
      pendingEmployees: 2,
      inconsistentDays: 2,
      receivedAt: "2026-07-31T16:20:00-03:00",
      updatedAt: "2026-08-01T11:47:00-03:00",
      closedAt: null,
    },
    {
      id: 4001,
      companyId: 4,
      empresa_id: 4,
      month: 7,
      mes: 7,
      year: 2026,
      ano: 2026,
      label: "07/2026",
      status: "fechada",
      statusLabel: "Fechada",
      employeeCount: 6,
      pendingCount: 0,
      fileCount: 1,
      progress: 100,
      confirmedEmployees: 6,
      pendingEmployees: 0,
      inconsistentDays: 0,
      receivedAt: "2026-07-29T14:04:00-03:00",
      updatedAt: "2026-08-01T08:10:00-03:00",
      closedAt: "2026-08-01T08:10:00-03:00",
    },
  ];

  var employees = [
    { id: 101, companyId: 1, empresa_id: 1, escala_id: 10001, scaleId: 10001, code: "Q001", codigo: "Q001", name: "André Luiz", nome: "André Luiz", role: "Assistente administrativo", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 102, companyId: 1, empresa_id: 1, escala_id: 10001, scaleId: 10001, code: "Q002", codigo: "Q002", name: "Beatriz Costa", nome: "Beatriz Costa", role: "Analista financeiro", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 103, companyId: 1, empresa_id: 1, escala_id: 10001, scaleId: 10001, code: "Q003", codigo: "Q003", name: "Lana Fernanda", nome: "Lana Fernanda", role: "Coordenadora operacional", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 104, companyId: 1, empresa_id: 1, escala_id: 10001, scaleId: 10001, code: "Q004", codigo: "Q004", name: "Carlos Henrique", nome: "Carlos Henrique", role: "Auxiliar de logística", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 105, companyId: 1, empresa_id: 1, escala_id: 10001, scaleId: 10001, code: "Q005", codigo: "Q005", name: "Débora Almeida", nome: "Débora Almeida", role: "Supervisora de atendimento", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 106, companyId: 1, empresa_id: 1, escala_id: 10001, scaleId: 10001, code: "Q006", codigo: "Q006", name: "Eduardo Martins", nome: "Eduardo Martins", role: "Assistente comercial", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 107, companyId: 1, empresa_id: 1, escala_id: 10001, scaleId: 10001, code: "Q007", codigo: "Q007", name: "Fernanda Rocha", nome: "Fernanda Rocha", role: "Analista de cadastro", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 108, companyId: 1, empresa_id: 1, escala_id: 10001, scaleId: 10001, code: "Q008", codigo: "Q008", name: "Gustavo Nunes", nome: "Gustavo Nunes", role: "Auxiliar administrativo", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 201, companyId: 2, empresa_id: 2, escala_id: 10002, scaleId: 10002, code: "JW01", codigo: "JW01", name: "Marina Wu", nome: "Marina Wu", role: "Atendimento", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 240 },
    { id: 301, companyId: 3, empresa_id: 3, escala_id: 10003, scaleId: 10003, code: "EX01", codigo: "EX01", name: "Paulo Mendes", nome: "Paulo Mendes", role: "Desenvolvedor", active: true, expectedWeekdayMinutes: 480, expectedSaturdayMinutes: 0 },
    { id: 401, companyId: 4, empresa_id: 4, escala_id: 10004, scaleId: 10004, code: "LM01", codigo: "LM01", name: "Sofia Ribeiro", nome: "Sofia Ribeiro", role: "Vendedora", active: true, expectedWeekdayMinutes: 440, expectedSaturdayMinutes: 360 },
  ];

  var files = [
    {
      id: "file-queen-txt",
      companyId: 1,
      competenceId: QUEEN_JULY_ID,
      name: "ALOG_001.txt",
      nome: "ALOG_001.txt",
      extension: "txt",
      sourceType: "txt_clock",
      typeLabel: "TXT de relógio",
      detectedFormat: "TXT AFD",
      mimeType: "text/plain",
      sizeBytes: 184320,
      uploadedAt: IMPORTED_AT,
      analyzedAt: "2026-08-01T09:14:12-03:00",
      status: "analisado",
      employeeCount: 8,
      punchCount: 742,
      dayCount: 31,
      pendingCount: 12,
      originalAvailable: true,
    },
    {
      id: "file-queen-xls",
      companyId: 1,
      competenceId: QUEEN_JULY_ID,
      name: "Folha_Ponto_Queen_Jul2026.xls",
      nome: "Folha_Ponto_Queen_Jul2026.xls",
      extension: "xls",
      sourceType: "xls_legacy",
      typeLabel: "XLS legado",
      detectedFormat: "Microsoft Excel 97–2003",
      mimeType: "application/vnd.ms-excel",
      sizeBytes: 97280,
      uploadedAt: "2026-08-01T09:31:00-03:00",
      analyzedAt: "2026-08-01T09:31:48-03:00",
      status: "analisado",
      employeeCount: 8,
      punchCount: 719,
      dayCount: 31,
      pendingCount: 7,
      originalAvailable: true,
    },
    {
      id: "file-queen-image",
      companyId: 1,
      competenceId: QUEEN_JULY_ID,
      name: "espelho_ponto_lana_julho.jpg",
      nome: "espelho_ponto_lana_julho.jpg",
      extension: "jpg",
      sourceType: "scanned_image",
      typeLabel: "Imagem escaneada",
      detectedFormat: "Imagem JPEG",
      mimeType: "image/jpeg",
      sizeBytes: 2480128,
      uploadedAt: "2026-08-01T10:02:00-03:00",
      analyzedAt: "2026-08-01T10:03:25-03:00",
      status: "leitura_sugerida",
      employeeCount: 1,
      punchCount: 82,
      dayCount: 24,
      pendingCount: 5,
      originalAvailable: true,
    },
    {
      id: "file-jianbin-xlsx",
      companyId: 2,
      competenceId: 2001,
      name: "Ponto_Jianbin_07-2026.xlsx",
      nome: "Ponto_Jianbin_07-2026.xlsx",
      extension: "xlsx",
      sourceType: "xlsx",
      typeLabel: "XLSX",
      detectedFormat: "Microsoft Excel XLSX",
      mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      sizeBytes: 126976,
      uploadedAt: "2026-08-01T10:08:00-03:00",
      analyzedAt: "2026-08-01T10:09:04-03:00",
      status: "analisado",
      employeeCount: 5,
      punchCount: 431,
      dayCount: 31,
      pendingCount: 4,
      originalAvailable: true,
    },
  ];

  function makeIssue(dayId, issue, index) {
    var item = typeof issue === "string" ? { message: issue } : issue;
    return {
      id: item.id || "issue-" + dayId + "-" + (index + 1),
      dayId: dayId,
      type: item.type || "review",
      severity: item.severity || "warning",
      message: item.message,
      resolved: item.resolved === true,
      resolution: item.resolution || null,
    };
  }

  function makeDay(employee, configuration) {
    var config = configuration || {};
    var day = config.day;
    var date = julyDate(day);
    var weekday = weekdayInfo(day);
    var id = "day-" + employee.id + "-" + date;
    var originalPunches = (config.originalPunches || []).slice();
    var sourceLines = (config.sourceLines || originalPunches.map(function (_, index) {
      return day * 10 + index + employee.id;
    })).slice();
    var suggestion = makeInterpretation(config.suggestion);
    var userEdition = config.userEdition ? {
      values: makeInterpretation(config.userEdition.values || config.userEdition),
      changedFields: (config.userEdition.changedFields || []).slice(),
      author: config.userEdition.author || "Marina Souza",
      changedAt: config.userEdition.changedAt || "2026-08-01T14:20:00-03:00",
      reason: config.userEdition.reason || "Ajuste manual durante a conferência.",
    } : null;
    var currentInterpretation = makeInterpretation(userEdition ? userEdition.values : suggestion);
    var confirmed = config.confirmed === true;
    var confirmedResult = confirmed ? makeInterpretation(currentInterpretation) : null;
    var expectedMinutes = Object.prototype.hasOwnProperty.call(config, "expectedMinutes")
      ? config.expectedMinutes
      : weekday.index === 6 ? employee.expectedSaturdayMinutes : weekday.index === 0 ? 0 : employee.expectedWeekdayMinutes;
    var workedMinutes = Object.prototype.hasOwnProperty.call(config, "workedMinutes")
      ? config.workedMinutes
      : basicWorkedMinutes(currentInterpretation);
    var balanceMinutes = Object.prototype.hasOwnProperty.call(config, "balanceMinutes")
      ? config.balanceMinutes
      : workedMinutes == null || expectedMinutes == null ? null : workedMinutes - expectedMinutes;
    var fileId = config.fileId || "file-queen-txt";
    var file = files.find(function (candidate) { return candidate.id === fileId; }) || files[0];
    var issues = (config.issues || []).map(function (issue, index) {
      return makeIssue(id, issue, index);
    });
    var history = (config.history || []).slice();

    if (!history.length) {
      history.push({
        id: "history-import-" + id,
        at: IMPORTED_AT,
        timeLabel: "09:13",
        type: "imported",
        actor: "Sistema",
        description: "Batidas importadas de " + file.name + ".",
      });
      if (confirmed) {
        history.push({
          id: "history-confirm-" + id,
          at: "2026-08-01T14:25:00-03:00",
          timeLabel: "14:25",
          type: "confirmed",
          actor: "Marina Souza",
          description: "Dia marcado como conferido.",
        });
      }
    }

    var status = config.status || (weekday.index === 0 ? "domingo" : "normal");
    var statusDefinition = statusById[status] || statusById.normal;
    var punchDetails = makePunchDetails(originalPunches, sourceLines, fileId);
    var source = {
      fileId: fileId,
      fileName: file.name,
      arquivo: file.name,
      format: file.detectedFormat,
      importedAt: file.uploadedAt,
      sourceLines: sourceLines,
      linhasOrigem: sourceLines,
      region: config.sourceRegion || (file.sourceType === "scanned_image" ? "Página 1, linhas " + day + "–" + (day + 1) : null),
      canOpenOriginal: true,
      canOpenRegion: true,
    };
    var original = {
      punches: originalPunches,
      punchDetails: punchDetails,
      source: source,
    };
    var review = {
      state: confirmed ? "confirmed" : userEdition ? "edited" : "suggested",
      status: status,
      statusLabel: statusDefinition.label,
      confirmed: confirmed,
      issues: issues,
      observation: config.observation || "",
    };

    return {
      id: id,
      companyId: QUEEN_ID,
      empresa_id: QUEEN_ID,
      competenceId: QUEEN_JULY_ID,
      competencia_id: QUEEN_JULY_ID,
      employeeId: employee.id,
      funcionario_id: employee.id,
      employeeName: employee.name,
      funcionario: employee.name,
      date: date,
      data: date,
      day: day,
      weekday: weekday.name,
      weekdayShort: weekday.short,
      isSaturday: weekday.index === 6,
      isSunday: weekday.index === 0,
      originalPunches: originalPunches,
      batidasOriginais: originalPunches,
      originalPunchDetails: punchDetails,
      original: original,
      suggestion: suggestion,
      suggested: suggestion,
      interpretacaoSugerida: suggestion,
      userEdition: userEdition,
      edited: userEdition,
      edicaoUsuario: userEdition,
      currentInterpretation: currentInterpretation,
      current: currentInterpretation,
      interpretacaoAtual: currentInterpretation,
      confirmedResult: confirmedResult,
      resultadoConferido: confirmedResult,
      reviewState: confirmed ? "confirmed" : userEdition ? "edited" : "suggested",
      confirmed: confirmed,
      conferido: confirmed,
      confirmedAt: confirmed ? config.confirmedAt || "2026-08-01T14:25:00-03:00" : null,
      status: status,
      statusLabel: statusDefinition.label,
      statusIcon: statusDefinition.icon,
      statusTone: statusDefinition.tone,
      caseTags: (config.caseTags || []).slice(),
      expectedMinutes: expectedMinutes,
      jornadaPrevistaMinutos: expectedMinutes,
      workedMinutes: workedMinutes,
      jornadaApuradaMinutos: workedMinutes,
      balanceMinutes: balanceMinutes,
      saldoMinutos: balanceMinutes,
      differenceReason: config.differenceReason || "",
      motivoDiferenca: config.differenceReason || "",
      observation: config.observation || "",
      observacao: config.observation || "",
      issues: issues,
      pendencias: issues,
      review: review,
      source: source,
      origem: source,
      history: history,
      historico: history,
      autosaveStatus: "saved",
    };
  }

  var lana = employees.find(function (employee) { return employee.id === 103; });
  var lanaDayConfigurations = [
    { day: 1, originalPunches: ["08:03:17", "14:22:59", "15:27:54", "17:08:23"], sourceLines: [32, 46, 49, 55], suggestion: { entry: "08:03", breakStart: "14:22", breakEnd: "15:27", exit: "17:08" }, status: "normal", caseTags: ["intervalo_fora_do_padrao"], expectedMinutes: 480, workedMinutes: 480, balanceMinutes: 0, issues: [{ type: "interval", message: "Intervalo iniciado fora do padrão esperado." }], observation: "O sistema manteve as quatro batidas originais para revisão.", confirmed: false },
    { day: 2, originalPunches: ["08:03:09", "13:46:41", "14:44:02", "17:12:11"], suggestion: { entry: "08:03", breakStart: "13:46", breakEnd: "14:44", exit: "17:12" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 489, balanceMinutes: 9, differenceReason: "Pequena variação positiva dentro da política configurada.", confirmed: true },
    { day: 3, originalPunches: ["07:56:12", "13:02:04", "14:03:18", "17:04:37"], suggestion: { entry: "07:56", breakStart: "13:02", breakEnd: "14:03", exit: "17:04" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 487, balanceMinutes: 7, confirmed: true },
    { day: 4, originalPunches: ["07:54:28", "13:04:52"], suggestion: { entry: "07:54", exit: "13:04" }, status: "normal", caseTags: ["sabado", "hora_extra"], expectedMinutes: 240, workedMinutes: 310, balanceMinutes: 70, issues: [{ type: "overtime", message: "Jornada de sábado excedeu a previsão em 1h10." }], differenceReason: "Permanência após o horário previsto de sábado.", confirmed: false },
    { day: 5, originalPunches: [], suggestion: {}, status: "domingo", caseTags: ["domingo"], expectedMinutes: 0, workedMinutes: null, balanceMinutes: null, observation: "Domingo sem expediente.", confirmed: true },
    { day: 6, originalPunches: ["08:27:03", "12:00:18", "13:00:42", "17:00:11"], suggestion: { entry: "08:27", breakStart: "12:00", breakEnd: "13:00", exit: "17:00" }, status: "normal", caseTags: ["atraso"], expectedMinutes: 480, workedMinutes: 453, balanceMinutes: -27, differenceReason: "Entrada 27 minutos após o horário previsto; ocorrência aceita na conferência.", observation: "Atraso informado pela gestora.", confirmed: true },
    { day: 7, originalPunches: ["07:48:08", "12:03:30", "13:01:12", "17:58:44"], suggestion: { entry: "07:48", breakStart: "12:03", breakEnd: "13:01", exit: "17:58" }, status: "normal", caseTags: ["hora_extra"], expectedMinutes: 480, workedMinutes: 552, balanceMinutes: 72, differenceReason: "Atendimento excepcional após o expediente.", confirmed: true },
    { day: 8, originalPunches: ["08:02:14", "12:01:06", "13:04:55"], suggestion: { entry: "08:02", breakStart: "12:01", breakEnd: "13:04", exit: null }, status: "normal", caseTags: ["incompleta", "tres_batidas"], expectedMinutes: 480, workedMinutes: null, balanceMinutes: null, issues: [{ type: "missing_punch", severity: "danger", message: "Apenas três batidas encontradas." }, { type: "missing_exit", severity: "danger", message: "Saída final não identificada." }], observation: "Aguardando confirmação do cliente.", confirmed: false },
    { day: 9, originalPunches: ["08:00:02", "10:15:09", "10:22:44", "12:00:10", "13:00:21", "17:06:39"], suggestion: { entry: "08:00", breakStart: "12:00", breakEnd: "13:00", exit: "17:06" }, status: "normal", caseTags: ["mais_de_quatro_batidas"], expectedMinutes: 480, workedMinutes: 486, balanceMinutes: 6, issues: [{ type: "extra_punches", message: "Mais de quatro batidas encontradas; duas marcações intermediárias não foram usadas na sugestão." }], observation: "Batidas das 10:15 e 10:22 permanecem preservadas no original.", confirmed: false },
    { day: 10, originalPunches: ["08:01:08", "12:04:37", "13:02:22", "17:06:05"], suggestion: { entry: "08:01", breakStart: "12:04", breakEnd: "13:02", exit: "17:06" }, userEdition: { values: { entry: "08:01", breakStart: "12:04", breakEnd: "13:02", exit: "17:08" }, changedFields: ["exit"], author: "Marina Souza", changedAt: "2026-08-01T14:20:00-03:00", reason: "Saída confirmada no espelho assinado." }, status: "normal", caseTags: ["alteracao_manual"], expectedMinutes: 480, workedMinutes: 489, balanceMinutes: 9, issues: [{ type: "manual_change", message: "Horário alterado manualmente.", resolved: true, resolution: "Saída confirmada no espelho assinado." }], history: [{ id: "history-10-import", at: IMPORTED_AT, timeLabel: "09:13", type: "imported", actor: "Sistema", description: "Batidas importadas de ALOG_001.txt." }, { id: "history-10-edit", at: "2026-08-01T14:20:00-03:00", timeLabel: "14:20", type: "edited", actor: "Marina Souza", description: "Saída alterada de 17:06 para 17:08." }, { id: "history-10-review", at: "2026-08-01T14:21:00-03:00", timeLabel: "14:21", type: "review", actor: "Marina Souza", description: "Dia marcado para conferência." }, { id: "history-10-confirm", at: "2026-08-01T14:25:00-03:00", timeLabel: "14:25", type: "confirmed", actor: "Marina Souza", description: "Dia marcado como conferido." }], confirmed: true },
    { day: 11, originalPunches: [], suggestion: {}, status: "folga", caseTags: ["sabado", "folga"], expectedMinutes: 0, workedMinutes: 0, balanceMinutes: 0, observation: "Folga compensatória registrada.", confirmed: true },
    { day: 12, originalPunches: [], suggestion: {}, status: "domingo", caseTags: ["domingo"], expectedMinutes: 0, workedMinutes: null, balanceMinutes: null, confirmed: true },
    { day: 13, originalPunches: [], suggestion: {}, status: "falta", caseTags: ["falta"], expectedMinutes: 480, workedMinutes: 0, balanceMinutes: -480, differenceReason: "Ausência sem marcações registrada como falta.", observation: "Falta confirmada pelo cliente.", confirmed: true },
    { day: 14, originalPunches: [], suggestion: {}, status: "atestado", caseTags: ["atestado"], expectedMinutes: 480, workedMinutes: 480, balanceMinutes: 0, differenceReason: "Jornada abonada por atestado médico.", observation: "Atestado recebido em 31/07/2026.", confirmed: true },
    { day: 15, originalPunches: [], suggestion: {}, status: "folga", caseTags: ["folga"], expectedMinutes: 0, workedMinutes: 0, balanceMinutes: 0, observation: "Folga programada.", confirmed: true },
    { day: 16, originalPunches: [], suggestion: {}, status: "feriado", caseTags: ["feriado"], expectedMinutes: 0, workedMinutes: 0, balanceMinutes: 0, observation: "Feriado municipal cadastrado para demonstração.", confirmed: true },
    { day: 17, originalPunches: [], suggestion: {}, status: "sem_expediente", caseTags: ["sem_expediente"], expectedMinutes: 0, workedMinutes: null, balanceMinutes: null, observation: "Unidade sem expediente nesta data.", confirmed: false },
    { day: 18, originalPunches: ["08:10:14", "12:12:31"], suggestion: { entry: "08:10", exit: "12:12" }, status: "trabalho_externo", caseTags: ["sabado", "externo"], expectedMinutes: 240, workedMinutes: 242, balanceMinutes: 2, differenceReason: "Atendimento externo em cliente.", confirmed: true },
    { day: 19, originalPunches: [], suggestion: {}, status: "domingo", caseTags: ["domingo"], expectedMinutes: 0, workedMinutes: null, balanceMinutes: null, confirmed: true },
    { day: 20, originalPunches: [], suggestion: {}, status: "afastamento", caseTags: ["afastamento"], expectedMinutes: 0, workedMinutes: 0, balanceMinutes: 0, observation: "Afastamento previamente informado.", confirmed: true },
    { day: 21, originalPunches: ["08:00:18", "12:01:09", "13:00:45", "16:59:57"], suggestion: { entry: "08:00", breakStart: "12:01", breakEnd: "13:00", exit: "16:59" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 480, balanceMinutes: 0, confirmed: true },
    { day: 22, originalPunches: ["07:59:49", "12:03:21", "13:01:18", "16:58:51"], suggestion: { entry: "07:59", breakStart: "12:03", breakEnd: "13:01", exit: "16:58" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 481, balanceMinutes: 1, confirmed: true },
    { day: 23, originalPunches: ["08:04:02", "12:02:47", "13:02:04", "17:04:12"], suggestion: { entry: "08:04", breakStart: "12:02", breakEnd: "13:02", exit: "17:04" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 480, balanceMinutes: 0, confirmed: true },
    { day: 24, originalPunches: ["07:42:17", "12:00:08", "13:01:33", "18:06:45"], suggestion: { entry: "07:42", breakStart: "12:00", breakEnd: "13:01", exit: "18:06" }, status: "normal", caseTags: ["hora_extra"], expectedMinutes: 480, workedMinutes: 563, balanceMinutes: 83, differenceReason: "Fechamento mensal realizado após o expediente.", confirmed: true },
    { day: 25, originalPunches: ["08:01:19", "12:03:12"], suggestion: { entry: "08:01", exit: "12:03" }, status: "normal", caseTags: ["sabado"], expectedMinutes: 240, workedMinutes: 242, balanceMinutes: 2, confirmed: true },
    { day: 26, originalPunches: [], suggestion: {}, status: "domingo", caseTags: ["domingo"], expectedMinutes: 0, workedMinutes: null, balanceMinutes: null, confirmed: true },
    { day: 27, originalPunches: ["08:02:03", "12:01:42", "13:00:29", "17:01:11"], suggestion: { entry: "08:02", breakStart: "12:01", breakEnd: "13:00", exit: "17:01" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 480, balanceMinutes: 0, confirmed: true },
    { day: 28, originalPunches: ["03:00:11", "07:02:49", "08:01:14", "12:03:33"], suggestion: { entry: "03:00", breakStart: "07:02", breakEnd: "08:01", exit: "12:03" }, status: "trabalho_externo", caseTags: ["horario_incomum", "externo"], expectedMinutes: 480, workedMinutes: 484, balanceMinutes: 4, issues: [{ type: "unusual_time", message: "Horário incomum de 03:00 confirmado para trabalho externo.", resolved: true, resolution: "Escala especial confirmada pelo cliente." }], differenceReason: "Escala externa iniciada durante a madrugada.", confirmed: true },
    { day: 29, originalPunches: ["08:00:03", "12:00:31", "13:00:20", "17:00:51"], suggestion: { entry: "08:00", breakStart: "12:00", breakEnd: "13:00", exit: "17:00" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 480, balanceMinutes: 0, confirmed: true },
    { day: 30, originalPunches: ["08:06:04", "12:04:39", "13:02:18", "17:08:22"], suggestion: { entry: "08:06", breakStart: "12:04", breakEnd: "13:02", exit: "17:08" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 484, balanceMinutes: 4, confirmed: true },
    { day: 31, originalPunches: ["08:01:36", "12:00:52", "13:00:09", "17:02:44"], suggestion: { entry: "08:01", breakStart: "12:00", breakEnd: "13:00", exit: "17:02" }, status: "normal", caseTags: ["normal"], expectedMinutes: 480, workedMinutes: 481, balanceMinutes: 1, confirmed: true },
  ];

  var lanaDays = lanaDayConfigurations.map(function (configuration) {
    return makeDay(lana, configuration);
  });

  function generatedConfiguration(employee, day, employeeIndex) {
    var weekday = weekdayInfo(day);
    if (weekday.index === 0) {
      return { day: day, originalPunches: [], suggestion: {}, status: "domingo", caseTags: ["domingo"], expectedMinutes: 0, workedMinutes: null, balanceMinutes: null, confirmed: true };
    }

    if (weekday.index === 6) {
      var saturdayEntryMinute = (employeeIndex + day) % 6;
      return {
        day: day,
        originalPunches: ["08:" + pad2(saturdayEntryMinute) + ":12", "12:" + pad2(saturdayEntryMinute + 1) + ":31"],
        suggestion: { entry: "08:" + pad2(saturdayEntryMinute), exit: "12:" + pad2(saturdayEntryMinute + 1) },
        status: "normal",
        caseTags: ["sabado"],
        expectedMinutes: 240,
        workedMinutes: 241,
        balanceMinutes: 1,
        confirmed: true,
      };
    }

    var entryMinute = (employeeIndex * 2 + day) % 7;
    var exitMinute = (entryMinute + (day % 3)) % 10;
    var pendingDemoDays = [8, 9, 10, 13, 14, 15, 16];
    var isPendingDemo = day === pendingDemoDays[employeeIndex] || (employeeIndex === 0 && day === 22);
    if (isPendingDemo) {
      return {
        day: day,
        originalPunches: ["08:" + pad2(entryMinute) + ":11", "12:00:24", "13:00:08"],
        suggestion: { entry: "08:" + pad2(entryMinute), breakStart: "12:00", breakEnd: "13:00", exit: null },
        status: "normal",
        caseTags: ["incompleta"],
        issues: [{ type: "missing_exit", severity: "danger", message: "Saída final não identificada." }],
        expectedMinutes: 480,
        workedMinutes: null,
        balanceMinutes: null,
        confirmed: false,
      };
    }

    return {
      day: day,
      originalPunches: ["08:" + pad2(entryMinute) + ":11", "12:00:24", "13:00:08", "17:" + pad2(exitMinute) + ":42"],
      suggestion: { entry: "08:" + pad2(entryMinute), breakStart: "12:00", breakEnd: "13:00", exit: "17:" + pad2(exitMinute) },
      status: "normal",
      caseTags: ["normal"],
      expectedMinutes: 480,
      workedMinutes: 480 + exitMinute - entryMinute,
      balanceMinutes: exitMinute - entryMinute,
      confirmed: true,
    };
  }

  var generatedQueenDays = [];
  employees.filter(function (employee) { return employee.companyId === QUEEN_ID && employee.id !== lana.id; }).forEach(function (employee, employeeIndex) {
    for (var day = 1; day <= 31; day += 1) {
      generatedQueenDays.push(makeDay(employee, generatedConfiguration(employee, day, employeeIndex)));
    }
  });

  var attendanceDays = lanaDays.concat(generatedQueenDays).sort(function (left, right) {
    if (left.employeeId !== right.employeeId) return left.employeeId - right.employeeId;
    return left.date.localeCompare(right.date);
  });

  var pendingIssues = [];
  attendanceDays.forEach(function (day) {
    day.issues.forEach(function (issue) {
      pendingIssues.push({
        id: issue.id,
        dayId: day.id,
        employeeId: day.employeeId,
        employeeName: day.employeeName,
        date: day.date,
        status: day.status,
        type: issue.type,
        severity: issue.severity,
        message: issue.message,
        resolved: issue.resolved,
        resolution: issue.resolution,
      });
    });
  });

  var employeeProgress = employees.filter(function (employee) { return employee.companyId === QUEEN_ID; }).map(function (employee, index) {
    var days = attendanceDays.filter(function (day) { return day.employeeId === employee.id; });
    var eligible = days.filter(function (day) { return day.status !== "domingo" && day.status !== "sem_expediente"; });
    var confirmed = eligible.filter(function (day) { return day.confirmed; }).length;
    var pending = days.reduce(function (total, day) {
      return total + day.issues.filter(function (issue) { return !issue.resolved; }).length;
    }, 0);
    return {
      employeeId: employee.id,
      employeeName: employee.name,
      position: index + 1,
      totalEmployees: 8,
      eligibleDayCount: employee.id === 103 ? 26 : eligible.length,
      confirmedDayCount: employee.id === 103 ? 22 : confirmed,
      pendingCount: pending,
      progress: employee.id === 103 ? 85 : eligible.length ? Math.round((confirmed / eligible.length) * 100) : 0,
      state: pending ? "com_pendencias" : "conferido",
    };
  });

  var importPreviewRows = attendanceDays.map(function (day) {
    var values = day.suggestion;
    var suggestedParts = [values.entry, values.breakStart, values.breakEnd, values.exit].map(function (value) {
      return value || "—";
    });
    return {
      id: "preview-" + day.id,
      fileId: day.source.fileId,
      companyId: day.companyId,
      competenceId: day.competenceId,
      employeeId: day.employeeId,
      employeeName: day.employeeName,
      funcionario: day.employeeName,
      date: day.date,
      data: day.date,
      originalPunches: day.originalPunches,
      batidasOriginais: day.originalPunches,
      suggestion: day.suggestion,
      interpretacaoSugerida: suggestedParts.join(" / "),
      status: day.issues.some(function (issue) { return !issue.resolved; }) ? "conferir" : day.status,
      statusLabel: day.issues.some(function (issue) { return !issue.resolved; }) ? "Conferir" : day.statusLabel,
      observation: day.observation || day.issues.map(function (issue) { return issue.message; }).join(" "),
      hasPendingIssue: day.issues.some(function (issue) { return !issue.resolved; }),
      issues: day.issues,
      source: day.source,
    };
  });

  var unresolvedPreviewCount = importPreviewRows.filter(function (row) { return row.hasPendingIssue; }).length;
  var originalPunchCount = attendanceDays.reduce(function (total, day) {
    return total + day.originalPunches.length;
  }, 0);
  var queenTxtFile = files.find(function (file) { return file.id === "file-queen-txt"; });
  var queenJulyCompetence = competencies.find(function (competence) { return competence.id === QUEEN_JULY_ID; });
  queenTxtFile.punchCount = originalPunchCount;
  queenTxtFile.pendingCount = unresolvedPreviewCount;
  queenJulyCompetence.pendingCount = unresolvedPreviewCount;

  var importAnalysis = {
    id: "analysis-queen-txt",
    fileId: "file-queen-txt",
    fileName: "ALOG_001.txt",
    companyId: QUEEN_ID,
    companyName: "Queen",
    competenceId: QUEEN_JULY_ID,
    competenceLabel: "07/2026",
    requestedType: "auto",
    detectedFormat: "TXT AFD",
    employeeCount: 8,
    punchCount: originalPunchCount,
    dayCount: 31,
    recordCount: importPreviewRows.length,
    pendingCount: unresolvedPreviewCount,
    analyzedAt: "2026-08-01T09:14:12-03:00",
    saved: false,
    rows: importPreviewRows,
  };

  var activityTimeline = [
    { id: "activity-1", competenceId: QUEEN_JULY_ID, at: "2026-08-01T09:13:00-03:00", type: "file_received", actor: "Marina Souza", title: "Arquivo recebido", description: "ALOG_001.txt foi adicionado à competência." },
    { id: "activity-2", competenceId: QUEEN_JULY_ID, at: "2026-08-01T09:14:12-03:00", type: "analysis_completed", actor: "Sistema", title: "Importação analisada", description: "Formato TXT AFD identificado. Leitura sugerida pronta para conferência." },
    { id: "activity-3", competenceId: QUEEN_JULY_ID, at: "2026-08-01T09:14:13-03:00", type: "punches_found", actor: "Sistema", title: "Batidas encontradas", description: "Batidas de 8 funcionários foram estruturadas sem alterar o arquivo original." },
    { id: "activity-4", competenceId: QUEEN_JULY_ID, at: "2026-08-01T09:14:14-03:00", type: "issues_found", actor: "Sistema", title: "Pendências identificadas", description: "12 registros precisam de revisão humana." },
    { id: "activity-5", competenceId: QUEEN_JULY_ID, at: "2026-08-01T14:20:00-03:00", type: "manual_change", actor: "Marina Souza", title: "Alteração feita", description: "Saída de Lana Fernanda em 10/07 foi alterada de 17:06 para 17:08." },
    { id: "activity-6", competenceId: 1000, at: "2026-07-05T16:50:00-03:00", type: "report_exported", actor: "Marina Souza", title: "Relatório exportado", description: "Relatório Excel da competência 06/2026 foi exportado." },
    { id: "activity-7", competenceId: 1000, at: "2026-07-05T17:30:00-03:00", type: "competence_closed", actor: "Marina Souza", title: "Competência fechada", description: "Competência 06/2026 da Queen foi fechada após confirmação." },
  ];

  var ocrMock = {
    id: "ocr-file-queen-image",
    fileId: "file-queen-image",
    message: "Leitura sugerida. Confira antes de salvar.",
    certaintyDisclaimer: "Os dados abaixo são uma interpretação simulada e podem conter erros.",
    document: {
      fileName: "espelho_ponto_lana_julho.jpg",
      type: "image/jpeg",
      page: 1,
      pageCount: 2,
      zoom: 100,
      rotation: 0,
      contrast: 100,
      previewUrl: "",
      controls: ["zoom_in", "zoom_out", "rotate", "contrast", "previous_page", "next_page"],
    },
    extractedRows: [
      { id: "ocr-row-1", employeeName: "Lana Fernanda", date: "2026-07-01", entry: "08:03", breakStart: "14:22", breakEnd: "15:27", exit: "17:08", confidence: 94, observation: "Quatro horários reconhecidos.", suggestedStatus: "conferir" },
      { id: "ocr-row-2", employeeName: "Lana Fernanda", date: "2026-07-08", entry: "08:02", breakStart: "12:01", breakEnd: "13:04", exit: "?", confidence: 61, observation: "Saída final não reconhecida.", suggestedStatus: "inconsistente" },
      { id: "ocr-row-3", employeeName: "Lana Fernanda", date: "2026-07-10", entry: "08:01", breakStart: "12:04", breakEnd: "13:02", exit: "17:06", confidence: 87, observation: "Confira o último dígito da saída.", suggestedStatus: "conferir" },
    ],
  };

  var dashboard = {
    indicators: {
      open: competencies.filter(function (item) { return item.status === "aberta"; }).length,
      inReview: competencies.filter(function (item) { return item.status === "em_conferencia"; }).length,
      withPendingIssues: competencies.filter(function (item) { return item.pendingCount > 0; }).length,
      closedThisMonth: competencies.filter(function (item) { return item.status === "fechada" && item.closedAt && item.closedAt.slice(0, 7) === "2026-08"; }).length,
    },
    recentCompetencies: competencies.slice().sort(function (left, right) {
      return right.updatedAt.localeCompare(left.updatedAt);
    }),
  };

  var fileTypeOptions = [
    { value: "auto", label: "Detectar automaticamente" },
    { value: "txt_clock", label: "TXT de relógio" },
    { value: "xls_legacy", label: "XLS legado" },
    { value: "xlsx", label: "XLSX" },
    { value: "scanned", label: "Imagem ou PDF escaneado" },
  ];

  var keyboardShortcuts = [
    { keys: "Ctrl + S", action: "save", label: "Salvar imediatamente" },
    { keys: "Ctrl + Z", action: "undo", label: "Desfazer" },
    { keys: "Alt + ↑", action: "previous_employee", label: "Funcionário anterior" },
    { keys: "Alt + ↓", action: "next_employee", label: "Próximo funcionário" },
    { keys: "N", action: "status_normal", label: "Normal", disabledWhileEditing: true },
    { keys: "F", action: "status_absence", label: "Falta", disabledWhileEditing: true },
    { keys: "A", action: "status_certificate", label: "Atestado", disabledWhileEditing: true },
    { keys: "C", action: "confirm_day", label: "Marcar como conferido", disabledWhileEditing: true },
  ];

  var bulkActions = [
    { id: "confirm", label: "Marcar como conferidos", requiresConfirmation: true, preservesOriginalPunches: true },
    { id: "set_status", label: "Definir situação", requiresConfirmation: true, preservesOriginalPunches: true },
    { id: "add_observation", label: "Adicionar observação", requiresConfirmation: true, preservesOriginalPunches: true },
  ];

  var rawData = {
    companies: companies,
    scales: scales,
    escalas: scales,
    competencias: competencies,
    competencies: competencies,
    employees: employees,
    funcionarios: employees,
    files: files,
    arquivos: files,
    attendanceDays: attendanceDays,
    dias: attendanceDays,
    pendingIssues: pendingIssues,
    pendencias: pendingIssues,
    importPreviewRows: importPreviewRows,
    linhasPrevia: importPreviewRows,
    importAnalysis: importAnalysis,
    analiseImportacao: importAnalysis,
    employeeProgress: employeeProgress,
    progressoFuncionarios: employeeProgress,
    statusDefinitions: statusDefinitions,
    status: statusDefinitions,
    dashboard: dashboard,
    activityTimeline: activityTimeline,
    historicoCompetencia: activityTimeline,
    ocr: ocrMock,
    fileTypeOptions: fileTypeOptions,
    keyboardShortcuts: keyboardShortcuts,
    bulkActions: bulkActions,
  };
  rawData.empresas = companies;

  function lockOriginalPunches(value, seen) {
    if (value === null || typeof value !== "object") return value;
    var visited = seen || new WeakSet();
    if (visited.has(value)) return value;
    visited.add(value);

    if (Array.isArray(value)) {
      value.forEach(function (item) { lockOriginalPunches(item, visited); });
    } else {
      Object.keys(value).forEach(function (key) {
        lockOriginalPunches(value[key], visited);
      });
      if (value.originalPunches) Object.freeze(value.originalPunches);
      if (value.batidasOriginais) Object.freeze(value.batidasOriginais);
      if (value.originalPunchDetails) deepFreeze(value.originalPunchDetails);
      if (value.original) deepFreeze(value.original);
      if (value.suggestion) deepFreeze(value.suggestion);
      if (value.suggested) deepFreeze(value.suggested);
      if (value.confirmedResult) deepFreeze(value.confirmedResult);
      if (value.resultadoConferido) deepFreeze(value.resultadoConferido);
    }
    return value;
  }

  deepFreeze(rawData);

  function createWorkingCopy() {
    return lockOriginalPunches(clone(rawData));
  }

  function getCompany(id) {
    return companies.find(function (company) { return String(company.id) === String(id); }) || null;
  }

  function getCompetence(id) {
    return competencies.find(function (competence) { return String(competence.id) === String(id); }) || null;
  }

  function getEmployee(id) {
    return employees.find(function (employee) { return String(employee.id) === String(id); }) || null;
  }

  function getEmployeesByCompany(companyId) {
    return employees.filter(function (employee) { return String(employee.companyId) === String(companyId); });
  }

  function getCompetenciesByCompany(companyId) {
    return competencies.filter(function (competence) { return String(competence.companyId) === String(companyId); });
  }

  function getFilesByCompetence(competenceId) {
    return files.filter(function (file) { return String(file.competenceId) === String(competenceId); });
  }

  function getDaysByEmployee(employeeId, competenceId) {
    return attendanceDays.filter(function (day) {
      return String(day.employeeId) === String(employeeId) && (competenceId == null || String(day.competenceId) === String(competenceId));
    });
  }

  function getDay(id) {
    return attendanceDays.find(function (day) { return String(day.id) === String(id); }) || null;
  }

  function getPreviewRows(filters) {
    var criteria = filters || {};
    return importPreviewRows.filter(function (row) {
      if (criteria.fileId != null && String(row.fileId) !== String(criteria.fileId)) return false;
      if (criteria.employeeId != null && String(row.employeeId) !== String(criteria.employeeId)) return false;
      if (criteria.onlyPending && !row.hasPendingIssue) return false;
      return true;
    });
  }

  var publicApi = {
    data: rawData,
    companies: companies,
    empresas: companies,
    scales: scales,
    escalas: scales,
    competencies: competencies,
    competencias: competencies,
    employees: employees,
    funcionarios: employees,
    files: files,
    arquivos: files,
    attendanceDays: attendanceDays,
    dias: attendanceDays,
    pendingIssues: pendingIssues,
    pendencias: pendingIssues,
    importPreviewRows: importPreviewRows,
    linhasPrevia: importPreviewRows,
    importAnalysis: importAnalysis,
    analiseImportacao: importAnalysis,
    employeeProgress: employeeProgress,
    progressoFuncionarios: employeeProgress,
    statusDefinitions: statusDefinitions,
    status: statusDefinitions,
    dashboard: dashboard,
    activityTimeline: activityTimeline,
    historicoCompetencia: activityTimeline,
    ocr: ocrMock,
    fileTypeOptions: fileTypeOptions,
    keyboardShortcuts: keyboardShortcuts,
    bulkActions: bulkActions,
    constants: deepFreeze({ QUEEN_ID: QUEEN_ID, QUEEN_JULY_ID: QUEEN_JULY_ID, YEAR: JULY_YEAR, MONTH: JULY_MONTH }),
    createWorkingCopy: createWorkingCopy,
    getFreshData: createWorkingCopy,
    reset: createWorkingCopy,
    getCompany: getCompany,
    getCompetence: getCompetence,
    getEmployee: getEmployee,
    getEmployeesByCompany: getEmployeesByCompany,
    getCompetenciesByCompany: getCompetenciesByCompany,
    getFilesByCompetence: getFilesByCompetence,
    getDaysByEmployee: getDaysByEmployee,
    getDay: getDay,
    getPreviewRows: getPreviewRows,
  };

  root.OnPontoMocks = Object.freeze(publicApi);
})(typeof window !== "undefined" ? window : globalThis);
