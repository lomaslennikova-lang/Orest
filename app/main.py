import logging
import os
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.database import AsyncSessionLocal, check_database_connection, init_database
from app.models import Category, Transaction, User


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
        "Orest - персональний Telegram-бот для одного користувача.\n"
        "Наразі я вмію відповідати на /start, /about, /help, /expense, "
        "/daily_expenses і повторювати текстові повідомлення."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Received /help command %s", get_update_context(update))
    await update.message.reply_text(
        "Доступні команди:\n"
        "/start - запустити бота\n"
        "/about - коротко про бота\n"
        "/help - показати цю довідку\n"
        "/expense <amount> <category> - додати витрату\n"
        "/daily_expenses <YYYY-MM> - сума денних витрат за місяць"
    )


def parse_amount(value: str) -> Decimal:
    normalized_value = value.replace(",", ".")
    amount = Decimal(normalized_value)

    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    return amount.quantize(Decimal("0.01"))


def parse_month(value: str) -> tuple[date, date]:
    try:
        year_text, month_text = value.split("-", maxsplit=1)
        year = int(year_text)
        month = int(month_text)
        monthrange(year, month)
    except ValueError as error:
        raise ValueError("Month must use YYYY-MM format.") from error

    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    return start_date, end_date


async def get_or_create_user(session: AsyncSession, telegram_user) -> User:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_user.id)
    )
    user = result.scalar_one_or_none()

    if user:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        return user

    user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
    )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_category(
    session: AsyncSession,
    user: User,
    category_name: str,
) -> Category:
    result = await session.execute(
        select(Category).where(
            Category.user_id == user.id,
            Category.name == category_name,
        )
    )
    category = result.scalar_one_or_none()

    if category:
        return category

    category = Category(user_id=user.id, name=category_name)
    session.add(category)
    await session.flush()
    return category


async def expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Received /expense command %s", get_update_context(update))

    if not update.message or not update.effective_user:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Приклад: /expense 12.50 food")
        return

    try:
        amount = parse_amount(context.args[0])
    except (InvalidOperation, ValueError):
        await update.message.reply_text(
            "Сума має бути додатним числом. Приклад: /expense 12.50 food"
        )
        return

    category_name = " ".join(context.args[1:]).strip().lower()
    if not category_name:
        await update.message.reply_text(
            "Категорія обов'язкова. Приклад: /expense 12.50 food"
        )
        return

    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(session, update.effective_user)
        category = await get_or_create_category(session, user, category_name)
        transaction = Transaction(
            user_id=user.id,
            category_id=category.id,
            amount=amount,
        )

        session.add(transaction)
        await session.commit()

    await update.message.reply_text(
        f"Витрату додано: {amount} у категорії '{category_name}'."
    )


async def daily_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Received /daily_expenses command %s", get_update_context(update))

    if not update.message or not update.effective_user:
        return

    if len(context.args) != 1:
        await update.message.reply_text("Приклад: /daily_expenses 2026-07")
        return

    try:
        start_date, end_date = parse_month(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Місяць має бути у форматі YYYY-MM. Приклад: /daily_expenses 2026-07"
        )
        return

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("За цей місяць витрат ще немає.")
            return

        result = await session.execute(
            select(
                func.date(Transaction.created_at).label("expense_day"),
                func.sum(Transaction.amount).label("daily_total"),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.created_at >= start_date,
                Transaction.created_at < end_date,
            )
            .group_by("expense_day")
            .order_by("expense_day")
        )
        rows = result.all()

    if not rows:
        await update.message.reply_text("За цей місяць витрат ще немає.")
        return

    total = sum((row.daily_total for row in rows), Decimal("0.00"))
    lines = [f"Витрати за {context.args[0]}:"]
    lines.extend(f"{row.expense_day}: {row.daily_total:.2f}" for row in rows)
    lines.append(f"Разом: {total:.2f}")

    await update.message.reply_text("\n".join(lines))


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
        "Не знаю такої команди. Доступні команди: /start, /about, /help, "
        "/expense, /daily_expenses."
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
    await init_database()
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
    application.add_handler(CommandHandler("expense", expense))
    application.add_handler(CommandHandler("daily_expenses", daily_expenses))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error_handler)

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
