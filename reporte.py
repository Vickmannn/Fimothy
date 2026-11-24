import datetime
import os
import re
import time
import unicodedata
import matplotlib
import numpy as np
import requests
from fpdf import FPDF

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ==============================================================================
# 1. VARIABLES DE ENTORNO (GITHUB SECRETS - FUENTES DE MERCADO Y TELEGRAM)
# ==============================================================================
ALPHAVANTAGE_API_KEY = os.environ.get("AlphaVantage_API_Key")
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
MARKETSTACK_KEY = os.environ.get("MARKETSTACK_API_KEY")
MASSIVE_KEY = os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_API_KEY") or os.environ.get("TWELVEDATA_API_KEY")
FMP_API_KEY = os.environ.get("FMP_API_KEY")
MARKETAUX_KEY = os.environ.get("MARKETAUX_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
NEWSDATA_KEY = os.environ.get("NEWSDATA_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ==============================================================================
# 2. DEFINICION DE INDICES Y HORIZONTES MULTITEMPORALES (100% DINAMICO)
# ==============================================================================
INDICES_CABECERA = [
    ("QQQ", "NASDAQ 100 / COMPOSITE PROXY"),
    ("SPY", "S&P 500 INDEX PROXY"),
    ("IWM", "RUSSELL 2000 SMALL CAP PROXY"),
]

PLAZOS_EVOLUTIVOS = [
    ("1D", 1),
    ("2D", 2),
    ("3D", 3),
    ("1Sem", 5),
    ("2Sem", 10),
    ("1Mes", 21),
    ("3Meses", 63),
    ("6Meses", 126),
    ("252D", 252),
]

UMBRAL_SMALL_MID_CAP = 10e9


def limpiar_texto_pdf(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)
    texto = re.sub(r"__(.*?)__", r"\1", texto)
    texto = re.sub(r"^#+\s*", "", texto, flags=re.MULTILINE)
    reemplazos = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "*",
        "…": "...",
        "€": "EUR ",
        "£": "GBP ",
        "→": "->",
        "✔": "[OK]",
        "≥": ">=",
        "≤": "<=",
        "ñ": "n",
        "Ñ": "N",
    }
    for orig, dest in reemplazos.items():
        texto = texto.replace(orig, dest)
    normalizado = unicodedata.normalize("NFKD", texto)
    return normalizado.encode("latin-1", "ignore").decode("latin-1")


def _fmt_miles_millones(valor: float | None, moneda: str = "$") -> str:
    if valor is None:
        return "N/D"
    abs_v = abs(float(valor))
    signo = "-" if float(valor) < 0 else ""
    if abs_v >= 1e12:
        return f"{signo}{moneda}{abs_v / 1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{signo}{moneda}{abs_v / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{signo}{moneda}{abs_v / 1e6:.2f}M"
    return f"{signo}{moneda}{abs_v:.2f}"


def _fmt_num(valor: float | None, sufijo: str = "", signed: bool = False) -> str:
    if valor is None:
        return "N/D"
    fmt = f"{float(valor):+.2f}" if signed else f"{float(valor):.2f}"
    return f"{fmt}{sufijo}"


# ==============================================================================
# 3. DESCUBRIMIENTO DINAMICO DE UNIVERSOS DESDE LAS APIS (SIN LISTAS FIJAS)
# ==============================================================================
def _es_ticker_valido(simbolo: str) -> bool:
    if not simbolo:
        return False
    s = simbolo.strip().upper()
    return bool(re.match(r"^[A-Z]{1,5}(\.[A-Z])?$", s))


def descubrir_candidatos_mercado() -> list[dict]:
    candidatos: dict[str, dict] = {}

    def _registrar(ticker: str, nombre: str = "", exchange: str = "", volumen: float = 0.0, precio: float = 0.0):
        tk = (ticker or "").strip().upper()
        if not _es_ticker_valido(tk):
            return
        if tk not in candidatos:
            candidatos[tk] = {
                "ticker": tk,
                "nombre": nombre or tk,
                "exchange": exchange.upper(),
                "volumen": float(volumen or 0.0),
                "precio_ref": float(precio or 0.0),
            }
        else:
            if nombre and candidatos[tk]["nombre"] == tk:
                candidatos[tk]["nombre"] = nombre
            if exchange and not candidatos[tk]["exchange"]:
                candidatos[tk]["exchange"] = exchange.upper()
            if volumen and volumen > candidatos[tk]["volumen"]:
                candidatos[tk]["volumen"] = float(volumen)
            if precio and candidatos[tk]["precio_ref"] <= 0:
                candidatos[tk]["precio_ref"] = float(precio)

    if ALPHAVANTAGE_API_KEY:
        try:
            resp = requests.get(
                "https://www.alphavantage.co/query",
                params={"function": "TOP_GAINERS_LOSERS", "apikey": ALPHAVANTAGE_API_KEY},
                timeout=20,
            )
            data = resp.json()
            for bloque in ("most_actively_traded", "top_gainers", "top_losers"):
                for item in data.get(bloque, [])[:15]:
                    _registrar(
                        ticker=item.get("ticker", ""),
                        volumen=float(item.get("volume") or 0),
                        precio=float(item.get("price") or 0),
                    )
        except Exception as exc:
            print(f"[Descubrimiento AlphaVantage] Aviso: {exc}")

    if MASSIVE_KEY:
        try:
            resp = requests.get(
                "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers",
                params={"apiKey": MASSIVE_KEY},
                timeout=25,
            )
            tickers_snap = resp.json().get("tickers", [])
            tickers_snap.sort(
                key=lambda x: float((x.get("day") or {}).get("v") or 0) * float((x.get("day") or {}).get("c") or 0),
                reverse=True,
            )
            for item in tickers_snap[:55]:
                day = item.get("day") or {}
                _registrar(
                    ticker=item.get("ticker", ""),
                    volumen=float(day.get("v") or 0),
                    precio=float(day.get("c") or (item.get("prevDay") or {}).get("c") or 0),
                )
        except Exception as exc:
            print(f"[Descubrimiento Massive] Aviso: {exc}")

    if FINNHUB_KEY:
        for idx_sym, exch_hint in [("^NDX", "NASDAQ"), ("^GSPC", "NYSE"), ("^RUT", "RUSSELL")]:
            try:
                resp = requests.get(
                    "https://finnhub.io/api/v1/index/constituents",
                    params={"symbol": idx_sym, "token": FINNHUB_KEY},
                    timeout=15,
                )
                const = resp.json().get("constituents", [])
                for tk in const[:25]:
                    _registrar(ticker=tk, exchange=exch_hint)
            except Exception:
                pass

    if MARKETSTACK_KEY and len(candidatos) < 45:
        for mic, exch_hint in [("XNAS", "NASDAQ"), ("XNYS", "NYSE")]:
            try:
                resp = requests.get(
                    "https://api.apilayer.net/marketstack/v2/tickers",
                    params={"access_key": MARKETSTACK_KEY, "exchange": mic, "limit": 25},
                    timeout=20,
                )
                for item in resp.json().get("data", []):
                    _registrar(
                        ticker=item.get("symbol", ""),
                        nombre=item.get("name", ""),
                        exchange=exch_hint,
                    )
            except Exception:
                pass

    if FMP_API_KEY and len(candidatos) < 45:
        for ruta, hint in [
            ("https://financialmodelingprep.com/api/v3/stock_market/actives", "NASDAQ"),
            ("https://financialmodelingprep.com/api/v3/stock_market/gainers", "NYSE"),
        ]:
            try:
                resp = requests.get(ruta, params={"apikey": FMP_API_KEY}, timeout=15)
                datos = resp.json()
                if isinstance(datos, list):
                    for item in datos[:15]:
                        _registrar(
                            ticker=item.get("symbol", ""),
                            nombre=item.get("name", ""),
