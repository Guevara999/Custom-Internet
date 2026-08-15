import logging
import time
import threading
import socket
import requests
from typing import Dict, Any

from config import CONFIG, validate_config
from tunnel_strategies import get_strategy
from ssh_connector import connect_via_ws_and_start_socks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Global flag for stopping
_stop_event = threading.Event()


def ping_worker(proxy_port: int, ping_url: str, ping_timeout: int, ping_interval: int):
    """Background thread to ping a URL through the SOCKS proxy to check health."""
    proxies = {
        'http': f'socks5h://127.0.0.1:{proxy_port}',
        'https': f'socks5h://127.0.0.1:{proxy_port}',
    }
    while not _stop_event.is_set():
        try:
            # Ping through the proxy with timeout
            response = requests.get(ping_url, proxies=proxies, timeout=ping_timeout)
            if response.status_code < 400:
                logger.debug(f"Ping OK: {response.status_code} ({int(response.elapsed.total_seconds()*1000)}ms)")
            else:
                logger.warning(f"Ping failed: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Ping timeout or error: {e}")
        # Wait for the next interval
        _stop_event.wait(timeout=ping_interval)


def run_tunnel(cfg: Dict[str, Any], auto_reconnect: bool = True) -> None:
    """
    Core tunnel logic with keep-alive ping and auto-reconnect.
    """
    attempt = 0
    while True:
        attempt += 1
        logger.info(f"Connection attempt #{attempt}")
        try:
            validate_config(cfg)

            # 1. Establish WebSocket tunnel
            strategy_cls = get_strategy(cfg["MODE"])
            ws_sock = strategy_cls(cfg).establish()

            # 2. Start SSH & SOCKS proxy
            ssh_connection = connect_via_ws_and_start_socks(
                ws_socket=ws_sock,
                ssh_user=cfg["SSH_USERNAME"],
                ssh_password=cfg["SSH_PASSWORD"],
                ssh_port=cfg["SSH_PORT"],
                local_socks_port=cfg["LOCAL_SOCKS_PORT"],
            )

            logger.info(
                "SOCKS proxy up on 127.0.0.1:%d – all traffic forwarded over SSH.",
                cfg["LOCAL_SOCKS_PORT"],
            )

            # 3. Start Ping / Keep-Alive thread
            _stop_event.clear()
            ping_thread = threading.Thread(
                target=ping_worker,
                args=(
                    cfg["LOCAL_SOCKS_PORT"],
                    cfg.get("PING_URL", "https://dns.google"),
                    cfg.get("PING_TIMEOUT", 5),
                    cfg.get("PING_INTERVAL", 2),
                ),
                daemon=True,
            )
            ping_thread.start()

            # 4. Block until the tunnel dies or user interrupts
            while ssh_connection.is_active():
                time.sleep(1)
            # If we exit the loop, SSH died
            logger.warning("SSH connection lost.")

            # Stop the ping thread
            _stop_event.set()
            ping_thread.join(timeout=1)

            # If auto-reconnect is disabled, break the loop
            if not auto_reconnect:
                break

            logger.info("Reconnecting in 3 seconds...")
            time.sleep(3)
            continue

        except KeyboardInterrupt:
            logger.info("Shutting down (KeyboardInterrupt).")
            _stop_event.set()
            break
        except Exception as exc:
            logger.error(f"Fatal error: {exc}")
            if not auto_reconnect:
                break
            logger.info("Reconnecting in 5 seconds...")
            time.sleep(5)
            continue


def main() -> None:
    """CLI entry point – uses the static CONFIG from config.py."""
    # You can add PING_URL, PING_TIMEOUT, PING_INTERVAL to CONFIG if you want
    run_tunnel(CONFIG, auto_reconnect=CONFIG.get("ALWAYS_RECONNECT", True))


if __name__ == "__main__":
    main()