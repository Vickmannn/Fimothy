import datetime
import os
import re
import time
import unicodedata
import requests
from fpdf import FPDF

# ==============================================================================
# 1. VARIABLES DE ENTORNO (GITHUB SECRETS)
# ==============================================================================
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY")
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY")
MARKETSTACK_KEY = os.environ.get("MARKETSTACK_API_KEY")
MASSIVE_KEY = os.environ.get("MASSIVE_API_KEY")
MARKETAUX_KEY = os.environ.get("MARKETAUX_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
NEWSDATA_KEY = os.environ.get("NEWSDATA_API_KEY")

GROK_KEY = os.environ.get("GROK_API_KEY")
GROK_MODEL = os.environ.get("GROK_MODEL", "grok-3-mini")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ==============================================================================
# 2. UNIVERSOS ROTATIVOS DE ACTIVOS Y EDITORIALES (CAMBIAN CADA SEMANA)
# ==============================================================================
BENCHMARKS_MACRO = [
    ("SPY", "S&P 500 Index ETF"),
    ("QQQ", "Nasdaq 100 Tech ETF"),
    ("IWM", "Russell 2000 Small Caps"),
    ("TLT", "US Treasury 20+Y Bonds"),
    ("GLD", "Gold Bullion Trust"),
    ("USO", "US Oil Benchmark"),
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
# 3. CONECTORES MULTIFUENTE DE DATOS DE MERCADO (BIG DATA FINANCIERO)
# ==============================================================================
def consultar_precio_alpha_vantage(ticker: str) -> dict | None:
    if not ALPHA_VANTAGE_KEY:
        return None
    time.sleep(1.3)
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
        cierre = float(serie[fechas[0]]["4. close"])
        previo = float(serie[fechas[min(5, len(fechas) - 1)]]["4. close"])
        var_sem = ((cierre - previo) / previo) * 100
        return {
            "cierre": cierre,
            "var_sem": var_sem,
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
        return {
            "cierre": cierre,
            "var_sem": var_dia,
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
                "limit": 6,
            },
            timeout=25,
        )
        filas = resp.json().get("data", [])
        if not filas:
            return None
        cierre = float(filas[0]["close"])
        previo = float(filas[-1]["close"])
        var_sem = ((cierre - previo) / previo) * 100
        fecha = str(filas[0].get("date", ""))[:10]
        return {
            "cierre": cierre,
            "var_sem": var_sem,
            "fecha": fecha,
            "fuente": "MarketStack",
        }
    except Exception:
        return None


def consultar_precio_massive(ticker: str) -> dict | None:
    if not MASSIVE_KEY:
        return None
    try:
        resp = requests.get(
            f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev",
            params={"adjusted": "true", "apiKey": MASSIVE_KEY},
            timeout=25,
        )
        res = resp.json().get("results", [])
        if not res:
            return None
        cierre = float(res[0]["c"])
        apertura = float(res[0]["o"])
        var = ((cierre - apertura) / apertura) * 100 if apertura else 0.0
        return {
            "cierre": cierre,
            "var_sem": var,
            "fecha": datetime.date.today().isoformat(),
            "fuente": "Massive",
        }
    except Exception:
        return None


def obtener_cotizacion_consolidada(ticker: str, nombre: str, preferir_externo: bool = False) -> dict:
    orden = (
        [
            consultar_precio_finnhub,
            consultar_precio_massive,
            consultar_precio_marketstack,
            consultar_precio_alpha_vantage,
        ]
        if preferir_externo
        else [
            consultar_precio_alpha_vantage,
            consultar_precio_marketstack,
            consultar_precio_finnhub,
            consultar_precio_massive,
        ]
    )

    for fn in orden:
        dato = fn(ticker)
        if dato:
            return {
                "ticker": ticker,
                "nombre": nombre,
                "cierre": dato["cierre"],
                "var_sem": dato["var_sem"],
                "fecha": dato["fecha"],
                "fuente": dato["fuente"],
            }

    return {
        "ticker": ticker,
        "nombre": nombre,
        "cierre": None,
        "var_sem": None,
        "fecha": "N/D",
        "fuente": "Sin respuesta",
    }


def recolectar_datos_mercado(universo: dict) -> tuple[list[dict], list[dict]]:
    macro_datos = [
        obtener_cotizacion_consolidada(t, n, preferir_externo=False)
        for t, n in BENCHMARKS_MACRO
    ]
    sectorial_datos = [
        obtener_cotizacion_consolidada(t, n, preferir_externo=True)
        for t, n in universo["activos"]
    ]
    return macro_datos, sectorial_datos


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
                "fuente": f"AlphaVantage/{i.get('source', 'Mercado')}",
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
                "fuente": f"Finnhub/{i.get('source', 'General')}",
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
                "limit": 3,
                "api_token": MARKETAUX_KEY,
            },
            timeout=25,
        )
        items = resp.json().get("data", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"Marketaux/{i.get('source', 'Corporativo')}",
                "etiqueta": "Radar Sectorial",
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
                "fuente": f"NewsAPI/{(i.get('source') or {}).get('name', 'Prensa')}",
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
                "fuente": f"NewsData/{i.get('source_id', 'Business')}",
                "etiqueta": "Global Business",
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

    return consolidadas[:14], conteo_por_fuente


# ==============================================================================
# 5. CONCLUSIONES FINALES (1 LLAMADA A GROK + 1 LLAMADA A GEMINI AL CIERRE)
# ==============================================================================
def consultar_grok_conclusion_final(dossier_revista: str) -> str:
    if not GROK_KEY:
        return "Clave GROK_API_KEY no configurada."
    try:
        resp = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROK_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROK_MODEL,
                "temperature": 0.35,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres analista cuantitativo y critico de FIMOTHY | FINANCIAL ENTERPRISE. "
                            "Escribe en texto plano sin Markdown. Entrega una conclusion final "
                            "directa basada exclusivamente en los datos y noticias de la revista."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"{dossier_revista}\n\n"
                            "Redacta tu Conclusion Final (150-200 palabras): que destaca de los "
                            "datos y noticias recopiladas esta semana, que senal pesa mas que el ruido "
                            "y que riesgo conviene vigilar de inmediato."
                        ),
                    },
                ],
            },
            timeout=60,
        )
        if not resp.ok:
            detalle = resp.text.strip().replace("\n", " ")[:220]
            return f"Conclusion Grok no disponible ({resp.status_code}): {detalle}"
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"Conclusion Grok no disponible en esta corrida ({exc})."


def consultar_gemini_conclusion_final(dossier_revista: str) -> str:
    if not GEMINI_KEY:
        return "Clave GEMINI_API_KEY no configurada."

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    )
    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "Eres sintetizador final de FIMOTHY | FINANCIAL ENTERPRISE. "
                        "Escribe en texto plano limpio (sin asteriscos ni Markdown). "
                        "Entrega una conclusion final concisa y objetiva a partir del dossier."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"{dossier_revista}\n\n"
                            "Redacta tu Conclusion Final de cierre (150-200 palabras): resume "
                            "el balance general de la edicion y deja 3 puntos finales de seguimiento "
                            "para la proxima semana."
                        )
                    }
                ],
            }
        ],
        "generationConfig": {"temperature": 0.35},
    }

    max_intentos = 3
    ultimo_error = ""
    for intento in range(1, max_intentos + 1):
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code in (429, 503):
                detalle = resp.text.strip().replace("\n", " ")[:220]
                ultimo_error = f"({resp.status_code} con '{GEMINI_MODEL}'): {detalle}"
                if intento < max_intentos:
                    time.sleep(3 * intento)
                    continue
                break
            if not resp.ok:
                detalle = resp.text.strip().replace("\n", " ")[:220]
                return f"Conclusion Gemini no disponible ({resp.status_code}): {detalle}"
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            ultimo_error = f"({exc})"
            if intento < max_intentos:
                time.sleep(3 * intento)
                continue
            break

    return f"Conclusion Gemini no disponible en esta corrida {ultimo_error}".strip()


# ==============================================================================
# 6. MAQUETACIÓN PDF EDITORIAL DE SUSCRIPCIÓN (MULTIPÁGINA INSTITUCIONAL)
# ==============================================================================
class RevistaFimothyPDF(FPDF):
    def __init__(self, num_edicion: int, fecha_str: str):
        super().__init__()
        self.num_edicion = num_edicion
        self.fecha_str = fecha_str
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(18, 28, 46)
        self.rect(0, 0, 210, 14, "F")
        self.set_xy(12, 4)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(255, 255, 255)
        self.cell(
            0,
            6,
            limpiar_texto_pdf(
                f"FIMOTHY | FINANCIAL ENTERPRISE   -   EDICION INSTITUCIONAL N. {self.num_edicion:02d} ({self.fecha_str})"
            ),
            align="L",
        )
        self.set_draw_color(185, 150, 85)
        self.set_line_width(0.5)
        self.line(12, 15.5, 198, 15.5)
        self.ln(13)

    def footer(self):
        self.set_y(-13)
        self.set_draw_color(215, 220, 228)
        self.set_line_width(0.3)
        self.line(12, self.get_y(), 198, self.get_y())
        self.set_font("Helvetica", "I", 7.8)
        self.set_text_color(105, 112, 122)
        self.cell(
            0,
            8,
            limpiar_texto_pdf(
                f"FIMOTHY Financial Enterprise | Inteligencia Cuantitativa & Estrategia | Pagina {self.page_no()}"
            ),
            align="C",
        )

    def portada(self, editorial: dict, universo: dict, macro_datos: list[dict], conteo_fuentes: dict):
        self.add_page()
        self.set_fill_color(18, 28, 46)
        self.rect(0, 0, 210, 56, "F")

        self.set_xy(14, 10)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(205, 170, 95)
        self.cell(0, 5, limpiar_texto_pdf("PUBLICACION SEMANAL DE INTELIGENCIA FINANCIERA"), ln=True)

        self.set_x(14)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, limpiar_texto_pdf("FIMOTHY | FINANCIAL ENTERPRISE"), ln=True)

        self.set_x(14)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(200, 212, 228)
        self.cell(
            0,
            6,
            limpiar_texto_pdf(
                f"EDICION N. {self.num_edicion:02d}   |   CIERRE SEMANAL: {self.fecha_str}   |   EDICION DE SUSCRIPCION"
            ),
            ln=True,
        )

        self.set_draw_color(205, 170, 95)
        self.set_line_width(0.8)
        self.line(14, 48, 196, 48)

        self.set_xy(14, 63)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(150, 115, 45)
        self.cell(0, 5, limpiar_texto_pdf("TEMA CENTRAL DE LA EDICION"), ln=True)

        self.set_x(14)
        self.set_font("Helvetica", "B", 16.5)
        self.set_text_color(18, 28, 46)
        self.multi_cell(182, 7.5, limpiar_texto_pdf(editorial["titulo"]))

        self.ln(1.5)
        self.set_x(14)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(75, 85, 98)
        self.multi_cell(182, 5.2, limpiar_texto_pdf(editorial["subtitulo"]))

        self.ln(4)
        y_box = self.get_y()
        self.set_fill_color(244, 246, 250)
        self.set_draw_color(200, 208, 220)
        self.rect(14, y_box, 182, 16, "DF")
        self.set_xy(17, y_box + 2.5)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(18, 28, 46)
        self.cell(0, 4.5, limpiar_texto_pdf(f"RADAR SECTORIAL ROTATIVO: {universo['nombre_foco']}"), ln=True)
        self.set_x(17)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(60, 70, 82)
        tickers_txt = ", ".join(f"{t} ({n})" for t, n in universo["activos"])
        self.cell(0, 5, limpiar_texto_pdf(f"Activos auditados esta semana: {tickers_txt}"), ln=True)

        self.ln(7)
        self.set_x(14)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(18, 28, 46)
        self.cell(0, 6, limpiar_texto_pdf("TABLERO DE MERCADO Y ACTIVOS DE REFERENCIA"), ln=True)
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
            self.cell(col_w - 6, 4.5, limpiar_texto_pdf(f"{item['ticker']} - {item['nombre'][:22]}"), ln=True)

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
                    ln=True,
                )
            else:
                self.set_text_color(110, 115, 125)
                self.cell(col_w - 6, 6, limpiar_texto_pdf("Dato no disponible"), ln=True)

            self.set_x(x + 3)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(100, 108, 118)
            self.cell(col_w - 6, 4, limpiar_texto_pdf(f"Fuente: {item['fuente']} | {item['fecha']}"), ln=True)

        self.set_y(y_ini + 2 * (row_h + 4) + 4)

        activas = [f"{k} ({v})" for k, v in conteo_fuentes.items() if v > 0]
        fuentes_str = ", ".join(activas) if activas else "Conectores en espera de cuota"

        self.set_fill_color(18, 28, 46)
        self.rect(14, self.get_y(), 182, 28, "F")
        self.set_xy(17, self.get_y() + 3)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(205, 170, 95)
        self.cell(0, 4.5, limpiar_texto_pdf("SUMARIO DE LA EDICION & COBERTURA DE DATOS"), ln=True)

        self.set_x(17)
        self.set_font("Helvetica", "", 8.3)
        self.set_text_color(235, 240, 246)
        self.multi_cell(
            176,
            4.3,
            limpiar_texto_pdf(
                "01. Carta Editorial & Caso de Estudio  |  02. Radiografia Sectorial & Tabla Comparativa\n"
                "03. Radar Global de Noticias Multifuente  |  04. Conclusiones Finales (Grok & Gemini)\n"
                f"Fuentes de noticias activas en esta corrida: {fuentes_str}"
            ),
        )

    def titulo_seccion(self, etiqueta: str, titulo: str):
        if self.get_y() > 245:
            self.add_page()
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(155, 120, 45)
        self.cell(0, 4.5, limpiar_texto_pdf(etiqueta.upper()), ln=True)

        self.set_font("Helvetica", "B", 13)
        self.set_text_color(18, 28, 46)
        self.cell(0, 6.5, limpiar_texto_pdf(titulo), ln=True)

        self.set_draw_color(185, 150, 85)
        self.set_line_width(0.5)
        self.line(12, self.get_y() + 1, 198, self.get_y() + 1)
        self.ln(4)

    def parrafo(self, texto: str):
        self.set_font("Helvetica", "", 9.8)
        self.set_text_color(32, 36, 42)
        self.multi_cell(0, 5.2, limpiar_texto_pdf(texto))
        self.ln(3)

    def caja_destacada(self, titulo: str, texto: str):
        if self.get_y() > 235:
            self.add_page()
        self.set_fill_color(244, 246, 250)
        self.set_draw_color(18, 28, 46)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(18, 28, 46)
        self.multi_cell(0, 5.5, limpiar_texto_pdf(titulo), fill=True)
        self.set_font("Helvetica", "", 9.2)
        self.set_text_color(40, 45, 52)
        self.multi_cell(0, 5, limpiar_texto_pdf(texto), fill=True)
        self.ln(4)

    def tabla_activos(self, filas: list[dict]):
        if self.get_y() > 230:
            self.add_page()
        headers = ["Ticker", "Compania / Activo", "Precio", "Var. Ref.", "Fecha", "Proveedor"]
        widths = [20, 66, 26, 24, 24, 26]

        self.set_fill_color(18, 28, 46)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 8.5)
        for h, w in zip(headers, widths):
            self.cell(w, 7, limpiar_texto_pdf(h), border=1, align="C", fill=True)
        self.ln()

        self.set_font("Helvetica", "", 8.5)
        for idx, f in enumerate(filas):
            fill = idx % 2 == 1
            self.set_fill_color(246, 248, 251)
            self.set_text_color(25, 30, 38)

            precio_txt = f"{f['cierre']:.2f}" if f["cierre"] is not None else "N/D"
            if f["var_sem"] is not None:
                signo = "+" if f["var_sem"] >= 0 else ""
                var_txt = f"{signo}{f['var_sem']:.2f}%"
            else:
                var_txt = "N/D"

            valores = [
                f["ticker"],
                f["nombre"][:32],
                precio_txt,
                var_txt,
                f["fecha"],
                f["fuente"][:14],
            ]
            aligns = ["C", "L", "R", "R", "C", "C"]
            for val, w, al in zip(valores, widths, aligns):
                self.cell(w, 6.5, limpiar_texto_pdf(val), border=1, align=al, fill=fill)
            self.ln()
        self.ln(4)


def construir_pdf(
    num_edicion: int,
    fecha_str: str,
    editorial: dict,
    universo: dict,
    macro_datos: list[dict],
    sectorial_datos: list[dict],
    noticias: list[dict],
    conteo_fuentes: dict,
    conclusion_grok: str,
    conclusion_gemini: str,
    ruta_salida: str = "revista_fimothy_semanal.pdf",
) -> str:
    pdf = RevistaFimothyPDF(num_edicion=num_edicion, fecha_str=fecha_str)

    # 1. Portada y tablero de mercado
    pdf.portada(editorial, universo, macro_datos, conteo_fuentes)

    # 2. Editorial, caso de estudio y filtros de asignacion
    pdf.add_page()
    pdf.titulo_seccion("Seccion 01  |  Estrategia & Marco Conceptual", editorial["titulo"])
    pdf.parrafo(editorial["cuerpo"])
    pdf.caja_destacada("APLICACION PRACTICA DE LA SEMANA", editorial["caso_estudio"])
    pdf.caja_destacada(
        "FILTROS CUANTITATIVOS DE ASIGNACION FIMOTHY",
        "\n".join(editorial["reglas"]),
    )

    # 3. Universo sectorial rotativo, tabla consolidada y radar de noticias
    pdf.add_page()
    pdf.titulo_seccion(
        "Seccion 02  |  Big Data & Enfoque Sectorial Rotativo",
        universo["nombre_foco"],
    )
    pdf.parrafo(universo["tesis_sectorial"])
    pdf.tabla_activos(sectorial_datos)

    pdf.titulo_seccion(
        "Seccion 03  |  Radar de Noticias Financieras Multifuente",
        "Flujo Informativo Consolidado (Alpha Vantage, Finnhub, Marketaux, NewsAPI, NewsData)",
    )
    if noticias:
        for idx, n in enumerate(noticias, start=1):
            linea = f"{idx:02d}. [{n['etiqueta']}] {n['titulo']}  --  ({n['fuente']})"
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(30, 35, 42)
            pdf.multi_cell(0, 4.8, limpiar_texto_pdf(linea))
            pdf.ln(1.2)
    else:
        pdf.parrafo("No se recibieron titulares nuevos en esta ventana de consulta.")

    # 4. Cierre final: 1 conclusion de Grok + 1 conclusion de Gemini
    pdf.add_page()
    pdf.titulo_seccion(
        "Seccion 04  |  Conclusiones Finales de Cierre",
        "Conclusion Final - Grok",
    )
    pdf.parrafo(conclusion_grok)

    pdf.titulo_seccion(
        "Seccion 04  |  Conclusiones Finales de Cierre",
        "Conclusion Final - Gemini",
    )
    pdf.parrafo(conclusion_gemini)

    pdf.caja_destacada(
        "EXENCION DE RESPONSABILIDAD INSTITUCIONAL",
        "Publicacion elaborada por FIMOTHY | FINANCIAL ENTERPRISE con fines estrictamente "
        "formativos, estadisticos y de investigacion de mercado. No constituye recomendacion "
        "personalizada de inversion ni oferta de valores.",
    )

    pdf.output(ruta_salida)
    return ruta_salida


# ==============================================================================
# 7. ENVÍO A TELEGRAM
# ==============================================================================
def enviar_telegram(ruta_pdf: str, num_edicion: int, titulo: str, foco: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Aviso: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados.")
        return

    caption = limpiar_texto_pdf(
        f"FIMOTHY | FINANCIAL ENTERPRISE - Edicion N. {num_edicion:02d}\n"
        f"Editorial: {titulo}\n"
        f"Foco Sectorial: {foco}"
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
# 8. PUNTO DE ENTRADA PRINCIPAL
# ==============================================================================
def main() -> None:
    num_edicion, editorial, universo = obtener_configuracion_semanal()
    fecha_str = datetime.date.today().strftime("%d/%m/%Y")

    macro_datos, sectorial_datos = recolectar_datos_mercado(universo)
    tickers_sec = [t for t, _ in universo["activos"]]
    noticias, conteo_fuentes = recolectar_noticias_consolidadas(tickers_sec)

    lineas_dossier = [
        f"EDICION N. {num_edicion:02d} | FECHA: {fecha_str}",
        f"EDITORIAL: {editorial['titulo']}",
        f"FOCO SECTORIAL: {universo['nombre_foco']}",
        "\nBENCHMARKS MACRO:",
    ]
    for m in macro_datos:
        if m["cierre"] is not None:
            lineas_dossier.append(
                f"- {m['ticker']} ({m['nombre']}): {m['cierre']:.2f} ({m['var_sem']:+.2f}%) [{m['fuente']}]"
            )

    lineas_dossier.append("\nACTIVOS SECTORIALES DE LA SEMANA:")
    for s in sectorial_datos:
        if s["cierre"] is not None:
            lineas_dossier.append(
                f"- {s['ticker']} ({s['nombre']}): {s['cierre']:.2f} ({s['var_sem']:+.2f}%) [{s['fuente']}]"
            )

    lineas_dossier.append("\nTITULARES FINANCIEROS CONSOLIDADOS:")
    for n in noticias[:10]:
        lineas_dossier.append(f"- [{n['fuente']}] {n['titulo']}")

    dossier_revista = "\n".join(lineas_dossier)

    # Una sola llamada a Grok y una sola llamada a Gemini, ambas como conclusion final
    conclusion_grok = consultar_grok_conclusion_final(dossier_revista)
    conclusion_gemini = consultar_gemini_conclusion_final(dossier_revista)

    ruta_pdf = construir_pdf(
        num_edicion=num_edicion,
        fecha_str=fecha_str,
        editorial=editorial,
        universo=universo,
        macro_datos=macro_datos,
        sectorial_datos=sectorial_datos,
        noticias=noticias,
        conteo_fuentes=conteo_fuentes,
        conclusion_grok=conclusion_grok,
        conclusion_gemini=conclusion_gemini,
    )

    enviar_telegram(ruta_pdf, num_edicion, editorial["titulo"], universo["nombre_foco"])
    print(f"Revista institucional generada con exito: {ruta_pdf}")


if __name__ == "__main__":
    main()
