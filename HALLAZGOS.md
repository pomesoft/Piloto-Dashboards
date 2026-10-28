# Hallazgos de los archivos proporcionados

## Ampliación del 20/10/2026: cuatro reportes gerenciales

Los cuatro nuevos archivos seleccionan originaciones del 01/01/2026 al 20/10/2026 y filtros generales de comercio, sucursal y plan. No aportan claves de préstamo/cuota ni corte válido. No se incorporan al detalle mediante uniones ni se suman a los importes anteriores. ARS permanece fijo.

| Reporte nuevo | Granularidad y filas | Resultados propios | Calidad |
|---|---|---|---|
| Proyección de pendientes | 27 meses, abril 2026–junio 2028 | Capital 1.113.831,57; interés 841.154,45; seguro 0,00; suma de componentes 1.954.986,02 ARS | 12 controles monetarios anuales/generales sin diferencias mayores a 0,02 |
| Préstamos por plan | 6 planes | 14 préstamos; capital 1.259.999,96; monto contractual 2.280.903,50; Saldo Venc 788.631,93 ARS | 8 controles sin diferencias mayores a 0,02 |
| Morosos por plan | 6 planes | Bloque Moroso: capital 1.103.831,57; interés 837.600,68; cuota 1.941.448,71 ARS | Capital Total original 156.168,39: diferencia detalle − Total = 947.663,18 ARS |
| Morosos por sucursal | 2 sucursales | Bloque Moroso: capital 1.103.831,57; interés 837.600,68; cuota 1.941.448,71 ARS | Misma diferencia de 947.663,18 ARS en capital |

Los controles de ambos reportes de morosos tienen 10 comparaciones monetarias cada uno: 9 coinciden y 1 difiere. Los dos porcentajes de la fila Total se conservan pero no se agregan ni se usan como indicadores. En el reporte por plan el % Total es 483,0800; en el de sucursal es 173,9373. Esas sumas no son tasas globales válidas.

El encabezado de proyección se detectó en fila 9 y sus reinicios anuales en filas 21 y 36. Préstamos por plan usa fila 9; los dos de morosos, fila 13, con rótulos superiores Cobrado y Moroso.

### Interpretación y compatibilidad

- La proyección suma pendientes, no obligaciones exigibles originales ni cobros realizados. No permite separar mora y futuro por préstamo. Carece de día de vencimiento y fecha de corte.
- “Saldo Venc” ya permite consultar saldo vencido **reportado por plan**, con corte y definición pendientes. No identifica cuánto es capital y no habilita capital en riesgo ni PAR.
- El bloque Moroso no equivale automáticamente a Saldo Venc: en el plan “108 - TASA UPCN”, Saldo Venc es 0,00 y Cuota Moroso es 116.241,76 ARS. Se mantienen como medidas distintas, sin atribuir una causa.
- Capital/Interes del bloque izquierdo rotulado Cobrado coinciden con los importes de originación del gerencial de préstamos por plan. No se los interpreta como recuperación efectiva. Sus rótulos originales se conservan y se advierte la ambigüedad.
- “Interes %” y “Monto S/IVA %” en el gerencial de planes contienen valores semejantes a importes, no tasas interpretables. No se convierten en porcentajes ni promedios financieros.
- Los gerenciales por plan y sucursal concuerdan en varias sumas, pero son dos agrupaciones potencialmente solapadas. No se suman entre sí. La proyección y el bloque Moroso difieren en 10.000,00 ARS de capital; no se fuerza una conciliación entre poblaciones sin detalle equivalente.
- El gerencial tiene 14 préstamos frente a los 15 del archivo de detalle anterior y períodos Hasta distintos. No se deduce cuál préstamo falta ni se reemplaza un total por otro.

### Indicadores pendientes actualizados

Se habilitaron, con alcance limitado: pendientes mensuales por componente, préstamos y Saldo Venc reportados por plan, y distribución del bloque Moroso por plan/sucursal. El estado depende de que el usuario cargue la fuente correspondiente con registros válidos.

Siguen pendientes mora por días/tramos, PAR30/60/90, capital en riesgo, efectividad sobre exigible, puntualidad, primera cuota impaga, recuperación de vencidos, roll rates, curación, mora por cohortes, rentabilidad y pérdidas. Faltan cuotas/préstamos identificados, vencimientos exactos, exigible original, imputaciones, corte, historia y costos según cada indicador.

## Análisis original del 19/10/2026

Análisis ejecutado el 19/10/2026. Ningún archivo identifica moneda. Por indicación posterior del usuario, todos los importes se interpretan en ARS y la aplicación fija esa moneda sin configuración.

| Fuente | Detalles | Cobertura según parámetros | Universo |
|---|---:|---|---|
| Préstamos Detalle | 15 | Préstamos 01/01/2026–19/10/2026 | CREDITO INTELIGENTE y ALTA DEMO; estados Vigentes y Cancelados |
| Cobranzas Detalle | 10 | Cobros 27/04/2026–19/10/2026 | CREDITO INTELIGENTE; estado Vigentes; tipo Pagos |
| Saldo de la Cartera | 123 | Préstamos originados 01/10/2026–17/10/2026; Cobro Hasta vacío | MACRO SOLUTIONS; tres sucursales |

Las poblaciones no son comparables. Los préstamos de cartera no representan necesariamente toda la cartera de la empresa. No se cruzaron códigos ni se combinaron tendencias.

## Resultados independientes

- Préstamos: capital 1.269.999,96; monto contractual 2.294.457,27; 15 préstamos; 13 clientes identificados por entidad y código; plazo medio 7,4 cuotas. No se afirma que sean meses.
- Cobranzas: total 256.991,22; capital 116.813,22; intereses 111.507,44; punitorios 5.254,00; seguros 0,00. Son 10 imputaciones a cuotas de 8 préstamos, no 10 recibos.
- Diferencia no explicada en cobranzas: 23.416,56. Se detecta en las 10 filas. Podría contener componentes fiscales no desglosados; requiere validación del sistema.
- Cartera: capital pendiente 53.482.000,00; saldo contractual pendiente 157.192.953,00; intereses pendientes 85.711.531,30; IVA de intereses 17.999.421,70. Son 123 préstamos con saldo y 122 clientes por entidad/código. Estos valores son la fotografía reportada, sin corte validado.
- Capital recuperado acumulado de esa población: 0,00. No mide la efectividad de cobranza de un período.
- Los diez principales clientes por entidad/código concentran 36,74 % del capital pendiente. Las cuotas impagas reportadas suman 1.159, sin interpretación de vencimiento.

## Controles ejecutados

Encabezados detectados por contenido en filas 11, 13 y 11, respectivamente. Se recuperaron los tres grupos de Saldo de la fila 10. Los subtotales explícitos de comercio y sucursal respaldan la interpretación de los niveles de agrupación en estos archivos.

Se verificaron 35 comparaciones de control en Préstamos, 18 en Cobranzas y 65 en Cartera, incluyendo conteos de detalle de los controles. No hubo diferencias fuera de tolerancia absoluta 0,02. Los 123 préstamos de Cartera cumplen Otorgado − Cobrado ≈ Saldo en los cuatro componentes.

No se detectaron duplicados de préstamo en Préstamos/Cartera ni duplicados exactos potenciales de imputaciones en el ejemplo. La lógica no elimina cobros iguales. Los controles originales no se sumaron entre sí.

## Decisiones pendientes

1. Moneda resuelta: ARS para las tres fuentes, según indicación del usuario.
2. Informar el corte real de Cartera: no se usa el 17/10 como sustituto de Cobro Hasta.
3. Validar si Anulado y Bonif vacíos significan falso. La aplicación muestra esa regla inicial y permite cambiarla a ambigua. No se restan bonificaciones de Cobrado.
4. Validar composición de los 23.416,56 no explicados.
5. Proveer equivalencias explícitas antes de cruzar códigos de préstamo y documentar semántica de estados y tasas.
6. Incorporar cronogramas, obligaciones exigibles, pagos imputados y cortes históricos para mora/PAR y cohortes. Incorporar costos y flujos para rentabilidad. No se generan calendarios supuestos ni modelos predictivos.
