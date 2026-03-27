#!/usr/bin/env python3
"""
Servidor local — serve dashboards + dispara scrapers via browser.
Uso: python3 server.py
Acesso: http://localhost:8080
"""
import subprocess, sys, os, json, time, threading, re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, SimpleHTTPRequestHandler

BASE = Path(__file__).parent
PORT = 8080

# Estado dos scrapers em execução
scraper_state = {}  # nicho -> {"status": "running"|"done"|"error", "log": [...]}
scraper_lock  = threading.Lock()

SCRAPERS = {
    "restaurantes": {
        "label": "Restaurantes",
        "script": "scraper_restaurantes.py",
        "dashboard_script": "generate_dashboard_restaurantes.py",
        "dashboard": "restaurantes.html",
        "excel": "Restaurantes Zona Oeste.xlsx",
    },
    "surf": {
        "label": "Escolas de Surf",
        "script": "scraper_instagram.py",
        "dashboard_script": "generate_dashboard.py",
        "dashboard": "dashboard.html",
        "excel": "Surf School Peniche Enriched.xlsx",
    },
}

PYTHON = sys.executable  # mesmo python que está a correr o server

# Garante directório para scrapes customizados
(BASE / "data").mkdir(exist_ok=True)

def run_scraper(nicho):
    cfg = SCRAPERS.get(nicho)
    if not cfg:
        return
    with scraper_lock:
        scraper_state[nicho] = {"status": "running", "log": []}

    def append_log(line):
        with scraper_lock:
            scraper_state[nicho]["log"].append(line)

    try:
        script = str(BASE / cfg["script"])
        append_log(f"▶ A correr {cfg['label']} scraper...")
        proc = subprocess.Popen(
            [PYTHON, script] + cfg.get("script_args", []),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=str(BASE)
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line and not line.startswith("\x1b"):  # skip ANSI
                append_log(line)
        proc.wait()
        if proc.returncode != 0:
            raise Exception(f"Script saiu com código {proc.returncode}")

        # Regenerar dashboard
        append_log(f"✅ Dados recolhidos. A gerar dashboard...")
        dash_script = str(BASE / cfg["dashboard_script"])
        r2 = subprocess.run(
            [PYTHON, dash_script] + cfg.get("dashboard_script_args", []),
            capture_output=True, text=True, cwd=str(BASE)
        )
        if r2.returncode != 0:
            append_log(f"Aviso dashboard: {r2.stderr[:200]}")
        else:
            append_log(r2.stdout.strip())

        # Regenerar index
        idx = str(BASE / "generate_index.py")
        subprocess.run([PYTHON, idx], cwd=str(BASE))
        append_log(f"🎉 Concluído! Abre /{cfg['dashboard']}")

        with scraper_lock:
            scraper_state[nicho]["status"] = "done"
    except Exception as ex:
        append_log(f"❌ Erro: {ex}")
        with scraper_lock:
            scraper_state[nicho]["status"] = "error"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(BASE), **kw)

    def log_message(self, fmt, *args):
        pass  # silencioso

    def do_GET(self):
        # POST via GET com ?action=
        if self.path.startswith("/api/scrape/"):
            nicho = self.path.split("/api/scrape/")[1].split("?")[0]
            self._handle_scrape(nicho)
        elif self.path.startswith("/api/status/"):
            nicho = self.path.split("/api/status/")[1].split("?")[0]
            self._handle_status(nicho)
        elif self.path == "/api/scrapers":
            self._handle_scrapers_list()
        else:
            super().do_GET()

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_scrape(self, nicho):
        # Scrape customizado: /api/scrape/custom?city=X&niche=Y
        if nicho == "custom":
            params = parse_qs(urlparse(self.path).query)
            city  = params.get("city",  [""])[0].strip()
            niche = params.get("niche", [""])[0].strip()
            if not city or not niche:
                self._send_json({"error": "city and niche are required"}, 400)
                return
            key = re.sub(r"[^a-z0-9]", "_", f"{niche}_{city}".lower())[:40]
            excel_path = str(BASE / "data" / f"{key}.xlsx")
            dash_path  = str(BASE / f"leads_{key}.html")
            SCRAPERS[key] = {
                "label": f"{niche} — {city}",
                "script": "scraper_restaurantes.py",
                "script_args": ["--city", city, "--niche", niche, "--output", excel_path],
                "dashboard_script": "generate_dashboard_restaurantes.py",
                "dashboard_script_args": ["--excel", excel_path, "--output", dash_path],
                "dashboard": f"leads_{key}.html",
                "excel": f"data/{key}.xlsx",
            }
            nicho = key

        if nicho not in SCRAPERS:
            self._send_json({"error": "nicho desconhecido"}, 404)
            return
        with scraper_lock:
            state = scraper_state.get(nicho, {})
        if state.get("status") == "running":
            self._send_json({"status": "already_running"})
            return
        t = threading.Thread(target=run_scraper, args=(nicho,), daemon=True)
        t.start()
        self._send_json({"status": "started", "nicho": nicho, "dashboard": SCRAPERS[nicho]["dashboard"]})

    def _handle_status(self, nicho):
        with scraper_lock:
            state = dict(scraper_state.get(nicho, {"status": "idle", "log": []}))
        self._send_json(state)

    def _handle_scrapers_list(self):
        result = {}
        for k, v in SCRAPERS.items():
            with scraper_lock:
                st = scraper_state.get(k, {}).get("status", "idle")
            excel_path = BASE / v["excel"]
            result[k] = {
                "label": v["label"],
                "status": st,
                "has_data": excel_path.exists(),
                "dashboard": v["dashboard"],
            }
        self._send_json(result)


if __name__ == "__main__":
    os.chdir(str(BASE))
    httpd = HTTPServer(("", PORT), Handler)
    print(f"✅ Servidor em http://localhost:{PORT}")
    print(f"   Dashboard principal: http://localhost:{PORT}/index.html")
    print(f"   Ctrl+C para parar\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor parado.")
