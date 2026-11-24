const form = document.querySelector("#analysis-form");
const analyzeButton = document.querySelector("#analyze-button");
const formError = document.querySelector("#form-error");
const databasePill = document.querySelector("#database-pill");
const databaseStatus = document.querySelector("#database-status");
const history = [];
let sessionState = null;
let lastAnalysisInputs = null;
const architectureSelect = document.querySelector("#architecture");
const architectureDescription = document.querySelector("#architecture-description");
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
    databaseStatus.textContent = `Neon conectado · ${status.facts} hechos · ${status.rules} reglas · ${status.learned || 0} aprendidos`;
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
  document.querySelector("#learning-panel").hidden = result.architecture !== "learning";

  const prediction = result.prediction;
  const predictionContent = document.querySelector("#prediction-content");
  if (prediction) {
    predictionContent.textContent = `${prediction.risk} · ${prediction.confidencePct}% en ${prediction.sampleCount} caso(s) · ${prediction.method}. ${prediction.tieBreak || "En empate se elige el riesgo de mayor severidad."} Distribución: ${prediction.distribution.map((item) => `${item.risk} ${item.percent}%`).join(" / ")}.`;
  } else {
    predictionContent.textContent = "No hay registros históricos para esta predicción.";
  }
  document.querySelector("#simulation-content").textContent = `${result.simulation.risk} · ${result.simulation.action}. ${result.simulation.reason}`;

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

  const trace = document.querySelector("#trace-list");
  trace.innerHTML = result.trace.map((step) => `<li><strong>${escapeHtml(step.title)}</strong><span>${escapeHtml(step.detail)}</span></li>`).join("");
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

  const severity = { "Bajo": 1, "Medio": 2, "Alto": 3, "Muy alto": 4 };
  const recent = history.slice(-5).map((item) => severity[item.risk]).filter(Boolean);
  const movingAverage = document.querySelector("#moving-average");
  if (!recent.length) {
    movingAverage.textContent = "Promedio móvil de riesgo (últimos 5): esperando análisis.";
  } else {
    const average = recent.reduce((sum, score) => sum + score, 0) / recent.length;
    let trend = `muestra ${recent.length}/${Math.min(history.length, 5)}`;
    if (history.length >= 6) {
      const previous = history.slice(-6, -3).map((item) => severity[item.risk]).filter(Boolean);
      const current = history.slice(-3).map((item) => severity[item.risk]).filter(Boolean);
      if (previous.length && current.length) {
        const delta = current.reduce((sum, score) => sum + score, 0) / current.length
          - previous.reduce((sum, score) => sum + score, 0) / previous.length;
        trend = delta > 0 ? `tendencia +${delta.toFixed(2)}` : delta < 0 ? `tendencia ${delta.toFixed(2)}` : "tendencia estable";
      }
    }
    movingAverage.textContent = `Promedio móvil de riesgo (últimos ${recent.length}): ${average.toFixed(2)}/4 · ${trend}.`;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.textContent = "";
  if (!form.reportValidity()) return;
  const inputs = Object.fromEntries(new FormData(form).entries());
  const architecture = inputs.architecture;
  delete inputs.architecture;
  lastAnalysisInputs = { ...inputs };
  inputs.architecture = architecture;
  inputs.previousState = sessionState;
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
    sessionState = result.nextState;
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
  architectureDescription.textContent = "Decide solo con las cinco condiciones actuales.";
  document.querySelector("#learning-panel").hidden = true;
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
  document.querySelector("#prediction-content").textContent = "Se calculará con los casos más parecidos de Base_Hechos.";
  document.querySelector("#simulation-content").textContent = "Aparecerá al ejecutar el escenario.";
  document.querySelector("#trace-list").innerHTML = "<li>Ejecuta un análisis para ver los cambios del entorno, las reglas y la decisión.</li>";
  document.querySelector("#learning-panel").hidden = true;
  document.querySelector("#learning-status").textContent = "";
  sessionState = null;
  lastAnalysisInputs = null;
  renderSummary();
});

architectureSelect.addEventListener("change", () => {
  const descriptions = {
    reactive: "Decide solo con las cinco condiciones actuales.",
    model: "Conserva los parámetros y la decisión de la observación anterior.",
    objectives: "Elige la acción con mayor utilidad: protección de calidad menos costo de intervención.",
    learning: "Usa frecuencias históricas y agrega resultados reales confirmados.",
    hybrid: "Combina el árbol PSeInt con las frecuencias históricas de Neon.",
  };
  architectureDescription.textContent = descriptions[architectureSelect.value];
  if (!lastAnalysisInputs) document.querySelector("#learning-panel").hidden = architectureSelect.value !== "learning";
});

document.querySelector("#learning-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.querySelector("#learning-status");
  if (!lastAnalysisInputs) return;
  const button = event.currentTarget.querySelector("button");
  button.disabled = true;
  status.textContent = "Guardando el caso observado en Neon…";
  try {
    const response = await fetch("/api/aprender", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...lastAnalysisInputs,
        observedRisk: document.querySelector("#observed-risk").value,
        observedAction: document.querySelector("#observed-action").value,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "No se pudo guardar el caso observado.");
    status.textContent = `Caso ${result.id} agregado al aprendizaje. Repite el análisis para actualizar la predicción.`;
    loadDatabaseStatus();
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

renderSummary();
loadDatabaseStatus();
