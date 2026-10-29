# Gestión de préstamos y cobranzas

## Chat analítico

El botón flotante **Conversá con tus datos**, siempre abajo a la derecha, abre el chat para consultar en
español las fuentes cargadas. Usa LangChain `create_agent` y OpenAI Responses con
`gpt-5.5` por defecto. Las funciones del servidor realizan los cálculos con las
métricas existentes; no se ejecuta SQL ni código generado. El chat no modifica
registros ni archivos cargados.

Instalar las dependencias de `requirements.txt` en el entorno del proyecto. La
clave se obtiene de `OPENAI_API_KEY` o de `[chat].api_key` en
`.streamlit/secrets.toml`. El modelo se puede cambiar con `OPENAI_MODEL` o
`[chat].model`; no hay sustitución automática si la cuenta no tiene acceso.
La configuración de ejemplo está en `.streamlit/secrets.example.toml`. El archivo
real de secretos está excluido de Git. Nunca introducir claves en el chat.

Por defecto se conservan los filtros de cada fuente. Un período explícito cambia
el alcance de esa consulta sin cambiar los filtros visuales. Un filtro
contradictorio requiere aclaración. Las selecciones que abren registros de un
gráfico no modifican los indicadores ni se heredan como filtros globales.
Reemplazar archivos, filtros, permisos o reglas inicia una conversación nueva.
El historial y las referencias personales viven solo en la sesión, vencen a los
30 minutos de inactividad y se pueden borrar con **Nueva conversación**.

El chat admite **5 preguntas por navegador**, sin reinicio diario. El contador se
guarda en `localStorage` bajo `piloto-dashboard.chat.questions.v1`, sin preguntas
ni datos personales, y persiste al recargar, cerrar o volver a abrir el sitio.
Cada envío consume una pregunta, incluyendo aclaraciones, denegaciones y errores.
La reserva se persiste antes de llamar a OpenAI y se sincroniza entre pestañas.
Nueva conversación, filtros y cambios de archivos no reinician el cupo. Si el
almacenamiento no está disponible, el chat queda bloqueado. Este límite depende
del navegador y del origen del sitio; borrar el almacenamiento o usar otro
navegador lo reinicia. Un límite por identidad resistente a esa manipulación
requeriría persistencia de servidor.

Ejemplos: “¿Cuántos préstamos del plan 106 tenemos colocados?”, “¿Qué capital
colocamos por plan este mes?”, “¿Cómo evolucionó el capital colocado respecto del
mes anterior?”, “¿Y de esos cuántos están vigentes?”. El panel muestra fuente,
filtros, período, corte, fecha de carga, cobertura y limitaciones. La fecha de
carga no se presenta como actualización del sistema de origen.

“Colocados” usa la definición existente **Préstamos otorgados**: claves distintas
de entidad y préstamo de registros incluidos, tanto Vigente como Cancelado salvo
filtro explícito. “Monto colocado” usa **Capital colocado**; el monto contractual
es otra métrica. No se deduce vigencia histórica o DNI a partir de saldo o CUIL.
Los préstamos por Documento se consultan solo en Préstamos Detalle; no se infiere
un padrón maestro ni se afirma inexistencia fuera de los archivos. Si el documento
corresponde a varios clientes, se solicita acotar o confirmar el conjunto.

### Acceso y privacidad

El modo predeterminado es **local**, restringido a loopback. Permite agregados,
detalle sin identificadores y auditoría. Las consultas por Documento y la
visualización/exportación de datos personales están bloqueadas por defecto,
incluso si se manipula la casilla de la interfaz. Para habilitarlas en un piloto
local autorizado, configurar `[access.local] personal = true` en el servidor.
Esa decisión no se puede tomar desde el chat.

Para uso compartido, configurar `[access] mode = "oidc"`, el proveedor `[auth]` de
Streamlit y las políticas `[access.users."issuer|sub"]` del ejemplo. Usuarios no
registrados quedan denegados. Los alcances `sources`, `entities` y `branches`, y
los permisos `personal`, `detail` y `audit`, se aplican en servidor al dashboard,
descargas y herramientas. Las fuentes sin dimensiones suficientes para aplicar
un alcance parcial se bloquean; no se reparten agregados por inferencia. Los
controles originales de toda la población se ocultan a usuarios con alcance
parcial. OIDC necesita completar datos reales del proveedor antes del despliegue.

Los cachés de lectura incluyen una clave de sesión. Los agentes y referencias
privadas no se cachean globalmente. Los documentos numéricos largos se reemplazan
por referencias opacas antes de enviar preguntas a OpenAI. Las filas de detalle
se muestran localmente y no se envían al modelo; las consultas agregadas envían
solo resultados y metadatos necesarios. El texto libre de las preguntas se envía
al proveedor: evitar incluir nombres u otros datos personales innecesarios.
El tracing de LangSmith está deshabilitado en las llamadas del chat; no se
registran prompts, documentos ni errores externos con sus argumentos. Los
registros se tratan como datos sin autoridad para dar instrucciones.

El chat limita longitud de pregunta, llamadas al modelo, herramientas, grupos y
páginas de detalle. Un error de OpenAI no muestra resultados parciales como una
respuesta completa. Se distinguen cero, resultado vacío, fuente faltante,
importe incompleto y acceso denegado. Las definiciones se recuperan del
diccionario sin embeddings ni infraestructura vectorial.

### Verificación del chat

`tests/test_chat_queries.py` compara consultas con cálculos directos, claves
distintas y métricas del dashboard. `tests/test_chat_agent.py` ejecuta el agente
con un modelo simulado sin red. `tests/test_chat_ui.py` prueba envío, seguimiento,
restablecimiento, errores y permisos con AppTest y fuentes sintéticas aisladas.
Las pruebas sintéticas no se muestran como datos reales de la aplicación.

Se verificaron además llamadas reales a GPT-5.5 para plan 106, DNI y seguimiento,
con una muestra sintética mínima. No se enviaron reportes reales para esas comprobaciones. La configuración OIDC y sus
permisos deben verificarse contra el proveedor elegido antes del uso multiusuario.

Aplicación local para gerencia y operaciones. Permite cargar independientemente siete tipos de reporte XLSX: tres de detalle y cuatro agregados gerenciales. Incluye colocación, cobranzas, cartera, proyección y morosidad, calidad y diccionario. La interfaz está en español. Los archivos originales no se modifican y no se copian al proyecto.

## Instalación y ejecución

Probado en Windows con Python 3.13 y las versiones fijadas en `requirements.txt`.

```powershell
cd C:\Work\SystemMaster\Dashboards\Piloto
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abrir http://localhost:8501. El entorno `.venv` ya se preparó en esta entrega. Si la creación de un entorno no instala pip, puede usarse el pip del Python principal: `python -m pip --python .venv\Scripts\python.exe install -r requirements.txt`.

## Uso diario

1. Abrir “Carga de archivos y filtros” en el área principal y cargar cada XLSX en el cargador de su tipo. Se admiten las fuentes disponibles de los siete tipos; las vistas ausentes lo indican. Los cuatro cargadores agregados están en “Reportes gerenciales y proyección”, dentro del mismo bloque.
2. La moneda de todos los reportes está fijada en ARS por indicación del usuario. No requiere configuración.
3. En Cartera declarar el corte cuando “Cobro Hasta” está vacío. El selector empieza vacío y exige confirmación. La fecha de carga o la última fecha de préstamo no sustituyen al corte.
4. Consultar población, cobertura y parámetros en “Detalle de Universo”, la última opción de navegación. Revisar alertas en “Calidad y conciliación”. El mapeo de Anulado y Bonif y la tolerancia se modifican en “Configuración de validación”, solo dentro de Calidad, y se conservan al navegar.
5. Aplicar filtros por fuente y navegar por las ocho vistas. La barra izquierda contiene únicamente navegación. Cada gráfico por segmento permite abrir sus registros mediante un selector. La proyección permite filtrar año y mes; los gerenciales, plan o sucursal según su dimensión.
6. Descargar las tablas filtradas como CSV o el informe completo de calidad como ZIP, con incidencias, conciliaciones, clasificación y configuración aplicada. La casilla de identificadores personales habilita su visualización y exportación solo en ese detalle.

Los filtros dimensionales vacíos significan todos. “Restablecer filtros” restablece períodos y dimensiones, conservando archivos y declaraciones. Reemplazar un archivo por contenido diferente restablece sus filtros y declaración de corte para evitar heredar supuestos de otra fuente. La moneda permanece fijada en ARS. La fecha de corte es metadato de una fotografía: cambiarla no reconstruye el saldo a otra fecha.

## Lectura de Resumen y gráficos

Resumen muestra tarjetas con la fuente y referencia temporal breve. El detalle completo del universo de cada archivo se consulta exclusivamente en “Detalle de Universo”. Allí aparecen entidades, sucursales, parámetros originales por hoja, corte informado/declarado, filtros activos y registros incluidos. Los gerenciales conservan su propio alcance y no se suman a las fuentes de detalle.

En Resumen, Colocación y Cobranzas usan barras con frecuencia seleccionable. Debajo se muestran las líneas mensuales “Evolución del capital colocado” y “Evolución de la cobranza”, siguiendo las referencias del cliente. Cuando solo hay una de esas fuentes, el gráfico ocupa el ancho disponible. Colocación y Cobranzas conservan gráficos de líneas en sus vistas específicas. La frecuencia inicial es mensual.

Los gráficos temporales expresan miles de ARS en el eje vertical, sin decimales innecesarios. El cursor muestra el importe exacto en ARS con dos decimales. Los intervalos sin registros quedan sin dato y las líneas no conectan huecos. Los valores cero respaldados por registros se conservan como cero. Las cinco preguntas de gestión y el detalle de las vistas están en desplegables dentro de Resumen.

## Formatos y lectura

Se admiten `.xlsx` de los siete esquemas especificados, con títulos, parámetros y controles. Se exploran todas las hojas. En los reportes de detalle se detecta el encabezado por Cliente, Prestamo y Plan; en los agregados se verifica la secuencia de encabezados correspondiente, sin fijar un número de fila. Las hojas ajenas se informan y los esquemas incompletos producen un mensaje. No se admiten XLS, XLSM, archivos cifrados ni variantes arbitrarias de encabezados sin adaptar los esquemas.

## Nuevos reportes agregados

- **Proyección de cobranzas pendientes:** una fila por mes y año, con capital, interés y seguro. Se conserva el contexto anual de cada bloque y se concilian sus subtotales anuales y Total contra los meses, sin sumar los controles. Los meses pueden ser anteriores o posteriores a la carga; no se clasifican como mora ni cobranza realizada. Los parámetros de fechas se refieren a originación, no a cobertura de cobros.
- **Gerencial de préstamos por plan:** una fila por plan, con cantidad de préstamos, capital, monto contractual y Saldo Venc reportado. Se muestra también en Colocación como fuente independiente, sin agregarla al detalle de préstamos. Los campos titulados Interes % y Monto S/IVA % contienen magnitudes semejantes a importes en estos archivos: se conservan con su ambigüedad, sin calcular tasas.
- **Gerenciales de morosos por plan/sucursal:** se conserva cada segmento y sus bloques Cobrado/Moroso. Los campos izquierdos Capital/Interes coinciden con importes originados del gerencial por plan, por lo que no se usan como capital/interés efectivamente cobrado. Las tarjetas del bloque Moroso suman los segmentos, señalando las diferencias con el Total original. Los porcentajes se muestran individualmente en escala 0–100 y sus Totales se clasifican como no agregables, sin sumas ni promedios de tasas.

Los reportes agregados no incluyen claves de préstamo/cuota ni un corte válido. “Saldo Venc” es la definición reportada por el sistema, no capital vencido ni PAR. No se equipara al bloque Moroso. Las dos vistas de morosos pueden representar poblaciones solapadas: no se suman entre sí. Las coincidencias de importes y filtros entre gerenciales no prueban equivalencia con otras fuentes.

“Indicadores pendientes de datos” se calcula según las fuentes cargadas con registros válidos. Se separan los indicadores habilitados con alcance limitado (proyección mensual, saldo vencido reportado por plan y distribución del bloque Moroso) de los aún pendientes (mora por días/PAR, efectividad, puntualidad, recuperación de vencidos, roll rates, cohortes y rentabilidad). La sección explica los datos faltantes de cada indicador y no transforma una proyección mensual en historia de pagos.

En Cartera se recuperan los grupos Otorgado/Cobrado/Saldo de la fila superior al encabezado y se anteponen a sus componentes. Los identificadores se mantienen como texto. Los ceros iniciales se conservan cuando existen como texto o con formato Excel compuesto por ceros. No es posible recuperar ceros ya perdidos en la exportación de origen.

Se conservan archivo, hoja, fila, valores originales de fechas/números y contexto de agrupación. El contexto se etiqueta entidad/comercio y sucursal solo cuando existen controles explícitos de ambos niveles. El formato observado es jerárquico de dos niveles. En reportes con jerarquías distintas debe adaptarse el lector antes de atribuir semántica. Las filas sin clave con otros datos se clasifican rechazadas; las agrupaciones, vacías, subtotales y totales se mantienen aparte y no integran métricas.

Los parámetros se extraen de filas con etiqueta terminada en dos puntos. Los números nativos se respetan; los textos argentinos usan coma decimal y punto de miles. Las fechas usan día/mes/año o valores Excel. No se evalúan fórmulas del documento: un importe basado en fórmula se observa como inválido en vez de ejecutar instrucciones o usar un valor supuesto.

## Reglas de negocio y limitaciones

- Clave de préstamo: grupo de entidad + código de préstamo dentro de cada fuente. No se unen códigos entre fuentes, no se usan nombres ni últimos dígitos. Ninguna coincidencia aparente habilita comparabilidad. Se mantienen tendencias separadas.
- Préstamos y Cartera con clave duplicada se excluyen de métricas hasta revisión, sin borrar registros. Los cobros iguales se señalan y se conservan: podrían ser pagos parciales reales.
- Fechas de movimiento inválidas, préstamo/entidad ausentes y estados desconocidos bloquean inclusión. Vigente y Cancelado se aceptan; Cancelado no se interpreta como anulación.
- Importes negativos se observan y se conservan, sin corregirlos. Importes/cantidades ausentes invalidan el total de esa métrica, sin convertirlos en cero. La conciliación también evita sumas parciales de componentes faltantes.
- Anulado y Bonif: sí/s/1/true/x = verdadero; no/n/0/false = falso; vacío = falso por regla declarada visible y modificable. Los dos campos vacíos son los únicos valores observados en el ejemplo. Valores desconocidos de Anulado se excluyen. Bonif ambiguo se observa pero no modifica Cobrado. Un importe numérico de bonificación distinto de los tokens configurados requiere validar la semántica.
- Total cobrado usa Cobrado sin volver a restar bonificaciones. La diferencia frente a Capital + Interes + Seguro + Punitorios se informa como no explicada; no se fuerza la igualdad ni se atribuye definitivamente a impuestos.
- Una fuente vacía no se presenta como importe cero. Divisiones con denominador cero/ausente muestran “No disponible”. Los conteos y sus unidades se distinguen de importes.
- Cobertura temporal proviene de parámetros, nunca de la fecha máxima de un movimiento. Las comparaciones admitidas son meses completos o un mes incompleto desde el día 1 contra el mismo día del mes anterior, dentro de cobertura explícita y con los mismos filtros dimensionales. Otros rangos o múltiples hojas muestran “Comparación no disponible”. No se compara un mes de 31 días con un período anterior más corto como si fueran equivalentes.
- Cartera muestra solo la población de originación del reporte al corte informado/declarado. Recuperación de capital es acumulada de esa población. Cuotas impagas no significa cuotas vencidas. Fecha Ult. Vto. no sustituye el cronograma. Tasa no se etiqueta TNA/TEA/CFT ni se promedia.
- Concentración y clientes se consolidan por entidad + código de cliente; no se presume identidad de una persona entre entidades. Concentración no disponible si faltan identificadores/capital o existen saldos negativos.
- La función opcional `authorized_join` exige una tabla explícita de equivalencias uno a uno, rechaza claves duplicadas, agrega cobros antes de unir y devuelve los cobros no mapeados. No se habilita en la interfaz sin una integración validada; la aplicación entregada no realiza cruces.

## Conciliación y trazabilidad

Tolerancia monetaria absoluta configurable, inicialmente 0,02 unidades por componente y control. Cada subtotal se compara contra los detalles originales de su hoja y grupo. El total general se compara solo contra detalles de la hoja completa. No se suman subtotales y no se usan controles de otra población. Se distingue la población original de conciliación de los registros válidos filtrados de métricas.

En Cartera se comprueba también Otorgado − Cobrado − Saldo por préstamo en capital, interés, IVA de interés y monto. Las discrepancias quedan visibles sin modificar el archivo. El informe de calidad puede descargarse en tablas separadas de incidencias, controles y filas clasificadas.

## Privacidad y exportación

El procesamiento se realiza localmente en memoria. Los cachés de lectura no persisten en disco, usan el contenido completo, nombre y tipo como clave, tienen máximo de seis entradas de detalle y ocho gerenciales y vencen en una hora. Validaciones y métricas se recalculan al cambiar configuración, por lo que no reutilizan resultados de otra regla. El proceso local comparte el caché entre sesiones; para uso multiusuario se requiere revisar aislamiento y autenticación antes de desplegar.

El procesamiento de Excel y los cálculos se realizan localmente. Al usar el chat se envían a OpenAI las preguntas minimizadas y los resultados necesarios, según la sección Chat analítico; las filas de detalle no se envían. Se desactiva telemetría de Streamlit y se escucha inicialmente en 127.0.0.1. Los identificadores personales requieren permiso del servidor y habilitación explícita en el detalle. Las descargas usan punto y coma, coma decimal y UTF-8 con BOM. Se neutralizan textos iniciados por caracteres de fórmula, incluso después de espacios. Una hoja CSV no puede imponer el tipo de identificador al abrirse en Excel: importarla como texto para conservar ceros iniciales.

## Verificación

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Las pruebas de datos reales buscan los tres nombres originales en Descargas o en `REPORTS_DIR`. Si no están presentes, se marcan omitidas; no se sustituyen por datos ficticios. Los casos sintéticos en pruebas están separados y prueban límites, nunca se muestran como información real en la aplicación. Las pruebas de pantallas usan AppTest con cargas reales inyectadas porque no reproduce el diálogo nativo del cargador. No equivalen a una comprobación visual en navegador ni a una prueba de usabilidad con usuarios.

Consultar `HALLAZGOS.md` y `VERIFICACION.md` para resultados ejecutados y pendientes.

## Módulos

`app.py`: navegación y coordinación. `core/reader.py`: lectura y clasificación del detalle. `core/normalization.py`: conversiones y CSV seguro. `core/validation.py`: calidad, cobertura y conciliaciones del detalle. `core/metrics.py`: métricas, diccionario y unión explícita opcional. `core/presentation.py`: filtros, tablas y gráficos. `core/management.py`: lectura, validación, conciliación, métricas y disponibilidad de los agregados. `core/management_ui.py`: carga y presentación gerencial. `tests/`: pruebas de reglas y pantallas.
