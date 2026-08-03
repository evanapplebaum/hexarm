"""Headless MJPEG-over-HTTP preview for one or more UVC cameras.

Usage:
    conda activate lerobot
    python software/vision/camera_preview.py --indices 0 2
    # then open http://<jetson-ip>:8080 in a browser on the laptop

Purely a positioning/framing aid — not part of the LeRobot camera config.
"""

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

BOUNDARY = "frame"


class Camera:
    def __init__(self, index, width, height):
        self.index = index
        self.cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.lock = threading.Lock()
        self.jpeg = None
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            ok, frame = self.cap.read()
            if ok:
                ok, buf = cv2.imencode(".jpg", frame)
                if ok:
                    with self.lock:
                        self.jpeg = buf.tobytes()
            else:
                time.sleep(0.1)

    def get_jpeg(self):
        with self.lock:
            return self.jpeg


def make_handler(cameras):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep stdout clean

        def do_GET(self):
            if self.path == "/":
                links = "".join(f'<p><a href="/video{i}">/dev/video{i}</a></p>' for i in cameras)
                body = f"<html><body>{links}</body></html>".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path.startswith("/video"):
                index = int(self.path.removeprefix("/video"))
                cam = cameras.get(index)
                if cam is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
                self.end_headers()
                try:
                    while True:
                        jpeg = cam.get_jpeg()
                        if jpeg is not None:
                            self.wfile.write(f"--{BOUNDARY}\r\n".encode())
                            self.wfile.write(b"Content-Type: image/jpeg\r\n")
                            self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                            self.wfile.write(jpeg)
                            self.wfile.write(b"\r\n")
                        time.sleep(1 / 30)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return

            self.send_error(404)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--indices", type=int, nargs="+", default=[0, 2])
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    cameras = {i: Camera(i, args.width, args.height) for i in args.indices}
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(cameras))
    print(f"Serving on http://0.0.0.0:{args.port}  (index page lists each /videoN feed)")
    server.serve_forever()


if __name__ == "__main__":
    main()
