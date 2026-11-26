import socket
import sys
import threading
import config
from protocol import create_packet, parse_packet


def receive_loop(recv_sock: socket.socket, phone_dir: dict):
    buffer = b""
    try:
        while True:
            chunk = recv_sock.recv(1024)
            if not chunk:
                print("\n[DISCONNECTED] Lost connection to Software 1 Hub.")
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                packet = parse_packet(line)
                if packet and packet.get("type") == "routed_sms":
                    payload = packet["payload"]
                    sender = str(payload.get("sender_device", "Unknown"))
                    sender_label = phone_dir.get(sender, sender)
                    text = payload.get("message_text", "")
                    print(f"\n[INCOMING SMS] From {sender_label} ({sender}): {text}")
                    print("Recipient no. (or 'exit'): ", end="", flush=True)
    except OSError:
        pass


def run_phone(my_number: str):
    phone_dir = getattr(config, "PHONE_DIRECTORY", {})
    my_label = phone_dir.get(my_number, my_number)

    # 1. Connect to Software 1 Hub (port 5002) to receive incoming messages
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    recv_sock.connect((config.HUB_HOST, config.HUB_TARGET_PORT))
    reg_packet = create_packet(
        msg_type="register_device",
        source=my_number,
        target="software_1_hub",
        payload={"device_name": my_number},
    )
    recv_sock.sendall(reg_packet)

    threading.Thread(
        target=receive_loop, args=(recv_sock, phone_dir), daemon=True
    ).start()

    # 2. Connect to Software 2 (port 6001) to send outgoing messages
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    send_sock.connect((config.SMS_SERVER_HOST, config.SMS_SERVER_PORT))

    print(f"=== {my_label} ({my_number}) READY ===")
    if phone_dir:
        print("Recognized numbers:", phone_dir)

    ack_buffer = b""
    try:
        while True:
            recipient = input("Recipient no. (or 'exit'): ").strip()
            if recipient.lower() in ("exit", "quit"):
                break
            text = input("Message: ").strip()
            if not recipient or not text:
                print("[WARN] Both recipient no. and message are required.")
                continue

            sms_packet = create_packet(
                msg_type="send_sms",
                source=my_number,
                target="software_2",
                payload={"to": recipient, "text": text},
            )
            send_sock.sendall(sms_packet)

            # Read confirmation from Software 2
            while b"\n" not in ack_buffer:
                chunk = send_sock.recv(1024)
                if not chunk:
                    break
                ack_buffer += chunk
            if b"\n" in ack_buffer:
                line, ack_buffer = ack_buffer.split(b"\n", 1)
                reply = parse_packet(line)
                if reply:
                    print(f"[SENT] {reply['payload']}")
    except KeyboardInterrupt:
        pass
    finally:
        send_sock.close()
        recv_sock.close()
        print(f"\n[{my_label}] Closed.")


if __name__ == "__main__":
    number = sys.argv[1].strip() if len(sys.argv) > 1 else input("Enter your phone number: ").strip()
    run_phone(number)