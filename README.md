<div align="center">

# 🏭 Control de Calidad de Defectos

**Aplicación web para analizar condiciones de producción y apoyar decisiones de calidad.**

[![Aplicación web](https://img.shields.io/badge/Aplicaci%C3%B3n-piai--ten.vercel.app-397c61?style=for-the-badge&logo=vercel&logoColor=white)](https://piai-ten.vercel.app)
[![Interfaz](https://img.shields.io/badge/Interfaz-HTML%20%7C%20CSS%20%7C%20JavaScript-526b5b?style=for-the-badge)](#tecnologías)
[![Datos](https://img.shields.io/badge/Base%20de%20datos-Neon%20PostgreSQL-168f78?style=for-the-badge)](#arquitectura)

[Aplicación](https://piai-ten.vercel.app) · [Cargar bases](https://piai-ten.vercel.app/importar.html) · [Consultar hechos y reglas](https://piai-ten.vercel.app/base.html) · [Comparar escenarios](https://piai-ten.vercel.app/comparar.html)

</div>

---

## 📌 Descripción

Este proyecto convierte la lógica del programa de PSeInt **Control de Calidad de Defectos** en una aplicación web. La persona usuaria carga las bases de hechos y reglas, captura las condiciones de un proceso y consulta una decisión, una referencia histórica y una predicción basada en los datos almacenados.

La aplicación distingue tres resultados para evitar confusiones:

| Resultado | Qué representa |
|---|---|
| **Simulación PSeInt** | Salida del árbol de decisión trasladado desde el pseudocódigo. |
| **Predicción** | Riesgo y acción más frecuentes en los casos de la base con condiciones más cercanas. |
| **Dato histórico** | Registro ya almacenado que se muestra como referencia; no es la corrida actual. |

## ✨ Funciones

- **Carga de datos:** valida y guarda conjuntamente `Base_Hechos.xlsx` y `Base_Reglas.xlsx` en Neon.
- **Consulta:** permite buscar y revisar hechos históricos y reglas del sistema.
- **Simulación:** acepta cinco condiciones de proceso y permite ejecutar nuevos escenarios o reiniciar la sesión.
- **Recorrido explicable:** muestra entrada, cambios de estado, predicción, decisión y referencia de regla cuando hay un hecho coincidente.
- **Indicadores:** presenta conteos de la sesión, distribución de riesgos, acción más frecuente y promedio móvil de riesgo sobre los últimos cinco análisis.
- **Comparación:** evalúa tres escenarios editables y separa predicción, referencia histórica y simulación.
- **Aprendizaje:** en esa arquitectura se puede registrar un riesgo y una acción observados; el caso queda guardado en Neon y participa en predicciones posteriores.
- **Diseño adaptable:** las páginas se ajustan a pantallas grandes y móviles.

## 🧠 Arquitecturas disponibles

| Arquitectura | Comportamiento que se puede mostrar |
|---|---|
| **Reactiva** | Responde a las cinco condiciones actuales. |
| **Basada en modelos** | Conserva el estado de la corrida anterior y muestra cambios al pasar al siguiente escenario. |
| **Orientada a objetivos** | Elige una acción según una utilidad que pondera protección de calidad y costo de intervención. |
| **Aprendizaje** | Incorpora casos etiquetados como observaciones nuevas. |
| **Híbrida** | Combina el árbol PSeInt con la frecuencia histórica para resolver el caso. |

### Método predictivo

El sistema compara cada entrada con los cinco campos categóricos de los hechos. Prioriza la menor cantidad de diferencias (distancia de Hamming) y calcula las frecuencias de riesgo y acción dentro de ese grupo de casos. La confianza es el porcentaje de casos cercanos que comparte el resultado seleccionado; si hay empate de riesgo, se elige el de mayor severidad.

## 🧰 Tecnologías

- **Interfaz:** HTML, CSS y JavaScript.
- **Funciones web:** Python en Vercel (`api/`).
- **Base de datos:** Neon PostgreSQL.
- **Control de versiones:** Git y GitHub.

## 🏗️ Arquitectura

```text
Navegador
  ├── Páginas HTML y recursos en assets/
  └── Solicitudes a /api/* en Vercel
          ├── importar.py  → excel_parser.py → Neon
          ├── status.py    → Neon
          ├── base.py      → Neon
          ├── clasificar.py → Neon + árbol de decisión
          └── aprender.py  → Neon
```

`DATABASE_URL` se configura como variable de entorno en Vercel. **No debe incluirse en el repositorio ni en este README.**

## 📚 Bitácora de desarrollo con IA generativa

**Asistente utilizado:** Codex, asistente de programación con IA. La IA se utilizó para proponer y editar código a partir de instrucciones iterativas. Los prompts de la tabla están resumidos para la bitácora; no son transcripciones literales.

| Etapa | Prompt representativo | Ajustes realizados |
|---|---|---|
| 1. Interfaz | “Quiero pasar mi programa de PSeInt a una página web. Empecemos por la bienvenida y la interfaz.” | Se creó la página de bienvenida y navegación hacia las funciones principales. |
| 2. Carga de Excel | “La página debe pedir Base de Hechos y Base de Reglas, procesarlos y guardarlos en una base de datos.” | Se añadió carga de ambos libros, validación de estructura y guardado en Neon. |
| 3. Despliegue | “Quiero usar Vercel para la página y Neon para la base de datos; ayúdame a conectarlos.” | Se prepararon las funciones Python y la configuración para Vercel y Neon. |
| 4. Corrección de errores | Se compartieron mensajes de error del despliegue y capturas de respuestas 404 de la API. | Se ajustó la configuración de Vercel y se corrigieron las rutas de las funciones. |
| 5. Visualización | “Ya cargué las bases; falta poder visualizar los datos y mostrar las reglas.” | Se agregó la vista de consulta de hechos y reglas con búsqueda. |
| 6. Simulación | “Permite cambiar variables, ejecutar y reiniciar, mostrar estados paso a paso, indicadores y comparar escenarios.” | Se incorporaron el análisis de cinco condiciones, el recorrido, indicadores y comparación de tres escenarios. |
| 7. Arquitecturas | Se solicitaron pruebas para agentes reactivos, basados en modelos, objetivos, aprendizaje e híbridos. | Se añadieron los modos de arquitectura y un formulario para guardar resultados observados en el modo de aprendizaje. |
| 8. Organización | “Ya no utilizaré el servidor local porque la app está en Vercel y Neon; quita lo que sea local.” | Se retiraron el servidor local y SQLite. El lector de Excel se separó para conservar la importación en Vercel. |

## ✅ Pruebas y evidencia

- **Carga de Excel:** durante el desarrollo, la interfaz confirmó **200 hechos y 10 reglas** guardados en la base conectada.
- **Despliegue:** Vercel mostró una versión en estado **Ready** durante la puesta en marcha.
- **Prueba de arquitectura:** para la exposición, selecciona una arquitectura y presenta el escenario que demuestra su comportamiento. Por ejemplo, en aprendizaje, registra un caso observado y vuelve a analizarlo.
- **Revisión final recomendada:** después del último despliegue, recorrer la carga, consulta, simulación, comparación y arquitectura elegida en la URL de producción; guardar capturas o una grabación breve como evidencia.

> Las capturas sirven como evidencia complementaria. La entrega debe incluir también el enlace funcional, el código fuente y la bitácora.

## 📂 Organización del repositorio

```text
.
├── api/                 # Funciones web de Vercel
├── assets/
│   ├── css/             # Estilos
│   └── js/              # Scripts de interfaz
├── excel_parser.py      # Lectura y validación de libros .xlsx
├── neon_storage.py      # Acceso a Neon PostgreSQL
├── index.html           # Bienvenida
├── analizar.html        # Simulación del proceso
├── importar.html        # Carga de bases Excel
├── base.html            # Consulta de hechos y reglas
├── comparar.html        # Comparación de escenarios
├── requirements.txt     # Dependencias Python
└── vercel.json          # Configuración de Vercel
```

## 📊 Estructura esperada de las bases

**Base de hechos:** `ID_Hecho`, `F1_Temperatura`, `F2_Presion`, `F3_Tiempo`, `F4_Materia_Prima`, `F5_Ajustes_Maquina`, `Regla_Aplicable`, `Riesgo_Esperado`, `Accion_Esperada`, `Tipo_Dato`.

**Base de reglas:** `ID_Regla`, `Condición (SI...)`, `Acción / Resultado (ENTONCES...)`, `Prioridad`.

## 🚀 Uso de la aplicación

1. Abre la [aplicación web](https://piai-ten.vercel.app).
2. Entra a **Cargar bases Excel** y selecciona los dos libros `.xlsx`.
3. Consulta los registros en **Consultar hechos y reglas**.
4. Ejecuta una evaluación desde **Ejecutar análisis** o modifica tres casos en **Comparar escenarios**.
5. Selecciona la arquitectura que vas a demostrar y conserva evidencia del resultado.

---

<div align="center">

**Proyecto académico · Control de calidad y análisis de defectos**

</div>
