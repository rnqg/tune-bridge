# TuneBridge

CLI для переноса понравившихся треков из Яндекс Музыки в Apple Music, Spotify и YouTube Music.

## Что нужно заранее

- Python 3.11+
- токен Яндекс Музыки
- Для Apple Music: аккаунт Apple Developer, ключ MusicKit `.p8`, `Team ID`, `Key ID`, активная подписка Apple Music
- Для Spotify: Spotify Developer app, `Client ID`, `Client Secret`, redirect URI `http://127.0.0.1:8766/callback`
- Для YouTube Music: OAuth-данные Google для `ytmusicapi`

Без ключа MusicKit из Apple Developer полноценное добавление в медиатеку Apple Music не работает. Если пытаться обходить это через управление сайтом Apple Music, получится хрупкая автоматизация, а не нормальный мигратор.

Spotify использует официальный Web API. YouTube Music использует `ytmusicapi`, потому что у YouTube Music нет нормального публичного API для добавления треков в лайки или библиотеку.

## Установка

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[test]
```

`.env` больше не обязателен. Если нужного значения нет в переменных окружения или `.env`, TuneBridge спросит его в консоли при запуске команды.

Старое имя команды `ym-to-apple` оставлено как alias, но основная команда теперь:

```powershell
tune-bridge --help
```

## Авторизация Apple Music

```powershell
tune-bridge auth-apple
```

Команда поднимет локальную страницу, откроет браузер и сохранит пользовательский токен Apple Music в файл из `APPLE_MUSIC_USER_TOKEN_PATH`.

Если авторизация MusicKit не открывается, проверь настройки MusicKit key в Apple Developer и разрешенный origin для локального адреса `http://127.0.0.1:8765`.

## Авторизация Spotify

Создай приложение в Spotify Developer Dashboard и добавь redirect URI:

```text
http://127.0.0.1:8766/callback
```

Запусти авторизацию. Если `SPOTIFY_CLIENT_ID` и `SPOTIFY_CLIENT_SECRET` не заданы заранее, TuneBridge спросит их в консоли:

```powershell
tune-bridge auth-spotify
```

Токен сохранится в `SPOTIFY_TOKEN_PATH`.

## Авторизация YouTube Music

Запусти авторизацию. Если `YOUTUBE_MUSIC_CLIENT_ID` и `YOUTUBE_MUSIC_CLIENT_SECRET` не заданы заранее, TuneBridge спросит их в консоли:

```powershell
tune-bridge auth-youtube-music
```

Токен сохранится в `YOUTUBE_MUSIC_OAUTH_PATH`. При переносе в YouTube Music скрипт ставит трекам `LIKE`, то есть переносит их в лайкнутые треки.

## Проверка без записи

```powershell
tune-bridge dry-run
```

По умолчанию назначение `apple`. Для других сервисов:

```powershell
tune-bridge dry-run --destination spotify
tune-bridge dry-run --destination youtube-music
```

Для маленькой проверки:

```powershell
tune-bridge dry-run --destination spotify --limit 10
```

## Перенос в медиатеку

```powershell
tune-bridge transfer --yes
```

Для других сервисов:

```powershell
tune-bridge transfer --destination spotify --yes
tune-bridge transfer --destination youtube-music --yes
```

Скрипт добавляет только уверенные совпадения. Сомнительные и ненайденные треки попадают в отчеты.

## Отчеты

```powershell
tune-bridge report
tune-bridge report --destination spotify
tune-bridge report --destination youtube-music
```

Файлы создаются в `reports/`:

- `dry-run.json`
- `transfer.json`
- `unmatched.csv`
- `ambiguous.csv`
- `spotify-dry-run.json`
- `spotify-transfer.json`
- `youtube-music-dry-run.json`
- `youtube-music-transfer.json`

## Тесты

```powershell
python -m unittest discover -s tests
```
