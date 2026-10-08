import os
import json
import random
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# ---------- CONFIGURAÇÃO ----------
BOT_TOKEN = os.environ["BOT_TOKEN"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_DIR.mkdir(exist_ok=True)

# Estados da conversa
NAME, PHONE, EMAIL, CODE, DESCRICAO = range(5)
MAX_CODE_ATTEMPTS = 3


# ---------- ENVIO DE E-MAIL ----------
def send_email_code(to_email: str, code: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = "Seu código de verificação"
    body = (
        f"Olá!\n\nSeu código de verificação é: {code}\n\n"
        "Se você não solicitou este código, apenas ignore este e-mail."
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)


# ---------- GERAÇÃO DO PDF ----------
def gerar_pdf(dados: dict, caminho: Path) -> None:
    doc = SimpleDocTemplate(
        str(caminho),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle("titulo", parent=styles["Title"], fontSize=18)
    corpo = styles["Normal"]

    elementos = []
    elementos.append(Paragraph("Formulário de Marketing", titulo_style))
    elementos.append(Spacer(1, 0.5 * cm))
    elementos.append(Paragraph(f"<b>Data:</b> {dados['data']}", corpo))
    elementos.append(Spacer(1, 0.5 * cm))

    tabela_dados = [
        ["Nome", dados["nome"]],
        ["Telefone", dados["telefone"]],
        ["E-mail", dados["email"]],
    ]
    tabela = Table(tabela_dados, colWidths=[4 * cm, 12 * cm])
    tabela.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elementos.append(tabela)
    elementos.append(Spacer(1, 0.8 * cm))
    elementos.append(Paragraph("<b>Descrição:</b>", styles["Heading2"]))
    elementos.append(Spacer(1, 0.2 * cm))

    for linha in dados["descricao"].split("\n"):
        elementos.append(Paragraph(linha if linha.strip() else "&nbsp;", corpo))

    doc.build(elementos)


# ---------- PERSISTÊNCIA ----------
def salvar_dados(dados: dict) -> None:
    arquivo = DATA_DIR / "cadastros.json"
    registros = []
    if arquivo.exists():
        try:
            registros = json.loads(arquivo.read_text(encoding="utf-8"))
        except Exception:
            registros = []
    registros.append(dados)
    arquivo.write_text(
        json.dumps(registros, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------- HANDLERS DA CONVERSA ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Olá! 👋\nVamos começar seu cadastro.\n\nQual é o seu *nome*?",
        parse_mode="Markdown",
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["nome"] = update.message.text.strip()
    await update.message.reply_text(
        f"Prazer, {context.user_data['nome']}! 📱\n"
        "Agora me diga seu *telefone* (com DDD):",
        parse_mode="Markdown",
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["telefone"] = update.message.text.strip()
    await update.message.reply_text(
        "Ótimo! Agora me envie seu *e-mail*:", parse_mode="Markdown"
    )
    return EMAIL


async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        await update.message.reply_text(
            "Hmm, esse e-mail parece inválido. Tente novamente:"
        )
        return EMAIL

    context.user_data["email"] = email
    codigo = f"{random.randint(0, 999999):06d}"
    context.user_data["codigo"] = codigo
    context.user_data["tentativas"] = 0

    try:
        send_email_code(email, codigo)
    except Exception as e:
        await update.message.reply_text(
            f"❌ Erro ao enviar e-mail: {e}\n" "Tente novamente com outro e-mail."
        )
        return EMAIL

    await update.message.reply_text(
        f"📧 Enviei um código de verificação para *{email}*.\n\n"
        "Digite o código de 6 dígitos:",
        parse_mode="Markdown",
    )
    return CODE


async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    digitado = update.message.text.strip()

    if digitado == context.user_data.get("codigo"):
        await update.message.reply_text(
            "✅ E-mail verificado!\n\n"
            "Agora escreva a *descrição do formulário de marketing* "
            "(pode ser um texto único ou várias linhas):",
            parse_mode="Markdown",
        )
        return DESCRICAO

    context.user_data["tentativas"] = context.user_data.get("tentativas", 0) + 1
    restantes = MAX_CODE_ATTEMPTS - context.user_data["tentativas"]

    if restantes <= 0:
        await update.message.reply_text(
            "❌ Você excedeu o número de tentativas.\nEnvie /start para recomeçar."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"❌ Código incorreto. Você tem {restantes} tentativa(s). Tente novamente:"
    )
    return CODE


async def get_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    descricao = update.message.text.strip()
    dados = {
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "telegram_id": update.effective_user.id,
        "nome": context.user_data["nome"],
        "telefone": context.user_data["telefone"],
        "email": context.user_data["email"],
        "descricao": descricao,
    }

    pasta_pdf = DATA_DIR / "pdfs"
    pasta_pdf.mkdir(exist_ok=True)
    nome_pdf = pasta_pdf / (
        f"formulario_{update.effective_user.id}_" f"{int(datetime.now().timestamp())}.pdf"
    )

    gerar_pdf(dados, nome_pdf)
    salvar_dados(dados)

    await update.message.reply_text("📄 Aqui está o seu formulário em PDF:")
    with open(nome_pdf, "rb") as f:
        await update.message.reply_document(document=f, filename=nome_pdf.name)

    await update.message.reply_text(
        "Tudo salvo com sucesso! 🎉\n\nEnvie /start para recomeçar."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Operação cancelada. Envie /start para começar de novo."
    )
    return ConversationHandler.END


# ---------- MAIN ----------
def main() -> None:
    # ✅ CORREÇÃO para Python 3.14: cria e registra um event loop manualmente
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception as e:
        print(f"Aviso ao configurar event loop: {e}")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_descricao)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    print("🤖 Bot iniciado...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
