import logging
import time

from config import CONFIG, validate_config
from tunnel_strategies import get_strategy
from ssh_connector import connect_via_ws_and_start_socks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_tunnel(cfg: dict) -> None:
    """
    Core tunnel logic – usable by both the CLI and the GUI.
    Expects a config dict with all required keys.
    """
    try:
        validate_config(cfg)

        strategy_cls = get_strategy(cfg["MODE"])
        ws_sock = strategy_cls(cfg).establish()

        ssh_connection = connect_via_ws_and_start_socks(
            ws_socket=ws_sock,
            ssh_user=cfg["SSH_USERNAME"],
            ssh_password=cfg["SSH_PASSWORD"],
            ssh_port=cfg["SSH_PORT"],
            local_socks_port=cfg["LOCAL_SOCKS_PORT"],
        )

        logger.info(
            "SOCKS proxy up on 127.0.0.1:%d – all traffic forwarded over SSH via WS tunnel.",
            cfg["LOCAL_SOCKS_PORT"],
        )

        # Block forever (or until interrupted)
        while True:
            time.sleep(999999)

    except KeyboardInterrupt:
        logger.info("Shutting down (KeyboardInterrupt).")
    except Exception as exc:
        logger.error("Fatal error: %s", exc)
        raise  # re-raise so the caller can handle if needed


def main() -> None:
    """CLI entry point – uses the static CONFIG from config.py."""
    run_tunnel(CONFIG)


if __name__ == "__main__":
    main()