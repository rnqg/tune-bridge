from __future__ import annotations

import html
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer

from .apple import generate_developer_token
from .config import AppConfig


class AuthServerError(RuntimeError):
    pass


class _TokenServer(TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_cls: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(server_address, handler_cls)
        self.saved_token: str | None = None
        self.error: str | None = None


def run_apple_auth(config: AppConfig, port: int = 8765, open_browser: bool = True) -> str:
    team_id, key_id, private_key_path = config.require_apple_signing()
    developer_token = generate_developer_token(team_id, key_id, private_key_path)
    output_path = config.apple_music_user_token_path
    html_page = _render_html(developer_token)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            if self.path not in ("/", "/index.html"):
                self.send_error(404)
                return
            body = html_page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/token":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(body)
                token = str(payload["token"]).strip()
                if not token:
                    raise ValueError("пустой токен")
                output_path.write_text(token + "\n", encoding="utf-8")
                self.server.saved_token = token
                self._json_response({"ok": True, "path": str(output_path)})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            except Exception as exc:
                self.server.error = str(exc)
                self._json_response({"ok": False, "error": str(exc)}, status=400)

        def _json_response(self, payload: dict[str, object], status: int = 200) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    with _TokenServer(("127.0.0.1", port), Handler) as server:
        url = f"http://127.0.0.1:{port}/"
        if open_browser:
            webbrowser.open(url)
        print(f"Открой {url} и авторизуй Apple Music")
        server.serve_forever()
        if server.saved_token:
            return str(output_path)
        raise AuthServerError(server.error or "Токен Apple Music не был сохранен")


def _render_html(developer_token: str) -> str:
    token_literal = json.dumps(developer_token)
    title = html.escape("TuneBridge")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://js-cdn.music.apple.com/musickit/v1/musickit.js"></script>
<style>
body {{
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #111;
  background: #f5f5f7;
}}
main {{
  width: min(480px, calc(100vw - 32px));
  padding: 28px;
  background: white;
  border: 1px solid #dedee3;
  border-radius: 8px;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.08);
}}
button {{
  width: 100%;
  min-height: 44px;
  border: 0;
  border-radius: 6px;
  background: #111;
  color: white;
  font: inherit;
  cursor: pointer;
}}
p {{
  line-height: 1.5;
}}
#status {{
  min-height: 24px;
}}
</style>
</head>
<body>
<main>
<h1>Авторизация Apple Music</h1>
<p>Разреши TuneBridge получить Music User Token для переноса треков.</p>
<button id="authorize">Авторизоваться</button>
<p id="status"></p>
</main>
<script>
const developerToken = {token_literal};
const statusNode = document.getElementById("status");
const button = document.getElementById("authorize");

document.addEventListener("musickitloaded", async () => {{
  try {{
    await MusicKit.configure({{
      developerToken,
      app: {{
        name: "TuneBridge",
        build: "0.1.0"
      }}
    }});
    statusNode.textContent = "Готово к авторизации.";
  }} catch (error) {{
    statusNode.textContent = `Не удалось настроить MusicKit: ${{error.message || error}}`;
  }}
}});

button.addEventListener("click", async () => {{
  button.disabled = true;
  statusNode.textContent = "Ждем авторизацию Apple...";
  try {{
    const music = MusicKit.getInstance();
    const token = await music.authorize();
    const response = await fetch("/token", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{token}})
    }});
    if (!response.ok) {{
      throw new Error(await response.text());
    }}
    statusNode.textContent = "Токен сохранен. Эту вкладку можно закрыть.";
  }} catch (error) {{
    button.disabled = false;
    statusNode.textContent = `Авторизация не удалась: ${{error.message || error}}`;
  }}
}});
</script>
</body>
</html>"""
