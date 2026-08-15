(function (root) {
  "use strict";

  var utils = root.OnPontoUtils || {};

  function escapeHtml(value) {
    if (typeof utils.escapeHtml === "function") return utils.escapeHtml(value);
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;",
      }[character];
    });
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function valueOf(object, keys, fallback) {
    var source = object || {};
    for (var index = 0; index < keys.length; index += 1) {
      if (source[keys[index]] !== undefined && source[keys[index]] !== null) return source[keys[index]];
    }
    return fallback;
  }

  function collection(data, keys) {
    var source = data && data.data && typeof data.data === "object" ? data.data : data || {};
    var entities = source.entities || source.entidades || {};
    for (var index = 0; index < keys.length; index += 1) {
      if (Array.isArray(source[keys[index]])) return source[keys[index]];
      if (Array.isArray(entities[keys[index]])) return entities[keys[index]];
    }
    return [];
  }

  function idOf(item) {
    return valueOf(item, ["id", "key", "codigo"], "");
  }

  function idsEqual(left, right) {
    return left !== undefined && left !== null && right !== undefined && right !== null && String(left) === String(right);
  }

  function findById(items, id) {
    if (id === undefined || id === null || id === "") return null;
    return asArray(items).find(function (item) { return idsEqual(idOf(item), id); }) || null;
  }

  function statusKey(value) {
    if (typeof utils.statusKey === "function") return utils.statusKey(value);
    return String(value == null ? "" : value)
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function formatDate(value, short) {
    if (typeof utils.formatDate === "function") return utils.formatDate(value, { short: short === true });
    if (!value) return "—";
    var parts = String(value).slice(0, 10).split("-");
    return parts.length === 3 ? parts[2] + "/" + parts[1] + (short ? "" : "/" + parts[0]) : String(value);
  }

  function formatDateTime(value) {
    if (typeof utils.formatDateTime === "function") return utils.formatDateTime(value);
    return value ? String(value) : "—";
  }

  function formatCompetence(item) {
    var label = valueOf(item, ["label", "competenceLabel", "competenciaLabel"], "");
    if (label) return label;
    if (typeof utils.formatCompetence === "function") return utils.formatCompetence(item);
    var month = valueOf(item, ["month", "mes"], null);
    var year = valueOf(item, ["year", "ano"], null);
    return month && year ? String(month).padStart(2, "0") + "/" + year : "—";
  }

  function formatDuration(value) {
    if (typeof utils.formatDuration === "function") return utils.formatDuration(value);
    if (value === null || value === undefined || value === "") return "—";
    var minutes = Number(value);
    if (!Number.isFinite(minutes)) return String(value);
    return String(Math.floor(Math.abs(minutes) / 60)).padStart(2, "0") + ":" + String(Math.abs(minutes) % 60).padStart(2, "0");
  }

  function formatBalance(value) {
    if (typeof utils.formatBalance === "function") return utils.formatBalance(value);
    if (value === null || value === undefined || value === "") return "—";
    var minutes = Number(value);
    if (!Number.isFinite(minutes)) return String(value);
    return (minutes > 0 ? "+" : minutes < 0 ? "-" : "") + formatDuration(Math.abs(minutes));
  }

  function formatFileSize(value) {
    if (typeof utils.formatFileSize === "function") return utils.formatFileSize(value);
    return value == null ? "—" : String(value) + " B";
  }

  function companyName(company) {
    return valueOf(company, ["name", "nome", "legalName", "razaoSocial"], "Empresa não selecionada");
  }

  function employeeName(employee) {
    return valueOf(employee, ["name", "nome", "employeeName", "funcionario"], "Funcionário não selecionado");
  }

  function normalizeStatus(raw) {
    var key = statusKey(raw || "conferir");
    var aliases = {
      aberta: "aberta",
      open: "aberta",
      em_conferencia: "em_conferencia",
      in_review: "em_conferencia",
      conferida: "conferida",
      ready: "conferida",
      fechada: "fechada",
      closed: "fechada",
      needs_review: "conferir",
      pendente: "conferir",
      pendente_conferencia: "conferir",
      review: "conferir",
      inconsistency: "inconsistente",
      absence: "falta",
      certificate: "atestado",
      day_off: "folga",
      holiday: "feriado",
      sunday: "domingo",
      no_schedule: "sem_expediente",
      external_work: "trabalho_externo",
      leave: "afastamento",
    };
    return aliases[key] || key || "conferir";
  }

  function statusMeta(raw, explicitLabel) {
    var key = normalizeStatus(raw);
    var definitions = {
      aberta: { label: "Aberta", icon: "○", tone: "info" },
      em_conferencia: { label: "Em conferência", icon: "!", tone: "warning" },
      conferida: { label: "Conferida", icon: "✓", tone: "success" },
      fechada: { label: "Fechada", icon: "✓", tone: "success" },
      normal: { label: "Normal", icon: "✓", tone: "success" },
      conferir: { label: "Conferir", icon: "!", tone: "warning" },
      inconsistente: { label: "Inconsistente", icon: "×", tone: "danger" },
      falta: { label: "Falta", icon: "!", tone: "danger" },
      atestado: { label: "Atestado", icon: "+", tone: "info" },
      folga: { label: "Folga", icon: "○", tone: "neutral" },
      feriado: { label: "Feriado", icon: "★", tone: "neutral" },
      domingo: { label: "Domingo", icon: "○", tone: "muted" },
      sem_expediente: { label: "Sem expediente", icon: "—", tone: "muted" },
      trabalho_externo: { label: "Trabalho externo", icon: "↗", tone: "info" },
      afastamento: { label: "Afastamento", icon: "‖", tone: "neutral" },
      analisado: { label: "Analisado", icon: "✓", tone: "success" },
      leitura_sugerida: { label: "Leitura sugerida", icon: "!", tone: "warning" },
    };
    var meta = definitions[key] || { label: String(raw || "Conferir"), icon: "•", tone: "neutral" };
    return { key: key, label: explicitLabel || meta.label, icon: meta.icon, tone: meta.tone };
  }

  function component(components, names, props, fallback) {
    var source = components || {};
    for (var index = 0; index < names.length; index += 1) {
      if (typeof source[names[index]] === "function") {
        try {
          var rendered = source[names[index]](props || {});
          if (typeof rendered === "string") return rendered;
        } catch (error) {
          /* A fallback keeps each screen usable with partial component bundles. */
        }
      }
    }
    return typeof fallback === "function" ? fallback(props || {}) : String(fallback || "");
  }

  function demoBanner(explicitState) {
    var appState = explicitState || (root.OnPontoApp && typeof root.OnPontoApp.getState === "function" ? root.OnPontoApp.getState() : null) || {};
    if (appState.apiMode === "online") return "";
    var loading = appState.apiMode === "loading";
    return [
      '<div class="demo-banner' + (loading ? " is-loading" : " is-offline") + '" role="status">',
      '<span class="demo-banner__icon" aria-hidden="true">◇</span>',
      loading
        ? '<span><strong>Conectando à API</strong> · Carregando dados do On Ponto.</span>'
        : '<span><strong>Modo demonstração</strong> · A API está indisponível; os dados exibidos são simulados e não serão enviados.</span>',
      "</div>",
    ].join("");
  }

  function actionButton(action) {
    var item = action || {};
    var routeAttribute = item.route ? ' data-route="' + escapeHtml(item.route) + '"' : "";
    var actionAttribute = item.action ? ' data-action="' + escapeHtml(item.action) + '"' : "";
    var extra = item.attributes || "";
    return '<button class="button ' + escapeHtml(item.variant || "button--secondary") + '" type="button"' + actionAttribute + routeAttribute + extra + (item.disabled ? " disabled" : "") + '>' + escapeHtml(item.label || "Ação") + "</button>";
  }

  function pageHeader(components, props) {
    var componentProps = Object.assign({}, props, {
      actions: asArray(props.actions).map(function (action) {
        return Object.assign({}, action, {
          value: action.value || action.route,
          variant: String(action.variant || "secondary").replace(/^button--?/, ""),
        });
      }),
    });
    return component(components, ["PageHeader", "pageHeader"], componentProps, function () {
      var options = props;
      var breadcrumbs = asArray(options.breadcrumbs).length
        ? '<nav class="breadcrumbs" aria-label="Navegação estrutural">' + asArray(options.breadcrumbs).map(function (crumb) {
          return crumb.route
            ? '<button type="button" data-route="' + escapeHtml(crumb.route) + '" data-action="navigate">' + escapeHtml(crumb.label) + "</button>"
            : "<span>" + escapeHtml(crumb.label) + "</span>";
        }).join('<span aria-hidden="true">/</span>') + "</nav>"
        : "";
      return [
        '<header class="op-page-header">',
        '<div class="op-page-header__copy">', breadcrumbs,
        options.eyebrow ? '<span class="eyebrow">' + escapeHtml(options.eyebrow) + "</span>" : "",
        "<h1>" + escapeHtml(options.title) + "</h1>",
        options.subtitle ? "<p>" + escapeHtml(options.subtitle) + "</p>" : "",
        "</div>",
        '<div class="op-page-header__actions">' + asArray(options.actions).map(actionButton).join("") + "</div>",
        "</header>",
      ].join("");
    });
  }

  function statusChip(components, status, explicitLabel) {
    var meta = statusMeta(status, explicitLabel);
    return component(components, ["StatusChip", "statusChip"], {
      status: meta.key,
      value: meta.key,
      label: meta.label,
      tone: meta.tone,
    }, function () {
      return '<span class="status-chip status-chip--' + escapeHtml(meta.tone) + ' status-chip--' + escapeHtml(meta.key) + '"><span aria-hidden="true">' + escapeHtml(meta.icon) + "</span><span>" + escapeHtml(meta.label) + "</span></span>";
    });
  }

  function progressIndicator(components, current, total, label, percentage) {
    var safeTotal = Math.max(Number(total) || 0, 0);
    var safeCurrent = Math.max(Number(current) || 0, 0);
    var computed = percentage == null ? (safeTotal ? Math.round((safeCurrent / safeTotal) * 100) : 0) : Number(percentage);
    if (computed > 0 && computed <= 1) computed *= 100;
    computed = Math.min(100, Math.max(0, Math.round(computed || 0)));
    return component(components, ["ProgressIndicator", "progressIndicator"], {
      current: safeCurrent,
      value: safeCurrent,
      total: safeTotal,
      max: safeTotal,
      percentage: computed,
      label: label,
      compact: !label,
    }, function () {
      return [
        '<div class="progress-indicator">',
        '<div class="progress-indicator__meta"><span>' + escapeHtml(label || "Progresso") + "</span><strong>" + computed + "%</strong></div>",
        '<div class="progress-indicator__track" role="progressbar" aria-label="' + escapeHtml(label || "Progresso") + '" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + computed + '"><span style="width:' + computed + '%"></span></div>',
        safeTotal ? '<small>' + safeCurrent + " de " + safeTotal + "</small>" : "",
        "</div>",
      ].join("");
    });
  }

  function emptyState(components, title, description, action) {
    var componentAction = action ? Object.assign({}, action, {
      value: action.value || action.route,
      variant: String(action.variant || "secondary").replace(/^button--?/, ""),
    }) : null;
    return component(components, ["EmptyState", "emptyState"], {
      title: title,
      description: description,
      action: componentAction,
    }, function () {
      return '<div class="empty-state"><span aria-hidden="true">□</span><h3>' + escapeHtml(title) + "</h3><p>" + escapeHtml(description) + "</p>" + (action ? actionButton(action) : "") + "</div>";
    });
  }

  function normalizeArgs(state, data, components) {
    if (state && state.state && (state.data || state.components) && data === undefined) {
      return { state: state.state || {}, data: state.data || {}, components: state.components || {} };
    }
    return { state: state || {}, data: data || {}, components: components || {} };
  }

  function selectedEntities(context) {
    var state = context.state;
    var companies = collection(context.data, ["companies", "empresas"]);
    var competencies = collection(context.data, ["competencies", "competencias"]);
    var employees = collection(context.data, ["employees", "funcionarios"]);
    var competenceId = valueOf(state, ["selectedCompetenceId", "selectedCompetencyId", "competenceId", "competencyId", "competenciaId", "competencia_id"], null);
    var employeeId = valueOf(state, ["selectedEmployeeId", "employeeId", "funcionarioId", "funcionario_id"], null);
    var companyId = valueOf(state, ["selectedCompanyId", "companyId", "empresaId", "empresa_id"], null);
    var competence = valueOf(state, ["selectedCompetence", "selectedCompetency", "competenciaSelecionada"], null) || (competenceId == null ? null : findById(competencies, competenceId));
    if (!companyId && competence) companyId = valueOf(competence, ["companyId", "empresaId", "empresa_id"], null);
    var company = valueOf(state, ["selectedCompany", "empresaSelecionada"], null) || (companyId == null ? null : findById(companies, companyId));
    if (company && competence && !idsEqual(valueOf(competence, ["companyId", "empresaId", "empresa_id"], null), idOf(company))) competence = null;
    var companyEmployees = company ? employees.filter(function (employee) {
      return idsEqual(valueOf(employee, ["companyId", "empresaId", "empresa_id"], null), idOf(company));
    }) : [];
    var employee = valueOf(state, ["selectedEmployee", "funcionarioSelecionado"], null) || (employeeId == null ? null : findById(employees, employeeId));
    if (employee && company && !idsEqual(valueOf(employee, ["companyId", "empresaId", "empresa_id"], null), idOf(company))) employee = null;
    return {
      companies: companies,
      competencies: competencies,
      employees: employees,
      companyEmployees: companyEmployees,
      company: company,
      competence: competence,
      employee: employee,
    };
  }

  function competenciesForCompany(entities, company) {
    if (!company) return [];
    return entities.competencies.filter(function (competence) {
      return idsEqual(valueOf(competence, ["companyId", "empresaId", "empresa_id"], null), idOf(company));
    }).slice().sort(function (left, right) {
      var leftDate = String(valueOf(left, ["updatedAt", "updated_at", "ultimaAtualizacao"], ""));
      var rightDate = String(valueOf(right, ["updatedAt", "updated_at", "ultimaAtualizacao"], ""));
      if (leftDate !== rightDate) return rightDate.localeCompare(leftDate);
      var leftValue = Number(valueOf(left, ["year", "ano"], 0)) * 100 + Number(valueOf(left, ["month", "mes"], 0));
      var rightValue = Number(valueOf(right, ["year", "ano"], 0)) * 100 + Number(valueOf(right, ["month", "mes"], 0));
      return rightValue - leftValue;
    });
  }

  function currentCompetenceForCompany(entities, company) {
    if (entities.competence && company && idsEqual(valueOf(entities.competence, ["companyId", "empresaId", "empresa_id"], null), idOf(company))) return entities.competence;
    return competenciesForCompany(entities, company)[0] || null;
  }

  function companyBreadcrumbs(company, area) {
    var crumbs = [{ label: "Empresas", route: "companies" }];
    if (company) crumbs.push({ label: companyName(company), route: area ? "company-overview" : null });
    if (area) crumbs.push({ label: area });
    return crumbs;
  }

  function competenceBreadcrumbs(entities, area, detail) {
    var areaRoutes = {
      Resumo: "competency-summary",
      "Importações": "imports",
      "Conferência": "review",
      Arquivos: "competency-files",
      "Histórico": "competency-history",
      "Exportações": "competency-exports",
    };
    var crumbs = [
      { label: "Empresas", route: "companies" },
      { label: companyName(entities.company), route: "company-overview" },
      { label: formatCompetence(entities.competence), route: area ? "competency-summary" : null },
    ];
    if (area) crumbs.push({ label: area, route: detail ? areaRoutes[area] : null });
    if (detail) crumbs.push({ label: detail });
    return crumbs;
  }

  function competencyAreaNavigation(activeRoute) {
    var items = [
      { route: "competency-summary", label: "Resumo" },
      { route: "imports", label: "Importações" },
      { route: "review", label: "Conferência" },
      { route: "competency-files", label: "Arquivos" },
      { route: "competency-history", label: "Histórico" },
      { route: "competency-exports", label: "Exportações" },
    ];
    return '<nav class="tabs competency-tabs" aria-label="Áreas da competência">' + items.map(function (item) {
      var active = item.route === activeRoute;
      return '<button type="button" class="tab' + (active ? " is-active" : "") + '" data-action="navigate" data-route="' + escapeHtml(item.route) + '"' + (active ? ' aria-current="page"' : "") + '>' + escapeHtml(item.label) + "</button>";
    }).join("") + "</nav>";
  }

  function missingContextScreen(context, title, description, needsCompetence) {
    var entities = selectedEntities(context);
    var breadcrumbs = entities.company ? companyBreadcrumbs(entities.company, title) : [{ label: "Empresas", route: "companies" }, { label: title }];
    return '<section class="screen screen--not-found" data-screen="context-missing">' + demoBanner() + pageHeader(context.components, {
      title: title,
      subtitle: description,
      breadcrumbs: breadcrumbs,
    }) + emptyState(context.components, needsCompetence ? "Selecione uma competência" : "Selecione uma empresa", description, {
      label: needsCompetence && entities.company ? "Ver competências" : "Ver empresas",
      route: needsCompetence && entities.company ? "company-competencies" : "companies",
      action: "navigate",
    }) + "</section>";
  }

  function renderCompanies(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    var search = String(valueOf(context.state, ["companySearch", "companiesSearch", "buscaEmpresas"], "") || "");
    var normalizedSearch = statusKey(search);
    var visibleCompanies = entities.companies.filter(function (company) {
      return !normalizedSearch || statusKey(companyName(company)).indexOf(normalizedSearch) !== -1 || statusKey(valueOf(company, ["legalName", "razaoSocial", "cnpj"], "")).indexOf(normalizedSearch) !== -1;
    });
    var rows = visibleCompanies.map(function (company) {
      var companyCompetencies = competenciesForCompany(entities, company);
      var current = companyCompetencies[0] || null;
      var employeeCount = entities.employees.filter(function (employee) {
        return idsEqual(valueOf(employee, ["companyId", "empresaId", "empresa_id"], null), idOf(company)) && valueOf(employee, ["active", "ativo"], true) !== false;
      }).length;
      return '<tr data-company-id="' + escapeHtml(idOf(company)) + '"><td><strong>' + escapeHtml(companyName(company)) + "</strong><small>" + escapeHtml(valueOf(company, ["legalName", "razaoSocial"], "")) + "</small></td><td>" + escapeHtml(current ? formatCompetence(current) : "Sem competência") + "</td><td>" + (current ? statusChip(context.components, current.status, current.statusLabel) : statusChip(context.components, "sem_expediente", "Sem competência")) + "</td><td>" + escapeHtml(employeeCount) + "</td><td>" + escapeHtml(current ? valueOf(current, ["pendingCount", "quantidadePendencias"], 0) : 0) + "</td><td>" + escapeHtml(current ? formatDateTime(valueOf(current, ["updatedAt", "updated_at"], null)) : "—") + '</td><td><button class="table-link" type="button" data-action="open-company" data-company-id="' + escapeHtml(idOf(company)) + '">Abrir empresa</button></td></tr>';
    }).join("");
    var table = rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Empresa</th><th>Competência atual</th><th>Status</th><th>Funcionários</th><th>Pendências</th><th>Última atualização</th><th><span class="sr-only">Ação</span></th></tr></thead><tbody>' + rows + "</tbody></table></div>" : emptyState(context.components, search ? "Nenhuma empresa encontrada" : "Nenhuma empresa cadastrada", search ? "Tente outro termo de busca." : "Cadastre a primeira empresa para iniciar o trabalho.", search ? null : { label: "Cadastrar empresa", action: "new-company" });
    return [
      '<section class="screen screen--companies" data-screen="companies">', demoBanner(),
      pageHeader(context.components, { title: "Todas as empresas", subtitle: "Selecione uma empresa para acessar funcionários e competências.", actions: [{ label: "Nova empresa", variant: "button--primary", action: "new-company" }] }),
      '<div class="toolbar"><label class="compact-field"><span>Buscar empresa</span><input type="search" value="' + escapeHtml(search) + '" placeholder="Nome da empresa" data-action="search-companies" autocomplete="off"></label><span class="position-label">' + escapeHtml(visibleCompanies.length) + " de " + escapeHtml(entities.companies.length) + " empresas</span></div>",
      '<section class="work-card">' + table + "</section></section>",
    ].join("");
  }

  function renderCompanyOverview(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    var company = entities.company;
    if (!company) return missingContextScreen(context, "Visão geral", "Abra uma empresa para continuar.", false);
    var companyCompetencies = competenciesForCompany(entities, company);
    var current = currentCompetenceForCompany(entities, company);
    var companyEmployees = entities.companyEmployees.filter(function (employee) { return valueOf(employee, ["active", "ativo"], true) !== false; });
    var activeEmployeeCount = companyEmployees.length;
    var pending = current ? Number(valueOf(current, ["pendingCount", "quantidadePendencias"], 0)) : 0;
    var currentActions = current ? '<button class="button button--primary" type="button" data-action="open-competence" data-competence-id="' + escapeHtml(idOf(current)) + '">Abrir competência atual</button><button class="button button--secondary" type="button" data-action="open-competence-area" data-competence-id="' + escapeHtml(idOf(current)) + '" data-route="imports">Adicionar documentos</button>' : "";
    var recentRows = companyCompetencies.slice(0, 5).map(function (competence) {
      return '<tr><td><strong>' + escapeHtml(formatCompetence(competence)) + "</strong></td><td>" + statusChip(context.components, competence.status, competence.statusLabel) + "</td><td>" + escapeHtml(valueOf(competence, ["employeeCount", "quantidadeFuncionarios"], companyEmployees.length)) + "</td><td>" + escapeHtml(valueOf(competence, ["pendingCount", "quantidadePendencias"], 0)) + "</td><td>" + escapeHtml(formatDateTime(valueOf(competence, ["updatedAt", "updated_at"], null))) + '</td><td><button class="table-link" type="button" data-action="open-competence" data-competence-id="' + escapeHtml(idOf(competence)) + '">Abrir</button></td></tr>';
    }).join("");
    return [
      '<section class="screen screen--company-overview" data-screen="company-overview">', demoBanner(),
      pageHeader(context.components, { title: companyName(company), subtitle: valueOf(company, ["legalName", "razaoSocial"], "Visão geral da empresa"), breadcrumbs: companyBreadcrumbs(company), actions: [{ label: "Editar empresa", variant: "button--secondary", action: "edit-company", id: idOf(company) }] }),
      '<section class="work-card competency-hero"><div>' + (current ? statusChip(context.components, current.status, current.statusLabel) : statusChip(context.components, "sem_expediente", "Sem competência")) + '</div><dl class="summary-grid summary-grid--four">' + summaryItem("Competência atual", current ? formatCompetence(current) : "Não criada") + summaryItem("Funcionários ativos", activeEmployeeCount) + summaryItem("Pendências", pending) + summaryItem("Última atualização", current ? formatDateTime(valueOf(current, ["updatedAt", "updated_at"], null)) : "—") + '</dl><div class="button-row"><button class="button button--secondary" type="button" data-action="new-competence">Criar competência</button>' + currentActions + "</div></section>",
      '<section class="work-card"><div class="section-heading"><div><h2>Competências recentes</h2><p>Acompanhe os fechamentos mais recentes desta empresa.</p></div><button class="text-button" type="button" data-action="navigate" data-route="company-competencies">Ver todas</button></div>',
      recentRows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Competência</th><th>Status</th><th>Funcionários</th><th>Pendências</th><th>Atualização</th><th><span class="sr-only">Ação</span></th></tr></thead><tbody>' + recentRows + "</tbody></table></div>" : emptyState(context.components, "Nenhuma competência", "Crie a primeira competência desta empresa.", { label: "Criar competência", action: "new-competence" }),
      '</section><section class="work-card"><div class="section-heading"><div><h2>Funcionários</h2><p>' + escapeHtml(activeEmployeeCount) + ' funcionário' + (Number(activeEmployeeCount) === 1 ? "" : "s") + ' ativo' + (Number(activeEmployeeCount) === 1 ? "" : "s") + '.</p></div><button class="text-button" type="button" data-action="navigate" data-route="company-employees">Ver funcionários</button></div></section>',
      "</section>",
    ].join("");
  }

  function renderCompanyEmployees(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    var company = entities.company;
    if (!company) return missingContextScreen(context, "Funcionários", "Abra uma empresa para visualizar seus funcionários.", false);
    var rows = entities.companyEmployees.map(function (employee) {
      var active = valueOf(employee, ["active", "ativo"], true) !== false;
      return '<tr><td><strong>' + escapeHtml(employeeName(employee)) + "</strong></td><td>" + escapeHtml(valueOf(employee, ["code", "codigo"], "—")) + "</td><td>" + escapeHtml(valueOf(employee, ["role", "cargo"], "—")) + "</td><td>" + statusChip(context.components, active ? "normal" : "sem_expediente", active ? "Ativo" : "Inativo") + '</td><td><button class="table-link" type="button" data-action="edit-employee" data-employee-id="' + escapeHtml(idOf(employee)) + '">Editar</button></td></tr>';
    }).join("");
    return '<section class="screen screen--company-employees" data-screen="company-employees">' + demoBanner() + pageHeader(context.components, {
      title: "Funcionários",
      subtitle: companyName(company),
      breadcrumbs: companyBreadcrumbs(company, "Funcionários"),
      actions: [{ label: "Novo funcionário", variant: "button--primary", action: "new-employee" }],
    }) + '<section class="work-card">' + (rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Funcionário</th><th>Código</th><th>Cargo</th><th>Status</th><th><span class="sr-only">Ação</span></th></tr></thead><tbody>' + rows + "</tbody></table></div>" : emptyState(context.components, "Nenhum funcionário cadastrado", "Cadastre os funcionários da empresa antes de importar o ponto.", { label: "Cadastrar funcionário", action: "new-employee" })) + "</section></section>";
  }

  function renderCompanyCompetencies(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    var company = entities.company;
    if (!company) return missingContextScreen(context, "Competências", "Abra uma empresa para visualizar suas competências.", false);
    var statusFilter = valueOf(context.state, ["competenciesStatusFilter", "statusFilter", "filtroStatus"], "all");
    var rows = competenciesForCompany(entities, company).filter(function (competence) {
      return statusFilter === "all" || normalizeStatus(competence.status) === statusFilter;
    }).map(function (competence) {
      var progress = Number(valueOf(competence, ["progress", "progresso"], 0));
      return '<tr><td><strong>' + escapeHtml(formatCompetence(competence)) + "</strong></td><td>" + statusChip(context.components, competence.status, competence.statusLabel) + "</td><td>" + escapeHtml(valueOf(competence, ["employeeCount", "quantidadeFuncionarios"], 0)) + '</td><td class="progress-cell">' + progressIndicator(context.components, progress, 100, "", progress) + "</td><td>" + escapeHtml(valueOf(competence, ["pendingCount", "quantidadePendencias"], 0)) + "</td><td>" + escapeHtml(valueOf(competence, ["fileCount", "quantidadeArquivos"], 0)) + "</td><td>" + escapeHtml(formatDateTime(valueOf(competence, ["updatedAt", "updated_at"], null))) + '</td><td><button class="table-link" type="button" data-action="open-competence" data-competence-id="' + escapeHtml(idOf(competence)) + '">Abrir</button></td></tr>';
    }).join("");
    return [
      '<section class="screen screen--company-competencies" data-screen="company-competencies">', demoBanner(),
      pageHeader(context.components, { title: "Competências", subtitle: companyName(company), breadcrumbs: companyBreadcrumbs(company, "Competências"), actions: [{ label: "Nova competência", variant: "button--primary", action: "new-competence" }] }),
      '<div class="toolbar"><div class="filter-group" role="group" aria-label="Situação">' + filterButton("Todas", "all", statusFilter, "competencies") + filterButton("Abertas", "aberta", statusFilter, "competencies") + filterButton("Em conferência", "em_conferencia", statusFilter, "competencies") + filterButton("Conferidas", "conferida", statusFilter, "competencies") + filterButton("Fechadas", "fechada", statusFilter, "competencies") + "</div></div>",
      '<section class="work-card">' + (rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Competência</th><th>Status</th><th>Funcionários</th><th>Progresso</th><th>Pendências</th><th>Arquivos</th><th>Atualização</th><th><span class="sr-only">Ação</span></th></tr></thead><tbody>' + rows + "</tbody></table></div>" : emptyState(context.components, "Nenhuma competência cadastrada", "Crie a competência mensal para começar a receber e conferir arquivos.", { label: "Criar competência", action: "new-competence" })) + "</section></section>",
    ].join("");
  }

  function renderDashboard(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var dashboard = valueOf(context.data, ["dashboard", "painel"], {}) || {};
    var competencies = asArray(valueOf(dashboard, ["recentCompetencies", "competenciasRecentes"], null));
    if (!competencies.length) competencies = collection(context.data, ["competencies", "competencias"]);
    var indicators = valueOf(dashboard, ["indicators", "indicadores"], {}) || {};
    var open = valueOf(indicators, ["open", "abertas"], competencies.filter(function (item) { return normalizeStatus(item.status) === "aberta"; }).length);
    var inReview = valueOf(indicators, ["inReview", "emConferencia"], competencies.filter(function (item) { return normalizeStatus(item.status) === "em_conferencia"; }).length);
    var ready = valueOf(indicators, ["ready", "conferidas"], competencies.filter(function (item) { return normalizeStatus(item.status) === "conferida"; }).length);
    var withPending = valueOf(indicators, ["withPendingIssues", "comPendencias"], competencies.filter(function (item) { return Number(valueOf(item, ["pendingCount", "pendencias"], 0)) > 0; }).length);
    var closed = valueOf(indicators, ["closedThisMonth", "fechadasNoMes"], competencies.filter(function (item) { return normalizeStatus(item.status) === "fechada"; }).length);
    var entities = selectedEntities(context);

    var table = competencies.length ? [
      '<div class="table-frame"><table class="data-table dashboard-table">',
      "<thead><tr><th>Empresa</th><th>Competência</th><th>Situação</th><th>Progresso</th><th>Pendências</th><th>Última atualização</th><th><span class=\"sr-only\">Abrir</span></th></tr></thead><tbody>",
      competencies.map(function (competence) {
        var company = findById(entities.companies, valueOf(competence, ["companyId", "empresa_id"], null));
        var progress = Number(valueOf(competence, ["progress", "progresso"], 0));
        var pending = Number(valueOf(competence, ["pendingCount", "pendencias"], 0));
        return [
          '<tr data-competence-id="' + escapeHtml(idOf(competence)) + '">',
          "<td><strong>" + escapeHtml(companyName(company)) + "</strong></td>",
          "<td>" + escapeHtml(formatCompetence(competence)) + "</td>",
          "<td>" + statusChip(context.components, competence.status, valueOf(competence, ["statusLabel"], "")) + "</td>",
          '<td class="progress-cell">' + progressIndicator(context.components, progress, 100, "", progress) + "</td>",
          '<td><span class="count-badge' + (pending ? " count-badge--warning" : "") + '">' + pending + "</span></td>",
          "<td>" + escapeHtml(formatDateTime(valueOf(competence, ["updatedAt", "updated_at", "ultimaAtualizacao"], null))) + "</td>",
          '<td><button class="table-link" type="button" data-action="open-competence" data-route="competency-detail" data-competence-id="' + escapeHtml(idOf(competence)) + '">Abrir<span class="sr-only"> ' + escapeHtml(formatCompetence(competence)) + "</span></button></td>",
          "</tr>",
        ].join("");
      }).join(""),
      "</tbody></table></div>",
    ].join("") : emptyState(context.components, "Nenhuma competência recente", "As competências criadas aparecerão aqui.", { label: "Criar competência", route: "competencies", action: "navigate" });

    return [
      '<section class="screen screen--dashboard" data-screen="dashboard">', demoBanner(),
      pageHeader(context.components, {
        title: "Painel",
        subtitle: "Acompanhe o trabalho que precisa de atenção agora.",
        actions: [{ label: "Importar ponto", variant: "button--primary", route: "imports", action: "navigate" }],
      }),
      '<div class="metric-grid" role="group" aria-label="Indicadores operacionais">',
      metricCard("Competências em aberto", open, "○", "open", "competencies"),
      metricCard("Em conferência", inReview, "!", "review", "competencies"),
      metricCard("Conferidas", ready, "✓", "confirmed", "competencies"),
      metricCard("Com pendências", withPending, "!", "pending", "review"),
      metricCard("Fechadas no mês", closed, "✓", "closed", "competencies"),
      "</div>",
      '<section class="work-card"><div class="section-heading"><div><h2>Competências recentes</h2><p>Abra uma competência para continuar exatamente de onde parou.</p></div><button class="text-button" type="button" data-route="competencies" data-action="navigate">Ver todas</button></div>',
      table,
      "</section></section>",
    ].join("");
  }

  function metricCard(label, value, icon, tone, route) {
    var descriptions = {
      open: "Aguardando processamento",
      review: "Em trabalho pela equipe",
      confirmed: "Prontas para fechamento",
      pending: "Exigem decisão operacional",
      closed: "Concluídas neste período",
    };
    var description = descriptions[tone] || "Abrir indicador";
    return '<button class="metric-card metric-card--' + escapeHtml(tone) + '" type="button" data-route="' + escapeHtml(route) + '" data-action="navigate" aria-label="' + escapeHtml(label + ": " + value + ". " + description) + '">' +
      '<span class="metric-card__icon" aria-hidden="true">' + escapeHtml(icon) + '</span><span class="metric-card__copy"><span class="metric-card__label">' + escapeHtml(label) + '</span><strong class="metric-card__value">' + escapeHtml(value) + '</strong><span class="metric-card__meta">' + escapeHtml(description) + '</span></span><span class="metric-card__link" aria-hidden="true">Abrir <span>→</span></span></button>';
  }

  function selectOptions(items, selectedId, labelFunction) {
    return asArray(items).map(function (item) {
      return '<option value="' + escapeHtml(idOf(item)) + '"' + (idsEqual(idOf(item), selectedId) ? " selected" : "") + ">" + escapeHtml(labelFunction(item)) + "</option>";
    }).join("");
  }

  function importAnalysisCard(context, analysis) {
    if (!analysis) return "";
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    return [
      '<section class="import-preview import-analysis-result" aria-labelledby="analysisTitle">',
      '<div class="section-heading"><div><span class="eyebrow">' + (online ? "Análise concluída" : "Análise de demonstração concluída") + '</span><h2 id="analysisTitle">' + escapeHtml(valueOf(analysis, ["fileName", "nomeArquivo"], "Arquivo de ponto")) + "</h2></div>" + statusChip(context.components, "analisado", "Pronto para prévia") + "</div>",
      '<dl class="summary-grid">',
      summaryItem("Formato detectado", valueOf(analysis, ["detectedFormat", "formatoDetectado"], "—")),
      summaryItem("Linhas válidas", valueOf(analysis, ["validLineCount", "totalLinhasValidas"], valueOf(analysis, ["recordCount"], 0))),
      summaryItem("Funcionários", valueOf(analysis, ["employeeCount", "totalFuncionarios"], 0)),
      summaryItem("Batidas", valueOf(analysis, ["punchCount", "totalBatidas"], 0)),
      summaryItem("Dias", valueOf(analysis, ["dayCount", "totalDias"], 0)),
      summaryItem("Pendências", valueOf(analysis, ["pendingCount", "totalPendencias"], 0)),
      "</dl>",
      '<div class="button-row"><button class="button button--primary" type="button" data-route="import-preview" data-action="open-import-preview">Ver prévia</button><button class="button button--ghost" type="button" data-action="discard-import">Descartar</button></div>',
      "</section>",
    ].join("");
  }

  function summaryItem(label, value) {
    return "<div><dt>" + escapeHtml(label) + "</dt><dd>" + escapeHtml(value == null || value === "" ? "—" : value) + "</dd></div>";
  }

  function renderImports(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Importações", "Selecione uma empresa e uma competência antes de adicionar arquivos.", true);
    var analysis = valueOf(context.state, ["importAnalysis", "analiseImportacao", "analysisResult"], undefined);
    if (analysis === undefined && valueOf(context.state, ["showImportAnalysis", "analysisVisible", "analiseVisivel"], false)) {
      analysis = valueOf(context.data, ["importAnalysis", "analiseImportacao"], null);
    }
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    var loading = valueOf(context.state, ["importLoading"], false) === true;
    var closed = competenceIsClosed(entities.competence);
    var importError = valueOf(context.state, ["importError"], "");
    var fileTypes = [
      { value: "auto", label: "Detectar automaticamente" },
      { value: "txt_clock", label: "TXT estruturado" },
    ];
    var dropzone = component(context.components, ["ImportDropzone", "importDropzone"], {
      id: "importFile",
      inputId: "importFile",
      action: "select-import-file",
      accept: ".txt,text/plain",
      disabled: loading || closed,
      file: valueOf(context.state, ["selectedImportFile", "arquivoSelecionado"], null),
      title: "Arraste o arquivo aqui",
      description: "ou escolha um arquivo do computador",
    }, function () {
      return '<label class="import-dropzone' + (loading || closed ? " is-disabled" : "") + '" for="importFile" data-action="open-file-picker"><span class="import-dropzone__icon" aria-hidden="true">⇧</span><strong>Arraste o arquivo aqui</strong><span>ou escolha um arquivo do computador</span><small>Somente TXT estruturado nesta etapa</small><input id="importFile" name="importFile" type="file" accept=".txt,text/plain" data-action="select-import-file"' + (loading || closed ? " disabled" : "") + "></label>";
    });

    return [
      '<section class="screen screen--imports" data-screen="imports">', demoBanner(),
      pageHeader(context.components, { title: "Importações", subtitle: companyName(entities.company) + " · " + formatCompetence(entities.competence), breadcrumbs: competenceBreadcrumbs(entities, "Importações") }),
      competencyAreaNavigation("imports"),
      closedCompetenceNotice(entities.competence),
      '<section class="work-card competency-hero"><div>' + statusChip(context.components, entities.competence.status, entities.competence.statusLabel) + '</div><dl class="summary-grid summary-grid--four">' + summaryItem("Empresa", companyName(entities.company)) + summaryItem("Competência", formatCompetence(entities.competence)) + summaryItem("Arquivos recebidos", valueOf(entities.competence, ["fileCount", "quantidadeArquivos"], 0)) + summaryItem("Pendências", valueOf(entities.competence, ["pendingCount", "quantidadePendencias"], 0)) + "</dl></section>",
      '<div class="content-grid content-grid--form">',
      '<form class="work-card import-form" data-form="import" data-action="analyze-import"' + (closed ? ' aria-disabled="true"' : "") + ">",
      '<fieldset class="field"><legend>Tipo de arquivo</legend><div class="segmented-options segmented-options--wrap">',
      fileTypes.map(function (type, index) {
        var typeValue = valueOf(type, ["value", "id"], "auto");
        var checked = idsEqual(typeValue, valueOf(context.state, ["importType", "tipoImportacao"], "auto")) || (index === 0 && !valueOf(context.state, ["importType", "tipoImportacao"], null));
        return '<label><input type="radio" name="importType" value="' + escapeHtml(typeValue) + '" data-action="select-import-type"' + (checked ? " checked" : "") + (closed ? " disabled" : "") + "><span>" + escapeHtml(valueOf(type, ["label", "nome"], typeValue)) + "</span></label>";
      }).join(""),
      "</div></fieldset>",
      dropzone,
      '<div class="form-footer"><p class="helper-text">' + (closed ? "Reabra a competência para analisar novos arquivos." : online ? "A análise salva o arquivo original, mas só cria marcações depois da sua confirmação." : "A API está offline; a análise usará dados de demonstração e não enviará o arquivo.") + '</p><button class="button button--primary" type="submit" data-action="analyze-import"' + (loading || closed ? " disabled" : "") + ">" + (loading ? "Analisando..." : "Analisar arquivo") + "</button></div>",
      "</form>",
      '<aside class="context-note"><strong>Como funciona</strong><ol><li>O original é preservado.</li><li>O sistema sugere uma interpretação.</li><li>Você confere e corrige.</li><li>Só então confirma o resultado.</li></ol></aside>',
      "</div>",
      importError ? '<div class="inline-feedback inline-feedback--error" role="alert"><strong>Erro na importação</strong><span>' + escapeHtml(importError) + "</span></div>" : "",
      importAnalysisCard(context, analysis),
      "</section>",
    ].join("");
  }

  function rowSuggestion(row) {
    var explicit = valueOf(row, ["interpretacaoSugerida", "suggestedLabel", "suggestionLabel"], "");
    if (explicit) return explicit;
    var suggestion = valueOf(row, ["suggestion", "suggested", "interpretacaoSugerida"], {}) || {};
    return [
      valueOf(suggestion, ["entry", "entrada"], null),
      valueOf(suggestion, ["breakStart", "breakOut", "saidaIntervalo", "saida_intervalo", "saida_almoco"], null),
      valueOf(suggestion, ["breakEnd", "breakIn", "retorno", "retorno_intervalo", "retorno_almoco"], null),
      valueOf(suggestion, ["exit", "saida"], null),
    ].map(function (time) { return time || "—"; }).join(" / ");
  }

  function originalPunchValues(item) {
    var original = valueOf(item, ["originalPunches", "batidasOriginais"], null);
    if (!original) {
      var nested = valueOf(item, ["original", "originalData", "dadosOriginais"], {}) || {};
      original = valueOf(nested, ["punches", "batidas"], []);
    }
    return asArray(original).map(function (punch) {
      return typeof punch === "object" ? valueOf(punch, ["value", "time", "horario"], "") : punch;
    }).filter(Boolean);
  }

  function renderImportPreview(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Prévia da importação", "Selecione uma empresa e uma competência antes de revisar a importação.", true);
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    var closed = competenceIsClosed(entities.competence);
    var stateAnalysis = valueOf(context.state, ["importAnalysis", "analiseImportacao", "analysisResult"], null);
    var analysis = stateAnalysis || (!online ? valueOf(context.data, ["importAnalysis", "analiseImportacao"], {}) : {}) || {};
    var analysisCompanyId = valueOf(analysis, ["companyId", "empresaId", "empresa_id"], null);
    var analysisCompetenceId = valueOf(analysis, ["competenceId", "competenciaId", "competencia_id"], null);
    if (!idsEqual(analysisCompanyId, idOf(entities.company)) || !idsEqual(analysisCompetenceId, idOf(entities.competence))) analysis = {};
    var rows = asArray(valueOf(context.state, ["importPreviewRows", "linhasPrevia"], null));
    if (!rows.length) rows = asArray(valueOf(analysis, ["rows", "linhas"], null));
    if (!rows.length && !online) rows = collection(context.data, ["importPreviewRows", "linhasPrevia"]);
    rows = rows.filter(function (row) {
      return idsEqual(valueOf(row, ["companyId", "empresaId", "empresa_id"], null), idOf(entities.company)) &&
        idsEqual(valueOf(row, ["competenceId", "competenciaId", "competencia_id"], null), idOf(entities.competence));
    });
    var filter = statusKey(valueOf(context.state, ["importPreviewFilter", "previewFilter", "filtroPrevia"], "all"));
    filter = { todos: "all", pendencias: "pending", somente_pendencias: "pending" }[filter] || filter;
    var employeeFilter = valueOf(context.state, ["importPreviewEmployeeId", "previewEmployeeId", "funcionarioPreviaId"], "");
    var visibleRows = rows.filter(function (row) {
      if (filter === "pending" && !valueOf(row, ["hasPendingIssue", "temPendencia"], false)) return false;
      if (employeeFilter && !idsEqual(valueOf(row, ["employeeId", "funcionario_id"], null), employeeFilter)) return false;
      return true;
    });
    var fileName = valueOf(analysis, ["fileName", "nomeArquivo"], "Nenhum arquivo analisado");
    var hasAnalysis = Boolean(valueOf(analysis, ["fileName", "nomeArquivo"], ""));
    var analysisSaved = valueOf(analysis, ["saved", "salva", "confirmada"], false) === true;
    var selectedIds = asArray(valueOf(context.state, ["selectedImportRowIds", "registrosImportacaoSelecionados"], []));
    var confirming = valueOf(context.state, ["importConfirming"], false) === true;
    var conflicts = asArray(valueOf(context.state, ["importConflicts", "conflitosImportacao"], []));
    var selectedCount = rows.filter(function (row) { return selectedIds.some(function (id) { return idsEqual(id, idOf(row)); }); }).length;
    var visibleSelectable = visibleRows.filter(function (row) { return valueOf(row, ["employeeFound", "funcionarioEncontrado"], true) !== false; });
    var visibleSelectedCount = visibleSelectable.filter(function (row) { return selectedIds.some(function (id) { return idsEqual(id, idOf(row)); }); }).length;
    var allVisibleSelected = visibleSelectable.length > 0 && visibleSelectedCount === visibleSelectable.length;
    var mixedVisibleSelection = visibleSelectedCount > 0 && !allVisibleSelected;

    var table = visibleRows.length ? [
      '<div class="table-frame table-frame--tall"><table class="data-table import-preview-table">',
      '<thead><tr><th class="selection-cell"><input type="checkbox" data-action="toggle-all-import-rows" aria-label="Selecionar todos os registros importáveis visíveis"' + (allVisibleSelected ? " checked" : "") + (mixedVisibleSelection ? ' aria-checked="mixed" data-indeterminate="true"' : "") + (closed ? " disabled" : "") + '></th><th>Funcionário</th><th>Data</th><th>Batidas originais</th><th>Interpretação sugerida</th><th>Status</th><th>Pendências</th></tr></thead><tbody>',
      visibleRows.map(function (row) {
        var punches = originalPunchValues(row);
        var rowId = idOf(row);
        var employeeFound = valueOf(row, ["employeeFound", "funcionarioEncontrado"], true) !== false;
        var outsideCompetence = valueOf(row, ["outsideCompetence", "foraDaCompetencia", "fora_da_competencia"], false) === true;
        var selected = selectedIds.some(function (id) { return idsEqual(id, rowId); });
        var issues = asArray(valueOf(row, ["issues", "pendencias"], [])).map(function (issue) {
          return typeof issue === "string" ? issue : valueOf(issue, ["message", "mensagem", "detail"], "Revisão necessária.");
        });
        var observation = valueOf(row, ["observation", "observacao"], "") || issues.join(" ");
        var sourceName = valueOf(row, ["employeeSourceName", "nomeFuncionarioOrigem", "employeeName", "funcionario", "nomeFuncionario"], "—");
        var registeredName = valueOf(row, ["employeeRegisteredName", "nomeFuncionarioCadastrado"], "");
        return [
          '<tr class="preview-row' + (!employeeFound ? " has-unmatched-employee" : "") + (outsideCompetence ? " is-outside-competence" : "") + '" data-preview-row-id="' + escapeHtml(rowId) + '">',
          '<td class="selection-cell"><input type="checkbox" data-action="toggle-import-row" data-preview-row-id="' + escapeHtml(rowId) + '" aria-label="Selecionar registro de ' + escapeHtml(sourceName) + '"' + (selected ? " checked" : "") + (!employeeFound || closed ? " disabled" : "") + "></td>",
          "<td><strong>" + escapeHtml(registeredName || sourceName) + "</strong>" + (registeredName && registeredName !== sourceName ? "<small>Origem: " + escapeHtml(sourceName) + "</small>" : "") + (!employeeFound ? '<span class="preview-warning preview-warning--danger">Funcionário não cadastrado</span>' : "") + "</td>",
          "<td>" + escapeHtml(formatDate(valueOf(row, ["date", "data"], null), true)) + (outsideCompetence ? '<span class="preview-warning">Data fora da competência</span>' : "") + "</td>",
          '<td><span class="original-data">' + escapeHtml(punches.length ? punches.join(", ") : "Sem batidas") + "</span></td>",
          '<td><span class="suggested-data">' + escapeHtml(rowSuggestion(row)) + "</span></td>",
          "<td>" + statusChip(context.components, valueOf(row, ["status", "situacao"], "conferir"), valueOf(row, ["statusLabel"], "")) + "</td>",
          '<td class="preview-issues">' + escapeHtml(observation || "—") + "</td>",
          "</tr>",
        ].join("");
      }).join(""),
      "</tbody></table></div>",
    ].join("") : emptyState(context.components, hasAnalysis ? "Nenhum registro neste filtro" : "Nenhuma análise disponível", hasAnalysis ? "Altere os filtros para visualizar outras linhas da prévia." : "Volte para Importações e analise um arquivo desta competência.", hasAnalysis ? null : { label: "Voltar para Importações", route: "imports", action: "navigate" });

    return [
      '<section class="screen screen--import-preview" data-screen="import-preview">', demoBanner(),
      pageHeader(context.components, {
        title: "Prévia da importação",
        subtitle: "O que o sistema entendeu deste arquivo?",
        breadcrumbs: competenceBreadcrumbs(entities, "Importações", "Prévia"),
      }),
      competencyAreaNavigation("imports"),
      closedCompetenceNotice(entities.competence),
      '<section class="work-card import-summary"><div class="section-heading"><div><span class="eyebrow">Arquivo analisado</span><h2>' + escapeHtml(fileName) + "</h2></div>" + (analysisSaved ? statusChip(context.components, "confirmed", "Importação confirmada") : '<span class="unsaved-badge">Não salvo</span>') + "</div>",
      '<dl class="summary-grid summary-grid--four">',
      summaryItem("Empresa", valueOf(analysis, ["companyName", "empresaNome"], companyName(entities.company))),
      summaryItem("Competência", valueOf(analysis, ["competenceLabel", "competenciaLabel"], formatCompetence(entities.competence))),
      summaryItem("Formato", valueOf(analysis, ["detectedFormat", "formatoDetectado"], "—")),
      summaryItem("Funcionários", valueOf(analysis, ["employeeCount", "totalFuncionarios"], 0)),
      summaryItem("Registros", valueOf(analysis, ["recordCount", "totalRegistros"], rows.length)),
      summaryItem("Pendências", valueOf(analysis, ["pendingCount", "totalPendencias"], rows.filter(function (row) { return row.hasPendingIssue; }).length)),
      summaryItem("Não cadastrados", valueOf(analysis, ["unmatchedEmployeeCount", "totalFuncionariosNaoCadastrados"], rows.filter(function (row) { return row.employeeFound === false; }).length)),
      summaryItem("Fora da competência", valueOf(analysis, ["outsideCompetenceCount", "totalForaDaCompetencia"], rows.filter(function (row) { return row.outsideCompetence; }).length)),
      "</dl></section>",
      '<div class="toolbar toolbar--sticky"><div class="filter-group" role="group" aria-label="Filtrar prévia">',
      filterButton("Todos", "all", filter, "preview"), filterButton("Somente pendências", "pending", filter, "preview"),
      '</div><span class="preview-selection-count"><strong>' + escapeHtml(selectedCount) + "</strong> de " + escapeHtml(rows.length) + ' registros selecionados</span><label class="compact-field"><span>Funcionário</span><select data-action="filter-preview-employee"><option value="">Todos</option>' + selectOptions(entities.companyEmployees, employeeFilter, employeeName) + "</select></label></div>",
      conflicts.length ? '<div class="inline-feedback inline-feedback--warning" role="alert"><strong>Conflitos encontrados</strong><ul>' + conflicts.map(function (conflict) { return "<li>" + escapeHtml(conflict) + "</li>"; }).join("") + "</ul></div>" : "",
      table,
      '<footer class="screen-actions screen-actions--sticky"><button class="button button--ghost" type="button" data-route="imports" data-action="navigate"' + (confirming ? " disabled" : "") + '>Voltar</button><div><button class="button button--danger-ghost" type="button" data-action="discard-import"' + (hasAnalysis && !confirming ? "" : " disabled") + '><span>Descartar</span></button><button class="button button--primary" type="button" data-action="save-import-start-review" data-route="review"' + (selectedCount && !confirming && !analysisSaved && !closed ? "" : " disabled") + ">" + (confirming ? "Salvando importação..." : closed ? "Competência fechada" : analysisSaved ? "Importação confirmada" : "Salvar importação e iniciar conferência") + "</button></div></footer>",
      "</section>",
    ].join("");
  }

  function filterButton(label, filter, active, scope) {
    return '<button class="filter-button' + (filter === active ? " is-active" : "") + '" type="button" data-action="set-filter" data-filter="' + escapeHtml(filter) + '" data-filter-scope="' + escapeHtml(scope || "") + '" aria-pressed="' + (filter === active ? "true" : "false") + '">' + escapeHtml(label) + "</button>";
  }

  function renderCompetencies(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    var companyFilter = valueOf(context.state, ["competenciesCompanyId", "selectedCompanyId", "empresaId"], "");
    var statusFilter = valueOf(context.state, ["competenciesStatusFilter", "statusFilter", "filtroStatus"], "all");
    var rows = entities.competencies.filter(function (competence) {
      if (companyFilter && !idsEqual(valueOf(competence, ["companyId", "empresa_id"], null), companyFilter)) return false;
      if (statusFilter !== "all" && normalizeStatus(competence.status) !== statusFilter) return false;
      return true;
    });
    var table = rows.length ? [
      '<div class="table-frame"><table class="data-table competencies-table"><thead><tr><th>Empresa</th><th>Competência</th><th>Situação</th><th>Funcionários</th><th>Progresso</th><th>Pendências</th><th>Arquivos</th><th>Atualização</th><th><span class="sr-only">Ação</span></th></tr></thead><tbody>',
      rows.map(function (competence) {
        var company = findById(entities.companies, valueOf(competence, ["companyId", "empresa_id"], null));
        var progress = Number(valueOf(competence, ["progress", "progresso"], 0));
        return '<tr><td><strong>' + escapeHtml(companyName(company)) + "</strong></td><td>" + escapeHtml(formatCompetence(competence)) + "</td><td>" + statusChip(context.components, competence.status, competence.statusLabel) + "</td><td>" + escapeHtml(valueOf(competence, ["employeeCount", "quantidadeFuncionarios"], 0)) + '</td><td class="progress-cell">' + progressIndicator(context.components, progress, 100, "", progress) + "</td><td>" + escapeHtml(valueOf(competence, ["pendingCount", "quantidadePendencias"], 0)) + "</td><td>" + escapeHtml(valueOf(competence, ["fileCount", "quantidadeArquivos"], 0)) + "</td><td>" + escapeHtml(formatDateTime(valueOf(competence, ["updatedAt", "updated_at"], null))) + '</td><td><button class="table-link" type="button" data-action="open-competence" data-route="competency-detail" data-competence-id="' + escapeHtml(idOf(competence)) + '">Abrir</button></td></tr>';
      }).join(""),
      "</tbody></table></div>",
    ].join("") : emptyState(context.components, "Nenhuma competência encontrada", "Ajuste os filtros ou crie uma nova competência.");
    return [
      '<section class="screen screen--competencies" data-screen="competencies">', demoBanner(),
      pageHeader(context.components, { title: "Competências", subtitle: "Cada competência funciona como uma pasta digital do fechamento.", actions: [{ label: "Nova competência", variant: "button--primary", action: "new-competence" }] }),
      '<div class="toolbar"><label class="compact-field"><span>Empresa</span><select data-action="filter-competencies-company"><option value="">Todas</option>' + selectOptions(entities.companies, companyFilter, companyName) + '</select></label><div class="filter-group" role="group" aria-label="Situação">',
      filterButton("Todas", "all", statusFilter, "competencies"), filterButton("Abertas", "aberta", statusFilter, "competencies"), filterButton("Em conferência", "em_conferencia", statusFilter, "competencies"), filterButton("Conferidas", "conferida", statusFilter, "competencies"), filterButton("Fechadas", "fechada", statusFilter, "competencies"),
      "</div></div>",
      '<section class="work-card">' + table + "</section></section>",
    ].join("");
  }

  function competencyTabs(active) {
    return '<nav class="tabs" aria-label="Conteúdo da competência">' + [
      ["summary", "Resumo"], ["employees", "Funcionários"], ["files", "Arquivos"], ["history", "Histórico"],
    ].map(function (tab) {
      return '<button type="button" role="tab" data-action="set-competency-tab" data-tab="' + tab[0] + '" aria-selected="' + (active === tab[0] ? "true" : "false") + '" class="tab' + (active === tab[0] ? " is-active" : "") + '">' + tab[1] + "</button>";
    }).join("") + "</nav>";
  }

  function normalizeCompetencyTab(value) {
    var key = statusKey(value || "summary");
    return {
      resumo: "summary",
      summary: "summary",
      funcionarios: "employees",
      employees: "employees",
      arquivos: "files",
      files: "files",
      historico: "history",
      history: "history",
    }[key] || "summary";
  }

  function activityTimeline(context, items) {
    return component(context.components, ["ActivityTimeline", "activityTimeline"], { items: items, activities: items }, function () {
      if (!items.length) return emptyState(context.components, "Nenhuma atividade disponível", "Esta versão não mantém uma trilha detalhada de auditoria da competência.");
      return '<ol class="activity-timeline">' + items.map(function (item) {
        return '<li><span class="activity-timeline__marker" aria-hidden="true"></span><div><div class="activity-timeline__meta"><strong>' + escapeHtml(valueOf(item, ["title", "titulo"], "Atividade")) + "</strong><time>" + escapeHtml(formatDateTime(valueOf(item, ["at", "data", "createdAt"], null))) + "</time></div><p>" + escapeHtml(valueOf(item, ["description", "descricao"], "")) + "</p><small>" + escapeHtml(valueOf(item, ["actor", "autor"], "Sistema")) + "</small></div></li>";
      }).join("") + "</ol>";
    });
  }

  function filesForCompetence(context, competence) {
    if (!competence) return [];
    return collection(context.data, ["files", "arquivos"]).filter(function (file) {
      return idsEqual(valueOf(file, ["competenceId", "competenciaId", "competencia_id"], null), idOf(competence));
    });
  }

  function activitiesForCompetence(context, competence) {
    if (!competence) return [];
    return collection(context.data, ["activityTimeline", "historicoCompetencia"]).filter(function (item) {
      return idsEqual(valueOf(item, ["competenceId", "competenciaId", "competencia_id"], null), idOf(competence));
    });
  }

  function competenceSummaryFor(context, competence) {
    var summaries = valueOf(context.data, ["competenceSummaries", "resumosCompetencia"], {});
    if (!summaries || typeof summaries !== "object") return null;
    return summaries[String(idOf(competence))] || null;
  }

  function availableSummaryValue(value) {
    return value === null || value === undefined || value === "" ? "Indisponível" : value;
  }

  function summaryDuration(value, minutes) {
    if (value !== null && value !== undefined && value !== "") return value;
    if (minutes === null || minutes === undefined || minutes === "") return "Indisponível";
    return formatDuration(minutes);
  }

  function summarySituationChip(components, value) {
    var key = statusKey(value);
    if (key === "conferido" || key === "confirmed") return statusChip(components, "normal", "Conferido");
    if (key === "pendente" || key === "pending") return statusChip(components, "conferir", "Pendente");
    return statusChip(components, "sem_expediente", "Indisponível");
  }

  function competenceIsClosed(competence) {
    return normalizeStatus(competence && competence.status) === "fechada";
  }

  function competenceLifecycleAction(context, competence) {
    var closed = competenceIsClosed(competence);
    var loading = valueOf(context.state, ["competenceLifecycleLoading"], false) === true;
    var pendingAction = valueOf(context.state, ["competenceLifecycleAction"], "");
    var label = closed ? "Reabrir competência" : "Fechar competência";
    if (loading) {
      label = pendingAction === "reabrir" ? "Reabrindo..." : pendingAction === "validar" ? "Verificando..." : "Fechando...";
    }
    return {
      label: label,
      variant: closed ? "button--secondary" : "button--danger-ghost",
      action: closed ? "request-reopen-competence" : "request-close-competence",
      disabled: loading,
    };
  }

  function closedCompetenceNotice(competence) {
    if (!competenceIsClosed(competence)) return "";
    var closedAt = valueOf(competence, ["closedAt", "data_fechamento"], null);
    var dateLabel = closedAt ? " em " + formatDate(closedAt) : "";
    return '<div class="inline-feedback" role="note"><strong>Competência fechada' + escapeHtml(dateLabel) + '</strong><span>Os dados permanecem disponíveis para consulta e exportação. Reabra a competência para importar, editar ou confirmar registros.</span></div>';
  }

  function lifecycleErrorNotice(context) {
    var message = valueOf(context.state, ["competenceLifecycleError"], "");
    return message ? '<div class="inline-feedback inline-feedback--error" role="alert"><strong>Não foi possível concluir a ação</strong><span>' + escapeHtml(message) + "</span></div>" : "";
  }

  function onlineSummaryHeader(context, entities) {
    var closed = competenceIsClosed(entities.competence);
    return pageHeader(context.components, {
      eyebrow: companyName(entities.company),
      title: formatCompetence(entities.competence),
      subtitle: valueOf(entities.competence, ["statusLabel"], statusMeta(entities.competence.status).label),
      breadcrumbs: competenceBreadcrumbs(entities, "Resumo"),
      actions: [
        { label: "Adicionar arquivos", variant: "button--secondary", route: "imports", action: "navigate", disabled: closed },
        { label: closed ? "Ver conferência" : "Continuar conferência", variant: "button--primary", route: "review", action: "navigate" },
        { label: "Exportar", route: "competency-exports", action: "navigate" },
        competenceLifecycleAction(context, entities.competence),
      ],
    });
  }

  function renderOnlineCompetencySummary(context, entities) {
    var competence = entities.competence;
    var loading = valueOf(context.state, ["competenceSummaryLoading"], false) === true;
    var error = valueOf(context.state, ["competenceSummaryError"], "");
    var summary = competenceSummaryFor(context, competence);
    var prefix = '<section class="screen screen--competency-summary" data-screen="competency-summary" data-competence-id="' + escapeHtml(idOf(competence)) + '">' +
      onlineSummaryHeader(context, entities) + competencyAreaNavigation("competency-summary") + lifecycleErrorNotice(context) + closedCompetenceNotice(competence);

    if (loading) {
      return prefix + '<section class="work-card" aria-busy="true"><div class="review-loading" role="status"><strong>Carregando resumo da competência</strong><p>Consultando a apuração mais recente.</p></div></section></section>';
    }
    if (error) {
      return prefix + '<section class="work-card"><div class="empty-state" role="alert"><span aria-hidden="true">!</span><h2>Resumo indisponível</h2><p>' + escapeHtml(error) + '</p><button class="button button--primary" type="button" data-action="retry-competence-summary">Tentar novamente</button></div></section></section>';
    }
    if (!summary) {
      return prefix + '<section class="work-card"><div class="empty-state" role="status"><span aria-hidden="true">□</span><h2>Resumo indisponível</h2><p>A API não retornou a apuração desta competência.</p><button class="button button--primary" type="button" data-action="retry-competence-summary">Tentar novamente</button></div></section></section>';
    }

    var general = summary.general || {};
    var rows = asArray(summary.rows);
    var table = rows.length ? [
      '<div class="table-frame"><table class="data-table"><caption class="sr-only">Resumo da apuração por funcionário</caption><thead><tr>',
      '<th scope="col">Funcionário</th><th scope="col">Dias processados</th><th scope="col">Atrasos</th><th scope="col">Extras</th><th scope="col">Faltas</th><th scope="col">Atestados</th><th scope="col">Pendências</th><th scope="col">Situação</th>',
      "</tr></thead><tbody>",
      rows.map(function (row) {
        var name = availableSummaryValue(row.employeeName);
        var code = row.employeeCode === null || row.employeeCode === undefined || row.employeeCode === "" ? "" : '<small>Código ' + escapeHtml(row.employeeCode) + "</small>";
        return '<tr><th scope="row"><strong>' + escapeHtml(name) + "</strong>" + code + "</th>" +
          "<td>" + escapeHtml(availableSummaryValue(row.processedDays)) + "</td>" +
          "<td>" + escapeHtml(summaryDuration(row.delays, row.delayMinutes)) + "</td>" +
          "<td>" + escapeHtml(summaryDuration(row.extras, row.extraMinutes)) + "</td>" +
          "<td>" + escapeHtml(availableSummaryValue(row.absences)) + "</td>" +
          "<td>" + escapeHtml(availableSummaryValue(row.certificates)) + "</td>" +
          "<td>" + escapeHtml(availableSummaryValue(row.pending)) + "</td>" +
          "<td>" + summarySituationChip(context.components, row.situation) + "</td></tr>";
      }).join(""),
      "</tbody></table></div>",
    ].join("") : emptyState(
      context.components,
      "Nenhum funcionário no resumo",
      "Cadastre um funcionário nesta empresa para incluí-lo na próxima apuração.",
      { label: "Cadastrar funcionário", route: "company-employees", action: "navigate" }
    );

    return prefix +
      '<section class="work-card competency-hero"><div>' + statusChip(context.components, competence.status, competence.statusLabel) + '</div><dl class="summary-grid">' +
        summaryItem("Funcionários", availableSummaryValue(general.employees)) +
        summaryItem("Conferidos", availableSummaryValue(general.confirmed)) +
        summaryItem("Pendentes", availableSummaryValue(general.pending)) +
        summaryItem("Dias com pendência", availableSummaryValue(general.pendingDays)) +
        summaryItem("Arquivos recebidos", availableSummaryValue(general.totalFiles)) +
      '</dl></section><section class="work-card"><div class="section-heading"><div><h2>Resumo por funcionário</h2><p>Totais calculados pela apuração desta competência.</p></div></div>' + table + "</section></section>";
  }

  function renderCompetencySummary(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Resumo da competência", "Selecione uma empresa e uma competência para continuar.", true);
    if (valueOf(context.state, ["apiMode"], "offline") === "online") return renderOnlineCompetencySummary(context, entities);
    var competence = entities.competence;
    var files = filesForCompetence(context, competence);
    var activities = activitiesForCompetence(context, competence);
    var employeeCount = valueOf(competence, ["employeeCount", "quantidadeFuncionarios"], entities.companyEmployees.length);
    var confirmedCount = valueOf(competence, ["confirmedEmployees", "funcionariosConferidos"], 0);
    var progress = Number(valueOf(competence, ["progress", "progresso"], 0));
    var closed = competenceIsClosed(competence);
    return [
      '<section class="screen screen--competency-summary" data-screen="competency-summary" data-competence-id="' + escapeHtml(idOf(competence)) + '">', demoBanner(),
      pageHeader(context.components, {
        eyebrow: companyName(entities.company),
        title: formatCompetence(competence),
        subtitle: valueOf(competence, ["statusLabel"], statusMeta(competence.status).label),
        breadcrumbs: competenceBreadcrumbs(entities, "Resumo"),
        actions: [
          { label: "Adicionar arquivos", variant: "button--secondary", route: "imports", action: "navigate", disabled: closed },
          { label: closed ? "Ver conferência" : "Continuar conferência", variant: "button--primary", route: "review", action: "navigate" },
          { label: "Exportar", route: "competency-exports", action: "navigate" },
          competenceLifecycleAction(context, competence),
        ],
      }),
      competencyAreaNavigation("competency-summary"),
      lifecycleErrorNotice(context), closedCompetenceNotice(competence),
      '<section class="work-card competency-hero"><div>' + statusChip(context.components, competence.status, competence.statusLabel) + '</div><dl class="summary-grid">' +
        summaryItem("Funcionários", employeeCount) +
        summaryItem("Funcionários conferidos", confirmedCount) +
        summaryItem("Pendências", valueOf(competence, ["pendingCount", "quantidadePendencias"], 0)) +
        summaryItem("Arquivos recebidos", valueOf(competence, ["fileCount", "quantidadeArquivos"], files.length)) +
        summaryItem("Última atualização", formatDateTime(valueOf(competence, ["updatedAt", "updated_at"], null))) +
      "</dl></section>",
      '<section class="work-card"><div class="competency-overview"><section class="overview-progress"><h2>Progresso da conferência</h2>' + progressIndicator(context.components, progress, 100, "Competência conferida", progress) + '</section><dl class="operational-summary">' +
        summaryItem("Funcionários pendentes", valueOf(competence, ["pendingEmployees", "funcionariosPendentes"], Math.max(Number(employeeCount) - Number(confirmedCount), 0))) +
        summaryItem("Dias com inconsistências", valueOf(competence, ["inconsistentDays", "diasInconsistentes"], 0)) +
        summaryItem("Status", valueOf(competence, ["statusLabel"], statusMeta(competence.status).label)) +
        summaryItem("Arquivos", files.length) +
      '</dl></div><section class="subsection"><div class="section-heading"><div><h2>Atividade recente</h2><p>Eventos disponíveis na sessão atual de demonstração.</p></div><button class="text-button" type="button" data-action="navigate" data-route="competency-history">Ver atividades</button></div>' + activityTimeline(context, activities.slice(0, 4)) + "</section></section></section>",
    ].join("");
  }

  function renderCompetencyDetail(state, data, components) {
    return renderCompetencySummary(state, data, components);
  }

  function renderCompetencyFiles(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Arquivos", "Selecione uma empresa e uma competência para visualizar arquivos.", true);
    var files = filesForCompetence(context, entities.competence);
    var closed = competenceIsClosed(entities.competence);
    var rows = files.map(function (file) {
      return '<tr><td><strong>' + escapeHtml(valueOf(file, ["name", "nome"], "Arquivo")) + "</strong><small>" + escapeHtml(formatFileSize(valueOf(file, ["sizeBytes", "tamanho"], null))) + "</small></td><td>" + escapeHtml(valueOf(file, ["detectedFormat", "typeLabel", "tipo"], "—")) + "</td><td>" + escapeHtml(formatDateTime(valueOf(file, ["uploadedAt", "createdAt"], null))) + "</td><td>" + escapeHtml(valueOf(file, ["punchCount", "recordCount"], 0)) + "</td><td>" + escapeHtml(valueOf(file, ["pendingCount"], 0)) + '</td><td><button class="table-link" type="button" data-action="open-original-file" data-file-id="' + escapeHtml(idOf(file)) + '">Ver original</button></td></tr>';
    }).join("");
    return '<section class="screen screen--competency-files" data-screen="competency-files">' + demoBanner() + pageHeader(context.components, {
      title: "Arquivos",
      subtitle: companyName(entities.company) + " · " + formatCompetence(entities.competence),
      breadcrumbs: competenceBreadcrumbs(entities, "Arquivos"),
      actions: [{ label: "Adicionar arquivos", variant: "button--primary", route: "imports", action: "navigate", disabled: closed }],
    }) + competencyAreaNavigation("competency-files") + closedCompetenceNotice(entities.competence) + '<section class="work-card">' + (rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Arquivo</th><th>Formato</th><th>Recebido em</th><th>Registros</th><th>Pendências</th><th><span class="sr-only">Ação</span></th></tr></thead><tbody>' + rows + "</tbody></table></div>" : emptyState(context.components, "Nenhum arquivo recebido", closed ? "A competência está fechada e continua disponível para consulta." : "Adicione documentos para iniciar a importação.", closed ? null : { label: "Adicionar arquivos", route: "imports", action: "navigate" })) + "</section></section>";
  }

  function renderCompetencyHistory(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Histórico", "Selecione uma empresa e uma competência para visualizar o histórico.", true);
    var activities = activitiesForCompetence(context, entities.competence);
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    return '<section class="screen screen--competency-history" data-screen="competency-history">' + demoBanner() + pageHeader(context.components, {
      title: "Histórico",
      subtitle: companyName(entities.company) + " · " + formatCompetence(entities.competence),
      breadcrumbs: competenceBreadcrumbs(entities, "Histórico"),
    }) + competencyAreaNavigation("competency-history") + '<section class="work-card">' + (online ? '<p class="context-note"><strong>Escopo do MVP:</strong> marcações e arquivos originais são preservados, mas esta versão não mantém um log detalhado de auditoria.</p>' : "") + activityTimeline(context, activities) + "</section></section>";
  }

  function currentSlots(day) {
    var current = valueOf(day, ["currentInterpretation", "interpretacaoAtual"], null);
    if (!current) {
      var nestedCurrent = valueOf(day, ["current", "atual"], {}) || {};
      current = valueOf(nestedCurrent, ["slots", "horarios"], nestedCurrent);
    }
    if (!current) current = valueOf(day, ["suggestion", "suggested", "interpretacaoSugerida"], {}) || {};
    return {
      entry: valueOf(current, ["entry", "entrada"], ""),
      breakStart: valueOf(current, ["breakStart", "breakOut", "saidaIntervalo", "saida_intervalo", "saida_almoco"], ""),
      breakEnd: valueOf(current, ["breakEnd", "breakIn", "retorno", "retorno_intervalo", "retorno_almoco"], ""),
      exit: valueOf(current, ["exit", "saida"], ""),
    };
  }

  function dayDate(day) {
    return valueOf(day, ["date", "data"], "");
  }

  function dayStatus(day) {
    var current = valueOf(day, ["current", "atual"], {}) || {};
    return valueOf(current, ["situation", "status", "situacao"], valueOf(day, ["status", "situacao", "status_dia"], "conferir"));
  }

  function dayConfirmed(day) {
    var review = valueOf(day, ["review", "conferencia"], {}) || {};
    var reviewState = valueOf(review, ["state", "status"], valueOf(day, ["reviewState"], ""));
    return valueOf(day, ["confirmed", "conferido"], false) === true || ["confirmed", "conferido"].indexOf(statusKey(reviewState)) !== -1;
  }

  function dayMetric(day, keys, nestedKeys) {
    var direct = valueOf(day, keys, undefined);
    if (direct !== undefined) return direct;
    var current = valueOf(day, ["current", "atual"], {}) || {};
    return valueOf(current, nestedKeys || keys, null);
  }

  function reviewDays(context, entities) {
    var days = asArray(valueOf(context.state, ["reviewDays", "attendanceDays", "diasConferencia", "dias"], null));
    if (!days.length) days = collection(context.data, ["attendanceDays", "dias"]);
    var employeeId = entities.employee ? idOf(entities.employee) : null;
    var competenceId = entities.competence ? idOf(entities.competence) : null;
    if (!employeeId || !competenceId) return [];
    return days.filter(function (day) {
      var dayEmployeeId = valueOf(day, ["employeeId", "funcionario_id"], null);
      var dayCompetenceId = valueOf(day, ["competenceId", "competencia_id"], null);
      return idsEqual(dayEmployeeId, employeeId) && idsEqual(dayCompetenceId, competenceId);
    });
  }

  function editableTimeCell(context, day, field, value, label, readonly) {
    return '<input class="editable-time-cell" type="text" inputmode="numeric" autocomplete="off" spellcheck="false" value="' + escapeHtml(value || "") + '" placeholder="—" aria-label="' + escapeHtml(label + " de " + formatDate(dayDate(day), true)) + '" data-action="edit-time" data-day-id="' + escapeHtml(idOf(day)) + '" data-field="' + escapeHtml(field) + '"' + (readonly ? " disabled" : "") + ">";
  }

  function fallbackAttendanceTable(context, days, selectedDay, selectedIds, readonly) {
    if (!days.length) return emptyState(context.components, "Nenhum dia neste filtro", "Escolha outro filtro ou funcionário.");
    return [
      '<div class="attendance-table-wrap" tabindex="0"><table class="attendance-table" data-density="compact" aria-label="Conferência diária">',
      '<thead><tr>' + (readonly ? "" : '<th scope="col" class="select-column"><input type="checkbox" data-action="toggle-all-days" aria-label="Selecionar todos os dias visíveis"></th>') + '<th scope="col" class="attendance-table__day-heading">Dia</th><th scope="col" class="attendance-table__time-heading">Entrada</th><th scope="col" class="attendance-table__time-heading">Saída intervalo</th><th scope="col" class="attendance-table__time-heading">Retorno</th><th scope="col" class="attendance-table__time-heading">Saída</th><th scope="col" class="attendance-table__number-heading">Jornada</th><th scope="col" class="attendance-table__number-heading">Saldo</th><th scope="col">Situação</th><th scope="col">Observação</th></tr></thead><tbody>',
      days.map(function (day) {
        var slots = currentSlots(day);
        var selected = selectedDay && idsEqual(idOf(day), idOf(selectedDay));
        var checked = selectedIds.some(function (id) { return idsEqual(id, idOf(day)); });
        var worked = dayMetric(day, ["workedMinutes", "jornadaApuradaMinutos"], ["workedMinutes", "apuradaMinutos"]);
        var balance = dayMetric(day, ["balanceMinutes", "saldoMinutos"], ["balanceMinutes", "saldoMinutos"]);
        return [
          '<tr class="attendance-row' + (selected ? " is-selected" : "") + (dayConfirmed(day) ? " is-confirmed" : "") + '" data-day-id="' + escapeHtml(idOf(day)) + '">',
          readonly ? "" : '<td class="select-column"><input type="checkbox" data-action="toggle-day-selection" data-day-id="' + escapeHtml(idOf(day)) + '" aria-label="Selecionar ' + escapeHtml(formatDate(dayDate(day), true)) + '"' + (checked ? " checked" : "") + "></td>",
          '<th scope="row"><button class="day-selector" type="button" data-action="select-day" data-day-id="' + escapeHtml(idOf(day)) + '" aria-controls="day-details-panel"' + (selected ? ' aria-current="date"' : "") + '><strong class="day-number">' + escapeHtml(valueOf(day, ["day"], String(dayDate(day)).slice(-2))) + "</strong><span>" + escapeHtml(valueOf(day, ["weekdayShort"], typeof utils.formatWeekday === "function" ? utils.formatWeekday(dayDate(day)) : "")) + "</span></button></th>",
          "<td>" + editableTimeCell(context, day, "entry", slots.entry, "Entrada", readonly) + "</td>",
          "<td>" + editableTimeCell(context, day, "breakStart", slots.breakStart, "Saída do intervalo", readonly) + "</td>",
          "<td>" + editableTimeCell(context, day, "breakEnd", slots.breakEnd, "Retorno do intervalo", readonly) + "</td>",
          "<td>" + editableTimeCell(context, day, "exit", slots.exit, "Saída", readonly) + "</td>",
          '<td class="duration-cell">' + escapeHtml(formatDuration(worked)) + "</td>",
          '<td class="balance-cell balance-cell--' + (Number(balance) > 0 ? "positive" : Number(balance) < 0 ? "negative" : "neutral") + '">' + escapeHtml(formatBalance(balance)) + "</td>",
          "<td>" + statusChip(context.components, dayStatus(day), valueOf(day, ["statusLabel"], "")) + "</td>",
          '<td><input class="observation-cell" type="text" value="' + escapeHtml(valueOf(day, ["observation", "observacao"], "")) + '" aria-label="Observação de ' + escapeHtml(formatDate(dayDate(day), true)) + '" data-action="edit-observation" data-day-id="' + escapeHtml(idOf(day)) + '"' + (readonly ? " disabled" : "") + "></td>",
          "</tr>",
        ].join("");
      }).join(""),
      "</tbody></table></div>",
    ].join("");
  }

  function autosaveIndicator(context) {
    var status = valueOf(context.state, ["autosaveStatus", "saveStatus", "estadoSalvamento"], "saved");
    return component(context.components, ["AutosaveIndicator", "autosaveIndicator"], { status: status, state: status }, function () {
      var meta = {
        saving: { icon: "…", text: "Salvando..." },
        saved: { icon: "✓", text: "Alterações salvas" },
        unsaved: { icon: "!", text: "Alterações não salvas" },
        error: { icon: "×", text: "Erro ao salvar" },
      }[status] || { icon: "✓", text: "Alterações salvas" };
      return '<span class="autosave-indicator autosave-indicator--' + escapeHtml(status) + '" role="status"><span aria-hidden="true">' + meta.icon + "</span>" + meta.text + "</span>";
    });
  }

  function originalPunchesList(context, day) {
    var punches = originalPunchValues(day);
    var details = asArray(valueOf(day, ["originalPunchDetails", "detalhesBatidasOriginais"], null));
    return component(context.components, ["OriginalPunchesList", "originalPunchesList"], {
      day: day,
      punches: details.length ? details : punches,
      readonly: true,
    }, function () {
      if (!punches.length) return '<p class="muted-text">Nenhuma batida no arquivo original.</p>';
      return '<ol class="original-punches-list" aria-label="Batidas originais somente leitura">' + punches.map(function (punch, index) {
        var detail = details[index] || {};
        var line = valueOf(detail, ["sourceLine", "linhaOrigem", "line"], null);
        return '<li><time>' + escapeHtml(punch) + "</time>" + (line ? "<small>Linha " + escapeHtml(line) + "</small>" : "") + "</li>";
      }).join("") + "</ol>";
    });
  }

  function dayTimeline(context, day) {
    var history = asArray(valueOf(day, ["history", "historico"], null));
    return activityTimeline(context, history.map(function (item) {
      return {
        title: valueOf(item, ["title", "description", "descricao"], "Atividade"),
        description: valueOf(item, ["description", "descricao"], ""),
        at: valueOf(item, ["at", "data"], null),
        actor: valueOf(item, ["actor", "autor"], ""),
      };
    }));
  }

  function contextActions(day) {
    var punches = originalPunchValues(day);
    var status = normalizeStatus(dayStatus(day));
    if (dayConfirmed(day)) {
      return [{ label: "Reabrir conferência", action: "reopen-day", variant: "button--secondary" }];
    }
    if (!punches.length) {
      return [
        { label: "Registrar falta", action: "set-day-absence" },
        { label: "Adicionar atestado", action: "set-day-certificate" },
        { label: "Registrar folga", action: "set-day-dayoff" },
        { label: "Inserir horários manualmente", action: "focus-first-time", variant: "button--secondary" },
        { label: "Marcar como sem expediente", action: "set-day-no-schedule", variant: "button--ghost" },
      ];
    }
    if (["conferir", "inconsistente"].indexOf(status) !== -1) {
      return [
        { label: "Corrigir marcações", action: "focus-first-time" },
        { label: "Manter interpretação", action: "keep-interpretation" },
        { label: "Adicionar observação", action: "focus-observation", variant: "button--secondary" },
        { label: "Marcar como conferido", action: "confirm-day", variant: "button--primary" },
      ];
    }
    return [{ label: "Marcar dia como conferido", action: "confirm-day", variant: "button--primary" }];
  }

  function fallbackDayDetailsPanel(context, day, readonly) {
    if (!day) return emptyState(context.components, "Selecione um dia", "Os detalhes e as batidas originais aparecerão aqui.");
    var slots = currentSlots(day);
    var source = valueOf(day, ["source", "origem"], {}) || {};
    var issues = asArray(valueOf(day, ["issues", "pendencias"], null));
    var expected = dayMetric(day, ["expectedMinutes", "jornadaPrevistaMinutos"], ["expectedMinutes", "previstaMinutos"]);
    var worked = dayMetric(day, ["workedMinutes", "jornadaApuradaMinutos"], ["workedMinutes", "apuradaMinutos"]);
    var balance = dayMetric(day, ["balanceMinutes", "saldoMinutos"], ["balanceMinutes", "saldoMinutos"]);
    return [
      '<aside id="day-details-panel" class="day-details-panel" aria-label="Detalhes do dia selecionado" data-day-id="' + escapeHtml(idOf(day)) + '">',
      '<header class="day-details-panel__header"><div><span class="eyebrow">' + escapeHtml(valueOf(day, ["weekday"], "Dia selecionado")) + '</span><h2>' + escapeHtml(formatDate(dayDate(day))) + "</h2></div>" + statusChip(context.components, dayStatus(day), valueOf(day, ["statusLabel"], "")) + "</header>",
      '<section><h3>Batidas originais <span class="readonly-label">Somente leitura</span></h3>' + originalPunchesList(context, day) + "</section>",
      '<section><h3>Interpretação atual</h3><dl class="detail-grid">',
      summaryItem("Entrada", slots.entry || "—"), summaryItem("Saída intervalo", slots.breakStart || "—"), summaryItem("Retorno", slots.breakEnd || "—"), summaryItem("Saída", slots.exit || "—"),
      summaryItem("Jornada prevista", formatDuration(expected)), summaryItem("Jornada apurada", formatDuration(worked)), summaryItem("Saldo", formatBalance(balance)),
      "</dl><p class=\"difference-reason\"><strong>Motivo da diferença:</strong> " + escapeHtml(valueOf(day, ["differenceReason", "motivoDiferenca"], "Sem diferença relevante informada.") || "Sem diferença relevante informada.") + "</p></section>",
      '<section><h3>Pendências</h3>' + (issues.length ? '<ul class="issue-list">' + issues.map(function (issue) { return '<li class="issue-list__item"><span aria-hidden="true">!</span><span>' + escapeHtml(typeof issue === "string" ? issue : valueOf(issue, ["message", "mensagem"], "Revisão necessária.")) + "</span></li>"; }).join("") + "</ul>" : '<p class="muted-text">Nenhuma pendência ativa.</p>') + "</section>",
      '<section><h3>Origem</h3><dl class="source-details">' + summaryItem("Arquivo", valueOf(source, ["fileName", "arquivo", "nomeArquivo"], "—")) + summaryItem("Importado em", formatDateTime(valueOf(source, ["importedAt", "importadoEm"], null))) + summaryItem("Linhas de origem", asArray(valueOf(source, ["sourceLines", "linhasOrigem"], [])).join(", ") || "—") + '</dl><div class="button-row"><button class="button button--secondary" type="button" data-action="open-original-file" data-file-id="' + escapeHtml(valueOf(source, ["fileId"], "")) + '">Ver arquivo original</button><button class="button button--ghost" type="button" data-action="open-source-region">Ver região de origem</button></div></section>',
      '<section><h3>Histórico do dia</h3>' + dayTimeline(context, day) + "</section>",
      '<section class="context-actions"><h3>Ações</h3>' + (readonly
        ? '<p class="muted-text" role="note">Competência fechada: este dia está disponível somente para consulta.</p>'
        : '<div class="context-actions__buttons">' + contextActions(day).map(function (action) {
          return actionButton({ label: action.label, action: action.action, variant: action.variant || "button--secondary", attributes: ' data-day-id="' + escapeHtml(idOf(day)) + '"' });
        }).join("") + "</div>") + "</section>",
      "</aside>",
    ].join("");
  }

  function dayForComponents(day) {
    if (!day) return null;
    var source = valueOf(day, ["source", "origem"], {}) || {};
    var original = valueOf(day, ["original", "dadosOriginais"], {}) || {};
    var details = asArray(valueOf(day, ["originalPunchDetails", "detalhesBatidasOriginais"], []));
    var punches = details.length ? details.map(function (punch) {
      return Object.assign({}, punch, {
        value: valueOf(punch, ["value", "time", "horario"], ""),
        line: valueOf(punch, ["line", "sourceLine", "linhaOrigem"], null),
        page: valueOf(punch, ["page", "pagina"], null),
        region: valueOf(punch, ["region", "regiao"], null),
      });
    }) : originalPunchValues(day);
    var current = Object.assign({}, valueOf(day, ["current", "currentInterpretation", "interpretacaoAtual"], {}) || {}, currentSlots(day), {
      situation: dayStatus(day),
      observation: valueOf(day, ["observation", "observacao"], ""),
      expectedMinutes: dayMetric(day, ["expectedMinutes", "jornadaPrevistaMinutos"], ["expectedMinutes", "previstaMinutos"]),
      workedMinutes: dayMetric(day, ["workedMinutes", "jornadaApuradaMinutos"], ["workedMinutes", "apuradaMinutos"]),
      balanceMinutes: dayMetric(day, ["balanceMinutes", "saldoMinutos"], ["balanceMinutes", "saldoMinutos"]),
      differenceReason: valueOf(day, ["differenceReason", "motivoDiferenca"], ""),
    });
    return Object.assign({}, day, {
      current: current,
      original: Object.assign({}, original, source, {
        punches: punches,
        fileId: valueOf(source, ["fileId"], valueOf(original, ["fileId"], null)),
        fileName: valueOf(source, ["fileName", "arquivo", "nomeArquivo"], valueOf(original, ["fileName"], null)),
        importedAt: valueOf(source, ["importedAt", "importadoEm"], valueOf(original, ["importedAt"], null)),
        lines: asArray(valueOf(source, ["sourceLines", "linhasOrigem"], valueOf(original, ["lines"], []))),
        region: valueOf(source, ["region", "regiao"], valueOf(original, ["region"], null)) || (valueOf(source, ["canOpenRegion"], false) ? "Região de origem disponível" : null),
      }),
    });
  }

  function renderReview(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Conferência", "Selecione uma empresa e uma competência antes de abrir a conferência.", true);
    var closed = competenceIsClosed(entities.competence);
    var allDays = reviewDays(context, entities);
    var filter = statusKey(valueOf(context.state, ["reviewFilter", "attendanceFilter", "filtroConferencia"], "all"));
    filter = {
      todos: "all",
      todos_os_dias: "all",
      pendencias: "pending",
      nao_conferidos: "unconfirmed",
      ausencias: "absences",
    }[filter] || filter;
    var days = allDays.filter(function (day) {
      var normalized = normalizeStatus(dayStatus(day));
      var issues = asArray(valueOf(day, ["issues", "pendencias"], []));
      if (filter === "pending") return ["conferir", "inconsistente"].indexOf(normalized) !== -1 || issues.some(function (issue) { return !(issue && issue.resolved); });
      if (filter === "unconfirmed") return !dayConfirmed(day);
      if (filter === "absences") return ["falta", "atestado", "folga", "afastamento"].indexOf(normalized) !== -1;
      return true;
    });
    var selectedDayId = valueOf(context.state, ["selectedDayId", "dayId", "diaSelecionadoId"], null);
    var selectedDay = findById(allDays, selectedDayId) || days[0] || allDays[0] || null;
    var selection = closed ? [] : asArray(valueOf(context.state, ["selectedDayIds", "bulkSelection", "diasSelecionados"], []));
    var progressItems = collection(context.data, ["employeeProgress", "progressoFuncionarios"]);
    var employeeProgress = progressItems.find(function (item) { return entities.employee && idsEqual(valueOf(item, ["employeeId", "funcionario_id"], null), idOf(entities.employee)); }) || {};
    var position = valueOf(employeeProgress, ["position", "posicao"], Math.max(1, entities.companyEmployees.indexOf(entities.employee) + 1));
    var totalEmployees = valueOf(employeeProgress, ["totalEmployees", "totalFuncionarios"], entities.companyEmployees.length);
    var confirmedDays = valueOf(employeeProgress, ["confirmedDayCount", "diasConferidos"], allDays.filter(dayConfirmed).length);
    var eligibleDays = valueOf(employeeProgress, ["eligibleDayCount", "totalDias"], allDays.length);
    var reviewLoading = valueOf(context.state, ["reviewLoading"], false) === true;
    var table = reviewLoading && !allDays.length ? '<div class="review-loading" role="status"><strong>Carregando marcações...</strong><span>Buscando os dados persistidos desta competência.</span></div>' : component(context.components, ["AttendanceTable", "attendanceTable"], {
      days: days,
      rows: days,
      selectedDayId: selectedDay ? idOf(selectedDay) : null,
      selectedIds: selection,
      bulkSelection: selection,
      selectable: !closed,
      readonly: closed,
    }, function () { return fallbackAttendanceTable(context, days, selectedDay, selection, closed); });
    var componentDay = dayForComponents(selectedDay);
    var panel = component(context.components, ["DayDetailsPanel", "dayDetailsPanel"], {
      day: componentDay,
      selectedDay: componentDay,
      readonly: closed,
      file: componentDay ? {
        id: valueOf(componentDay.original, ["fileId"], null),
        name: valueOf(componentDay.original, ["fileName"], null),
        importedAt: valueOf(componentDay.original, ["importedAt"], null),
      } : null,
    }, function () { return fallbackDayDetailsPanel(context, selectedDay, closed); });

    return [
      '<section class="screen screen--review" data-screen="review">', demoBanner(),
      pageHeader(context.components, {
        title: "Conferência",
        subtitle: companyName(entities.company) + " · " + formatCompetence(entities.competence),
        breadcrumbs: competenceBreadcrumbs(entities, "Conferência"),
        actions: [{ label: closed ? "Somente leitura" : "Salvar agora", action: "save-now", disabled: closed }],
      }),
      competencyAreaNavigation("review"),
      closedCompetenceNotice(entities.competence),
      '<section class="review-toolbar work-card">',
      '<div class="employee-navigation"><button class="icon-button" type="button" data-action="previous-employee" aria-label="Funcionário anterior" title="Funcionário anterior (Alt + ↑)">←</button><label><span class="sr-only">Funcionário</span><select data-action="select-review-employee">' + selectOptions(entities.companyEmployees, entities.employee ? idOf(entities.employee) : "", employeeName) + '</select></label><button class="icon-button" type="button" data-action="next-employee" aria-label="Próximo funcionário" title="Próximo funcionário (Alt + ↓)">→</button><span class="position-label">' + escapeHtml(position) + " de " + escapeHtml(totalEmployees) + " funcionários</span></div>",
      '<div class="review-progress">' + progressIndicator(context.components, confirmedDays, eligibleDays, "Progresso") + (closed ? '<span class="autosave-indicator" role="status">Somente leitura</span>' : autosaveIndicator(context)) + "</div>",
      '<div class="filter-group review-filters" role="group" aria-label="Filtrar dias">' + filterButton("Todos os dias", "all", filter, "review") + filterButton("Pendências", "pending", filter, "review") + filterButton("Não conferidos", "unconfirmed", filter, "review") + filterButton("Ausências", "absences", filter, "review") + "</div>",
      "</section>",
      '<section class="bulk-actions' + (selection.length ? " is-active" : "") + '" aria-label="Ações em massa" aria-live="polite"><strong>' + (closed ? "Ações indisponíveis enquanto a competência estiver fechada" : selection.length + " registro" + (selection.length === 1 ? "" : "s") + " selecionado" + (selection.length === 1 ? "" : "s")) + '</strong><div><button class="button button--secondary" type="button" data-action="bulk-confirm" data-bulk-action="confirm"' + (closed || !selection.length ? " disabled" : "") + '>Marcar como conferidos</button><button class="button button--secondary" type="button" data-action="bulk-set-status" data-bulk-action="set_status"' + (closed || !selection.length ? " disabled" : "") + '>Definir situação</button><button class="button button--secondary" type="button" data-action="bulk-add-observation" data-bulk-action="add_observation"' + (closed || !selection.length ? " disabled" : "") + ">Adicionar observação</button></div><small>As batidas originais nunca serão alteradas.</small></section>",
      '<div class="review-layout"><section class="review-grid" aria-label="Tabela de conferência">' + table + '</section><div class="review-context">' + panel + "</div></div>",
      "</section>",
    ].join("");
  }

  function renderOcr(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Leitura de imagem", "Selecione uma empresa e uma competência antes de revisar a imagem.", true);
    var closed = competenceIsClosed(entities.competence);
    var ocr = valueOf(context.state, ["ocr", "ocrPreview"], null) || valueOf(context.data, ["ocr"], {}) || {};
    var sourceFile = findById(collection(context.data, ["files", "arquivos"]), valueOf(ocr, ["fileId", "arquivoId", "arquivo_id"], null));
    var sourceMatchesContext = Boolean(sourceFile) &&
      idsEqual(valueOf(sourceFile, ["companyId", "empresaId", "empresa_id"], null), idOf(entities.company)) &&
      idsEqual(valueOf(sourceFile, ["competenceId", "competenciaId", "competencia_id"], null), idOf(entities.competence));
    var importAnalysis = valueOf(context.state, ["importAnalysis", "analiseImportacao"], null);
    var selectedFile = valueOf(context.state, ["selectedImportFile", "arquivoSelecionado"], null);
    var uploadedDocument = selectedFile && importAnalysis && typeof importAnalysis === "object" &&
      valueOf(importAnalysis, ["detectedType", "tipoDetectado"], "") === "scanned" &&
      idsEqual(valueOf(importAnalysis, ["companyId", "empresaId", "empresa_id"], null), idOf(entities.company)) &&
      idsEqual(valueOf(importAnalysis, ["competenceId", "competenciaId", "competencia_id"], null), idOf(entities.competence));
    var documentData = Object.assign({}, valueOf(ocr, ["document", "documento"], {}) || {});
    if (uploadedDocument) documentData.fileName = valueOf(selectedFile, ["name", "nome"], "Documento selecionado");
    if (!sourceMatchesContext && !uploadedDocument) documentData.fileName = "Nenhum documento selecionado";
    var rows = sourceMatchesContext ? asArray(valueOf(ocr, ["extractedRows", "linhasExtraidas"], [])) : [];
    return [
      '<section class="screen screen--ocr" data-screen="ocr">', demoBanner(),
      pageHeader(context.components, { title: "Comparação de imagem", subtitle: valueOf(documentData, ["fileName", "nomeArquivo"], "Documento escaneado"), breadcrumbs: competenceBreadcrumbs(entities, "Importações", "Leitura de imagem") }),
      competencyAreaNavigation("imports"),
      closedCompetenceNotice(entities.competence),
      '<div class="ocr-disclaimer" role="note"><strong>Leitura sugerida. Confira antes de salvar.</strong><span>' + escapeHtml(valueOf(ocr, ["certaintyDisclaimer"], "Os dados são uma interpretação simulada e podem conter erros.")) + "</span></div>",
      '<div class="ocr-layout">',
      '<section class="ocr-document work-card" aria-label="Documento original"><div class="ocr-toolbar"><div><button class="icon-button" type="button" data-action="ocr-zoom-out" aria-label="Diminuir zoom">−</button><span>' + escapeHtml(valueOf(documentData, ["zoom"], 100)) + '%</span><button class="icon-button" type="button" data-action="ocr-zoom-in" aria-label="Aumentar zoom">+</button></div><button class="button button--ghost" type="button" data-action="ocr-rotate">Girar</button><label class="compact-field"><span>Contraste</span><input type="range" min="50" max="160" value="' + escapeHtml(valueOf(documentData, ["contrast"], 100)) + '" data-action="ocr-contrast"></label></div>',
      '<div class="document-canvas" style="--document-rotation:' + escapeHtml(valueOf(documentData, ["rotation"], 0)) + 'deg;--document-contrast:' + escapeHtml(valueOf(documentData, ["contrast"], 100)) + '%;--document-zoom:' + escapeHtml(Number(valueOf(documentData, ["zoom"], 100)) / 100) + '"><div class="document-placeholder"><span aria-hidden="true">▤</span><strong>Documento original</strong><small>' + escapeHtml(valueOf(documentData, ["fileName"], "Imagem não incorporada")) + "</small><p>Visualização simulada para comparação lado a lado.</p></div></div>",
      '<footer class="page-controls"><button type="button" class="icon-button" data-action="ocr-previous-page" aria-label="Página anterior">←</button><span>Página ' + escapeHtml(valueOf(documentData, ["page"], 1)) + " de " + escapeHtml(valueOf(documentData, ["pageCount"], 1)) + '</span><button type="button" class="icon-button" data-action="ocr-next-page" aria-label="Próxima página">→</button></footer></section>',
      '<section class="ocr-extracted work-card" aria-label="Dados extraídos"><div class="section-heading"><div><h2>Dados sugeridos</h2><p>Campos com “?” não foram reconhecidos.</p></div></div>',
      rows.length ? '<div class="table-frame"><table class="data-table ocr-table"><thead><tr><th>Data</th><th>Entrada</th><th>Intervalo</th><th>Retorno</th><th>Saída</th><th>Confiança</th><th>Status</th><th>Observação</th></tr></thead><tbody>' + rows.map(function (row) {
        return '<tr data-ocr-row-id="' + escapeHtml(idOf(row)) + '"><td>' + escapeHtml(formatDate(valueOf(row, ["date", "data"], null), true)) + "</td>" + ["entry", "breakStart", "breakEnd", "exit"].map(function (field) {
          var aliases = { entry: ["entry", "entrada"], breakStart: ["breakStart", "saidaIntervalo"], breakEnd: ["breakEnd", "retorno"], exit: ["exit", "saida"] }[field];
          var time = valueOf(row, aliases, "?");
          return '<td><input class="editable-time-cell' + (time === "?" ? " is-unknown" : "") + '" type="text" value="' + escapeHtml(time) + '" data-action="edit-ocr-time" data-field="' + field + '" data-ocr-row-id="' + escapeHtml(idOf(row)) + '" aria-label="' + escapeHtml(field + " de " + formatDate(valueOf(row, ["date", "data"], null), true)) + '"' + (closed ? " disabled" : "") + "></td>";
        }).join("") + '<td><span class="confidence confidence--' + (Number(valueOf(row, ["confidence", "confianca"], 0)) >= 85 ? "high" : "low") + '">' + escapeHtml(valueOf(row, ["confidence", "confianca"], 0)) + "%</span></td><td>" + statusChip(context.components, valueOf(row, ["suggestedStatus", "statusSugerido"], "conferir")) + '</td><td><input class="observation-cell" type="text" value="' + escapeHtml(valueOf(row, ["observation", "observacao"], "")) + '" data-action="edit-ocr-observation" data-ocr-row-id="' + escapeHtml(idOf(row)) + '" aria-label="Observação da leitura de ' + escapeHtml(formatDate(valueOf(row, ["date", "data"], null), true)) + '"' + (closed ? " disabled" : "") + "></td></tr>";
      }).join("") + "</tbody></table></div>" : emptyState(context.components, "Nenhum campo sugerido", "A simulação não encontrou linhas neste documento."),
      '<footer class="screen-actions"><button class="button button--ghost" type="button" data-route="imports" data-action="navigate">Voltar</button><button class="button button--primary" type="button" data-action="accept-ocr-preview"' + (rows.length && !closed ? "" : " disabled") + ">" + (closed ? "Competência fechada" : "Continuar para prévia") + "</button></footer></section>",
      "</div></section>",
    ].join("");
  }

  function competencyExportContent(context, entities) {
    var competence = entities.competence;
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    var exporting = valueOf(context.state, ["exportExcelLoading"], false) === true;
    var summary = online ? competenceSummaryFor(context, competence) : null;
    var general = summary && summary.general || {};
    var pendingValue = online ? availableSummaryValue(general.pending) : Number(valueOf(competence, ["pendingCount", "quantidadePendencias"], 0));
    var employeeTotal = online && general.employees !== null && general.employees !== undefined && general.employees !== "" ? Number(general.employees) : null;
    var confirmedTotal = online && general.confirmed !== null && general.confirmed !== undefined && general.confirmed !== "" ? Number(general.confirmed) : null;
    var pendingTotal = online && general.pending !== null && general.pending !== undefined && general.pending !== "" ? Number(general.pending) : Number(pendingValue);
    var progress = online
      ? (Number.isFinite(employeeTotal) && employeeTotal > 0 && Number.isFinite(confirmedTotal) ? Math.round((confirmedTotal / employeeTotal) * 100) + "%" : "Indisponível")
      : valueOf(competence, ["progress", "progresso"], 0) + "%";
    var hasUnavailableRows = online && summary && asArray(summary.rows).some(function (row) {
      var situation = statusKey(row.situation);
      return !situation || situation === "indisponivel" || situation === "unavailable";
    });
    var readinessStatus = online
      ? (!summary || progress === "Indisponível" || !Number.isFinite(pendingTotal) || hasUnavailableRows
        ? statusChip(context.components, "sem_expediente", "Apuração indisponível")
        : statusChip(context.components, pendingTotal > 0 ? "conferir" : "normal", pendingTotal > 0 ? "Revisão recomendada" : "Pronto para exportar"))
      : statusChip(context.components, pendingValue ? "conferir" : "normal", pendingValue ? "Revisão recomendada" : "Pronto para exportar");
    return [
      '<div class="report-grid">',
      reportCard("Resumo da competência", "Visão consolidada de saldo, ausências e pendências por funcionário.", "Abrir prévia", "preview-summary-report"),
      reportCard("Planilha de conferência", "Exportação operacional com as marcações e o resultado atual da conferência.", exporting ? "Gerando..." : "Exportar Excel", "export-excel", { disabled: exporting, busy: exporting }),
      reportCard("Relatório para impressão", "Layout limpo para imprimir ou salvar como PDF no navegador.", "Abrir impressão", "open-print-report"),
      "</div>",
      '<section class="work-card report-readiness"><div class="section-heading"><div><h2>Prontidão para exportação</h2><p>' + (online ? "Indicadores da apuração mais recente desta competência." : "Os indicadores abaixo são simulados.") + "</p></div>" + readinessStatus + '</div><dl class="summary-grid summary-grid--four">' + summaryItem("Empresa", companyName(entities.company)) + summaryItem("Competência", formatCompetence(competence)) + summaryItem("Progresso", progress) + summaryItem("Pendências", pendingValue) + "</dl></section>",
    ].join("");
  }

  function renderCompetencyExports(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company || !entities.competence) return missingContextScreen(context, "Exportações", "Selecione uma empresa e uma competência antes de exportar.", true);
    return '<section class="screen screen--competency-exports" data-screen="competency-exports">' + demoBanner() + pageHeader(context.components, {
      title: "Exportações",
      subtitle: companyName(entities.company) + " · " + formatCompetence(entities.competence),
      breadcrumbs: competenceBreadcrumbs(entities, "Exportações"),
    }) + competencyAreaNavigation("competency-exports") + competencyExportContent(context, entities) + "</section>";
  }

  function renderCompanyReports(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    if (!entities.company) return missingContextScreen(context, "Relatórios", "Abra uma empresa para visualizar seus relatórios.", false);
    var competencies = competenciesForCompany(entities, entities.company);
    var totalPending = competencies.reduce(function (total, competence) { return total + Number(valueOf(competence, ["pendingCount", "quantidadePendencias"], 0)); }, 0);
    var rows = competencies.map(function (competence) {
      return '<tr><td><strong>' + escapeHtml(formatCompetence(competence)) + "</strong></td><td>" + statusChip(context.components, competence.status, competence.statusLabel) + "</td><td>" + escapeHtml(valueOf(competence, ["progress", "progresso"], 0)) + "%</td><td>" + escapeHtml(valueOf(competence, ["pendingCount", "quantidadePendencias"], 0)) + "</td><td>" + escapeHtml(formatDateTime(valueOf(competence, ["updatedAt", "updated_at"], null))) + '</td><td><button class="table-link" type="button" data-action="open-competence-area" data-competence-id="' + escapeHtml(idOf(competence)) + '" data-route="competency-exports">Abrir exportações</button></td></tr>';
    }).join("");
    return '<section class="screen screen--company-reports" data-screen="company-reports">' + demoBanner() + pageHeader(context.components, {
      title: "Relatórios",
      subtitle: companyName(entities.company),
      breadcrumbs: companyBreadcrumbs(entities.company, "Relatórios"),
    }) + '<section class="work-card competency-hero"><dl class="summary-grid">' + summaryItem("Competências", competencies.length) + summaryItem("Em conferência", competencies.filter(function (item) { return normalizeStatus(item.status) === "em_conferencia"; }).length) + summaryItem("Conferidas", competencies.filter(function (item) { return normalizeStatus(item.status) === "conferida"; }).length) + summaryItem("Fechadas", competencies.filter(function (item) { return normalizeStatus(item.status) === "fechada"; }).length) + summaryItem("Pendências", totalPending) + '</dl></section><section class="work-card"><div class="section-heading"><div><h2>Relatórios por competência</h2><p>Escolha uma competência para gerar suas saídas.</p></div></div>' + (rows ? '<div class="table-frame"><table class="data-table"><thead><tr><th>Competência</th><th>Status</th><th>Progresso</th><th>Pendências</th><th>Atualização</th><th><span class="sr-only">Ação</span></th></tr></thead><tbody>' + rows + "</tbody></table></div>" : emptyState(context.components, "Nenhuma competência", "Crie uma competência antes de gerar relatórios.", { label: "Criar competência", action: "new-competence" })) + "</section></section>";
  }

  function renderReports(state, data, components) {
    return renderCompanyReports(state, data, components);
  }

  function reportCard(title, description, label, action, options) {
    var settings = options || {};
    return '<article class="report-card"><span class="report-card__icon" aria-hidden="true">▤</span><h2>' + escapeHtml(title) + "</h2><p>" + escapeHtml(description) + '</p><button class="button button--secondary" type="button" data-action="' + escapeHtml(action) + '"' + (settings.busy ? ' aria-busy="true"' : "") + (settings.disabled ? " disabled" : "") + ">" + escapeHtml(label) + "</button></article>";
  }

  function renderRegistrations(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    var activeTab = statusKey(valueOf(context.state, ["registrationsTab", "cadastrosTab", "abaCadastros"], "companies"));
    activeTab = { empresas: "companies", funcionarios: "employees" }[activeTab] || activeTab;
    var rows;
    if (activeTab === "employees") {
      rows = entities.employees.map(function (employee) {
        var company = findById(entities.companies, valueOf(employee, ["companyId", "empresa_id"], null));
        return '<tr><td><strong>' + escapeHtml(employeeName(employee)) + "</strong></td><td>" + escapeHtml(valueOf(employee, ["code", "codigo"], "—")) + "</td><td>" + escapeHtml(companyName(company)) + "</td><td>" + escapeHtml(valueOf(employee, ["role", "cargo"], "—")) + "</td><td>" + statusChip(context.components, valueOf(employee, ["active", "ativo"], true) ? "normal" : "sem_expediente", valueOf(employee, ["active", "ativo"], true) ? "Ativo" : "Inativo") + '</td><td><button class="table-link" type="button" data-action="edit-employee" data-employee-id="' + escapeHtml(idOf(employee)) + '">Editar</button></td></tr>';
      }).join("");
    } else {
      rows = entities.companies.map(function (company) {
        var count = entities.employees.filter(function (employee) { return idsEqual(valueOf(employee, ["companyId", "empresa_id"], null), idOf(company)); }).length;
        return '<tr><td><strong>' + escapeHtml(companyName(company)) + "</strong><small>" + escapeHtml(valueOf(company, ["legalName", "razaoSocial"], "")) + "</small></td><td>" + escapeHtml(valueOf(company, ["cnpj"], "—")) + "</td><td>" + count + "</td><td>" + statusChip(context.components, valueOf(company, ["active", "ativa"], true) ? "normal" : "sem_expediente", valueOf(company, ["active", "ativa"], true) ? "Ativa" : "Inativa") + '</td><td><button class="table-link" type="button" data-action="edit-company" data-company-id="' + escapeHtml(idOf(company)) + '">Editar</button></td></tr>';
      }).join("");
    }
    return [
      '<section class="screen screen--registrations" data-screen="registrations">', demoBanner(),
      pageHeader(context.components, { title: "Cadastros", subtitle: online ? "Mantenha os dados de empresas e funcionários." : "Mantenha empresas e funcionários usados no modo demonstração.", actions: [{ label: activeTab === "employees" ? "Novo funcionário" : "Nova empresa", variant: "button--primary", action: activeTab === "employees" ? "new-employee" : "new-company" }] }),
      '<nav class="tabs" aria-label="Cadastros"><button class="tab' + (activeTab === "companies" ? " is-active" : "") + '" type="button" data-action="set-registrations-tab" data-tab="companies" aria-selected="' + (activeTab === "companies" ? "true" : "false") + '">Empresas</button><button class="tab' + (activeTab === "employees" ? " is-active" : "") + '" type="button" data-action="set-registrations-tab" data-tab="employees" aria-selected="' + (activeTab === "employees" ? "true" : "false") + '">Funcionários</button></nav>',
      '<section class="work-card"><div class="table-frame"><table class="data-table"><thead><tr>' + (activeTab === "employees" ? "<th>Funcionário</th><th>Código</th><th>Empresa</th><th>Cargo</th><th>Status</th><th><span class=\"sr-only\">Ação</span></th>" : "<th>Empresa</th><th>CNPJ</th><th>Funcionários</th><th>Status</th><th><span class=\"sr-only\">Ação</span></th>") + "</tr></thead><tbody>" + rows + "</tbody></table></div></section>",
      "</section>",
    ].join("");
  }

  function renderCompanySettings(state, data, components) {
    var context = normalizeArgs(state, data, components);
    var entities = selectedEntities(context);
    var company = entities.company;
    if (!company) return missingContextScreen(context, "Configurações", "Abra uma empresa para ajustar suas configurações.", false);
    var settings = valueOf(context.state, ["settings", "configuracoes"], {}) || {};
    var online = valueOf(context.state, ["apiMode"], "offline") === "online";
    var weekdayMinutes = Math.round(Number(valueOf(company, ["jornada_seg_sex_horas"], 8)) * 60);
    var saturdayMinutes = Math.round(Number(valueOf(company, ["jornada_sabado_horas"], 4)) * 60);
    return [
      '<section class="screen screen--company-settings" data-screen="company-settings">', demoBanner(),
      pageHeader(context.components, { title: "Configurações", subtitle: companyName(company) + " · Preferências locais da interface.", breadcrumbs: companyBreadcrumbs(company, "Configurações") }),
      '<div class="settings-layout">',
      '<section class="work-card settings-section"><div class="section-heading"><div><h2>Jornada padrão</h2><p>Valores do cadastro da empresa usados no cálculo atual.</p></div><button class="button button--secondary" type="button" data-action="edit-company" data-company-id="' + escapeHtml(idOf(company)) + '">Editar empresa</button></div><dl class="summary-grid summary-grid--four">' + summaryItem("Segunda a sexta", formatDuration(weekdayMinutes)) + summaryItem("Sábado", formatDuration(saturdayMinutes)) + summaryItem("Tolerância de atraso", valueOf(company, ["tolerancia_atraso_minutos"], 5) + " min") + summaryItem("Tolerância de saldo positivo", valueOf(company, ["tolerancia_extra_minutos"], 10) + " min") + "</dl></section>",
      '<section class="work-card settings-section"><div class="section-heading"><div><h2>Experiência de conferência</h2><p>Preferências válidas somente durante esta sessão do navegador.</p></div></div><label class="switch-row"><span><strong>Salvamento automático</strong><small>' + (online ? "Persiste cada edição na API." : "Simula o estado de salvamento enquanto a API está offline.") + '</small></span><input type="checkbox" role="switch"' + (valueOf(settings, ["autosave"], true) ? " checked" : "") + ' data-action="toggle-autosave"></label><label class="switch-row"><span><strong>Alertar horários incomuns</strong><small>Permite o horário e pede uma confirmação adicional.</small></span><input type="checkbox" role="switch"' + (valueOf(settings, ["unusualTimeAlerts"], true) ? " checked" : "") + ' data-action="toggle-unusual-time-alert"></label><label class="switch-row"><span><strong>Atalhos de uma tecla</strong><small>Desativados automaticamente durante edição de texto.</small></span><input type="checkbox" role="switch"' + (valueOf(settings, ["singleKeyShortcuts"], true) ? " checked" : "") + ' data-action="toggle-single-key-shortcuts"></label></section>',
      online
        ? '<section class="work-card settings-section"><span class="eyebrow">Ambiente atual</span><h2>Integração ativa</h2><p>Empresas, competências, funcionários, importações e marcações são carregados da API.</p><dl class="detail-grid">' + summaryItem("Empresa ativa", companyName(company)) + summaryItem("Armazenamento", "Backend") + summaryItem("API", valueOf(context.state, ["apiBase"], "Ativa")) + "</dl></section>"
        : '<section class="work-card settings-section settings-section--demo"><span class="eyebrow">Ambiente atual</span><h2>Modo demonstração</h2><p>A API está indisponível e os dados exibidos são fictícios.</p><dl class="detail-grid">' + summaryItem("Empresa ativa", companyName(company)) + summaryItem("Armazenamento", "Memória do navegador") + summaryItem("Integração", "Desativada") + '</dl><button class="button button--danger-ghost" type="button" data-action="reset-demo-data">Restaurar dados simulados</button></section>',
      "</div></section>",
    ].join("");
  }

  function renderSettings(state, data, components) {
    return renderCompanySettings(state, data, components);
  }

  function renderUnknown(state, data, components) {
    var context = normalizeArgs(state, data, components);
    return '<section class="screen screen--not-found" data-screen="not-found">' + demoBanner() + pageHeader(context.components, { title: "Tela não encontrada", subtitle: "Esta rota não faz parte do protótipo." }) + emptyState(context.components, "Não encontramos esta tela", "Volte à lista de empresas para continuar.", { label: "Ver empresas", route: "companies", action: "navigate" }) + "</section>";
  }

  var routes = {
    companies: renderCompanies,
    empresas: renderCompanies,
    dashboard: renderCompanies,
    painel: renderCompanies,
    panel: renderCompanies,
    company_overview: renderCompanyOverview,
    company_employees: renderCompanyEmployees,
    company_competencies: renderCompanyCompetencies,
    competency_summary: renderCompetencySummary,
    imports: renderImports,
    importacoes: renderImports,
    importacao: renderImports,
    import_preview: renderImportPreview,
    preview: renderImportPreview,
    previa_importacao: renderImportPreview,
    competencies: renderCompanyCompetencies,
    competencias: renderCompanyCompetencies,
    competency_detail: renderCompetencySummary,
    competence_detail: renderCompetencySummary,
    competencia: renderCompetencySummary,
    detalhe_competencia: renderCompetencySummary,
    review: renderReview,
    conferencia: renderReview,
    attendance_review: renderReview,
    competency_files: renderCompetencyFiles,
    competency_history: renderCompetencyHistory,
    competency_exports: renderCompetencyExports,
    ocr: renderOcr,
    image_review: renderOcr,
    company_reports: renderCompanyReports,
    reports: renderCompanyReports,
    relatorios: renderCompanyReports,
    registrations: renderRegistrations,
    cadastros: renderRegistrations,
    company_settings: renderCompanySettings,
    settings: renderCompanySettings,
    configuracoes: renderCompanySettings,
  };

  function normalizeRoute(route) {
    return statusKey(route || "dashboard");
  }

  function render(route, state, data, components) {
    if (route && typeof route === "object") {
      components = route.components;
      data = route.data;
      state = route.state;
      route = route.route || route.screen || route.view;
    }
    var key = normalizeRoute(route);
    return (routes[key] || renderUnknown)(state, data, components);
  }

  root.OnPontoScreens = Object.freeze({
    render: render,
    renderRoute: render,
    renderCompanies: renderCompanies,
    companies: renderCompanies,
    empresas: renderCompanies,
    renderCompanyOverview: renderCompanyOverview,
    companyOverview: renderCompanyOverview,
    renderCompanyEmployees: renderCompanyEmployees,
    companyEmployees: renderCompanyEmployees,
    renderCompanyCompetencies: renderCompanyCompetencies,
    companyCompetencies: renderCompanyCompetencies,
    renderCompetencySummary: renderCompetencySummary,
    competencySummary: renderCompetencySummary,
    renderDashboard: renderDashboard,
    dashboard: renderDashboard,
    panel: renderDashboard,
    painel: renderDashboard,
    renderImports: renderImports,
    imports: renderImports,
    importacoes: renderImports,
    renderImportPreview: renderImportPreview,
    importPreview: renderImportPreview,
    previaImportacao: renderImportPreview,
    renderCompetencies: renderCompetencies,
    competencies: renderCompetencies,
    competencias: renderCompetencies,
    renderCompetencyDetail: renderCompetencyDetail,
    competencyDetail: renderCompetencyDetail,
    detalheCompetencia: renderCompetencyDetail,
    renderReview: renderReview,
    review: renderReview,
    conferencia: renderReview,
    renderCompetencyFiles: renderCompetencyFiles,
    competencyFiles: renderCompetencyFiles,
    renderCompetencyHistory: renderCompetencyHistory,
    competencyHistory: renderCompetencyHistory,
    renderCompetencyExports: renderCompetencyExports,
    competencyExports: renderCompetencyExports,
    renderOcr: renderOcr,
    ocr: renderOcr,
    renderCompanyReports: renderCompanyReports,
    companyReports: renderCompanyReports,
    renderReports: renderReports,
    reports: renderReports,
    relatorios: renderReports,
    renderRegistrations: renderRegistrations,
    registrations: renderRegistrations,
    cadastros: renderRegistrations,
    renderSettings: renderSettings,
    settings: renderSettings,
    configuracoes: renderSettings,
    renderCompanySettings: renderCompanySettings,
    companySettings: renderCompanySettings,
    notFound: renderUnknown,
    routeMap: Object.freeze(Object.assign({}, routes)),
  });
})(typeof window !== "undefined" ? window : globalThis);
