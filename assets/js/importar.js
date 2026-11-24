const uploadForm = document.querySelector("#import-form");
const feedback = document.querySelector("#feedback");
const submitButton = document.querySelector("#submit-button");

function describeFile(inputId, labelId, placeholder) {
  const input = document.querySelector(inputId);
  const label = document.querySelector(labelId);
  input.addEventListener("change", () => {
    const file = input.files[0];
    label.textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(0)} KB` : placeholder;
    input.closest(".file-card").classList.toggle("has-file", Boolean(file));
  });
}

describeFile("#facts-file", "#facts-name", "Selecciona Base_Hechos.xlsx");
describeFile("#rules-file", "#rules-name", "Selecciona Base_Reglas.xlsx");

fetch("/api/status")
  .then((response) => response.json())
  .then((status) => {
    const statusLabel = document.querySelector("#database-status");
    if (status.loaded) {
      statusLabel.textContent = `${status.facts} hechos y ${status.rules} reglas cargados · ${status.importedAt}`;
    } else {
      statusLabel.textContent = status.error || "Todavía no hay bases cargadas.";
    }
  })
  .catch(() => {
    document.querySelector("#database-status").textContent = "No se pudo consultar el estado de la base conectada.";
  });

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  feedback.className = "feedback";
  feedback.textContent = "";
  const facts = document.querySelector("#facts-file").files[0];
  const rules = document.querySelector("#rules-file").files[0];
  if (!facts || !rules) return;
  if (!facts.name.toLowerCase().endsWith(".xlsx") || !rules.name.toLowerCase().endsWith(".xlsx")) {
    showError(["Selecciona ambos archivos en formato .xlsx."]);
    return;
  }

  const body = new FormData();
  body.append("facts", facts);
  body.append("rules", rules);
  submitButton.disabled = true;
  submitButton.innerHTML = "Validando archivos… <span>◌</span>";

  try {
    const response = await fetch("/api/importar", { method: "POST", body });
    const result = await response.json();
    if (!response.ok) {
      showError(result.errors || [result.error || "No se pudieron importar los archivos."]);
      return;
    }
    feedback.className = "feedback visible success";
    feedback.innerHTML = `<strong>¡Bases cargadas correctamente!</strong>Se guardaron ${result.facts} hechos y ${result.rules} reglas en la base de datos conectada. <a href="analizar.html">Ejecutar análisis →</a>`;
    document.querySelector("#facts-name").textContent = `${facts.name} · ${result.facts} registros importados`;
    document.querySelector("#rules-name").textContent = `${rules.name} · ${result.rules} reglas importadas`;
    document.querySelector("#database-status").textContent = `${result.facts} hechos y ${result.rules} reglas cargados en Neon.`;
  } catch (error) {
    showError(["No se pudo conectar con el servicio. Actualiza la página e inténtalo de nuevo."]);
  } finally {
    submitButton.disabled = false;
    submitButton.innerHTML = "Validar y guardar <span aria-hidden=\"true\">→</span>";
  }
});

function showError(errors) {
  feedback.className = "feedback visible error";
  const title = document.createElement("strong");
  title.textContent = "No se guardaron los archivos. Revisa lo siguiente:";
  const list = document.createElement("ul");
  for (const message of errors) {
    const item = document.createElement("li");
    item.textContent = message;
    list.append(item);
  }
  feedback.replaceChildren(title, list);
}
