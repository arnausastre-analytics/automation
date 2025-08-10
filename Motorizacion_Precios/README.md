# Monitorización Automática de Precios y Alertas de Competencia

Este proyecto implementa un pipeline de monitorización de precios para empresas que venden productos o servicios en mercados competitivos. El sistema captura precios desde webs o APIs, los compara con los propios, y envía alertas cuando detecta cambios relevantes.

## ¿Qué hace?

- Extrae precios y stock de competidores desde **APIs o scraping**.
- Compara con los precios internos y detecta variaciones significativas.
- Genera alertas automáticas vía email, Slack o Teams.
- Guarda histórico de precios para análisis de tendencias.
- Automatiza todo el proceso con GitHub Actions.

## Ejemplo de salida

Puedes encontrar el último archivo de precios consolidados en la carpeta `outputs/` o como *artifact* en GitHub Actions.  
Incluye:
- CSV con precios por producto y competidor.
- Reporte de alertas generado en Markdown.

## Stack usado

- Python, pandas, requests, BeautifulSoup (para scraping)
- GitHub Actions

## Frecuencia

Se ejecuta automáticamente todos los días a las 06:00 UTC.
