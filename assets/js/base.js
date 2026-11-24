let facts = [];
let rules = [];
let activeTab = "facts";
let page = 1;
const pageSize = 10;
const search = document.querySelector("#base-search");
const factsList = document.querySelector("#facts-list");
const rulesList = document.querySelector("#rules-list");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function riskClass(risk) {
  return `risk-${String(risk).toLowerCase().replaceAll(" ", "-")}`;
}

function render() {
  const query = search.value.trim().toLocaleLowerCase("es");
  const activeRecords = activeTab === "facts" ? facts : rules;
  const filtered = activeRecords.filter((record) => JSON.stringify(record).toLocaleLowerCase("es").includes(query));
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  page = Math.min(page, pageCount);
  document.querySelectorAll(".data-tab").forEach((button) => button.classList.toggle("active", button.dataset.tab === activeTab));
  factsList.hidden = activeTab !== "facts";
  rulesList.hidden = activeTab !== "rules";
  document.querySelector("#data-caption").textContent = activeTab === "facts"
    ? "Hechos observados, condiciones de entrada y resultados históricos."
    : "Reglas activas ordenadas por prioridad. Sus condiciones se comparan al evaluar casos similares.";

  if (!filtered.length) {
    (activeTab === "facts" ? factsList : rulesList).innerHTML = '<div class="empty-state">No hay resultados para esa búsqueda.</div>';
  } else if (activeTab === "facts") {
    factsList.innerHTML = filtered.slice((page - 1) * pageSize, page * pageSize).map((fact) => `
      <article class="fact-card">
        <div class="fact-head"><div><span class="fact-id">${escapeHtml(fact.id)}</span><span class="fact-type">${escapeHtml(fact.type)}</span></div><span class="fact-risk ${riskClass(fact.risk)}">Riesgo ${escapeHtml(fact.risk)}</span></div>
        <div class="fact-conditions">
          <span class="condition-chip">Temp.: ${escapeHtml(fact.temperature)}</span><span class="condition-chip">Presión: ${escapeHtml(fact.pressure)}</span><span class="condition-chip">Tiempo: ${escapeHtml(fact.time)}</span><span class="condition-chip">Materia: ${escapeHtml(fact.rawMaterial)}</span><span class="condition-chip">Máquina: ${escapeHtml(fact.machineSettings)}</span>
        </div>
        <div class="fact-foot"><span>Regla <strong>${escapeHtml(fact.ruleId)}</strong></span><span>Acción esperada: <strong>${escapeHtml(fact.action)}</strong></span></div>
      </article>`).join("");
  } else {
    rulesList.innerHTML = filtered.map((rule) => `
      <article class="rule-card">
        <div class="rule-head"><span class="rule-id">${escapeHtml(rule.id)}</span><span class="rule-priority">Prioridad ${escapeHtml(rule.priority)}</span></div>
        <p class="rule-condition">${escapeHtml(rule.condition)}</p><p class="rule-result">${escapeHtml(rule.result)}</p>
      </article>`).join("");
  }

  const pageLabel = activeTab === "rules" ? `${filtered.length} regla(s)` : `${filtered.length ? (page - 1) * pageSize + 1 : 0}–${Math.min(page * pageSize, filtered.length)} de ${filtered.length} hechos`;
  document.querySelector("#page-label").textContent = pageLabel;
  document.querySelector("#page-prev").disabled = activeTab === "rules" || page <= 1;
  document.querySelector("#page-next").disabled = activeTab === "rules" || page >= pageCount;
}

document.querySelectorAll(".data-tab").forEach((button) => button.addEventListener("click", () => {
  activeTab = button.dataset.tab;
  page = 1;
  render();
}));
search.addEventListener("input", () => { page = 1; render(); });
document.querySelector("#page-prev").addEventListener("click", () => { page -= 1; render(); });
document.querySelector("#page-next").addEventListener("click", () => { page += 1; render(); });

async function loadBase() {
  const status = document.querySelector("#data-status");
  try {
    const response = await fetch("/api/base", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "No se pudieron consultar las bases.");
    facts = payload.facts;
    rules = payload.rules;
    document.querySelector("#fact-count").textContent = facts.length;
    document.querySelector("#rule-count").textContent = rules.length;
    const learned = Number(payload.status.learned || 0);
    status.textContent = `Neon · ${payload.status.facts} hechos Excel + ${learned} casos aprendidos · ${rules.length} reglas`;
    render();
  } catch (error) {
    status.textContent = error.message;
    factsList.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

loadBase();
