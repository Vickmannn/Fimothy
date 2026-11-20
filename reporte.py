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
    for intento in range(2):
        resp = requests.get(url, params=query, timeout=35)
        resp.raise_for_status()
        data = resp.json()
        aviso = data.get("Note") or data.get("Information")
        if aviso:
            print(f"Aviso API Alpha Vantage ({params.get('function')}): {aviso}")
            if intento == 0:
                time.sleep(12)
                continue
        return data
    return {}


def a_float(valor):
    if valor in (None, "", "None", "N/A", "-", "null"):
        return None
    try:
        return float(str(valor).replace(",", "").strip())
    except ValueError:
        return None


def fmt_monto(val):
    if val is None:
        return "no disponible"
    abs_val = abs(val)
    signo = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000_000:
        return f"{signo}${abs_val / 1_000_000_000_000:.2f} billones"
    if abs_val >= 1_000_000_000:
        return f"{signo}${abs_val / 1_000_000_000:.2f} mil millones"
    if abs_val >= 1_000_000:
        return f"{signo}${abs_val / 1_000_000:.1f} millones"
    return f"{signo}${abs_val:,.0f}"


def fmt_pct(val, dec=1):
    if val is None:
        return "no disponible"
    return f"{val:+.{dec}f}%" if val != 0 else f"0.{'0' * dec}%"


def fmt_ratio(val, dec=2):
    if val is None:
        return "no disponible"
    return f"{val:.{dec}f} veces"


def analizar_ticker(ticker):
    ticker = ticker.strip().upper()
    overview = obtener_json({"function": "OVERVIEW", "symbol": ticker})
    time.sleep(2.0)
    income = obtener_json({"function": "INCOME_STATEMENT", "symbol": ticker})
    time.sleep(2.0)
    balance = obtener_json({"function": "BALANCE_SHEET", "symbol": ticker})
    time.sleep(2.0)
    cashflow = obtener_json({"function": "CASH_FLOW", "symbol": ticker})

    nombre_raw = (overview.get("Name") or "").strip()
    nombre = nombre_raw if nombre_raw and nombre_raw.upper() != ticker else f"Empresa ({ticker})"
    sector_raw = (overview.get("Sector") or "").strip()
    sector = sector_raw if sector_raw and sector_raw.upper() != "N/A" else "Sector no especificado en ficha"
    industria = (overview.get("Industry") or "").strip()

    pe = a_float(overview.get("PERatio"))
    peg = a_float(overview.get("PEGRatio"))
    roe_pct = None
    roe_raw = a_float(overview.get("ReturnOnEquityTTM"))
    if roe_raw is not None:
        roe_pct = roe_raw * 100.0 if abs(roe_raw) <= 1.5 else roe_raw

    margen_op_pct = None
    op_margin_raw = a_float(overview.get("OperatingMarginTTM"))
    if op_margin_raw is not None:
        margen_op_pct = op_margin_raw * 100.0 if abs(op_margin_raw) <= 1.5 else op_margin_raw

    deuda_patrimonio = a_float(overview.get("DebtToEquityRatio"))

    annual_inc = income.get("annualReports") or []
    ingresos_actual = None
    ingresos_anterior = None
    utilidad_neta_actual = None
    utilidad_operativa_actual = None
    crecimiento_ing_pct = None

    if annual_inc:
        rep0 = annual_inc[0]
        ingresos_actual = a_float(rep0.get("totalRevenue"))
        utilidad_neta_actual = a_float(rep0.get("netIncome"))
        utilidad_operativa_actual = a_float(rep0.get("operatingIncome"))
        if margen_op_pct is None and ingresos_actual not in (None, 0) and utilidad_operativa_actual is not None:
            margen_op_pct = (utilidad_operativa_actual / ingresos_actual) * 100.0

    if len(annual_inc) >= 2:
        ingresos_anterior = a_float(annual_inc[1].get("totalRevenue"))
        if ingresos_actual is not None and ingresos_anterior not in (None, 0):
            crecimiento_ing_pct = ((ingresos_actual - ingresos_anterior) / abs(ingresos_anterior)) * 100.0

    annual_bal = balance.get("annualReports") or []
    act_corr = None
    pas_corr = None
    act_totales = None
    pas_totales = None
    patrimonio_total = None
    efectivo = None
    liquidez_corriente = None

    if annual_bal:
        bal0 = annual_bal[0]
        act_corr = a_float(bal0.get("totalCurrentAssets"))
        pas_corr = a_float(bal0.get("totalCurrentLiabilities"))
        act_totales = a_float(bal0.get("totalAssets"))
        pas_totales = a_float(bal0.get("totalLiabilities"))
        patrimonio_total = a_float(bal0.get("totalShareholderEquity"))
        efectivo = a_float(bal0.get("cashAndCashEquivalentsAtCarryingValue")) or a_float(
            bal0.get("cashAndShortTermInvestments")
        )
        if act_corr is not None and pas_corr not in (None, 0):
            liquidez_corriente = act_corr / pas_corr
        if deuda_patrimonio is None and pas_totales is not None and patrimonio_total not in (None, 0):
            deuda_patrimonio = pas_totales / patrimonio_total
        if roe_pct is None and utilidad_neta_actual is not None and patrimonio_total not in (None, 0):
            roe_pct = (utilidad_neta_actual / patrimonio_total) * 100.0

    annual_cf = cashflow.get("annualReports") or []
    flujo_caja_operativo = None
    if annual_cf:
        flujo_caja_operativo = a_float(annual_cf[0].get("operatingCashflow"))

    riesgos = []
    if deuda_patrimonio is not None and deuda_patrimonio > 2.0:
        riesgos.append(
            f"Carga de deuda elevada frente al capital propio ({fmt_ratio(deuda_patrimonio)}): "
            "si suben los costos de financiamiento o baja la caja, presiona el margen."
        )
    if liquidez_corriente is not None and liquidez_corriente < 1.0:
        riesgos.append(
            f"Liquidez de corto plazo ajustada ({fmt_ratio(liquidez_corriente)}): "
            "los compromisos a menos de un año superan los activos líquidos inmediatos."
        )
    elif liquidez_corriente is not None and liquidez_corriente < 1.25:
        riesgos.append(
            f"Colchón de liquidez moderado ({fmt_ratio(liquidez_corriente)}): "
            "conviene vigilar el flujo de caja operativo para cubrir obligaciones corrientes."
        )
    if utilidad_neta_actual is not None and utilidad_neta_actual < 0:
        riesgos.append(
            f"Resultado neto negativo ({fmt_monto(utilidad_neta_actual)}): "
            "la empresa está registrando pérdidas contables en el último ejercicio anual."
        )
    if flujo_caja_operativo is not None and flujo_caja_operativo < 0:
        riesgos.append(
            f"Flujo de caja operativo negativo ({fmt_monto(flujo_caja_operativo)}): "
            "la operación diaria está consumiendo efectivo en lugar de generarlo."
        )
    if crecimiento_ing_pct is not None and crecimiento_ing_pct < 0:
        riesgos.append(
            f"Caída anual en las ventas ({fmt_pct(crecimiento_ing_pct)}): "
            "se observa contracción de ingresos frente al año anterior."
        )
    if pe is not None and pe > 35:
        riesgos.append(
            f"Precio exigente respecto a las ganancias ({pe:.1f} veces utilidades): "
            "el mercado ya descuenta expectativas altas y puede corregir si el ritmo se enfría."
        )
    if not riesgos:
        riesgos.append(
            "No se detectan señales críticas de alerta en los estados financieros consultados, "
            "aunque siempre conviene revisar cambios en márgenes, competencia y regulación."
        )

    if FOCUS == "solidity":
        explicacion_enfoque = (
            f"Enfoque de solidez financiera: la empresa reporta ingresos anuales por {fmt_monto(ingresos_actual)}, "
            f"utilidad neta de {fmt_monto(utilidad_neta_actual)} y efectivo disponible por {fmt_monto(efectivo)}. "
            f"Su liquidez corriente (capacidad de pagar deudas de corto plazo con activos cercanos a efectivo) es de "
            f"{fmt_ratio(liquidez_corriente)}, su relación de deuda frente a patrimonio es de {fmt_ratio(deuda_patrimonio)} "
            f"y su margen operativo (cuánto deja la operación antes de impuestos e intereses) es de {fmt_pct(margen_op_pct)}."
        )
    else:
        explicacion_enfoque = (
            f"Enfoque de crecimiento y generación de valor: las ventas anuales alcanzan {fmt_monto(ingresos_actual)} "
            f"con una variación interanual de {fmt_pct(crecimiento_ing_pct)}. La rentabilidad sobre el capital de los "
            f"accionistas (ROE) se ubica en {fmt_pct(roe_pct)}, el margen operativo en {fmt_pct(margen_op_pct)} "
            f"y el flujo de caja generado por la operación en {fmt_monto(flujo_caja_operativo)}."
        )

    detalle_metricas = [
        f"Ventas anuales (último año): {fmt_monto(ingresos_actual)} | Variación anual: {fmt_pct(crecimiento_ing_pct)}",
        f"Utilidad neta: {fmt_monto(utilidad_neta_actual)} | Margen operativo: {fmt_pct(margen_op_pct)}",
        f"Efectivo y equivalentes: {fmt_monto(efectivo)} | Flujo de caja operativo: {fmt_monto(flujo_caja_operativo)}",
        f"Activos corrientes vs. Pasivos corrientes: {fmt_monto(act_corr)} vs. {fmt_monto(pas_corr)} (Liquidez: {fmt_ratio(liquidez_corriente)})",
        f"Patrimonio total: {fmt_monto(patrimonio_total)} | Deuda/Patrimonio: {fmt_ratio(deuda_patrimonio)} | P/E: {fmt_ratio(pe)} | PEG: {fmt_ratio(peg)}",
    ]

    return {
        "ticker": ticker,
        "nombre": nombre,
        "sector": sector,
        "industria": industria,
        "explicacion_enfoque": explicacion_enfoque,
        "detalle_metricas": detalle_metricas,
        "riesgos": riesgos,
    }


def construir_mensaje_telegram(resultados, enfoque, fecha_str):
    enfoque_titulo = "Solidez Financiera" if enfoque == "solidity" else "Crecimiento del Negocio"
    partes = [
        f"📊 *Informe Fundamental Amplio — {enfoque_titulo}*",
        f"🕒 {fecha_str}",
        "_Análisis basado en estados financieros y riesgos reales, sin depender de rumores o sentimiento._",
        "",
    ]
    for r in resultados:
        encabezado_sec = f"{r['sector']}" + (f" · {r['industria']}" if r["industria"] else "")
        partes.append(f"*{r['ticker']} — {r['nombre']}*")
        partes.append(f"_{encabezado_sec}_")
        partes.append(r["explicacion_enfoque"])
        partes.append("*Indicadores clave:*")
        for linea in r["detalle_metricas"]:
            partes.append(f"• {linea}")
        partes.append("*Riesgos a vigilar:*")
        for riesgo in r["riesgos"]:
            partes.append(f"⚠️ {riesgo}")
        partes.append("")

    texto = "\n".join(partes).strip()
    if len(texto) > 3900:
        texto = texto[:3880] + "\n\n_(El detalle completo va adjunto en el PDF)._"
    return texto


def generar_pdf(resultados, enfoque, fecha_str, ruta_pdf):
    enfoque_titulo = "Solidez Financiera" if enfoque == "solidity" else "Crecimiento del Negocio"
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_x(pdf.l_margin)
    pdf.cell(
        pdf.epw,
        10,
        limpiar_texto_pdf(f"Informe Fundamental - {enfoque_titulo}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", 10)
    pdf.set_x(pdf.l_margin)
    pdf.cell(
        pdf.epw,
        6,
        limpiar_texto_pdf(f"Generado: {fecha_str}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        pdf.epw,
        5.5,
        limpiar_texto_pdf(
            "Enfoque de análisis: Evaluación objetiva de ingresos, rentabilidad, liquidez, "
            "endeudamiento y riesgos operativos por encima del sentimiento del mercado."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    for r in resultados:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_x(pdf.l_margin)
        titulo_emp = f"{r['ticker']} - {r['nombre']}"
        pdf.cell(pdf.epw, 7, limpiar_texto_pdf(titulo_emp), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "I", 9.5)
        pdf.set_x(pdf.l_margin)
        sub_emp = r["sector"] + (f" | {r['industria']}" if r["industria"] else "")
        pdf.cell(pdf.epw, 5.5, limpiar_texto_pdf(sub_emp), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(pdf.l_margin)
        pdf.cell(pdf.epw, 6, limpiar_texto_pdf("Lectura general:"), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(
            pdf.epw,
            5.5,
            limpiar_texto_pdf(r["explicacion_enfoque"]),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(pdf.l_margin)
        pdf.cell(pdf.epw, 6, limpiar_texto_pdf("Detalle de cifras y ratios:"), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9.5)
        for item in r["detalle_metricas"]:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                pdf.epw,
                5.5,
                limpiar_texto_pdf(f"- {item}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_x(pdf.l_margin)
        pdf.cell(pdf.epw, 6, limpiar_texto_pdf("Riesgos identificados:"), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9.5)
        for riesgo in r["riesgos"]:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                pdf.epw,
                5.5,
                limpiar_texto_pdf(f"- {riesgo}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        pdf.ln(5)

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
    enviar_telegram_documento(ruta_pdf, caption=f"Informe PDF ({enfoque}) - {fecha_str}")
    print("Reporte amplio enviado correctamente a Telegram.")


if __name__ == "__main__":
    main()
