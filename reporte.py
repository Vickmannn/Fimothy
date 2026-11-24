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
# 1. VARIABLES DE ENTORNO (GITHUB SECRETS - FUENTES ACTIVAS + TELEGRAM)
# ==============================================================================
ALPHA_VANTAGE_KEY = (
    os.environ.get("ALPHAVANTAGE_API_KEY")
    or os.environ.get("ALPHA_VANTAGE_API_KEY")
)
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
MARKETSTACK_KEY = os.environ.get("MARKETSTACK_API_KEY")
MASSIVE_KEY = os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
TWELVEDATA_KEY = os.environ.get("TWELVEDATA_API_KEY")
FMP_KEY = os.environ.get("FMP_API_KEY")

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
    """
    Obtiene dinamicamente los simbolos mas activos y relevantes de la jornada
    desde Alpha Vantage, Massive/Polygon, Finnhub, FMP y MarketStack.
    """
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

    # 1. Alpha Vantage: TOP_GAINERS_LOSERS
    if ALPHA_VANTAGE_KEY:
        try:
            resp = requests.get(
                "https://www.alphavantage.co/query",
                params={"function": "TOP_GAINERS_LOSERS", "apikey": ALPHA_VANTAGE_KEY},
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
            print(f"[Descubrimiento AV] Aviso: {exc}")

    # 2. Massive / Polygon: Snapshot completo del mercado estadounidense ordenado por flujo
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
            for item in tickers_snap[:45]:
                day = item.get("day") or {}
                _registrar(
                    ticker=item.get("ticker", ""),
                    volumen=float(day.get("v") or 0),
                    precio=float(day.get("c") or (item.get("prevDay") or {}).get("c") or 0),
                )
        except Exception as exc:
            print(f"[Descubrimiento Massive] Aviso: {exc}")

    # 3. Finnhub: Constituyentes de indices (^NDX, ^GSPC, ^RUT)
    if FINNHUB_KEY:
        for idx_sym, exch_hint in [("^NDX", "NASDAQ"), ("^GSPC", "NYSE"), ("^RUT", "RUSSELL")]:
            try:
                resp = requests.get(
                    "https://finnhub.io/api/v1/index/constituents",
                    params={"symbol": idx_sym, "token": FINNHUB_KEY},
                    timeout=15,
                )
                const = resp.json().get("constituents", [])
                for tk in const[:20]:
                    _registrar(ticker=tk, exchange=exch_hint)
            except Exception:
                pass

    # 4. FMP: Activos mas negociados del dia
    if FMP_KEY and len(candidatos) < 25:
        for ep, exch_hint in [
            ("https://financialmodelingprep.com/api/v3/stock_market/actives", ""),
            ("https://financialmodelingprep.com/api/v3/stock_market/gainers", ""),
        ]:
            try:
                resp = requests.get(ep, params={"apikey": FMP_KEY}, timeout=15)
                datos = resp.json()
                if isinstance(datos, list):
                    for item in datos[:15]:
                        _registrar(
                            ticker=item.get("symbol", ""),
                            nombre=item.get("name", ""),
                            exchange=exch_hint,
                            precio=float(item.get("price") or 0),
                        )
            except Exception:
                pass

    # 5. MarketStack (APILayer v2 con respaldo v1): Activos listados en XNAS / XNYS
    if MARKETSTACK_KEY and len(candidatos) < 30:
        for mic, exch_hint in [("XNAS", "NASDAQ"), ("XNYS", "NYSE")]:
            for url_tk in (
                "https://api.apilayer.net/marketstack/v2/tickers",
                "http://api.marketstack.com/v1/tickers",
            ):
                try:
                    resp = requests.get(
                        url_tk,
                        params={"access_key": MARKETSTACK_KEY, "exchange": mic, "limit": 25},
                        timeout=20,
                    )
                    filas = resp.json().get("data", [])
                    if filas:
                        for item in filas:
                            _registrar(
                                ticker=item.get("symbol", ""),
                                nombre=item.get("name", ""),
                                exchange=exch_hint,
                            )
                        break
                except Exception:
                    pass

    # 6. Respaldo en vivo si los listados masivos vienen vacios: consulta indices y tickers en fuentes activas
    if not candidatos:
        semilla_consulta = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "JPM", "XOM", "QQQ", "SPY", "IWM"]
        for tk in semilla_consulta:
            if serie_finnhub(tk) or serie_alpaca(tk) or serie_twelvedata(tk) or serie_marketstack(tk) or serie_fmp(tk):
                _registrar(ticker=tk, volumen=1.0)

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
    if (not perfil["nombre"] or perfil["nombre"] == ticker or perfil["cap_mercado"] is None) and FMP_KEY:
        try:
            resp = requests.get(
                f"https://financialmodelingprep.com/api/v3/profile/{ticker}",
                params={"apikey": FMP_KEY},
                timeout=12,
            )
            arr = resp.json()
            if isinstance(arr, list) and arr:
                p = arr[0]
                if p.get("companyName") and perfil["nombre"] == ticker:
                    perfil["nombre"] = str(p["companyName"])
                if p.get("exchangeShortName") and not perfil["exchange"]:
                    perfil["exchange"] = str(p["exchangeShortName"]).upper()
                if p.get("mktCap") and perfil["cap_mercado"] is None:
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


def serie_alpaca(ticker: str) -> dict | None:
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None
    try:
        desde = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=410)).strftime("%Y-%m-%dT00:00:00Z")
        resp = requests.get(
            f"https://data.alpaca.markets/v2/stocks/{ticker}/bars",
            headers={
                "APCA-API-KEY-ID": ALPACA_API_KEY,
                "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
            },
            params={"timeframe": "1Day", "start": desde, "limit": 300, "feed": "iex", "sort": "desc"},
            timeout=20,
        )
        barras = resp.json().get("bars", [])
        if not barras:
            return None
        cierres = [float(b["c"]) for b in barras if b.get("c") and float(b["c"]) > 0]
        if not cierres:
            return None
        evol = _calcular_evolucion(cierres)
        fecha_bar = str(barras[0].get("t", ""))[:10] or datetime.date.today().isoformat()
        return {
            "precio": cierres[0],
            "var_1d": evol.get("1D", 0.0),
            "evolucion": evol,
            "fecha": fecha_bar,
            "fuente": "Alpaca",
        }
    except Exception:
        return None


def serie_twelvedata(ticker: str) -> dict | None:
    if not TWELVEDATA_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.twelvedata.com/time_series",
            params={"symbol": ticker, "interval": "1day", "outputsize": 270, "apikey": TWELVEDATA_KEY},
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


def serie_fmp(ticker: str) -> dict | None:
    if not FMP_KEY:
        return None
    try:
        resp = requests.get(
            f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}",
            params={"apikey": FMP_KEY},
            timeout=20,
        )
        hist = resp.json().get("historical", [])
        if not hist:
            return None
        cierres = [float(h["close"]) for h in hist[:270] if h.get("close") and float(h["close"]) > 0]
        if not cierres:
            return None
        evol = _calcular_evolucion(cierres)
        return {
            "precio": cierres[0],
            "var_1d": evol.get("1D", 0.0),
            "evolucion": evol,
            "fecha": str(hist[0].get("date", ""))[:10],
            "fuente": "FMP",
        }
    except Exception:
        return None


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


def serie_marketstack(ticker: str) -> dict | None:
    if not MARKETSTACK_KEY:
        return None
    for url_eod in (
        "https://api.apilayer.net/marketstack/v2/eod",
        "http://api.marketstack.com/v1/eod",
    ):
        try:
            resp = requests.get(
                url_eod,
                params={"access_key": MARKETSTACK_KEY, "symbols": ticker, "limit": 270},
                timeout=20,
            )
            filas = resp.json().get("data", [])
            if not filas:
                continue
            cierres = [float(x["close"]) for x in filas if x.get("close") and float(x["close"]) > 0]
            if not cierres:
                continue
            evol = _calcular_evolucion(cierres)
            return {
                "precio": cierres[0],
                "var_1d": evol.get("1D", 0.0),
                "evolucion": evol,
                "fecha": str(filas[0].get("date", ""))[:10],
                "fuente": "MarketStack",
            }
        except Exception:
            continue
    return None


def serie_alpha_vantage(ticker: str) -> dict | None:
    if not ALPHA_VANTAGE_KEY:
        return None
    time.sleep(0.35)
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "full",
                "apikey": ALPHA_VANTAGE_KEY,
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
            "fuente": "Alpha Vantage",
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

        def _f(campo: str) -> float | None:
            val = m.get(campo)
            if val is None:
                return None
            try:
                return float(val)
            except Exception:
                return None

        pe = _f("peTTM") or _f("peBasicExclExtraTTM")
        fwd_pe = _f("forwardPE")
        pm = _f("netProfitMarginTTM") or _f("netProfitMarginAnnual")
        eps_g = _f("epsGrowthTTMYOY") or _f("epsGrowthQuarterlyYOY")
        rev_g = _f("revenueGrowthTTMYOY") or _f("revenueGrowthQuarterlyYOY")
        deuda_eq = _f("totalDebt/totalEquityQuarterly") or _f("totalDebt/totalEquityAnnual")
        mcap_m = _f("marketCapitalization")
        mcap = mcap_m * 1e6 if mcap_m is not None else None
        fcf_ps = _f("freeCashFlowPerShareTTM")
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


def fundamentales_fmp(ticker: str) -> dict:
    if not FMP_KEY:
        return {}
    try:
        resp = requests.get(
            f"https://financialmodelingprep.com/api/v3/ratios-ttm/{ticker}",
            params={"apikey": FMP_KEY},
            timeout=15,
        )
        arr = resp.json()
        if not isinstance(arr, list) or not arr:
            return {}
        r = arr[0]

        def _f(campo: str, mult: float = 1.0) -> float | None:
            val = r.get(campo)
            if val is None:
                return None
            try:
                return float(val) * mult
            except Exception:
                return None

        return {
            "pe": _f("peRatioTTM"),
            "margen_neto": _f("netProfitMarginTTM", 100.0),
            "deuda_patrimonio": _f("debtEquityRatioTTM", 100.0),
            "fuente_fund": "FMP",
        }
    except Exception:
        return {}


def fundamentales_alpha_vantage(ticker: str) -> dict:
    if not ALPHA_VANTAGE_KEY:
        return {}
    time.sleep(0.35)
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "OVERVIEW", "symbol": ticker, "apikey": ALPHA_VANTAGE_KEY},
            timeout=20,
        )
        ov = resp.json()
        if not ov or "Symbol" not in ov:
            return {}

        def _f(campo: str, mult: float = 1.0) -> float | None:
            raw = ov.get(campo)
            if raw in (None, "", "None", "-"):
                return None
            try:
                return float(raw) * mult
            except Exception:
                return None

        return {
            "nombre": ov.get("Name"),
            "exchange": ov.get("Exchange"),
            "cap_mercado": _f("MarketCapitalization"),
            "pe": _f("PERatio"),
            "pe_futuro": _f("ForwardPE"),
            "margen_neto": _f("ProfitMargin", 100.0),
            "crec_ganancias": _f("QuarterlyEarningsGrowthYOY", 100.0),
            "crec_ingresos": _f("QuarterlyRevenueGrowthYOY", 100.0),
            "deuda_patrimonio": _f("DebtToEquityRatio"),
            "caja_libre": _f("OperatingCashflow"),
            "fuente_fund": "Alpha Vantage",
        }
    except Exception:
        return {}


def noticias_alpha_vantage() -> list[dict]:
    if not ALPHA_VANTAGE_KEY:
        return []
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "topics": "technology,financial_markets",
                "limit": 6,
                "apikey": ALPHA_VANTAGE_KEY,
            },
            timeout=20,
        )
        items = resp.json().get("feed", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"Alpha Vantage ({i.get('source', 'Mercado')})",
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


def recolectar_noticias_7_fuentes(tickers_ref: list[str]) -> tuple[list[dict], dict]:
    fuentes = {
        "Alpha Vantage": noticias_alpha_vantage(),
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
# 5. EVALUACION 100 % REAL Y CLASIFICACION DINAMICA POR UNIVERSO
# ==============================================================================
def evaluar_activo_real(candidato: dict) -> dict | None:
    ticker = candidato["ticker"]
    orden_series = [
        serie_alpaca,
        serie_finnhub,
        serie_twelvedata,
        serie_massive,
        serie_fmp,
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
        for fn_extra in (serie_twelvedata, serie_fmp, serie_marketstack, serie_alpha_vantage):
            if fn_extra.__name__.lower().replace("serie_", "") in serie["fuente"].lower().replace(" ", "_"):
                continue
            extra = fn_extra(ticker)
            if extra and extra.get("evolucion"):
                for k, v in extra["evolucion"].items():
                    evol.setdefault(k, v)
                break

    perfil = enriquecer_perfil_dinamico(ticker)
    fh_fund = fundamentales_finnhub(ticker)
    fmp_fund = fundamentales_fmp(ticker)
    av_fund = fundamentales_alpha_vantage(ticker)

    fund = {}
    for fuente_d in (fh_fund, fmp_fund, av_fund):
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
        partes_lectura.append(f"Variacion diaria: {var_1d:+.2f}% (fuente: {serie['fuente']})")

    if deuda_eq is not None:
        d_val = float(deuda_eq)
        if d_val > 120:
            partes_lectura.append(f"apalancamiento elevado ({d_val:.1f}%)")
        elif d_val > 55:
            partes_lectura.append(f"deuda moderada ({d_val:.1f}%)")
        else:
            partes_lectura.append(f"endeudamiento contenido ({d_val:.1f}%)")

    if caja_libre is not None:
        c_val = float(caja_libre)
        if c_val >= 0:
            partes_lectura.append(f"flujo de caja positivo ({_fmt_miles_millones(c_val)})")
        else:
            partes_lectura.append(f"flujo de caja negativo ({_fmt_miles_millones(c_val)})")

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


def construir_universos_dinamicos() -> list[dict]:
    candidatos = descubrir_candidatos_mercado()
    evaluados: list[dict] = []

    for cand in candidatos[:40]:
        activo = evaluar_activo_real(cand)
        if activo:
            evaluados.append(activo)

    if not evaluados:
        raise RuntimeError(
            "Ninguna API devolvio precios reales hoy. Revisa las API Keys en GitHub Secrets y el mapeo env en tu workflow."
        )

    nasdaq_pool = [
        a for a in evaluados
        if "NASDAQ" in a["exchange"] or "XNAS" in a["exchange"]
    ]
    sp500_pool = [
        a for a in evaluados
        if (a["cap_mercado"] is not None and float(a["cap_mercado"]) >= 10e9)
        or "NYSE" in a["exchange"]
        or "XNYS" in a["exchange"]
    ]
    russell_pool = [
        a for a in evaluados
        if (a["cap_mercado"] is not None and float(a["cap_mercado"]) < 10e9)
        or "RUSSELL" in a["exchange"]
    ]

    def _top10_dinamico(pool_primario: list[dict], respaldo_real: list[dict]) -> list[dict]:
        ordenado = sorted(pool_primario, key=lambda x: x["score"], reverse=True)
        vistos = {x["ticker"] for x in ordenado}
        if len(ordenado) < 10:
            extras = sorted(
                [x for x in respaldo_real if x["ticker"] not in vistos],
                key=lambda x: x["score"],
                reverse=True,
            )
            ordenado.extend(extras[: 10 - len(ordenado)])
        top = [dict(x) for x in ordenado[:10]]
        for idx, emp in enumerate(top, start=1):
            emp["rank"] = idx
        return top

    nasdaq_top = _top10_dinamico(nasdaq_pool, evaluados)
    sp500_top = _top10_dinamico(sp500_pool, sorted(evaluados, key=lambda x: float(x["cap_mercado"] or 0), reverse=True))
    russell_top = _top10_dinamico(russell_pool, sorted(evaluados, key=lambda x: float(x["cap_mercado"] or 1e15)))

    definiciones = [
        {
            "clave": "nasdaq",
            "titulo_bloque": "NASDAQ TOP 10",
            "subtitulo_universo": "Seleccion dinamica en vivo: Activos lideres en Nasdaq por actividad y traccion",
            "prefijo_archivo": "nasdaq",
            "empresas": nasdaq_top,
        },
        {
            "clave": "sp500",
            "titulo_bloque": "S&P 500 TOP 10",
            "subtitulo_universo": "Seleccion dinamica en vivo: Gran capitalizacion en tiempo real",
            "prefijo_archivo": "sp500",
            "empresas": sp500_top,
        },
        {
            "clave": "russell2000",
            "titulo_bloque": "RUSSELL 2000 TOP 10",
            "subtitulo_universo": "Seleccion dinamica en vivo: Pequena y mediana capitalizacion activa",
            "prefijo_archivo": "russell2000",
            "empresas": russell_top,
        },
    ]

    for b in definiciones:
        b["lider"] = b["empresas"][0] if b["empresas"] else None
        print(f"[{b['titulo_bloque']}] Top 10 dinamico de hoy: {[e['ticker'] for e in b['empresas']]}")

    return definiciones


def obtener_indices_cabecera() -> list[dict]:
    orden_idx = [
        serie_finnhub,
        serie_alpaca,
        serie_twelvedata,
        serie_massive,
        serie_fmp,
        serie_marketstack,
        serie_alpha_vantage,
    ]
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
def generar_graficos_universo(bloque: dict) -> dict[str, str]:
    empresas = bloque["empresas"]
    prefijo = bloque["prefijo_archivo"]
    plazos = [etq for etq, _ in PLAZOS_EVOLUTIVOS]

    matriz_calor = np.array([
        [float(emp["evolucion"][p]) if emp["evolucion"].get(p) is not None else np.nan for p in plazos]
        for emp in empresas
    ])
    etiquetas_y = [f"{emp['rank']}. {emp['ticker']}" for emp in empresas]

    fig, ax = plt.subplots(figsize=(8.2, 3.8))
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
    ax.set_title(
        f"Mapa de Calor Multitemporal ({bloque['titulo_bloque']})",
        fontsize=9.2,
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
    plt.tight_layout()
    ruta_calor = f"mapa_calor_{prefijo}.png"
    plt.savefig(ruta_calor, dpi=180)
    plt.close(fig)

    crec_x = [float(emp["crec_prom"]) if emp["crec_prom"] is not None else float(emp["var_1d"]) for emp in empresas]
    imp_y = [float(emp["impulso_prom"]) for emp in empresas]
    scores = [float(emp["score"]) for emp in empresas]
    tamanos = [max(90.0, min(420.0, abs(s) * 2.5 + 90.0)) for s in scores]

    fig2, ax2 = plt.subplots(figsize=(8.2, 4.0))
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
            fontsize=7.5,
            fontweight="bold",
            color="#0F172A",
        )

    ax2.set_title(
        f"FIMOTHY QUANT - Matriz Crecimiento / Traccion vs. Impulso ({bloque['titulo_bloque']})",
        fontsize=9.2,
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
    plt.tight_layout()
    ruta_matriz = f"matriz_cuant_{prefijo}.png"
    plt.savefig(ruta_matriz, dpi=180)
    plt.close(fig2)

    return {"calor": ruta_calor, "matriz": ruta_matriz}


# ==============================================================================
# 7. MAQUETACION EN PDF
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

    def header(self):
        self.set_fill_color(248, 250, 252)
        self.rect(0, 0, 210, 17, "F")
        self.set_draw_color(203, 213, 225)
        self.set_line_width(0.4)
        self.line(12, 17, 198, 17)

        self.set_xy(12, 4.5)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(15, 23, 42)
        self.cell(95, 5, limpiar_texto_pdf("FIMOTHY"), new_x="RIGHT", new_y="TOP")

        self.set_xy(107, 4.5)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(30, 58, 138)
        self.cell(91, 5, limpiar_texto_pdf("INSTITUTIONAL TECH REPORT"), align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_xy(12, 9.5)
        self.set_font("Helvetica", "B", 6.8)
        self.set_text_color(100, 116, 139)
        self.cell(95, 4, limpiar_texto_pdf("FINANCIAL ENTERPRISE"), new_x="RIGHT", new_y="TOP")

        self.set_xy(107, 9.5)
        self.set_font("Helvetica", "", 7.2)
        self.set_text_color(71, 85, 105)
        self.cell(
            91,
            4,
            limpiar_texto_pdf(f"FIMOTHY RESEARCH | {self.universo_actual}"),
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )
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
        self.set_font("Helvetica", "B", 16.0)
        self.set_text_color(15, 23, 42)
        self.cell(
            self.ancho_util,
            7.2,
            limpiar_texto_pdf("Radar Dinamico Top 10: Nasdaq, S&P 500 y Russell 2000"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 8.3)
        self.set_text_color(71, 85, 105)
        self.cell(
            self.ancho_util,
            4.8,
            limpiar_texto_pdf(
                f"Emision: {self.fecha_utc} | Lectura 100% en vivo | Horizontes multitemporales activos"
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
            self.set_font("Helvetica", "B", 6.7)
            self.set_text_color(100, 116, 139)
            self.cell(w_card - 5, 3.4, limpiar_texto_pdf(idx_item["etiqueta"]), new_x="LMARGIN", new_y="NEXT")

            self.set_x(x + 2.5)
            self.set_font("Helvetica", "B", 10.2)
            self.set_text_color(15, 23, 42)
            p_txt = f"{idx_item['precio']:,.2f}" if idx_item["precio"] is not None else "N/D"
            self.cell(w_card - 5, 5.0, limpiar_texto_pdf(p_txt), new_x="LMARGIN", new_y="NEXT")

            self.set_x(x + 2.5)
            self.set_font("Helvetica", "B", 7.4)
            v1d = idx_item["var_1d"]
            if v1d is None:
                self.set_text_color(100, 116, 139)
                v_txt = "Variacion 1D: N/D"
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
        self.rect(x0, y0, w0, 11.5, "DF")

        self.set_xy(x0 + 3, y0 + 1.5)
        self.set_font("Helvetica", "B", 9.8)
        self.set_text_color(255, 255, 255)
        self.cell(w0 - 6, 4.2, limpiar_texto_pdf(titulo_bloque), new_x="LMARGIN", new_y="NEXT")

        self.set_x(x0 + 3)
        self.set_font("Helvetica", "", 7.3)
        self.set_text_color(203, 213, 225)
        self.cell(w0 - 6, 3.8, limpiar_texto_pdf(subtitulo_universo), new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + 13.8)

    def titulo_seccion_numerada(self, num_str: str, titulo: str, bajada: str):
        if self.get_y() > 245:
            self.add_page()
        self.set_x(self.l_margin)
        self.set_fill_color(30, 58, 138)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 8.5)
        self.cell(6.5, 6, limpiar_texto_pdf(num_str), align="C", fill=True, new_x="RIGHT", new_y="TOP")

        self.set_xy(self.l_margin + 8, self.get_y())
        self.set_font("Helvetica", "B", 11.5)
        self.set_text_color(15, 23, 42)
        self.cell(self.ancho_util - 8, 6, limpiar_texto_pdf(titulo), new_x="LMARGIN", new_y="NEXT")

        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 8.0)
        self.set_text_color(100, 116, 139)
        self.cell(self.ancho_util, 4.3, limpiar_texto_pdf(bajada), new_x="LMARGIN", new_y="NEXT")

        self.set_draw_color(203, 213, 225)
        self.line(self.l_margin, self.get_y() + 1, self.l_margin + self.ancho_util, self.get_y() + 1)
        self.ln(2.8)

    def tarjeta_empresa_ranking(self, emp: dict, es_lider: bool = False):
        if self.get_y() > 232:
            self.add_page()

        x0 = self.l_margin
        y0 = self.get_y()
        w0 = self.ancho_util
        evol = emp.get("evolucion") or {}
        plazos = [etq for etq, _ in PLAZOS_EVOLUTIVOS]

        self.set_fill_color(241, 245, 249)
        self.set_draw_color(203, 213, 225)
        self.rect(x0, y0, w0, 6.0, "DF")

        self.set_xy(x0 + 2, y0 + 1.0)
        self.set_font("Helvetica", "B", 8.3)
        self.set_text_color(15, 23, 42)
        self.cell(112, 4, limpiar_texto_pdf(f"#{emp['rank']} {emp['nombre']} ({emp['ticker']})"), new_x="RIGHT", new_y="TOP")

        self.set_font("Helvetica", "B", 8.0)
        self.set_text_color(30, 58, 138)
        self.cell(42, 4, limpiar_texto_pdf(f"Precio: ${emp['precio']:,.2f}"), align="R", new_x="RIGHT", new_y="TOP")

        self.set_font("Helvetica", "B", 8.0)
        self.set_text_color(15, 23, 42)
        self.cell(w0 - 156, 4, limpiar_texto_pdf(f"Score: {emp['score']:.2f}"), align="R", new_x="LMARGIN", new_y="NEXT")

        y_plazos = y0 + 6.0
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
            self.set_font("Helvetica", "B", 6.5)
            if raw_val is None:
                self.set_text_color(100, 116, 139)
                txt_p = "N/D"
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

        self.set_y(y_plazos + 10.1)
        self.set_x(x0 + 1.5)
        self.set_font("Helvetica", "B", 7.3)
        self.set_text_color(30, 41, 59)
        cg_txt = _fmt_num(emp["crec_ganancias"], "%", signed=True)
        ci_txt = _fmt_num(emp["crec_ingresos"], "%", signed=True)
        self.cell(
            w0 - 3,
            3.7,
            limpiar_texto_pdf(
                f"Crecimiento del negocio: Ganancias {cg_txt} | Ingresos {ci_txt} | Fecha dato: {emp['fecha_dato']}"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(x0 + 1.5)
        self.set_font("Helvetica", "", 7.2)
        self.set_text_color(71, 85, 105)
        self.cell(w0 - 3, 3.7, limpiar_texto_pdf(f"Lectura: {emp['lectura']}"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2.0)

    def bloque_proyeccion_empresa(self, emp: dict):
        if self.get_y() > 246:
            self.add_page()
        x0 = self.l_margin
        y0 = self.get_y()
        w0 = self.ancho_util

        self.set_fill_color(248, 250, 252)
        self.set_draw_color(203, 213, 225)
        self.rect(x0, y0, w0, 14.0, "DF")

        self.set_xy(x0 + 2.5, y0 + 1.4)
        self.set_font("Helvetica", "B", 8.0)
        self.set_text_color(15, 23, 42)
        self.cell(w0 - 5, 3.8, limpiar_texto_pdf(emp["fase_titulo"]), new_x="LMARGIN", new_y="NEXT")

        self.set_x(x0 + 2.5)
        self.set_font("Helvetica", "", 7.4)
        self.set_text_color(51, 65, 85)
        self.multi_cell(w0 - 5, 3.7, limpiar_texto_pdf(emp["fase_desc"]))
        self.set_y(y0 + 15.8)

    def bloque_fundamental_empresa(self, emp: dict):
        if self.get_y() > 248:
            self.add_page()
        x0 = self.l_margin
        y0 = self.get_y()
        w0 = self.ancho_util

        self.set_fill_color(248, 250, 252)
        self.set_draw_color(203, 213, 225)
        self.rect(x0, y0, w0, 11.2, "DF")

        self.set_xy(x0 + 2.5, y0 + 1.3)
        self.set_font("Helvetica", "B", 8.1)
        self.set_text_color(15, 23, 42)
        self.cell(w0 - 5, 3.8, limpiar_texto_pdf(f"{emp['nombre']} ({emp['ticker']})"), new_x="LMARGIN", new_y="NEXT")

        cap_txt = _fmt_miles_millones(emp.get("cap_mercado"))
        pe_txt = f"{float(emp['pe']):.1f}x" if emp.get("pe") is not None else "N/D"
        fpe_txt = f"{float(emp['pe_futuro']):.1f}x" if emp.get("pe_futuro") is not None else "N/D"
        pm_txt = _fmt_num(emp.get("margen_neto"), "%", signed=True)
        de_txt = f"{float(emp['deuda_patrimonio']):.1f}%" if emp.get("deuda_patrimonio") is not None else "N/D"
        fcf_txt = _fmt_miles_millones(emp.get("caja_libre"))

        linea_met = (
            f"Cap. Mercado: {cap_txt} | P/E: {pe_txt} | P/E Futuro: {fpe_txt} | "
            f"Margen Neto: {pm_txt} | Deuda/Patrimonio: {de_txt} | Caja Libre: {fcf_txt}"
        )
        self.set_x(x0 + 2.5)
        self.set_font("Helvetica", "", 7.2)
        self.set_text_color(51, 65, 85)
        self.cell(w0 - 5, 4.0, limpiar_texto_pdf(linea_met), new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + 13.0)


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
            f"Ranking Top 10 y Comparativas Multitemporales ({bloque['titulo_bloque']})",
            "Seleccion dinamica ordenada por Score en tiempo real a traves de horizontes multitemporales.",
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
            f"Proyeccion y Escenarios Operativos ({bloque['titulo_bloque']})",
            "Diagnostico dinamico por empresa segun comportamiento real de horizontes.",
        )
        for emp in bloque["empresas"]:
            pdf.bloque_proyeccion_empresa(emp)

        pdf.add_page()
        pdf.titulo_seccion_numerada(
            "4",
            f"Resumen Final - Bloque Fundamental ({bloque['titulo_bloque']})",
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
        limpiar_texto_pdf("Radar Informativo Consolidado (Alpaca, Twelve Data, FMP, Alpha Vantage, Finnhub, MarketStack, Massive, Marketaux, NewsAPI, NewsData)"),
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
    noticias, conteo_noticias = recolectar_noticias_7_fuentes(list(dict.fromkeys(todos_tickers)))

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
