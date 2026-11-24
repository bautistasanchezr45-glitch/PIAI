# Control de Calidad de Defectos

La aplicación permite cargar y consultar las bases Excel, ejecutar el árbol de decisión del programa PSeInt y comparar arquitecturas de agente en una página web. En local se usa SQLite; en Vercel, las funciones de `api/` guardan y consultan Neon PostgreSQL.

## Iniciar

1. Instala Python 3 si aún no está instalado.
2. Ejecuta `iniciar.bat` (inicia `local_server.py`).
3. Abre http://127.0.0.1:8000 en tu navegador.
4. Entra a **Cargar archivos Excel**, selecciona `Base_Hechos.xlsx` y `Base_Reglas.xlsx`, y pulsa **Validar y guardar**.
5. Abre **Ejecutar análisis**, captura las cinco condiciones y pulsa **Analizar proceso**. La página conserva el resumen de riesgos y acciones durante la sesión.
6. En **Consultar bases** puedes buscar hechos y reglas; en **Comparar escenarios** puedes editar tres casos y evaluar cinco arquitecturas: reactiva, basada en modelos, objetivos, aprendizaje e híbrida.

El servidor local lee `.xlsx` con la biblioteca estándar de Python y crea `data/control_calidad.db` al completar una importación correcta. Los dos libros se validan juntos antes de reemplazar los datos guardados.

## Desplegar en Vercel con Neon

1. Importa este repositorio de GitHub como proyecto en Vercel.
2. Añade la integración de Neon al proyecto y habilita `DATABASE_URL` para Production y Preview.
3. Vercel detecta las funciones Python dentro de `api/`; `requirements.txt` instala el driver PostgreSQL.
4. Después del despliegue, abre la aplicación y vuelve a cargar `Base_Hechos.xlsx` y `Base_Reglas.xlsx` para copiarlos a Neon. La base SQLite local no se copia automáticamente.
5. Desde la bienvenida, entra a **Ejecutar análisis**. El resultado principal conserva la lógica PSeInt y muestra una referencia de Base_Hechos/Base_Reglas cuando hay una combinación coincidente.
6. **Consultar bases** permite buscar los registros de Neon. **Comparar escenarios** separa el resultado simulado PSeInt, la frecuencia predictiva y el dato histórico.
7. La arquitectura **Aprendizaje** registra un caso nuevo solo cuando el usuario confirma el riesgo y la acción observados; esos casos se guardan aparte en Neon y se incorporan a las frecuencias siguientes.

No pongas `DATABASE_URL` en el código ni la subas a GitHub. Las funciones usan esa variable del entorno de Vercel.

## Estructura aceptada

- Hechos: `ID_Hecho`, `F1_Temperatura`, `F2_Presion`, `F3_Tiempo`, `F4_Materia_Prima`, `F5_Ajustes_Maquina`, `Regla_Aplicable`, `Riesgo_Esperado`, `Accion_Esperada`, `Tipo_Dato`.
- Reglas: `ID_Regla`, `Condición (SI...)`, `Acción / Resultado (ENTONCES...)`, `Prioridad`.

El servidor solo escucha en el equipo local (`127.0.0.1`).

## Organización del proyecto

- Las páginas HTML (`index.html`, `analizar.html`, `importar.html`, `base.html`, `comparar.html`) permanecen en la raíz para conservar las rutas públicas de Vercel.
- `assets/css/` contiene los estilos de la interfaz y `assets/js/` los scripts de las páginas.
- `api/` contiene las funciones web de Vercel; `neon_storage.py` conecta esas funciones con Neon.
- `local_server.py` e `iniciar.bat` permiten usar la aplicación localmente; `data/control_calidad.db` es la base SQLite local.
- `__pycache__/` es una carpeta temporal que Python crea al ejecutar el servidor y puede regenerar.
