"""
spatialble_ota_server - HTTP server to receive OTA updates for spatialble_server.py
"""

import json
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from spatialble_config import OTA_PORT, OTA_UPLOAD_PATH, OTA_RESTART_CMD


class OTAHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/upload":
            self._respond(404, {"success": False, "message": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            with open(OTA_UPLOAD_PATH, "wb") as f:
                f.write(body)

            result = subprocess.run(OTA_RESTART_CMD, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self._respond(200, {"success": True, "message": "Updated and restarted"})
            else:
                self._respond(500, {"success": False, "message": result.stderr.strip()})
        except subprocess.TimeoutExpired:
            self._respond(500, {"success": False, "message": "Restart timed out"})
        except Exception as e:
            self._respond(500, {"success": False, "message": str(e)})

    def _respond(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[OTA] {args[0]} {args[1]} {args[2]}\n")


def main():
    server = HTTPServer(("0.0.0.0", OTA_PORT), OTAHandler)
    print(f"OTA server listening on 0.0.0.0:{OTA_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.server_close()


if __name__ == "__main__":
    main()
