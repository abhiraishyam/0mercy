import socket
import sys
import config
from protocol import create_packet, parse_packet


def run_sender(device_id: str):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((config.SMS_SERVER_HOST, config.SMS_SERVER_PORT))
    print(f"[{device_id}] Connected to Software 2 SMS Server!")
    print("Type messages below to send SMS (press Ctrl+C to exit).\n")

    try:
        while True:
            number = input(f"[{device_id}] Enter recipient phone number: ").strip()
            text = input(f"[{device_id}] Enter SMS text: ").strip()
            if not number or not text:
                continue

            packet = create_packet(
                msg_type="send_sms",
                source=device_id,
                target="software_2",
                payload={"to": number, "text": text},
            )
            sock.sendall(packet)

            resp_raw = sock.recv(1024)
            resp = parse_packet(resp_raw.split(b"\n")[0])
            print(f"[{device_id}] Software 2 Response: {resp['payload']}\n")
    except KeyboardInterrupt:
        print(f"\n[{device_id}] Exiting.")
    finally:
        sock.close()


if __name__ == "__main__":
    client_name = sys.argv[1] if len(sys.argv) > 1 else "Phone_Device_A"
    run_sender(client_name)
