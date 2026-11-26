import queue
import socket
import threading
import time
import config
from protocol import create_packet, parse_packet

class SMSSoftwareNode:
    """Software 2: Receives SMS from multiple devices, sends SMS, and relays data to Software 1."""

    def __init__(self):
        self.outbound_queue: queue.Queue[bytes] = queue.Queue()
        self.hub_socket: socket.socket | None = None
        self.connected_to_hub = threading.Event()

    def dispatch_physical_sms(self, sender_device: str, phone_number: str, message: str) -> str:
        """
        Hook for real SMS sending (e.g., via PySerial + GSM SIM800L modem or ADB/Android gateway).
        Currently simulates SMS dispatch and returns delivery status.
        """
        print(f"[SMS GATEWAY] Sending SMS to {phone_number} (requested by {sender_device}): '{message}'")
        time.sleep(0.2)
        return "SENT"

    def hub_connection_worker(self):
        """Maintains persistent Bluetooth (or TCP) connection to Software 1 and flushes queued SMS data."""
        while True:
            try:
                if config.TRANSPORT_MODE == "bluetooth":
                    print(f"[SOFTWARE 2] Connecting to Software 1 via Bluetooth ({config.HUB_BLUETOOTH_MAC})...")
                    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                    sock.connect((config.HUB_BLUETOOTH_MAC, config.BLUETOOTH_CHANNEL))
                else:
                    print(f"[SOFTWARE 2] Connecting to Software 1 via TCP ({config.HUB_HOST}:{config.HUB_SMS_PORT})...")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((config.HUB_HOST, config.HUB_SMS_PORT))

                self.hub_socket = sock
                self.connected_to_hub.set()
                print("[SOFTWARE 2] Connected to Software 1 Hub!")

                # Start listener thread for ACKs from Software 1
                threading.Thread(target=self.listen_hub_acks, args=(sock,), daemon=True).start()

                # Flush queued SMS packets to Software 1
                while self.connected_to_hub.is_set():
                    packet_bytes = self.outbound_queue.get()
                    try:
                        sock.sendall(packet_bytes)
                    except OSError:
                        # Put packet back in queue if wireless link drops mid-send
                        self.outbound_queue.put(packet_bytes)
                        raise

            except OSError as e:
                self.connected_to_hub.clear()
                print(f"[SOFTWARE 2] Hub disconnected ({e}). Retrying in 3 seconds...")
                time.sleep(3)

    def listen_hub_acks(self, sock: socket.socket):
        buffer = b""
        try:
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    ack = parse_packet(line)
                    if ack and ack.get("type") == "sms_ack":
                        print(f"[SOFTWARE 2 <- HUB ACK] Confirmed by Software 1: {ack['payload']}")
        except OSError:
            pass
        finally:
            self.connected_to_hub.clear()

    def handle_sender_device(self, conn: socket.socket, addr):
        """Handles an individual sender device submitting SMS messages to Software 2."""
        print(f"[SOFTWARE 2] Sender device connected from {addr}")
        buffer = b""
        try:
            while True:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    req = parse_packet(line)
                    if not req or req.get("type") != "send_sms":
                        continue

                    sender_device = req.get("source", f"client_{addr[1]}")
                    phone_number = req["payload"].get("to", "")
                    text = req["payload"].get("text", "")

                    # 1. Dispatch the SMS
                    status = self.dispatch_physical_sms(sender_device, phone_number, text)

                    # 2. Queue SMS data to forward wirelessly to Software 1
                    hub_packet = create_packet(
                        msg_type="sms_data",
                        source="software_2",
                        target="software_1_hub",
                        payload={
                            "sender_device": sender_device,
                            "recipient_number": phone_number,
                            "message_text": text,
                            "sms_status": status,
                        },
                    )
                    self.outbound_queue.put(hub_packet)

                    # 3. Reply immediately to the sender device
                    reply = create_packet(
                        msg_type="sms_queued",
                        source="software_2",
                        target=sender_device,
                        payload={"status": status, "relayed_to_hub": self.connected_to_hub.is_set()},
                    )
                    conn.sendall(reply)
        except OSError:
            pass
        finally:
            conn.close()
            print(f"[SOFTWARE 2] Sender device disconnected: {addr}")

    def run(self):
        print("=== SOFTWARE 2: MULTI-DEVICE SMS RELAY STARTED ===")
        threading.Thread(target=self.hub_connection_worker, daemon=True).start()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((config.SMS_SERVER_HOST, config.SMS_SERVER_PORT))
        server.listen(10)
        print(f"[SOFTWARE 2] Accepting multiple SMS sender devices on {config.SMS_SERVER_HOST}:{config.SMS_SERVER_PORT}...")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.handle_sender_device, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    SMSSoftwareNode().run()
