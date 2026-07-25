#!/usr/bin/env python3
"""Server locale per pilotare l'estrazione da interfaccia web e modificare il JSON.

Avvio:  python serve.py   ->   http://127.0.0.1:8000
Solo libreria standard. Fa da ponte tra index.html ed extract.py:
  POST /extract  {opzioni}  -> esegue l'estrazione, scrive istituti.json, ritorna i record
  POST /save     [record]   -> riscrive istituti.json con le modifiche della tabella
  GET  /istituti.json       -> l'ultimo JSON generato
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import extract

HERE = Path(__file__).parent
OUTPUT = HERE / "istituti.json"
CACHE = HERE / "geocache.json"
PORT = 8000
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}  # difesa DNS rebinding / CSRF cross-origin


def _write(records: list) -> None:
    OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=1))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body, ctype: str = "application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _origin_ok(self) -> bool:
        # blocca Host non locali (DNS rebinding) e POST cross-origin (CSRF)
        if self.headers.get("Host", "").split(":")[0] not in ALLOWED_HOSTS:
            return False
        origin = self.headers.get("Origin")
        return not origin or urlparse(origin).hostname in ALLOWED_HOSTS

    def do_GET(self):
        if not self._origin_ok():
            self._send(403, {"error": "forbidden"})
            return
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path.startswith("/istituti.json"):
            self._send(200, OUTPUT.read_bytes() if OUTPUT.exists() else b"[]")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._origin_ok():
            self._send(403, {"error": "forbidden"})
            return
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"null")
        try:
            if self.path == "/extract":
                records = extract.build({
                    "statali": payload.get("statali", True),
                    "paritarie": payload.get("paritarie", True),
                    "regione": payload.get("regione") or None,
                    "provincia": payload.get("provincia") or None,
                    "livello": payload.get("livello") or None,
                    "grado": payload.get("grado") or None,
                    "geocode": payload.get("geocode", False),
                    "cache": str(CACHE),
                })
                _write(records)
                self._send(200, {"count": len(records), "records": records})
            elif self.path == "/save":
                _write(payload)
                self._send(200, {"ok": True, "count": len(payload)})
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:  # errori di rete/catalogo mostrati nella UI
            self._send(500, {"error": str(exc)})

    def log_message(self, *args):  # silenzia il log di default per richiesta
        pass


def main():
    print(f"istituti-scraper -> http://127.0.0.1:{PORT}  (Ctrl+C per fermare)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
