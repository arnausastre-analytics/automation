# Consolidación Financiera Multi-Fuente

Este proyecto consolida datos financieros desde múltiples fuentes (Stripe, APIs externas, ficheros CSV) en una moneda base, calcula KPIs clave y genera un resumen automático para dirección.

## ¿Qué hace?

- Conecta con **Stripe API** para extraer ventas y reembolsos.
- Integra datos de **fuentes JSON genéricas** protegidas con token.
- Lee y unifica CSV locales con transacciones históricas.
- Convierte todas las operaciones a una **moneda base** usando tipos de cambio actualizados.
- Calcula KPIs diarios y por fuente (ventas brutas, devoluciones, fees, ingresos netos).
- Genera un resumen semanal en formato Markdown.
- Automatiza todo con GitHub Actions.

## Ejemplo de salida

Puedes encontrar los últimos archivos generados en la carpeta `outputs/` o como *artifact* en GitHub Actions:
- `transactions_consolidated.csv`
- `kpi_daily.csv`
- `kpi_by_source.csv`
- `summary_YYYYMMDD.md`

## Stack usado

- Python, pandas, requests, dateutil
- GitHub Actions

## Frecuencia

Se ejecuta automáticamente todos los días a las 06:10 UTC.
