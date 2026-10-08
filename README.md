# Bot de Autoatendimento Telegram

Bot que coleta nome, telefone e e-mail, verifica o e-mail com código
enviado por SMTP (Gmail), gera um formulário de marketing em PDF e
salva todos os cadastros em JSON.

## Fluxo
1. /start → nome → telefone → e-mail
2. Código de verificação por e-mail
3. Descrição do formulário
4. PDF gerado, enviado no chat e salvo em `data/cadastros.json`

## Variáveis de ambiente
- `BOT_TOKEN` – token do @BotFather
- `GMAIL_USER` – seu Gmail
- `GMAIL_APP_PASSWORD` – senha de app do Gmail (16 caracteres)
- `DATA_DIR` – pasta de dados (padrão: `data`)

## Deploy no Render
1. Suba este repositório no GitHub.
2. No Render, crie um **Background Worker**.
3. Build: `pip install -r requirements.txt`
4. Start: `python bot.py`
5. Configure as variáveis de ambiente.

## Observação
No plano gratuito do Render o disco é efêmero — os JSON/PDF podem
ser perdidos em reinícios. Para produção, use um banco externo
(PostgreSQL, MongoDB Atlas) ou Google Sheets.
