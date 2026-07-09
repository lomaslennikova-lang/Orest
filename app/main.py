import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.database import check_database_connection


logger = logging.getLogger(__name__)


def configure_logging() -> None:
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_levels = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }
    log_level = log_levels.get(log_level_name, logging.INFO)

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=log_level,
    )


def get_update_context(update: Update) -> str:
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    return f"user_id={user_id} chat_id={chat_id}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Received /start command %s", get_update_context(update))
    await update.message.reply_text("Вітаю! Бот запущено і готовий до роботи.")


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Received /about command %s", get_update_context(update))
    await update.message.reply_text(
        "Orest — персональний Telegram-бот для одного користувача.\n"
        "Наразі я вмію відповідати на /start, /about і повторювати текстові повідомлення."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Received /help command %s", get_update_context(update))
    await update.message.reply_text(
        "Доступні команди:\n"
        "/start — запустити бота\n"
        "/about — коротко про бота\n"
        "/help — показати цю довідку"
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.debug("Received text message %s", get_update_context(update))
    await update.message.reply_text(update.message.text)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.warning(
        "Received unknown command %s command=%s",
        get_update_context(update),
        update.message.text.split(maxsplit=1)[0],
    )
    await update.message.reply_text(
        "Не знаю такої команди. Доступні команди: /start, /about, /help."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    update_context = (
        get_update_context(update) if isinstance(update, Update) else "no update context"
    )
    exc_info = (type(error), error, error.__traceback__) if error else None

    logger.error(
        "Unhandled error while processing update %s",
        update_context,
        exc_info=exc_info,
    )


async def post_init(application: Application) -> None:
    await check_database_connection()
    logger.info("Database connection is ready")


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")
    configure_logging()

    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN is not set")
        raise RuntimeError("BOT_TOKEN is not set. Add it to your .env file.")

    logger.info("Starting bot")
    application = Application.builder().token(token).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error_handler)

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
