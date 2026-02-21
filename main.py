from __future__ import annotations

import logging
import sys

from PyQt5.QtWidgets import QApplication

from gui import MainWindow
from mexc_flipping_gui.models.config_manager import ConfigManager
from mexc_flipping_gui.models.database import init_db
from mexc_flipping_gui.models.encryption import EncryptedSettings, get_or_create_fernet_key
from mexc_flipping_gui.models.pair_manager import PairManager
from strategy import FlippingStrategy
from mexc_flipping_gui.models.trader import Trader


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("mexc_flipping_bot")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    bot_file = logging.FileHandler("bot.log", encoding="utf-8")
    bot_file.setFormatter(formatter)

    operations_file = logging.FileHandler("operations.log", encoding="utf-8")
    operations_file.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(console)
    logger.addHandler(bot_file)
    logger.addHandler(operations_file)
    return logger


def create_exchange(api_key: str, api_secret: str):
    import ccxt

    return ccxt.mexc(
        {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "swap", "unifiedAccount": True},
        }
    )


def main() -> int:
    logger = setup_logging()
    db_connection = init_db("trading_bot.db")

    fernet = get_or_create_fernet_key("master.key")
    encrypted_settings = EncryptedSettings(db_connection, fernet)
    config_manager = ConfigManager(db_connection)
    pair_manager = PairManager(db_connection, logger)

    api_key, api_secret = encrypted_settings.get_api_keys()

    trader = None
    strategy = None

    if api_key and api_secret:
        try:
            exchange = create_exchange(api_key, api_secret)
            trader = Trader(exchange, pair_manager, db_connection, config_manager, logger)
            strategy = FlippingStrategy(exchange, config_manager, logger)
            logger.info("Trader initialized. Waiting for Start Trading button.")
        except Exception as exc:
            logger.error("Failed to initialize exchange/trader: %s", exc)
    else:
        logger.warning("API keys not configured. Add keys in API tab and restart application.")

    app = QApplication(sys.argv)
    window = MainWindow(
        db_connection=db_connection,
        fernet=fernet,
        pair_manager=pair_manager,
        config_manager=config_manager,
        logger=logger,
        encrypted_settings=encrypted_settings,
        trader=trader,
        strategy=strategy,
    )

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
