import argparse
from Gooey import Gooey, GooeyParser

# Import the core function from main
from main import run_tunnel

@Gooey(
    program_name="Custom-Internet GUI",
    program_description="SSH + HTTP Injection Tunnel (like HTTP Custom)",
    language="english",
    show_success_modal=True,
    clear_before_run=True,
    default_size=(850, 750)
)
def gui_main():
    parser = GooeyParser(description="Enter your tunnel configuration")

    # --- SSH / Auth ---
    ssh_group = parser.add_argument_group("SSH Details")
    ssh_group.add_argument('--target_host', help='SSH Host (e.g., ssh.ethiodragon.sbs)', default='ssh.ethiodragon.sbs')
    ssh_group.add_argument('--target_port', help='SSH Port (WebSocket gateway port)', default=80, type=int)
    ssh_group.add_argument('--ssh_username', help='SSH Username', default='f3q_049ae56880')
    ssh_group.add_argument('--ssh_password', help='SSH Password', widget='PasswordField')
    ssh_group.add_argument('--ssh_port', help='Internal SSH port (usually 22)', default=22, type=int)

    # --- Proxy / Frontend ---
    proxy_group = parser.add_argument_group("Remote Proxy (Frontend)")
    proxy_group.add_argument('--proxy_host', help='Proxy Host (e.g., viton.com)', default='viton.com')
    proxy_group.add_argument('--proxy_port', help='Proxy Port', default=80, type=int)

    # --- Payload ---
    payload_group = parser.add_argument_group("Custom Payload")
    payload_group.add_argument('--payload_template', help='Payload with [host], [crlf], [split]', widget='TextArea',
                               default=(
                                   'GET /cdn-cgi/trace HTTP/1.1[crlf]'
                                   'Host: [host][crlf]'
                                   'User-Agent: [ua][crlf]'
                                   'Referer: [https/host][crlf][crlf]'
                                   '[split]'
                                   'VERSION-CONTROL ws://[host] HTTP/1.1[crlf]'
                                   'Host: [host][crlf]'
                                   'Connection: Upgrade[crlf]'
                                   ':upgrade[crlf]'
                                   't.me/rickytechwizard[crlf]'
                                   'Upgrade: websocket[crlf]'
                                   'User-Agent: Googlebot/2.1 (+http://www.google.com/bot.html)[crlf][crlf]'
                                   '[split]'
                                   'UNLOCK /? HTTP/1.1[crlf]'
                                   'Host: [proxy][crlf]'
                                   'Content-Length:999999999999[crlf]'
                               ))

    # --- Mode ---
    parser.add_argument('--mode', help='Tunnel mode', choices=['direct', 'http_payload', 'sni_fronted'], default='http_payload')
    parser.add_argument('--front_domain', help='SNI front domain (only for sni_fronted mode)', default='')
    parser.add_argument('--local_socks_port', help='Local SOCKS proxy port', default=1080, type=int)

    args = parser.parse_args()

    # Build the config dictionary that matches config.py structure
    config = {
        'MODE': args.mode,
        'FRONT_DOMAIN': args.front_domain,
        'LOCAL_SOCKS_PORT': args.local_socks_port,
        'PROXY_HOST': args.proxy_host,
        'PROXY_PORT': args.proxy_port,
        'TARGET_HOST': args.target_host,
        'TARGET_PORT': args.target_port,
        'SSH_USERNAME': args.ssh_username,
        'SSH_PASSWORD': args.ssh_password,
        'SSH_PORT': args.ssh_port,
        'PAYLOAD_TEMPLATE': args.payload_template,
    }

    # Call the core tunnel function
    run_tunnel(config)


if __name__ == '__main__':
    gui_main()