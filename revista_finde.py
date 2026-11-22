import datetime
import os
import time
import unicodedata
import requests
from fpdf import FPDF

# ==============================================================================
# 1. VARIABLES DE ENTORNO (GITHUB SECRETS)
# ==============================================================================
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ==============================================================================
# 2. EJES FINANCIEROS Y DE RIESGO (ROTACIÓN SEMANAL)
# ==============================================================================
TEMAS_FINANCIEROS = [
    {
        "titulo": "Señal estructural frente a ruido de mercado",
        "eje_financiero": (
            "Separar cambios en fundamentos, flujos de caja, tasas o liquidez "
            "de reacciones de corto plazo impulsadas por titulares."
        ),
        "enfoque_riesgo": (
            "Evaluar asimetría de riesgo, tamaño de posición y horizonte "
            "temporal antes de tomar decisiones."
        ),
    },
    {
        "titulo": "Liquidez, apalancamiento y dinámica de consenso",
        "eje_financiero": (
            "Analizar cómo la liquidez y el posicionamiento colectivo amplifican "
            "movimientos bruscos al alza o a la baja."
        ),
        "enfoque_riesgo": (
            "Identificar puntos de vulnerabilidad ante cambios en expectativas "
            "o condiciones de financiamiento."
        ),
    },
    {
        "titulo": "Revisión de tesis y control de sesgos en cartera",
        "eje_financiero": (
            "Contrastar la tesis inicial de una inversión o estrategia frente "
            "a datos nuevos y resultados verificables."
        ),
        "enfoque_riesgo": (
            "Evitar aferrarse a pérdidas o decisiones pasadas cuando cambia el "
            "escenario de riesgo/retorno."
        ),
    },
    {
        "titulo": "Incentivos económicos, márgenes y sostenibilidad",
        "eje_financiero": (
            "Leer los movimientos corporativos y sectoriales a través de "
            "incentivos, costos, márgenes y asignación de capital."
        ),
        "enfoque_riesgo": (
            "Distinguir crecimiento sostenible de expansión frágil o "
            "dependiente de condiciones favorables."
        ),
    },
]


def obtener_edicion_y_tema() -> tuple[int, dict]:
    hoy = datetime.date.today()
    num_edicion = hoy.isocalendar()[1]
    tema = TEMAS_FINANCIEROS[num_edicion % len(TEMAS_FINANCIEROS)]
    return num_edicion, tema


def obtener_hechos_semana() -> str:
    """
    Reemplaza o amplía este bloque con las noticias, cifras, movimientos de
    precios, tasas o eventos verificados de la semana.
    """
    return (
        "Hechos de la semana (prueba): Seguimiento de noticias financieras y "
        "corporativas, movimientos relevantes en sectores o activos y "
        "condiciones de mercado de los últimos siete días. Trabaja únicamente "
        "con los hechos indicados aquí sin inventar cifras ni eventos."
    )


def limpiar_texto_pdf(texto: str) -> str:
    """Normaliza caracteres para que la fuente estándar de FPDF no falle."""
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
    }
    for orig, dest in reemplazos.items():
        texto = texto.replace(orig, dest)
    normalizado = unicodedata.normalize("NFKD", texto)
    return normalizado.encode("latin-1", "ignore").decode("latin-1")


# ==============================================================================
# 3. MOTOR DE ANÁLISIS FINANCIERO (GEMINI)
# ==============================================================================
def consultar_gemini(prompt_sistema: str, prompt_usuario: str) -> str:
    if not GEMINI_KEY:
        return "Clave GEMINI_API_KEY no configurada."

    modelos_candidatos = []
    for m in [GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.0-flash"]:
        if m and m not in modelos_candidatos:
            modelos_candidatos.append(m)

    payload = {
        "systemInstruction": {"parts": [{"text": prompt_sistema}]},
        "contents": [{"role": "user", "parts": [{"text": prompt_usuario}]}],
        "generationConfig": {"temperature": 0.35},
    }

    ultimo_error = ""
    for modelo in modelos_candidatos:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{modelo}:generateContent?key={GEMINI_KEY}"
        )
        max_intentos = 3
        for intento in range(1, max_intentos + 1):
            try:
                resp = requests.post(url, json=payload, timeout=60)
                if resp.status_code in (429, 503):
                    detalle = resp.text.strip().replace("\n", " ")[:220]
                    ultimo_error = f"({resp.status_code} con '{modelo}'): {detalle}"
                    if intento < max_intentos:
                        time.sleep(2 * intento)
                        continue
                    break
                if not resp.ok:
                    detalle = resp.text.strip().replace("\n", " ")[:220]
                    ultimo_error = f"({resp.status_code} con '{modelo}'): {detalle}"
                    break
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as exc:
                ultimo_error = f"(modelo '{modelo}'): {exc}"
                if intento < max_intentos:
                    time.sleep(2 * intento)
                    continue
                break

    return f"Gemini no disponible {ultimo_error}".strip()


def construir_edicion(num_edicion: int, tema: dict, hechos_semana: str) -> dict:
    base_sistema = (
        "Eres analista y editor de FIMOTHY | FINANCIAL ENTERPRISE. "
        "Redacta con enfoque estrictamente financiero, técnico, sobrio y "
        "objetivo: fundamentos, liquidez, incentivos, valoración y gestión de "
        "riesgo. No inventes cifras, precios ni noticias que no estén en los "
        "hechos entregados ni des asesoría personalizada."
    )

    contexto = (
        f"Edición N.º {num_edicion:02d}\n"
        f"Eje de la semana: {tema['titulo']}\n"
        f"Enfoque financiero: {tema['eje_financiero']}\n"
        f"Gestión de riesgo: {tema['enfoque_riesgo']}\n\n"
        f"Hechos y datos de la semana:\n{hechos_semana}\n"
    )

    panorama_macro = consultar_gemini(
        base_sistema + " Redacta el análisis principal de mercado y fundamentos.",
        contexto
        + "\nEscribe un análisis financiero claro y estructurado (180-240 palabras) "
        "sobre el eje de la semana y cómo interpretar los hechos reportados.",
    )

    lectura_catalizadores = consultar_gemini(
        base_sistema + " Analiza catalizadores, incentivos y reacción del mercado.",
        contexto
        + "\nExamina qué catalizadores o incentivos importan más en este escenario "
        "y qué elementos suelen ser ruido de corto plazo (140-190 palabras).",
    )

    riesgos_escenarios = consultar_gemini(
        base_sistema + " Evalúa riesgos clave, supuestos críticos y escenarios.",
        contexto
        + "\nDetalla los principales riesgos, supuestos a vigilar y qué "
        "confirmaría o invalidaría una lectura del escenario (140-190 palabras).",
    )

    plan_seguimiento = consultar_gemini(
        base_sistema + " Sintetiza puntos concretos de monitoreo para la próxima semana.",
        contexto
        + "\nCon base en los análisis anteriores:\n"
        + f"[PANORAMA]: {panorama_macro}\n\n"
        + f"[CATALIZADORES]: {lectura_catalizadores}\n\n"
        + f"[RIESGOS]: {riesgos_escenarios}\n\n"
        + "Redacta una síntesis ejecutiva y 3 puntos concretos de seguimiento "
        "financiero y de riesgo para los próximos días.",
    )

    return {
        "panorama_macro": panorama_macro,
        "lectura_catalizadores": lectura_catalizadores,
        "riesgos_escenarios": riesgos_escenarios,
        "plan_seguimiento": plan_seguimiento,
    }


# ==============================================================================
# 4. GENERACIÓN DEL PDF (ESTILO REVISTA INSTITUCIONAL)
# ==============================================================================
class RevistaPDF(FPDF):
    def __init__(self, num_edicion: int, fecha_str: str):
        super().__init__()
        self.num_edicion = num_edicion
        self.fecha_str = fecha_str
        self.set_auto_page_break(auto=True, margin=16)

    def header(self):
        self.set_fill_color(20, 30, 48)
        self.rect(0, 0, 210, 24, "F")

        self.set_xy(12, 5)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 6, limpiar_texto_pdf("FIMOTHY | FINANCIAL ENTERPRISE"), ln=True)

        self.set_x(12)
        self.set_text_color(195, 208, 225)
        self.set_font("Helvetica", "", 8.5)
        subtitulo = (
            f"REVISTA FINANCIERA SEMANAL  |  EDICION N. {self.num_edicion:02d}  |  {self.fecha_str}"
        )
        self.cell(0, 5, limpiar_texto_pdf(subtitulo), ln=True)

        self.set_draw_color(180, 150, 90)
        self.set_line_width(0.6)
        self.line(12, 26, 198, 26)
        self.ln(8)
        self.set_text_color(25, 25, 25)

    def footer(self):
        self.set_y(-13)
        self.set_text_color(110, 110, 110)
        self.set_font("Helvetica", "I", 8)
        pie = (
            f"Fimothy Financial Enterprise - Revista Semanal (Edicion N. {self.num_edicion:02d}) "
            f"| Pagina {self.page_no()}"
        )
        self.cell(0, 8, limpiar_texto_pdf(pie), align="C")

    def agregar_seccion(self, titulo: str, cuerpo: str):
        self.set_font("Helvetica", "B", 11.5)
        self.set_text_color(20, 30, 48)
        self.cell(0, 7, limpiar_texto_pdf(titulo), ln=True)

        self.set_draw_color(210, 215, 222)
        self.set_line_width(0.3)
        self.line(12, self.get_y(), 198, self.get_y())
        self.ln(2.5)

        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, limpiar_texto_pdf(cuerpo))
        self.ln(5)


def generar_pdf(
    num_edicion: int,
    fecha_str: str,
    tema: dict,
    contenido: dict,
    ruta_salida: str = "revista_fimothy_semanal.pdf",
) -> str:
    pdf = RevistaPDF(num_edicion=num_edicion, fecha_str=fecha_str)
    pdf.add_page()

    pdf.set_fill_color(244, 246, 249)
    pdf.set_draw_color(20, 30, 48)
    pdf.rect(12, pdf.get_y(), 186, 28, "DF")

    y_actual = pdf.get_y() + 3
    pdf.set_xy(15, y_actual)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(140, 105, 40)
    pdf.cell(0, 4.5, limpiar_texto_pdf("EJE FINANCIERO DE LA SEMANA"), ln=True)

    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 30, 48)
    pdf.multi_cell(180, 5.5, limpiar_texto_pdf(tema["titulo"]))

    pdf.set_x(15)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(70, 80, 95)
    pdf.multi_cell(180, 4.5, limpiar_texto_pdf(f"Enfoque: {tema['eje_financiero']}"))

    pdf.ln(7)

    pdf.agregar_seccion(
        "1. Panorama Financiero y Fundamentos",
        contenido["panorama_macro"],
    )
    pdf.agregar_seccion(
        "2. Catalizadores, Incentivos y Ruido",
        contenido["lectura_catalizadores"],
    )
    pdf.agregar_seccion(
        "3. Riesgos Clave y Escenarios",
        contenido["riesgos_escenarios"],
    )
    pdf.agregar_seccion(
        "4. Sintesis y Puntos de Seguimiento",
        contenido["plan_seguimiento"],
    )

    pdf.output(ruta_salida)
    return ruta_salida


# ==============================================================================
# 5. ENVÍO A TELEGRAM
# ==============================================================================
def enviar_telegram(ruta_pdf: str, num_edicion: int, titulo_tema: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Aviso: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados.")
        return

    caption = limpiar_texto_pdf(
        f"FIMOTHY | FINANCIAL ENTERPRISE - Revista Semanal Ed. N. {num_edicion:02d}\n"
        f"Eje: {titulo_tema}"
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
# 6. PUNTO DE ENTRADA
# ==============================================================================
def main() -> None:
    num_edicion, tema = obtener_edicion_y_tema()
    fecha_str = datetime.date.today().strftime("%d/%m/%Y")
    hechos_semana = obtener_hechos_semana()

    contenido = construir_edicion(num_edicion, tema, hechos_semana)
    ruta_pdf = generar_pdf(num_edicion, fecha_str, tema, contenido)
    enviar_telegram(ruta_pdf, num_edicion, tema["titulo"])
    print(f"Revista generada con éxito: {ruta_pdf}")


if __name__ == "__main__":
    main()
