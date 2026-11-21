import os
import math
from datetime import datetime, timezone
import requests
import yfinance as yf
from fpdf import FPDF

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

INDICES = {
    "NASDAQ Composite": "^IXIC",
    "S&P 500": "^GSPC",
}

TECH_UNIVERSE = [
    "NVDA", "IBM", "INTC", "MSFT", "AAPL", "GOOGL", "META", "AMZN",
    "AVGO", "AMD", "ORCL", "CRM", "ADBE", "QCOM", "CSCO", "TXN",
    "MU", "PLTR", "SNOW", "NOW"
]


def safe_float(val):
    try:
        if val is None:
            return None
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return None


def pct_change(current, past):
    c = safe_float(current)
    p = safe_float(past)
    if c is None or p is None or p == 0:
        return None
    return ((c - p) / abs(p)) * 100.0


def fmt_pct(val):
    v = safe_float(val)
    if v is None:
        return "N/D"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"


def fmt_num(val, prefix="$", decimals=2):
    v = safe_float(val)
    if v is None:
        return "N/D"
    return f"{prefix}{v:,.{decimals}f}"


def fmt_big(val):
    v = safe_float(val)
    if v is None:
        return "N/D"
    abs_v = abs(v)
    sign = "-" if v < 0 else ""
    if abs_v >= 1e12:
        return f"{sign}${abs_v / 1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{sign}${abs_v / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{sign}${abs_v / 1e6:.2f}M"
    return f"{sign}${abs_v:,.0f}"


def get_index_snapshot(name, symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="10d", interval="1d")
        closes = hist["Close"].dropna()
        if len(closes) >= 2:
            last_val = float(closes.iloc[-1])
            prev_val = float(closes.iloc[-2])
            chg = pct_change(last_val, prev_val)
            return {
                "name": name,
                "symbol": symbol,
                "value": last_val,
                "chg_1d": chg,
            }
    except Exception:
        pass
    return {"name": name, "symbol": symbol, "value": None, "chg_1d": None}


def get_period_return(closes, trading_days_back):
    if closes is None or len(closes) <= trading_days_back:
        return None
    latest = float(closes.iloc[-1])
    past = float(closes.iloc[-(trading_days_back + 1)])
    return pct_change(latest, past)


def analyze_stock(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="6mo", interval="1d")
        closes = hist["Close"].dropna() if (hist is not None and not hist.empty and "Close" in hist) else None
        if closes is None or len(closes) < 2:
            return None

        info = t.info or {}
        price = float(closes.iloc[-1])

        d_1d = get_period_return(closes, 1)
        d_2d = get_period_return(closes, 2)
        d_3d = get_period_return(closes, 3)
        d_1w = get_period_return(closes, 5)
        d_15d = get_period_return(closes, 11)
        d_1m = get_period_return(closes, 21)
        d_3m = get_period_return(closes, 63)

        rev_growth = safe_float(info.get("revenueGrowth"))
        earn_growth = safe_float(info.get("earningsGrowth"))
        rev_growth_pct = rev_growth * 100.0 if rev_growth is not None else None
        earn_growth_pct = earn_growth * 100.0 if earn_growth is not None else None

        pe_ratio = safe_float(info.get("trailingPE"))
        fwd_pe = safe_float(info.get("forwardPE"))
        debt_to_equity = safe_float(info.get("debtToEquity"))
        profit_margins = safe_float(info.get("profitMargins"))
        profit_margin_pct = profit_margins * 100.0 if profit_margins is not None else None
        free_cash_flow = safe_float(info.get("freeCashflow"))
        market_cap = safe_float(info.get("marketCap"))

        growth_components = [x for x in [earn_growth_pct, rev_growth_pct] if x is not None]
        fin_growth_score = (sum(growth_components) / len(growth_components)) if growth_components else 0.0

        price_components = [x for x in [d_3m, d_1m, d_1w, d_1d] if x is not None]
        price_score = (sum(price_components) / len(price_components)) if price_components else 0.0

        combined_score = (0.55 * fin_growth_score) + (0.45 * price_score)

        horizons = [d_1d, d_2d, d_3d, d_1w, d_15d, d_1m, d_3m]
        valid_horizons = [x for x in horizons if x is not None]
        positive_count = len([x for x in valid_horizons if x > 0])
        positive_ratio = positive_count / max(1, len(valid_horizons))

        if positive_ratio >= 0.75 and (earn_growth_pct is None or earn_growth_pct >= 0):
            projection_label = "Impulso alcista sostenido"
            projection_detail = (
                "Mantiene fuerza en la mayoria de los plazos desde 1D hasta 3 meses. El escenario base favorece "
                "continuidad mientras respete soportes recientes y no pierda ritmo en el cierre."
            )
        elif positive_ratio >= 0.5:
            projection_label = "Avance con pausas / selectivo"
            projection_detail = (
                "Combina tramos positivos con consolidaciones. Conviene vigilar si el crecimiento de ganancias "
                "y el volumen respaldan nuevas subidas o si hay toma de ganancias."
            )
        else:
            projection_label = "Fase de ajuste o cautela"
            projection_detail = (
                "Presenta presion o retrocesos en varios plazos revisados. Es preferible esperar confirmacion "
                "de piso antes de asumir que la subida retomara velocidad."
            )

        fundamental_summary = []
        if earn_growth_pct is not None:
            if earn_growth_pct > 15:
                fundamental_summary.append(f"ganancias creciendo con fuerza ({fmt_pct(earn_growth_pct)})")
            elif earn_growth_pct > 0:
                fundamental_summary.append(f"ganancias en expansion moderada ({fmt_pct(earn_growth_pct)})")
            else:
                fundamental_summary.append(f"ganancias bajo presion ({fmt_pct(earn_growth_pct)})")

        if debt_to_equity is not None:
            if debt_to_equity < 80:
                fundamental_summary.append("endeudamiento contenido")
            elif debt_to_equity < 180:
                fundamental_summary.append("deuda moderada frente al patrimonio")
            else:
                fundamental_summary.append("apalancamiento elevado a vigilar")

        if free_cash_flow is not None and free_cash_flow > 0:
            fundamental_summary.append(f"genera caja libre positiva ({fmt_big(free_cash_flow)})")

        plain_read = "; ".join(fundamental_summary) if fundamental_summary else "datos fundamentales parciales en fuente"

        return {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "price": price,
            "d_1d": d_1d,
            "d_2d": d_2d,
            "d_3d": d_3d,
            "d_1w": d_1w,
            "d_15d": d_15d,
            "d_1m": d_1m,
            "d_3m": d_3m,
            "rev_growth_pct": rev_growth_pct,
            "earn_growth_pct": earn_growth_pct,
            "pe_ratio": pe_ratio,
            "fwd_pe": fwd_pe,
            "debt_to_equity": debt_to_equity,
            "profit_margin_pct": profit_margin_pct,
            "free_cash_flow": free_cash_flow,
            "market_cap": market_cap,
            "combined_score": combined_score,
            "projection_label": projection_label,
            "projection_detail": projection_detail,
            "plain_read": plain_read,
        }
    except Exception:
        return None


def sanitize_pdf_text(text):
    replacements = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "*",
        "…": "...",
        "≥": ">=",
        "≤": "<=",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class FinancialPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 13)
        self.set_x(self.l_margin)
        self.cell(
            0,
            8,
            sanitize_pdf_text("Reporte Tecnologico - Top 10 y Analisis Fundamental"),
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )
        self.set_draw_color(180, 180, 180)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_x(self.l_margin)
        self.cell(0, 8, sanitize_pdf_text(f"Pagina {self.page_no()}/{{nb}}"), align="C")


def pdf_line(pdf, text, h=5, bold=False, size=8.5):
    pdf.set_font("Helvetica", "B" if bold else "", size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, h, sanitize_pdf_text(text))


def build_pdf(filepath, now_str, indices_data, top10):
    pdf = FinancialPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    pdf_line(pdf, f"Fecha de generacion (UTC): {now_str}", h=5, bold=False, size=9)
    pdf.ln(2)

    pdf_line(pdf, "1. Indices de Referencia (NASDAQ y S&P 500)", h=6, bold=True, size=11)
    for idx in indices_data:
        line = f"- {idx['name']} ({idx['symbol']}): {fmt_num(idx['value'], prefix='')} | 1D: {fmt_pct(idx['chg_1d'])}"
        pdf_line(pdf, line, h=5, bold=False, size=9)
    pdf.ln(3)

    pdf_line(pdf, "2. Top 10 Empresas Tecnologicas (Crecimiento + Impulso)", h=6, bold=True, size=11)
    for i, item in enumerate(top10, 1):
        pdf_line(
            pdf,
            f"{i}. {item['name']} ({item['symbol']}) - Precio: {fmt_num(item['price'])} | Score: {item['combined_score']:.2f}",
            h=5,
            bold=True,
            size=9,
        )
        pdf_line(
            pdf,
            f"   Diferencias: 1D {fmt_pct(item['d_1d'])} | 2D {fmt_pct(item['d_2d'])} | 3D {fmt_pct(item['d_3d'])} | "
            f"1Sem {fmt_pct(item['d_1w'])} | 15D {fmt_pct(item['d_15d'])} | 1Mes {fmt_pct(item['d_1m'])} | 3Meses {fmt_pct(item['d_3m'])}",
            h=4.5,
            bold=False,
            size=8.5,
        )
        pdf_line(
            pdf,
            f"   Crecimiento negocio: Ganancias {fmt_pct(item['earn_growth_pct'])} | Ingresos {fmt_pct(item['rev_growth_pct'])}",
            h=4.5,
            bold=False,
            size=8.5,
        )
        pdf_line(pdf, f"   Lectura: {item['plain_read']}", h=4.5, bold=False, size=8.5)
        pdf.ln(1.5)

    pdf.ln(2)
    pdf_line(pdf, "3. Proyeccion y Escenarios", h=6, bold=True, size=11)
    for item in top10:
        pdf_line(
            pdf,
            f"- {item['symbol']} ({item['projection_label']}): {item['projection_detail']}",
            h=4.5,
            bold=False,
            size=8.5,
        )
    pdf.ln(3)

    pdf_line(pdf, "4. Bloque Fundamental Detallado (Al Cierre del Reporte)", h=6, bold=True, size=11)
    for item in top10:
        pdf_line(
            pdf,
            f"- {item['symbol']} | Cap. Mercado: {fmt_big(item['market_cap'])} | "
            f"P/E: {fmt_num(item['pe_ratio'], prefix='', decimals=1)} | "
            f"P/E Futuro: {fmt_num(item['fwd_pe'], prefix='', decimals=1)} | "
            f"Margen Neto: {fmt_pct(item['profit_margin_pct'])} | "
            f"Deuda/Patrimonio: {fmt_num(item['debt_to_equity'], prefix='', decimals=1)} | "
            f"Caja Libre: {fmt_big(item['free_cash_flow'])}",
            h=4.5,
            bold=False,
            size=8.5,
        )

    pdf.output(filepath)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()


def send_telegram_document(filepath, caption=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    with open(filepath, "rb") as f:
        files = {"document": (os.path.basename(filepath), f, "application/pdf")}
        data = {"chat_id": CHAT_ID, "caption": caption[:1020]}
        resp = requests.post(url, data=data, files=files, timeout=60)
        resp.raise_for_status()


def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en variables de entorno.")

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    indices_data = [get_index_snapshot(name, sym) for name, sym in INDICES.items()]

    analyzed = []
    for sym in TECH_UNIVERSE:
        res = analyze_stock(sym)
        if res is not None:
            analyzed.append(res)

    analyzed.sort(key=lambda x: x["combined_score"], reverse=True)
    top10 = analyzed[:10]

    lines = []
    lines.append(f"RADAR TECNOLOGICO - TOP 10 ({now_utc})")
    lines.append("")
    lines.append("INDICES DE REFERENCIA:")
    for idx in indices_data:
        lines.append(f"• {idx['name']}: {fmt_num(idx['value'], prefix='')} ({fmt_pct(idx['chg_1d'])})")
    lines.append("")
    lines.append("TOP 10 EMPRESAS (CRECIMIENTO + IMPULSO):")

    for i, item in enumerate(top10, 1):
        lines.append(
            f"{i}. {item['name']} ({item['symbol']}) — {fmt_num(item['price'])}\n"
            f"   Dif: 1D {fmt_pct(item['d_1d'])} | 2D {fmt_pct(item['d_2d'])} | 3D {fmt_pct(item['d_3d'])} | "
            f"1Sem {fmt_pct(item['d_1w'])} | 15D {fmt_pct(item['d_15d'])} | 1Mes {fmt_pct(item['d_1m'])} | 3Meses {fmt_pct(item['d_3m'])}\n"
            f"   Ganancias: {fmt_pct(item['earn_growth_pct'])} | Ingresos: {fmt_pct(item['rev_growth_pct'])}\n"
            f"   Lectura: {item['plain_read'].capitalize()}."
        )

    lines.append("")
    lines.append("PROYECCION Y ESCENARIOS:")
    for item in top10[:5]:
        lines.append(f"• {item['symbol']} ({item['projection_label']}): {item['projection_detail']}")

    lines.append("")
    lines.append("BLOQUE FUNDAMENTAL (RESUMEN FINAL):")
    for item in top10:
        lines.append(
            f"• {item['symbol']}: Cap {fmt_big(item['market_cap'])} | P/E {fmt_num(item['pe_ratio'], prefix='', decimals=1)} | "
            f"Margen {fmt_pct(item['profit_margin_pct'])} | Deuda/Pat {fmt_num(item['debt_to_equity'], prefix='', decimals=1)} | "
            f"FCF {fmt_big(item['free_cash_flow'])}"
        )

    full_text = "\n".join(lines)

    chunk_size = 3800
    for start in range(0, len(full_text), chunk_size):
        send_telegram_message(full_text[start:start + chunk_size])

    pdf_path = "/tmp/reporte_tecnologico_top10.pdf"
    build_pdf(pdf_path, now_utc, indices_data, top10)
    send_telegram_document(pdf_path, caption="PDF detallado: Top 10 Tecnologicas, comparativas hasta 3 meses y bloque fundamental.")


if __name__ == "__main__":
    main()
