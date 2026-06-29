from watchfiles import run_process

from app.main import main as bot_main


def main() -> None:
    run_process("app", target=bot_main)


if __name__ == "__main__":
    main()
