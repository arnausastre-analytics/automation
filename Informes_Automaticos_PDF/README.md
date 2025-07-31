# Informe Automático de Acciones

Este proyecto simula un pipeline de reporting semanal para empresas financieras o consultoras. El informe analiza acciones populares (AAPL, MSFT, AMZN), genera KPIs, visualizaciones y entrega un PDF con todo el análisis.

## ¿Qué hace?

- Descarga datos de acciones usando `yfinance`.
- Calcula retornos, medias móviles y acumulados.
- Genera visualizaciones clave.
- Crea un PDF final listo para el cliente.
- Automatiza todo semanalmente con GitHub Actions.

## Ejemplo de salida

Puedes encontrar el último PDF generado en la carpeta `reports/` o como *artifact* en GitHub Actions.

## Stack usado

- Python, yfinance, pandas, matplotlib y weasyprint
- GitHub Actions

## Frecuencia

Se ejecuta automáticamente todos los lunes (cron semanal).
