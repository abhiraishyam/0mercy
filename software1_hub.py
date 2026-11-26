import os
import json
import socket
import threading
from pathlib import Path
import config
from protocol import create_packet, parse_packet

class PendriveStorageManager:
    """Manages pendrive detection, safe atomic file writes, and SMS archiving."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.lock = threading.Lock()
        self._ensure_storage_ready()

    def _ensure_storage_ready(self) -> bool:
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            return os.access(self.base_path, os.W_OK)
        except OSError as e:
            print(f"[STORAGE ERROR] Pendrive not accessible at {self.base_path}: {e}")
            return False

    def save_sms_record(self, record: dict) -> bool:
        with self.lock:
            if not self._ensure_storage_ready():
                print("[STORAGE WARNING] Pendrive disconnected! Record not saved to USB.")
                return False

            # 1. Append to master log file
            log_file = self.base_path / "sms_master_log.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
                f.flush()
                os.fsync(f.fileno())

            # 2. Atomic individual file write (temp file -> rename prevents corruption if unplugged)
            msg_id = record.get("message_id", "unknown")
            temp_file = self.base_path / f".tmp_{msg_id}.json"
            final_file = self.base_path / f"sms_{msg_id}.json"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, final_file)

            print(f"[PENDRIVE] Saved SMS {msg_id} -> {final_file}")
            return True


class HubController:
    """Software 1: Connects to Software 2 (Bluetooth/TCP) and routes data to 2 Target Devices."""

    def __init__(self):
        self.storage = PendriveStorageManager(config.PENDRIVE_PATH)
        self.target_devices: dict[str, socket.socket] = {}
        self.targets_lock = threading.Lock()

    def register_target_device(self, device_name: str, conn: socket.socket):
        with self.targets_lock:
            self.target_devices[device_name] = conn
            print(f"[HUB] Target device connected: '{device_name}' (Total active: {len(self.target_devices)}/2)")

    def remove_target_device(self, device_name: str):
        with self.targets_lock:
            if device_name in self.target_devices:
                del self.target_devices[device_name]
                print(f"[HUB] Target device disconnected: '{device_name}'")

    def forward_to_target_devices(self, sms_packet: dict):
        """Forwards SMS data from Software 1 only to the recognized recipient phone number."""
        payload = sms_packet["payload"]
        recipient = str(payload.get("recipient_number", "")).strip()
        phone_dir = getattr(config, "PHONE_DIRECTORY", {})

        if phone_dir and recipient not in phone_dir:
            print(f"[HUB] Unrecognized recipient number: '{recipient}'. Message not routed.")
            return

        outbound = create_packet(
            msg_type="routed_sms",
            source="software_1_hub",
            target=recipient,
            payload=payload,
        )

        with self.targets_lock:
            conn = self.target_devices.get(recipient)
            if not conn:
                print(f"[HUB] Recipient '{recipient}' is not connected. Online: {list(self.target_devices.keys())}")
                return

            try:
                conn.sendall(outbound)
                label = phone_dir.get(recipient, recipient)
                print(f"[HUB -> {label} ({recipient})] Forwarded SMS ID {sms_packet['message_id']}")
            except OSError:
                del self.target_devices[recipient]
                print(f"[HUB] Failed to send to '{recipient}'; removed disconnected device.")
                
    def handle_software2_client(self, conn: socket.socket, addr):
        print(f"[HUB] Software 2 connected from {addr}")
        buffer = b""
        try:
            while True:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    packet = parse_packet(line)
                    if not packet:
                        continue

                    if packet.get("type") == "sms_data":
                        print(f"\n[HUB RECEIVED FROM SOFTWARE 2] {packet['payload']}")
                        # 1. Save to Pendrive
                        saved = self.storage.save_sms_record(packet)
                        # 2. Route to the 2 Target Devices
                        self.forward_to_target_devices(packet)
                        # 3. Send ACK back to Software 2
                        ack = create_packet(
                            msg_type="sms_ack",
                            source="software_1_hub",
                            target="software_2",
                            payload={"ack_id": packet["message_id"], "saved_to_pendrive": saved},
                        )
                        conn.sendall(ack)
        except OSError as e:
            print(f"[HUB] Software 2 connection error: {e}")
        finally:
            conn.close()
            print("[HUB] Software 2 disconnected.")

    def handle_target_device_client(self, conn: socket.socket, addr):
        device_name = f"device_{addr[1]}"
        buffer = b""
        try:
            while True:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    packet = parse_packet(line)
                    if not packet:
                        continue
                    if packet.get("type") == "register_device":
                        device_name = packet["payload"].get("device_name", device_name)
                        self.register_target_device(device_name, conn)
        except OSError:
            pass
        finally:
            self.remove_target_device(device_name)
            conn.close()

    def start_sms_listener(self):
        if config.TRANSPORT_MODE == "bluetooth":
            server = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            server.bind((config.HUB_BLUETOOTH_MAC, config.BLUETOOTH_CHANNEL))
            server.listen(1)
            print(f"[SOFTWARE 1] Listening for Software 2 via BLUETOOTH on channel {config.BLUETOOTH_CHANNEL}...")
        else:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((config.HUB_HOST, config.HUB_SMS_PORT))
            server.listen(5)
            print(f"[SOFTWARE 1] Listening for Software 2 via TCP on {config.HUB_HOST}:{config.HUB_SMS_PORT}...")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.handle_software2_client, args=(conn, addr), daemon=True).start()

    def start_target_devices_listener(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((config.HUB_HOST, config.HUB_TARGET_PORT))
        server.listen(5)
        print(f"[SOFTWARE 1] Listening for 2 Target Devices on {config.HUB_HOST}:{config.HUB_TARGET_PORT}...")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.handle_target_device_client, args=(conn, addr), daemon=True).start()

    def run(self):
        print("=== SOFTWARE 1: LAPTOP HOME SERVER HUB STARTED ===")
        print(f"Pendrive Storage Path: {config.PENDRIVE_PATH.resolve()}")
        threading.Thread(target=self.start_sms_listener, daemon=True).start()
        self.start_target_devices_listener()


if __name__ == "__main__":
    HubController().run()
