const form = document.querySelector("#analysis-form");
const analyzeButton = document.querySelector("#analyze-button");
const formError = document.querySelector("#form-error");
const databasePill = document.querySelector("#database-pill");
const databaseStatus = document.querySelector("#database-status");
const history = [];
const risks = ["Bajo", "Medio", "Alto", "Muy alto", "Indefinida"];
const actions = [
  "Continuar producción",
  "Ajustar parámetros",
  "Inspeccionar producto",
  "Retener lote",
  "Detener proceso",
  "Sin determinar",
];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function riskClass(value) {
  return `risk-${value.toLowerCase().replaceAll(" ", "-")}`;
}

async function loadDatabaseStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const status = await response.json();
    if (!response.ok || !status.loaded) {
      databasePill.classList.add("error");
      databaseStatus.textContent = status.error || "Carga las bases antes de analizar";
      return;
    }
    databasePill.classList.add("connected");
    databaseStatus.textContent = `Neon conectado · ${status.facts} hechos · ${status.rules} reglas`;
    analyzeButton.disabled = false;
  } catch {
    databasePill.classList.add("error");
    databaseStatus.textContent = "No se pudo consultar Neon";
  }
}

function showResult(result) {
  document.querySelector("#result-title").textContent = "Evaluación completada";
  const badge = document.querySelector("#risk-badge");
  badge.textContent = result.risk;
  badge.className = `risk-badge ${riskClass(result.risk)}`;
  document.querySelector("#result-action").textContent = result.action;
  document.querySelector("#result-reason").textContent = result.reason;

  const referenceBox = document.querySelector("#reference-box");
  const referenceContent = document.querySelector("#reference-content");
  const reference = result.databaseReference;
  referenceBox.classList.toggle("conflict", Boolean(reference && (!reference.sameRisk || !reference.sameAction)));
  if (!reference) {
    referenceContent.textContent = "No existe una combinación idéntica en Base_Hechos. Se aplicó el árbol PSeInt.";
  } else {
    const outcome = `${escapeHtml(reference.risk)} · ${escapeHtml(reference.action)}`;
    const agreement = reference.sameRisk && reference.sameAction
      ? "La referencia coincide con el resultado PSeInt."
      : `La base registra ${outcome}; el resultado principal conserva el árbol PSeInt.`;
    referenceContent.innerHTML = `<strong>${escapeHtml(reference.factId)}</strong> · ${reference.examples} caso(s) coincidente(s) · Regla ${escapeHtml(reference.ruleId)} (prioridad ${escapeHtml(reference.priority)}).<br>${escapeHtml(agreement)}<br><span>${escapeHtml(reference.condition || "")}</span>`;
  }
}

function renderSummary() {
  document.querySelector("#analysis-count").textContent = history.length;
  document.querySelector("#reset-session").disabled = history.length === 0;
  const riskCounts = Object.fromEntries(risks.map((risk) => [risk, history.filter((item) => item.risk === risk).length]));
  const container = document.querySelector("#risk-summary");
  container.innerHTML = risks.map((risk) => {
    const count = riskCounts[risk];
    const percent = history.length ? Math.round((count / history.length) * 100) : 0;
    return `<div class="risk-row"><span class="risk-label">${escapeHtml(risk)}</span><div class="risk-track"><div class="risk-fill ${riskClass(risk)}" style="width:${percent}%"></div></div><span class="risk-percent">${percent}%</span></div>`;
  }).join("");

  const actionCounts = Object.fromEntries(actions.map((action) => [action, history.filter((item) => item.action === action).length]));
  const maxCount = Math.max(0, ...Object.values(actionCounts));
  const topActions = maxCount ? actions.filter((action) => actionCounts[action] === maxCount) : [];
  const topLabel = !topActions.length
    ? "La acción más recomendada aparecerá aquí."
    : `${topActions.length > 1 ? "Acciones empatadas" : "Acción más recomendada"}: ${topActions.map(escapeHtml).join(" / ")} · ${Math.round((maxCount / history.length) * 100)}%`;
  document.querySelector("#top-action").textContent = topLabel;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";
  if (!form.reportValidity()) return;
  const inputs = Object.fromEntries(new FormData(form).entries());
  analyzeButton.disabled = true;
  analyzeButton.innerHTML = "Analizando… <span aria-hidden=\"true\">◌</span>";
  try {
    const response = await fetch("/api/clasificar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inputs),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "No se pudo analizar el proceso.");
    showResult(result);
    history.push({ risk: result.risk, action: result.action });
    renderSummary();
  } catch (error) {
    formError.textContent = error.message || "No se pudo conectar con el servicio de análisis.";
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.innerHTML = "Analizar proceso <span aria-hidden=\"true\">→</span>";
  }
});

form.addEventListener("reset", () => {
  formError.textContent = "";
});

document.querySelector("#reset-session").addEventListener("click", () => {
  history.length = 0;
  form.reset();
  document.querySelector("#result-title").textContent = "Esperando análisis";
  document.querySelector("#risk-badge").textContent = "—";
  document.querySelector("#risk-badge").className = "risk-badge risk-empty";
  document.querySelector("#result-action").textContent = "Completa las condiciones y pulsa «Analizar proceso».";
  document.querySelector("#result-reason").textContent = "La evaluación aplicará el árbol de decisión del programa PSeInt.";
  document.querySelector("#reference-box").classList.remove("conflict");
  document.querySelector("#reference-content").textContent = "El resultado mostrará si existe un caso coincidente en Neon.";
  renderSummary();
});

renderSummary();
loadDatabaseStatus();
