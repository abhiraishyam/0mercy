import socket
import sys
import time
import config
from protocol import create_packet, parse_packet


def run_target_device(device_name: str):
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((config.HUB_HOST, config.HUB_TARGET_PORT))
            print(f"[{device_name}] Connected to Software 1 Hub!")

            # Register this device name with Software 1
            reg = create_packet(
                msg_type="register_device",
                source=device_name,
                target="software_1_hub",
                payload={"device_name": device_name},
            )
            sock.sendall(reg)

            buffer = b""
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    packet = parse_packet(line)
                    if packet and packet.get("type") == "routed_sms":
                        print(f"\n[{device_name} RECEIVED DATA FROM SOFTWARE 1]")
                        print(f"  From Sender Device : {packet['payload']['sender_device']}")
                        print(f"  Recipient Number   : {packet['payload']['recipient_number']}")
                        print(f"  Message Text       : {packet['payload']['message_text']}")
                        print(f"  SMS Status         : {packet['payload']['sms_status']}")
        except OSError as e:
            print(f"[{device_name}] Disconnected from Hub ({e}). Reconnecting in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "Target_Device_1"
    run_target_device(name)
