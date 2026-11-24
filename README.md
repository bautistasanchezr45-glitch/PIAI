# Control de Calidad de Defectos

Primera etapa funcional: bienvenida, carga de las bases Excel y almacenamiento. En ejecución local se usa SQLite; en Vercel, las funciones de `api/` guardan en Neon PostgreSQL.

## Iniciar

1. Instala Python 3 si aún no está instalado.
2. Ejecuta `iniciar.bat` (inicia `local_server.py`).
3. Abre http://127.0.0.1:8000 en tu navegador.
4. Entra a **Cargar archivos Excel**, selecciona `Base_Hechos.xlsx` y `Base_Reglas.xlsx`, y pulsa **Validar y guardar**.

El servidor local lee `.xlsx` con la biblioteca estándar de Python y crea `data/control_calidad.db` al completar una importación correcta. Los dos libros se validan juntos antes de reemplazar los datos guardados.

## Desplegar en Vercel con Neon

1. Importa este repositorio de GitHub como proyecto en Vercel.
2. Añade la integración de Neon al proyecto y habilita `DATABASE_URL` para Production y Preview.
3. Vercel detecta las funciones Python dentro de `api/`; `requirements.txt` instala el driver PostgreSQL.
4. Después del despliegue, abre la aplicación y vuelve a cargar `Base_Hechos.xlsx` y `Base_Reglas.xlsx` para copiarlos a Neon. La base SQLite local no se copia automáticamente.

No pongas `DATABASE_URL` en el código ni la subas a GitHub. Las funciones usan esa variable del entorno de Vercel.

## Estructura aceptada

- Hechos: `ID_Hecho`, `F1_Temperatura`, `F2_Presion`, `F3_Tiempo`, `F4_Materia_Prima`, `F5_Ajustes_Maquina`, `Regla_Aplicable`, `Riesgo_Esperado`, `Accion_Esperada`, `Tipo_Dato`.
- Reglas: `ID_Regla`, `Condición (SI...)`, `Acción / Resultado (ENTONCES...)`, `Prioridad`.

El servidor solo escucha en el equipo local (`127.0.0.1`).
