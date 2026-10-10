(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoApi=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  var sessions=new WeakMap();
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
  function localSession(force,signal,expiredCsrf) {
    var base=configuredApiBase(),byBase=sessions.get(root);
    if(!byBase){byBase=Object.create(null);sessions.set(root,byBase);}
    if(force && byBase[base] && byBase[base].csrf===expiredCsrf) delete byBase[base];
    if(!byBase[base]) {
      var pending=root.fetch(base+"/sessao/local",{credentials:"include",headers:{Accept:"application/json"},signal:signal}).then(function(response){
        return response.text().then(function(body){
          var payload;try{payload=JSON.parse(body);}catch(e){throw new Error("Resposta de sessão local inválida.");}
          if(!response.ok || typeof payload.csrf!=="string" || payload.csrf.length<20) throw new Error(apiErrorMessage(payload,"Não foi possível iniciar a sessão local."));
          pending.csrf=payload.csrf;
          return payload.csrf;
        });
      }).catch(function(error){if(byBase[base]===pending)delete byBase[base];throw error;});
      byBase[base]=pending;
    }
    return byBase[base];
  }
  function authenticatedFetch(path,options,retry) {
    var settings=Object.assign({},options || {});
    var usedCsrf;
    return localSession(false,settings.signal).then(function(csrf){
      usedCsrf=csrf;
      settings.credentials="include";
      settings.headers=Object.assign({},settings.headers || {});
      if(!/^(GET|HEAD)$/i.test(settings.method || "GET")) settings.headers["X-OnPonto-CSRF"]=csrf;
      return root.fetch(configuredApiBase()+path,settings);
    }).then(function(response){
      if(response.status===401 && !retry) return localSession(true,settings.signal,usedCsrf).then(function(){return authenticatedFetch(path,options,true);});
      return response;
    });
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

    return authenticatedFetch(path, requestOptions).then(function (response) {
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
    return Object.freeze({authenticatedFetch:authenticatedFetch,apiErrorMessage:apiErrorMessage,isClosedCompetenceError:isClosedCompetenceError,isRevisionConflictError:isRevisionConflictError,apiRequest:apiRequest,apiCollection:apiCollection});
  }
  return Object.freeze({create:create});
});
