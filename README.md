# Home Server SMS Hub

A lightweight, pure-Python home server and local SMS relay system that routes messages between recognized phone numbers, queues traffic across a hub-and-relay architecture, and archives every message to local or USB pendrive storage.

## Features

* **Two-Way Phone Number Messaging:** Endpoints register with recognized phone numbers (e.g., `9000000001`, `9000000002`) and can send and receive messages simultaneously.
* **Hub & Relay Architecture:** Separates message intake and queuing (`software2_sms.py`) from central routing and storage (`software1_hub.py`), with automatic hub reconnection and delivery acknowledgments (ACKs).
* **Crash-Safe Storage Archiving:** Writes every SMS to a master log (`sms_master_log.jsonl`) and saves individual JSON records (`sms_<message_id>.json`) using atomic temp-file writes to prevent corruption if a USB pendrive is unplugged.
* **Flexible Transport:** Runs locally over TCP sockets for easy testing, with built-in configuration support for Bluetooth RFCOMM between the relay and hub.
* **Zero External Dependencies:** Built entirely with Python 3 standard library modules (`socket`, `threading`, `json`, `queue`, `pathlib`, `os`).

## Project Structure

* `config.py` — Shared settings for transport mode (`tcp`/`bluetooth`), hosts/ports (`5001`, `5002`, `6001`), storage path (`PENDRIVE_PATH`), and recognized numbers (`PHONE_DIRECTORY`).
* `protocol.py` — JSON newline-delimited packet creation and parsing helpers.
* `software1_hub.py` — Central hub server that routes incoming SMS to the target phone number and saves records to disk/pendrive.
* `software2_sms.py` — Multi-device SMS relay that accepts outgoing messages, queues them for the hub, and provides a hook for real GSM/ADB SMS dispatch.
* `phone_endpoint.py` — Combined two-way client for sending and receiving SMS under a single phone number.
* `target_device.py` & `sms_sender_client.py` — Standalone receive-only and send-only clients for modular testing.

## Getting Started

### Prerequisites
* Python 3.10+

### Configuration
Open `config.py` and verify:
1. `PENDRIVE_PATH` points to an existing local folder or USB drive path.
2. `PHONE_DIRECTORY` lists the phone numbers you want the hub to recognize.

### Running the System
Open 4 separate terminals inside the `home_server_sms_hub` folder and start each component in order:
1.software1_hub.py
2.software2_sms.py
3.phone_endpoint.py - phone_A naming- 9000000001 and phone_B naming- 9000000002


1. **Start the Central Hub:**
   ```bash
   python software1_hub.py
