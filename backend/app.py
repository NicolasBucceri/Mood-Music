import re
import os, time, requests
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import unicodedata

# --- ENV ---
load_dotenv(dotenv_path=Path(__file__).with_name('.env'))

CID = (os.getenv("SPOTIFY_CLIENT_ID") or "").strip()
SEC = (os.getenv("SPOTIFY_CLIENT_SECRET") or "").strip()
MARKET = (os.getenv("SPOTIFY_MARKET") or "AR").strip()

PORT = int(os.getenv("PORT", "5000"))

app = Flask(__name__)
CORS(app)

# ---------------- Spotify ----------------
_token = {"val": None, "exp": 0.0}

def spotify_token():
    """Obtiene y cachea el access_token de Spotify (Client Credentials)."""
    now = time.time()
    if _token["val"] and now < _token["exp"]:
        return _token["val"]

    if not CID or not SEC:
        raise RuntimeError("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET faltantes o vacíos")

    try:
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            auth=(CID, SEC),
            data={"grant_type": "client_credentials"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Fallo de red al pedir token a Spotify: {e}") from e

    if r.status_code != 200:
        try:
            body = r.json()
        except Exception:
            body = r.text
        raise RuntimeError(f"Spotify token error {r.status_code}: {body}")

    j = r.json()
    _token["val"] = j["access_token"]
    _token["exp"] = now + j.get("expires_in", 3600) - 60
    return _token["val"]

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/spotify/playlists")
def playlists():
    """Búsqueda de playlists públicas por texto (no requiere login del usuario)."""
    q = (request.args.get("query") or "").strip()
    limit = min(max(int(request.args.get("limit", "8")), 1), 20)

    if not q:
        return jsonify({"error": "query requerida"}), 400

    try:
        tok = spotify_token()
    except Exception as e:
        return jsonify({"error": "spotify_auth_failed", "message": str(e)}), 500

    try:
        r = requests.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {tok}"},
            params={"q": q, "type": "playlist", "limit": limit, "market": MARKET},
            timeout=15,
        )
        if r.status_code != 200:
            try:
                body = r.json()
            except Exception:
                body = r.text
            return jsonify({"error": "spotify_search_failed", "status": r.status_code, "body": body}), 400

        out = []
        for it in r.json().get("playlists", {}).get("items", []):
            out.append({
                "id": it.get("id"),
                "name": it.get("name"),
                "image": (it.get("images") or [{}])[0].get("url"),
                "url": (it.get("external_urls") or {}).get("spotify"),
                "owner": (it.get("owner") or {}).get("display_name"),
            })
        return {"items": out, "count": len(out)}
    except requests.RequestException as e:
        return jsonify({"error": "spotify_request_failed", "message": str(e)}), 500

@app.get("/api/spotify/playlist_covers")
def playlist_covers():
    """Devuelve la portada (URL) de 1..N playlists por id."""
    ids = (request.args.get("ids") or "").strip()
    if not ids:
        return jsonify({"error": "ids requeridos (comma-separated)"}), 400

    try:
        tok = spotify_token()
    except Exception as e:
        return jsonify({"error": "spotify_auth_failed", "message": str(e)}), 500

    out = {}
    for pid in [p.strip() for p in ids.split(",") if p.strip()]:
        try:
            r = requests.get(
                f"https://api.spotify.com/v1/playlists/{pid}/images",
                headers={"Authorization": f"Bearer {tok}"},
                timeout=12,
            )
            if r.status_code == 200 and isinstance(r.json(), list) and r.json():
                out[pid] = r.json()[0].get("url")
            else:
                out[pid] = None
        except requests.RequestException:
            out[pid] = None

    return {"covers": out}

# ---------------- Weather (Open-Meteo + Geocoding + Reverse) ----------------

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _norm_city_key(s: str) -> str:
    s = (s or "").strip().lower()
    return _strip_accents(s)

def _clean_city_suffix(q: str) -> str:
    """Quita sufijos tipo ', AR' o ', Argentina', dobles comas/espacios."""
    s = (q or "").strip()
    s = re.sub(r",\s*(ar|argentina)\s*$", "", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s)
    s = s.strip(" ,")
    return s

CITY_COORDS = {
    "buenos aires": (-34.6037, -58.3816),
    "buenos aires ar": (-34.6037, -58.3816),
    "buenos aires argentina": (-34.6037, -58.3816),
    "caba": (-34.6037, -58.3816),
    "caba ar": (-34.6037, -58.3816),
    "caba argentina": (-34.6037, -58.3816),
}

def _is_coords(q: str):
    q = (q or "").strip()
    m = q.split(",")
    if len(m) != 2:
        return None
    try:
        lat = float(m[0].strip())
        lon = float(m[1].strip())
    except ValueError:
        return None
    if lat < -90 or lat > 90 or lon < -180 or lon > 180:
        return None
    return lat, lon

def _geocode_open_meteo(q: str, lang="es"):
    q = (q or "").strip()

    # coords directas
    coords = _is_coords(q)
    if coords:
        return {"name": q, "latitude": coords[0], "longitude": coords[1], "country": None}

    q_clean = _clean_city_suffix(q)
    key_clean = _norm_city_key(q_clean)

    # match local (evita depender de la red)
    if key_clean in CITY_COORDS:
        lat, lon = CITY_COORDS[key_clean]
        return {"name": q_clean, "latitude": lat, "longitude": lon, "country": "Argentina", "admin1": "Buenos Aires"}

    # intento API externa (primero con q original, luego con q_clean)
    def _try(name):
        try:
            r = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": name, "count": 5, "language": lang, "format": "json"},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                results = data.get("results") or []
                if results:
                    ar = [x for x in results if (x.get("country") or "").lower() in ("argentina",)]
                    pick = ar[0] if ar else results[0]
                    return {
                        "name": pick.get("name") or name,
                        "latitude": pick.get("latitude"),
                        "longitude": pick.get("longitude"),
                        "country": pick.get("country"),
                        "admin1": pick.get("admin1"),
                    }
        except requests.RequestException:
            pass
        return None

    geo = _try(q) or _try(q_clean)
    if geo:
        return geo

    # último intento: key cruda al diccionario
    key_raw = _norm_city_key(q)
    if key_raw in CITY_COORDS:
        lat, lon = CITY_COORDS[key_raw]
        return {"name": q, "latitude": lat, "longitude": lon, "country": "Argentina", "admin1": "Buenos Aires"}

    return None

def _reverse_geocode(lat: float, lon: float, lang="es"):
    """Usa el reverse geocoding de Open-Meteo para nombrar el lugar."""
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/reverse",
            params={"latitude": lat, "longitude": lon, "language": lang},
            timeout=15,
        )
        if r.status_code == 200:
            res = (r.json().get("results") or [])
            if res:
                pick = res[0]
                name = pick.get("name")
                admin1 = pick.get("admin1")
                country = pick.get("country")
                label = ", ".join([x for x in [name, admin1, country] if x])
                return label or f"{lat},{lon}"
    except requests.RequestException:
        pass
    return f"{lat},{lon}"

def _map_weathercode(code: int, is_day: bool):
    W = {
        0: ("Despejado", "Clear"),
        1: ("Mayormente despejado", "Clear"),
        2: ("Parcialmente nublado", "Clouds"),
        3: ("Nublado", "Clouds"),
        45: ("Niebla", "Mist"),
        48: ("Niebla helada", "Mist"),
        51: ("Llovizna ligera", "Drizzle"),
        53: ("Llovizna", "Drizzle"),
        55: ("Llovizna intensa", "Drizzle"),
        56: ("Llovizna helada ligera", "Drizzle"),
        57: ("Llovizna helada intensa", "Drizzle"),
        61: ("Lluvia ligera", "Rain"),
        63: ("Lluvia", "Rain"),
        65: ("Lluvia intensa", "Rain"),
        66: ("Lluvia helada ligera", "Rain"),
        67: ("Lluvia helada intensa", "Rain"),
        71: ("Nieve ligera", "Snow"),
        73: ("Nieve", "Snow"),
        75: ("Nieve intensa", "Snow"),
        77: ("Granos de nieve", "Snow"),
        80: ("Chubascos ligeros", "Rain"),
        81: ("Chubascos", "Rain"),
        82: ("Chubascos intensos", "Rain"),
        85: ("Chubascos de nieve", "Snow"),
        86: ("Chubascos de nieve fuertes", "Snow"),
        95: ("Tormenta", "Thunderstorm"),
        96: ("Tormenta con granizo", "Thunderstorm"),
        99: ("Tormenta fuerte con granizo", "Thunderstorm"),
    }
    text, main = W.get(int(code or 0), ("Despejado", "Clear"))
    emoji_map = {
        "Clear": "☀️" if is_day else "🌙",
        "Clouds": "☁️",
        "Rain": "🌧️",
        "Drizzle": "🌦️",
        "Thunderstorm": "⛈️",
        "Snow": "❄️",
        "Mist": "🌫️",
    }
    return text, main, emoji_map.get(main, "🎵")

def _current_payload(lat: float, lon: float, city_label: str, lang="es"):
    """
    Pedimos datos con timezone=auto + timeformat=unixtime.
    Open-Meteo devuelve:
      - current_weather.time en *unixtime local*
      - utc_offset_seconds (segundos de diferencia local vs UTC)
      - timezone (IANA, ej: "America/Buenos_Aires")
    Convertimos a UTC: dt_utc = local_unixtime - utc_offset_seconds
    """
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
                "daily": "sunrise,sunset",
                "timezone": "auto",
                "timeformat": "unixtime",
            },
            timeout=15,
        )
    except requests.RequestException as e:
        return None, {"error": "meteo_network_error", "message": str(e)}

    if r.status_code != 200:
        return None, {"error": "meteo_error", "status": r.status_code, "body": r.text}

    J = r.json() or {}
    cw = J.get("current_weather") or {}
    daily = J.get("daily") or {}
    utc_off = int(J.get("utc_offset_seconds") or 0)
    tz_name = J.get("timezone")  # IANA

    # current
    try:
        temp_c = round(float(cw.get("temperature")))
    except Exception:
        temp_c = None

    code = int(cw.get("weathercode", 0) or 0)
    is_day = bool(cw.get("is_day", 1))
    text, main, emoji = _map_weathercode(code, is_day)

    # dt (UTC): current_weather.time viene como unixtime local -> pasamos a UTC
    dt_local = int(cw.get("time") or 0)
    dt_utc = dt_local - utc_off if dt_local else None

    # sunrise/sunset (primer elemento del día) también vienen como unixtime local
    sunrise_utc = None
    sunset_utc = None
    try:
        if isinstance(daily.get("sunrise"), list) and daily["sunrise"]:
            sunrise_utc = int(daily["sunrise"][0]) - utc_off
        if isinstance(daily.get("sunset"), list) and daily["sunset"]:
            sunset_utc = int(daily["sunset"][0]) - utc_off
    except Exception:
        pass

    payload = {
        "city": city_label,
        "lat": lat,
        "lon": lon,
        "temp": temp_c,               # °C reales
        "weather": text,              # etiqueta ES
        "main": main,                 # categoría EN
        "emoji": emoji,
        "icon": "",
        "dt": dt_utc,                 # epoch UTC (CORRECTO)
        "tz_offset_sec": utc_off,     # offset local vs UTC (segundos)
        "timezone": tz_name,          # IANA (usar en el front para formatear)
        "sunrise": sunrise_utc,       # epoch UTC
        "sunset": sunset_utc,         # epoch UTC
    }
    return payload, None

@app.get("/api/weather")
def weather_by_city():
    raw_city = (request.args.get("city") or "Buenos Aires").strip()
    lang = (request.args.get("lang") or "es").strip()
    geo = _geocode_open_meteo(raw_city, lang=lang)
    if not geo:
        return jsonify({"error": "geo_failed", "message": f"No se pudo geocodificar '{raw_city}'"}), 400
    label = f'{geo.get("name") or raw_city}{", " + (geo.get("country") or "") if geo.get("country") else ""}'
    payload, err = _current_payload(geo["latitude"], geo["longitude"], label, lang=lang)
    if err:
        return jsonify(err), 400
    return jsonify(payload)

@app.get("/api/weather/geo")
def weather_by_geo():
    """Clima por coordenadas precisas (lat,lon)."""
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
    except ValueError:
        return jsonify({"error": "bad_params", "message": "lat/lon inválidos"}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"error": "bad_params", "message": "lat/lon fuera de rango"}), 400

    lang = (request.args.get("lang") or "es").strip()
    label = _reverse_geocode(lat, lon, lang=lang)
    payload, err = _current_payload(lat, lon, label, lang=lang)
    if err:
        return jsonify(err), 400
    return jsonify(payload)

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
