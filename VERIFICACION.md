# Verificación ejecutada

## Lectura y navegación verificadas el 26/10/2026

Se simplificó la barra lateral a navegación, se trasladaron carga/filtros al área principal y la configuración de validación a Calidad. Se agregó “Detalle de Universo” como última opción y se retiraron de las demás vistas los paneles de población y parámetros originales. Resumen contiene las cinco preguntas, el detalle de las ocho vistas, barras de colocación/cobranzas y dos líneas mensuales de evolución en miles de ARS. Las vistas específicas usan líneas. Con una sola fuente temporal los gráficos ocupan el ancho disponible.

La suite se amplió a 45 pruebas, con controles explícitos de tipos y títulos de los cuatro gráficos de Resumen, unidades, sumas mensuales, ausencia frente a cero, huecos sin conexión, aislamiento de Universo, sidebar sin controles y persistencia de las reglas al navegar. Se mantienen las pruebas sobre los siete archivos reales y sus cálculos.

Se abrió la aplicación en navegador local y se revisó visualmente Resumen con Préstamos Detalle: gráfico de barras y evolución mensual, escala de miles y ancho con carga parcial. Las capturas quedaron en `output/playwright/`. La carga de Cobranzas en el navegador no fue autorizada por la puerta de permisos, por lo que no se reintentó ni se usó otra vía de carga. Las pantallas y cálculos de Cobranzas sí se verificaron con AppTest, como parte de la suite.

## Ampliación verificada el 20/10/2026

Suite final tras integrar los cuatro gerenciales: **39 passed in 30.80s**, sin pruebas omitidas. `python -m pip check`: **No broken requirements found**. Incluye las 24 pruebas previas, 9 nuevas de lectura/cálculo y 6 de integración de pantallas. Las pruebas de interfaz usan los bytes reales de los cuatro archivos nuevos, cada uno por separado, los cuatro juntos y los siete reportes juntos.

Se verificaron detección de encabezados por contenido, contexto anual de los 27 meses, exclusión de subtotales y Totales, 12 controles de proyección y 8 de préstamos por plan sin diferencias. En cada gerencial de morosos se comprueba expresamente la diferencia de capital de 947.663,18 ARS y la clasificación no agregable de los dos porcentajes de Total. Estas discrepancias esperadas no se consideran una falla de software ni se corrigen silenciosamente.

También se probaron meses inválidos, encabezados desplazados, duplicados de mes, importes ausentes, esquema incorrecto y que cargar todos los gerenciales no habilita PAR ni efectividad. En pantallas se verificaron navegación, diccionario ampliado, conciliaciones visibles, filtros por año/mes, resultado vacío, restablecimiento y existencia de botones de descarga. Se mantiene la limitación de no haber comprobado apariencia visual ni descarga real en navegador.

## Verificación de la versión original

Fecha: 19/10/2026. Entorno: Windows, Python 3.13.5. Dependencias instaladas: Streamlit 1.66.0, pandas 3.0.6, openpyxl 3.1.5, Plotly 7.1.0 y pytest 9.1.1.

## Resultado final

`python -m pytest -q --tb=short`: **24 passed in 24.80s**. Ninguna prueba omitida en esta ejecución. `python -m pip check`: **No broken requirements found**. También se ejecutó compilación de sintaxis de app, módulos y pruebas sin errores antes de la última suite, que importó los archivos finales.

## Alcance probado

- Lectura de los tres XLSX reales: 15, 10 y 123 detalles. Encabezados por contenido y prefijos Otorgado/Cobrado/Saldo.
- Exclusión de agrupaciones y controles de los cálculos. Conciliación por nivel y población: 35 controles de Préstamos, 18 de Cobranzas y 65 de Cartera, todos dentro de tolerancia 0,02. La cantidad incluye componentes y conteos, no cantidad de filas de total.
- Igualdad por préstamo de los cuatro componentes de Cartera, dentro de tolerancia.
- Identificadores como texto y prueba separada de ceros iniciales por formato Excel.
- Cobros parciales/idénticos conservados; anulación explícita, mapeo desconocido y vacío tratado como ambiguo. Diferencia no explicada de los cobros reales: 23.416,56.
- Fechas inválidas, columnas faltantes, duplicados de préstamo, Cancelado aceptado, ausencia de importe y valores negativos observados.
- Denominadores cero/ausentes, datos vacíos y comparaciones de mes incompleto con cobertura suficiente o insuficiente.
- Unión opcional mediante equivalencias explícitas con agregación previa: no multiplica capital y devuelve claves de cobro sin correspondencia; rechaza equivalencias duplicadas.
- Seis vistas sin fuentes y seis vistas para cada una de las siete combinaciones no vacías posibles de fuentes reales cargadas.
- Interacción con filtro de plan, tabla restringida al segmento, identificadores ocultos por defecto y visibles tras casilla explícita, existencia de descargas, período sin resultados y restablecimiento de filtros.
- Serialización de tablas CSV con neutralización de texto de fórmula y preservación del valor numérico separado del texto.

Las pruebas de pantallas usan Streamlit AppTest. El cargador se sustituye únicamente durante las pruebas por objetos en memoria con los bytes reales de los archivos originales. La fecha 19/10/2026 se inyecta solo en ese entorno para ejercitar las pantallas de Cartera y no se considera corte real ni valor predeterminado de la aplicación.

## Límites de la verificación

No se ejecutó una comprobación visual en navegador, no se operó el diálogo nativo de selección de archivos y no se comprobó una descarga mediante navegador. Se verificó la serialización CSV y que las pantallas construyen sus botones de descarga. No hubo pruebas de usabilidad con usuarios ni de volumen masivo. No se publicaron datos ni se desplegó un servicio externo.

AppTest necesitó ejecutarse fuera del aislamiento de sockets porque Windows bloqueaba sus canales internos locales. Los primeros intentos aislados quedaron detenidos en la creación del canal de eventos y fueron interrumpidos; no se contaron como pruebas pasadas. La suite final se ejecutó completamente.

La moneda quedó fijada en ARS para las tres fuentes por indicación del usuario, sin campo configurable. El corte de Cartera, los blancos de Anulado/Bonif, la composición fiscal y la equivalencia de códigos siguen pendientes de validación de negocio. Las reglas declaradas se muestran en la aplicación y en el informe descargable. Las cifras reales se detallan en HALLAZGOS.md sin afirmar comparabilidad entre fuentes.
