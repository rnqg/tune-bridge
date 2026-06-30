from __future__ import annotations

import html
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler
from socketserver import TCPServer
from urllib.parse import parse_qs, urlencode, urlparse

from .config import AppConfig, ConfigError
from .spotify import exchange_spotify_code, save_spotify_token


class SpotifyAuthError(RuntimeError):
    pass


class _SpotifyTokenServer(TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_cls: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(server_address, handler_cls)
        self.saved = False
        self.error: str | None = None


def run_spotify_auth(config: AppConfig, open_browser: bool = True) -> str:
    client_id, client_secret = config.require_spotify_app()
    redirect = urlparse(config.spotify_redirect_uri)
    if redirect.scheme != "http":
        raise ConfigError("SPOTIFY_REDIRECT_URI должен использовать http для локального сервера авторизации")
    if redirect.hostname not in {"127.0.0.1", "localhost"}:
        raise ConfigError("Хост в SPOTIFY_REDIRECT_URI должен быть 127.0.0.1 или localhost")
    if not redirect.port:
        raise ConfigError("В SPOTIFY_REDIRECT_URI должен быть указан порт")

    state = secrets.token_urlsafe(24)
    callback_path = redirect.path or "/callback"
    authorize_url = _authorize_url(client_id, config.spotify_redirect_uri, state)
    success_page = _render_page("Авторизация Spotify сохранена", "Токен сохранен. Эту вкладку можно закрыть.")
    error_page = _render_page("Авторизация Spotify не удалась", "Вернись в терминал и посмотри текст ошибки.")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != callback_path:
                self.send_error(404)
                return
            query = parse_qs(parsed.query)
            if query.get("state", [""])[0] != state:
                self.server.error = "Не совпал параметр state в Spotify OAuth"
                self._html(error_page, status=400)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            error = query.get("error", [""])[0]
            if error:
                self.server.error = f"Ошибка Spotify OAuth: {error}"
                self._html(error_page, status=400)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            code = query.get("code", [""])[0]
            if not code:
                self.server.error = "В ответе Spotify OAuth нет code"
                self._html(error_page, status=400)
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            try:
                payload = exchange_spotify_code(client_id, client_secret, code, config.spotify_redirect_uri)
                save_spotify_token(config.spotify_token_path, payload)
                self.server.saved = True
                self._html(success_page)
            except Exception as exc:
                self.server.error = str(exc)
                self._html(error_page, status=500)
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def _html(self, body: str, status: int = 200) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    host = "127.0.0.1" if redirect.hostname == "localhost" else redirect.hostname
    with _SpotifyTokenServer((host, redirect.port), Handler) as server:
        if open_browser:
            webbrowser.open(authorize_url)
        print(f"Открой {authorize_url} и авторизуй Spotify")
        server.serve_forever()
        if server.saved:
            return str(config.spotify_token_path)
        raise SpotifyAuthError(server.error or "Токен Spotify не был сохранен")


def _authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "user-library-modify",
        "state": state,
    }
    return "https://accounts.spotify.com/authorize?" + urlencode(params)


def _render_page(title: str, message: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
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
p {{
  line-height: 1.5;
}}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p>{html.escape(message)}</p>
</main>
</body>
</html>"""
