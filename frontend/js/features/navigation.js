(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoNavigation=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var COMPANY_VIEWS=deps.COMPANY_VIEWS;
    var COMPETENCY_VIEWS=deps.COMPETENCY_VIEWS;
    var ROUTE_ALIASES=deps.ROUTE_ALIASES;
    var VIEWS=deps.VIEWS;
    var asId=deps.asId;
    var companies=deps.companies;
    var competencies=deps.competencies;
    var employees=deps.employees;
    var files=deps.files;
    var idsEqual=deps.idsEqual;
    var scales=deps.scales;
    var state=deps.state;
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
    return Object.freeze({emptyRoute:emptyRoute,safeDecode:safeDecode,parseHashRoute:parseHashRoute,validateRoute:validateRoute,routeHash:routeHash,routeView:routeView,navigationTarget:navigationTarget,normalizeRoute:normalizeRoute});
  }
  return Object.freeze({create:create});
});
