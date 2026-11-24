# Control de Calidad de Defectos

Aplicación web para cargar y consultar bases Excel, ejecutar el árbol de decisión PSeInt y comparar arquitecturas de agente. Vercel sirve la interfaz y ejecuta las funciones de `api/`; Neon PostgreSQL almacena los datos y los casos aprendidos.

## Despliegue en Vercel y Neon

1. Importa este repositorio de GitHub como proyecto en Vercel.
2. Conecta Neon al proyecto y habilita `DATABASE_URL` para Production y Preview.
3. Vercel detecta las funciones Python en `api/`; `requirements.txt` instala el controlador PostgreSQL.
4. En la aplicación desplegada, abre **Cargar bases Excel** y carga `Base_Hechos.xlsx` y `Base_Reglas.xlsx` para guardarlos en Neon.
5. Usa **Ejecutar análisis** para evaluar las cinco condiciones del proceso.
6. **Consultar bases** muestra hechos y reglas; **Comparar escenarios** evalúa tres casos con cinco arquitecturas: reactiva, basada en modelos, objetivos, aprendizaje e híbrida.
7. El modo **Aprendizaje** guarda un caso cuando se confirma su riesgo y acción observados. Los incorpora a las predicciones siguientes.

No pongas `DATABASE_URL` en el código ni la subas a GitHub. Las funciones la leen de las variables de entorno de Vercel.

## Archivos y datos

- Las páginas HTML están en la raíz para conservar sus rutas públicas.
- `assets/css/` contiene los estilos y `assets/js/` los scripts de la interfaz.
- `api/` contiene las funciones de Vercel; `neon_storage.py` gestiona las consultas a Neon.
- `excel_parser.py` lee y valida los libros `.xlsx` recibidos por la función de importación.
- `requirements.txt` declara las dependencias del servidor.

## Estructura de los Excel

- Hechos: `ID_Hecho`, `F1_Temperatura`, `F2_Presion`, `F3_Tiempo`, `F4_Materia_Prima`, `F5_Ajustes_Maquina`, `Regla_Aplicable`, `Riesgo_Esperado`, `Accion_Esperada`, `Tipo_Dato`.
- Reglas: `ID_Regla`, `Condición (SI...)`, `Acción / Resultado (ENTONCES...)`, `Prioridad`.
