Here’s a complete README for your project based on everything we’ve discussed and implemented so far:

---

# Proctoring Client-Server Monitoring System

A lightweight Python-based **client-server monitoring system** designed for **proctored exam environments**. It captures **keystrokes**, **webcam video**, and **screen share** from the client machine and streams them to the server in real-time. All communication is **encrypted** using RSA + Fernet symmetric encryption.

The system also includes a **richly-decorated PyInstaller build script** to generate a standalone client executable.

---

## Features

### Client-Side

* **Keystroke Logging**

  * Captures normal and special keys (e.g., `Ctrl`, `Backspace`, `Space`) accurately.
* **Webcam Capture**

  * Streams webcam video to the server.
  * Optional live preview window.
  * Encoded to MJPEG and saved to MP4.
* **Screen Sharing**

  * Captures full-screen video using `mss`.
  * Streams screen frames to server.
  * Optional preview window.
  * Lower FPS for lightweight bandwidth usage.
* **Encrypted Communication**

  * RSA used to exchange a session key.
  * Fernet used for symmetric encryption of all data packets.
* **Multi-threaded**

  * Separate threads for keystrokes, webcam, and screen share for smooth operation.

### Server-Side

* **Live Data Display**

  * Rich live display for keystrokes, webcam feed, and screen share.
  * Tables for keystrokes with timestamps.
  * Separate live panels for webcam and screen share.
* **Recording**

  * Saves webcam and screen share as separate MP4 files.
* **Encrypted Reception**

  * Decrypts client data in real-time.

### Build Script

* **Rich-Powered Live Build Display**

  * Shows console output in a live panel during PyInstaller compilation.
  * Success or failure displayed in colored panels.
* **Custom Output**

  * Optional output file name.
  * Optional logo/icon for executable.
* **Cross-Platform Build**

  * Linux and Windows builds supported.

---

## Requirements

* Python 3.10+
* Packages:

  ```bash
  pip install pynput cryptography rich opencv-python numpy mss pyinstaller
  ```
* Optional for Windows builds: Wine (if building on Linux for Windows).

---

## Usage

### Server

```bash
python server.py --host 0.0.0.0 --port 5555 --out webcam.mp4 --no-preview
```

* `--host` – IP to bind server.
* `--port` – Port to listen on.
* `--out` – MP4 filename for webcam recording.
* `--no-preview` – Disable live preview windows.

### Client

* Modify `client.py` to set host and port of the server.
* Run directly (Python) or build using PyInstaller:

```bash
python client.py
```

### Build Executable

```bash
python build.py --client client.py --output myclient --logo icon.ico
```

* `--client` – Python client file to build.
* `--output` – Executable name.
* `--logo` – Optional icon/logo file for executable.

---

## Architecture

```
Client                          Server
-------                         -------
Keystroke Thread  ----\
Webcam Thread      ----> Encrypted Packets ---> Live Display / MP4
Screen Share Thread ----/
```

* **Encrypted Packets**

  * Packet Types:

    * `TYPE_TEXT` – Keystrokes
    * `TYPE_VIDEO` – Webcam video
    * `TYPE_SCREEN` – Screen share

* **Threading**

  * Each client module runs in its own thread.
  * Server maintains queues for each type of data.
  * Workers read from queues and update Rich live panels + save files.

---

## Notes

* Intended for **proctored environments**; respect privacy laws.
* Low bandwidth options included:

  * Webcam: adjustable FPS and quality.
  * Screen: reduced FPS and resolution for live monitoring.

---

## Screenshots / Examples

* **Live Keystrokes Table** – Displays timestamped keystrokes.
* **Webcam Preview Window** – Optional preview of incoming webcam feed.
* **Screen Share Preview** – Optional live screen share window.
* **Rich Build Panels** – Live feedback while building client executable.

---

## License

Open source for educational or monitoring purposes. Use responsibly.

---

I can also make a **super concise version for GitHub**, with badges and minimal text for README.md if you want.

Do you want me to do that too?
