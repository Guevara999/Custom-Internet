from __future__ import annotations

import socket
import ssl
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ws_tunnel import establish_ws_tunnel

logger = logging.getLogger(__name__)


class TunnelStrategy(ABC):
    """
    Abstract Strategy that returns a connected *raw* socket ready for Paramiko.
    """

    def __init__(self, cfg: Dict):
        self.cfg = cfg

    @abstractmethod
    def establish(self) -> socket.socket:
        """
        Establish the tunnel and return an already-connected socket.
        Must raise an exception on failure.
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- #
#                             Concrete strategies                             #
# --------------------------------------------------------------------------- #

class DirectStrategy(TunnelStrategy):
    """
    Straight TCP connection to TARGET_HOST:TARGET_PORT.
    """

    def establish(self) -> socket.socket:
        return socket.create_connection(
            (self.cfg["TARGET_HOST"], self.cfg["TARGET_PORT"])
        )


class HttpPayloadStrategy(TunnelStrategy):
    """
    Default (legacy) mode: plain-text connection to PROXY_HOST where we run the
    custom HTTP/WebSocket upgrade payload defined in CONFIG['PAYLOAD_TEMPLATE'].

    Now supports:
      - [split] tokens – payload is split into parts sent with a delay.
      - [rotate=...] – list of proxy hosts; tries each in order until one works.
    """

    def _get_rotate_hosts(self) -> List[str]:
        """Extract the list of hosts from [rotate=...] in the payload template."""
        match = re.search(r'\[rotate=([^\]]+)\]', self.cfg["PAYLOAD_TEMPLATE"])
        if match:
            return [h.strip() for h in match.group(1).split(';') if h.strip()]
        return [self.cfg["PROXY_HOST"]]

    def _build_config_for_host(self, host: str) -> Dict:
        """Return a copy of the config with PROXY_HOST replaced."""
        cfg_copy = self.cfg.copy()
        cfg_copy["PROXY_HOST"] = host
        return cfg_copy

    def establish(self) -> socket.socket:
        hosts = self._get_rotate_hosts()
        split_delay = self.cfg.get("SPLIT_DELAY", 0.5)  # default 500ms

        last_exception = None
        for host in hosts:
            try:
                logger.info(f"Trying proxy host: {host}")
                cfg_copy = self._build_config_for_host(host)
                return establish_ws_tunnel(
                    proxy_host=host,
                    proxy_port=cfg_copy["PROXY_PORT"],
                    target_host=cfg_copy["TARGET_HOST"],
                    target_port=cfg_copy["TARGET_PORT"],
                    payload_template=cfg_copy["PAYLOAD_TEMPLATE"],
                    use_tls=False,
                    split_delay=split_delay,
                )
            except Exception as e:
                last_exception = e
                logger.warning(f"Host {host} failed: {e}")
                # Optionally wait a short time before trying next host
                time.sleep(0.2)
                continue

        # If we exhausted all hosts, raise the last exception
        raise last_exception or RuntimeError("All proxy hosts failed.")


class SNIFrontedStrategy(TunnelStrategy):
    """
    Like HttpPayloadStrategy but wrapped in TLS with an arbitrary SNI (domain
    fronting).  The TLS layer hides the HTTP upgrade and the front domain can
    be an unrelated host served by the same CDN.
    """

    def _get_rotate_hosts(self) -> List[str]:
        """Same as in HttpPayloadStrategy – rotate over front domains if needed."""
        match = re.search(r'\[rotate=([^\]]+)\]', self.cfg["PAYLOAD_TEMPLATE"])
        if match:
            return [h.strip() for h in match.group(1).split(';') if h.strip()]
        return [self.cfg["PROXY_HOST"]]

    def establish(self) -> socket.socket:
        hosts = self._get_rotate_hosts()
        split_delay = self.cfg.get("SPLIT_DELAY", 0.5)

        last_exception = None
        for host in hosts:
            try:
                logger.info(f"Trying SNI fronted host: {host}")
                # 1. Build a TLS socket to PROXY_HOST with forged SNI.
                raw_sock = socket.create_connection((host, self.cfg["PROXY_PORT"]))
                ctx = ssl.create_default_context()
                front_domain = self.cfg.get("FRONT_DOMAIN") or host
                tls_sock = ctx.wrap_socket(raw_sock, server_hostname=front_domain)

                # 2. Perform the WebSocket upgrade inside the TLS tunnel.
                return establish_ws_tunnel(
                    proxy_host=host,
                    proxy_port=self.cfg["PROXY_PORT"],
                    target_host=self.cfg["TARGET_HOST"],
                    target_port=self.cfg["TARGET_PORT"],
                    payload_template=self.cfg["PAYLOAD_TEMPLATE"],
                    sock=tls_sock,          # reuse the already-encrypted socket
                    use_tls=False,          # don’t double-wrap
                    split_delay=split_delay,
                )
            except Exception as e:
                last_exception = e
                logger.warning(f"SNI host {host} failed: {e}")
                time.sleep(0.2)
                continue

        raise last_exception or RuntimeError("All SNI hosts failed.")


# --------------------------------------------------------------------------- #
#                                Factory helper                               #
# --------------------------------------------------------------------------- #

def get_strategy(mode: str) -> type[TunnelStrategy]:
    """
    Map CONFIG['MODE'] to its Strategy class.

    >>> strategy_cls = get_strategy("sni_fronted")
    >>> tunnel = strategy_cls(cfg).establish()
    """
    table = {
        "direct":       DirectStrategy,
        "http_payload": HttpPayloadStrategy,
        "sni_fronted":  SNIFrontedStrategy,
    }
    try:
        return table[mode.lower()]
    except KeyError:
        valid = ", ".join(table.keys())
        raise ValueError(f"Unknown MODE '{mode}'. Valid choices: {valid}")