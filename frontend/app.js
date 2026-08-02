const state = {
  apiBase: localStorage.getItem("onponto.apiBase") || "http://127.0.0.1:8000",
  empresas: [],
  funcionarios: [],
  competencias: [],
  arquivos: [],
  marcacoes: [],
  importacao: null,
  view: "empresas",
};

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  })[char]);
}

function apiUrl(path) {
  return `${state.apiBase}${path}`;
}

function setNotice(message, isError = false) {
  const notice = $("#notice");
  notice.textContent = message;
  notice.classList.toggle("error", isError);
  notice.hidden = !message;
  if (message) {
    window.clearTimeout(setNotice.timer);
    setNotice.timer = window.setTimeout(() => {
      notice.hidden = true;
    }, 4500);
  }
}

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    headers: options.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    let detail = "Erro na requisição.";
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function toNumber(value, fallback = null) {
  if (value === "" || value === null || value === undefined) {
    return fallback;
  }
  return Number(value);
}

function emptyToNull(value) {
  return value === "" ? null : value;
}

function formatCompetencia(comp) {
  return `${String(comp.mes).padStart(2, "0")}/${comp.ano}`;
}

function selectedValue(id) {
  return Number($(id).value || 0);
}

function setSelectOptions(select, items, labelFn, valueFn = (item) => item.id, emptyLabel = "Selecione") {
  const selected = select.value;
  select.innerHTML = `<option value="">${emptyLabel}</option>`;
  for (const item of items) {
    const option = document.createElement("option");
    option.value = valueFn(item);
    option.textContent = labelFn(item);
    select.appendChild(option);
  }
  if ([...select.options].some((option) => option.value === selected)) {
    select.value = selected;
  }
}

function renderEmpty(tbody, colspan, text = "Nenhum registro.") {
  tbody.innerHTML = `<tr><td class="empty-row" colspan="${colspan}">${text}</td></tr>`;
}

function currentEmpresaId(prefix) {
  return selectedValue(`#${prefix}EmpresaSelect`);
}

function competenciasDaEmpresa(empresaId) {
  return state.competencias.filter((competencia) => competencia.empresa_id === Number(empresaId));
}

function funcionariosDaEmpresa(empresaId) {
  return state.funcionarios.filter((funcionario) => funcionario.empresa_id === Number(empresaId));
}

async function loadBaseData() {
  state.empresas = await request("/empresas");
  state.funcionarios = await request("/funcionarios");
  state.competencias = await request("/competencias");
  renderAll();
  await pingApi();
}

async function pingApi() {
  const pill = $("#connectionStatus");
  try {
    await request("/");
    pill.textContent = "API online";
    pill.className = "status-pill ok";
  } catch {
    pill.textContent = "API offline";
    pill.className = "status-pill error";
  }
}

function renderAll() {
  renderEmpresaSelects();
  renderEmpresas();
  renderFuncionarios();
  renderCompetencias();
  renderCompetenciaDependentSelects();
}

function renderEmpresaSelects() {
  const selects = [
    "#funcEmpresaSelect",
    "#compEmpresaSelect",
    "#arqEmpresaSelect",
    "#impEmpresaSelect",
    "#confEmpresaSelect",
    "#apuEmpresaSelect",
    "#relEmpresaSelect",
  ].map((id) => $(id));

  for (const select of selects) {
    setSelectOptions(select, state.empresas, (empresa) => empresa.nome, (empresa) => empresa.id, "Empresa");
    if (!select.value && state.empresas.length) {
      select.value = state.empresas[0].id;
    }
  }
}

function renderCompetenciaDependentSelects() {
  updateCompetenciaSelect("arq");
  updateCompetenciaSelect("imp");
  updateCompetenciaSelect("conf");
  updateFuncionarioSelect();
  updateCompetenciaSelect("apu");
  updateCompetenciaSelect("rel");
}

function updateCompetenciaSelect(prefix) {
  const empresaId = currentEmpresaId(prefix);
  const select = $(`#${prefix}CompetenciaSelect`);
  const competencias = competenciasDaEmpresa(empresaId);
  setSelectOptions(select, competencias, formatCompetencia, (competencia) => competencia.id, "Competência");
  if (!select.value && competencias.length) {
    select.value = competencias[0].id;
  }
}

function competenciaSelecionada(prefix) {
  const competenciaId = selectedValue(`#${prefix}CompetenciaSelect`);
  return state.competencias.find((competencia) => competencia.id === competenciaId);
}

function updateFuncionarioSelect() {
  const empresaId = currentEmpresaId("conf");
  const select = $("#confFuncionarioSelect");
  const funcionarios = funcionariosDaEmpresa(empresaId);
  setSelectOptions(select, funcionarios, (funcionario) => funcionario.nome, (funcionario) => funcionario.id, "Funcionário");
  if (!select.value && funcionarios.length) {
    select.value = funcionarios[0].id;
  }
}

function renderEmpresas() {
  const tbody = $("#empresasTable");
  if (!state.empresas.length) {
    renderEmpty(tbody, 4);
    return;
  }

  tbody.innerHTML = state.empresas
    .map(
      (empresa) => `
        <tr>
          <td>${escapeHtml(empresa.nome)}</td>
          <td>${escapeHtml(empresa.cnpj)}</td>
          <td>${empresa.ativa ? "Sim" : "Não"}</td>
          <td class="actions-cell"><button type="button" data-edit-empresa="${empresa.id}">Editar</button></td>
        </tr>
      `,
    )
    .join("");
}

function resetEmpresaForm() {
  $("#empresaId").value = "";
  $("#empresaNome").value = "";
  $("#empresaCnpj").value = "";
  $("#empresaJornadaSemana").value = 8;
  $("#empresaJornadaSabado").value = 4;
  $("#empresaTolAtraso").value = 5;
  $("#empresaTolExtra").value = 10;
  $("#empresaAtiva").checked = true;
  $("#empresaObs").value = "";
}

function editEmpresa(id) {
  const empresa = state.empresas.find((item) => item.id === Number(id));
  if (!empresa) return;
  $("#empresaId").value = empresa.id;
  $("#empresaNome").value = empresa.nome;
  $("#empresaCnpj").value = empresa.cnpj || "";
  $("#empresaJornadaSemana").value = empresa.jornada_seg_sex_horas;
  $("#empresaJornadaSabado").value = empresa.jornada_sabado_horas;
  $("#empresaTolAtraso").value = empresa.tolerancia_atraso_minutos;
  $("#empresaTolExtra").value = empresa.tolerancia_extra_minutos;
  $("#empresaAtiva").checked = empresa.ativa;
  $("#empresaObs").value = empresa.observacoes || "";
}

async function saveEmpresa(event) {
  event.preventDefault();
  const id = $("#empresaId").value;
  const payload = {
    nome: $("#empresaNome").value.trim(),
    cnpj: emptyToNull($("#empresaCnpj").value.trim()),
    jornada_seg_sex_horas: toNumber($("#empresaJornadaSemana").value, 8),
    jornada_sabado_horas: toNumber($("#empresaJornadaSabado").value, 4),
    tolerancia_atraso_minutos: toNumber($("#empresaTolAtraso").value, 5),
    tolerancia_extra_minutos: toNumber($("#empresaTolExtra").value, 10),
    ativa: $("#empresaAtiva").checked,
    observacoes: emptyToNull($("#empresaObs").value.trim()),
  };
  await request(id ? `/empresas/${id}` : "/empresas", {
    method: id ? "PATCH" : "POST",
    body: JSON.stringify(payload),
  });
  resetEmpresaForm();
  await loadBaseData();
  setNotice("Empresa salva.");
}

function renderFuncionarios() {
  const empresaId = selectedValue("#funcEmpresaSelect");
  const funcionarios = funcionariosDaEmpresa(empresaId);
  const tbody = $("#funcionariosTable");
  if (!funcionarios.length) {
    renderEmpty(tbody, 5);
    return;
  }

  tbody.innerHTML = funcionarios
    .map(
      (funcionario) => `
        <tr>
          <td>${escapeHtml(funcionario.codigo)}</td>
          <td>${escapeHtml(funcionario.nome)}</td>
          <td>${escapeHtml(funcionario.cargo)}</td>
          <td>${funcionario.ativo ? "Sim" : "Não"}</td>
          <td class="actions-cell"><button type="button" data-edit-funcionario="${funcionario.id}">Editar</button></td>
        </tr>
      `,
    )
    .join("");
}

function resetFuncionarioForm() {
  $("#funcionarioId").value = "";
  $("#funcCodigo").value = "";
  $("#funcNome").value = "";
  $("#funcCargo").value = "";
  $("#funcJornadaSemana").value = "";
  $("#funcJornadaSabado").value = "";
  $("#funcAtivo").checked = true;
  $("#funcObs").value = "";
}

function editFuncionario(id) {
  const funcionario = state.funcionarios.find((item) => item.id === Number(id));
  if (!funcionario) return;
  $("#funcionarioId").value = funcionario.id;
  $("#funcCodigo").value = funcionario.codigo || "";
  $("#funcNome").value = funcionario.nome;
  $("#funcCargo").value = funcionario.cargo || "";
  $("#funcJornadaSemana").value = funcionario.jornada_especifica_seg_sex_horas ?? "";
  $("#funcJornadaSabado").value = funcionario.jornada_especifica_sabado_horas ?? "";
  $("#funcAtivo").checked = funcionario.ativo;
  $("#funcObs").value = funcionario.observacoes || "";
}

async function saveFuncionario(event) {
  event.preventDefault();
  const empresaId = selectedValue("#funcEmpresaSelect");
  if (!empresaId) {
    setNotice("Selecione uma empresa.", true);
    return;
  }
  const id = $("#funcionarioId").value;
  const payload = {
    empresa_id: empresaId,
    codigo: emptyToNull($("#funcCodigo").value.trim()),
    nome: $("#funcNome").value.trim(),
    cargo: emptyToNull($("#funcCargo").value.trim()),
    ativo: $("#funcAtivo").checked,
    jornada_especifica_seg_sex_horas: toNumber($("#funcJornadaSemana").value),
    jornada_especifica_sabado_horas: toNumber($("#funcJornadaSabado").value),
    observacoes: emptyToNull($("#funcObs").value.trim()),
  };
  await request(id ? `/funcionarios/${id}` : "/funcionarios", {
    method: id ? "PATCH" : "POST",
    body: JSON.stringify(payload),
  });
  resetFuncionarioForm();
  await loadBaseData();
  setNotice("Funcionário salvo.");
}

function renderCompetencias() {
  const empresaId = selectedValue("#compEmpresaSelect");
  const competencias = competenciasDaEmpresa(empresaId);
  const tbody = $("#competenciasTable");
  if (!competencias.length) {
    renderEmpty(tbody, 4);
    return;
  }

  tbody.innerHTML = competencias
    .map(
      (competencia) => `
        <tr>
          <td>${formatCompetencia(competencia)}</td>
          <td>${escapeHtml(competencia.status)}</td>
          <td>${escapeHtml(competencia.data_recebimento)}</td>
          <td class="actions-cell"><button type="button" data-edit-competencia="${competencia.id}">Editar</button></td>
        </tr>
      `,
    )
    .join("");
}

function resetCompetenciaForm() {
  const hoje = new Date();
  $("#competenciaId").value = "";
  $("#compMes").value = hoje.getMonth() + 1;
  $("#compAno").value = hoje.getFullYear();
  $("#compStatus").value = "aberta";
  $("#compRecebimento").value = "";
  $("#compFechamento").value = "";
  $("#compObs").value = "";
}

function editCompetencia(id) {
  const competencia = state.competencias.find((item) => item.id === Number(id));
  if (!competencia) return;
  $("#competenciaId").value = competencia.id;
  $("#compMes").value = competencia.mes;
  $("#compAno").value = competencia.ano;
  $("#compStatus").value = competencia.status;
  $("#compRecebimento").value = competencia.data_recebimento || "";
  $("#compFechamento").value = competencia.data_fechamento || "";
  $("#compObs").value = competencia.observacoes || "";
}

async function saveCompetencia(event) {
  event.preventDefault();
  const empresaId = selectedValue("#compEmpresaSelect");
  if (!empresaId) {
    setNotice("Selecione uma empresa.", true);
    return;
  }
  const id = $("#competenciaId").value;
  const payload = {
    empresa_id: empresaId,
    mes: toNumber($("#compMes").value),
    ano: toNumber($("#compAno").value),
    status: $("#compStatus").value,
    data_recebimento: emptyToNull($("#compRecebimento").value),
    data_fechamento: emptyToNull($("#compFechamento").value),
    observacoes: emptyToNull($("#compObs").value.trim()),
  };
  await request(id ? `/competencias/${id}` : "/competencias", {
    method: id ? "PATCH" : "POST",
    body: JSON.stringify(payload),
  });
  resetCompetenciaForm();
  await loadBaseData();
  setNotice("Competência salva.");
}

async function loadArquivos() {
  const competenciaId = selectedValue("#arqCompetenciaSelect");
  if (!competenciaId) {
    $("#arquivosTable").innerHTML = "";
    renderEmpty($("#arquivosTable"), 4, "Selecione uma competência.");
    return;
  }
  state.arquivos = await request(`/arquivos?competencia_id=${competenciaId}`);
  renderArquivos();
}

function renderArquivos() {
  const tbody = $("#arquivosTable");
  if (!state.arquivos.length) {
    renderEmpty(tbody, 4);
    return;
  }

  tbody.innerHTML = state.arquivos
    .map(
      (arquivo) => `
        <tr>
          <td>${escapeHtml(arquivo.nome_original)}</td>
          <td>${escapeHtml(arquivo.tipo_arquivo)}</td>
          <td>${new Date(arquivo.created_at).toLocaleString("pt-BR")}</td>
          <td class="actions-cell"><a href="${apiUrl(`/arquivos/${arquivo.id}/download`)}" target="_blank" rel="noopener">Abrir</a></td>
        </tr>
      `,
    )
    .join("");
}

async function uploadArquivo(event) {
  event.preventDefault();
  const competenciaId = selectedValue("#arqCompetenciaSelect");
  const file = $("#arquivoInput").files[0];
  if (!competenciaId || !file) {
    setNotice("Selecione competência e arquivo.", true);
    return;
  }

  const formData = new FormData();
  formData.append("competencia_id", competenciaId);
  formData.append("observacoes", $("#arquivoObs").value.trim());
  formData.append("arquivo", file);

  await request("/arquivos", {
    method: "POST",
    body: formData,
  });
  $("#arquivoForm").reset();
  await loadArquivos();
  setNotice("Arquivo enviado.");
}

function limparPreviaImportacao(texto = "Nenhuma importação carregada.") {
  state.importacao = null;
  renderEmpty($("#importadorPreviewTable"), 8, texto);
  $("#salvarImportacao").disabled = true;
}

async function importarXlsxGenerico(event) {
  event.preventDefault();
  const empresaId = selectedValue("#impEmpresaSelect");
  const competencia = competenciaSelecionada("imp");
  const file = $("#importadorArquivo").files[0];
  if (!empresaId || !competencia || !file) {
    setNotice("Selecione empresa, competência e arquivo XLSX.", true);
    return;
  }

  const formData = new FormData();
  formData.append("empresa_id", empresaId);
  formData.append("competencia_id", competencia.id);
  formData.append("mes", competencia.mes);
  formData.append("ano", competencia.ano);
  formData.append("arquivo", file);

  state.importacao = await request("/importadores/xlsx-ponto-generico", {
    method: "POST",
    body: formData,
  });
  renderImportacaoPreview();
  setNotice(`${state.importacao.total_marcacoes} marcações estruturadas na prévia.`);
}

function renderImportacaoPreview() {
  const tbody = $("#importadorPreviewTable");
  const marcacoes = state.importacao?.marcacoes || [];
  if (!marcacoes.length) {
    renderEmpty(tbody, 8, "Nenhuma marcação encontrada.");
    $("#salvarImportacao").disabled = true;
    return;
  }

  tbody.innerHTML = marcacoes
    .map((item) => {
      const funcionario = item.funcionario_encontrado ? item.funcionario : `${item.funcionario} (não cadastrado)`;
      return `
        <tr>
          <td>${escapeHtml(funcionario)}</td>
          <td>${escapeHtml(item.data)}</td>
          <td>${escapeHtml(item.entrada)}</td>
          <td>${escapeHtml(item.saida_almoco)}</td>
          <td>${escapeHtml(item.retorno_almoco)}</td>
          <td>${escapeHtml(item.saida)}</td>
          <td>${escapeHtml(item.status)}</td>
          <td>${escapeHtml(item.observacoes)}</td>
        </tr>
      `;
    })
    .join("");
  $("#salvarImportacao").disabled = !marcacoes.some((item) => item.funcionario_id);
}

async function salvarMarcacoesImportadas() {
  const marcacoes = state.importacao?.marcacoes || [];
  const salvaveis = marcacoes.filter((item) => item.funcionario_id);
  if (!salvaveis.length) {
    setNotice("Nenhuma marcação possui funcionário cadastrado para salvar.", true);
    return;
  }

  let salvas = 0;
  for (const item of salvaveis) {
    await request("/marcacoes", {
      method: "POST",
      body: JSON.stringify({
        competencia_id: item.competencia_id,
        funcionario_id: item.funcionario_id,
        data: item.data,
        entrada: item.entrada,
        saida_almoco: item.saida_almoco,
        retorno_almoco: item.retorno_almoco,
        saida: item.saida,
        status_dia: item.status_dia,
        origem: "xlsx_importado",
        conferido: false,
        observacoes: emptyToNull(item.observacoes),
      }),
    });
    salvas += 1;
  }

  const ignoradas = marcacoes.length - salvas;
  await loadBaseData();
  setNotice(`${salvas} marcações salvas.${ignoradas ? ` ${ignoradas} sem funcionário cadastrado foram ignoradas.` : ""}`);
}

function diasDaCompetencia(competencia) {
  const total = new Date(competencia.ano, competencia.mes, 0).getDate();
  return Array.from({ length: total }, (_, index) => {
    const dia = String(index + 1).padStart(2, "0");
    const mes = String(competencia.mes).padStart(2, "0");
    return `${competencia.ano}-${mes}-${dia}`;
  });
}

async function loadMarcacoes() {
  const competenciaId = selectedValue("#confCompetenciaSelect");
  const funcionarioId = selectedValue("#confFuncionarioSelect");
  if (!competenciaId || !funcionarioId) {
    renderEmpty($("#marcacoesTable"), 9, "Selecione empresa, competência e funcionário.");
    return;
  }
  state.marcacoes = await request(`/marcacoes?competencia_id=${competenciaId}&funcionario_id=${funcionarioId}`);
  renderMarcacoes();
}

function renderMarcacoes() {
  const competenciaId = selectedValue("#confCompetenciaSelect");
  const competencia = state.competencias.find((item) => item.id === competenciaId);
  const tbody = $("#marcacoesTable");
  if (!competencia) {
    renderEmpty(tbody, 9, "Selecione uma competência.");
    return;
  }

  const porData = new Map(state.marcacoes.map((marcacao) => [marcacao.data, marcacao]));
  tbody.innerHTML = diasDaCompetencia(competencia)
    .map((data) => {
      const item = porData.get(data) || {};
      return `
        <tr data-marcacao-row="${data}">
          <td>${data}</td>
          <td><input class="mini-input" type="time" data-field="entrada" value="${escapeHtml(item.entrada)}"></td>
          <td><input class="mini-input" type="time" data-field="saida_almoco" value="${escapeHtml(item.saida_almoco)}"></td>
          <td><input class="mini-input" type="time" data-field="retorno_almoco" value="${escapeHtml(item.retorno_almoco)}"></td>
          <td><input class="mini-input" type="time" data-field="saida" value="${escapeHtml(item.saida)}"></td>
          <td>
            <select data-field="status_dia">
              ${["normal", "falta", "atestado", "folga", "feriado", "pendente", "pendente_conferencia"]
                .map((status) => `<option value="${status}" ${status === (item.status_dia || "pendente") ? "selected" : ""}>${status}</option>`)
                .join("")}
            </select>
          </td>
          <td><input type="checkbox" data-field="conferido" ${item.conferido ? "checked" : ""}></td>
          <td><input class="obs-input" data-field="observacoes" value="${escapeHtml(item.observacoes)}"></td>
          <td class="actions-cell"><button type="button" data-save-marcacao="${data}">Salvar</button></td>
        </tr>
      `;
    })
    .join("");
}

async function saveMarcacao(data) {
  const competenciaId = selectedValue("#confCompetenciaSelect");
  const funcionarioId = selectedValue("#confFuncionarioSelect");
  const row = document.querySelector(`[data-marcacao-row="${data}"]`);
  const field = (name) => row.querySelector(`[data-field="${name}"]`);
  const payload = {
    competencia_id: competenciaId,
    funcionario_id: funcionarioId,
    data,
    entrada: emptyToNull(field("entrada").value),
    saida_almoco: emptyToNull(field("saida_almoco").value),
    retorno_almoco: emptyToNull(field("retorno_almoco").value),
    saida: emptyToNull(field("saida").value),
    status_dia: field("status_dia").value,
    origem: "manual",
    conferido: field("conferido").checked,
    observacoes: emptyToNull(field("observacoes").value.trim()),
  };
  await request("/marcacoes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await loadMarcacoes();
  setNotice(`Marcação de ${data} salva.`);
}

async function loadApuracao() {
  const competenciaId = selectedValue("#apuCompetenciaSelect");
  if (!competenciaId) {
    renderEmpty($("#apuracaoResumoTable"), 6, "Selecione uma competência.");
    renderEmpty($("#apuracaoPendenciasTable"), 4, "Selecione uma competência.");
    return;
  }
  const apuracao = await request(`/apuracao?competencia_id=${competenciaId}`);
  renderApuracao(apuracao);
}

function renderApuracao(apuracao) {
  const resumoBody = $("#apuracaoResumoTable");
  if (!apuracao.resumo.length) {
    renderEmpty(resumoBody, 6);
  } else {
    resumoBody.innerHTML = apuracao.resumo
      .map(
        (item) => `
          <tr>
            <td>${escapeHtml(item.funcionario)}</td>
            <td>${item.atrasos}</td>
            <td>${item.extras}</td>
            <td>${item.faltas}</td>
            <td>${item.atestados}</td>
            <td>${item.pendencias}</td>
          </tr>
        `,
      )
      .join("");
  }

  const pendenciasBody = $("#apuracaoPendenciasTable");
  if (!apuracao.pendencias.length) {
    renderEmpty(pendenciasBody, 4, "Sem pendências.");
  } else {
    pendenciasBody.innerHTML = apuracao.pendencias
      .map(
        (item) => `
          <tr>
            <td>${item.data}</td>
            <td>${escapeHtml(item.funcionario)}</td>
            <td>${escapeHtml(item.pendencia_motivo)}</td>
            <td>${escapeHtml(item.observacoes)}</td>
          </tr>
        `,
      )
      .join("");
  }
}

function openExcel() {
  const competenciaId = selectedValue("#relCompetenciaSelect");
  if (!competenciaId) {
    setNotice("Selecione uma competência.", true);
    return;
  }
  window.open(apiUrl(`/relatorios/excel?competencia_id=${competenciaId}`), "_blank");
}

function openPrintReport() {
  const competenciaId = selectedValue("#relCompetenciaSelect");
  if (!competenciaId) {
    setNotice("Selecione uma competência.", true);
    return;
  }
  window.open(apiUrl(`/relatorios/impressao?competencia_id=${competenciaId}`), "_blank");
}

function bindNavigation() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", async () => {
      state.view = button.dataset.view;
      document.querySelectorAll(".nav-button").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${state.view}`));
      if (state.view === "arquivos") await loadArquivos();
      if (state.view === "importar" && !state.importacao) limparPreviaImportacao();
      if (state.view === "conferencia") await loadMarcacoes();
      if (state.view === "apuracao") await loadApuracao();
    });
  });
}

function bindEvents() {
  $("#apiBase").value = state.apiBase;
  $("#apiBase").addEventListener("change", async (event) => {
    state.apiBase = event.target.value.replace(/\/$/, "");
    localStorage.setItem("onponto.apiBase", state.apiBase);
    await loadBaseData().catch((error) => setNotice(error.message, true));
  });

  $("#empresaForm").addEventListener("submit", (event) => saveEmpresa(event).catch((error) => setNotice(error.message, true)));
  $("#empresaNovo").addEventListener("click", resetEmpresaForm);
  $("#empresasTable").addEventListener("click", (event) => {
    const id = event.target.dataset.editEmpresa;
    if (id) editEmpresa(id);
  });

  $("#funcionarioForm").addEventListener("submit", (event) => saveFuncionario(event).catch((error) => setNotice(error.message, true)));
  $("#funcNovo").addEventListener("click", resetFuncionarioForm);
  $("#funcEmpresaSelect").addEventListener("change", () => {
    resetFuncionarioForm();
    renderFuncionarios();
  });
  $("#funcionariosTable").addEventListener("click", (event) => {
    const id = event.target.dataset.editFuncionario;
    if (id) editFuncionario(id);
  });

  $("#competenciaForm").addEventListener("submit", (event) => saveCompetencia(event).catch((error) => setNotice(error.message, true)));
  $("#compNovo").addEventListener("click", resetCompetenciaForm);
  $("#compEmpresaSelect").addEventListener("change", () => {
    resetCompetenciaForm();
    renderCompetencias();
  });
  $("#competenciasTable").addEventListener("click", (event) => {
    const id = event.target.dataset.editCompetencia;
    if (id) editCompetencia(id);
  });

  ["arq", "imp", "conf", "apu", "rel"].forEach((prefix) => {
    $(`#${prefix}EmpresaSelect`).addEventListener("change", async () => {
      updateCompetenciaSelect(prefix);
      if (prefix === "conf") updateFuncionarioSelect();
      if (prefix === "arq") await loadArquivos().catch((error) => setNotice(error.message, true));
      if (prefix === "imp") limparPreviaImportacao("Importe um arquivo para visualizar a prévia.");
      if (prefix === "conf") await loadMarcacoes().catch((error) => setNotice(error.message, true));
      if (prefix === "apu") await loadApuracao().catch((error) => setNotice(error.message, true));
    });
    $(`#${prefix}CompetenciaSelect`).addEventListener("change", async () => {
      if (prefix === "arq") await loadArquivos().catch((error) => setNotice(error.message, true));
      if (prefix === "imp") limparPreviaImportacao("Importe um arquivo para visualizar a prévia.");
      if (prefix === "conf") await loadMarcacoes().catch((error) => setNotice(error.message, true));
      if (prefix === "apu") await loadApuracao().catch((error) => setNotice(error.message, true));
    });
  });

  $("#confFuncionarioSelect").addEventListener("change", () => loadMarcacoes().catch((error) => setNotice(error.message, true)));
  $("#arquivoForm").addEventListener("submit", (event) => uploadArquivo(event).catch((error) => setNotice(error.message, true)));
  $("#importadorForm").addEventListener("submit", (event) => importarXlsxGenerico(event).catch((error) => setNotice(error.message, true)));
  $("#salvarImportacao").addEventListener("click", () => salvarMarcacoesImportadas().catch((error) => setNotice(error.message, true)));
  $("#marcacoesTable").addEventListener("click", (event) => {
    const data = event.target.dataset.saveMarcacao;
    if (data) saveMarcacao(data).catch((error) => setNotice(error.message, true));
  });
  $("#apuAtualizar").addEventListener("click", () => loadApuracao().catch((error) => setNotice(error.message, true)));
  $("#exportExcel").addEventListener("click", openExcel);
  $("#openPrintReport").addEventListener("click", openPrintReport);
}

async function init() {
  bindNavigation();
  bindEvents();
  resetEmpresaForm();
  resetFuncionarioForm();
  resetCompetenciaForm();
  limparPreviaImportacao();
  try {
    await loadBaseData();
  } catch (error) {
    $("#connectionStatus").textContent = "API offline";
    $("#connectionStatus").className = "status-pill error";
    setNotice(`Não foi possível conectar à API: ${error.message}`, true);
  }
}

init();
