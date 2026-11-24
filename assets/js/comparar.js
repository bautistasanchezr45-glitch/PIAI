const fieldOptions = [
  { key: "temperature", label: "Temperatura", values: ["Correcta", "Fuera de especificación"] },
  { key: "pressure", label: "Presión", values: ["Correcta", "Incorrecta"] },
  { key: "time", label: "Tiempo", values: ["Adecuado", "Inadecuado"] },
  { key: "rawMaterial", label: "Materia prima", values: ["Conforme", "No conforme"] },
  { key: "machineSettings", label: "Ajustes", values: ["Correctos", "Incorrectos"] },
];
const presets = {
  a: { temperature: "Correcta", pressure: "Correcta", time: "Adecuado", rawMaterial: "Conforme", machineSettings: "Correctos" },
  b: { temperature: "Fuera de especificación", pressure: "Correcta", time: "Adecuado", rawMaterial: "Conforme", machineSettings: "Correctos" },
  c: { temperature: "Correcta", pressure: "Incorrecta", time: "Adecuado", rawMaterial: "Conforme", machineSettings: "Incorrectos" },
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function makeScenarioForms() {
  document.querySelectorAll(".scenario-card").forEach((card) => {
    const key = card.dataset.scenario;
    card.querySelector(".scenario-fields").innerHTML = fieldOptions.map((field) => `
      <label class="scenario-field"><span>${field.label}</span><select data-field="${field.key}" required>${field.values.map((value) => `<option value="${escapeHtml(value)}" ${presets[key][field.key] === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}</select></label>`).join("");
  });
}

function scenarioInputs(card) {
  return Object.fromEntries([...card.querySelectorAll("select[data-field]")].map((select) => [select.dataset.field, select.value]));
}

function renderScenario(card, result) {
  const prediction = result.prediction;
  const historical = result.databaseReference
    ? `${result.databaseReference.factId}: ${result.databaseReference.risk} · ${result.databaseReference.action} (${result.databaseReference.type})`
    : "No hay un hecho con coincidencia exacta.";
  const predicted = prediction
    ? `${prediction.risk} · ${prediction.action} · confianza ${prediction.confidencePct}% de ${prediction.sampleCount} caso(s). ${prediction.method}.`
    : "Sin muestra histórica suficiente.";
  return `<article class="comparison-card">
    <h2>${escapeHtml(card.querySelector(".scenario-title span").textContent)}</h2>
    <div class="comparison-final">Decisión ${escapeHtml(result.architecture)}: ${escapeHtml(result.risk)} · ${escapeHtml(result.action)}</div>
    <div class="comparison-line"><strong>Resultado simulado · árbol PSeInt</strong>${escapeHtml(result.simulation.risk)} · ${escapeHtml(result.simulation.action)}</div>
    <div class="comparison-line"><strong>Predicción · frecuencia de Neon</strong>${escapeHtml(predicted)}</div>
    <div class="comparison-history"><strong>Dato histórico · no es esta simulación</strong><br>${escapeHtml(historical)}</div>
    <div class="comparison-line"><strong>Método</strong>${escapeHtml(result.reason)}</div>
  </article>`;
}

document.querySelector("#compare-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!event.currentTarget.reportValidity()) return;
  const button = document.querySelector("#compare-button");
  const status = document.querySelector("#compare-status");
  const results = document.querySelector("#compare-results");
  const architecture = document.querySelector("#compare-architecture").value;
  button.disabled = true;
  button.textContent = "Comparando…";
  status.textContent = "Consultando PSeInt y los casos históricos de Neon…";
  try {
    const cards = [...document.querySelectorAll(".scenario-card")];
    let previousState = null;
    const outputs = [];
    for (const card of cards) {
      const response = await fetch("/api/clasificar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...scenarioInputs(card), architecture, previousState }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "No se pudo evaluar un escenario.");
      outputs.push(renderScenario(card, result));
      previousState = result.nextState;
    }
    results.innerHTML = outputs.join("");
    status.textContent = "Comparación lista: predicción, dato histórico y resultado simulado están separados; los escenarios recorren el estado en orden.";
  } catch (error) {
    results.innerHTML = `<div class="compare-error">${escapeHtml(error.message)}</div>`;
    status.textContent = "No se completó la comparación.";
  } finally {
    button.disabled = false;
    button.innerHTML = "Comparar los tres <span aria-hidden=\"true\">→</span>";
  }
});

makeScenarioForms();
