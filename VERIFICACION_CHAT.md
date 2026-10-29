# Verificación del chat analítico

Fecha: 29/10/2026.

## Alcance

- Consultas deterministas sobre los DataFrames validados del dashboard.
- Agente LangChain `create_agent`, herramientas tipadas y OpenAI Responses.
- Interfaz Streamlit, permisos comunes y aislamiento de sesiones.
- Cambios previos de navegación y ayuda conservados.

## Comprobaciones

Suite completa: **80 pruebas aprobadas** en la ejecución final. `pip check` sin
conflictos de dependencias y revisión de diferencias sin errores de espacios.

La suite incluye casos sintéticos de plan 106 y Documento, seguimientos a
Vigente, filtros heredados y contradictorios, cambio de período, importes
agrupados, claves duplicadas, cero, importes incompletos, registros ausentes,
cobertura desconocida, comparación mensual y denominador cero. Se prueba que
un error no reutiliza otra población para un seguimiento.

También verifica permisos de fuentes, entidad, detalle, datos personales y
auditoría; políticas OIDC con denegación por defecto; vencimiento e invalidación
de contexto; paginación; documentos con separadores; múltiples clientes para un
documento; errores del proveedor; y que las filas de detalle no lleguen al modelo.
Las pruebas existentes de `authorized_join` verifican que varios cobros no
multipliquen capital y que los mapas duplicados se rechacen. El chat no habilita
esa unión.

Las pruebas de interfaz usan AppTest y cargadores sustituidos para datos
sintéticos o fuentes reales locales, sin invocar OpenAI. Las pruebas existentes
con archivos reales continúan leyendo esos archivos localmente.

## Comprobación real de OpenAI

Se usó la clave ya configurada en el entorno, sin copiarla a archivos ni
mostrarla. GPT-5.5 respondió sobre una muestra sintética de tres préstamos:
plan 106 = 2; Documento de prueba = 2; seguimiento Vigente = 1.
Los tres resultados coincidieron con consultas directas. No se enviaron reportes
reales a OpenAI. No se habilitó tracing ni almacenamiento de Responses.

## Límites

No se verificó visualmente en navegador ni se configuró un proveedor OIDC real.
El acceso compartido necesita configurar el proveedor y sus políticas de
usuarios en el servidor. El modo local permanece limitado a loopback y los
datos personales están bloqueados por defecto. El ejemplo de configuración no
contiene credenciales y no se creó un archivo real de secretos.

La interpretación de Documento y los estados sigue limitada a los archivos
reportados: no se afirma existencia en un padrón maestro ni vigencia histórica.
