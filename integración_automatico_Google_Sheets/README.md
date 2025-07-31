# Automatización entre Google Sheets y API externa

Este proyecto simula una automatización real para equipos comerciales que usan Google Sheets como CRM. Se conecta a la hoja de cálculo, enriquece los leads con un score simulado y actualiza los datos automáticamente.

## ¿Qué hace?

- Lee nuevos leads de una hoja de Google Sheets.
- Llama a una API simulada para calcular un score.
- Actualiza automáticamente la hoja con la información.

## ¿Para quién es útil?

- Agencias de marketing o ventas que gestionan leads en Sheets.
- Empresas que quieren automatizar procesos sin pagar por un CRM caro.
- Freelancers que integran APIs externas con flujos no-code.

## Stack

- Python, gspread, Google Sheets API
- GitHub Actions (opcional)

## Requisitos

- Archivo `credentials.json` con acceso a Google API.
- Hoja de cálculo compartida con ese email de servicio.
