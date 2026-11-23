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
MASSIVE_KEY = os.environ.get("MASSIVE_API_KEY")
MARKETAUX_KEY = os.environ.get("MARKETAUX_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
NEWSDATA_KEY = os.environ.get("NEWSDATA_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ==============================================================================
# 2. BENCHMARKS, TOP 10 EMPRESAS, FILTRO NASDAQ VS S&P 500 Y RUSSELL 2000
# ==============================================================================
BENCHMARKS_MACRO = [
    ("SPY", "S&P 500 ETF (Top 500)"),
    ("QQQ", "Nasdaq 100 ETF (Tecnologia)"),
    ("IWM", "Russell 2000 ETF (2,000 Small Caps)"),
    ("TLT", "Bonos Tesoro EE.UU. 20+ Anos"),
    ("GLD", "Oro Fisico (Refugio / Valor)"),
    ("USO", "Petroleo Crudo (Energia)"),
]

TOP_10_EMPRESAS = [
    ("AAPL", "Apple Inc.", "Consumo Tech / Ecosistema"),
    ("MSFT", "Microsoft Corp.", "Nube / Software Empresarial"),
    ("NVDA", "NVIDIA Corp.", "Semiconductores / IA"),
    ("AMZN", "Amazon.com Inc.", "Nube AWS / Comercio"),
    ("GOOGL", "Alphabet Inc.", "Busqueda / Publicidad / Nube"),
    ("META", "Meta Platforms", "Redes / Monetizacion Digital"),
    ("BRK.B", "Berkshire Hathaway", "Conglomerado / Seguros / Caja"),
    ("LLY", "Eli Lilly and Co.", "Farmaceutica / Salud"),
    ("AVGO", "Broadcom Inc.", "Chips / Infraestructura Red"),
    ("JPM", "JPMorgan Chase", "Banca / Credito / Liquidez"),
]

TOP_10_NASDAQ = [
    ("AAPL", "Apple Inc.", "Nasdaq 100 Top"),
    ("MSFT", "Microsoft Corp.", "Nasdaq 100 Top"),
    ("NVDA", "NVIDIA Corp.", "Nasdaq 100 Top"),
    ("AMZN", "Amazon.com Inc.", "Nasdaq 100 Top"),
    ("GOOGL", "Alphabet Inc.", "Nasdaq 100 Top"),
    ("META", "Meta Platforms", "Nasdaq 100 Top"),
    ("AVGO", "Broadcom Inc.", "Nasdaq 100 Top"),
    ("TSLA", "Tesla Inc.", "Nasdaq 100 Top"),
    ("COST", "Costco Wholesale", "Nasdaq 100 Top"),
    ("NFLX", "Netflix Inc.", "Nasdaq 100 Top"),
]

TOP_10_SP500 = [
    ("AAPL", "Apple Inc.", "S&P 500 Top"),
    ("MSFT", "Microsoft Corp.", "S&P 500 Top"),
    ("NVDA", "NVIDIA Corp.", "S&P 500 Top"),
    ("AMZN", "Amazon.com Inc.", "S&P 500 Top"),
    ("GOOGL", "Alphabet Inc.", "S&P 500 Top"),
    ("META", "Meta Platforms", "S&P 500 Top"),
    ("BRK.B", "Berkshire Hathaway", "S&P 500 Top"),
    ("LLY", "Eli Lilly and Co.", "S&P 500 Top"),
    ("AVGO", "Broadcom Inc.", "S&P 500 Top"),
    ("JPM", "JPMorgan Chase", "S&P 500 Top"),
]

RUSSELL_2000_MUESTRA = [
    ("IWM", "iShares Russell 2000 ETF", "Indice General 2,000 Small Caps"),
    ("SMCI", "Super Micro Computer", "Hardware / Servidores"),
    ("IONQ", "IonQ Inc.", "Computacion Cuantica / Tech"),
    ("SOUN", "SoundHound AI", "Voz / Software Especializado"),
    ("RKLB", "Rocket Lab USA", "Aeroespacial / Defensa"),
    ("MARA", "MARA Holdings", "Activos Digitales / Infraestructura"),
]

UNIVERSOS_SECTORIALES = [
    {
        "nombre_foco": "Infraestructura Digital, Semiconductores y Computo",
        "activos": [
            ("NVDA", "NVIDIA Corp."),
            ("ASML", "ASML Holding"),
            ("AVGO", "Broadcom Inc."),
            ("MSFT", "Microsoft Corp."),
            ("AMD", "Advanced Micro Devices"),
            ("TSM", "Taiwan Semiconductor"),
        ],
        "tesis_sectorial": (
            "La expansion de capacidad de calculo exige inversion intensiva en "
            "capital (CapEx), energia y litografia avanzada. El punto critico no "
            "es el crecimiento de ingresos bruto, sino el retorno sobre el capital "
            "invertido (ROIC), la visibilidad de pedidos y la sostenibilidad de "
            "margenes frente a ciclos de inventario."
        ),
        "claves_lectura": [
            "Vigila si el gasto en CapEx de los hiperescaladores se traduce en flujo de caja libre real.",
            "Observa la brecha entre semiconductores ligados a centros de datos y demanda industrial/automotriz.",
            "Evalua multiplos de valoracion frente al ritmo de desaceleracion o aceleracion de ingresos.",
        ],
    },
    {
        "nombre_foco": "Materias Primas Estrategicas, Energia e Industria Pesada",
        "activos": [
            ("FCX", "Freeport-McMoRan (Cobre)"),
            ("XOM", "Exxon Mobil Corp."),
            ("CAT", "Caterpillar Inc."),
            ("ALB", "Albemarle Corp. (Litio)"),
            ("CVX", "Chevron Corp."),
            ("DE", "Deere & Company"),
        ],
        "tesis_sectorial": (
            "Los insumos fisicos y la maquinaria industrial actuan como cuello de "
            "botella real de la electrificacion, la construccion y la logistica. "
            "En este segmento mandan el costo marginal de extraccion, la disciplina "
            "de balance y la generacion de caja en la parte baja del ciclo."
        ),
        "claves_lectura": [
            "Contrasta el movimiento del precio spot con el comportamiento de las acciones productoras.",
            "Revisa disciplina de recompras y dividendos frente a fluctuaciones de inventarios globales.",
            "Analiza la sensibilidad del sector a la actividad manufacturera y al tipo de cambio.",
        ],
    },
    {
        "nombre_foco": "Sistema Financiero, Liquidez y Asignadores de Capital",
        "activos": [
            ("JPM", "JPMorgan Chase & Co."),
            ("BRK.B", "Berkshire Hathaway"),
            ("GS", "Goldman Sachs Group"),
            ("BLK", "BlackRock Inc."),
            ("BAC", "Bank of America Corp."),
            ("V", "Visa Inc."),
        ],
        "tesis_sectorial": (
            "Las entidades financieras y grandes asignadores reflejan de inmediato "
            "la pendiente de la curva de tasas, la calidad del credito corporativo y "
            "los flujos institucionales. La solvencia patrimonial y el costo de "
            "fondeo determinan quien absorbe volatilidad y quien compra activos baratos."
        ),
        "claves_lectura": [
            "Observa la diferencia entre bancos de inversion, banca minorista y gestores de activos.",
            "Atiende a senales de morosidad, condiciones crediticias y entradas/salidas en fondos.",
            "Valora la solidez de capital y la capacidad de retorno disciplinado al accionista.",
        ],
    },
    {
        "nombre_foco": "Salud, Biotecnologia y Consumo Defensivo de Flujo Estable",
        "activos": [
            ("LLY", "Eli Lilly and Co."),
            ("UNH", "UnitedHealth Group"),
            ("COST", "Costco Wholesale"),
            ("PG", "Procter & Gamble"),
            ("JNJ", "Johnson & Johnson"),
            ("KO", "The Coca-Cola Co."),
        ],
        "tesis_sectorial": (
            "Cuando la dispersion macroeconomica sube, los negocios con demanda "
            "inelastica, poder de fijacion de precios y baja sensibilidad al ciclo "
            "crediticio sirven como ancla de preservacion y generacion recurrente de caja."
        ),
        "claves_lectura": [
            "Compara el poder de fijacion de precios frente al costo de insumos y salarios.",
            "Distingue entre empresas de consumo basico estables y firmas de salud con mayor volatilidad regulatoria.",
            "Evalua el rol defensivo de estos activos cuando los indices amplios muestran fatiga.",
        ],
    },
]

ENFOQUES_PSICOLOGICOS = [
    {
        "titulo_psi": "Psicologia del Inversor: Sesgo de Confirmacion y FOMO en Tendencias Maduras",
        "analisis_psi": (
            "Cuando un activo o sector acumula subidas visibles, la mente humana tiende "
            "a filtrar la informacion que valida la continuidad del movimiento y a "
            "minimizar los datos de riesgo o valoracion exigente (sesgo de confirmacion). "
            "A ello se suma el temor a quedarse fuera (FOMO), que empuja a tomar "
            "decisiones reactivas justo cuando la relacion riesgo-recompensa es menos favorable.\n\n"
            "Desde una perspectiva conductual, el mercado amplifica emociones colectivas: "
            "euforia en fases de expansion y urgencia defensiva en correcciones. Registrar "
            "por escrito la tesis y las condiciones de invalidacion antes de actuar ayuda "
            "a separar el impulso emocional de la ejecucion metodica."
        ),
        "ejercicio_practico": (
            "EJERCICIO DE DISCIPLINA CONDUCTUAL:\n"
            "Antes de anadir o aumentar una posicion tras una noticia llamativa, responde "
            "por escrito: (1) Que dato objetivo cambiaria mi opinion en contra? "
            "(2) Estoy actuando por conviccion fundada o por prisa ante el precio? "
            "(3) Cual es el tamano de posicion que me permite dormir tranquilo si cae un 15%?"
        ),
    },
    {
        "titulo_psi": "Psicologia del Mercado: Aversion a la Perdida y Anclaje al Precio de Compra",
        "analisis_psi": (
            "El dolor psicologico de una perdida suele ser desproporcionado frente a la "
            "satisfaccion de una ganancia equivalente. Este desequilibrio lleva con "
            "frecuencia a aferrarse a posiciones deterioradas esperando 'recuperar el punto "
            "de entrada' (anclaje) o, por el contrario, a vender demasiado pronto los "
            "activos que funcionan bien para asegurar un alivio inmediato.\n\n"
            "El mercado no sabe a que precio compraste ni necesita devolverte tu punto de "
            "equilibrio. Evaluar cada posicion como si decidieras hoy si asignarias ese "
            "capital limpia el anclaje historico y mejora la asignacion futura."
        ),
        "ejercicio_practico": (
            "EJERCICIO DE DISCIPLINA CONDUCTUAL:\n"
            "Toma dos posiciones de tu seguimiento: una en ganancia y otra en perdida. "
            "Pregunta: si hoy tuvieras el efectivo equivalente a su valor actual, "
            "comprarias exactamente el mismo monto hoy? La respuesta revela si mandan "
            "los fundamentos o el anclaje emocional."
        ),
    },
    {
        "titulo_psi": "Psicologia del Ruido: Sobrecarga Informativa e Ilusion de Control",
        "analisis_psi": (
            "La abundancia constante de titulares y variaciones intradia genera la "
            "sensacion de que reaccionar a cada minuto equivale a controlar el riesgo. "
            "En realidad, perseguir cada titular suele elevar la rotacion, los costos "
            "de friccion y los errores por exceso de confianza.\n\n"
            "La calma operativa proviene de definir ventanas de revision claras (por "
            "ejemplo, cierres semanales) y distinguir entre fluctuacion estadistica "
            "normal y cambio estructural en el entorno."
        ),
        "ejercicio_practico": (
            "EJERCICIO DE DISCIPLINA CONDUCTUAL:\n"
            "Separa las noticias de esta semana en dos montones mentales: 'titulares "
            "que agitan el dia' y 'hechos que alteran flujos, tasas o balances en "
            "varios trimestres'. Concentra tu atencion solo en el segundo grupo."
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


def obtener_configuracion_semanal() -> tuple[int, dict, dict, dict]:
    hoy = datetime.date.today()
    num_edicion = hoy.isocalendar()[1]
    editorial = EDITORIALES_SEMANALES[num_edicion % len(EDITORIALES_SEMANALES)]
    universo = UNIVERSOS_SECTORIALES[num_edicion % len(UNIVERSOS_SECTORIALES)]
    psicologia = ENFOQUES_PSICOLOGICOS[num_edicion % len(ENFOQUES_PSICOLOGICOS)]
    return num_edicion, editorial, universo, psicologia


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
# 3. CONECTORES MULTIFUENTE DE DATOS DE MERCADO (SIN IA)
# ==============================================================================
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


def obtener_cotizacion_consolidada(
    ticker: str,
    nombre: str,
    categoria_extra: str = "",
    preferir_externo: bool = True,
) -> dict:
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
                "extra": categoria_extra,
                "cierre": dato["cierre"],
                "var_sem": dato["var_sem"],
                "fecha": dato["fecha"],
                "fuente": dato["fuente"],
            }

    return {
        "ticker": ticker,
        "nombre": nombre,
        "extra": categoria_extra,
        "cierre": None,
        "var_sem": None,
        "fecha": "N/D",
        "fuente": "Sin respuesta",
    }


def recolectar_todos_los_datos(universo: dict) -> dict:
    macro = [
        obtener_cotizacion_consolidada(t, n, "Benchmark", preferir_externo=False)
        for t, n in BENCHMARKS_MACRO
    ]
    top10 = [
        obtener_cotizacion_consolidada(t, n, seg, preferir_externo=True)
        for t, n, seg in TOP_10_EMPRESAS
    ]
    nasdaq10 = [
        obtener_cotizacion_consolidada(t, n, seg, preferir_externo=True)
        for t, n, seg in TOP_10_NASDAQ
    ]
    sp500_10 = [
        obtener_cotizacion_consolidada(t, n, seg, preferir_externo=True)
        for t, n, seg in TOP_10_SP500
    ]
    russell2000 = [
        obtener_cotizacion_consolidada(t, n, seg, preferir_externo=True)
        for t, n, seg in RUSSELL_2000_MUESTRA
    ]
    sectorial = [
        obtener_cotizacion_consolidada(t, n, universo["nombre_foco"], preferir_externo=True)
        for t, n in universo["activos"]
    ]

    return {
        "macro": macro,
        "top10": top10,
        "nasdaq10": nasdaq10,
        "sp500_10": sp500_10,
        "russell2000": russell2000,
        "sectorial": sectorial,
    }


# ==============================================================================
# 4. CONECTORES MULTIFUENTE DE NOTICIAS (ETIQUETAS Y RESUMEN EN ESPANOL)
# ==============================================================================
ETIQUETAS_SENTIMIENTO_ES = {
    "Bullish": "Alcista",
    "Somewhat-Bullish": "Moderadamente Alcista",
    "Neutral": "Neutral",
    "Somewhat-Bearish": "Moderadamente Bajista",
    "Bearish": "Bajista",
}


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
        salida = []
        for i in items[:5]:
            if i.get("title"):
                sent_raw = i.get("overall_sentiment_label", "Neutral")
                sent_es = ETIQUETAS_SENTIMIENTO_ES.get(sent_raw, "Macro")
                salida.append(
                    {
                        "titulo": i.get("title", ""),
                        "fuente": f"Alpha Vantage ({i.get('source', 'Mercado')})",
                        "etiqueta": f"Macro / {sent_es}",
                    }
                )
        return salida
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
            for i in items[:5]
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
                "language": "es,en",
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
                "q": "(mercados OR bolsa OR economia OR inflation OR Federal Reserve)",
                "sortBy": "publishedAt",
                "pageSize": 6,
                "apiKey": NEWS_API_KEY,
            },
            timeout=25,
        )
        items = resp.json().get("articles", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"NewsAPI ({(i.get('source') or {}).get('name', 'Prensa')})",
                "etiqueta": "Coyuntura",
            }
            for i in items[:5]
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
                "q": "economia OR finanzas OR markets",
                "language": "es,en",
                "category": "business",
            },
            timeout=25,
        )
        items = resp.json().get("results", [])
        return [
            {
                "titulo": i.get("title", ""),
                "fuente": f"NewsData ({i.get('source_id', 'Negocios')})",
                "etiqueta": "Negocios Globales",
            }
            for i in items[:5]
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

    return consolidadas[:20], conteo_por_fuente


# ==============================================================================
# 5. ANALISIS SEMANAL, PROYECCIONES PROXIMA SEMANA Y FILTRO NASDAQ VS S&P 500
# ==============================================================================
def resumen_grupo(filas: list[dict], etiqueta_grupo: str) -> str:
    validos = [f for f in filas if f["var_sem"] is not None]
    if not validos:
        return f"{etiqueta_grupo}: Sin variaciones numericas disponibles en esta corrida."
    prom = sum(f["var_sem"] for f in validos) / len(validos)
    alzas = sum(1 for f in validos if f["var_sem"] > 0)
    bajas = sum(1 for f in validos if f["var_sem"] < 0)
    mejor = max(validos, key=lambda f: f["var_sem"])
    peor = min(validos, key=lambda f: f["var_sem"])
    return (
        f"{etiqueta_grupo} ({len(validos)}/{len(filas)} con dato): promedio {prom:+.2f}%, "
        f"{alzas} en alza / {bajas} en baja. Destacado: {mejor['ticker']} ({mejor['var_sem']:+.2f}%) | "
        f"Rezagado: {peor['ticker']} ({peor['var_sem']:+.2f}%)."
    )


def construir_analisis_semanal_y_proyecciones(datos: dict, conteo_fuentes: dict) -> dict:
    res_macro = resumen_grupo(datos["macro"], "Benchmarks Macro")
    res_top10 = resumen_grupo(datos["top10"], "Top 10 Empresas")
    res_nq = resumen_grupo(datos["nasdaq10"], "Top 10 Nasdaq 100")
    res_sp = resumen_grupo(datos["sp500_10"], "Top 10 S&P 500")
    res_r2k = resumen_grupo(datos["russell2000"], "Russell 2000 / Small Caps")

    tickers_nq = {x["ticker"] for x in datos["nasdaq10"]}
    tickers_sp = {x["ticker"] for x in datos["sp500_10"]}
    comunes = sorted(tickers_nq & tickers_sp)
    solo_nq = sorted(tickers_nq - tickers_sp)
    solo_sp = sorted(tickers_sp - tickers_nq)

    prom_nq = None
    validos_nq = [x["var_sem"] for x in datos["nasdaq10"] if x["var_sem"] is not None]
    if validos_nq:
        prom_nq = sum(validos_nq) / len(validos_nq)

    prom_sp = None
    validos_sp = [x["var_sem"] for x in datos["sp500_10"] if x["var_sem"] is not None]
    if validos_sp:
        prom_sp = sum(validos_sp) / len(validos_sp)

    if prom_nq is not None and prom_sp is not None:
        brecha = prom_nq - prom_sp
        lectura_brecha = (
            f"El filtro entre los 10 mayores de Nasdaq 100 (promedio {prom_nq:+.2f}%) "
            f"y los 10 mayores del S&P 500 (promedio {prom_sp:+.2f}%) arroja una "
            f"diferencia de {brecha:+.2f} puntos porcentuales a favor de "
            f"{'Nasdaq 100' if brecha >= 0 else 'S&P 500'}."
        )
    else:
        lectura_brecha = (
            "El filtro compara la concentracion tecnologica/crecimiento de los 10 "
            "mayores del Nasdaq 100 frente a la composicion mas diversificada "
            "hacia finanzas y salud de los 10 mayores del S&P 500."
        )

    total_noticias = sum(conteo_fuentes.values())
    analisis_semana = (
        f"ANALISIS DE LA INFORMACION DE LA SEMANA:\n"
        f"{res_macro}\n"
        f"{res_top10}\n"
        f"{res_r2k}\n"
        f"Radar informativo: se consultaron 5 fuentes de noticias con {total_noticias} "
        f"registros capturados en esta corrida. Cuando las megacapitalizaciones "
        f"avanzan con mayor firmeza que el Russell 2000, el mercado privilegia "
        f"liquidez y escala; cuando el Russell 2000 acompana o supera, mejora la "
        f"amplitud y el apetito por riesgo domestico."
    )

    filtro_texto = (
        f"{lectura_brecha}\n"
        f"- Coinciden en ambos Top 10 ({len(comunes)}): {', '.join(comunes) if comunes else 'N/D'}.\n"
        f"- Exclusivos del Top 10 Nasdaq 100 ({len(solo_nq)}): {', '.join(solo_nq) if solo_nq else 'N/D'}.\n"
        f"- Exclusivos del Top 10 S&P 500 ({len(solo_sp)}): {', '.join(solo_sp) if solo_sp else 'N/D'}."
    )

    proyecciones_prox_semana = (
        "PROYECCIONES PARA LA PROXIMA SEMANA (ESCENARIOS DE SEGUIMIENTO):\n"
        "1. Escenario Base (Continuidad Selectiva): Si los benchmarks principales "
        "mantienen su rango sin shocks en tasas o energia, es probable que sigan "
        "predominando movimientos selectivos por resultados y flujo sectorial, con "
        "rotacion entre grandes lideres y nombres defensivos.\n"
        "2. Escenario Alcista de Amplitud: Si el Russell 2000 (IWM) logra sostener "
        "avances junto a SPY y QQQ, la recuperacion gana profundidad mas alla de "
        "las megacapitalizaciones y favorece a empresas medianas/pequenas.\n"
        "3. Escenario de Cautela / Riesgo: Si suben las tensiones en rendimientos "
        "de bonos o materias primas y el Russell 2000 retrocede con fuerza, conviene "
        "priorizar liquidez, balances solidos y control estricto del tamano de posicion."
    )

    return {
        "res_nq": res_nq,
        "res_sp": res_sp,
        "filtro_texto": filtro_texto,
        "analisis_semana": analisis_semana,
        "proyecciones_prox_semana": proyecciones_prox_semana,
    }


# ==============================================================================
# 6. GENERACION DE GRAFICOS (NASDAQ, S&P 500 Y RUSSELL 2000)
# ==============================================================================
def generar_grafico_barras(filas: list[dict], titulo: str, ruta_png: str) -> str | None:
    validos = [f for f in filas if f["var_sem"] is not None]
    if not validos:
        return None

    tickers = [f["ticker"] for f in validos][::-1]
    valores = [float(f["var_sem"]) for f in validos][::-1]
    colores = ["#167341" if v >= 0 else "#AF2D2D" for v in valores]

    plt.figure(figsize=(8.2, 3.6))
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    ax = plt.gca()
    ax.set_facecolor("#FAFBFD")
    plt.gcf().patch.set_facecolor("white")

    barras = plt.barh(tickers, valores, color=colores, height=0.58, edgecolor="none")
    plt.axvline(0, color="#121C2E", linewidth=0.9)
    plt.grid(axis="x", linestyle="--", alpha=0.45, color="#8A96A8")
    ax.set_axisbelow(True)

    plt.title(titulo, fontsize=10.5, fontweight="bold", color="#121C2E", pad=10, loc="left")
    plt.xlabel("Variacion (%) de referencia en la muestra", fontsize=8.5, color="#3C4652")
    plt.tick_params(axis="both", labelsize=8.5, colors="#1F2630")

    max_abs = max([abs(v) for v in valores] + [1.0])
    margen_x = max_abs * 0.22
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


def generar_graficos_tres_indices(datos: dict) -> dict:
    return {
        "nasdaq": generar_grafico_barras(
            datos["nasdaq10"],
            "Grafico Nasdaq 100 (Top 10) - Variacion Porcentual",
            "grafico_nasdaq.png",
        ),
        "sp500": generar_grafico_barras(
            datos["sp500_10"],
            "Grafico S&P 500 (Top 10) - Variacion Porcentual",
            "grafico_sp500.png",
        ),
        "russell2000": generar_grafico_barras(
            datos["russell2000"],
            "Grafico Russell 2000 (2,000 Small Caps / Muestra) - Variacion Porcentual",
            "grafico_russell2000.png",
        ),
    }


# ==============================================================================
# 7. MAQUETACION PDF EDITORIAL CON GRAFICOS (SIN IA)
# ==============================================================================
class RevistaFimothyPDF(FPDF):
    def __init__(self, num_edicion: int, fecha_str: str):
        super().__init__()
        self.num_edicion = num_edicion
        self.fecha_str = fecha_str
        self.set_margins(left=12, top=16, right=12)
        self.set_auto_page_break(auto=True, margin=18)

    @property
    def ancho_util(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def header(self):
        if self.page_no() == 1:
            return
        self.set_fill_color(18, 28, 46)
        self.rect(0, 0, 210, 14, "F")
        self.set_xy(12, 4)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(255, 255, 255)
        self.cell(
            self.ancho_util,
            6,
            limpiar_texto_pdf(
                f"FIMOTHY | FINANCIAL ENTERPRISE   -   EDICION N. {self.num_edicion:02d} ({self.fecha_str})"
            ),
            align="L",
            new_x="LMARGIN",
            new_y="NEXT",
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
            self.ancho_util,
            8,
            limpiar_texto_pdf(
                f"FIMOTHY Financial Enterprise | Mercados, Graficos, Analisis Semanal y Psicologia | Pagina {self.page_no()}"
            ),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    def portada(self, editorial: dict, universo: dict, macro_datos: list[dict], conteo_fuentes: dict):
        self.add_page()
        self.set_fill_color(18, 28, 46)
        self.rect(0, 0, 210, 56, "F")

        self.set_xy(14, 10)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(205, 170, 95)
        self.cell(
            182,
            5,
            limpiar_texto_pdf("PUBLICACION SEMANAL DE ANALISIS DE MERCADOS Y ESTRATEGIA"),
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
                f"EDICION N. {self.num_edicion:02d}   |   CIERRE SEMANAL: {self.fecha_str}   |   CON GRAFICOS"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_draw_color(205, 170, 95)
        self.set_line_width(0.8)
        self.line(14, 48, 196, 48)

        self.set_xy(14, 63)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(150, 115, 45)
        self.cell(
            182,
            5,
            limpiar_texto_pdf("TEMA EDITORIAL DE LA SEMANA"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

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
        self.cell(
            176,
            4.5,
            limpiar_texto_pdf(f"SECTOR EN FOCO ESTA SEMANA: {universo['nombre_foco']}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_x(17)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(60, 70, 82)
        tickers_txt = ", ".join(f"{t}" for t, _ in universo["activos"])
        self.cell(
            176,
            5,
            limpiar_texto_pdf(
                f"Canasta sectorial: {tickers_txt}  |  Graficos: Nasdaq 100, S&P 500 y Russell 2000"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.ln(7)
        self.set_x(14)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(18, 28, 46)
        self.cell(
            182,
            6,
            limpiar_texto_pdf("TABLERO DE REFERENCIA DE MERCADO"),
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

        activas = [f"{k} ({v})" for k, v in conteo_fuentes.items() if v > 0]
        fuentes_str = ", ".join(activas) if activas else "Fuentes en espera de respuesta"

        self.set_fill_color(18, 28, 46)
        self.rect(14, self.get_y(), 182, 34, "F")
        self.set_xy(17, self.get_y() + 3)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(205, 170, 95)
        self.cell(
            176,
            4.5,
            limpiar_texto_pdf("INDICE DE ESTA EDICION & COBERTURA DE DATOS"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(17)
        self.set_font("Helvetica", "", 8.2)
        self.set_text_color(235, 240, 246)
        self.multi_cell(
            176,
            4.2,
            limpiar_texto_pdf(
                "01. Editorial & Caso Practico  |  02. Psicologia del Inversor  |  03. Analisis Semanal & Proyecciones\n"
                "04. Top 10, Filtro Nasdaq vs S&P 500 y Graficos  |  05. Russell 2000 (Grafico) & Sectorial\n"
                f"06. Radar de Noticias en Espanol  |  Fuentes activas: {fuentes_str}"
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
        self.line(12, self.get_y() + 1, 198, self.get_y() + 1)
        self.ln(4)

    def parrafo(self, texto: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9.7)
        self.set_text_color(32, 36, 42)
        self.multi_cell(self.ancho_util, 5.1, limpiar_texto_pdf(texto))
        self.ln(3)

    def caja_destacada(self, titulo: str, texto: str):
        if self.get_y() > 232:
            self.add_page()
        self.set_x(self.l_margin)
        self.set_fill_color(244, 246, 250)
        self.set_draw_color(18, 28, 46)
        self.set_font("Helvetica", "B", 9.3)
        self.set_text_color(18, 28, 46)
        self.multi_cell(
            self.ancho_util,
            5.3,
            limpiar_texto_pdf(titulo),
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9.0)
        self.set_text_color(40, 45, 52)
        self.multi_cell(
            self.ancho_util,
            4.8,
            limpiar_texto_pdf(texto),
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.ln(3.5)

    def insertar_grafico(self, ruta_png: str | None, ancho_mm: float = 184):
        if not ruta_png or not os.path.exists(ruta_png):
            self.parrafo("Grafico no disponible por falta de datos numericos en esta corrida.")
            return
        if self.get_y() > 195:
            self.add_page()
        self.set_x(self.l_margin + (self.ancho_util - ancho_mm) / 2)
        self.image(ruta_png, w=ancho_mm)
        self.ln(3)

    def tabla_activos(self, filas: list[dict], titulo_col_extra: str = "Segmento / Foco"):
        if self.get_y() > 220:
            self.add_page()
        self.set_x(self.l_margin)
        headers = ["Ticker", "Compania / Activo", titulo_col_extra[:18], "Precio", "Var.", "Proveedor"]
        widths = [18, 52, 42, 23, 21, 28]

        self.set_fill_color(18, 28, 46)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 8.2)
        for h, w in zip(headers, widths):
            self.cell(w, 6.8, limpiar_texto_pdf(h), border=1, align="C", fill=True)
        self.ln()

        self.set_font("Helvetica", "", 8.2)
        for idx, f in enumerate(filas):
            if self.get_y() > 265:
                self.add_page()
                self.set_x(self.l_margin)
                self.set_fill_color(18, 28, 46)
                self.set_text_color(255, 255, 255)
                self.set_font("Helvetica", "B", 8.2)
                for h, w in zip(headers, widths):
                    self.cell(w, 6.8, limpiar_texto_pdf(h), border=1, align="C", fill=True)
                self.ln()
                self.set_font("Helvetica", "", 8.2)

            self.set_x(self.l_margin)
            fill = idx % 2 == 1
            self.set_fill_color(246, 248, 251)
            self.set_text_color(25, 30, 38)

            precio_txt = f"{f['cierre']:.2f}" if f["cierre"] is not None else "N/D"
            if f["var_sem"] is not None:
                signo = "+" if f["var_sem"] >= 0 else ""
                var_txt = f"{signo}{f['var_sem']:.2f}%"
            else:
                var_txt = "N/D"

            extra_txt = (f.get("extra") or f["fecha"])[:24]
            valores = [
                f["ticker"],
                f["nombre"][:26],
                extra_txt,
                precio_txt,
                var_txt,
                f["fuente"][:14],
            ]
            aligns = ["C", "L", "L", "R", "R", "C"]
            for val, w, al in zip(valores, widths, aligns):
                self.cell(w, 6.2, limpiar_texto_pdf(val), border=1, align=al, fill=fill)
            self.ln()
        self.ln(3.5)


def construir_pdf(
    num_edicion: int,
    fecha_str: str,
    editorial: dict,
    universo: dict,
    psicologia: dict,
    datos: dict,
    analisis: dict,
    graficos: dict,
    noticias: list[dict],
    conteo_fuentes: dict,
    ruta_salida: str = "revista_fimothy_semanal.pdf",
) -> str:
    pdf = RevistaFimothyPDF(num_edicion=num_edicion, fecha_str=fecha_str)

    # 1. Portada y tablero macro
    pdf.portada(editorial, universo, datos["macro"], conteo_fuentes)

    # 2. Editorial de estrategia, caso practico y reglas
    pdf.add_page()
    pdf.titulo_seccion("Seccion 01  |  Editorial de Estrategia", editorial["titulo"])
    pdf.parrafo(editorial["cuerpo"])
    pdf.caja_destacada("APLICACION PRACTICA DE LA SEMANA", editorial["caso_estudio"])
    pdf.caja_destacada(
        "CRITERIOS DE REVISION CUANTITATIVA",
        "\n".join(editorial["reglas"]),
    )

    # 3. Enfoque psicologico del inversor
    pdf.add_page()
    pdf.titulo_seccion("Seccion 02  |  Psicologia y Conducta del Inversor", psicologia["titulo_psi"])
    pdf.parrafo(psicologia["analisis_psi"])
    pdf.caja_destacada("EJERCICIO PRACTICO DE AUTOCONTROL", psicologia["ejercicio_practico"])

    # 4. Analisis de la informacion de la semana y proyecciones para la proxima semana
    pdf.add_page()
    pdf.titulo_seccion(
        "Seccion 03  |  Analisis Semanal y Proyecciones",
        "Lectura de la Semana y Escenarios para la Proxima Semana",
    )
    pdf.caja_destacada("ANALISIS DE LA INFORMACION DE LA SEMANA", analisis["analisis_semana"])
    pdf.caja_destacada(
        "PROYECCIONES A FUTURO PARA LA PROXIMA SEMANA",
        analisis["proyecciones_prox_semana"],
    )

    # 5. Top 10 empresas mas importantes + Filtro Nasdaq 100 vs S&P 500 + Graficos
    pdf.add_page()
    pdf.titulo_seccion(
        "Seccion 04  |  Las 10 Empresas Clave y Filtro Nasdaq vs. S&P 500",
        "Radiografia de las 10 Empresas Mas Importantes",
    )
    pdf.tabla_activos(datos["top10"], titulo_col_extra="Rol / Segmento")

    pdf.titulo_seccion(
        "Filtro Comparativo de Indices",
        "10 Mayores de Nasdaq 100 vs. 10 Mayores del S&P 500",
    )
    pdf.caja_destacada("RESULTADO DEL FILTRO NASDAQ 100 VS. S&P 500", analisis["filtro_texto"])
    pdf.tabla_activos(datos["nasdaq10"], titulo_col_extra="Referencia Nasdaq")
    pdf.insertar_grafico(graficos.get("nasdaq"))

    pdf.tabla_activos(datos["sp500_10"], titulo_col_extra="Referencia S&P 500")
    pdf.insertar_grafico(graficos.get("sp500"))

    # 6. Russell 2000 (2,000 pequenas empresas) + Grafico + Universo Sectorial
    pdf.add_page()
    pdf.titulo_seccion(
        "Seccion 05  |  Russell 2000 (2,000 Empresas Pequenas) y Sectorial",
        "Pulso del Russell 2000 y Amplitud de Mercado",
    )
    pdf.parrafo(
        "El indice Russell 2000 agrupa a unas 2,000 empresas de menor capitalizacion "
        "y permite medir el pulso real de la economia domestica y el apetito por "
        "riesgo mas alla de las grandes corporaciones."
    )
    pdf.tabla_activos(datos["russell2000"], titulo_col_extra="Amplitud / Tema")
    pdf.insertar_grafico(graficos.get("russell2000"))

    pdf.titulo_seccion(
        "Enfoque Sectorial Rotativo de la Semana",
        universo["nombre_foco"],
    )
    pdf.parrafo(universo["tesis_sectorial"])
    pdf.tabla_activos(datos["sectorial"], titulo_col_extra="Foco Sectorial")
    pdf.caja_destacada(
        "CLAVES DE LECTURA PARA ESTE SECTOR",
        "\n".join(f"- {c}" for c in universo["claves_lectura"]),
    )

    # 7. Radar de noticias en espanol y estado de conectores
    pdf.add_page()
    pdf.titulo_seccion(
        "Seccion 06  |  Radar de Noticias y Cobertura de Fuentes",
        "Titulares Recopilados de la Semana",
    )
    pdf.parrafo(
        "Nota editorial: Los titulares originales provenientes de proveedores internacionales "
        "conservan su redaccion de origen, mientras que las etiquetas, categorias, "
        "analisis, graficos y proyecciones de la revista se presentan en espanol."
    )

    if noticias:
        for idx, n in enumerate(noticias, start=1):
            linea = f"{idx:02d}. [{n['etiqueta']}] {n['titulo']}  --  Fuente: {n['fuente']}"
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "", 8.8)
            pdf.set_text_color(30, 35, 42)
            pdf.multi_cell(pdf.ancho_util, 4.6, limpiar_texto_pdf(linea))
            pdf.ln(1.2)
    else:
        pdf.parrafo("No se recibieron titulares nuevos en esta ventana de consulta.")

    pdf.ln(2)
    detalle_fuentes = "\n".join(
        f"- {fuente}: {cant} titular(es) recopilado(s)"
        for fuente, cant in conteo_fuentes.items()
    )
    pdf.caja_destacada("REPORTE DE CONECTORES DE NOTICIAS", detalle_fuentes)
    pdf.caja_destacada(
        "AVISO EDITORIAL",
        "Publicacion generada por FIMOTHY | FINANCIAL ENTERPRISE con fines informativos "
        "y de estudio de mercado. No constituye asesoria financiera personalizada.",
    )

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
# 9. PUNTO DE ENTRADA PRINCIPAL (SIN LLAMADAS A IA)
# ==============================================================================
def main() -> None:
    num_edicion, editorial, universo, psicologia = obtener_configuracion_semanal()
    fecha_str = datetime.date.today().strftime("%d/%m/%Y")

    datos = recolectar_todos_los_datos(universo)
    tickers_sec = [t for t, _ in universo["activos"]]
    noticias, conteo_fuentes = recolectar_noticias_consolidadas(tickers_sec)
    analisis = construir_analisis_semanal_y_proyecciones(datos, conteo_fuentes)
    graficos = generar_graficos_tres_indices(datos)

    ruta_pdf = construir_pdf(
        num_edicion=num_edicion,
        fecha_str=fecha_str,
        editorial=editorial,
        universo=universo,
        psicologia=psicologia,
        datos=datos,
        analisis=analisis,
        graficos=graficos,
        noticias=noticias,
        conteo_fuentes=conteo_fuentes,
    )

    enviar_telegram(ruta_pdf, num_edicion, editorial["titulo"], universo["nombre_foco"])
    print(f"Revista institucional con graficos generada con exito: {ruta_pdf}")


if __name__ == "__main__":
    main()
