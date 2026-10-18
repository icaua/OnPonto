(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoStore=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var data=deps.data;
    var employees=deps.employees;
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
      operational: source.operacional || null,
      closing: source.fechamento || null,
      importIssues: source.pendencias_importacao || [],
      linkWarnings: Array.isArray(source.avisos_vinculo) ? source.avisos_vinculo : [],
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
          observations: valueFromAliases(item, ["observacoes", "observations"]),
          bank: item.banco_horas || null,
          dsrDays: item.dsr_dias,
          dsrDiscount: item.dsr_desconto_dias,
          distribution: Object.prototype.hasOwnProperty.call(item, "extra_apurada_minutos") ? {
            gross:item.extra_apurada_minutos, payroll:item.extra_folha_minutos, bankBase:item.extra_banco_base_minutos,
            bank:item.extra_banco_minutos, debit:item.debito_banco_minutos, premiums:item.adicionais_folha || [],
            policies:item.politicas_horas_aplicadas || []
          } : null,
          processedDays: valueFromAliases(item, ["dias_processados", "processed_days", "day_count"]),
          delays: valueFromAliases(item, ["atrasos", "atraso", "total_atrasos", "delays"]),
          delayMinutes: valueFromAliases(item, ["atrasos_minutos", "atraso_minutos", "delay_minutes"]),
          extras: valueFromAliases(item, ["extras", "horas_extras", "total_extras", "overtime"]),
          extraMinutes: valueFromAliases(item, ["extras_minutos", "extra_minutos", "overtime_minutes"]),
          holidayMinutes: Object.prototype.hasOwnProperty.call(item, "horas_feriado_minutos") ? item.horas_feriado_minutos : null,
          absences: valueFromAliases(item, ["faltas", "absences"]),
          certificates: valueFromAliases(item, ["atestados", "certificates", "medical_certificates"]),
          pending: valueFromAliases(item, ["problemas", "pending", "issues"]),
          awaiting: valueFromAliases(item, ["aguardando_conferencia"]),
          situation: valueFromAliases(item, ["situacao", "situation", "status"]),
        };
      }),
    };
  }
    return Object.freeze({valueFromAliases:valueFromAliases,normalizeCompetenceSummary:normalizeCompetenceSummary});
  }
  return Object.freeze({create:create});
});
