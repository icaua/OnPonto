(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoImportacao=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var Utils=deps.Utils;
    var currentCompany=deps.currentCompany;
    var currentCompetency=deps.currentCompetency;
    var data=deps.data;
    var firstValue=deps.firstValue;
    var normalizeIssues=deps.normalizeIssues;
    var normalizeOriginalPunches=deps.normalizeOriginalPunches;
    var normalizedTime=deps.normalizedTime;
    var state=deps.state;
    var statusFromBackend=deps.statusFromBackend;
    var statusLabel=deps.statusLabel;
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
  function importConflictMessages(payload) {
    var source = payload || {};
    var conflicts = firstValue(source.conflitos, source.conflicts, source.erros, []);
    if (!Array.isArray(conflicts)) conflicts = conflicts ? [conflicts] : [];
    return conflicts.map(function (conflict) {
      if (typeof conflict === "string") return conflict;
      return conflict.message || conflict.mensagem || conflict.detail || "Registro não importado.";
    });
  }
    return Object.freeze({normalizePreviewRow:normalizePreviewRow,normalizeImportAnalysis:normalizeImportAnalysis,importConflictMessages:importConflictMessages});
  }
  return Object.freeze({create:create});
});
