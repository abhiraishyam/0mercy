import json
import uuid
from datetime import datetime, timezone


def create_packet(msg_type: str, source: str, target: str, payload: dict) -> bytes:
    """Creates a newline-delimited JSON packet ready to send over Bluetooth/TCP."""
    packet = {
        "message_id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": msg_type,       # e.g., "sms_data", "sms_ack", "register_device", "routed_sms"
        "source": source,       # e.g., "software_2", "phone_A", "device_1"
        "target": target,       # e.g., "software_1", "all_targets", "device_1"
        "payload": payload,
    }
    return (json.dumps(packet) + "\n").encode("utf-8")


def parse_packet(raw_line: bytes) -> dict | None:
    """Safely decodes a single JSON line."""
    try:
        text = raw_line.decode("utf-8").strip()
        if not text:
            return None
        return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None