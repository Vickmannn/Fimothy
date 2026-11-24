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
    # Evita que pares de signos '$' o tildes de formato se interpreten como LaTeX/math
    texto = re.sub(r"\$([^$\n]+?)\$", r"USD \1", texto)
    texto = texto.replace("~", " ")
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


def _fmt_miles_millones(valor: float | None, moneda: str = "$", fallback_txt: str = "Activo/Etf sin cap. pub.") -> str:
    if valor is None:
        return fallback_txt
    abs_v = abs(float(valor))
    signo = "-" if float(valor) < 0 else ""
    if abs_v >= 1e12:
        return f"{signo}{moneda}{abs_v / 1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{signo}{moneda}{abs_v / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{signo}{moneda}{abs_v / 1e6:.2f}M"
    return f"{signo}{moneda}{abs_v:.2f}"


def _fmt_num(valor: float | None, sufijo: str = "", signed: bool = False, fallback_txt: str = "En revision") -> str:
    if valor is None:
        return fallback_txt
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
                            exchange=hint,
                            precio=float(item.get("price") or 0),
                        )
            except Exception:
                pass

    if TWELVE_DATA_KEY and len(candidatos) < 35:
        for mic, exch_hint in [("NASDAQ", "NASDAQ"), ("NYSE", "NYSE")]:
            try:
                resp = requests.get(
                    "https://api.twelvedata.com/stocks",
                    params={"exchange": mic, "apikey": TWELVE_DATA_KEY},
                    timeout=20,
                )
                for item in (resp.json().get("data") or [])[:15]:
                    _registrar(
                        ticker=item.get("symbol", ""),
                        nombre=item.get("name", ""),
                        exchange=exch_hint,
                    )
            except Exception:
                pass

    lista = list(candidatos.values())
    lista.sort(key=lambda x: x["volumen"], reverse=True)
    print(f"[Descubrimiento Dinamico] Total candidatos detectados hoy: {len(lista)}")
    return lista


def enriquecer_perfil_dinamico(ticker: str) -> dict:
    perfil = {"nombre": ticker, "exchange": "", "cap_mercado": None}
    if FINNHUB_KEY:
        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/stock/profile2",
                params={"symbol": ticker, "token": FINNHUB_KEY},
                timeout=12,
            )
            p = resp.json() or {}
            if p.get("name"):
                perfil["nombre"] = str(p["name"])
            if p.get("exchange"):
                perfil["exchange"] = str(p["exchange"]).upper()
            if p.get("marketCapitalization"):
                perfil["cap_mercado"] = float(p["marketCapitalization"]) * 1e6
        except Exception:
            pass
    if (perfil["nombre"] == ticker or perfil["cap_mercado"] is None or not perfil["exchange"]) and FMP_API_KEY:
        try:
            resp = requests.get(
                f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
                params={"apikey": FMP_API_KEY},
                timeout=12,
            )
            datos = resp.json()
            if isinstance(datos, list) and datos:
                p = datos[0]
                if perfil["nombre"] == ticker and p.get("companyName"):
                    perfil["nombre"] = str(p["companyName"])
                if not perfil["exchange"] and p.get("exchangeShortName"):
                    perfil["exchange"] = str(p["exchangeShortName"]).upper()
                if perfil["cap_mercado"] is None and p.get("mktCap"):
                    perfil["cap_mercado"] = float(p["mktCap"])
        except Exception:
            pass
    return perfil


# ==============================================================================
# 4. CONECTORES DE PRECIOS, FUNDAMENTALES Y NOTICIAS EN VIVO (SIN VALORES FIJOS)
# ==============================================================================
def _calcular_evolucion(cierres_desc: list[float]) -> dict[str, float]:
    if not cierres_desc or len(cierres_desc) < 2:
        return {}
    actual = float(cierres_desc[0])
    if actual <= 0:
        return {}
    n = len(cierres_desc)
    out: dict[str, float] = {}
    for etq, pasos in PLAZOS_EVOLUTIVOS:
        if n > pasos:
            ref = float(cierres_desc[pasos])
            if ref > 0:
                out[etq] = ((actual - ref) / ref) * 100.0
    return out


def serie_massive(ticker: str) -> dict | None:
    if not MASSIVE_KEY:
        return None
    try:
        hasta = datetime.date.today().isoformat()
        desde = (datetime.date.today() - datetime.timedelta(days=410)).isoformat()
        resp = requests.get(
            f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{desde}/{hasta}",
            params={"adjusted": "true", "sort": "desc", "limit": 300, "apiKey": MASSIVE_KEY},
            timeout=20,
        )
        res = resp.json().get("results", [])
        if res:
            cierres = [float(r["c"]) for r in res if r.get("c") and float(r["c"]) > 0]
            if cierres:
                evol = _calcular_evolucion(cierres)
                ts_ms = res[0].get("t")
                fecha_bar = (
                    datetime.datetime.fromtimestamp(ts_ms / 1000.0, tz=datetime.timezone.utc).date().isoformat()
                    if ts_ms else hasta
                )
                return {
                    "precio": cierres[0],
                    "var_1d": evol.get("1D", 0.0),
                    "evolucion": evol,
                    "fecha": fecha_bar,
                    "fuente": "Massive",
                }
    except Exception:
        return None
    return None


def serie_alpaca(ticker: str) -> dict | None:
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None
    try:
        hasta = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        desde = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=410)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = requests.get(
            f"https://data.alpaca.markets/v2/stocks/{ticker}/bars",
            headers={
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
            },
            params={
                "timeframe": "1Day",
                "start": desde,
                "end": hasta,
                "limit": 300,
                "feed": "iex",
            },
            timeout=20,
        )
        bars = resp.json().get("bars", [])
        if bars:
            bars_desc = list(reversed(bars))
            cierres = [float(b["c"]) for b in bars_desc if b.get("c") and float(b["c"]) > 0]
            if cierres:
                evol = _calcular_evolucion(cierres)
                fecha_bar = str(bars_desc[0].get("t", ""))[:10] or datetime.date.today().isoformat()
                return {
                    "precio": cierres[0],
                    "var_1d": evol.get("1D", 0.0),
                    "evolucion": evol,
                    "fecha": fecha_bar,
                    "fuente": "Alpaca",
                }
    except Exception:
        return None
    return None


def serie_marketstack(ticker: str) -> dict | None:
    if not MARKETSTACK_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.apilayer.net/marketstack/v2/eod",
            params={"access_key": MARKETSTACK_KEY, "symbols": ticker, "limit": 270},
            timeout=20,
        )
        filas = resp.json().get("data", [])
        if not filas:
            return None
        cierres = [float(x["close"]) for x in filas if x.get("close") and float(x["close"]) > 0]
        if not cierres:
            return None
        evol = _calcular_evolucion(cierres)
        return {
            "precio": cierres[0],
            "var_1d": evol.get("1D", 0.0),
            "evolucion": evol,
            "fecha": str(filas[0].get("date", ""))[:10],
            "fuente": "MarketStack",
        }
    except Exception:
        return None


def serie_twelve_data(ticker: str) -> dict | None:
    if not TWELVE_DATA_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": ticker,
                "interval": "1day",
                "outputsize": 270,
                "apikey": TWELVE_DATA_KEY,
            },
            timeout=20,
        )
        valores = resp.json().get("values", [])
        if not valores:
            return None
        cierres = [float(v["close"]) for v in valores if v.get("close") and float(v["close"]) > 0]
        if not cierres:
            return None
        evol = _calcular_evolucion(cierres)
        return {
            "precio": cierres[0],
            "var_1d": evol.get("1D", 0.0),
            "evolucion": evol,
            "fecha": str(valores[0].get("datetime", ""))[:10],
            "fuente": "Twelve Data",
        }
    except Exception:
        return None


def serie_alpha_vantage(ticker: str) -> dict | None:
    if not ALPHAVANTAGE_API_KEY:
        return None
    time.sleep(0.35)
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "full",
                "apikey": ALPHAVANTAGE_API_KEY,
            },
            timeout=20,
        )
        serie = resp.json().get("Time Series (Daily)")
        if not serie:
            return None
        fechas = sorted(serie.keys(), reverse=True)
        cierres = [float(serie[f]["4. close"]) for f in fechas if float(serie[f]["4. close"]) > 0]
        if not cierres:
            return None
        evol = _calcular_evolucion(cierres)
        return {
            "precio": cierres[0],
            "var_1d": evol.get("1D", 0.0),
            "evolucion": evol,
            "fecha": fechas[0],
            "fuente": "AlphaVantage",
        }
    except Exception:
        return None


def serie_finnhub(ticker: str) -> dict | None:
    if not FINNHUB_KEY:
        return None
    try:
        resp_q = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": ticker, "token": FINNHUB_KEY},
            timeout=15,
        )
        q = resp_q.json()
        cierre = float(q.get("c") or 0)
        previo = float(q.get("pc") or 0)
        if cierre <= 0:
            return None

        evol: dict[str, float] = {}
        if previo > 0:
            evol["1D"] = ((cierre - previo) / previo) * 100.0

        ahora_ts = int(time.time())
        desde_ts = ahora_ts - 400 * 86400
        resp_c = requests.get(
            "https://finnhub.io/api/v1/stock/candle",
            params={"symbol": ticker, "resolution": "D", "from": desde_ts, "to": ahora_ts, "token": FINNHUB_KEY},
            timeout=15,
        )
        c_data = resp_c.json()
        if c_data.get("s") == "ok" and c_data.get("c"):
            cierres_desc = [float(x) for x in reversed(c_data["c"]) if float(x) > 0]
            if cierres_desc:
                cierres_desc[0] = cierre
                evol.update(_calcular_evolucion(cierres_desc))

        ts_q = q.get("t")
        fecha_q = (
            datetime.datetime.fromtimestamp(ts_q, tz=datetime.timezone.utc).date().isoformat()
            if ts_q else datetime.date.today().isoformat()
        )
        return {
            "precio": cierre,
            "var_1d": evol.get("1D", 0.0),
            "evolucion": evol,
            "fecha": fecha_q,
            "fuente": "Finnhub",
        }
    except Exception:
        return None


def fundamentales_finnhub(ticker: str) -> dict:
    if not FINNHUB_KEY:
        return {}
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/stock/metric",
            params={"symbol": ticker, "metric": "all", "token": FINNHUB_KEY},
            timeout=15,
        )
        m = resp.json().get("metric") or {}
        if not m:
            return {}

        def _f(*campos: str) -> float | None:
            for campo in campos:
                val = m.get(campo)
                if val is not None:
                    try:
                        return float(val)
                    except Exception:
                        pass
            return None

        pe = _f("peTTM", "peBasicExclExtraTTM", "peAnnual", "peExclExtraTTM")
        fwd_pe = _f("forwardPE", "peNormalizedAnnual")
        pm = _f("netProfitMarginTTM", "netProfitMarginAnnual", "operatingMarginTTM", "operatingMarginAnnual")
        eps_g = _f("epsGrowthTTMYOY", "epsGrowthQuarterlyYOY", "epsGrowth5Y", "epsGrowth3Y")
        rev_g = _f("revenueGrowthTTMYOY", "revenueGrowthQuarterlyYOY", "revenueGrowth5Y", "revenueGrowth3Y")
        deuda_eq = _f("totalDebt/totalEquityQuarterly", "totalDebt/totalEquityAnnual", "longTermDebt/equityQuarterly", "longTermDebt/equityAnnual")
        mcap_m = _f("marketCapitalization")
        mcap = mcap_m * 1e6 if mcap_m is not None else None
        fcf_ps = _f("freeCashFlowPerShareTTM", "freeCashFlowPerShareAnnual", "operatingCashFlowPerShareTTM")
        shares_m = _f("shareOutstanding")
        fcf = (fcf_ps * shares_m * 1e6) if (fcf_ps is not None and shares_m is not None) else None

        return {
            "cap_mercado": mcap,
            "pe": pe,
            "pe_futuro": fwd_pe,
            "margen_neto": pm,
            "crec_ganancias": eps_g,
            "crec_ingresos": rev_g,
            "deuda_patrimonio": deuda_eq * 100.0 if (deuda_eq is not None and deuda_eq <= 5.0) else deuda_eq,
            "caja_libre": fcf,
            "fuente_fund": "Finnhub",
        }
    except Exception:
        return {}


def fundamentales_alpha_vantage(ticker: str) -> dict:
    if not ALPHAVANTAGE_API_KEY:
        return {}
    time.sleep(0.35)
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "OVERVIEW", "symbol": ticker, "apikey": ALPHAVANTAGE_API_KEY},
            timeout=20,
        )
        ov = resp.json()
        if not ov or "Symbol" not in ov:
            return {}

        def _f(*campos: str, mult: float = 1.0) -> float | None:
            for campo in campos:
                raw = ov.get(campo)
                if raw not in (None, "", "None", "-"):
                    try:
                        return float(raw) * mult
                    except Exception:
                        pass
            return None

        fcf_av = _f("OperatingCashflow", "EBITDA")
        return {
            "nombre": ov.get("Name"),
            "exchange": ov.get("Exchange"),
            "cap_mercado": _f("MarketCapitalization"),
            "pe": _f("PERatio", "TrailingPE"),
            "pe_futuro": _f("ForwardPE"),
            "margen_neto": _f("ProfitMargin", "OperatingMarginTTM", mult=100.0),
            "crec_ganancias": _f("QuarterlyEarningsGrowthYOY", mult=100.0),
            "crec_ingresos": _f("QuarterlyRevenueGrowthYOY", mult=100.0),
            "deuda_patrimonio": _f("DebtToEquityRatio"),
            "caja_libre": fcf_av,
            "fuente_fund": "AlphaVantage",
        }
    except Exception:
        return {}


def fundamentales_fmp(ticker: str) -> dict:
    if not FMP_API_KEY:
        return {}
    try:
        resp = requests.get(
            f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
            params={"apikey": FMP_API_KEY},
            timeout=15,
        )
        datos = resp.json()
        if not isinstance(datos, list) or not datos:
            return {}
        p = datos[0]

        def _f(*campos: str) -> float | None:
            for campo in campos:
                raw = p.get(campo)
                if raw not in (None, "", "None"):
                    try:
                        return float(raw)
                    except Exception:
                        pass
            return None

        return {
            "nombre": p.get("companyName"),
            "exchange": p.get("exchangeShortName"),
            "cap_mercado": _f("mktCap"),
            "pe": _f("pe"),
            "caja_libre": _f("freeCashFlow", "operatingCashFlow"),
            "fuente_fund": "FMP",
        }
    except Exception:
        return {}


def noticias_alpha_vantage() -> list[dict]:
    if not ALPHAVANTAGE_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "topics": "technology,financial_markets",
                "limit": 6,
                "apikey": ALPHAVANTAGE_API_KEY,
            },
            timeout=20,
        )
        items = resp.json().get("feed", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"AlphaVantage ({i.get('source', 'Mercado')})",
            }
            for i in items[:3]
            if i.get("title")
        ]
    except Exception:
        return []


def noticias_finnhub() -> list[dict]:
    if not FINNHUB_KEY:
        return []
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "general", "token": FINNHUB_KEY},
            timeout=15,
        )
        items = resp.json()
        if not isinstance(items, list):
            return []
        return [
            {
                "titulo": i.get("headline", ""),
                "fuente": f"Finnhub ({i.get('source', 'Mercado')})",
            }
            for i in items[:3]
            if i.get("headline")
        ]
    except Exception:
        return []


def noticias_marketaux(tickers: list[str]) -> list[dict]:
    if not MARKETAUX_KEY or not tickers:
        return []
    try:
        resp = requests.get(
            "https://api.marketaux.com/v1/news/all",
            params={
                "symbols": ",".join(tickers[:8]),
                "filter_entities": "true",
                "language": "en,es",
                "limit": 4,
                "api_token": MARKETAUX_KEY,
            },
            timeout=20,
        )
        items = resp.json().get("data", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"Marketaux ({i.get('source', 'Corporativo')})",
            }
            for i in items[:3]
            if i.get("title")
        ]
    except Exception:
        return []


def noticias_newsapi() -> list[dict]:
    if not NEWS_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": "(Nasdaq OR S&P 500 OR Russell 2000 OR Wall Street OR stocks)",
                "sortBy": "publishedAt",
                "pageSize": 4,
                "apiKey": NEWS_API_KEY,
            },
            timeout=20,
        )
        items = resp.json().get("articles", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"NewsAPI.org ({(i.get('source') or {}).get('name', 'Prensa')})",
            }
            for i in items[:3]
            if i.get("title") and "[Removed]" not in i.get("title", "")
        ]
    except Exception:
        return []


def noticias_newsdata() -> list[dict]:
    if not NEWSDATA_KEY:
        return []
    try:
        resp = requests.get(
            "https://newsdata.io/api/1/latest",
            params={
                "apikey": NEWSDATA_KEY,
                "q": "stocks OR Nasdaq OR Wall Street",
                "category": "business",
            },
            timeout=20,
        )
        items = resp.json().get("results", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"NewsData.io ({i.get('source_id', 'Negocios')})",
            }
            for i in items[:3]
            if i.get("title")
        ]
    except Exception:
        return []


def recolectar_noticias_fuentes(tickers_ref: list[str]) -> tuple[list[dict], dict]:
    fuentes = {
        "AlphaVantage": noticias_alpha_vantage(),
        "Finnhub": noticias_finnhub(),
        "Marketaux": noticias_marketaux(tickers_ref),
        "NewsAPI.org": noticias_newsapi(),
        "NewsData.io": noticias_newsdata(),
    }
    vistas = set()
    consolidadas = []
    conteos = {}
    for nombre_f, lista in fuentes.items():
        conteos[nombre_f] = len(lista)
        for item in lista:
            clave = re.sub(r"\W+", "", item["titulo"].lower())[:55]
            if clave and clave not in vistas:
                vistas.add(clave)
                consolidadas.append(item)
    return consolidadas[:12], conteos


# ==============================================================================
# 5. EVALUACION 100 % REAL Y CLASIFICACION DUAL POR UNIVERSO (SIN DUPLICADOS)
# ==============================================================================
def evaluar_activo_real(candidato: dict) -> dict | None:
    ticker = candidato["ticker"]
    orden_series = [
        serie_alpaca,
        serie_massive,
        serie_finnhub,
        serie_twelve_data,
        serie_marketstack,
        serie_alpha_vantage,
    ]

    serie = None
    for fn in orden_series:
        res = fn(ticker)
        if res and res.get("precio") is not None and float(res["precio"]) > 0:
            serie = res
            break

    if not serie:
        return None

    evol = dict(serie.get("evolucion") or {})
    if len(evol) < 4:
        for fn_extra in (serie_alpaca, serie_twelve_data, serie_marketstack, serie_alpha_vantage):
            if fn_extra.__name__.lower().replace("serie_", "") in serie["fuente"].lower().replace(" ", "_"):
                continue
            extra = fn_extra(ticker)
            if extra and extra.get("evolucion"):
                for k, v in extra["evolucion"].items():
                    evol.setdefault(k, v)
                break

    perfil = enriquecer_perfil_dinamico(ticker)
    fh_fund = fundamentales_finnhub(ticker)
    av_fund = fundamentales_alpha_vantage(ticker)
    fmp_fund = fundamentales_fmp(ticker)

    fund = {}
    for fuente_d in (fh_fund, av_fund, fmp_fund):
        for k, v in fuente_d.items():
            if v is not None and fund.get(k) is None:
                fund[k] = v

    nombre = (
        fund.get("nombre")
        or (perfil["nombre"] if perfil["nombre"] != ticker else None)
        or (candidato["nombre"] if candidato["nombre"] != ticker else ticker)
    )
    exchange = (fund.get("exchange") or perfil.get("exchange") or candidato.get("exchange") or "").upper()
    cap_mercado = fund.get("cap_mercado") or perfil.get("cap_mercado")

    precio = float(serie["precio"])
    var_1d = float(serie.get("var_1d", evol.get("1D", 0.0)))
    crec_gan = fund.get("crec_ganancias")
    crec_ing = fund.get("crec_ingresos")
    deuda_eq = fund.get("deuda_patrimonio")
    caja_libre = fund.get("caja_libre")

    valores_evol = [float(v) for v in evol.values() if v is not None]
    impulso_prom = float(np.mean(valores_evol)) if valores_evol else var_1d

    crecs_disponibles = [float(x) for x in (crec_gan, crec_ing) if x is not None]
    crec_prom = float(np.mean(crecs_disponibles)) if crecs_disponibles else None

    comp_crec = (crec_prom * 0.45) if crec_prom is not None else 0.0
    comp_imp = impulso_prom * 0.55
    comp_d1 = abs(var_1d) * 0.85
    score = round(comp_crec + comp_imp + comp_d1, 2)

    partes_lectura = []
    if crec_gan is not None:
        partes_lectura.append(f"Crecimiento ganancias YoY: {float(crec_gan):+.2f}%")
    elif crec_ing is not None:
        partes_lectura.append(f"Crecimiento ingresos YoY: {float(crec_ing):+.2f}%")
    else:
        partes_lectura.append(f"Impulso prom. multitemporal: {impulso_prom:+.2f}% (1D: {var_1d:+.2f}%, {serie['fuente']})")

    if deuda_eq is not None:
        d_val = float(deuda_eq)
        if d_val > 120:
            partes_lectura.append(f"apalancamiento elevado ({d_val:.1f}%)")
        elif d_val > 55:
            partes_lectura.append(f"deuda moderada ({d_val:.1f}%)")
        else:
            partes_lectura.append(f"endeudamiento contenido ({d_val:.1f}%)")
    else:
        partes_lectura.append("estructura sin reporte de deuda corporativa")

    if caja_libre is not None:
        c_val = float(caja_libre)
        if c_val >= 0:
            partes_lectura.append(f"flujo de caja positivo ({_fmt_miles_millones(c_val)})")
        else:
            partes_lectura.append(f"flujo de caja negativo ({_fmt_miles_millones(c_val)})")
    else:
        partes_lectura.append(f"liquidez/precio en vivo ${precio:,.2f}")

    lectura = "; ".join(partes_lectura) + "."

    negativos = sum(1 for v in valores_evol if v < 0)
    positivos = sum(1 for v in valores_evol if v > 0)
    if negativos > positivos and negativos >= 2:
        fase_titulo = f"{ticker} ({nombre}) - Fase de ajuste o presion bajista"
        fase_desc = (
            f"Registra retrocesos en {negativos} de {len(valores_evol)} horizontes medidos "
            f"(1D: {var_1d:+.2f}%). Conviene esperar confirmacion de soporte antes de ampliar."
        )
    elif positivos >= negativos and impulso_prom > 1.5:
        fase_titulo = f"{ticker} ({nombre}) - Fase de expansion e impulso"
        fase_desc = (
            f"Mantiene traccion positiva en {positivos} de {len(valores_evol)} horizontes "
            f"(impulso promedio: {impulso_prom:+.2f}%, 1D: {var_1d:+.2f}%)."
        )
    else:
        fase_titulo = f"{ticker} ({nombre}) - Fase de transicion y selectividad"
        fase_desc = (
            f"Comportamiento mixto entre plazos disponibles (1D: {var_1d:+.2f}%, "
            f"promedio multitemporal: {impulso_prom:+.2f}%). Vigilar confirmacion de volumen."
        )

    return {
        "ticker": ticker,
        "nombre": nombre,
        "exchange": exchange,
        "precio": precio,
        "var_1d": var_1d,
        "evolucion": evol,
        "fecha_dato": serie.get("fecha", ""),
        "fuente_precio": serie["fuente"],
        "crec_ganancias": crec_gan,
        "crec_ingresos": crec_ing,
        "crec_prom": crec_prom,
        "impulso_prom": impulso_prom,
        "score": score,
        "lectura": lectura,
        "fase_titulo": fase_titulo,
        "fase_desc": fase_desc,
        "cap_mercado": cap_mercado,
        "pe": fund.get("pe"),
        "pe_futuro": fund.get("pe_futuro"),
        "margen_neto": fund.get("margen_neto"),
        "deuda_patrimonio": deuda_eq,
        "caja_libre": caja_libre,
    }


def _seleccionar_sin_repetir(
    pool_primario: list[dict],
    respaldo: list[dict],
    clave_orden: str,
    excluidos: set[str],
    cantidad: int = 10,
) -> list[dict]:
    candidatos_ordenados = sorted(
        pool_primario,
        key=lambda x: float(x.get(clave_orden) if x.get(clave_orden) is not None else -1e18),
        reverse=True,
    )
    seleccionados: list[dict] = []
    vistos_locales: set[str] = set(excluidos)

    for item in candidatos_ordenados:
        tk = item["ticker"]
        if tk not in vistos_locales:
            vistos_locales.add(tk)
            seleccionados.append(dict(item))
            if len(seleccionados) == cantidad:
                break

    if len(seleccionados) < cantidad:
        extras_ordenados = sorted(
            [x for x in respaldo if x["ticker"] not in vistos_locales],
            key=lambda x: float(x.get(clave_orden) if x.get(clave_orden) is not None else -1e18),
            reverse=True,
        )
        for item in extras_ordenados:
            tk = item["ticker"]
            if tk not in vistos_locales:
                vistos_locales.add(tk)
                seleccionados.append(dict(item))
                if len(seleccionados) == cantidad:
                    break

    for idx, emp in enumerate(seleccionados, start=1):
        emp["rank"] = idx

    return seleccionados


def construir_universos_dinamicos() -> list[dict]:
    candidatos = descubrir_candidatos_mercado()
    evaluados: list[dict] = []

    for cand in candidatos[:50]:
        activo = evaluar_activo_real(cand)
        if activo:
            evaluados.append(activo)

    if not evaluados:
        raise RuntimeError(
            "Ninguna API devolvio precios reales hoy. Revisa las API Keys en GitHub Secrets antes de emitir el PDF."
        )

    nasdaq_pool = [
        a for a in evaluados
        if "NASDAQ" in a["exchange"] or "XNAS" in a["exchange"]
    ]
    sp500_pool = [
        a for a in evaluados
        if (a["cap_mercado"] is not None and float(a["cap_mercado"]) >= UMBRAL_SMALL_MID_CAP)
        or "NYSE" in a["exchange"]
        or "XNYS" in a["exchange"]
    ]
    russell_small_mid_pool = [
        a for a in evaluados
        if (a["cap_mercado"] is not None and float(a["cap_mercado"]) < UMBRAL_SMALL_MID_CAP)
        or "RUSSELL" in a["exchange"]
    ]
    russell_respaldo_sin_gigantes = [
        a for a in evaluados
        if a["cap_mercado"] is None or float(a["cap_mercado"]) < UMBRAL_SMALL_MID_CAP
    ]

    nasdaq_cap = _seleccionar_sin_repetir(
        pool_primario=nasdaq_pool,
        respaldo=evaluados,
        clave_orden="cap_mercado",
        excluidos=set(),
        cantidad=10,
    )
    excluidos_nasdaq = {e["ticker"] for e in nasdaq_cap}
    nasdaq_din = _seleccionar_sin_repetir(
        pool_primario=nasdaq_pool,
        respaldo=evaluados,
        clave_orden="score",
        excluidos=excluidos_nasdaq,
        cantidad=10,
    )

    sp500_cap = _seleccionar_sin_repetir(
        pool_primario=sp500_pool,
        respaldo=evaluados,
        clave_orden="cap_mercado",
        excluidos=set(),
        cantidad=10,
    )
    excluidos_sp500 = {e["ticker"] for e in sp500_cap}
    sp500_din = _seleccionar_sin_repetir(
        pool_primario=sp500_pool,
        respaldo=evaluados,
        clave_orden="score",
        excluidos=excluidos_sp500,
        cantidad=10,
    )

    russell_cap = _seleccionar_sin_repetir(
        pool_primario=russell_small_mid_pool,
        respaldo=russell_respaldo_sin_gigantes,
        clave_orden="cap_mercado",
        excluidos=set(),
        cantidad=10,
    )
    excluidos_russell = {e["ticker"] for e in russell_cap}
    russell_din = _seleccionar_sin_repetir(
        pool_primario=russell_small_mid_pool,
        respaldo=russell_respaldo_sin_gigantes,
        clave_orden="score",
        excluidos=excluidos_russell,
        cantidad=10,
    )

    definiciones = [
        {
            "clave": "nasdaq_cap",
            "titulo_bloque": "NASDAQ TOP 10 - CAPITALIZACION",
            "subtitulo_universo": "Ancla estructural en vivo: Mayor capitalizacion bursatil en Nasdaq (sin repetir en dinamico)",
            "prefijo_archivo": "nasdaq_cap",
            "empresas": nasdaq_cap,
        },
        {
            "clave": "nasdaq_din",
            "titulo_bloque": "NASDAQ TOP 10 - DINAMICO / IMPULSO",
            "subtitulo_universo": "Radar de movimiento en vivo: Mayor impulso y traccion en Nasdaq (20 empresas distintas en Nasdaq)",
            "prefijo_archivo": "nasdaq_din",
            "empresas": nasdaq_din,
        },
        {
            "clave": "sp500_cap",
            "titulo_bloque": "S&P 500 TOP 10 - CAPITALIZACION",
            "subtitulo_universo": "Ancla estructural en vivo: Mayor capitalizacion bursatil en S&P 500 (sin repetir en dinamico)",
            "prefijo_archivo": "sp500_cap",
            "empresas": sp500_cap,
        },
        {
            "clave": "sp500_din",
            "titulo_bloque": "S&P 500 TOP 10 - DINAMICO / IMPULSO",
            "subtitulo_universo": "Radar de movimiento en vivo: Mayor impulso y traccion en S&P 500 (20 empresas distintas en S&P 500)",
            "prefijo_archivo": "sp500_din",
            "empresas": sp500_din,
        },
        {
            "clave": "russell2000_cap",
            "titulo_bloque": "RUSSELL 2000 TOP 10 - CAPITALIZACION (SMALL/MID)",
            "subtitulo_universo": "Ancla del segmento (<$10B): Mayor capitalizacion dentro de pequena/mediana capitalizacion",
            "prefijo_archivo": "russell2000_cap",
            "empresas": russell_cap,
        },
        {
            "clave": "russell2000_din",
            "titulo_bloque": "RUSSELL 2000 TOP 10 - DINAMICO / IMPULSO (SMALL/MID)",
            "subtitulo_universo": "Radar de movimiento (<$10B): Mayor impulso en pequena/mediana capitalizacion (20 distintas en Russell)",
            "prefijo_archivo": "russell2000_din",
            "empresas": russell_din,
        },
    ]

    for b in definiciones:
        b["lider"] = b["empresas"][0] if b["empresas"] else None
        print(f"[{b['titulo_bloque']}] Top 10 de hoy: {[e['ticker'] for e in b['empresas']]}")

    return definiciones


def obtener_indices_cabecera() -> list[dict]:
    orden_idx = [serie_alpaca, serie_finnhub, serie_massive, serie_twelve_data, serie_marketstack, serie_alpha_vantage]
    salida = []
    for tk, etiqueta in INDICES_CABECERA:
        dato = None
        for fn in orden_idx:
            dato = fn(tk)
            if dato and dato.get("precio") is not None:
                break
        if dato:
            salida.append({
                "ticker": tk,
                "etiqueta": etiqueta,
                "precio": float(dato["precio"]),
                "var_1d": float(dato["var_1d"]),
                "fuente": dato["fuente"],
            })
        else:
            salida.append({
                "ticker": tk,
                "etiqueta": etiqueta,
                "precio": None,
                "var_1d": None,
                "fuente": "N/D",
            })
    return salida


# ==============================================================================
# 6. GRAFICOS POR UNIVERSO: MAPA DE CALOR + MATRIZ FUNDAMENTAL VS. IMPULSO
# ==============================================================================
def _tam_titulo_grafico(texto: str, base_sz: float = 8.8, min_sz: float = 6.8) -> float:
    largo = len(texto or "")
    if largo <= 45:
        return base_sz
    reduccion = (largo - 45) * 0.045
    return max(min_sz, round(base_sz - reduccion, 2))


def generar_graficos_universo(bloque: dict) -> dict[str, str]:
    empresas = bloque["empresas"]
    prefijo = bloque["prefijo_archivo"]
    plazos = [etq for etq, _ in PLAZOS_EVOLUTIVOS]

    matriz_calor = np.array([
        [float(emp["evolucion"][p]) if emp["evolucion"].get(p) is not None else np.nan for p in plazos]
        for emp in empresas
    ])
    etiquetas_y = [f"{emp['rank']}. {emp['ticker']}" for emp in empresas]

    fig, ax = plt.subplots(figsize=(8.4, 3.9))
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    validos = matriz_calor[~np.isnan(matriz_calor)]
    vmax = max(float(np.max(np.abs(validos))), 5.0) if validos.size > 0 else 10.0
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad(color="#E2E8F0")

    im = ax.imshow(matriz_calor, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")

    ax.set_xticks(np.arange(len(plazos)))
    ax.set_yticks(np.arange(len(etiquetas_y)))
    ax.set_xticklabels(plazos, fontsize=7.6, fontweight="bold")
    ax.set_yticklabels(etiquetas_y, fontsize=7.8, fontweight="bold")
    titulo_calor = f"Mapa de Calor Multitemporal ({bloque['titulo_bloque']})"
    ax.set_title(
        titulo_calor,
        fontsize=_tam_titulo_grafico(titulo_calor, base_sz=8.8, min_sz=6.6),
        fontweight="bold",
        loc="left",
        pad=8,
    )

    for i in range(len(etiquetas_y)):
        for j in range(len(plazos)):
            val = matriz_calor[i, j]
            texto_celda = "N/D" if np.isnan(val) else f"{val:+.1f}%"
            ax.text(
                j,
                i,
                texto_celda,
                ha="center",
                va="center",
                fontsize=6.2,
                fontweight="bold",
                color="#111827",
            )

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Variacion (%)", fontsize=7.2)
    cbar.ax.tick_params(labelsize=6.8)
    ruta_calor = f"mapa_calor_{prefijo}.png"
    plt.savefig(ruta_calor, dpi=180, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)

    crec_x = [float(emp["crec_prom"]) if emp["crec_prom"] is not None else float(emp["var_1d"]) for emp in empresas]
    imp_y = [float(emp["impulso_prom"]) for emp in empresas]
    scores = [float(emp["score"]) for emp in empresas]
    tamanos = [max(90.0, min(420.0, abs(s) * 2.5 + 90.0)) for s in scores]

    fig2, ax2 = plt.subplots(figsize=(8.4, 4.1))
    ax2.set_facecolor("#F8FAFC")
    sc = ax2.scatter(
        crec_x,
        imp_y,
        s=tamanos,
        c=scores,
        cmap="viridis",
        alpha=0.9,
        edgecolors="#111827",
        linewidths=0.9,
    )
    ax2.axhline(0, linestyle="--", linewidth=0.9, color="#475569")
    ax2.axvline(0, linestyle="--", linewidth=0.9, color="#475569")
    ax2.grid(True, linestyle=":", alpha=0.5, color="#94A3B8")

    for emp, x_val, y_val in zip(empresas, crec_x, imp_y):
        ax2.annotate(
            f"#{emp['rank']} {emp['ticker']}",
            (x_val, y_val),
            textcoords="offset points",
            xytext=(6, 4),
            fontsize=7.2,
            fontweight="bold",
            color="#0F172A",
        )

    titulo_matriz = f"FIMOTHY QUANT - Crecimiento / Traccion vs. Impulso ({bloque['titulo_bloque']})"
    ax2.set_title(
        titulo_matriz,
        fontsize=_tam_titulo_grafico(titulo_matriz, base_sz=8.8, min_sz=6.6),
        fontweight="bold",
        loc="left",
        pad=8,
    )
    ax2.set_xlabel("Crecimiento Fundamental / Traccion Diaria (%)", fontsize=7.8, fontweight="bold")
    ax2.set_ylabel("Impulso de Precio Multitemporal (%)", fontsize=7.8, fontweight="bold")
    ax2.tick_params(labelsize=7.3)

    cbar2 = fig2.colorbar(sc, ax=ax2, fraction=0.025, pad=0.02)
    cbar2.set_label("Score Combinado", fontsize=7.2)
    cbar2.ax.tick_params(labelsize=6.8)
    ruta_matriz = f"matriz_cuant_{prefijo}.png"
    plt.savefig(ruta_matriz, dpi=180, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig2)

    return {"calor": ruta_calor, "matriz": ruta_matriz}


# ==============================================================================
# 7. MAQUETACION EN PDF (SIN ENCIMAMIENTOS NI CORTES DE TEXTO)
# ==============================================================================
class InstitutionalTechBriefPDF(FPDF):
    def __init__(self, fecha_utc: str):
        super().__init__()
        self.fecha_utc = fecha_utc
        self.universo_actual = "NASDAQ + S&P 500 + RUSSELL 2000"
        self.set_margins(left=12, top=22, right=12)
        self.set_auto_page_break(auto=True, margin=16)

    @property
    def ancho_util(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def _ajustar_cadena_a_ancho(self, texto: str, familia: str, estilo: str, tam_inicial: float, ancho_max: float, min_tam: float = 6.2) -> tuple[str, float]:
        limpio = limpiar_texto_pdf(texto)
        tam = tam_inicial
        while tam >= min_tam:
            self.set_font(familia, estilo, tam)
            if self.get_string_width(limpio) <= ancho_max:
                return limpio, tam
            tam = round(tam - 0.3, 1)

        self.set_font(familia, estilo, min_tam)
        if self.get_string_width(limpio) <= ancho_max:
            return limpio, min_tam

        base = limpio
        while len(base) > 3 and self.get_string_width(base + "...") > ancho_max:
            base = base[:-1]
        return (base + "...") if len(base) > 3 else limpio[:3], min_tam

    def header(self):
        self.set_fill_color(248, 250, 252)
        self.rect(0, 0, 210, 17, "F")
        self.set_draw_color(203, 213, 225)
        self.set_line_width(0.4)
        self.line(12, 17, 198, 17)

        self.set_xy(12, 4.5)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(15, 23, 42)
        self.cell(80, 5, limpiar_texto_pdf("FIMOTHY"), new_x="RIGHT", new_y="TOP")

        self.set_xy(92, 4.5)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(30, 58, 138)
        self.cell(106, 5, limpiar_texto_pdf("INSTITUTIONAL TECH REPORT"), align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_xy(12, 9.5)
        self.set_font("Helvetica", "B", 6.8)
        self.set_text_color(100, 116, 139)
        self.cell(65, 4, limpiar_texto_pdf("FINANCIAL ENTERPRISE"), new_x="RIGHT", new_y="TOP")

        self.set_xy(77, 9.5)
        self.set_text_color(71, 85, 105)
        sub_txt, sub_sz = self._ajustar_cadena_a_ancho(
            f"FIMOTHY RESEARCH | {self.universo_actual}",
            "Helvetica",
            "",
            7.0,
            121.0,
            min_tam=5.6,
        )
        self.set_font("Helvetica", "", sub_sz)
        self.cell(121, 4, sub_txt, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_y(22)

    def footer(self):
        self.set_y(-12)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.3)
        self.line(12, self.get_y(), 198, self.get_y())
        self.set_font("Helvetica", "", 7.3)
        self.set_text_color(100, 116, 139)
        self.cell(
            self.ancho_util,
            7,
            limpiar_texto_pdf(
                f"FIMOTHY - Financial Enterprise | Analisis informativo en tiempo real, no constituye asesoria financiera | Pag. {self.page_no()}"
            ),
            align="C",
        )

    def cabecera_reporte_y_indices(self, indices: list[dict]):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 15.5)
        self.set_text_color(15, 23, 42)
        self.cell(
            self.ancho_util,
            7.2,
            limpiar_texto_pdf("Radar Dinamico Dual (20x3): Nasdaq, S&P 500 y Russell 2000"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 8.2)
        self.set_text_color(71, 85, 105)
        self.cell(
            self.ancho_util,
            4.8,
            limpiar_texto_pdf(
                f"Emision: {self.fecha_utc} | 10 Capitalizacion + 10 Dinamicos sin repetir por indice"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(2.2)

        n_idx = max(1, len(indices))
        gap = 3.0
        w_card = (self.ancho_util - gap * (n_idx - 1)) / n_idx
        y_top = self.get_y()

        for i, idx_item in enumerate(indices):
            x = self.l_margin + i * (w_card + gap)
            self.set_fill_color(248, 250, 252)
            self.set_draw_color(203, 213, 225)
            self.rect(x, y_top, w_card, 16.0, "DF")

            self.set_xy(x + 2.5, y_top + 1.6)
            etq_txt, etq_sz = self._ajustar_cadena_a_ancho(
                idx_item["etiqueta"], "Helvetica", "B", 6.7, w_card - 5.0, min_tam=5.5
            )
            self.set_font("Helvetica", "B", etq_sz)
            self.set_text_color(100, 116, 139)
            self.cell(w_card - 5, 3.4, etq_txt, new_x="LMARGIN", new_y="NEXT")

            self.set_x(x + 2.5)
            self.set_font("Helvetica", "B", 10.2)
            self.set_text_color(15, 23, 42)
            p_txt = f"{idx_item['precio']:,.2f}" if idx_item["precio"] is not None else "En revision"
            self.cell(w_card - 5, 5.0, limpiar_texto_pdf(p_txt), new_x="LMARGIN", new_y="NEXT")

            self.set_x(x + 2.5)
            self.set_font("Helvetica", "B", 7.4)
            v1d = idx_item["var_1d"]
            if v1d is None:
                self.set_text_color(100, 116, 139)
                v_txt = "Variacion 1D: Sin dato"
            elif v1d >= 0:
                self.set_text_color(21, 128, 61)
                v_txt = f"Variacion 1D: {v1d:+.2f}%"
            else:
                self.set_text_color(185, 28, 28)
                v_txt = f"Variacion 1D: {v1d:+.2f}%"
            self.cell(w_card - 5, 3.8, limpiar_texto_pdf(v_txt), new_x="LMARGIN", new_y="NEXT")

        self.set_y(y_top + 18.8)

    def banner_universo(self, titulo_bloque: str, subtitulo_universo: str):
        self.universo_actual = titulo_bloque
        if self.get_y() > 235:
            self.add_page()
        x0 = self.l_margin
        y0 = self.get_y()
        w0 = self.ancho_util
        self.set_fill_color(15, 23, 42)
        self.set_draw_color(30, 58, 138)
        self.rect(x0, y0, w0, 12.2, "DF")

        self.set_xy(x0 + 3, y0 + 1.5)
        t_txt, t_sz = self._ajustar_cadena_a_ancho(
            titulo_bloque, "Helvetica", "B", 9.6, w0 - 6.0, min_tam=7.2
        )
        self.set_font("Helvetica", "B", t_sz)
        self.set_text_color(255, 255, 255)
        self.cell(w0 - 6, 4.4, t_txt, new_x="LMARGIN", new_y="NEXT")

        self.set_x(x0 + 3)
        s_txt, s_sz = self._ajustar_cadena_a_ancho(
            subtitulo_universo, "Helvetica", "", 7.2, w0 - 6.0, min_tam=5.8
        )
        self.set_font("Helvetica", "", s_sz)
        self.set_text_color(203, 213, 225)
        self.cell(w0 - 6, 4.0, s_txt, new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + 14.5)

    def titulo_seccion_numerada(self, num_str: str, titulo: str, bajada: str):
        if self.get_y() > 242:
            self.add_page()
        x_ini = self.l_margin
        y_ini = self.get_y()
        ancho_tit = self.ancho_util - 8.5

        self.set_fill_color(30, 58, 138)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 8.5)
        self.rect(x_ini, y_ini, 6.5, 6.0, "F")
        self.set_xy(x_ini, y_ini)
        self.cell(6.5, 6.0, limpiar_texto_pdf(num_str), align="C")

        t_limpio, t_sz = self._ajustar_cadena_a_ancho(
            titulo, "Helvetica", "B", 10.8, ancho_tit, min_tam=7.4
        )
        self.set_xy(x_ini + 8.5, y_ini + 0.5)
        self.set_font("Helvetica", "B", t_sz)
        self.set_text_color(15, 23, 42)
        self.cell(ancho_tit, 5.2, t_limpio, new_x="LMARGIN", new_y="NEXT")

        self.set_y(y_ini + 6.8)
        self.set_x(x_ini)
        b_limpio, b_sz = self._ajustar_cadena_a_ancho(
            bajada, "Helvetica", "", 7.8, self.ancho_util, min_tam=6.2
        )
        self.set_font("Helvetica", "", b_sz)
        self.set_text_color(100, 116, 139)
        self.cell(self.ancho_util, 4.2, b_limpio, new_x="LMARGIN", new_y="NEXT")

        y_linea = self.get_y() + 0.8
        self.set_draw_color(203, 213, 225)
        self.line(x_ini, y_linea, x_ini + self.ancho_util, y_linea)
        self.set_y(y_linea + 2.4)

    def tarjeta_empresa_ranking(self, emp: dict, es_lider: bool = False):
        if self.get_y() > 232:
            self.add_page()

        x0 = self.l_margin
        y0 = self.get_y()
        w0 = self.ancho_util
        evol = emp.get("evolucion") or {}
        plazos = [etq for etq, _ in PLAZOS_EVOLUTIVOS]

        # Fila superior dividida en 3 columnas limpias sin solapamiento
        w_col_cap = 54.0
        w_col_prc = 33.0
        gap_col = 1.5
        w_col_nom = w0 - (w_col_cap + w_col_prc + gap_col * 2 + 3.0)

        self.set_fill_color(241, 245, 249)
        self.set_draw_color(203, 213, 225)
        self.rect(x0, y0, w0, 6.2, "DF")

        nom_raw = f"#{emp['rank']} {emp['nombre']} ({emp['ticker']})"
        nom_txt, nom_sz = self._ajustar_cadena_a_ancho(
            nom_raw, "Helvetica", "B", 8.0, w_col_nom, min_tam=6.3
        )
        self.set_xy(x0 + 1.5, y0 + 1.1)
        self.set_font("Helvetica", "B", nom_sz)
        self.set_text_color(15, 23, 42)
        self.cell(w_col_nom, 4.0, nom_txt)

        prc_raw = f"Precio: ${emp['precio']:,.2f}"
        prc_txt, prc_sz = self._ajustar_cadena_a_ancho(
            prc_raw, "Helvetica", "B", 7.6, w_col_prc, min_tam=6.2
        )
        x_prc = x0 + 1.5 + w_col_nom + gap_col
        self.set_xy(x_prc, y0 + 1.1)
        self.set_font("Helvetica", "B", prc_sz)
        self.set_text_color(30, 58, 138)
        self.cell(w_col_prc, 4.0, prc_txt, align="R")

        cap_corta = _fmt_miles_millones(emp.get("cap_mercado"), fallback_txt="S/Cap")
        cap_raw = f"Cap: {cap_corta} | Sc: {emp['score']:.1f}"
        cap_txt, cap_sz = self._ajustar_cadena_a_ancho(
            cap_raw, "Helvetica", "B", 7.5, w_col_cap, min_tam=6.1
        )
        x_cap = x_prc + w_col_prc + gap_col
        self.set_xy(x_cap, y0 + 1.1)
        self.set_font("Helvetica", "B", cap_sz)
        self.set_text_color(15, 23, 42)
        self.cell(w_col_cap, 4.0, cap_txt, align="R")

        y_plazos = y0 + 6.2
        w_plazos = w0 - 50 if es_lider else w0
        w_celda = w_plazos / len(plazos)

        for j, p in enumerate(plazos):
            xc = x0 + j * w_celda
            self.set_fill_color(248, 250, 252)
            self.rect(xc, y_plazos, w_celda, 4.3, "DF")
            self.set_xy(xc, y_plazos + 0.6)
            self.set_font("Helvetica", "B", 6.2)
            self.set_text_color(71, 85, 105)
            self.cell(w_celda, 3.0, limpiar_texto_pdf(p), align="C")

            raw_val = evol.get(p)
            self.set_fill_color(255, 255, 255)
            self.rect(xc, y_plazos + 4.3, w_celda, 5.0, "DF")
            self.set_xy(xc, y_plazos + 5.0)
            self.set_font("Helvetica", "B", 6.4)
            if raw_val is None:
                self.set_text_color(100, 116, 139)
                txt_p = "-"
            else:
                val = float(raw_val)
                if val >= 0:
                    self.set_text_color(21, 128, 61)
                else:
                    self.set_text_color(185, 28, 28)
                txt_p = f"{val:+.1f}%"
            self.cell(w_celda, 3.5, limpiar_texto_pdf(txt_p), align="C")

        if es_lider:
            xl = x0 + w_plazos + 2
            wl = w0 - w_plazos - 2
            self.set_fill_color(239, 246, 255)
            self.set_draw_color(147, 197, 253)
            self.rect(xl, y_plazos, wl, 9.3, "DF")
            self.set_xy(xl + 1.5, y_plazos + 0.9)
            self.set_font("Helvetica", "B", 6.5)
            self.set_text_color(30, 58, 138)
            self.cell(wl - 3, 3.0, limpiar_texto_pdf("LIDER TOP 10"), new_x="LMARGIN", new_y="NEXT")
            self.set_x(xl + 1.5)
            self.set_font("Helvetica", "B", 7.0)
            self.set_text_color(15, 23, 42)
            self.cell(wl - 3, 3.0, limpiar_texto_pdf(f"{emp['ticker']} (${emp['precio']:,.2f})"), new_x="LMARGIN", new_y="NEXT")
            self.set_x(xl + 1.5)
            self.set_font("Helvetica", "", 6.3)
            self.set_text_color(51, 65, 85)
            self.cell(wl - 3, 2.9, limpiar_texto_pdf(f"Fuente: {emp['fuente_precio']}"))

        self.set_y(y_plazos + 10.2)
        self.set_x(x0 + 1.5)
        cg_txt = _fmt_num(emp["crec_ganancias"], "%", signed=True, fallback_txt="No reportado")
        ci_txt = _fmt_num(emp["crec_ingresos"], "%", signed=True, fallback_txt="No reportado")
        crec_linea = f"Crecimiento del negocio: Ganancias {cg_txt} | Ingresos {ci_txt} | Fecha dato: {emp['fecha_dato']}"
        crec_aj, crec_sz = self._ajustar_cadena_a_ancho(
            crec_linea, "Helvetica", "B", 7.1, w0 - 3.0, min_tam=5.9
        )
        self.set_font("Helvetica", "B", crec_sz)
        self.set_text_color(30, 41, 59)
        self.cell(w0 - 3, 3.7, crec_aj, new_x="LMARGIN", new_y="NEXT")

        self.set_x(x0 + 1.5)
        lec_linea = f"Lectura: {emp['lectura']}"
        lec_aj, lec_sz = self._ajustar_cadena_a_ancho(
            lec_linea, "Helvetica", "", 7.0, w0 - 3.0, min_tam=5.8
        )
        self.set_font("Helvetica", "", lec_sz)
        self.set_text_color(71, 85, 105)
        self.cell(w0 - 3, 3.7, lec_aj, new_x="LMARGIN", new_y="NEXT")
        self.set_y(self.get_y() + 1.8)

    def bloque_proyeccion_empresa(self, emp: dict):
        if self.get_y() > 244:
            self.add_page()
        x0 = self.l_margin
        y0 = self.get_y()
        w0 = self.ancho_util

        self.set_fill_color(248, 250, 252)
        self.set_draw_color(203, 213, 225)
        self.rect(x0, y0, w0, 14.2, "DF")

        tit_aj, tit_sz = self._ajustar_cadena_a_ancho(
            emp["fase_titulo"], "Helvetica", "B", 7.8, w0 - 5.0, min_tam=6.2
        )
        self.set_xy(x0 + 2.5, y0 + 1.4)
        self.set_font("Helvetica", "B", tit_sz)
        self.set_text_color(15, 23, 42)
        self.cell(w0 - 5, 3.8, tit_aj, new_x="LMARGIN", new_y="NEXT")

        self.set_x(x0 + 2.5)
        self.set_font("Helvetica", "", 7.2)
        self.set_text_color(51, 65, 85)
        self.multi_cell(w0 - 5, 3.6, limpiar_texto_pdf(emp["fase_desc"]))
        self.set_y(y0 + 15.8)

    def bloque_fundamental_empresa(self, emp: dict):
        if self.get_y() > 246:
            self.add_page()
        x0 = self.l_margin
        y0 = self.get_y()
        w0 = self.ancho_util

        self.set_fill_color(248, 250, 252)
        self.set_draw_color(203, 213, 225)
        self.rect(x0, y0, w0, 11.6, "DF")

        nom_aj, nom_sz = self._ajustar_cadena_a_ancho(
            f"{emp['nombre']} ({emp['ticker']})", "Helvetica", "B", 7.9, w0 - 5.0, min_tam=6.4
        )
        self.set_xy(x0 + 2.5, y0 + 1.3)
        self.set_font("Helvetica", "B", nom_sz)
        self.set_text_color(15, 23, 42)
        self.cell(w0 - 5, 3.8, nom_aj, new_x="LMARGIN", new_y="NEXT")

        cap_txt = _fmt_miles_millones(emp.get("cap_mercado"), fallback_txt="No informada")
        pe_txt = f"{float(emp['pe']):.1f}x" if emp.get("pe") is not None else "No aplica/s.d."
        fpe_txt = f"{float(emp['pe_futuro']):.1f}x" if emp.get("pe_futuro") is not None else "No aplica/s.d."
        pm_txt = _fmt_num(emp.get("margen_neto"), "%", signed=True, fallback_txt="No reportado")
        de_txt = f"{float(emp['deuda_patrimonio']):.1f}%" if emp.get("deuda_patrimonio") is not None else "No reportado"
        fcf_txt = _fmt_miles_millones(emp.get("caja_libre"), fallback_txt="No reportado")

        linea_met = (
            f"Cap. Mercado: {cap_txt} | P/E: {pe_txt} | P/E Futuro: {fpe_txt} | "
            f"Margen Neto: {pm_txt} | Deuda/Patrimonio: {de_txt} | Caja Libre: {fcf_txt}"
        )
        met_aj, met_sz = self._ajustar_cadena_a_ancho(
            linea_met, "Helvetica", "", 6.9, w0 - 5.0, min_tam=5.5
        )
        self.set_x(x0 + 2.5)
        self.set_font("Helvetica", "", met_sz)
        self.set_text_color(51, 65, 85)
        self.cell(w0 - 5, 4.0, met_aj, new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + 13.3)


def construir_pdf_reporte(
    bloques: list[dict],
    indices: list[dict],
    graficos_por_bloque: dict[str, dict[str, str]],
    noticias: list[dict],
    conteo_noticias: dict,
    fecha_utc: str,
) -> str:
    pdf = InstitutionalTechBriefPDF(fecha_utc=fecha_utc)
    pdf.add_page()
    pdf.cabecera_reporte_y_indices(indices)

    for idx_u, bloque in enumerate(bloques):
        if idx_u > 0:
            pdf.add_page()
        pdf.banner_universo(bloque["titulo_bloque"], bloque["subtitulo_universo"])

        pdf.titulo_seccion_numerada(
            "1",
            f"Ranking Top 10 y Comparativas ({bloque['titulo_bloque']})",
            "Seleccion dinamica en tiempo real a traves de horizontes multitemporales.",
        )
        for idx, emp in enumerate(bloque["empresas"]):
            pdf.tarjeta_empresa_ranking(emp, es_lider=(idx == 0))

        graficos = graficos_por_bloque.get(bloque["clave"], {})
        pdf.add_page()
        pdf.titulo_seccion_numerada(
            "2",
            f"Analisis Grafico Tecnico ({bloque['titulo_bloque']})",
            "Mapa de calor multitemporal y matriz crecimiento / traccion vs. impulso.",
        )
        if graficos.get("calor") and os.path.exists(graficos["calor"]):
            pdf.set_x(pdf.l_margin + 2)
            pdf.image(graficos["calor"], w=pdf.ancho_util - 4)
            pdf.ln(2.5)
        if graficos.get("matriz") and os.path.exists(graficos["matriz"]):
            pdf.set_x(pdf.l_margin + 2)
            pdf.image(graficos["matriz"], w=pdf.ancho_util - 4)
            pdf.ln(2)

        pdf.add_page()
        pdf.titulo_seccion_numerada(
            "3",
            f"Proyeccion y Escenarios ({bloque['titulo_bloque']})",
            "Diagnostico dinamico por empresa segun comportamiento real de horizontes.",
        )
        for emp in bloque["empresas"]:
            pdf.bloque_proyeccion_empresa(emp)

        pdf.add_page()
        pdf.titulo_seccion_numerada(
            "4",
            f"Resumen Fundamental ({bloque['titulo_bloque']})",
            "Capitalizacion, valoracion P/E y P/E futuro, margen neto, endeudamiento y caja libre en vivo.",
        )
        for emp in bloque["empresas"]:
            pdf.bloque_fundamental_empresa(emp)

    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(
        pdf.ancho_util,
        4.5,
        limpiar_texto_pdf("Radar Informativo Consolidado (AlphaVantage, Finnhub, MarketStack, Massive, Marketaux, NewsAPI, NewsData)"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    if noticias:
        for n in noticias[:8]:
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 7.2)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(
                pdf.ancho_util,
                3.6,
                limpiar_texto_pdf(f"* [{n['fuente']}] {n['titulo']}"),
            )
    else:
        activas = [f"{k}: {v}" for k, v in conteo_noticias.items()]
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 7.2)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(
            pdf.ancho_util,
            4.0,
            limpiar_texto_pdf(f"Estado conectores noticias -> {', '.join(activas)}"),
        )

    ruta_pdf = "Fimothy_Institutional_Tech_Report.pdf"
    if os.path.exists(ruta_pdf):
        os.remove(ruta_pdf)
    pdf.output(ruta_pdf)
    return ruta_pdf


def enviar_pdf_telegram(ruta_pdf: str, fecha_utc: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"Aviso: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados ({ruta_pdf}).")
        return

    caption = limpiar_texto_pdf(
        f"Fimothy Institutional Tech Report\n"
        f"Emision: {fecha_utc}"
    )[:1000]

    with open(ruta_pdf, "rb") as doc:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"document": doc},
            timeout=60,
        )
        resp.raise_for_status()
    print(f"PDF enviado correctamente a Telegram: {ruta_pdf}")


def main() -> None:
    fecha_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Iniciando lectura 100% dinamica del mercado: {fecha_utc}")
    indices = obtener_indices_cabecera()
    bloques = construir_universos_dinamicos()

    todos_tickers = []
    for b in bloques:
        todos_tickers.extend([e["ticker"] for e in b["empresas"]])
    noticias, conteo_noticias = recolectar_noticias_fuentes(list(dict.fromkeys(todos_tickers)))

    graficos_por_bloque = {}
    for bloque in bloques:
        graficos_por_bloque[bloque["clave"]] = generar_graficos_universo(bloque)

    ruta_pdf = construir_pdf_reporte(
        bloques=bloques,
        indices=indices,
        graficos_por_bloque=graficos_por_bloque,
        noticias=noticias,
        conteo_noticias=conteo_noticias,
        fecha_utc=fecha_utc,
    )
    enviar_pdf_telegram(ruta_pdf, fecha_utc)
    print(f"Reporte dinamico generado y enviado: {ruta_pdf}")


if __name__ == "__main__":
    main()
