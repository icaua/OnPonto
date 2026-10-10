(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoApi=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var configuredApiBase=deps.configuredApiBase;
    var data=deps.data;
    var root=deps.root;
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
  function isRevisionConflictError(error) {
    var detail = error && error.payload && error.payload.detail;
    return Boolean(error && error.status === 409 && detail && /^revisao_/.test(detail.codigo || ""));
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
    return Object.freeze({apiErrorMessage:apiErrorMessage,isClosedCompetenceError:isClosedCompetenceError,isRevisionConflictError:isRevisionConflictError,apiRequest:apiRequest,apiCollection:apiCollection});
  }
  return Object.freeze({create:create});
});
