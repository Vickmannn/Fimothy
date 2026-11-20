import os
import sys
import time
from datetime import datetime, timezone
import requests
from fpdf import FPDF

ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TICKERS_RAW = os.environ.get("TICKERS", "AAPL")
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


def av_get(params: dict) -> dict:
    url = "https://www.alphavantage.co/query"
    query = dict(params)
    query["apikey"] = ALPHAVANTAGE_API_KEY
    resp = requests.get(url, params=query, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "Note" in data or "Information" in data:
        raise RuntimeError(f"Límite o aviso de Alpha Vantage: {data.get('Note') or data.get('Information')}")
    return data


def to_float(val):
    try:
        if val in (None, "", "None", "N/A", "-"):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None


def fmt_num(val, suffix=""):
    if val is None:
        return "N/D"
    if abs(val) >= 1e9:
        return f"{val / 1e9:.2f}B{suffix}"
    if abs(val) >= 1e6:
        return f"{val / 1e6:.2f}M{suffix}"
    return f"{val:.2f}{suffix}"


def obtener_analisis_ticker(ticker: str, focus: str) -> dict:
    overview = av_get({"function": "OVERVIEW", "symbol": ticker})
    time.sleep(1.2)
    cashflow = av_get({"function": "CASH_FLOW", "symbol": ticker})

    nombre = overview.get("Name") or ticker
    sector = overview.get("Sector") or "N/D"
    pe = to_float(overview.get("PERatio"))
    profit_margin = to_float(overview.get("ProfitMargin"))
    op_margin = to_float(overview.get("OperatingMarginTTM"))
    rev_growth = to_float(overview.get("QuarterlyRevenueGrowthYOY"))
    earn_growth = to_float(overview.get("QuarterlyEarningsGrowthYOY"))
    ev_ebitda = to_float(overview.get("EVToEBITDA"))
    debt_equity = None  # No siempre viene directo en OVERVIEW; se reporta N/D si falta

    # Flujo de caja operativo y libre del último reporte anual disponible
    ocf = None
    fcf = None
    reports = cashflow.get("annualReports") or []
    if reports:
        latest = reports[0]
        ocf = to_float(latest.get("operatingCashflow"))
        capex = to_float(latest.get("capitalExpenditures"))
        if ocf is not None and capex is not None:
            fcf = ocf - abs(capex)

    riesgos = []
    if focus == "growth":
        if rev_growth is not None and rev_growth < 0.05:
            riesgos.append(f"Crecimiento interanual de ingresos bajo ({rev_growth * 100:.1f}%).")
        elif rev_growth is None:
            riesgos.append("Crecimiento trimestral de ingresos no disponible en OVERVIEW.")
        if op_margin is not None and op_margin < 0.10:
            riesgos.append(f"Margen operativo ajustado ({op_margin * 100:.1f}%).")
        if fcf is not None and fcf < 0:
            riesgos.append(f"Flujo de caja libre negativo ({fmt_num(fcf)}).")
        if pe is not None and pe > 35:
            riesgos.append(f"Múltiplo P/E exigente ({pe:.1f}x) frente a riesgos de ejecución.")
    else:
        if fcf is not None and fcf < 0:
            riesgos.append(f"Consumo de caja libre en último reporte anual ({fmt_num(fcf)}).")
        if ocf is None:
            riesgos.append("Flujo de caja operativo no disponible en CASH_FLOW.")
        if profit_margin is not None and profit_margin < 0.08:
            riesgos.append(f"Margen neto estrecho ({profit_margin * 100:.1f}%) ante presiones de costos.")
        if ev_ebitda is not None and ev_ebitda > 18:
            riesgos.append(f"Valoración EV/EBITDA elevada ({ev_ebitda:.1f}x).")

    if not riesgos:
        riesgos.append("Sin alertas críticas automáticas en los campos revisados; verificar deuda y vencimientos.")

    return {
        "ticker": ticker,
        "nombre": nombre,
        "sector": sector,
        "rev_growth": f"{rev_growth * 100:.1f}%" if rev_growth is not None else "N/D",
        "earn_growth": f"{earn_growth * 100:.1f}%" if earn_growth is not None else "N/D",
        "op_margin": f"{op_margin * 100:.1f}%" if op_margin is not None else "N/D",
        "profit_margin": f"{profit_margin * 100:.1f}%" if profit_margin is not None else "N/D",
        "ocf": fmt_num(ocf),
        "fcf": fmt_num(fcf),
        "pe": f"{pe:.1f}x" if pe is not None else "N/D",
        "ev_ebitda": f"{ev_ebitda:.1f}x" if ev_ebitda is not None else "N/D",
        "riesgos": riesgos,
    }


def limpiar_texto_pdf(texto: str) -> str:
    return texto.encode("latin-1", "replace").decode("latin-1")


def construir_resumen_texto(resultados: list, focus: str, fecha_str: str) -> str:
    enfoque_label = "Crecimiento (Growth)" if focus == "growth" else "Solidez y Deuda"
    lineas = [
        f"INFORME FUNDAMENTAL ({enfoque_label}) - {fecha_str}",
        "Prioridad: Fundamentos y riesgos reales (sin depender de sentimiento de noticias).",
        ""
    ]
    for r in resultados:
        lineas.append(f"*{r['ticker']}* - {r['nombre']} ({r['sector']})")
        lineas.append(
            f"Crec. Ingresos YoY: {r['rev_growth']} | Marg. Op: {r['op_margin']} | "
            f"OCF: {r['ocf']} | FCF: {r['fcf']} | P/E: {r['pe']}"
        )
        for rs in r["riesgos"]:
            lineas.append(f"- Riesgo: {rs}")
        lineas.append("")
    lineas.append("Se adjunta el informe en PDF.")
    return "\n".join(lineas)


def generar_pdf(resultados: list, focus: str, fecha_str: str, ruta_pdf: str):
    enfoque_label = "Crecimiento (Growth)" if focus == "growth" else "Solidez y Deuda"
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 10, limpiar_texto_pdf(f"Informe Fundamental - {enfoque_label}"), ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, limpiar_texto_pdf(f"Fecha (UTC): {fecha_str}"), ln=True)
    pdf.cell(0, 6, limpiar_texto_pdf("Criterio: Fundamentos y riesgos reales por encima de sentimiento."), ln=True)
    pdf.ln(4)

    for r in resultados:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, limpiar_texto_pdf(f"{r['ticker']} - {r['nombre']} ({r['sector']})"), ln=True)

        pdf.set_font("Helvetica", "", 10)
        metrics_line = (
            f"Crec. Ingresos YoY: {r['rev_growth']} | Crec. Utilidad YoY: {r['earn_growth']} | "
            f"Margen Op: {r['op_margin']} | Margen Neto: {r['profit_margin']}"
        )
        val_line = (
            f"Flujo Caja Op (OCF): {r['ocf']} | Flujo Caja Libre (FCF): {r['fcf']} | "
            f"P/E: {r['pe']} | EV/EBITDA: {r['ev_ebitda']}"
        )
        pdf.multi_cell(0, 6, limpiar_texto_pdf(metrics_line))
        pdf.multi_cell(0, 6, limpiar_texto_pdf(val_line))

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, limpiar_texto_pdf("Riesgos identificados:"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        for rs in r["riesgos"]:
            pdf.multi_cell(0, 6, limpiar_texto_pdf(f"  * {rs}"))
        pdf.ln(4)

    pdf.output(ruta_pdf)


def enviar_telegram_texto(texto: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto[:4000],
    }
    resp = requests.post(url, json=payload, timeout=20)
    resp.raise_for_status()


def enviar_telegram_pdf(ruta_pdf: str, caption: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    with open(ruta_pdf, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1000]},
            files={"document": (os.path.basename(ruta_pdf), f, "application/pdf")},
            timeout=30,
        )
    resp.raise_for_status()


def main():
    validar_entorno()
    tickers = [t.strip().upper() for t in TICKERS_RAW.split(",") if t.strip()]
    if not tickers:
        tickers = ["AAPL"]

    focus = FOCUS if FOCUS in ("growth", "solidity") else "growth"
    fecha_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ruta_pdf = "informe.pdf"

    resultados = []
    for idx, ticker in enumerate(tickers):
        if idx > 0:
            time.sleep(1.5)
        try:
            resultados.append(obtener_analisis_ticker(ticker, focus))
        except Exception as exc:
            resultados.append({
                "ticker": ticker,
                "nombre": ticker,
                "sector": "N/D",
                "rev_growth": "N/D",
                "earn_growth": "N/D",
                "op_margin": "N/D",
                "profit_margin": "N/D",
                "ocf": "N/D",
                "fcf": "N/D",
                "pe": "N/D",
                "ev_ebitda": "N/D",
                "riesgos": [f"Error al consultar datos: {exc}"],
            })

    resumen = construir_resumen_texto(resultados, focus, fecha_str)
    generar_pdf(resultados, focus, fecha_str, ruta_pdf)

    enviar_telegram_texto(resumen)
    enviar_telegram_pdf(ruta_pdf, f"PDF adjunto - {', '.join(tickers)} ({fecha_str})")
    print("Reporte enviado correctamente a Telegram.")


if __name__ == "__main__":
    main()
