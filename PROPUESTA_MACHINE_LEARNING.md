# Propuesta de implementación de machine learning para préstamos y cobranzas

Fecha: 29 de octubre de 2026  
Estado: propuesta para evaluación e implementación por etapas.

## 1. Objetivo y alcance

Pasar del dashboard descriptivo a herramientas que permitan anticipar problemas de pago, estimar cobranzas y organizar la gestión de la cartera. La prioridad propuesta es un modelo de alerta temprana para préstamos vigentes; en paralelo, preparar segmentación exploratoria y pronósticos de cobranza.

Este informe se basa en `README.md`, los esquemas de `core/reader.py` y las reglas de `core/metrics.py` del proyecto. No se analizaron archivos XLSX reales ni una base histórica en esta revisión. Por eso, la disponibilidad de campos es documental: no implica que estén completos, sean correctos o que exista volumen suficiente para entrenar modelos. No se presentan resultados predictivos ni mejoras económicas comprobadas.

El chat analítico existente ayuda a consultar información, pero no constituye un modelo predictivo de riesgo crediticio.

## 2. Qué datos contempla el dashboard

| Fuente | Granularidad documentada | Datos principales | Utilidad y limitación para ML |
|---|---|---|---|
| Préstamos detalle | Préstamo por entidad | Cliente, documento, préstamo, fecha, cuotas, plan, capital, interés, seguro, IVA, monto, estado, usuario | Condiciones de originación. No contiene por sí solo ingresos, decisión crediticia ni resultados históricos de mora |
| Cobranzas detalle | Imputación de cobro a cuota | Cliente, préstamo, cuota, fecha de cobro, capital, interés, seguro, punitorios, cobrado, tipo de pago, bonificación, anulado | Comportamiento de pagos si se verifica cobertura y vínculo con cuotas. Falta un identificador inequívoco de transacción |
| Cartera | Préstamo en una fotografía | Cliente, CUIL, solicitud, fecha, último vencimiento, plan, tasa, cuotas, cuotas impagas, otorgado/cobrado/saldo por componente | Exposición al corte. Una fotografía no reconstruye la evolución de la deuda |
| Proyección de pendientes | Mes y año | Capital, interés, seguro | Obligaciones proyectadas agregadas; no son cobros efectivos ni probabilidades de recuperación |
| Gerencial por plan | Plan | Cantidades, capital, monto contractual, saldo vencido reportado | Control agregado. No permite etiquetar préstamos individuales |
| Morosos por plan | Segmento | Bloques Cobrado/Moroso y porcentajes | Descripción agregada con semántica que requiere validación |
| Morosos por sucursal | Segmento | Bloques Cobrado/Moroso y porcentajes | Puede solaparse con el anterior; no deben sumarse ambos universos |

### Restricciones que se deben conservar

- La clave de préstamo depende de la entidad y del código; no se deben unir fuentes por coincidencia aparente de códigos, nombres o documentos.
- Se necesita una equivalencia validada entre fuentes. La aplicación actual no realiza esos cruces automáticamente.
- Cliente por entidad no significa persona única entre entidades.
- Cuotas impagas no equivale a cuotas vencidas. Último vencimiento no sustituye el cronograma completo.
- Cancelado no significa anulado ni demuestra incumplimiento.
- Saldo pendiente no equivale a saldo vencido; los intereses cobrados no son ganancia neta.
- La moneda declarada es ARS. Las comparaciones monetarias entre períodos deben documentar el tratamiento de cambios de precios.
- Hay ambigüedades documentadas en tasas y componentes gerenciales que deben resolverse antes de usarlos como variables.

## 3. Casos de uso y modelos propuestos

| Prioridad | Caso y decisión que ayuda a tomar | Modelo inicial | Objetivo y unidad | Condición para implementarlo |
|---|---|---|---|---|
| 1 | Alerta temprana: qué préstamos revisar primero | Regresión logística | Probabilidad de alcanzar 30 días de atraso dentro de los próximos 90 días; préstamo al corte | Cronograma, pagos imputados e historia fechada para construir etiquetas |
| 2 | Presupuesto de caja: cuánto se cobrará | Regresión lineal regularizada y referencia estacional | Cobranza efectiva en ARS del próximo mes; cartera o segmento por mes | Serie histórica completa, calendario y exposición comparable |
| 2 | Segmentación: qué perfiles de cartera requieren tratamientos diferentes | Clustering, inicialmente K-means si las variables lo permiten | Grupos de clientes de una entidad o de préstamos al corte; sin etiqueta objetivo | Definir una única unidad, normalizar variables y verificar estabilidad |
| 3 | Priorización de vencidos: quién podría regularizar | Regresión logística | Probabilidad de regularización en 30 días; préstamo vencido al corte | Mora validada, pagos posteriores y registro de gestiones |
| 3 | Estimar monto recuperable por caso | Modelo de dos etapas: probabilidad de pago y regresión del importe positivo | Importe cobrado en próximos 30 días; préstamo al corte | Pagos atribuibles, exposición y suficientes casos con y sin recuperación |
| 4 | Originación: apoyar la evaluación de nuevas solicitudes | Regresión logística; comparar luego con árboles o boosting | Incumplimiento en horizonte acordado desde la originación; solicitud | Solicitudes, decisiones, datos disponibles al solicitar y resultados maduros |
| 4 | Tiempo hasta regularización | Análisis de supervivencia | Días hasta regularizar; episodio de mora | Fechas de inicio/fin, seguimiento y tratamiento de casos aún abiertos |
| Complementaria | Alertas de movimientos atípicos | Reglas y posteriormente detección de anomalías | Movimiento o préstamo inusual | Identificadores de transacción y revisión humana para confirmar hallazgos |

La regresión logística estima probabilidades para eventos, como entrar en mora. La regresión lineal estima cantidades, como el monto mensual cobrado. El clustering descubre grupos: no predice automáticamente incumplimiento ni demuestra que un segmento sea de alto riesgo. Una anomalía tampoco prueba fraude.

No se propone entrenar todos los modelos simultáneamente. Primero se debe verificar la viabilidad del caso prioritario y comparar su utilidad con reglas simples.

## 4. Inventario de datos requeridos

Leyenda: **documentado** = el esquema actual contempla el dato; **parcial** = existe una aproximación insuficiente; **no identificado** = no se encontró en los esquemas revisados. Esto no sustituye una auditoría de archivos reales.

| Conjunto y campos necesarios | Estado actual | Granularidad y frecuencia propuesta | Uso |
|---|---|---|---|
| Entidad, sucursal, ID estable de cliente y préstamo | Documentado, sujeto a validación de contexto | Catálogo e historial de cambios | Identidad, segmentación y conciliación |
| Tabla de equivalencias entre fuentes y sistemas, vigencia de cada vínculo | No identificado como fuente cargada | Un vínculo validado por clave y período | Integrar préstamos, cartera y pagos sin cruces erróneos |
| ID de solicitud, fecha/hora, canal, producto, plan y versión | Parcial: solicitud en cartera y plan en detalle | Solicitud y evento de cambio | Originación y condiciones comerciales |
| Fecha de otorgamiento, capital desembolsado, monto contractual, cuotas y periodicidad | Parcial: falta validar desembolso y periodicidad | Préstamo al otorgamiento | Exposición y esfuerzo de pago |
| Tasa, tipo de tasa, moneda, impuestos, comisiones, costo total y condiciones | Parcial: tasa sin semántica completa y componentes monetarios | Contrato y versión | Comparabilidad y economía del préstamo |
| Cronograma completo: ID cuota, vencimiento, capital, interés, impuestos, seguro, total exigible | No identificado; solo cuota de cobro y último vencimiento | Cuota y cada versión del cronograma | Días de atraso, etiquetas y flujo esperado |
| ID único de pago/recibo, fecha efectiva, fecha de registración, importe y moneda | Parcial: fecha e importes; sin ID de recibo | Transacción, extracción diaria | Evitar duplicar pagos y reconstruir información disponible |
| Imputación del pago a préstamo/cuota y componente; pagos parciales y no aplicados | Parcial | Relación transacción–cuota | Saldo exigible histórico y regularización |
| Anulaciones, reversos, bonificaciones y su fecha efectiva/registro | Parcial: indicadores sin historial completo | Evento | Reconstrucción correcta de saldos |
| Saldo por préstamo/cuota, fecha de corte, días de atraso y saldo vencido | Parcial: fotografía de cartera | Diario o mensual según uso; con corte explícito | Riesgo, transiciones y exposición |
| Refinanciación, reestructuración, prórroga, castigo, quita y vínculo con contrato anterior | No identificado | Evento con fecha y motivo | No confundir regularización con renovación o pérdida |
| Ingreso verificable, fecha de verificación, estabilidad laboral, obligaciones y capacidad de pago | No identificado | Solicitud y actualizaciones autorizadas | Evaluación de originación; no son imprescindibles para todo modelo de comportamiento |
| Historial de solicitudes aprobadas/rechazadas, oferta, decisión y motivo | No identificado | Solicitud | Medir sesgo de selección del scoring de originación |
| Gestiones: fecha, canal, responsable, contacto logrado, promesa, monto, vencimiento y cumplimiento | No identificado | Interacción | Priorización de cobranzas y evaluación de tratamientos |
| Costos de contacto, gestión, fondeo, operación y pérdidas recuperadas | No identificado | Gestión/préstamo/período | Medir beneficio neto y definir umbrales |
| Calendario de días hábiles, feriados, cierres y campañas | No identificado | Día | Pronóstico de caja y efectos operativos |
| Índices de precios u otras variables económicas justificadas, fecha publicada y versión | No identificado | Mes y fecha de disponibilidad | Comparar importes y evaluar cambios de contexto |
| Fuente, archivo, hoja, fila, fecha de extracción, cobertura, reglas de inclusión y versión | Parcial: trazabilidad de archivos existente | Cada carga y registro | Reproducibilidad y auditoría |

### Datos opcionales y límites

Datos externos crediticios pueden mejorar ciertos modelos, pero solo deben incorporarse si su uso está autorizado, su procedencia es verificable y agregan valor medible. No son un requisito para empezar con modelos de comportamiento interno. Nombres, DNI y CUIL deben servir para una vinculación controlada, no como variables numéricas de predicción. No se deben recopilar datos personales sin una finalidad definida.

## 5. Diseño mínimo de la base para ML

| Tabla propuesta | Clave y contenido esencial |
|---|---|
| clientes | Entidad + ID cliente, atributos permitidos e historia de vigencias |
| prestamos | Entidad + ID préstamo, cliente, solicitud y condiciones originales |
| cuotas | Entidad + préstamo + cuota + versión, vencimiento e importe exigible |
| pagos | ID transacción, fechas efectiva/de registro, importe, estado y reverso |
| imputaciones | ID transacción + ID cuota + componente, importe aplicado |
| eventos_crediticios | Préstamo, evento, fecha, motivo y contrato relacionado |
| gestiones | ID gestión, préstamo, acción, resultado, promesa y costo |
| snapshots | Préstamo + fecha de corte, exposición y situación reconstruida |
| dataset_modelo | Préstamo o cliente + fecha de observación, variables y etiqueta madura |
| predicciones | Clave + fecha de cálculo, modelo, probabilidad/importe, horizonte y vigencia |

Cada tabla debe conservar origen y fechas de disponibilidad. El historial debe permitir responder tanto “qué ocurrió” como “qué se conocía cuando se tomó la decisión”. Los archivos actuales se conservan como fuente; las tablas integradas son una nueva capa validada.

## 6. Construcción de objetivos y variables

### Modelo prioritario: alerta temprana de mora

**Definición propuesta para acordar con negocio:** al cierre de cada mes, seleccionar préstamos activos que todavía no tienen 30 días de atraso y predecir si alcanzarán al menos 30 días de atraso en algún momento de los siguientes 90 días. Separar préstamos al día de los que ya tienen atrasos de 1–29 días para medir desempeño por situación inicial.

El atraso se calcula contra cuotas exigibles e importes pendientes, con una regla acordada para pagos parciales, tolerancias, feriados, refinanciaciones y anulaciones. No se deduce de la cantidad reportada de cuotas impagas.

- Etiqueta 1: se observa el evento definido dentro del horizonte.
- Etiqueta 0: se observa el horizonte completo sin el evento.
- Sin etiqueta: falta seguimiento, cobertura o información para determinar el resultado. No convertir estos casos en cero.
- Cancelaciones anticipadas, castigos y refinanciaciones requieren reglas explícitas para evitar etiquetas engañosas.

**Variables candidatas, calculadas solo con información disponible al corte:**

| Familia | Ejemplos | Requisito |
|---|---|---|
| Contrato | Capital original, plazo, periodicidad, plan, antigüedad | Condiciones históricas válidas |
| Exposición | Saldo de capital, proporción de capital pendiente, deuda exigible | Corte y conciliación |
| Comportamiento | Máximo atraso previo, proporción de cuotas pagadas a tiempo, pagos parciales | Cronograma e imputaciones |
| Actividad reciente | Días desde último pago; monto y frecuencia en 30/60/90 días | Cobertura completa de esas ventanas |
| Relación | Cantidad de préstamos previos, regularizaciones previas | Identidad estable e historial |
| Gestión | Contactos y promesas anteriores al corte | Registro de gestiones y disponibilidad temporal |

No usar saldo de hoy para predecir un evento de hace seis meses. No usar pagos posteriores al corte, el resultado final del préstamo o información corregida que todavía no estaba disponible.

### Regresión de cobranza

Construir una fila por mes y segmento con el monto efectivamente cobrado en el mes siguiente. Variables: cobranza rezagada, vencimientos futuros conocidos al corte, exposición, cantidad de préstamos, composición por plan, días hábiles y calendario. La proyección contractual es un predictor posible, no la etiqueta de cobranza real.

Comparar regresión lineal regularizada con una referencia simple: último mes o mismo mes del año anterior, si existe historia suficiente. Revisar valores negativos pronosticados y considerar transformaciones o modelos adecuados a importes no negativos. Reportar ARS nominales y, si se utiliza, la transformación a moneda comparable con su fuente y fecha de disponibilidad.

### Clustering

Elegir cliente por entidad o préstamo, sin mezclarlos. Empezar con exposición, antigüedad, cantidad de préstamos, frecuencia y tamaño de pagos. Incorporar puntualidad solo cuando pueda calcularse. Escalar magnitudes y controlar extremos; con variables mixtas puede ser necesario otro método o distancia.

Describir grupos con estadísticas y nombres comprensibles después de revisarlos. Evaluar separación, estabilidad temporal y utilidad operativa. Un buen valor de silhouette por sí solo no demuestra valor comercial.

## 7. Historia, volumen y calidad necesarios

No hay un número universal de registros que garantice un modelo útil. Importan la cantidad de clientes independientes, eventos de mora, cobertura, variabilidad y cambios de política. Repetir el mismo préstamo en varios cortes no equivale a sumar casos independientes.

Como objetivo inicial de recolección, buscar 24–36 meses completos; es una referencia de planificación, no un mínimo estadístico ni una garantía. Con menos historia puede evaluarse un piloto limitado, dejando explícito qué estacionalidad o escenario no está representado. Para una etiqueta de 90 días, los cortes recientes no tendrán resultado completo hasta madurar ese horizonte.

El diagnóstico debe medir:

- Filas, préstamos y clientes únicos por mes, entidad, plan y sucursal.
- Cantidad y proporción de eventos por período y segmento.
- Datos faltantes, duplicados de claves, pagos huérfanos y cuotas sin cronograma.
- Meses ausentes, cobertura de originación/cobro y cambios de alcance de reportes.
- Conciliación entre pagos, imputaciones y saldos, con tolerancias documentadas.
- Cambios de políticas, refinanciaciones y modificaciones del sistema de origen.

Antes de entrenar, resolver la identidad y las fechas necesarias para construir etiquetas. Los umbrales de calidad de campos secundarios se fijarán tras la auditoría; no corresponde inventar porcentajes aceptables sin conocer el impacto.

## 8. Validación y criterios de éxito

Separar entrenamiento, validación y prueba final por tiempo. Ajustar transformaciones únicamente en entrenamiento y reservar el período más reciente con resultados maduros para la prueba final. Usar ventanas móviles para comprobar estabilidad. En paneles de préstamos, adaptar la separación a las fechas y entidades: no aplicar mecánicamente una división de filas.

Si una etiqueta usa los próximos 90 días, impedir que las etiquetas del entrenamiento incorporen resultados del período de evaluación. Evaluar por separado clientes nuevos y recurrentes; si el objetivo es generalizar a clientes nunca vistos, incorporar separación por cliente.

| Modelo | Evaluación técnica | Evaluación de negocio |
|---|---|---|
| Clasificación de mora | PR-AUC, ROC-AUC como complemento, calibración, precisión y recall al umbral | Casos riesgosos detectados con capacidad real de gestión; costo de falsas alertas |
| Regresión de importes | MAE en ARS, RMSE, sesgo y error por segmento; WAPE si el total real es positivo | Error de presupuesto y utilidad para caja |
| Clustering | Silhouette cuando aplica, tamaños, estabilidad y sensibilidad a variables | Segmentos comprensibles que permitan acciones diferenciadas |
| Supervivencia | Discriminación y calibración por horizonte con censura | Mejor programación de esfuerzos y recuperaciones |

La exactitud global no basta cuando la mora es poco frecuente. Comparar siempre con la política o regla actual, sobre la misma población y período. Definir el umbral según capacidad diaria y costos; 0,5 no es un valor obligatorio.

El beneficio de una campaña de cobranza no se demuestra solo prediciendo quién pagará. Hace falta un piloto controlado para estimar recuperación incremental frente a la gestión habitual, descontando costos y evitando contar pagos que habrían ocurrido de todos modos. Registrar intervalos de incertidumbre y desempeño por segmentos.

## 9. Integración propuesta con el dashboard

1. Mantener la carga, conciliación y métricas existentes como control de entrada.
2. Incorporar una capa histórica persistente con claves, cortes e imputaciones validadas.
3. Crear un proceso reproducible de preparación, entrenamiento y registro de modelos.
4. Generar predicciones por lotes fuera de la navegación del dashboard.
5. Mostrar una nueva vista de ML con fecha del dato, fecha de cálculo, horizonte, cobertura, versión y calidad.
6. Presentar probabilidades de mora, importes previstos o segmentos junto con factores asociados y acciones revisables.
7. Registrar la revisión humana, la gestión realizada y los resultados para evaluar el piloto.

El primer despliegue debe operar en modo de observación: comparar predicciones con resultados sin automatizar decisiones crediticias. Los factores explicativos son asociaciones del modelo; no prueban causas.

Mantener los permisos por entidad y sucursal, limitar la exportación de datos personales y conservar identificadores separados de las variables analíticas. Definir responsables, accesos, conservación y revisión de uso antes de incorporar información personal adicional. El alcance legal específico requiere evaluación propia; este documento no constituye un dictamen normativo.

## 10. Hoja de ruta orientativa

Los plazos siguientes son estimaciones de trabajo sujetas al acceso y la calidad de datos; no incluyen esperar la maduración de resultados nuevos.

| Etapa | Duración orientativa | Entregable | Condición de avance |
|---|---|---|---|
| 1. Acordar decisión y auditar fuentes | 1–2 semanas | Objetivo, inventario, cobertura y brechas verificadas | Responsable de negocio y definición de mora acordados |
| 2. Integrar y reconstruir historia | 2–4 semanas | Tablas conciliadas, cronogramas, pagos y cortes | Etiquetas reproducibles y vínculos validados |
| 3. Referencias y primer modelo | 2–3 semanas | Regla base, logística, evaluación temporal y ficha del modelo | Mejora útil en prueba futura reservada |
| 4. Integrar piloto | 1–2 semanas | Vista ML, predicciones fechadas y registro de revisión | Operación y permisos comprobados |
| 5. Observar y medir intervención | Según horizonte y cantidad de casos | Evaluación prospectiva y beneficio incremental | Resultados maduros y evidencia suficiente |

Roles necesarios: responsable de crédito/cobranzas para definiciones y decisiones; responsable del sistema de origen para extracciones; ingeniería de datos para historial y calidad; analista/científico de datos para modelos; responsable de aplicación para integración y operación. Una persona puede cubrir varios roles, pero cada decisión necesita un responsable.

No se estima presupuesto monetario sin conocer volumen, infraestructura, disponibilidad del equipo y alcance de integración.

## 11. Monitoreo y mantenimiento

Controlar en cada ejecución cobertura, claves, datos faltantes y antigüedad de fuentes. Revisar periódicamente cambios de distribución, tasas de alerta y resultados por plan/sucursal. Medir desempeño real solo cuando las etiquetas hayan madurado; para el objetivo de 90 días existe ese retraso de observación.

Conservar versiones de datos, reglas, variables, modelo y umbrales. Ante entradas incompatibles o deterioro relevante, suspender nuevas puntuaciones y volver a la regla operativa acordada. Reentrenar cuando exista evidencia de necesidad y validar antes de sustituir el modelo, sin asumir que una actualización automática lo mejora.

## 12. Pedido concreto de datos al negocio

Para iniciar el diagnóstico se necesita una extracción histórica autorizada de:

1. Préstamos originales y condiciones contractuales, incluyendo cerrados y cancelados.
2. Cronograma de todas las cuotas y sus modificaciones.
3. Pagos completos, anulaciones y reversos con ID de transacción e imputación.
4. Cartera histórica con fechas de corte y cobertura explícitas, si existe.
5. Maestros de entidad, sucursal, cliente, plan y equivalencias entre reportes.
6. Refinanciaciones, castigos, quitas, prórrogas y cancelaciones anticipadas.
7. Diccionario del sistema y significado de estados, tasa, cuotas impagas y saldo vencido.
8. Para una segunda etapa: gestiones de cobranza, costos y solicitudes con decisiones.

Por cada extracción, informar período cubierto, filtros, zona horaria, frecuencia, responsable, fecha de generación y cambios de formato. Si falta algún conjunto, documentarlo: no reemplazar su ausencia por valores cero o supuestos silenciosos.

## 13. Recomendación final de implementación

Empezar por un diagnóstico de viabilidad del modelo de mora de cartera vigente. El entregable inicial debe demostrar que es posible reconstruir vencimientos, pagos y resultados a lo largo del tiempo. Si esa condición se cumple, entrenar una regresión logística interpretable y compararla con reglas de negocio; después evaluar mayor complejidad.

Mientras se completa ese historial, se puede evaluar segmentación exploratoria con fotografías validadas y pronóstico agregado si hay suficientes períodos comparables. El scoring de nuevas solicitudes queda para una etapa posterior porque requiere datos y validaciones distintos del comportamiento de préstamos ya otorgados.

## Referencias metodológicas

- [Regresión logística — documentación oficial de scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html): modelo de referencia para clasificación probabilística.
- [División temporal — documentación oficial de scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html): fundamento de evaluación ordenada por tiempo; requiere adaptación al panel y horizonte de este negocio.
- [Clustering — documentación oficial de scikit-learn](https://scikit-learn.org/stable/modules/clustering): métodos y evaluación de agrupamientos, incluida silhouette.
