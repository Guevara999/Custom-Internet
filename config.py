# config.py

CONFIG = {
    'MODE': 'http_payload',        # direct | http_payload | sni_fronted
    'FRONT_DOMAIN': '',            # used only in sni_fronted

    # The local port on which we will run a SOCKS proxy
    'LOCAL_SOCKS_PORT': 1080,

    # The intermediate HTTP proxy or WebSocket proxy you connect to
    'PROXY_HOST': '',
    'PROXY_PORT': 0,

    # The ultimate SSH server that lives behind the WS tunnel
    'TARGET_HOST': '',
    'TARGET_PORT': 0,

    # SSH credentials
    'SSH_USERNAME': '',
    'SSH_PASSWORD': '',
    'SSH_PORT': 0,

    # The WebSocket handshake payload (with [split], [rotate], etc.)
    'PAYLOAD_TEMPLATE': (
        "GET / HTTP/1.1[crlf]"
    ),

    # --- Keep-Alive / Ping Settings (like HTTP Custom) ---
    'PING_URL': 'https://dns.google',      # URL to ping
    'PING_INTERVAL': 2,                    # seconds between pings
    'PING_TIMEOUT': 5,                     # seconds to wait for response
    'ALWAYS_RECONNECT': True,              # auto-reconnect on failure
}

def validate_config(cfg: dict) -> None:
    """Raise ValueError early if required config fields are missing."""
    required_str = ['PROXY_HOST', 'TARGET_HOST', 'SSH_USERNAME', 'SSH_PASSWORD']
    required_port = ['PROXY_PORT', 'TARGET_PORT', 'SSH_PORT']
    for key in required_str:
        if not cfg.get(key):
            raise ValueError(f"CONFIG['{key}'] must not be empty")
    for key in required_port:
        if not cfg.get(key):
            raise ValueError(f"CONFIG['{key}'] must be a non-zero port number")