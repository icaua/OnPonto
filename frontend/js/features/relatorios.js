(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoRelatorios=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var apiErrorMessage=deps.apiErrorMessage;
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
    return Object.freeze({exportFilename:exportFilename,exportResponseError:exportResponseError,exportErrorDetail:exportErrorDetail});
  }
  return Object.freeze({create:create});
});
