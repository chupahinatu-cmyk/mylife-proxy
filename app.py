"""
MyLife — FatSecret OAuth 2.0 Proxy
Деплоится на Render.com как Web Service (Python).
Хранит Client ID/Secret, получает Bearer токен и пересылает запросы к FatSecret.
"""

import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ── Credentials (задаются через Environment Variables на Render) ──
CLIENT_ID     = os.environ.get("FATSECRET_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("FATSECRET_CLIENT_SECRET", "")

TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
API_URL   = "https://platform.fatsecret.com/rest/server.api"

# ── Кэш токена (живёт 23 часа, FatSecret выдаёт на 24) ──────────
_token: str = ""
_token_expires: float = 0.0


def get_token() -> str:
    global _token, _token_expires
    if _token and time.time() < _token_expires:
        return _token
    resp = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials", "scope": "basic"},
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token = data["access_token"]
    _token_expires = time.time() + data.get("expires_in", 86400) - 3600
    return _token


# ── Единственный endpoint — /api ─────────────────────────────────
# iPhone отправляет: GET /api?method=foods.search&search_expression=chicken&...
# Прокси добавляет Bearer токен и пересылает в FatSecret.

@app.route("/api", methods=["GET"])
def proxy():
    try:
        token = get_token()
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    # Берём все query-параметры от клиента, добавляем format=json
    params = dict(request.args)
    params.setdefault("format", "json")

    try:
        fs_resp = requests.get(
            API_URL,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        return (fs_resp.content, fs_resp.status_code,
                {"Content-Type": "application/json"})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


# ── Health-check — Render проверяет что сервис живой ─────────────
@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
