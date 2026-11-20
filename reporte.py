import os
import sys
import time
import unicodedata
from datetime import datetime, timezone

import requests
from fpdf import FPDF

ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TICKERS_RAW = os.environ.get("TICKERS", "AAPL").strip()
FOCUS = os.environ.get("FOCUS", "growth").strip().lower()


def validar_entorno():
    faltantes = []
    if not ALPHAVANTAGE_API_KEY:
        faltantes.append("ALPHAVANTAGE_API_KEY")
    if not TELEGRAM_BOT_TOKEN:
        faltantes.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        faltantes.append("TELEGRAM_CHAT_ID")
    if faltantes:
        print(f"Faltan secretos de entorno: {', '.join(faltantes)}", file=sys.stderr)
        sys.exit(1)


def limpiar_texto_pdf(texto):
    if not texto:
        return ""
    normalizado = unicodedata.normalize("NFKD", str(texto))
    return normalizado.encode("latin-1", "ignore").decode("latin-1")


def obtener_json(params):
    url = "https://www.alphavantage.co/query"
    query = dict(params)
    query["apikey"] = ALPHAVANTAGE_API_KEY
    resp = requests.get(url, params=query, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "Note" in data or "Information" in data:
        print(f"Aviso API Alpha Vantage: {data.get('Note') or data.get('Information')}")
    return data


def a_float(valor):
    if valor in (None, "", "None", "N/A", "-"):
        return None
    try:
        return float(str(valor).replace(",", "").strip())
    except ValueError:
        return None


def fmt_num(val, dec=2, prefijo="", sufijo=""):
    if val is None:
        return "N/D"
    return f"{prefijo}{val:,.{dec}f}{sufijo}"


def analizar_ticker(ticker):
    ticker = ticker.strip().upper()
    overview = obtener_json({"function": "OVERVIEW", "symbol": ticker})
    time.sleep(1.2)
    income = obtener_json({"function": "INCOME_STATEMENT", "symbol": ticker})
    time.sleep(1.2)
    balance = obtener_json({"function": "BALANCE_SHEET", "symbol": ticker})

    nombre = overview.get("Name") or ticker
    sector = overview.get("Sector") or "N/D"
    pe = a_float(overview.get("PERatio"))
    peg = a_float(overview.get("PEGRatio"))
    roe = a_float(overview.get("ReturnOnEquityTTM"))
    margen_op = a_float(overview.get("OperatingMarginTTM"))
    deuda_patrimonio = a_float(overview.get("DebtToEquityRatio"))

    annual_inc = income.get("annualReports") or []
    crecimiento_ing = None
    if len(annual_inc) >= 2:
        rev_0 = a_float(annual_inc[0].get("totalRevenue"))
        rev_1 = a_float(annual_inc[1].get("totalRevenue"))
        if rev_0 is not None and rev_1 not in (None, 0):
            crecimiento_ing = ((rev_0 - rev_1) / abs(rev_1)) * 100.0

    liquidez_corriente = None
    annual_bal = balance.get("annualReports") or []
    if annual_bal:
        act_corr = a_float(annual_bal[0].get("totalCurrentAssets"))
        pas_corr = a_float(annual_bal[0].get("totalCurrentLiabilities"))
        if act_corr is not None and pas_corr not in (None, 0):
            liquidez_corriente = act_corr / pas_corr

    riesgos = []
    if deuda_patrimonio is not None and deuda_patrimonio > 2.0:
        riesgos.append(f"Apalancamiento elevado (D/E {deuda_patrimonio:.2f})")
    if liquidez_corriente is not None and liquidez_corriente < 1.0:
        riesgos.append(f"Liquidez corriente ajustada ({liquidez_corriente:.2f}x)")
    if pe is not None and pe > 35:
        riesgos.append(f"Valoracion exigente (P/E {pe:.1f}x)")
    if crecimiento_ing is not None and crecimiento_ing < 0:
        riesgos.append(f"Contracción anual de ingresos ({crecimiento_ing:.1f}%)")
    if not riesgos:
        riesgos.append("Sin alertas criticas evidentes en metricas base")

    if FOCUS == "solidity":
        resumen_enfoque = (
            f"Solidez: D/E {fmt_num(deuda_patrimonio)}, Liquidez {fmt_num(liquidez_corriente)}x, "
            f"Margen op. {fmt_num(margen_op, 1, '', '%')}."
        )
    else:
        resumen_enfoque = (
            f"Crecimiento: Ingresos YoY {fmt_num(crecimiento_ing, 1, '', '%')}, "
            f"ROE {fmt_num(roe, 1, '', '%')}, P/E {fmt_num(pe, 1, '', 'x')}, PEG {fmt_num(peg)}."
        )

    return {
        "ticker": ticker,
        "nombre": nombre,
        "sector": sector,
        "pe": pe,
        "peg": peg,
        "roe": roe,
        "margen_op": margen_op,
        "deuda_patrimonio": deuda_patrimonio,
        "liquidez_corriente": liquidez_corriente,
        "crecimiento_ing": crecimiento_ing,
        "riesgos": riesgos,
        "resumen_enfoque": resumen_enfoque,
    }


def construir_mensaje_telegram(resultados, enfoque, fecha_str):
    enfoque_label = "Solidez Financiera" if enfoque == "solidity" else "Crecimiento"
    lineas = [
        f"📊 *Informe Fundamental ({enfoque_label})*",
        f"🕒 {fecha_str}",
        "",
    ]
    for r in resultados:
        lineas.append(f"*{r['ticker']}* — {r['nombre']} ({r['sector']})")
        lineas.append(f"• {r['resumen_enfoque']}")
        lineas.append(f"• Riesgos: {'; '.join(r['riesgos'])}")
        lineas.append("")
    return "\n".join(lineas).strip()


def generar_pdf(resultados, enfoque, fecha_str, ruta_pdf):
    enfoque_label = "Solidez Financiera" if enfoque == "solidity" else "Crecimiento"
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_x(pdf.l_margin)
    pdf.cell(
        pdf.epw,
        10,
        limpiar_texto_pdf(f"Informe fundamental - {enfoque_label}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 10)
    pdf.set_x(pdf.l_margin)
    pdf.cell(
        pdf.epw,
        6,
        limpiar_texto_pdf(f"Fecha (UTC): {fecha_str}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_x(pdf.l_margin)
    pdf.cell(
        pdf.epw,
        6,
        limpiar_texto_pdf("Criterio: Fundamentos y riesgos reales por encima de sentimiento."),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    for r in resultados:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(pdf.l_margin)
        pdf.cell(
            pdf.epw,
            8,
            limpiar_texto_pdf(f"{r['ticker']} - {r['nombre']} ({r['sector']})"),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        pdf.set_font("Helvetica", "", 10)
        metricas_line = (
            f"P/E: {fmt_num(r['pe'], 1, '', 'x')} | PEG: {fmt_num(r['peg'])} | "
            f"ROE: {fmt_num(r['roe'], 1, '', '%')} | Margen Op.: {fmt_num(r['margen_op'], 1, '', '%')} | "
            f"D/E: {fmt_num(r['deuda_patrimonio'])} | Liq. Corr.: {fmt_num(r['liquidez_corriente'])}x | "
            f"Ingresos YoY: {fmt_num(r['crecimiento_ing'], 1, '', '%')}"
        )
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            pdf.epw,
            6,
            limpiar_texto_pdf(metricas_line),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        val_line = f"Lectura ({enfoque_label}): {r['resumen_enfoque']}"
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            pdf.epw,
            6,
            limpiar_texto_pdf(val_line),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        riesgos_line = f"Riesgos clave: {'; '.join(r['riesgos'])}"
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            pdf.epw,
            6,
            limpiar_texto_pdf(riesgos_line),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(3)

    pdf.output(ruta_pdf)


def enviar_telegram_mensaje(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, json=payload, timeout=30)
    if not resp.ok:
        payload.pop("parse_mode", None)
        resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()


def enviar_telegram_documento(ruta_pdf, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(ruta_pdf, "rb") as f:
        files = {"document": (os.path.basename(ruta_pdf), f, "application/pdf")}
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
        resp = requests.post(url, data=data, files=files, timeout=60)
    resp.raise_for_status()


def main():
    validar_entorno()
    enfoque = "solidity" if FOCUS == "solidity" else "growth"
    tickers = [t.strip().upper() for t in TICKERS_RAW.split(",") if t.strip()]
    if not tickers:
        tickers = ["AAPL"]

    fecha_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    resultados = [analizar_ticker(t) for t in tickers]

    mensaje = construir_mensaje_telegram(resultados, enfoque, fecha_str)
    ruta_pdf = "informe.pdf"
    generar_pdf(resultados, enfoque, fecha_str, ruta_pdf)

    enviar_telegram_mensaje(mensaje)
    enviar_telegram_documento(ruta_pdf, caption=f"Reporte PDF ({enfoque}) - {fecha_str}")
    print("Reporte enviado correctamente a Telegram.")


if __name__ == "__main__":
    main()
