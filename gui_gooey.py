# gui_gooey.py
import argparse
from Gooey import Gooey, GooeyParser

# Import your existing tunnel logic
from tunnel_strategies import get_strategy
from ssh_connector import SSHTunnel

@Gooey(
    program_name="Custom-Internet GUI",
    program_description="SSH + HTTP Injection Tunnel",
    language="english",
    show_success_modal=True,
    clear_before_run=True,
    default_size=(800, 700)
)
def main():
    parser = GooeyParser(description="Enter your tunnel configuration")

    # --- SSH / Auth ---
    ssh_group = parser.add_argument_group("SSH Details")
    ssh_group.add_argument('--target_host', help='SSH Host (e.g., ssh.ethiodragon.sbs)', default='ssh.ethiodragon.sbs')
    ssh_group.add_argument('--target_port', help='SSH Port', default=80, type=int)
    ssh_group.add_argument('--ssh_username', help='SSH Username', default='f3q_049ae56880')
    ssh_group.add_argument('--ssh_password', help='SSH Password', widget='PasswordField')

    # --- Proxy / Frontend ---
    proxy_group = parser.add_argument_group("Remote Proxy")
    proxy_group.add_argument('--proxy_host', help='Proxy Host (e.g., viton.com)', default='viton.com')
    proxy_group.add_argument('--proxy_port', help='Proxy Port', default=80, type=int)

    # --- Payload ---
    payload_group = parser.add_argument_group("Custom Payload")
    payload_group.add_argument('--payload_template', help='Payload with [host], [crlf], [split]', widget='TextArea',
                               default='GET /cdn-cgi/trace HTTP/1.1[crlf]Host: [host][crlf]...')

    # --- Mode ---
    parser.add_argument('--mode', help='Tunnel mode', choices=['direct', 'http_payload', 'sni_fronted'], default='http_payload')

    args = parser.parse_args()

    # Build config dict (like config.py)
    config = {
        'TARGET_HOST': args.target_host,
        'TARGET_PORT': args.target_port,
        'SSH_USERNAME': args.ssh_username,
        'SSH_PASSWORD': args.ssh_password,
        'PROXY_HOST': args.proxy_host,
        'PROXY_PORT': args.proxy_port,
        'PAYLOAD_TEMPLATE': args.payload_template,
        'MODE': args.mode,
        # Add other constants from config.py if needed
    }

    # Start the tunnel using the existing logic
    # (This will call get_strategy() and SSH connection)
    from main import run_tunnel
    run_tunnel(config)

if __name__ == '__main__':
    main()