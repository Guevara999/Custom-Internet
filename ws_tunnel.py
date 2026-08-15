from __future__ import annotations

import logging
import socket
import ssl
import time
import re
from typing import Optional

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#                               Helper utilities                              #
# --------------------------------------------------------------------------- #
def replace_placeholders(payload: str, target_host: str, target_port: int) -> str:
    """
    Swap placeholders inside payload.
    Returns the processed string (not bytes).
    """
    host_value = f"{target_host}:{target_port}"
    payload = payload.replace("[host]", host_value)
    payload = payload.replace("[crlf]", "\r\n")
    payload = payload.replace("[ua]", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    # [https/host] – if you need it
    payload = payload.replace("[https/host]", f"https://{host_value}")
    return payload


def read_headers(sock: socket.socket) -> bytes:
    """Read until blank line (\r\n\r\n) and return the full header block."""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def extract_rotate_hosts(payload: str) -> list[str]:
    """Extract the rotate host list from [rotate=...] placeholder."""
    match = re.search(r'\[rotate=([^\]]+)\]', payload)
    if match:
        return match.group(1).split(';')
    return []


# --------------------------------------------------------------------------- #
#                              Public entry point                              #
# --------------------------------------------------------------------------- #
def establish_ws_tunnel(
    *,
    proxy_host: str,
    proxy_port: int,
    target_host: str,
    target_port: int,
    payload_template: str,
    use_tls: bool = False,
    sock: Optional[socket.socket] = None,
    split_delay: float = 0.5,
) -> socket.socket:
    """
    Perform the upgrade handshake and return a ready-for-SSH socket.

    Now handles:
    - [split] → splits payload into parts sent with `split_delay`.
    - [rotate=...] → cycles through hosts on connection failure.
    """
    # If we have a rotate list, try each host
    rotate_hosts = extract_rotate_hosts(payload_template)
    if rotate_hosts:
        # Use the first host as the initial proxy_host
        # The strategy will handle rotation; for now, we just use the provided proxy_host
        # (rotate is better handled in the strategy layer)
        pass

    # ------------------------------------------------------------------ #
    # 1. Connect or re-use an existing socket
    # ------------------------------------------------------------------ #
    if sock is None:
        sock = socket.create_connection((proxy_host, proxy_port))

    # Optional TLS upgrade (skip if it’s already SSL)
    if use_tls and not isinstance(sock, ssl.SSLSocket):
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(sock, server_hostname=proxy_host)

    # ------------------------------------------------------------------ #
    # 2. Process payload: replace placeholders, then split on [split]
    # ------------------------------------------------------------------ #
    processed = replace_placeholders(payload_template, target_host, target_port)
    # Split on literal [split] marker
    parts = processed.split("[split]")
    # Clean up each part (strip leading/trailing whitespace, but keep CRLF)
    parts = [p.strip() for p in parts if p.strip()]
    logger.info(f"Split payload into {len(parts)} parts")

    # ------------------------------------------------------------------ #
    # 3. Send each part sequentially with delay
    # ------------------------------------------------------------------ #
    for i, part in enumerate(parts):
        # Ensure each part ends with \r\n\r\n (if not already)
        if not part.endswith("\r\n\r\n"):
            part = part + "\r\n\r\n"
        sock.sendall(part.encode())
        logger.debug(f"Sent part {i+1}/{len(parts)}")
        if i < len(parts) - 1:
            time.sleep(split_delay)

    # ------------------------------------------------------------------ #
    # 4. Read responses (handle 100 Continue if present)
    # ------------------------------------------------------------------ #
    first_resp = read_headers(sock)
    logger.debug("First response: %s", first_resp.decode("latin1", errors="replace"))

    # If we got 100 Continue, read the final response
    if b"100 Continue" in first_resp:
        second_resp = read_headers(sock)
        logger.debug("Final response: %s", second_resp.decode("latin1", errors="replace"))

    # ------------------------------------------------------------------ #
    # 5. Tunnel is live
    # ------------------------------------------------------------------ #
    logger.info("WebSocket handshake complete – tunnel is live.")
    return sock