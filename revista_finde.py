import datetime
import os
import unicodedata
import requests
from fpdf import FPDF

# ==============================================================================
# 1. VARIABLES DE ENTORNO (GITHUB SECRETS)
# ==============================================================================
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROK_KEY = os.environ.get("GROK_API_KEY")
META_KEY = os.environ.get("META_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ==============================================================================
# 2. TEMAS FORMATIVOS, PSICOLÓGICOS Y DE ORIENTACIÓN (ROTACIÓN SEMANAL)
# ==============================================================================
TEMAS_FORMATIVOS = [
    {
        "titulo": "El ruido de la noticia frente a la estructura del capital",
        "eje_formativo": (
            "Distinguir un cambio estructural real de una reacción emocional, "
            "titular sensacionalista o escándalo pasajero."
        ),
        "orientacion_psicologica": (
            "Sesgo de recencia, urgencia por responder al instante y búsqueda "
            "de certeza en escenarios ambiguos."
        ),
    },
    {
        "titulo": "Psicología de la manada: euforia, pánico y contagio social",
        "eje_formativo": (
            "Cómo influye el movimiento colectivo cuando una empresa sube o cae "
            "con fuerza y qué suele pasar desapercibido."
        ),
        "orientacion_psicologica": (
            "Contagio emocional, presión de pertenencia y diferencia entre "
            "análisis propio e imitación reactiva."
        ),
    },
    {
        "titulo": "Ego, costo hundido y criterio frente al error",
        "eje_formativo": (
            "Cómo revisar una lectura o tesis cuando los hechos cambian, sin "
            "confundir el valor de una decisión con el amor propio."
        ),
        "orientacion_psicologica": (
            "Defensa narcisista, racionalización posterior al hecho y madurez "
            "para ajustar el rumbo a tiempo."
        ),
    },
    {
        "titulo": "Ética práctica, incentivos y naturaleza amoral del mercado",
        "eje_formativo": (
            "Leer los hechos financieros como un mecanismo regido por "
            "incentivos, liquidez, expectativas y riesgo, no por juicios morales."
        ),
        "orientacion_psicologica": (
            "Superar el pensamiento mágico o moralizador y cultivar sobriedad, "
            "disciplina y autonomía de juicio."
        ),
    },
]


def obtener_edicion_y_tema() -> tuple[int, dict]:
    hoy = datetime.date.today()
    num_edicion = hoy.isocalendar()[1]
    tema = TEMAS_FORMATIVOS[num_edicion % len(TEMAS_FORMATIVOS)]
    return num_edicion, tema


def obtener_hechos_semana() -> str:
    """
    Reemplaza o amplía este bloque con las noticias, movimientos empresariales
    o datos verificados de la semana que quieras someter al análisis.
    """
    return (
        "Hechos de la semana (prueba): Seguimiento de noticias corporativas, "
        "movimientos destacados en empresas o sectores y cambios de ánimo del "
        "mercado durante los últimos siete días. Trabaja únicamente con los "
        "hechos indicados aquí sin inventar cifras ni eventos."
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
# 3. CONECTORES DE INTELIGENCIA ARTIFICIAL
# ==============================================================================
def consultar_gemini(prompt_sistema: str, prompt_usuario: str) -> str:
    if not GEMINI_KEY:
        return "Clave GEMINI_API_KEY no configurada."
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": prompt_sistema}]},
        "contents": [{"role": "user", "parts": [{"text": prompt_usuario}]}],
        "generationConfig": {"temperature": 0.4},
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        return f"Gemini no disponible en esta corrida ({exc})."


def consultar_openai_compatible(
    url: str,
    api_key: str | None,
    modelo: str,
    etiqueta: str,
    prompt_sistema: str,
    prompt_usuario: str,
) -> str:
    if not api_key:
        return f"Clave para {etiqueta} no configurada."
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": modelo,
                "temperature": 0.4,
                "messages": [
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return f"{etiqueta} no disponible en esta corrida ({exc})."


def construir_edicion(num_edicion: int, tema: dict, hechos_semana: str) -> dict:
    base_sistema = (
        "Eres parte del Comité Editorial y Formativo de FIMOTHY | FINANCIAL ENTERPRISE. "
        "Mantén un tono sobrio, claro, formativo y estratégico, integrando "
        "educación financiera, psicología profunda y filosofía práctica sin "
        "sermones moralistas. No inventes cifras ni noticias que no estén en "
        "los hechos entregados."
    )

    contexto = (
        f"Edición N.º {num_edicion:02d}\n"
        f"Tema de la semana: {tema['titulo']}\n"
        f"Eje formativo: {tema['eje_formativo']}\n"
        f"Orientación psicológica: {tema['orientacion_psicologica']}\n\n"
        f"Noticias y hechos de la semana:\n{hechos_semana}\n"
    )

    articulo_gemini = consultar_gemini(
        base_sistema + " Redacta el artículo formativo y de psicología aplicada.",
        contexto
        + "\nEscribe un artículo educativo y bien estructurado (180-240 palabras) "
        "sobre el tema de la semana y cómo leer noticias o movimientos de empresas "
        "con criterio y templanza.",
    )

    opinion_grok = consultar_openai_compatible(
        "https://api.x.ai/v1/chat/completions",
        GROK_KEY,
        "grok-3-mini",
        "Grok",
        base_sistema + " Aporta un análisis directo, sin rodeos ni autocomplacencia.",
        contexto
        + "\nOpina sobre el impacto de subidas, caídas o escándalos en las "
        "decisiones y qué suele pasar por alto el lector promedio (140-190 palabras).",
    )

    opinion_meta = consultar_openai_compatible(
        "https://api.meta.ai/v1/chat/completions",
        META_KEY,
        "muse-spark-1.3",
        "Meta",
        base_sistema + " Aporta orientación práctica, estructura de criterio y dinámica social.",
        contexto
        + "\nDa orientación práctica y formativa sobre la dinámica colectiva ante "
        "las noticias de la semana y qué hábitos mentales conviene entrenar "
        "(140-190 palabras).",
    )

    debate_comite = consultar_gemini(
        base_sistema + " Modera y sintetiza el diálogo entre las tres voces.",
        contexto
        + "\nA continuación tienes los tres aportes del comité:\n"
        + f"[GEMINI]: {articulo_gemini}\n\n"
        + f"[GROK]: {opinion_grok}\n\n"
        + f"[META]: {opinion_meta}\n\n"
        + "Redacta un breve 'Diálogo y Contraste del Comité' donde las tres IA "
        "interactúen entre sí: dónde coinciden, qué matices o tensiones aparecen "
        "y 2 recomendaciones formativas concretas.",
    )

    return {
        "articulo_principal": articulo_gemini,
        "column_grok": opinion_grok,
        "column_meta": opinion_meta,
        "dialogo_comite": debate_comite,
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
            f"REVISTA SEMANAL  |  EDICION N. {self.num_edicion:02d}  |  {self.fecha_str}"
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
    pdf.cell(0, 4.5, limpiar_texto_pdf("TEMA FORMATIVO Y PSICOLOGIA DE LA SEMANA"), ln=True)

    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 30, 48)
    pdf.multi_cell(180, 5.5, limpiar_texto_pdf(tema["titulo"]))

    pdf.set_x(15)
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(70, 80, 95)
    pdf.multi_cell(180, 4.5, limpiar_texto_pdf(f"Enfoque: {tema['eje_formativo']}"))

    pdf.ln(7)

    pdf.agregar_seccion(
        "1. Articulo Formativo y Psicologia Aplicada (Gemini)",
        contenido["articulo_principal"],
    )
    pdf.agregar_seccion(
        "2. Lectura Critica ante Noticias y Eventos (Grok)",
        contenido["column_grok"],
    )
    pdf.agregar_seccion(
        "3. Orientacion Practica y Dinamica Colectiva (Meta)",
        contenido["column_meta"],
    )
    pdf.agregar_seccion(
        "4. Interaccion y Debate del Comite Editorial",
        contenido["dialogo_comite"],
    )

    pdf.output(ruta_salida)
    return ruta_salida


# ==============================================================================
# 5. ENVÍO A TELEGRAM
# ==============================================================================
def enviar_telegram(ruta_pdf: str, num_edicion: int, titulo_tema: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Aviso: TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados.")
        return

    caption = limpiar_texto_pdf(
        f"FIMOTHY | FINANCIAL ENTERPRISE - Revista Semanal Ed. N. {num_edicion:02d}\n"
        f"Tema: {titulo_tema}"
    )[:1000]

    with open(ruta_pdf, "rb") as doc:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
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
