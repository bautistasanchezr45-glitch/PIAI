# Control de Calidad de Defectos

Primera etapa funcional: bienvenida, carga de las bases Excel y almacenamiento local en SQLite.

## Iniciar

1. Instala Python 3 si aún no está instalado.
2. Ejecuta `iniciar.bat`.
3. Abre http://127.0.0.1:8000 en tu navegador.
4. Entra a **Cargar archivos Excel**, selecciona `Base_Hechos.xlsx` y `Base_Reglas.xlsx`, y pulsa **Validar y guardar**.

No se requieren paquetes externos. El servidor lee `.xlsx` con la biblioteca estándar de Python y crea `data/control_calidad.db` al completar una importación correcta. Los dos libros se validan juntos antes de reemplazar los datos guardados.

## Estructura aceptada

- Hechos: `ID_Hecho`, `F1_Temperatura`, `F2_Presion`, `F3_Tiempo`, `F4_Materia_Prima`, `F5_Ajustes_Maquina`, `Regla_Aplicable`, `Riesgo_Esperado`, `Accion_Esperada`, `Tipo_Dato`.
- Reglas: `ID_Regla`, `Condición (SI...)`, `Acción / Resultado (ENTONCES...)`, `Prioridad`.

El servidor solo escucha en el equipo local (`127.0.0.1`).
