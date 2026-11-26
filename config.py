import os
from pathlib import Path

# Transport Mode:
# "tcp" -> Test all software locally in VS Code terminals over localhost
# "bluetooth" -> Real Bluetooth RFCOMM connection between Software 2 and Software 1
TRANSPORT_MODE = "tcp"

# --- Bluetooth Settings (Used when TRANSPORT_MODE = "bluetooth") ---
# Replace with your Laptop's Bluetooth MAC address (run `getmac` or `ipconfig /all` on Windows, `hciconfig` on Linux)
HUB_BLUETOOTH_MAC = "00:11:22:33:44:55"
BLUETOOTH_CHANNEL = 4

# --- TCP Settings (Used when TRANSPORT_MODE = "tcp" & for Target Devices) ---
HUB_HOST = "127.0.0.1"
HUB_SMS_PORT = 5001       # Software 2 connects here
HUB_TARGET_PORT = 5002    # The 2 other devices connect here

# Software 2 local API port (Multiple devices connect here to submit SMS)
SMS_SERVER_HOST = "127.0.0.1"
SMS_SERVER_PORT = 6001

# --- Pendrive Storage Settings ---
# Change this to your actual pendrive path (e.g., "E:/" on Windows or "/media/user/USB" on Linux).
# Defaults to a local folder named 'pendrive_storage' for safe immediate testing.
PENDRIVE_PATH = Path(r"C:\sms_hub_storage")

# --- Recognized Phone Numbers ---
PHONE_DIRECTORY = {
    "9000000001": "Phone_A",
    "9000000002": "Phone_B",
}