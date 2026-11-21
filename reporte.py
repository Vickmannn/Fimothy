import os
import math
from datetime import datetime, timezone
import numpy as np
import requests
import yfinance as yf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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

# Paleta institucional sobria (FIMOTHY | FINANCIAL ENTERPRISE)
NAVY = (17, 29, 54)
SLATE = (71, 85, 105)
GOLD = (186, 142, 56)
DARK_TEXT = (24, 30, 38)
MUTED_TEXT = (100, 110, 124)
BG_LIGHT = (244, 246, 250)
BG_CARD = (250, 251, 253)
BORDER_GRAY = (214, 220, 229)
POS_GREEN = (22, 118, 72)
POS_BG = (232, 246, 238)
NEG_RED = (168, 42, 48)
NEG_BG = (252, 235, 236)
NEU_GRAY = (85, 92, 102)


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
                "continuidad mientras respete soportes recientes y no pierda ritmo al cierre."
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
            "fin_growth_score": fin_growth_score,
            "price_score": price_score,
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


def generate_technical_charts(top10, heatmap_path, matrix_path):
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    plt.rcParams["axes.edgecolor"] = "#CBD5E1"
    plt.rcParams["axes.linewidth"] = 0.8

    # 1. Mapa de calor multitemporal (Top 10 x 7 horizontes)
    horizons_keys = ["d_1d", "d_2d", "d_3d", "d_1w", "d_15d", "d_1m", "d_3m"]
    horizons_labels = ["1D", "2D", "3D", "1Sem", "15D", "1Mes", "3Meses"]
    symbols = [f"{i}. {item['symbol']}" for i, item in enumerate(top10, 1)]

    matrix_vals = []
    for item in top10:
        row = []
        for k in horizons_keys:
            v = safe_float(item.get(k))
            row.append(v if v is not None else np.nan)
        matrix_vals.append(row)
    data = np.array(matrix_vals, dtype=float)

    vmax = np.nanmax(np.abs(data)) if np.any(~np.isnan(data)) else 10.0
    vmax = max(float(vmax), 5.0)
    vmax = min(vmax, 45.0)

    fig, ax = plt.subplots(figsize=(9.5, 4.6), dpi=260)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    im = ax.imshow(data, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto")

    ax.set_xticks(np.arange(len(horizons_labels)))
    ax.set_yticks(np.arange(len(symbols)))
    ax.set_xticklabels(horizons_labels, fontsize=9.5, fontweight="bold", color="#111D36")
    ax.set_yticklabels(symbols, fontsize=9, fontweight="bold", color="#111D36")
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False, length=0)

    # Cuadricula sutil entre celdas
    ax.set_xticks(np.arange(-0.5, len(horizons_labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(symbols), 1), minor=True)
    ax.grid(which="minor", color="#FFFFFF", linestyle="-", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False, top=False)

    for r in range(data.shape[0]):
        for c in range(data.shape[1]):
            val = data[r, c]
            if np.isnan(val):
                txt = "N/D"
                col = "#475569"
            else:
                sign = "+" if val > 0 else ""
                txt = f"{sign}{val:.1f}%"
                col = "#0F172A"
            ax.text(c, r, txt, ha="center", va="center", fontsize=8, fontweight="bold", color=col)

    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.03)
    cbar.ax.tick_params(labelsize=8, colors="#334155")
    cbar.set_label("Variacion (%)", fontsize=8.5, fontweight="bold", color="#111D36")

    ax.set_title(
        "FIMOTHY RESEARCH — Mapa de Calor Multitemporal (Top 10 Tecnologicas)",
        fontsize=11,
        fontweight="bold",
        color="#111D36",
        loc="left",
        pad=22,
    )
    plt.tight_layout()
    plt.savefig(heatmap_path, dpi=260, facecolor="#FFFFFF")
    plt.close(fig)

    # 2. Matriz Crecimiento de Negocio vs. Impulso de Precio
    fig, ax = plt.subplots(figsize=(9.5, 4.5), dpi=260)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    xs = [safe_float(x.get("fin_growth_score")) or 0.0 for x in top10]
    ys = [safe_float(x.get("price_score")) or 0.0 for x in top10]
    scores = [safe_float(x.get("combined_score")) or 0.0 for x in top10]
    sizes = [max(75.0, min(260.0, 90.0 + abs(s) * 2.2)) for s in scores]

    ax.axhline(0, color="#94A3B8", linestyle="--", linewidth=1, zorder=1)
    ax.axvline(0, color="#94A3B8", linestyle="--", linewidth=1, zorder=1)

    sc = ax.scatter(
        xs,
        ys,
        s=sizes,
        c=scores,
        cmap="viridis",
        alpha=0.88,
        edgecolors="#111D36",
        linewidth=1.1,
        zorder=3,
    )

    for idx_i, item in enumerate(top10):
        ax.annotate(
            f"#{idx_i + 1} {item['symbol']}",
            (xs[idx_i], ys[idx_i]),
            xytext=(6, 5),
            textcoords="offset points",
            fontsize=8.5,
            fontweight="bold",
            color="#111D36",
            zorder=4,
        )

    cbar2 = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.03)
    cbar2.ax.tick_params(labelsize=8, colors="#334155")
    cbar2.set_label("Score Combinado", fontsize=8.5, fontweight="bold", color="#111D36")

    ax.set_xlabel("Crecimiento del Negocio Promedio: Ganancias / Ingresos (%)", fontsize=9, fontweight="bold", color="#111D36")
    ax.set_ylabel("Traccion / Impulso de Precio (%)", fontsize=9, fontweight="bold", color="#111D36")
    ax.set_title(
        "FIMOTHY QUANT — Matriz Crecimiento Fundamental vs. Impulso de Mercado",
        fontsize=11,
        fontweight="bold",
        color="#111D36",
        loc="left",
        pad=12,
    )
    ax.grid(True, linestyle=":", color="#CBD5E1", alpha=0.8, zorder=0)

    plt.tight_layout()
    plt.savefig(matrix_path, dpi=260, facecolor="#FFFFFF")
    plt.close(fig)


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


class FimothyPDF(FPDF):
    def header(self):
        banner_h = 24
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, banner_h, style="F")

        self.set_fill_color(*GOLD)
        self.rect(0, banner_h, self.w, 1.8, style="F")

        self.set_xy(self.l_margin, 4.5)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 16.5)
        self.cell(
            self.epw * 0.65,
            7.5,
            sanitize_pdf_text("FIMOTHY"),
            new_x="RIGHT",
            new_y="TOP",
            align="L",
        )

        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(226, 194, 122)
        self.cell(
            self.epw * 0.35,
            7.5,
            sanitize_pdf_text("INSTITUTIONAL TECH BRIEF"),
            new_x="LMARGIN",
            new_y="NEXT",
            align="R",
        )

        self.set_xy(self.l_margin, 13)
        self.set_text_color(214, 222, 235)
        self.set_font("Helvetica", "B", 8.5)
        self.cell(
            self.epw,
            5,
            sanitize_pdf_text("FINANCIAL ENTERPRISE"),
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )

        self.set_text_color(*DARK_TEXT)
        self.set_y(banner_h + 7)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*BORDER_GRAY)
        self.line(self.l_margin, self.get_y() - 1.5, self.w - self.r_margin, self.get_y() - 1.5)
        self.set_text_color(*MUTED_TEXT)
        self.set_font("Helvetica", "I", 7.8)
        self.set_x(self.l_margin)
        self.cell(
            self.epw,
            8,
            sanitize_pdf_text(
                f"FIMOTHY - Financial Enterprise  |  Analisis informativo, no constituye asesoria financiera  |  Pag. {self.page_no()}/{{nb}}"
            ),
            align="C",
        )


def pdf_paragraph(pdf, text, h=5.0, bold=False, size=8.8, color=DARK_TEXT, space_after=1.5):
    pdf.set_text_color(*color)
    pdf.set_font("Helvetica", "B" if bold else "", size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, h, sanitize_pdf_text(text))
    if space_after > 0:
        pdf.ln(space_after)


def pdf_section_title(pdf, title, subtitle=None):
    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    y_top = pdf.get_y()
    box_h = 11.5 if subtitle else 8.0
    if y_top + box_h > pdf.h - pdf.b_margin:
        pdf.add_page()
        y_top = pdf.get_y()

    pdf.set_fill_color(*BG_LIGHT)
    pdf.rect(pdf.l_margin, y_top, pdf.epw, box_h, style="F")
    pdf.set_fill_color(*GOLD)
    pdf.rect(pdf.l_margin, y_top, 2.8, box_h, style="F")

    pdf.set_xy(pdf.l_margin + 5.5, y_top + 1.3)
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(pdf.epw - 6, 5.2, sanitize_pdf_text(title), new_x="LMARGIN", new_y="NEXT", align="L")

    if subtitle:
        pdf.set_x(pdf.l_margin + 5.5)
        pdf.set_text_color(*MUTED_TEXT)
        pdf.set_font("Helvetica", "", 8.0)
        pdf.cell(pdf.epw - 6, 4.2, sanitize_pdf_text(subtitle), new_x="LMARGIN", new_y="NEXT", align="L")

    pdf.set_text_color(*DARK_TEXT)
    pdf.ln(3)


def draw_kpi_cards(pdf, indices_data, top10):
    pdf.set_x(pdf.l_margin)
    y0 = pdf.get_y()
    card_h = 18.0
    gap = 3.0
    card_w = (pdf.epw - gap * 2) / 3.0

    nasdaq = indices_data[0] if len(indices_data) > 0 else {"name": "NASDAQ", "value": None, "chg_1d": None}
    sp500 = indices_data[1] if len(indices_data) > 1 else {"name": "S&P 500", "value": None, "chg_1d": None}
    leader = top10[0] if len(top10) > 0 else {"symbol": "N/D", "price": None, "combined_score": 0.0}

    cards = [
        (
            "NASDAQ COMPOSITE",
            fmt_num(nasdaq.get("value"), prefix="", decimals=2),
            f"Variacion 1D: {fmt_pct(nasdaq.get('chg_1d'))}",
            safe_float(nasdaq.get("chg_1d")),
        ),
        (
            "S&P 500 INDEX",
            fmt_num(sp500.get("value"), prefix="", decimals=2),
            f"Variacion 1D: {fmt_pct(sp500.get('chg_1d'))}",
            safe_float(sp500.get("chg_1d")),
        ),
        (
            "LIDER TOP 10",
            f"{leader.get('symbol')} ({fmt_num(leader.get('price'))})",
            f"Score combinado: {leader.get('combined_score', 0.0):.2f}",
            safe_float(leader.get("combined_score")),
        ),
    ]

    for idx_c, (label, main_val, sub_val, tone_val) in enumerate(cards):
        x0 = pdf.l_margin + idx_c * (card_w + gap)
        pdf.set_fill_color(*BG_CARD)
        pdf.set_draw_color(*BORDER_GRAY)
        pdf.rect(x0, y0, card_w, card_h, style="DF")

        top_bar_col = NAVY if idx_c == 2 else (POS_GREEN if (tone_val is not None and tone_val >= 0) else NEG_RED)
        pdf.set_fill_color(*top_bar_col)
        pdf.rect(x0, y0, card_w, 1.4, style="F")

        pdf.set_xy(x0 + 2.5, y0 + 2.6)
        pdf.set_text_color(*MUTED_TEXT)
        pdf.set_font("Helvetica", "B", 7.2)
        pdf.cell(card_w - 5, 3.8, sanitize_pdf_text(label), align="L")

        pdf.set_xy(x0 + 2.5, y0 + 6.8)
        pdf.set_text_color(*NAVY)
        pdf.set_font("Helvetica", "B", 10.2)
        pdf.cell(card_w - 5, 5.0, sanitize_pdf_text(main_val), align="L")

        pdf.set_xy(x0 + 2.5, y0 + 12.2)
        if tone_val is not None and idx_c < 2:
            pdf.set_text_color(*(POS_GREEN if tone_val >= 0 else NEG_RED))
        else:
            pdf.set_text_color(*SLATE)
        pdf.set_font("Helvetica", "B", 7.8)
        pdf.cell(card_w - 5, 4.0, sanitize_pdf_text(sub_val), align="L")

    pdf.set_y(y0 + card_h + 3)


def draw_stock_card(pdf, rank, item):
    # Reserva espacio aproximado para evitar cabecera huerfana
    needed_h = 28.0
    if pdf.get_y() + needed_h > pdf.h - pdf.b_margin:
        pdf.add_page()

    x0 = pdf.l_margin
    y0 = pdf.get_y()

    # Encabezado de fila de empresa
    pdf.set_fill_color(*BG_LIGHT)
    pdf.set_draw_color(*BORDER_GRAY)
    pdf.rect(x0, y0, pdf.epw, 6.8, style="DF")

    pdf.set_xy(x0 + 2.5, y0 + 1.1)
    pdf.set_text_color(*NAVY)
    pdf.set_font("Helvetica", "B", 9.2)
    title_str = f"#{rank}  {item['name']} ({item['symbol']})  —  Precio: {fmt_num(item['price'])}"
    pdf.cell(pdf.epw * 0.72, 4.6, sanitize_pdf_text(title_str), align="L")

    pdf.set_text_color(*GOLD)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.cell(
        pdf.epw * 0.25,
        4.6,
        sanitize_pdf_text(f"Score: {item['combined_score']:.2f}"),
        align="R",
    )

    pdf.set_y(y0 + 7.6)

    # Tabla de 7 horizontes (1D, 2D, 3D, 1Sem, 15D, 1Mes, 3Meses)
    cols = [
        ("1D", item["d_1d"]),
        ("2D", item["d_2d"]),
        ("3D", item["d_3d"]),
        ("1Sem", item["d_1w"]),
        ("15D", item["d_15d"]),
        ("1Mes", item["d_1m"]),
        ("3Meses", item["d_3m"]),
    ]
    col_w = pdf.epw / len(cols)
    t_y = pdf.get_y()

    for idx_col, (h_label, h_val) in enumerate(cols):
        cx = x0 + idx_col * col_w
        num_v = safe_float(h_val)

        # Cabecera del plazo
        pdf.set_fill_color(235, 239, 245)
        pdf.set_draw_color(*BORDER_GRAY)
        pdf.rect(cx, t_y, col_w, 4.5, style="DF")
        pdf.set_xy(cx, t_y + 0.5)
        pdf.set_text_color(*SLATE)
        pdf.set_font("Helvetica", "B", 7.2)
        pdf.cell(col_w, 3.5, sanitize_pdf_text(h_label), align="C")

        # Valor porcentual con color semantico
        if num_v is not None and num_v > 0:
            pdf.set_fill_color(*POS_BG)
            txt_col = POS_GREEN
        elif num_v is not None and num_v < 0:
            pdf.set_fill_color(*NEG_BG)
            txt_col = NEG_RED
        else:
            pdf.set_fill_color(255, 255, 255)
            txt_col = NEU_GRAY

        pdf.rect(cx, t_y + 4.5, col_w, 5.2, style="DF")
        pdf.set_xy(cx, t_y + 5.1)
        pdf.set_text_color(*txt_col)
        pdf.set_font("Helvetica", "B", 7.6)
        pdf.cell(col_w, 4.0, sanitize_pdf_text(fmt_pct(h_val)), align="C")

    pdf.set_y(t_y + 11.0)

    # Crecimiento de negocio + lectura clara
    growth_line = (
        f"Crecimiento del negocio: Ganancias {fmt_pct(item['earn_growth_pct'])}  |  "
        f"Ingresos {fmt_pct(item['rev_growth_pct'])}"
    )
    pdf_paragraph(pdf, growth_line, h=4.5, bold=True, size=8.0, color=SLATE, space_after=0.8)
    pdf_paragraph(pdf, f"Lectura: {item['plain_read'].capitalize()}.", h=4.6, bold=False, size=8.3, color=DARK_TEXT, space_after=2.5)


def build_pdf(filepath, now_str, indices_data, top10):
    heatmap_path = "/tmp/fimothy_heatmap.png"
    matrix_path = "/tmp/fimothy_matrix.png"
    generate_technical_charts(top10, heatmap_path, matrix_path)

    pdf = FimothyPDF()
    pdf.alias_nb_pages()
    pdf.set_margins(left=14, top=30, right=14)
    pdf.set_auto_page_break(auto=True, margin=17)
    pdf.add_page()

    pdf_paragraph(
        pdf,
        "Radar Tecnologico — Top 10 Empresas (Crecimiento del Negocio + Impulso)",
        h=5.8,
        bold=True,
        size=11.5,
        color=NAVY,
        space_after=0.8,
    )
    pdf_paragraph(
        pdf,
        f"Emision: {now_str}  |  Universo: Tecnologia (incluye NVDA, IBM, INTC y lideres del sector)",
        h=4.5,
        bold=False,
        size=8.0,
        color=MUTED_TEXT,
        space_after=2.5,
    )

    draw_kpi_cards(pdf, indices_data, top10)

    pdf_section_title(
        pdf,
        "1. Ranking Top 10 y Comparativas Multitemporales (1D a 3 Meses)",
        "Ordenado por combinacion de crecimiento financiero (ganancias/ingresos) y traccion de precio.",
    )
    for rank, item in enumerate(top10, 1):
        draw_stock_card(pdf, rank, item)

    # Pagina dedicada a graficos tecnicos
    pdf.add_page()
    pdf_section_title(
        pdf,
        "2. Analisis Grafico Tecnico — Estructura de Impulso y Crecimiento",
        "Visualizacion cuantitativa de los 7 horizontes temporales y del posicionamiento de cada empresa.",
    )

    if os.path.exists(heatmap_path):
        pdf.set_x(pdf.l_margin)
        y_img1 = pdf.get_y()
        pdf.image(heatmap_path, x=pdf.l_margin, y=y_img1, w=pdf.epw)
        pdf.set_y(y_img1 + (pdf.epw * 4.6 / 9.5) + 4)

    if os.path.exists(matrix_path):
        if pdf.get_y() + (pdf.epw * 4.5 / 9.5) > pdf.h - pdf.b_margin:
            pdf.add_page()
        pdf.set_x(pdf.l_margin)
        y_img2 = pdf.get_y()
        pdf.image(matrix_path, x=pdf.l_margin, y=y_img2, w=pdf.epw)
        pdf.set_y(y_img2 + (pdf.epw * 4.5 / 9.5) + 3)

    # Proyeccion y escenarios
    pdf.add_page()
    pdf_section_title(
        pdf,
        "3. Proyeccion y Escenarios Operativos",
        "Lectura condicional segun consistencia de plazos (1D-3Meses) y expansion de beneficios.",
    )
    for item in top10:
        if pdf.get_y() + 14 > pdf.h - pdf.b_margin:
            pdf.add_page()
        pdf_paragraph(
            pdf,
            f"{item['symbol']} ({item['name']}) — {item['projection_label']}",
            h=4.8,
            bold=True,
            size=8.8,
            color=NAVY,
            space_after=0.5,
        )
        pdf_paragraph(
            pdf,
            item["projection_detail"],
            h=4.6,
            bold=False,
            size=8.4,
            color=DARK_TEXT,
            space_after=2.2,
        )

    # Bloque fundamental como resumen final
    pdf_section_title(
        pdf,
        "4. Resumen Final — Bloque Fundamental",
        "Solidez financiera, valoracion, margenes, apalancamiento y generacion de caja libre.",
    )
    for item in top10:
        if pdf.get_y() + 14 > pdf.h - pdf.b_margin:
            pdf.add_page()
        pdf_paragraph(
            pdf,
            f"{item['name']} ({item['symbol']})",
            h=4.8,
            bold=True,
            size=8.8,
            color=NAVY,
            space_after=0.5,
        )
        fund_txt = (
            f"Cap. Mercado: {fmt_big(item['market_cap'])}  |  P/E: {fmt_num(item['pe_ratio'], prefix='', decimals=1)}  |  "
            f"P/E Futuro: {fmt_num(item['fwd_pe'], prefix='', decimals=1)}  |  Margen Neto: {fmt_pct(item['profit_margin_pct'])}  |  "
            f"Deuda/Patrimonio: {fmt_num(item['debt_to_equity'], prefix='', decimals=1)}  |  Caja Libre: {fmt_big(item['free_cash_flow'])}"
        )
        pdf_paragraph(
            pdf,
            fund_txt,
            h=4.6,
            bold=False,
            size=8.3,
            color=SLATE,
            space_after=2.2,
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

    # Mensaje limpio en Telegram: encabezado, fecha, indices y Top 10
    lines = []
    lines.append("FIMOTHY | FINANCIAL ENTERPRISE")
    lines.append("RADAR TECNOLOGICO — TOP 10 (CRECIMIENTO + IMPULSO)")
    lines.append(f"Fecha: {now_utc}")
    lines.append("")
    lines.append("INDICES DE REFERENCIA:")
    for idx in indices_data:
        lines.append(f"• {idx['name']}: {fmt_num(idx['value'], prefix='')} ({fmt_pct(idx['chg_1d'])})")
    lines.append("")
    lines.append("Comparativas completas (1D a 3M), graficos tecnicos, proyeccion y bloque fundamental final en el PDF adjunto.")
    send_telegram_message("\n".join(lines))

    pdf_path = "/tmp/Fimothy_Institutional_Tech_Report.pdf"
    build_pdf(pdf_path, now_utc, indices_data, top10)
    send_telegram_document(
        pdf_path,
        caption="FIMOTHY - Financial Enterprise | Informe Institucional, Graficos Tecnicos y Bloque Fundamental."
    )


if __name__ == "__main__":
    main()
