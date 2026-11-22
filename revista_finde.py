import datetime
import json
import os
import requests
from fpdf import FPDF

# 1. Leer claves desde GitHub Secrets / variables de entorno
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GROK_KEY = os.environ.get("GROK_API_KEY")
META_KEY = os.environ.get("META_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

TEMAS_SEMANALES = [
    {
        "titulo": "El Superyó moralista frente a la pulsión del mercado",
        "eje": (
            "Cómo el deseo de certidumbre o moralidad choca con la naturaleza "
            "amoral de los precios, el pánico y la codicia colectiva."
        ),
    },
    {
        "titulo": "Mimetismo y manada: cuando seguir a la multitud cuesta caro",
        "eje": (
            "Dinámica social del consenso y por qué las entradas tardías nacen "
            "de la necesidad de pertenencia."
        ),
    },
    {
        "titulo": "Anclaje, falacia del costo hundido y ego del inversor",
        "eje": (
            "Por qué cuesta cortar una tesis rota o aceptar una pérdida "
            "pequeña antes de que se vuelva estructural."
        ),
    },
]


def obtener_tema() -> dict:
    semana_iso = datetime.date.today().isocalendar()[1]
    return TEMAS_SEMANALES[semana_iso % len(TEMAS_SEMANALES)]


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
        "generationConfig": {"temperature": 0.35},
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"Sin respuesta de Gemini en esta corrida ({e})."


def consultar_openai_compatible(
    url: str, api_key: str | None, modelo: str, nombre_ia: str,
    prompt_sistema: str, prompt_usuario: str
) -> str:
    if not api_key:
        return f"Clave para {nombre_ia} no configurada."
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": modelo,
                "temperature": 0.35,
                "messages": [
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario},
                ],
            },
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Sin respuesta de {nombre_ia} en esta corrida ({e})."


def generar_pdf(texto_revista: str, ruta_pdf: str = "revista_fimothy.pdf") -> str:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "FIMOTHY | FINANCIAL ENTERPRISE - REVISTA SEMANAL", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Fecha: {datetime.date.today().isoformat()}", ln=True)
    pdf.ln(4)

    # Limpia caracteres no compatibles con latin-1 básico en FPDF estándar
    texto_seguro = texto_revista.encode("latin-1", "replace").decode("latin-1")
    pdf.multi_cell(0, 6, texto_seguro)
    pdf.output(ruta_pdf)
    return ruta_pdf


def enviar_telegram(ruta_pdf: str, resumen: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID; se omite envío.")
        return
    with open(ruta_pdf, "rb") as doc:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": resumen[:1000]},
            files={"document": doc},
            timeout=60,
        ).raise_for_status()


def main() -> None:
    tema = obtener_tema()
    # Aquí puedes traer o armar los datos verificados de la semana
    datos_semana = "Resumen semanal de mercado y focos de observación."

    sistema = (
        "Eres analista y editor de FIMOTHY | FINANCIAL ENTERPRISE. "
        "Hablas como financista sobrio y estratégico, integrando psicología "
        "financiera y dinámica social sin sermones morales. "
        "Usa solo los datos entregados sin inventar cifras."
    )
    usuario = (
        f"Tema de la semana: {tema['titulo']} ({tema['eje']})\n"
        f"Datos:\n{datos_semana}\n"
        "Redacta un análisis claro, conciso y estructurado."
    )

    aporte_gemini = consultar_gemini(sistema, usuario)
    # Ajusta la URL y el modelo según el proveedor exacto de tu clave de Grok y Meta
    aporte_grok = consultar_openai_compatible(
        "https://api.x.ai/v1/chat/completions",
        GROK_KEY,
        "grok-3-mini",
        "Grok",
        sistema,
        usuario,
    )
    aporte_meta = consultar_openai_compatible(
        "https://api.meta.ai/v1/chat/completions",
        META_KEY,
        "muse-spark-1.3",
        "Meta",
        sistema,
        usuario,
    )

    cuerpo = (
        f"TEMA: {tema['titulo']}\n\n"
        f"--- ANALISIS GEMINI ---\n{aporte_gemini}\n\n"
        f"--- ANALISIS GROK ---\n{aporte_grok}\n\n"
        f"--- ANALISIS META ---\n{aporte_meta}\n"
    )

    pdf_path = generar_pdf(cuerpo)
    enviar_telegram(
        pdf_path,
        f"Revista Semanal FIMOTHY - {tema['titulo']}",
    )


if __name__ == "__main__":
    main()
