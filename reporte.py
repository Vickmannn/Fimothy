import datetime
import os
import re
import time
import unicodedata
import matplotlib
import requests
from fpdf import FPDF

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ==============================================================================
# 1. VARIABLES DE ENTORNO (GITHUB SECRETS - SIN IA)
# ==============================================================================
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY")
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
MARKETSTACK_KEY = os.environ.get("MARKETSTACK_API_KEY")
MASSIVE_KEY = os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
MARKETAUX_KEY = os.environ.get("MARKETAUX_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
NEWSDATA_KEY = os.environ.get("NEWSDATA_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ==============================================================================
# 2. BENCHMARKS, 10 EMPRESAS NASDAQ, 10 S&P 500, 10 RUSSELL 2000 Y SECTORIAL
# ==============================================================================
BENCHMARKS_MACRO = [
    ("SPY", "S&P 500 Index ETF"),
    ("QQQ", "Nasdaq 100 Tech ETF"),
    ("IWM", "Russell 2000 Small Caps"),
    ("TLT", "US Treasury 20+Y Bonds"),
    ("GLD", "Gold Bullion Trust"),
    ("USO", "US Oil Benchmark"),
]

TOP_10_NASDAQ = [
    ("AAPL", "Apple Inc.", "Nasdaq Top 10"),
    ("MSFT", "Microsoft Corp.", "Nasdaq Top 10"),
    ("NVDA", "NVIDIA Corp.", "Nasdaq Top 10"),
    ("AMZN", "Amazon.com Inc.", "Nasdaq Top 10"),
    ("GOOGL", "Alphabet Inc.", "Nasdaq Top 10"),
    ("META", "Meta Platforms", "Nasdaq Top 10"),
    ("AVGO", "Broadcom Inc.", "Nasdaq Top 10"),
    ("TSLA", "Tesla Inc.", "Nasdaq Top 10"),
    ("COST", "Costco Wholesale", "Nasdaq Top 10"),
    ("NFLX", "Netflix Inc.", "Nasdaq Top 10"),
]

TOP_10_SP500 = [
    ("AAPL", "Apple Inc.", "S&P 500 Top 10"),
    ("MSFT", "Microsoft Corp.", "S&P 500 Top 10"),
    ("NVDA", "NVIDIA Corp.", "S&P 500 Top 10"),
    ("AMZN", "Amazon.com Inc.", "S&P 500 Top 10"),
    ("GOOGL", "Alphabet Inc.", "S&P 500 Top 10"),
    ("META", "Meta Platforms", "S&P 500 Top 10"),
    ("BRK.B", "Berkshire Hathaway", "S&P 500 Top 10"),
    ("LLY", "Eli Lilly and Co.", "S&P 500 Top 10"),
    ("AVGO", "Broadcom Inc.", "S&P 500 Top 10"),
    ("JPM", "JPMorgan Chase & Co.", "S&P 500 Top 10"),
]

TOP_10_RUSSELL2000 = [
    ("IWM", "iShares Russell 2000 ETF", "Russell 2000 Ref."),
    ("SMCI", "Super Micro Computer", "Russell 2000 / Servidores"),
    ("IONQ", "IonQ Inc.", "Russell 2000 / Cuantica"),
    ("SOUN", "SoundHound AI", "Russell 2000 / IA Voz"),
    ("RKLB", "Rocket Lab USA", "Russell 2000 / Aeroespacial"),
    ("MARA", "MARA Holdings", "Russell 2000 / Infraestructura"),
    ("SPHR", "Sphere Entertainment", "Russell 2000 / Entretenimiento"),
    ("MOD", "Modine Manufacturing", "Russell 2000 / Termica"),
    ("FN", "Fabrinet", "Russell 2000 / Optica"),
    ("MSTR", "Strategy / MicroStrategy", "Russell 2000 / Tesoreria"),
]

UNIVERSOS_SECTORIALES = [
    {
        "nombre_foco": "Infraestructura Digital, Semiconductores y Computo",
        "activos": [
            ("NVDA", "NVIDIA Corp."),
            ("ASML", "ASML Holding"),
            ("AVGO", "Broadcom Inc."),
            ("MSFT", "Microsoft Corp."),
        ],
        "tesis_sectorial": (
            "La expansion de capacidad de calculo exige inversion intensiva en "
            "capital (CapEx), energia y litografia avanzada. El punto critico no "
            "es el crecimiento de ingresos bruto, sino el retorno sobre el capital "
            "invertido (ROIC) y la sostenibilidad de margenes frente a ciclos de inventario."
        ),
    },
    {
        "nombre_foco": "Materias Primas Estrategicas, Energia e Industria Pesada",
        "activos": [
            ("FCX", "Freeport-McMoRan (Cobre)"),
            ("XOM", "Exxon Mobil Corp."),
            ("CAT", "Caterpillar Inc."),
            ("ALB", "Albemarle Corp. (Litio)"),
        ],
        "tesis_sectorial": (
            "Los insumos fisicos y la maquinaria industrial actuan como cuello de "
            "botella real de la electrificacion y la reindustrializacion. En este "
            "segmento mandan el costo marginal de extraccion, la disciplina de deuda "
            "y el flujo de caja libre en la parte baja del ciclo."
        ),
    },
    {
        "nombre_foco": "Sistema Financiero, Liquidez y Asignadores de Capital",
        "activos": [
            ("JPM", "JPMorgan Chase & Co."),
            ("BRK.B", "Berkshire Hathaway"),
            ("GS", "Goldman Sachs Group"),
            ("BLK", "BlackRock Inc."),
        ],
        "tesis_sectorial": (
            "Las entidades financieras y grandes asignadores reflejan de inmediato "
            "la pendiente de la curva de tasas, la calidad del credito corporativo y "
            "los flujos institucionales. La solvencia patrimonial y el costo de "
            "fondeo determinan quien absorbe volatilidad y quien compra activos baratos."
        ),
    },
    {
        "nombre_foco": "Salud, Biotecnologia y Consumo Defensivo de Flujo Estable",
        "activos": [
            ("LLY", "Eli Lilly and Co."),
            ("UNH", "UnitedHealth Group"),
            ("COST", "Costco Wholesale"),
            ("PG", "Procter & Gamble"),
        ],
        "tesis_sectorial": (
            "Cuando la dispersion macroeconomica sube, los negocios con demanda "
            "inelastica, poder de fijacion de precios y baja sensibilidad al ciclo "
            "crediticio sirven como ancla de preservacion y generacion recurrente de caja."
        ),
    },
]

EDITORIALES_SEMANALES = [
    {
        "titulo": "El Pensamiento de Segundo Orden ante la Dispersion de Liquidez",
        "subtitulo": "Por que el consenso suele llegar tarde al precio y como medir asimetrias reales.",
        "cuerpo": (
            "En los mercados financieros, el analisis de primer orden reacciona al "
            "titular inmediato: si una compania supera estimaciones o un indice sube, "
            "asume continuidad lineal. El analisis institucional de segundo orden "
            "formula una pregunta distinta: cuanto de ese escenario ya esta descontado "
            "en los multiplos actuales y que ocurre con la liquidez marginal si las "
            "condiciones de tasas o credito cambian.\n\n"
            "Cuando los grandes indices avanzan mientras los segmentos sensibles al "
            "costo de financiamiento muestran debilidad, el mercado envia una senal "
            "de selectividad extrema. En ese entorno, la ventaja competitiva del "
            "analista riguroso consiste en auditar el flujo de caja libre operativo, "
            "la cobertura de intereses y el costo de oportunidad antes de comprometer capital."
        ),
        "caso_estudio": (
            "CASO DE ESTUDIO: Trampa de Multiplos vs. Calidad de Caja.\n"
            "Dos empresas del mismo sector crecen al 18% anual. La Empresa A cotiza a "
            "48x beneficios con flujo de caja libre negativo tras compensacion en "
            "acciones y deuda creciente; la Empresa B cotiza a 21x con conversion de "
            "caja superior al 85% y caja neta positiva. Ante un repunte de 40 puntos "
            "basicos en el rendimiento del bono a 10 anos, la compresion de multiplos "
            "castiga severamente a A mientras B conserva capacidad de recompra y "
            "expansion organica."
        ),
        "reglas": [
            "1. Audita conversion de beneficio neto a flujo de caja libre (FCF > 70%).",
            "2. Exige cobertura de intereses (EBIT / Gasto Financiero) superior a 4x.",
            "3. Define de antemano el nivel cuantitativo que invalida tu hipotesis.",
        ],
    },
    {
        "titulo": "Anatomia del Ciclo Crediticio y Costo del Capital",
        "subtitulo": "Como los tipos de interes reordenan las valoraciones entre duracion corta y larga.",
        "cuerpo": (
            "Todo activo financiero es, en ultima instancia, el valor presente de sus "
            "flujos de caja futuros descontados a una tasa acorde con su riesgo. "
            "Cuando el costo del dinero abandona niveles artificialmente bajos y se "
            "estabiliza en mesetas estructuralmente mas altas, la duracion financiera "
            "se convierte en el factor determinante del rendimiento.\n\n"
            "Los negocios que prometen rentabilidad a cinco o siete anos sufren una "
            "penalizacion matematica en su valor actual, mientras que las empresas con "
            "activos tangibles, poder de fijacion de precios y caja disponible hoy "
            "ganan poder estrategico para adquirir competidores debilitados."
        ),
        "caso_estudio": (
            "CASO DE ESTUDIO: Refinanciacion en Muro de Vencimientos.\n"
            "Una compania industrial con deuda estructurada al 3.2% en 2021 enfrenta "
            "vencimientos significativos que debe renovar al 6.8%. Aunque sus ventas "
            "se mantengan estables, el incremento del gasto financiero absorbe el 30% "
            "de su utilidad operativa, reduciendo el margen de seguridad para el accionista."
        ),
        "reglas": [
            "1. Revisa el calendario de vencimientos de deuda a 24 meses de cada emisor.",
            "2. Compara el rendimiento de flujo de caja libre (FCF Yield) frente al Bono 10Y.",
            "3. Evita estructuras con apalancamiento elevado en sectores ciclicos.",
        ],
    },
    {
        "titulo": "Microestructura de Mercado: Volumen, Amplitud y Ruido Informativo",
        "subtitulo": "Separar acumulacion institucional de movimientos especulativos de corto plazo.",
        "cuerpo": (
            "El flujo diario de noticias financieras esta disenado para maximizar "
            "atencion, no precision analitica. Sin embargo, los grandes participantes "
            "institucionales dejan huella cuantitativa en el volumen negociado, la "
            "amplitud del mercado y la rotacion entre sectores defensivos y ciclicos.\n\n"
            "Observar exclusivamente el precio de cierre sin verificar si el movimiento "
            "viene acompanado de participacion amplia o concentracion en unos pocos "
            "titulos conduce a lecturas distorsionadas sobre la salud real de la tendencia."
        ),
        "caso_estudio": (
            "CASO DE ESTUDIO: Divergencia entre Indice Ponderado y Amplitud.\n"
            "Durante tres semanas consecutivas, el indice principal registra maximos "
            "impulsados por cuatro megacapitalizaciones, mientras mas del 60% de las "
            "empresas medianas y pequenas operan bajo su media de 50 sesiones. Esta "
            "estrechez advierte fragilidad estructural ante cualquier toma de ganancias."
        ),
        "reglas": [
            "1. Contrasta siempre el comportamiento de SPY/QQQ frente a IWM (Small Caps).",
            "2. Valida rupturas tecnicas unicamente cuando el volumen supera su promedio.",
            "3. No operes titulares sin confirmar impacto real en ingresos o margenes.",
        ],
    },
    {
        "titulo": "Gestion de Riesgo Institucional y Preservacion del Capital",
        "subtitulo": "La asimetria matematica entre perdidas y recuperaciones en portafolios reales.",
        "cuerpo": (
            "La supervivencia y composicion de capital a largo plazo dependen mas de "
            "limitar las caidas profundas que de capturar cada tramo especulativo. "
            "Una perdida del 50% exige un rendimiento posterior del 100% solo para "
            "volver al punto de partida, consumiendo tiempo y costo de oportunidad.\n\n"
            "Por ello, el diseno de portafolio profesional combina activos generadores "
            "de flujo, cobertura frente a shocks macroeconomicos y liquidez tactica "
            "lista para desplegarse cuando el mercado liquida activos de calidad por panico."
        ),
        "caso_estudio": (
            "CASO DE ESTUDIO: Dimensionamiento por Volatilidad.\n"
            "Asignar el mismo peso nominal a un bono del Tesoro y a una accion de alta "
            "beta produce un portafolio dominado en mas del 85% por el riesgo de la "
            "accion. Ajustar el tamano de posicion segun volatilidad equilibra la "
            "contribucion al riesgo total."
        ),
        "reglas": [
            "1. Limita el riesgo maximo por tesis individual a un porcentaje fijo del capital.",
            "2. Mantiene activos descorrelacionados (liquidez, bonos, materias primas).",
            "3. Revisa trimestralmente si los fundamentos originales siguen vigentes.",
        ],
    },
]

PLAZOS_EVOLUTIVOS = [
    ("1D", 1),
    ("2D", 2),
    ("3D", 3),
    ("1S", 5),
    ("15D", 11),
    ("1M", 21),
    ("3M", 63),
]


def obtener_configuracion_semanal() -> tuple[int, dict, dict]:
    hoy = datetime.date.today()
    num_edicion = hoy.isocalendar()[1]
    editorial = EDITORIALES_SEMANALES[num_edicion % len(EDITORIALES_SEMANALES)]
    universo = UNIVERSOS_SECTORIALES[num_edicion % len(UNIVERSOS_SECTORIALES)]
    return num_edicion, editorial, universo


def limpiar_texto_pdf(texto: str) -> str:
    """Limpia Markdown basico y normaliza caracteres para compatibilidad con FPDF."""
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
    }
    for orig, dest in reemplazos.items():
        texto = texto.replace(orig, dest)
    normalizado = unicodedata.normalize("NFKD", texto)
    return normalizado.encode("latin-1", "ignore").decode("latin-1")


# ==============================================================================
# 3. CONECTORES MULTIFUENTE DE DATOS DE MERCADO (7 FUENTES INTEGRADA EN PRECIOS)
# ==============================================================================
def _calcular_evolucion_desde_cierres(cierres_recientes_primero: list[float]) -> dict[str, float]:
    """
    Recibe una lista de precios de cierre ordenados del mas reciente al mas antiguo.
    Calcula variaciones porcentuales para 1D, 2D, 3D, 1S, 15D, 1M y 3M con respaldo
    progresivo si la serie historica devuelta por el proveedor es mas corta.
    """
    if not cierres_recientes_primero or len(cierres_recientes_primero) < 2:
        return {}
    actual = float(cierres_recientes_primero[0])
    if actual <= 0:
        return {}
    n = len(cierres_recientes_primero)
    evolucion: dict[str, float] = {}
    for etiqueta, pasos in PLAZOS_EVOLUTIVOS:
        idx = min(pasos, n - 1)
        ref = float(cierres_recientes_primero[idx])
        if ref > 0:
            evolucion[etiqueta] = ((actual - ref) / ref) * 100.0
    return evolucion


def consultar_precio_alpha_vantage(ticker: str) -> dict | None:
    if not ALPHA_VANTAGE_KEY:
        return None
    time.sleep(1.2)
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": "compact",
                "apikey": ALPHA_VANTAGE_KEY,
            },
            timeout=25,
        )
        serie = resp.json().get("Time Series (Daily)")
        if not serie:
            return None
        fechas = sorted(serie.keys(), reverse=True)
        cierres = [float(serie[f]["4. close"]) for f in fechas if float(serie[f]["4. close"]) > 0]
        if not cierres:
            return None
        cierre = cierres[0]
        evol = _calcular_evolucion_desde_cierres(cierres)
        var_sem = evol.get("1S") if "1S" in evol else evol.get("1D", 0.0)
        return {
            "cierre": cierre,
            "var_sem": var_sem,
            "evolucion": evol,
            "fecha": fechas[0],
            "fuente": "Alpha Vantage",
        }
    except Exception:
        return None


def consultar_precio_finnhub(ticker: str) -> dict | None:
    if not FINNHUB_KEY:
        return None
    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": ticker, "token": FINNHUB_KEY},
            timeout=20,
        )
        data = resp.json()
        cierre = float(data.get("c") or 0)
        previo = float(data.get("pc") or 0)
        if cierre <= 0 or previo <= 0:
            return None
        var_dia = ((cierre - previo) / previo) * 100
        evol = _calcular_evolucion_desde_cierres([cierre, previo])
        return {
            "cierre": cierre,
            "var_sem": var_dia,
            "evolucion": evol,
            "fecha": datetime.date.today().isoformat(),
            "fuente": "Finnhub",
        }
    except Exception:
        return None


def consultar_precio_marketstack(ticker: str) -> dict | None:
    if not MARKETSTACK_KEY:
        return None
    try:
        resp = requests.get(
            "http://api.marketstack.com/v1/eod",
            params={
                "access_key": MARKETSTACK_KEY,
                "symbols": ticker,
                "limit": 65,
            },
            timeout=25,
        )
        filas = resp.json().get("data", [])
        if not filas:
            return None
        cierres = [float(f["close"]) for f in filas if f.get("close") and float(f["close"]) > 0]
        if not cierres:
            return None
        cierre = cierres[0]
        evol = _calcular_evolucion_desde_cierres(cierres)
        var_sem = evol.get("1S") if "1S" in evol else evol.get("1D", 0.0)
        fecha = str(filas[0].get("date", ""))[:10]
        return {
            "cierre": cierre,
            "var_sem": var_sem,
            "evolucion": evol,
            "fecha": fecha,
            "fuente": "MarketStack",
        }
    except Exception:
        return None


def consultar_precio_massive(ticker: str) -> dict | None:
    if not MASSIVE_KEY:
        return None
    try:
        hasta = datetime.date.today().isoformat()
        desde = (datetime.date.today() - datetime.timedelta(days=140)).isoformat()
        resp = requests.get(
            f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{desde}/{hasta}",
            params={"adjusted": "true", "sort": "desc", "limit": 120, "apiKey": MASSIVE_KEY},
            timeout=25,
        )
        res = resp.json().get("results", [])
        if res:
            cierres = [float(r["c"]) for r in res if r.get("c") and float(r["c"]) > 0]
            if cierres:
                cierre = cierres[0]
                evol = _calcular_evolucion_desde_cierres(cierres)
                var_sem = evol.get("1S") if "1S" in evol else evol.get("1D", 0.0)
                return {
                    "cierre": cierre,
                    "var_sem": var_sem,
                    "evolucion": evol,
                    "fecha": datetime.date.today().isoformat(),
                    "fuente": "Massive",
                }
        resp_prev = requests.get(
            f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev",
            params={"adjusted": "true", "apiKey": MASSIVE_KEY},
            timeout=25,
        )
        res_prev = resp_prev.json().get("results", [])
        if not res_prev:
            return None
        cierre = float(res_prev[0]["c"])
        apertura = float(res_prev[0]["o"])
        var = ((cierre - apertura) / apertura) * 100 if apertura else 0.0
        evol = _calcular_evolucion_desde_cierres([cierre, apertura]) if apertura else {"1D": var}
        return {
            "cierre": cierre,
            "var_sem": var,
            "evolucion": evol,
            "fecha": datetime.date.today().isoformat(),
            "fuente": "Massive",
        }
    except Exception:
        return None


def consultar_precio_news_apis(ticker: str) -> dict | None:
    """
    Respaldo ligero usando las APIs de noticias/mercado (Marketaux, NewsAPI, NewsData)
    si ninguna de las cuatro APIs de cotizaciones (Alpha Vantage, Finnhub, MarketStack,
    Massive) devolvio precio en esta corrida.
    """
    if MARKETAUX_KEY:
        try:
            resp = requests.get(
                "https://api.marketaux.com/v1/entity/stats/intraday",
                params={"symbols": ticker, "api_token": MARKETAUX_KEY},
                timeout=15,
            )
            data = resp.json().get("data", [])
            if data and isinstance(data, list):
                precio = float(data[0].get("price") or 0)
                if precio > 0:
                    return {
                        "cierre": precio,
                        "var_sem": 0.0,
                        "evolucion": {},
                        "fecha": datetime.date.today().isoformat(),
                        "fuente": "Marketaux",
                    }
        except Exception:
            pass
    return None


def obtener_cotizacion_consolidada(
    ticker: str,
    nombre: str,
    categoria_extra: str = "",
    orden_conectores: list | None = None,
) -> dict:
    orden = orden_conectores or [
        consultar_precio_alpha_vantage,
        consultar_precio_marketstack,
        consultar_precio_finnhub,
        consultar_precio_massive,
        consultar_precio_news_apis,
    ]

    for fn in orden:
        dato = fn(ticker)
        if dato:
            return {
                "ticker": ticker,
                "nombre": nombre,
                "extra": categoria_extra,
                "cierre": dato["cierre"],
                "var_sem": dato["var_sem"],
                "evolucion": dato.get("evolucion") or {},
                "fecha": dato["fecha"],
                "fuente": dato["fuente"],
            }

    return {
        "ticker": ticker,
        "nombre": nombre,
        "extra": categoria_extra,
        "cierre": None,
        "var_sem": None,
        "evolucion": {},
        "fecha": "N/D",
        "fuente": "Sin respuesta",
    }


def recolectar_todos_los_datos(universo: dict) -> dict:
    orden_macro = [
        consultar_precio_alpha_vantage,
        consultar_precio_marketstack,
        consultar_precio_finnhub,
        consultar_precio_massive,
    ]
    orden_nasdaq = [
        consultar_precio_finnhub,
        consultar_precio_massive,
        consultar_precio_marketstack,
        consultar_precio_alpha_vantage,
    ]
    orden_sp500 = [
        consultar_precio_marketstack,
        consultar_precio_finnhub,
        consultar_precio_massive,
        consultar_precio_alpha_vantage,
    ]
    orden_russell = [
        consultar_precio_massive,
        consultar_precio_finnhub,
        consultar_precio_marketstack,
        consultar_precio_alpha_vantage,
    ]

    macro = [
        obtener_cotizacion_consolidada(t, n, "Benchmark", orden_conectores=orden_macro)
        for t, n in BENCHMARKS_MACRO
    ]
    nasdaq10 = [
        obtener_cotizacion_consolidada(t, n, seg, orden_conectores=orden_nasdaq)
        for t, n, seg in TOP_10_NASDAQ
    ]
    sp500_10 = [
        obtener_cotizacion_consolidada(t, n, seg, orden_conectores=orden_sp500)
        for t, n, seg in TOP_10_SP500
    ]
    russell10 = [
        obtener_cotizacion_consolidada(t, n, seg, orden_conectores=orden_russell)
        for t, n, seg in TOP_10_RUSSELL2000
    ]
    sectorial = [
        obtener_cotizacion_consolidada(t, n, universo["nombre_foco"], orden_conectores=orden_nasdaq)
        for t, n in universo["activos"]
    ]

    return {
        "macro": macro,
        "nasdaq10": nasdaq10,
        "sp500_10": sp500_10,
        "russell10": russell10,
        "sectorial": sectorial,
    }


def auditar_las_7_fuentes(datos: dict, conteo_noticias: dict) -> list[dict]:
    """Verifica el estado y aporte de las 7 fuentes configuradas en el sistema."""
    todas_filas = (
        datos["macro"]
        + datos["nasdaq10"]
        + datos["sp500_10"]
        + datos["russell10"]
        + datos["sectorial"]
    )
    def _contar_precios(etiqueta_fuente: str) -> int:
        return sum(1 for f in todas_filas if etiqueta_fuente.lower() in f["fuente"].lower())

    return [
        {
            "fuente": "Alpha Vantage",
            "clave_ok": bool(ALPHA_VANTAGE_KEY),
            "precios": _contar_precios("Alpha Vantage"),
            "noticias": conteo_noticias.get("Alpha Vantage", 0),
        },
        {
            "fuente": "Finnhub",
            "clave_ok": bool(FINNHUB_KEY),
            "precios": _contar_precios("Finnhub"),
            "noticias": conteo_noticias.get("Finnhub", 0),
        },
        {
            "fuente": "MarketStack",
            "clave_ok": bool(MARKETSTACK_KEY),
            "precios": _contar_precios("MarketStack"),
            "noticias": 0,
        },
        {
            "fuente": "Massive",
            "clave_ok": bool(MASSIVE_KEY),
            "precios": _contar_precios("Massive"),
            "noticias": 0,
        },
        {
            "fuente": "Marketaux",
            "clave_ok": bool(MARKETAUX_KEY),
            "precios": _contar_precios("Marketaux"),
            "noticias": conteo_noticias.get("Marketaux", 0),
        },
        {
            "fuente": "NewsAPI.org",
            "clave_ok": bool(NEWS_API_KEY),
            "precios": 0,
            "noticias": conteo_noticias.get("NewsAPI.org", 0),
        },
        {
            "fuente": "NewsData.io",
            "clave_ok": bool(NEWSDATA_KEY),
            "precios": 0,
            "noticias": conteo_noticias.get("NewsData.io", 0),
        },
    ]


# ==============================================================================
# 4. CONECTORES MULTIFUENTE DE NOTICIAS E INTELIGENCIA DE MERCADO
# ==============================================================================
def noticias_alpha_vantage() -> list[dict]:
    if not ALPHA_VANTAGE_KEY:
        return []
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "topics": "financial_markets,economy_macro",
                "limit": 8,
                "apikey": ALPHA_VANTAGE_KEY,
            },
            timeout=25,
        )
        items = resp.json().get("feed", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"Alpha Vantage ({i.get('source', 'Mercado')})",
                "etiqueta": i.get("overall_sentiment_label", "Macro"),
            }
            for i in items[:4]
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
            timeout=20,
        )
        items = resp.json()
        if not isinstance(items, list):
            return []
        return [
            {
                "titulo": i.get("headline", ""),
                "fuente": f"Finnhub ({i.get('source', 'General')})",
                "etiqueta": "Mercado Global",
            }
            for i in items[:4]
            if i.get("headline")
        ]
    except Exception:
        return []


def noticias_marketaux(tickers: list[str]) -> list[dict]:
    if not MARKETAUX_KEY:
        return []
    try:
        resp = requests.get(
            "https://api.marketaux.com/v1/news/all",
            params={
                "symbols": ",".join(tickers),
                "filter_entities": "true",
                "language": "en,es",
                "limit": 4,
                "api_token": MARKETAUX_KEY,
            },
            timeout=25,
        )
        items = resp.json().get("data", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"Marketaux ({i.get('source', 'Corporativo')})",
                "etiqueta": "Radar Sectorial",
            }
            for i in items[:4]
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
                "q": "(stock market OR Federal Reserve OR inflation OR earnings)",
                "sortBy": "publishedAt",
                "pageSize": 5,
                "apiKey": NEWS_API_KEY,
            },
            timeout=25,
        )
        items = resp.json().get("articles", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"NewsAPI.org ({(i.get('source') or {}).get('name', 'Prensa')})",
                "etiqueta": "Coyuntura",
            }
            for i in items[:4]
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
                "q": "finance OR economy OR markets",
                "category": "business",
            },
            timeout=25,
        )
        items = resp.json().get("results", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"NewsData.io ({i.get('source_id', 'Business')})",
                "etiqueta": "Negocios Globales",
            }
            for i in items[:4]
            if i.get("title")
        ]
    except Exception:
        return []


def recolectar_noticias_consolidadas(tickers_sectoriales: list[str]) -> tuple[list[dict], dict]:
    fuentes = {
        "Alpha Vantage": noticias_alpha_vantage(),
        "Finnhub": noticias_finnhub(),
        "Marketaux": noticias_marketaux(tickers_sectoriales),
        "NewsAPI.org": noticias_newsapi(),
        "NewsData.io": noticias_newsdata(),
    }

    vistas = set()
    consolidadas = []
    conteo_por_fuente = {}

    for nombre_fuente, lista in fuentes.items():
        conteo_por_fuente[nombre_fuente] = len(lista)
        for item in lista:
            clave = re.sub(r"\W+", "", item["titulo"].lower())[:55]
            if clave and clave not in vistas:
                vistas.add(clave)
                consolidadas.append(item)

    return consolidadas[:16], conteo_por_fuente


# ==============================================================================
# 5. ANALISIS CUANTITATIVO DETERMINISTA Y PROYECCIONES (SIN IA)
# ==============================================================================
def _promedios_por_plazo(filas: list[dict]) -> dict[str, float | None]:
    salida: dict[str, float | None] = {}
    for etiqueta, _ in PLAZOS_EVOLUTIVOS:
        vals = [f["evolucion"][etiqueta] for f in filas if etiqueta in f.get("evolucion", {})]
        salida[etiqueta] = (sum(vals) / len(vals)) if vals else None
    return salida


def construir_analisis_bloques(datos: dict, auditoria_fuentes: list[dict]) -> dict:
    def _resumen_bloque(filas: list[dict], nombre: str) -> str:
        proms = _promedios_por_plazo(filas)
        partes = [f"{k}: {v:+.2f}%" for k, v in proms.items() if v is not None]
        validos = [f for f in filas if f["var_sem"] is not None]
        if not validos:
            return f"{nombre}: sin cotizaciones numericas en esta corrida."
        mejor = max(validos, key=lambda x: x["var_sem"])
        peor = min(validos, key=lambda x: x["var_sem"])
        linea_plazos = " | ".join(partes) if partes else f"Ref: {sum(f['var_sem'] for f in validos)/len(validos):+.2f}%"
        return (
            f"{nombre} ({len(validos)}/{len(filas)} activos con dato) -> {linea_plazos}. "
            f"Lider: {mejor['ticker']} ({mejor['var_sem']:+.2f}%) | Rezagado: {peor['ticker']} ({peor['var_sem']:+.2f}%)."
        )

    res_nq = _resumen_bloque(datos["nasdaq10"], "10 Mayores Nasdaq")
    res_sp = _resumen_bloque(datos["sp500_10"], "10 Mayores S&P 500")
    res_r2k = _resumen_bloque(datos["russell10"], "10 Mayores Russell 2000")

    activas = [f"{a['fuente']} (P:{a['precios']}/N:{a['noticias']})" for a in auditoria_fuentes if a["clave_ok"]]
    resumen_fuentes = (
        f"Auditoria de 7 fuentes ({len(activas)}/7 claves presentes): "
        + (", ".join(activas) if activas else "sin claves configuradas en entorno.")
    )

    proyecciones = (
        "PROYECCIONES Y LECTURA POR HORIZONTES (1D A 3M):\n"
        "- Corto plazo (1D, 2D, 3D y 1S): Mide el impulso tactico inmediato y la reaccion a flujos diarios.\n"
        "- Mediano plazo (15D y 1M): Confirma si la rotacion entre Nasdaq, S&P 500 y Russell 2000 gana traccion o se agota.\n"
        "- Plazo trimestral (3M): Filtra el ruido diario y muestra la tendencia estructural subyacente de cada bloque.\n"
        "- Regla de amplitud: Si el bloque Russell 2000 acompana a Nasdaq y S&P 500 en 1S-1M, la participacion es mas sana; "
        "si queda rezagado, el avance depende de mayor selectividad y escala."
    )

    return {
        "res_nq": res_nq,
        "res_sp": res_sp,
        "res_r2k": res_r2k,
        "resumen_fuentes": resumen_fuentes,
        "proyecciones": proyecciones,
    }


# ==============================================================================
# 6. GENERACION DE GRAFICOS (NASDAQ, S&P 500 Y RUSSELL 2000)
# ==============================================================================
def generar_grafico_bloque(filas: list[dict], titulo: str, ruta_png: str) -> str | None:
    validos = [f for f in filas if f["var_sem"] is not None]
    if not validos:
        return None

    tickers = [f["ticker"] for f in validos][::-1]
    valores = [float(f["var_sem"]) for f in validos][::-1]
    colores = ["#167341" if v >= 0 else "#AF2D2D" for v in valores]

    plt.figure(figsize=(8.4, 3.8))
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    ax = plt.gca()
    ax.set_facecolor("#FAFBFD")
    plt.gcf().patch.set_facecolor("white")

    barras = plt.barh(tickers, valores, color=colores, height=0.6, edgecolor="none")
    plt.axvline(0, color="#121C2E", linewidth=0.9)
    plt.grid(axis="x", linestyle="--", alpha=0.45, color="#8A96A8")
    ax.set_axisbelow(True)

    plt.title(titulo, fontsize=10.5, fontweight="bold", color="#121C2E", pad=10, loc="left")
    plt.xlabel("Variacion (%) de referencia en la muestra", fontsize=8.5, color="#3C4652")
    plt.tick_params(axis="both", labelsize=8.5, colors="#1F2630")

    max_abs = max([abs(v) for v in valores] + [1.0])
    margen_x = max_abs * 0.24
    plt.xlim(-max_abs - margen_x, max_abs + margen_x)

    for barra, val in zip(barras, valores):
        desp = max_abs * 0.03 if val >= 0 else -max_abs * 0.03
        alineacion = "left" if val >= 0 else "right"
        plt.text(
            val + desp,
            barra.get_y() + barra.get_height() / 2,
            f"{val:+.2f}%",
            va="center",
            ha=alineacion,
            fontsize=8,
            fontweight="bold",
            color="#167341" if val >= 0 else "#AF2D2D",
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    plt.savefig(ruta_png, dpi=180)
    plt.close()
    return ruta_png


def generar_graficos_tres_bloques(datos: dict) -> dict:
    return {
        "nasdaq": generar_grafico_bloque(
            datos["nasdaq10"],
            "Nasdaq (10 Mayores) - Variacion Porcentual",
            "grafico_reporte_nasdaq.png",
        ),
        "sp500": generar_grafico_bloque(
            datos["sp500_10"],
            "S&P 500 (10 Mayores) - Variacion Porcentual",
            "grafico_reporte_sp500.png",
        ),
        "russell2000": generar_grafico_bloque(
            datos["russell10"],
            "Russell 2000 (10 Mayores) - Variacion Porcentual",
            "grafico_reporte_russell2000.png",
        ),
    }


# ==============================================================================
# 7. MAQUETACION PDF EDITORIAL CON BLOQUES SEPARADOS Y EVOLUCION (1D A 3M)
# ==============================================================================
class ReporteDiarioPDF(FPDF):
    def __init__(self, num_edicion: int, fecha_str: str):
        super().__init__()
        self.num_edicion = num_edicion
        self.fecha_str = fecha_str
        self.set_margins(left=11, top=16, right=11)
        self.set_auto_page_break(auto=True, margin=18)

    @property
    def ancho_util(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(18, 28, 46)
        self.rect(0, 0, 210, 14, "F")
        self.set_xy(11, 4)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(255, 255, 255)
        self.cell(
            self.ancho_util,
            6,
            limpiar_texto_pdf(
                f"FIMOTHY | FINANCIAL ENTERPRISE   -   REPORTE DIARIO ED. {self.num_edicion:02d} ({self.fecha_str})"
            ),
            align="L",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_draw_color(185, 150, 85)
        self.set_line_width(0.5)
        self.line(11, 15.5, 199, 15.5)
        self.ln(13)

    def footer(self):
        self.set_y(-13)
        self.set_draw_color(215, 220, 228)
        self.set_line_width(0.3)
        self.line(11, self.get_y(), 199, self.get_y())
        self.set_font("Helvetica", "I", 7.8)
        self.set_text_color(105, 112, 122)
        self.cell(
            self.ancho_util,
            8,
            limpiar_texto_pdf(
                f"FIMOTHY Financial Enterprise | Nasdaq, S&P 500 y Russell 2000 (1D-3M) | Pagina {self.page_no()}"
            ),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    def portada(self, editorial: dict, universo: dict, macro_datos: list[dict], resumen_fuentes: str):
        self.add_page()
        self.set_fill_color(18, 28, 46)
        self.rect(0, 0, 210, 56, "F")

        self.set_xy(14, 10)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(205, 170, 95)
        self.cell(
            182,
            5,
            limpiar_texto_pdf("REPORTE DIARIO DE MERCADOS - BLOQUES SEPARADOS Y GRAFICOS"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(14)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(255, 255, 255)
        self.cell(
            182,
            10,
            limpiar_texto_pdf("FIMOTHY | FINANCIAL ENTERPRISE"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(14)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(200, 212, 228)
        self.cell(
            182,
            6,
            limpiar_texto_pdf(
                f"EDICION N. {self.num_edicion:02d}   |   FECHA: {self.fecha_str}   |   LINEA EVOLUTIVA: 1D, 2D, 3D, 1S, 15D, 1M, 3M"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_draw_color(205, 170, 95)
        self.set_line_width(0.8)
        self.line(14, 48, 196, 48)

        self.set_xy(14, 62)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(150, 115, 45)
        self.cell(
            182,
            5,
            limpiar_texto_pdf("TEMA EDITORIAL DE REFERENCIA"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(14)
        self.set_font("Helvetica", "B", 15.5)
        self.set_text_color(18, 28, 46)
        self.multi_cell(182, 7.0, limpiar_texto_pdf(editorial["titulo"]))

        self.ln(1.5)
        self.set_x(14)
        self.set_font("Helvetica", "I", 9.8)
        self.set_text_color(75, 85, 98)
        self.multi_cell(182, 5.0, limpiar_texto_pdf(editorial["subtitulo"]))

        self.ln(4)
        y_box = self.get_y()
        self.set_fill_color(244, 246, 250)
        self.set_draw_color(200, 208, 220)
        self.rect(14, y_box, 182, 16, "DF")
        self.set_xy(17, y_box + 2.5)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(18, 28, 46)
        self.cell(
            176,
            4.5,
            limpiar_texto_pdf(f"FOCO SECTORIAL: {universo['nombre_foco']}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_x(17)
        self.set_font("Helvetica", "", 8.3)
        self.set_text_color(60, 70, 82)
        self.cell(
            176,
            5,
            limpiar_texto_pdf(
                "Bloques independientes: 10 Nasdaq, 10 S&P 500 y 10 Russell 2000 + graficos por bloque."
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.ln(6)
        self.set_x(14)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(18, 28, 46)
        self.cell(
            182,
            6,
            limpiar_texto_pdf("BENCHMARKS MACRO DE REFERENCIA"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(1.5)

        col_w = 58
        row_h = 22
        x_ini = 14
        y_ini = self.get_y()

        for idx, item in enumerate(macro_datos[:6]):
            col = idx % 3
            fila = idx // 3
            x = x_ini + col * (col_w + 4)
            y = y_ini + fila * (row_h + 4)

            self.set_fill_color(250, 251, 253)
            self.set_draw_color(205, 212, 222)
            self.rect(x, y, col_w, row_h, "DF")

            self.set_xy(x + 3, y + 2.5)
            self.set_font("Helvetica", "B", 8.5)
            self.set_text_color(18, 28, 46)
            self.cell(
                col_w - 6,
                4.5,
                limpiar_texto_pdf(f"{item['ticker']} - {item['nombre'][:22]}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )

            self.set_x(x + 3)
            self.set_font("Helvetica", "B", 11)
            if item["cierre"] is not None:
                signo = "+" if item["var_sem"] >= 0 else ""
                if item["var_sem"] >= 0:
                    self.set_text_color(22, 115, 65)
                else:
                    self.set_text_color(175, 45, 45)
                self.cell(
                    col_w - 6,
                    6,
                    limpiar_texto_pdf(f"{item['cierre']:.2f} ({signo}{item['var_sem']:.2f}%)"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            else:
                self.set_text_color(110, 115, 125)
                self.cell(
                    col_w - 6,
                    6,
                    limpiar_texto_pdf("Dato no disponible"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

            self.set_x(x + 3)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(100, 108, 118)
            self.cell(
                col_w - 6,
                4,
                limpiar_texto_pdf(f"Fuente: {item['fuente']} | {item['fecha']}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )

        self.set_y(y_ini + 2 * (row_h + 4) + 4)

        self.set_fill_color(18, 28, 46)
        self.rect(14, self.get_y(), 182, 34, "F")
        self.set_xy(17, self.get_y() + 3)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(205, 170, 95)
        self.cell(
            176,
            4.5,
            limpiar_texto_pdf("ESTADO DE LAS 7 FUENTES & ESTRUCTURA DEL REPORTE"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(17)
        self.set_font("Helvetica", "", 8.0)
        self.set_text_color(235, 240, 246)
        self.multi_cell(
            176,
            4.1,
            limpiar_texto_pdf(
                f"{resumen_fuentes}\n"
                "Bloques separados: 10 Nasdaq + Grafico | 10 S&P 500 + Grafico | 10 Russell 2000 + Grafico "
                "(con evolucion 1D, 2D, 3D, 1S, 15D, 1M, 3M)."
            ),
        )

    def titulo_seccion(self, etiqueta: str, titulo: str):
        if self.get_y() > 245:
            self.add_page()
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(155, 120, 45)
        self.cell(
            self.ancho_util,
            4.5,
            limpiar_texto_pdf(etiqueta.upper()),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(18, 28, 46)
        self.cell(
            self.ancho_util,
            6.5,
            limpiar_texto_pdf(titulo),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_draw_color(185, 150, 85)
        self.set_line_width(0.5)
        self.line(11, self.get_y() + 1, 199, self.get_y() + 1)
        self.ln(3.5)

    def parrafo(self, texto: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9.4)
        self.set_text_color(32, 36, 42)
        self.multi_cell(self.ancho_util, 4.9, limpiar_texto_pdf(texto))
        self.ln(2.5)

    def caja_destacada(self, titulo: str, texto: str):
        if self.get_y() > 235:
            self.add_page()
        self.set_x(self.l_margin)
        self.set_fill_color(244, 246, 250)
        self.set_draw_color(18, 28, 46)
        self.set_font("Helvetica", "B", 9.0)
        self.set_text_color(18, 28, 46)
        self.multi_cell(
            self.ancho_util,
            5.0,
            limpiar_texto_pdf(titulo),
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 8.6)
        self.set_text_color(40, 45, 52)
        self.multi_cell(
            self.ancho_util,
            4.5,
            limpiar_texto_pdf(texto),
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(3)

    def insertar_grafico(self, ruta_png: str | None, ancho_mm: float = 186):
        if not ruta_png or not os.path.exists(ruta_png):
            self.parrafo("Grafico no disponible por falta de datos numericos en esta corrida.")
            return
        if self.get_y() > 192:
            self.add_page()
        self.set_x(self.l_margin + (self.ancho_util - ancho_mm) / 2)
        self.image(ruta_png, w=ancho_mm)
        self.ln(3)

    def tabla_evolucion_10(self, filas: list[dict]):
        """
        Tabla compacta para 10 empresas con precio y linea evolutiva completa:
        1D, 2D, 3D, 1S, 15D, 1M, 3M + fuente.
        Ancho total = 188 mm.
        """
        if self.get_y() > 215:
            self.add_page()
        headers = ["Ticker", "Empresa", "Precio", "1D", "2D", "3D", "1S", "15D", "1M", "3M", "Fuente"]
        widths = [15, 38, 17, 14.5, 14.5, 14.5, 14.5, 14.5, 14.5, 14.5, 19]

        def _dibujar_cabecera():
            self.set_x(self.l_margin)
            self.set_fill_color(18, 28, 46)
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 7.4)
            for h, w in zip(headers, widths):
                self.cell(w, 6.2, limpiar_texto_pdf(h), border=1, align="C", fill=True)
            self.ln()

        _dibujar_cabecera()
        self.set_font("Helvetica", "", 7.3)
        for idx, f in enumerate(filas):
            if self.get_y() > 266:
                self.add_page()
                _dibujar_cabecera()
                self.set_font("Helvetica", "", 7.3)

            self.set_x(self.l_margin)
            fill = idx % 2 == 1
            self.set_fill_color(246, 248, 251)
            self.set_text_color(25, 30, 38)

            precio_txt = f"{f['cierre']:.2f}" if f["cierre"] is not None else "N/D"
            evol = f.get("evolucion") or {}
            plazos_txt = []
            for etq, _ in PLAZOS_EVOLUTIVOS:
                val = evol.get(etq)
                if val is None and etq == "1S" and f.get("var_sem") is not None:
                    val = f["var_sem"]
                plazos_txt.append(f"{val:+.1f}%" if val is not None else "N/D")

            valores = [
                f["ticker"],
                f["nombre"][:20],
                precio_txt,
                *plazos_txt,
                f["fuente"][:10],
            ]
            aligns = ["C", "L", "R", "R", "R", "R", "R", "R", "R", "R", "C"]
            for val, w, al in zip(valores, widths, aligns):
                self.cell(w, 5.8, limpiar_texto_pdf(val), border=1, align=al, fill=fill)
            self.ln()
        self.ln(3)


def construir_pdf(
    num_edicion: int,
    fecha_str: str,
    editorial: dict,
    universo: dict,
    datos: dict,
    analisis: dict,
    graficos: dict,
    noticias: list[dict],
    auditoria_fuentes: list[dict],
    ruta_salida: str = "reporte_diario_fimothy.pdf",
) -> str:
    pdf = ReporteDiarioPDF(num_edicion=num_edicion, fecha_str=fecha_str)

    # 1. Portada y benchmarks
    pdf.portada(editorial, universo, datos["macro"], analisis["resumen_fuentes"])

    # 2. Bloque separado 1: 10 Mayores de Nasdaq + Evolucion (1D-3M) + Grafico
    pdf.add_page()
    pdf.titulo_seccion(
        "Bloque 01  |  Nasdaq (10 Mayores Empresas)",
        "Evolucion Temporal (1D a 3M) y Grafico Nasdaq",
    )
    pdf.caja_destacada("LECTURA DEL BLOQUE NASDAQ", analisis["res_nq"])
    pdf.tabla_evolucion_10(datos["nasdaq10"])
    pdf.insertar_grafico(graficos.get("nasdaq"))

    # 3. Bloque separado 2: 10 Mayores del S&P 500 + Evolucion (1D-3M) + Grafico
    pdf.add_page()
    pdf.titulo_seccion(
        "Bloque 02  |  S&P 500 (10 Mayores Empresas)",
        "Evolucion Temporal (1D a 3M) y Grafico S&P 500",
    )
    pdf.caja_destacada("LECTURA DEL BLOQUE S&P 500", analisis["res_sp"])
    pdf.tabla_evolucion_10(datos["sp500_10"])
    pdf.insertar_grafico(graficos.get("sp500"))

    # 4. Bloque separado 3: 10 Mayores del Russell 2000 + Evolucion (1D-3M) + Grafico
    pdf.add_page()
    pdf.titulo_seccion(
        "Bloque 03  |  Russell 2000 (10 Mayores / Muestra Small Caps)",
        "Evolucion Temporal (1D a 3M) y Grafico Russell 2000",
    )
    pdf.caja_destacada("LECTURA DEL BLOQUE RUSSELL 2000", analisis["res_r2k"])
    pdf.tabla_evolucion_10(datos["russell10"])
    pdf.insertar_grafico(graficos.get("russell2000"))

    # 5. Proyecciones, sectorial, noticias y auditoria de las 7 fuentes
    pdf.add_page()
    pdf.titulo_seccion(
        "Bloque 04  |  Proyecciones, Sectorial, Noticias y 7 Fuentes",
        "Perspectiva Evolutiva, Radar Informativo y Estado de APIs",
    )
    pdf.caja_destacada("PROYECCIONES Y HORIZONTES (1D A 3M)", analisis["proyecciones"])
    pdf.caja_destacada(
        f"FOCO SECTORIAL: {universo['nombre_foco']}",
        universo["tesis_sectorial"],
    )

    if noticias:
        for idx, n in enumerate(noticias, start=1):
            linea = f"{idx:02d}. [{n['etiqueta']}] {n['titulo']}  --  Fuente: {n['fuente']}"
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(30, 35, 42)
            pdf.multi_cell(pdf.ancho_util, 4.4, limpiar_texto_pdf(linea))
            pdf.ln(1.0)
    else:
        pdf.parrafo("No se recibieron titulares nuevos en esta ventana de consulta.")

    pdf.ln(2)
    lineas_7 = []
    for a in auditoria_fuentes:
        estado = "Clave OK" if a["clave_ok"] else "Sin clave"
        lineas_7.append(
            f"- {a['fuente']}: {estado} | Precios asignados: {a['precios']} | Noticias: {a['noticias']}"
        )
    pdf.caja_destacada("AUDITORIA DE LAS 7 FUENTES (PRECIOS Y NOTICIAS)", "\n".join(lineas_7))

    pdf.output(ruta_salida)
    return ruta_salida


# ==============================================================================
# 8. ENVIO A TELEGRAM
# ==============================================================================
def enviar_telegram(ruta_pdf: str, num_edicion: int, titulo: str, foco: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Aviso: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados.")
        return

    caption = limpiar_texto_pdf(
        f"FIMOTHY | FINANCIAL ENTERPRISE - Reporte Diario Ed. {num_edicion:02d}\n"
        f"Bloques: 10 Nasdaq, 10 S&P 500, 10 Russell 2000 (1D-3M) + Graficos\n"
        f"Foco: {foco}"
    )[:1000]

    with open(ruta_pdf, "rb") as doc:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"document": doc},
            timeout=60,
        )
        resp.raise_for_status()


# ==============================================================================
# 9. PUNTO DE ENTRADA PRINCIPAL
# ==============================================================================
def main() -> None:
    num_edicion, editorial, universo = obtener_configuracion_semanal()
    fecha_str = datetime.date.today().strftime("%d/%m/%Y")

    datos = recolectar_todos_los_datos(universo)
    tickers_sec = [t for t, _ in universo["activos"]]
    noticias, conteo_noticias = recolectar_noticias_consolidadas(tickers_sec)
    auditoria_fuentes = auditar_las_7_fuentes(datos, conteo_noticias)
    analisis = construir_analisis_bloques(datos, auditoria_fuentes)
    graficos = generar_graficos_tres_bloques(datos)

    ruta_pdf = construir_pdf(
        num_edicion=num_edicion,
        fecha_str=fecha_str,
        editorial=editorial,
        universo=universo,
        datos=datos,
        analisis=analisis,
        graficos=graficos,
        noticias=noticias,
        auditoria_fuentes=auditoria_fuentes,
    )

    enviar_telegram(ruta_pdf, num_edicion, editorial["titulo"], universo["nombre_foco"])
    print(f"Reporte diario generado con exito: {ruta_pdf}")


if __name__ == "__main__":
    main()
