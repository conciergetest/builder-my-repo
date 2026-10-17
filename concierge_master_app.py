"""Concierge Master — Streamlit + Supabase.

Instalación:
    pip install -r requirements_streamlit.txt
Ejecución:
    streamlit run concierge_master_app.py

Secrets requeridos en .streamlit/secrets.toml:
    SUPABASE_URL = "..."
    SUPABASE_KEY = "..."
    DELETE_PASSWORD = "..."  # opcional, pero recomendado
"""

from __future__ import annotations

import base64
import math
import re
import html
import os
from datetime import datetime, timedelta, date
from datetime import time as time_cls
from io import BytesIO
from urllib.parse import urlencode

import pandas as pd
import streamlit as st
from supabase import Client, create_client

try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
except ImportError:
    st.error(
        "Falta la dependencia `streamlit-aggrid`. Ejecuta: "
        "`pip install streamlit-aggrid`"
    )
    st.stop()


# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Concierge Master",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# Splash Screen
# -----------------------------------------------------------------------------
if "splash_shown" not in st.session_state:
    st.session_state.splash_shown = False

# No mostrar splash si el usuario ya interactuo o viene de regresar a tabla
has_action_params = any(k in st.query_params for k in ["action", "sel_id", "checkout_filtro", "fecha_date"])
if st.query_params.get("skip_splash"):
    st.session_state.splash_shown = True

if not st.session_state.splash_shown and not has_action_params:
    splash_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "splashscreen.png")

    # CSS de la pantalla de bienvenida: todo animado con CSS puro (sin JS ni imagenes externas)
    st.markdown(
        """
        <style>
        header, [data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
        [data-testid="stStatusWidget"] { display: none !important; }
        .stApp, [data-testid="stAppViewContainer"] { background: #000 !important; }
        .main .block-container { padding: 0 !important; max-width: 100% !important; }

        .splash-root {
            position: fixed; inset: 0; width: 100vw; height: 100vh;
            z-index: 9999; overflow: hidden; background: #000;
        }
        .splash-root img.splash-photo {
            display: block; width: 100%; height: 100%; object-fit: cover;
            transform-origin: 50% 44%;
            animation: splashKen 5.4s ease-out both, splashIn 1.2s ease-out both;
        }
        .splash-veil {
            position: absolute; inset: 0; pointer-events: none;
            background:
                radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 36%, rgba(0,0,0,0.58) 100%),
                linear-gradient(to bottom, rgba(0,0,0,0.62) 0%, rgba(0,0,0,0) 24%,
                                rgba(0,0,0,0) 62%, rgba(0,0,0,0.78) 100%);
            animation: splashIn 1.6s ease-out both;
        }
        .splash-sheen {
            position: absolute; top: -30%; left: -45%; width: 40%; height: 160%;
            background: linear-gradient(90deg, rgba(212,175,55,0) 0%, rgba(255,240,190,0.10) 42%,
                        rgba(255,248,214,0.26) 50%, rgba(255,240,190,0.10) 58%, rgba(212,175,55,0) 100%);
            pointer-events: none; filter: blur(0.5px);
            animation: splashSheen 2.4s ease-in-out 0.9s 1 both;
        }
        .splash-loader {
            position: absolute; left: 0; right: 0; bottom: 0; height: 4px;
            background: rgba(255,255,255,0.08);
            box-shadow: 0 0 18px rgba(0,0,0,0.9);
            animation: splashIn 1.2s ease-out 0.5s both;
        }
        .splash-loader-fill {
            position: relative; height: 100%; width: 0%;
            background: linear-gradient(90deg, #8a6f22 0%, #D4AF37 48%, #F7E9AE 78%, #D4AF37 100%);
            box-shadow: 0 0 10px rgba(212,175,55,0.85), 0 0 26px rgba(212,175,55,0.45);
            animation: splashFill 2.6s cubic-bezier(0.22, 0.61, 0.36, 1.0) forwards;
        }
        .splash-loader-fill::after {
            content: ""; position: absolute; right: 0; top: 50%;
            width: 8px; height: 8px; border-radius: 50%;
            transform: translate(50%, -50%);
            background: #FFF8DC;
            box-shadow: 0 0 10px 3px rgba(255,248,220,0.90), 0 0 24px 8px rgba(212,175,55,0.55);
        }
        .splash-loader-glowwrap { position: absolute; inset: 0; overflow: hidden; }
        .splash-loader-glow {
            position: absolute; top: 0; bottom: 0; left: 0; width: 30%;
            background: linear-gradient(90deg, rgba(255,248,214,0) 0%, rgba(255,248,214,0.55) 50%,
                        rgba(255,248,214,0) 100%);
            animation: splashGlow 1.6s ease-in-out 2.0s infinite;
        }
        .splash-out {
            position: absolute; inset: 0; background: #000; opacity: 0; pointer-events: none;
            animation: splashOut 3.4s ease-in forwards;
        }

        @keyframes splashIn     { from { opacity: 0; } to { opacity: 1; } }
        @keyframes splashKen    { from { transform: scale(1.005); } to { transform: scale(1.075); } }
        @keyframes splashSheen  { 0%   { transform: translateX(0) skewX(-16deg); opacity: 0; }
                                  10%  { opacity: 0.9; }
                                  100% { transform: translateX(420%) skewX(-16deg); opacity: 0; } }
        @keyframes splashFill   { from { width: 0%; } to { width: 100%; } }
        @keyframes splashGlow   { 0%   { transform: translateX(-120%); opacity: 0; }
                                  30%  { opacity: 1; }
                                  100% { transform: translateX(430%); opacity: 0; } }
        @keyframes splashOut    { 0%, 76% { opacity: 0; } 100% { opacity: 1; } }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if os.path.exists(splash_path):
        st.markdown(
            '<div class="splash-root">'
            '<img class="splash-photo" src="data:image/png;base64,'
            + base64.b64encode(open(splash_path, "rb").read()).decode("utf-8")
            + '" alt="Concierge Master">'
            '<div class="splash-veil"></div>'
            '<div class="splash-sheen"></div>'
            '<div class="splash-loader">'
            '<div class="splash-loader-fill">'
            '<div class="splash-loader-glowwrap"><div class="splash-loader-glow"></div></div>'
            '</div>'
            '</div>'
            '<div class="splash-out"></div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("No se encontro `splashscreen.png`. Subelo a tu repositorio junto a este archivo.")

    import time
    time.sleep(4)
    st.session_state.splash_shown = True
    st.session_state.splash_fade_in = True
    st.rerun()

# Transicion suave: el tablero entra desde negro (solo en la primera carga)
if st.session_state.pop("splash_fade_in", False):
    st.markdown(
        """
        <style>
        @keyframes appFadeIn { from { opacity: 1; } to { opacity: 0; } }
        .app-fade {
            position: fixed; inset: 0; background: #000; z-index: 9998;
            pointer-events: none; animation: appFadeIn 0.9s ease-out forwards;
        }
        </style>
        <div class="app-fade"></div>
        """,
        unsafe_allow_html=True,
    )

TABLE_NAME = "huespedes"
RECOGNITION_COLUMN = "recognition"
DB_COLUMNS = [
    "id", "eta", "name", "qty", "room", "email", "check_in", "check_out",
    "res_number", "phone", "info", "ird", "hsk", "rate", "trans",
]
DISPLAY_COLUMNS = [
    "eta", "name", "qty", "room", "check_in", "check_out", "nights",
    "res_number", "phone", "email", "info", "ird", "hsk", "rate", "trans",
]
IMPORT_COLUMNS = [column for column in DB_COLUMNS if column != "id"]

CATEGORY_COLORS = {
    "VIP": "#00E5FF",
    "BIRTHDAY": "#FF5252",
    "HONEYMOON": "#FF9800",
    "BABYMOON": "#A78BFA",
    "ANNIVERSARY": "#4ADE80",
    "RELAXURY": "#F472B6",
    "TEAM MEMBER": "#FACC15",
    "LEISURE": "#22D3EE",
}
BOX_FOLDER_URL = "https://app.box.com/folder/416990015860"

# Enlaces operativos proporcionados por el usuario; navegan en la pestaña actual.
QUICK_LINKS = [
    (
        "ACT. CALEND",
        "https://hilton-my.sharepoint.com/shared?listurl=https%3A%2F%2Fhilton%2Dmy%2Esharepoint%2Ecom%2Fpersonal%2Fdaniela%5Frojas%5Fwaldorfastoria%5Fcom%2FDocuments&CT=1761512662870&OR=OWA%2DNT%2DMail&e=5%3A15d1fd28f8234839a764af20385bbe03&sharingv2=true&fromShare=true&at=9&clickParams=eyJYLUFwcE5hbWUiOiJNaWNyb3NvZnQgT3V0bG9vayBXZWIgQXBwIiwiWC1BcHBWZXJzaW9uIjoiMjAyNTEwMTcwMDIuMTYiLCJPUyI6IldpbmRvd3MgMTEifQ%3D%3D&cidOR=Client&id=%2Fpersonal%2Fdaniela%5Frojas%5Fwaldorfastoria%5Fcom%2FDocuments%2FCALENDARIO%20ACTIVIDADES%20A%20Y%20B&FolderCTID=0x012000D256DD7AE71A594B8E3E3E9677541131",
        "#D97706",
    ),
    (
        "ALICE",
        "https://auth.aliceapp.com/login-staff?__hstc=85647430.18528c557a8d4857356bbdc77be22153.1745273864718.1745273864718.1745273864718.1&__hssc=85647430.2.1745273864718&__hsfp=92250610",
        "#6C5CE7",
    ),
    (
        "ARRIVALS",
        "https://hilton-my.sharepoint.com/shared?listurl=https%3A%2F%2Fhilton%2Dmy%2Esharepoint%2Ecom%2Fpersonal%2Fefrem%5Fcatellani%5Fwaldorfastoria%5Fcom%2FDocuments&e=5%3A5760d5a1b59d4b69adb09d888a758bb4&sharingv2=true&fromShare=true&at=9&CT=1782844742090&OR=OWA%2DNT%2DMail&SI=NonSentItems&clickParams=eyJYLUFwcE5hbWUiOiJNaWNyb3NvZnQgT3V0bG9vayBXZWIgQXBwIiwiWC1BcHBWZXJzaW9uIjoiMjAyNjA2MTkwMTAuMTIiLCJPUyI6IldpbmRvd3MgMTEifQ%3D%3D&cidOR=Client&id=%2Fpersonal%2Fefrem%5Fcatellani%5Fwaldorfastoria%5Fcom%2FDocuments%2FARRIVAL%20DAYS%2F2026&FolderCTID=0x0120000A5710A5FF38F342BA540726A6B97804",
        "#0284C7",
    ),
    ("LA CERNIA", "https://lacerniaadventures.com/", "#059669"),
    ("NO LIMIT", "https://www.experiencecollectioncr.com/", "#EA580C"),
    ("OPEN TABLE", "https://guestcenter.opentable.com/login", "#DC2626"),
    (
        "OUTLOOK-FW",
        "https://outlook.office365.com/mail/inbox/id/AAQkAGMyMWEwZDZkLTk2NDQtNDZiMC1hMmE1LWIxYjFmZGJjYjBmOAAQAIbRdEConWFGtPTirYcPWFY%3D",
        "#2563EB",
    ),
    (
        "OUTLOOK-PC",
        "https://outlook.cloud.microsoft/mail/personalconcierge.costarica@waldorfastoria.com/",
        "#0078D4",
    ),
    (
        "OUTLOOK-RES",
        "https://outlook.cloud.microsoft/mail/LIRGU.ConciergeResidencias@waldorfastoria.com/",
        "#7C3AED",
    ),
    ("RELAXURY", "https://relaxury.agilesd.com/", "#DB2777"),
]


# -----------------------------------------------------------------------------
# Estilos
# -----------------------------------------------------------------------------

st.markdown(
    """
<style>
    :root { color-scheme: dark; }
    .stApp { background: #000000; color: #edf8ff; }
    /* AG Grid selected row handled via rowClassRules */
    header[data-testid="stHeader"] { display: none; }
    .block-container { max-width: 100%; padding: .7rem 1.1rem 1.4rem; }
    [data-testid="stVerticalBlock"] { gap: .45rem; }
    [data-testid="stTextInput"] input, [data-testid="stDateInput"] input {
        color: #effaff !important; background: #0d0d0d !important;
        border: 1px solid #222222 !important; border-radius: 8px !important;
    }
    [data-testid="stTextInput"] input:focus, [data-testid="stDateInput"] input:focus {
        border-color: #00e5ff !important; box-shadow: 0 0 0 1px #00e5ff !important;
    }
    div[data-testid="stMetric"] {
        border: 1px solid #1a1a1a; background: #0a0a0a; border-radius: 10px; padding: 10px;
    }
    div[data-testid="stMetric"] label { color: #8ca4ba !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #00e5ff !important; }
    .quick-links { display: grid; grid-template-columns: repeat(9, minmax(88px, 1fr)); gap: 7px; }
    .quick-link, .action-link {
        display: flex; align-items: center; justify-content: center; min-height: 32px;
        padding: 6px 9px; border-radius: 7px; color: white !important; text-decoration: none !important;
        font: 800 11px/1.1 "Segoe UI", sans-serif; letter-spacing: .25px; text-align: center;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,.15), 0 3px 9px rgba(0,0,0,.25);
        transition: transform .12s ease, filter .12s ease;
    }
    .quick-link:hover, .action-link:hover { filter: brightness(1.15); transform: translateY(-1px); }
    .action-links { display: grid; grid-template-columns: repeat(6, minmax(100px, 1fr)); gap: 8px; margin: 10px 0 3px; }
    .action-link { min-height: 36px; font-size: 11px; }
    .page-title { display:flex; justify-content:space-between; gap:18px; align-items:center; margin-bottom:10px; }
    .brand { display:flex; align-items:center; gap:11px; }
    .brand-mark { color:#d4af37; font: 32px Georgia, serif; letter-spacing:5px; padding-right:11px; border-right:1px solid #766129; }
    .brand-name { color:#d4af37; font-size:11px; font-weight:800; letter-spacing:1.7px; }
    .brand-place { color:#6f879a; font-size:9px; letter-spacing:1px; margin-top:2px; }
    .brand-product { color:#00e5ff; font-size:14px; font-weight:800; margin-top:3px; }
    .clock { color:#00e5ff; font-size:16px; font-weight:800; text-align:right; text-shadow:0 0 12px rgba(0,229,255,.45); }
    .clock-date { color:#00e5ff; font-size:14px; font-weight:700; margin-top:4px; }
    .panel { background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px; padding:12px; }
    .panel-title { color:#00e5ff; font-size:11px; font-weight:800; letter-spacing:.7px; text-transform:uppercase; margin-bottom:8px; }
    .total-strip { border:1px solid #00e5ff; color:#dffcff; background:linear-gradient(90deg,#000000,#0a0a0a); border-radius:8px; padding:7px 12px; text-align:center; font-size:12px; }
    .total-strip strong { color:#00e5ff; font-size:17px; margin-left:6px; }
    .summary-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin:8px 0; }
    .summary-card { min-height:57px; background:#080808; border:1px solid #1a1a1a; border-radius:8px; padding:8px 10px; }
    .summary-label { display:flex; align-items:center; justify-content:space-between; color:#71879a; font-size:9px; font-weight:800; letter-spacing:.7px; text-transform:uppercase; }
    .summary-value { margin-top:5px; color:#00e5ff; font-size:20px; line-height:1; font-weight:900; }
    .summary-card.gold .summary-value { color:#d4af37; }
    .summary-card.pink .summary-value { color:#f472b6; }
    .summary-card.purple .summary-value { color:#a78bfa; }
    .summary-grid-3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:8px 0; }
    .total-badge { display:flex; align-items:center; gap:8px; background:#080808; border:1px solid #1a1a1a; border-radius:8px; padding:8px 14px; margin:4px 0 6px; }
    .total-badge .summary-label { font-size:10px; }
    .total-badge .summary-value { margin-top:0; font-size:18px; }
    .category-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:6px; }
    .category-card { min-height:46px; border-radius:7px; padding:9px 11px 7px; }
    .category-card-head { display:flex; justify-content:space-between; gap:5px; color:var(--category-color); font-size:10px; font-weight:900; text-transform:uppercase; letter-spacing:.4px; }
    .category-card-track { height:4px; margin-top:7px; border-radius:3px; background:rgba(0,0,0,.25); overflow:hidden; }
    .category-card-fill { height:100%; border-radius:3px; background:var(--category-color); }
    .st-key-category_chart_panel { background:transparent !important; border:0 !important; padding:0 !important; }
    .st-key-category_chart_panel [data-testid="stVerticalBlock"] { gap:.22rem !important; }
    .category-chart-title { color:#00e5ff; font-size:10px; font-weight:900; letter-spacing:.7px; text-transform:uppercase; margin:0 0 5px 1px; }
    .category-row { display:flex; align-items:center; gap:8px; margin:6px 0; }
    .category-label { color:#b9cad8; font-size:10px; width:92px; text-align:right; white-space:nowrap; }
    .category-track { flex:1; height:13px; background:#111111; border-radius:5px; overflow:hidden; }
    .category-fill { height:100%; border-radius:5px; }
    .category-value { color:#e8f8ff; font-size:11px; font-weight:700; width:22px; }
    @media (max-width: 980px) {
        .summary-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
        .summary-grid-3 { grid-template-columns:repeat(2,minmax(0,1fr)); }
        .category-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
    }
    .selection-banner { margin: 8px 0; padding:8px 11px; background:#001111; border:1px solid #00e5ff; color:#edfaff; border-radius:8px; font-size:12px; }
    .selection-banner b { color:#00e5ff; }
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
        background:#1a1a1a !important; color:#eefaff !important; border:1px solid #333333 !important;
        border-radius:7px !important; font-weight:750 !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
        border-color:#00e5ff !important; color:#00e5ff !important;
    }
    @media (max-width: 980px) {
        .quick-links { grid-template-columns: repeat(3, 1fr); }
        .action-links { grid-template-columns: repeat(2, 1fr); }
        .clock { display:none; }
    }
    /* Borde cyan intenso alrededor de TODOS los popups (st.dialog) */
    div[data-testid="stDialog"] > div:first-child {
        border: 2px solid #00e5ff !important;
        border-radius: 14px !important;
        box-shadow: 0 0 18px rgba(0,229,255,.65), 0 0 40px rgba(0,229,255,.25) !important;
    }
</style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def safe_text(value: object) -> str:
    """Escapa datos de base de datos antes de interpolarlos en HTML."""
    if value is None or pd.isna(value):
        return ""
    return html.escape(str(value))


# -----------------------------------------------------------------------------
# Exportar tablas a Excel / PDF (usado por el Directorio Telefónico, etc.)
# -----------------------------------------------------------------------------

def exportar_excel_bytes(df: pd.DataFrame, headers: dict[str, str] | None = None, sheet_name: str = "Datos") -> bytes:
    """Genera un .xlsx en memoria a partir de un DataFrame.

    `headers` (opcional) mapea nombre_de_columna -> encabezado bonito para
    mostrar en el Excel (ej: {"colaborador": "Colaborador"}).
    """
    export_df = df.copy()
    if headers:
        export_df = export_df.rename(columns=headers)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name=sheet_name)
        worksheet = writer.sheets[sheet_name]
        for idx, column in enumerate(export_df.columns):
            max_len = max(
                [len(str(column))] + [len(str(v)) for v in export_df[column].astype(str).tolist()]
            )
            worksheet.column_dimensions[chr(65 + idx) if idx < 26 else "A"].width = min(max_len + 3, 45)
    return buffer.getvalue()


def exportar_pdf_bytes(df: pd.DataFrame, headers: dict[str, str] | None = None, title: str = "Reporte") -> bytes:
    """Genera un PDF en memoria con una tabla simple a partir de un DataFrame."""
    from fpdf import FPDF

    export_df = df.copy()
    if headers:
        export_df = export_df.rename(columns=headers)
    export_df = export_df.fillna("").astype(str)

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, title, ln=1)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 5, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}  ·  {len(export_df)} registros", ln=1)
    pdf.ln(2)

    columns = list(export_df.columns)
    page_width = pdf.w - 20
    row_height = 6

    def _clip(text: str, width_mm: float, font_size: float) -> str:
        """Recorta `text` con '...' si no entra en `width_mm` al tamaño de fuente actual."""
        pdf.set_font("Helvetica", "", font_size)
        max_w = width_mm - 2
        if pdf.get_string_width(text) <= max_w:
            return text
        clipped = text
        while clipped and pdf.get_string_width(clipped + "...") > max_w:
            clipped = clipped[:-1]
        return (clipped + "...") if clipped else text[:1]

    # Anchos proporcionales al contenido más largo de cada columna (con topes
    # razonables) en vez de dividir el ancho de página en partes iguales —
    # así "Nombre / Puesto" (texto largo) no se encima con la columna vecina.
    raw_widths = []
    for col in columns:
        longest = max([len(str(col))] + [len(v) for v in export_df[col].tolist()] or [1])
        raw_widths.append(min(max(longest, 6), 45))
    total_raw = sum(raw_widths) or 1
    col_widths = [w / total_raw * page_width for w in raw_widths]

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(20, 20, 20)
    pdf.set_text_color(255, 255, 255)
    for col, width_mm in zip(columns, col_widths):
        pdf.cell(width_mm, row_height, _clip(str(col), width_mm, 8), border=1, fill=True)
    pdf.ln(row_height)

    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(0, 0, 0)
    for _, row in export_df.iterrows():
        for col, width_mm in zip(columns, col_widths):
            pdf.cell(width_mm, row_height, _clip(str(row[col]), width_mm, 7.5), border=1)
        pdf.ln(row_height)

    return bytes(pdf.output())


def parse_fecha(value: object) -> datetime | None:
    """Convierte un valor de fecha (texto o fecha real) a datetime.

    CORRECCIÓN: cuando `pd.read_excel()` lee una celda de Excel formateada
    como fecha, entrega un objeto `Timestamp`/`datetime` real, NO un texto.
    Antes, esta función lo convertía directo a string con `str(value)`, lo
    que producía algo como "2026-09-07 00:00:00" (con hora incluida) — un
    texto que no calzaba con NINGÚN patrón de abajo (todos esperan solo
    fecha, sin hora). Eso hacía que `parse_fecha` devolviera `None` y que
    `normalizar_fecha` guardara el texto crudo sin formatear, en vez de
    "September 07, 2026" como el resto de la app.

    La solución: revisar PRIMERO si el valor ya es un objeto de fecha
    (Timestamp de pandas es subclase de datetime, así que un solo chequeo
    cubre ambos) y, de ser así, usarlo directamente sin pasar por texto.
    """
    if value is None or pd.isna(value):
        return None

    # Timestamp de pandas es subclase de datetime.datetime -> este chequeo
    # cubre tanto Timestamps como objetos datetime normales.
    if isinstance(value, datetime):
        return datetime(value.year, value.month, value.day)
    # Objetos `date` "puros" (sin hora), por si aparecen en otra fuente.
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)

    value_str = str(value).strip()
    if not value_str:
        return None

    for pattern in (
        "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%B %d", "%b %d",
        "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%m/%d/%Y %H:%M:%S",
    ):
        try:
            return datetime.strptime(value_str, pattern)
        except ValueError:
            continue

    # Último recurso: dejar que pandas intente inferir el formato
    # (cubre variantes que no anticipamos en la lista de patrones).
    parsed = pd.to_datetime(value_str, errors="coerce")
    if pd.notna(parsed):
        return parsed.to_pydatetime()
    return None


def normalizar_fecha(value: object) -> str:
    date_value = parse_fecha(value)
    if date_value:
        if date_value.year == 1900:
            date_value = date_value.replace(year=datetime.now().year)
        return date_value.strftime("%B %d, %Y")
    return "" if value is None or pd.isna(value) else str(value).strip()


def normalizar_room(value: object) -> str:
    """Limpia el valor de ROOM: quita el ".0" que Excel deja al importar.

    IMPORTANTE: no convierte el valor a número, para no perder habitaciones
    escritas con ceros a la izquierda ("0821") o con letras ("PH-2"). Solo
    elimina el sufijo decimal cuando el valor es un entero tipo "811.0"
    (que es como llega una celda numérica de Excel) -> "811".
    """
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return ""
    if re.fullmatch(r"[+-]?\d+\.0+", text):
        return text.split(".")[0]
    return text


def normalizar_rate(value: object) -> str:
    """Deja RATE siempre con el símbolo $ (y sin el ".0" que agrega Excel).

    Se usa al importar, al guardar y al mostrar la tabla, así el valor queda
    consistente venga con "$" o sin él: "250", "250.0" y "$250" terminan
    todos como "$250". Si el texto no tiene números (por ejemplo "COMP") se
    respeta tal cual. Los dígitos siguen intactos para `evaluar_vip`, que los
    extrae del texto con `_extraer_numeros_rate`.
    """
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return ""
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return text
    numero = match.group(0)
    if re.fullmatch(r"\d[\d,]*\.0+", numero):
        numero = numero.split(".")[0]
    reemplazo = numero if "$" in text else "$" + numero
    return text[: match.start()] + reemplazo + text[match.end():]


def formatear_fecha_corta(value: object) -> str:
    """Formatea una fecha para MOSTRARSE en la tabla como "Sep 14, 2026" en
    vez de "September 14, 2026".

    IMPORTANTE: esto es solo para presentación en el grid. Los valores que
    se guardan en Supabase (via `normalizar_fecha`, `check_in.strftime(...)`,
    etc.) y los que usan los filtros (`apply_filters`, los links de checkout
    por fecha, `fecha_date` en la URL) siguen usando el formato largo
    "%B %d, %Y" sin ningún cambio. Esta función solo interviene al construir
    el DataFrame `visible` que se le pasa a AgGrid.
    """
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    parsed = parse_fecha(text)
    if not parsed:
        return text
    if parsed.year == 1900:
        parsed = parsed.replace(year=datetime.now().year)
    return parsed.strftime("%b %d, %Y")


def es_checkout_pasado(check_out_value: object) -> bool:
    """True si `check_out_value` (fecha guardada, con o sin el icono 🏃 ya
    pegado) ya pasó (es hoy o antes de hoy). Usado tanto para pintar el
    icono 🏃 en la tabla principal como para saber en HUÉSPEDES cuáles
    reservas ya hicieron checkout."""
    if check_out_value is None or pd.isna(check_out_value):
        return False
    val_str = str(check_out_value).strip()
    if not val_str:
        return False
    cleaned = re.sub(r"(\d{4})\s*[^\d]*$", r"\1", val_str).strip()
    dt = parse_fecha(cleaned)
    if not dt:
        return False
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0) <= today


def normalizar_eta(value: object) -> str:
    """Normaliza un valor de ETA a la misma forma que usan las opciones del
    selector de horas ("9:00 AM", "11:00 AM", sin cero a la izquierda).

    Soporta:
    - Texto ya en formato "hh:mm AM/PM" CON o SIN cero a la izquierda
      (ej. "09:00 AM", "9:00 AM", "03:00 PM") — así se puede importar el
      Excel con el formato "11:00 AM", "09:00 AM", "03:00 PM" tal cual lo
      pide el usuario.
    - Texto en formato 24 horas ("09:00", "15:00").
    - Objetos `datetime.time` / `datetime.datetime` / `pandas.Timestamp`,
      por si Excel guardó la celda con formato de hora real en vez de texto.
    - Vacío / "-- Sin hora --" / valores no reconocibles -> se devuelve "".
    """
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%I:%M %p").lstrip("0")
    if isinstance(value, time_cls):
        return value.strftime("%I:%M %p").lstrip("0")

    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "null", "-- sin hora --"):
        return ""

    for pattern in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text.upper(), pattern).strftime("%I:%M %p").lstrip("0")
        except ValueError:
            continue
    # No se pudo reconocer el formato: se deja el texto tal cual llegó en
    # vez de perderlo (mejor que mostrar vacío si el usuario escribió algo
    # que no calza con los patrones de arriba).
    return text


def generate_eta_options() -> list[str]:
    """Genera lista de horas cada 30 min en formato 12h AM/PM."""
    options = ["-- Sin hora --"]
    for hour in range(24):
        for minute in (0, 30):
            t = datetime.strptime(f"{hour}:{minute:02d}", "%H:%M")
            options.append(t.strftime("%I:%M %p").lstrip("0"))
    return options


def parse_eta_index(current: str, options: list[str]) -> int:
    """Devuelve el indice de la opcion que coincida con current, o 0.

    Primero intenta un match exacto de texto; si no calza (por ejemplo,
    datos importados con cero a la izquierda: "09:00 AM" en vez de
    "9:00 AM"), reintenta comparando la hora real en vez del texto.
    """
    if not current or current.strip() in ("", "nan", "none"):
        return 0
    current_clean = current.strip().upper()
    for i, opt in enumerate(options):
        if opt.upper() == current_clean:
            return i
    try:
        parsed_time = datetime.strptime(current_clean, "%I:%M %p").time()
    except ValueError:
        return 0
    for i, opt in enumerate(options):
        try:
            opt_time = datetime.strptime(opt.upper(), "%I:%M %p").time()
        except ValueError:
            continue
        if opt_time == parsed_time:
            return i
    return 0

def calcular_noches(check_in: object, check_out: object) -> int | None:
    """Devuelve checkout - checkin, sin contar una noche negativa."""
    start, end = parse_fecha(check_in), parse_fecha(check_out)
    if not start or not end:
        return None
    current_year = datetime.now().year
    if start.year == 1900:
        start = start.replace(year=current_year)
    if end.year == 1900:
        end = end.replace(year=current_year)
    nights = (end - start).days
    return nights if nights >= 0 else None


def date_from_filter(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(value or "", "%Y-%m-%d")
    except ValueError:
        return None


def url_with(**params: str) -> str:
    """Fusiona parámetros nuevos con los query_params actuales (conserva filtros)."""
    current = {k: v for k, v in st.query_params.items()}
    for key, value in params.items():
        if value in (None, ""):
            current.pop(key, None)
        else:
            current[key] = value
    return "?" + urlencode(current) if current else "?"


def clear_selection() -> None:
    for key in ("selected_reservation", "selected_reservation_id"):
        st.session_state.pop(key, None)


def get_action() -> str:
    return str(st.query_params.get("action", ""))


def set_action(action: str) -> None:
    st.query_params["action"] = action
    st.rerun()


def get_selected_reservation(df: pd.DataFrame) -> dict | None:
    """Recupera la reserva seleccionada desde session_state o query_params."""
    reservation = st.session_state.get("selected_reservation")
    if reservation:
        return reservation
    sel_id = st.query_params.get("sel_id")
    if sel_id:
        candidate = df[df["id"].astype(str) == str(sel_id)]
        if not candidate.empty:
            row = candidate.iloc[0].to_dict()
            st.session_state["selected_reservation"] = row
            st.session_state["selected_reservation_id"] = sel_id
            return row
    return None


def bump_grid_version() -> None:
    """Fuerza que AgGrid se vuelva a montar desde cero en el próximo render.

    CORRECCIÓN (tabla en blanco tras Guardar Cambios): streamlit-aggrid es un
    componente basado en iframe. Cuando reutilizamos el mismo `key` en cada
    `st.rerun()`, el componente NO se destruye/recrea: solo recibe props
    nuevas dentro del mismo iframe/instancia de AG Grid. Justo después de
    editar/borrar/crear una reserva, la fila que estaba seleccionada ya no
    calza con los datos nuevos (no usamos `getRowId`), y el grid queda en un
    estado interno inconsistente que se renderiza en blanco. Solo una
    recarga real de página (como el link "APLICAR FECHA", que navega con
    <a href>) fuerza un iframe nuevo y "arregla" la tabla — por eso el
    workaround manual funcionaba.

    La solución real: cambiar el `key` del AgGrid cada vez que los datos
    cambian, para que Streamlit destruya el iframe viejo y monte uno nuevo,
    sin depender de una recarga de página manual.
    """
    st.session_state["grid_version"] = st.session_state.get("grid_version", 0) + 1


def clear_page() -> None:
    clear_selection()
    st.session_state.bulk_selected_ids = []
    bump_grid_version()
    # Preservar filtros; solo eliminamos parámetros de navegación
    for key in list(st.query_params.keys()):
        if key in ("action", "sel_id"):
            del st.query_params[key]
    st.query_params["skip_splash"] = "1"
    st.rerun()


# -----------------------------------------------------------------------------
# Supabase CRUD
# -----------------------------------------------------------------------------

@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


try:
    supabase = init_supabase()
except KeyError:
    st.error("Configura `SUPABASE_URL` y `SUPABASE_KEY` en los Secrets de Streamlit.")
    st.stop()


@st.cache_data(ttl=30, show_spinner=False)
def cargar_reservaciones() -> pd.DataFrame:
    response = supabase.table(TABLE_NAME).select("*").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=DB_COLUMNS + ["nights", RECOGNITION_COLUMN])

    for column in DB_COLUMNS:
        if column not in df.columns:
            df[column] = "" if column != "qty" else 0
    if RECOGNITION_COLUMN not in df.columns:
        df[RECOGNITION_COLUMN] = False

    df["nights"] = df.apply(
        lambda row: calcular_noches(row.get("check_in"), row.get("check_out")), axis=1
    )
    sort_date = df["check_in"].map(parse_fecha)
    return df.assign(_sort_date=sort_date).sort_values(
        by=["_sort_date", "name"], na_position="last"
    ).drop(columns="_sort_date")


@st.cache_data(ttl=30, show_spinner=False)
def recognition_column_available() -> bool:
    """Detecta si Supabase ya tiene el campo persistente de Recognition."""
    try:
        supabase.table(TABLE_NAME).select(RECOGNITION_COLUMN).limit(1).execute()
        return True
    except Exception:
        return False


def is_recognition_marked(value: object) -> bool:
    """Interpreta valores booleanos de Supabase y valores legados seguros."""
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "sí", "si", "on", "x"}


def recognition_percentage_label(recognized_count: int, total_count: int) -> str:
    """Formatea la proporción a dos decimales, truncada para coincidir con el ejemplo del usuario."""
    if total_count <= 0:
        return "0.00%"
    hundredths = (recognized_count * 10_000) // total_count
    return f"{hundredths // 100}.{hundredths % 100:02d}%"


def insertar_reserva(data: dict) -> None:
    supabase.table(TABLE_NAME).insert(data).execute()
    st.cache_data.clear()
    bump_grid_version()


def actualizar_reserva(reservation_id: object, data: dict) -> None:
    supabase.table(TABLE_NAME).update(data).eq("id", reservation_id).execute()
    st.cache_data.clear()
    bump_grid_version()


def eliminar_reserva(reservation_id: object) -> None:
    supabase.table(TABLE_NAME).delete().eq("id", reservation_id).execute()
    st.cache_data.clear()
    bump_grid_version()


def eliminar_reservas(reservation_ids: list) -> None:
    if reservation_ids:
        supabase.table(TABLE_NAME).delete().in_("id", reservation_ids).execute()
        st.cache_data.clear()
        bump_grid_version()


def insertar_lote(records: list[dict]) -> None:
    if records:
        supabase.table(TABLE_NAME).insert(records).execute()
        st.cache_data.clear()
        bump_grid_version()


# -----------------------------------------------------------------------------
# Reminders (tabla `activity_logs`)
# -----------------------------------------------------------------------------

REMINDERS_TABLE = "activity_logs"


@st.cache_data(ttl=30, show_spinner=False)
def cargar_reminders() -> pd.DataFrame:
    response = supabase.table(REMINDERS_TABLE).select("*").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=["id", "activity", "active_date", "due_date", "created_at"])
    sort_key = df["active_date"].map(parse_fecha) if "active_date" in df.columns else None
    if sort_key is not None:
        df = df.assign(_sort=sort_key).sort_values(by="_sort", na_position="last").drop(columns="_sort")
    return df.reset_index(drop=True)


def insertar_reminder(activity: str, active_date: date, due_date: date) -> None:
    supabase.table(REMINDERS_TABLE).insert({
        "activity": activity,
        "active_date": active_date.isoformat(),
        "due_date": due_date.isoformat(),
    }).execute()
    st.cache_data.clear()


def actualizar_reminder(reminder_id: object, activity: str, active_date: date, due_date: date) -> None:
    supabase.table(REMINDERS_TABLE).update({
        "activity": activity,
        "active_date": active_date.isoformat(),
        "due_date": due_date.isoformat(),
    }).eq("id", reminder_id).execute()
    st.cache_data.clear()


def eliminar_reminder(reminder_id: object) -> None:
    supabase.table(REMINDERS_TABLE).delete().eq("id", reminder_id).execute()
    st.cache_data.clear()


def reminders_tiene_contenido() -> bool:
    """True si hay al menos un reminder con actividad (texto) guardado."""
    df = cargar_reminders()
    if df.empty or "activity" not in df.columns:
        return False
    return df["activity"].astype(str).str.strip().ne("").any()


def reminders_contar_activos() -> int:
    """Cuenta cuántos reminders tienen actividad (texto) guardada."""
    df = cargar_reminders()
    if df.empty or "activity" not in df.columns:
        return 0
    return int(df["activity"].astype(str).str.strip().ne("").sum())


def limpiar_reminders_vencidos() -> None:
    """Borra automáticamente los reminders cuyo Due Date ya pasó (antes de hoy)."""
    df = cargar_reminders()
    if df.empty or "due_date" not in df.columns or "id" not in df.columns:
        return
    hoy = datetime.today().date()
    vencidos = []
    for _, row in df.iterrows():
        due = parse_fecha(row.get("due_date"))
        if due is None:
            continue
        due_date_only = due.date() if isinstance(due, datetime) else due
        if due_date_only < hoy:
            vencidos.append(row.get("id"))
    if vencidos:
        supabase.table(REMINDERS_TABLE).delete().in_("id", vencidos).execute()
        st.cache_data.clear()


# -----------------------------------------------------------------------------
# Directorio Telefónico (tabla `directorio_personal`)  -  Supabase CRUD
# -----------------------------------------------------------------------------

DIRECTORIO_TABLE = "directorio_personal"
# Proporciones de las columnas de la tabla del Directorio (colaborador,
# departamento, puesto, correo, extension, telefono). PUESTO y CORREO llevan
# mas ancho porque son los que se cortaban con el popup estrecho.
DIRECTORIO_ROW_RATIOS = [1.5, 1.3, 2.0, 2.1, 0.9, 1.1]
DIRECTORIO_HEADERS = ["COLABORADOR", "DEPARTAMENTO", "PUESTO", "CORREO", "EXT.", "TELÉFONO"]
DIRECTORIO_COLUMNS = [
    "colaborador", "departamento", "nombre_puesto",
    "correo_electronico", "extension", "telefono_contacto",
]
# Encabezados tal cual vienen en "Directorio Telefonico.xlsx", para poder
# importar el Excel original directamente sin tener que renombrar columnas.
DIRECTORIO_EXCEL_HEADERS = {
    "Colaborador": "colaborador",
    "Departamento": "departamento",
    "Nombre / Puesto": "nombre_puesto",
    "Correo Electrónico": "correo_electronico",
    "Extensión": "extension",
    "Teléfono de Contacto": "telefono_contacto",
}


@st.cache_data(ttl=30, show_spinner=False)
def cargar_directorio() -> pd.DataFrame:
    response = supabase.table(DIRECTORIO_TABLE).select("*").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=["id"] + DIRECTORIO_COLUMNS)
    for column in DIRECTORIO_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df.sort_values(
        by=["departamento", "colaborador"], na_position="last", key=lambda s: s.fillna("").astype(str).str.lower()
    ).reset_index(drop=True)


def insertar_colaborador(data: dict) -> None:
    supabase.table(DIRECTORIO_TABLE).insert(data).execute()
    st.cache_data.clear()


def actualizar_colaborador(colaborador_id: object, data: dict) -> None:
    supabase.table(DIRECTORIO_TABLE).update(data).eq("id", colaborador_id).execute()
    st.cache_data.clear()


def eliminar_colaborador(colaborador_id: object) -> None:
    supabase.table(DIRECTORIO_TABLE).delete().eq("id", colaborador_id).execute()
    st.cache_data.clear()


def insertar_colaboradores_lote(records: list[dict]) -> None:
    if records:
        supabase.table(DIRECTORIO_TABLE).insert(records).execute()
        st.cache_data.clear()


# -----------------------------------------------------------------------------
# Huéspedes / Contactos extra (tabla `guests`)  -  Supabase CRUD
#
# Columnas en Supabase: id (uuid), nombre (text), telefono (text),
# detalles (text), created_at (timestamptz, autogenerado).
# -----------------------------------------------------------------------------

GUESTS_TABLE = "guests"
GUESTS_COLUMNS = ["nombre", "telefono", "detalles"]


@st.cache_data(ttl=30, show_spinner=False)
def cargar_guests() -> pd.DataFrame:
    response = supabase.table(GUESTS_TABLE).select("*").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=["id"] + GUESTS_COLUMNS + ["created_at"])
    for column in GUESTS_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df


def buscar_guest_por_nombre(nombre: str, guests_df: pd.DataFrame | None = None) -> dict | None:
    """Busca en `guests` (por nombre, sin distinguir mayúsculas/espacios) el
    contacto extra guardado para un huésped de la tabla principal."""
    if guests_df is None:
        guests_df = cargar_guests()
    if guests_df.empty or not nombre:
        return None
    text = nombre.strip().lower()
    matches = guests_df[guests_df["nombre"].astype(str).str.strip().str.lower() == text]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


def insertar_guest(data: dict) -> None:
    supabase.table(GUESTS_TABLE).insert(data).execute()
    st.cache_data.clear()


def actualizar_guest(guest_id: object, data: dict) -> None:
    supabase.table(GUESTS_TABLE).update(data).eq("id", guest_id).execute()
    st.cache_data.clear()


def eliminar_guest(guest_id: object) -> None:
    supabase.table(GUESTS_TABLE).delete().eq("id", guest_id).execute()
    st.cache_data.clear()


def limpiar_guests_checkout() -> None:
    """Borra automáticamente de `guests` los contactos de huéspedes cuyas
    reservas YA hicieron checkout (o que ya no existen en la tabla
    principal), para que en HUÉSPEDES solo queden los datos de reservas que
    todavía no han hecho checkout. Se corre cada vez que se abre el popup
    de Huéspedes."""
    guests_df = cargar_guests()
    if guests_df.empty:
        return

    reservas_df = cargar_reservaciones()
    activos = set()
    if not reservas_df.empty:
        for _, row in reservas_df.iterrows():
            if es_checkout_pasado(row.get("check_out")):
                continue
            nombre = str(row.get("name", "")).strip().lower()
            if nombre:
                activos.add(nombre)

    to_delete = [
        row["id"] for _, row in guests_df.iterrows()
        if str(row.get("nombre", "")).strip().lower() not in activos
    ]
    if to_delete:
        supabase.table(GUESTS_TABLE).delete().in_("id", to_delete).execute()
        st.cache_data.clear()


# -----------------------------------------------------------------------------
# Pending  -  Supabase CRUD
# Columnas en Supabase: id (int8, autogenerado), numero_orden (int,
# 1 a 15), contenido (text), actualizado_at (timestamptz).
# -----------------------------------------------------------------------------

PENDING_TABLE = "block_notas"
PENDING_LINES = 15


@st.cache_data(ttl=15, show_spinner=False)
def cargar_pending() -> dict:
    """Devuelve {numero_orden: {"id": ..., "contenido": ...}} con lo que
    haya guardado en `block_notas`."""
    response = supabase.table(PENDING_TABLE).select("*").execute()
    data = {}
    for row in response.data or []:
        try:
            numero = int(row.get("numero_orden"))
        except (TypeError, ValueError):
            continue
        data[numero] = {"id": row.get("id"), "contenido": row.get("contenido", "") or ""}
    return data


def guardar_pending_linea(numero: int, texto: str) -> None:
    """Guarda (o borra si queda vacío) el contenido de una línea puntual."""
    texto = (texto or "").strip()
    existentes = cargar_pending()
    existente = existentes.get(numero)

    if not texto:
        if existente:
            eliminar_pending_linea(numero)
        return

    payload = {"numero_orden": numero, "contenido": texto, "actualizado_at": datetime.utcnow().isoformat()}
    if existente:
        supabase.table(PENDING_TABLE).update(payload).eq("id", existente["id"]).execute()
    else:
        supabase.table(PENDING_TABLE).insert(payload).execute()
    st.cache_data.clear()


def eliminar_pending_linea(numero: int) -> None:
    """Borra de la base de datos la línea `numero` (queda vacía)."""
    existentes = cargar_pending()
    existente = existentes.get(numero)
    if existente and existente.get("id") is not None:
        supabase.table(PENDING_TABLE).delete().eq("id", existente["id"]).execute()
    else:
        # Respaldo: por si no se encontró por id, intenta por numero_orden.
        supabase.table(PENDING_TABLE).delete().eq("numero_orden", numero).execute()
    st.cache_data.clear()


def eliminar_pending_todo() -> None:
    """Borra de la base de datos las 15 líneas."""
    existentes = cargar_pending()
    ids = [v["id"] for v in existentes.values() if v.get("id") is not None]
    if ids:
        supabase.table(PENDING_TABLE).delete().in_("id", ids).execute()
    st.cache_data.clear()


def pending_tiene_contenido() -> bool:
    """True si alguna de las 15 líneas del Pending tiene texto."""
    data = cargar_pending()
    return any((v.get("contenido") or "").strip() for v in data.values())


def pending_contar_lineas() -> int:
    """Cuenta cuántas de las 15 líneas del Pending tienen texto."""
    data = cargar_pending()
    return sum(1 for v in data.values() if (v.get("contenido") or "").strip())


# -----------------------------------------------------------------------------
# Bonus / Aguinaldo  -  Supabase CRUD
# -----------------------------------------------------------------------------

BONUS_TABLE = "bonus_registro"


def cargar_bonus(year: int) -> dict[int, list[str]]:
    """Carga los datos de bonus para un año desde Supabase."""
    try:
        response = supabase.table(BONUS_TABLE).select("data").eq("year", year).execute()
        if response.data:
            raw = response.data[0]["data"]
            return {int(k): v for k, v in raw.items()}
    except Exception:
        pass
    return {m: ["", ""] for m in range(12)}


def guardar_bonus(year: int, data: dict[int, list[str]]) -> None:
    """Guarda o actualiza los datos de bonus para un año en Supabase."""
    try:
        # Verificar si ya existe
        existing = supabase.table(BONUS_TABLE).select("id").eq("year", year).execute()
        payload = {"year": year, "data": data}
        if existing.data:
            supabase.table(BONUS_TABLE).update({"data": data}).eq("year", year).execute()
        else:
            supabase.table(BONUS_TABLE).insert(payload).execute()
    except Exception as exc:
        st.error(f"No se pudo guardar en Supabase: {exc}")


def borrar_bonus(year: int) -> None:
    """Elimina los datos de bonus para un año."""
    try:
        supabase.table(BONUS_TABLE).delete().eq("year", year).execute()
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Exportaciones
# -----------------------------------------------------------------------------

def exportar_excel_categorias_safe(df: pd.DataFrame) -> BytesIO:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    export_columns = [
        ("eta", "ETA"), ("name", "NAME"), ("qty", "QTY"),
        ("room", "ROOM"), ("email", "EMAIL"), ("check_in", "CHECK IN"),
        ("check_out", "CHECK OUT"), ("nights", "NIGHTS"),
        ("res_number", "RESERVATION"), ("phone", "PHONE"), ("info", "INFORMATION"),
        ("ird", "IRD"), ("hsk", "HSK"), ("rate", "RATE"), ("trans", "TRANSPORTATION"),
    ]

    # DEFENSA: garantizar que TODAS las columnas que usa la exportación existan.
    # Si falta alguna (p. ej. "info" renombrada/borrada en Supabase o caché viejo),
    # se crea vacía en lugar de lanzar KeyError.
    df = df.copy()
    for key, _ in export_columns:
        if key not in df.columns:
            df[key] = ""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Arrivals"

    # Paleta tomada de la plantilla Excel de referencia:
    # categorías crema, encabezados turquesa y filas de datos gris muy claro.
    fill_section = PatternFill("solid", fgColor="FCD5B4")
    fill_header = PatternFill("solid", fgColor="4BACC6")
    fill_data = PatternFill("solid", fgColor="F4F7F9")
    section_font = Font(name="Calibri", size=10, bold=True, color="000000")
    header_font = Font(name="Calibri", size=10, bold=True, color="000000")
    black_font = Font(name="Calibri", size=10, color="000000")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    border = Border(*(Side(style="thin", color="D6DEE4") for _ in range(4)))

    groups = [
        ("CUMPLEAÑOS", ("BIRTHDAY", "CUMPLE", "BDAY")),
        ("VIP", ("VIP",)),
        ("HONEYMOON", ("HONEYMOON", "LUNA DE MIEL")),
        ("ANNIVERSARY", ("ANNIVERSARY", "ANIVERSARIO")),
        ("BABYMOON", ("BABYMOON",)),
        ("TEAM MEMBER", ("TEAM MEMBER", "STAFF", "EMPLOYEE")),
        ("GENERAL", ()),
    ]

    remaining = df.copy()
    row_number = 1
    for title, keywords in groups:
        if keywords:
            if remaining.empty:
                break
            mask = remaining["info"].fillna("").astype(str).str.upper().apply(
                lambda value: any(keyword in value for keyword in keywords)
            )
            rows = remaining[mask]
            remaining = remaining[~mask]
        else:
            rows = remaining

        if rows.empty:
            continue

        sheet.merge_cells(start_row=row_number, start_column=1, end_row=row_number, end_column=len(export_columns))
        cell = sheet.cell(row=row_number, column=1, value=title)
        cell.fill, cell.font, cell.alignment = fill_section, section_font, center
        sheet.row_dimensions[row_number].height = 24
        row_number += 1

        for column_index, (_, heading) in enumerate(export_columns, 1):
            cell = sheet.cell(row=row_number, column=column_index, value=heading)
            cell.fill, cell.font, cell.alignment, cell.border = fill_header, header_font, center, border
        sheet.row_dimensions[row_number].height = 22
        row_number += 1

        for _, data in rows.iterrows():
            for column_index, (key, _) in enumerate(export_columns, 1):
                value = data.get(key, "")
                if pd.isna(value):
                    value = ""
                cell = sheet.cell(row=row_number, column=column_index, value=value)
                cell.fill, cell.font, cell.alignment, cell.border = fill_data, black_font, left, border
            row_number += 1
        row_number += 1

    widths = [11, 24, 7, 10, 28, 17, 17, 9, 17, 18, 28, 18, 18, 10, 22]
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[chr(64 + index)].width = width
    sheet.freeze_panes = "A3"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output

def exportar_reporte_excel(data: dict[str, pd.DataFrame], report_date: datetime) -> BytesIO:
    from openpyxl.styles import Alignment, Font, PatternFill

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Hoja Resumen
        overview_data = []
        overview_data.append([f"REPORTE DE OCUPACIÓN — {report_date.strftime('%B %d, %Y').upper()}", "", "", ""])
        overview_data.append([])
        overview_data.append(["Métrica", "Reservas", "VIPs", "Habitaciones"])

        for title, frame in data.items():
            vip_count = int(frame["info"].fillna("").astype(str).str.upper().str.contains("VIP").sum())
            rooms_list = frame["room"].dropna().astype(str).replace("", pd.NA).dropna().tolist()
            rooms = ", ".join(rooms_list) if rooms_list else "—"
            overview_data.append([title, len(frame), vip_count, rooms])

        df_overview = pd.DataFrame(overview_data)
        df_overview.to_excel(writer, sheet_name="Resumen", index=False, header=False)

        # Estilizar Resumen
        ws = writer.sheets["Resumen"]
        cyan_fill = PatternFill("solid", fgColor="00B0F0")
        dark_fill = PatternFill("solid", fgColor="123047")
        white_font = Font(color="FFFFFF", bold=True)

        ws.merge_cells("A1:D1")
        ws["A1"].fill = cyan_fill
        ws["A1"].font = Font(color="FFFFFF", bold=True, size=14)
        ws["A1"].alignment = Alignment(horizontal="center")

        for cell in ws[3]:
            cell.fill = dark_fill
            cell.font = white_font

        for col, width in zip(("A", "B", "C", "D"), (30, 12, 12, 55)):
            ws.column_dimensions[col].width = width

        # Hojas individuales
        for title, frame in data.items():
            sheet_name = title[:31]
            visible = frame[[column for column in DISPLAY_COLUMNS if column in frame.columns]].copy()
            visible.to_excel(writer, sheet_name=sheet_name, index=False)

            ws = writer.sheets[sheet_name]
            for cell in ws[1]:
                cell.fill = dark_fill
                cell.font = white_font
            ws.freeze_panes = "A2"

    output.seek(0)
    return output


def show_header() -> None:
    import streamlit.components.v1 as components

    header_left, header_center, header_right = st.columns([1.15, 1.35, 0.85])
    with header_left:
        st.markdown(
            """
<div class="page-title">
  <div class="brand">
    <div class="brand-mark">WA</div>
    <div>
      <div class="brand-name">WALDORF ASTORIA</div>
      <div class="brand-place">COSTA RICA · PUNTA CACIQUE</div>
      <div class="brand-product">Concierge Master <span style="color:#6f879a">v5.1</span></div>
    </div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with header_center:
        # Botones centrales: reemplazan el logo Fred Wayne. Abren popups de
        # "Arrivals By Date" y "Reminders" sobre el dashboard.
        st.markdown(
            """
            <style>
            .st-key-header_center_btns { display:flex; justify-content:center; align-items:center; gap:8px; }
            .st-key-header_arrivals_btn button {
                background: linear-gradient(135deg,#0891B2,#00e5ff) !important;
                color:#001018 !important;
                border:1px solid rgba(0,229,255,.55) !important;
                border-radius:10px !important;
                font: 800 11px/1.15 'Segoe UI', sans-serif !important;
                letter-spacing:0.4px !important;
                text-transform:uppercase !important;
                padding:10px 8px !important;
                white-space:nowrap !important;
                overflow:visible !important;
                box-shadow:0 4px 14px rgba(0,229,255,.25) !important;
                transition: all .12s ease !important;
            }
            .st-key-header_arrivals_btn button:hover {
                filter:brightness(1.12) !important;
                transform:translateY(-1px) !important;
            }
            .st-key-header_reminders_btn button {
                background: linear-gradient(135deg,#D97706,#FACC15) !important;
                color:#1C1300 !important;
                border:1px solid rgba(250,204,21,.55) !important;
                border-radius:10px !important;
                font: 800 11px/1.15 'Segoe UI', sans-serif !important;
                letter-spacing:0.4px !important;
                text-transform:uppercase !important;
                padding:10px 8px !important;
                white-space:nowrap !important;
                overflow:visible !important;
                box-shadow:0 4px 14px rgba(250,204,21,.25) !important;
                transition: all .12s ease !important;
            }
            .st-key-header_reminders_btn button:hover {
                filter:brightness(1.12) !important;
                transform:translateY(-1px) !important;
            }
            .st-key-header_qrcode_btn button {
                background: linear-gradient(135deg,#0EA5E9,#22D3EE) !important;
                color:#04212B !important;
                border:1px solid rgba(34,211,238,.55) !important;
                border-radius:10px !important;
                font: 800 11px/1.15 'Segoe UI', sans-serif !important;
                letter-spacing:0.4px !important;
                text-transform:uppercase !important;
                padding:10px 8px !important;
                white-space:nowrap !important;
                overflow:visible !important;
                box-shadow:0 4px 14px rgba(34,211,238,.25) !important;
                transition: all .12s ease !important;
            }
            .st-key-header_qrcode_btn button:hover {
                filter:brightness(1.12) !important;
                transform:translateY(-1px) !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        if reminders_tiene_contenido():
            st.markdown(
                """
                <style>
                .st-key-header_reminders_btn button {
                    background: linear-gradient(135deg,#B91C1C,#FF1744) !important;
                    color:#ffffff !important;
                    border:1px solid rgba(255,23,68,.7) !important;
                    box-shadow:0 0 14px rgba(255,23,68,.55) !important;
                    animation: reminderPulse 1.6s ease-in-out infinite;
                }
                @keyframes reminderPulse {
                    0%, 100% { box-shadow:0 0 10px rgba(255,23,68,.45); }
                    50% { box-shadow:0 0 20px rgba(255,23,68,.85); }
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
        with st.container(key="header_center_btns"):
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                with st.container(key="header_arrivals_btn"):
                    if st.button(
                        "📅 Arrivals By Date",
                        key="btn_header_arrivals",
                        use_container_width=True,
                    ):
                        st.session_state["open_arrivals"] = True
                        st.rerun()
            with btn_col2:
                with st.container(key="header_reminders_btn"):
                    _reminders_count = reminders_contar_activos()
                    _reminders_label = (
                        f"🔔 Reminders  {_reminders_count}" if _reminders_count > 0 else "🔔 Reminders"
                    )
                    if st.button(
                        _reminders_label,
                        key="btn_header_reminders",
                        use_container_width=True,
                    ):
                        st.session_state["open_reminders"] = True
                        st.rerun()
            with btn_col3:
                with st.container(key="header_qrcode_btn"):
                    if st.button(
                        "🔗 QR Code",
                        key="btn_header_qrcode",
                        use_container_width=True,
                    ):
                        st.session_state["open_qrcode"] = True
                        st.rerun()
    with header_right:
        components.html(
            """
<!doctype html>
<html>
<head>
<style>
  body { margin:0; background:transparent; font-family:Segoe UI,sans-serif; text-align:right; }
  #local-clock { color:#00e5ff; font-size:16px; font-weight:800; line-height:1.2; text-shadow:0 0 12px rgba(0,229,255,.45); }
  #local-date { color:#00e5ff; font-size:14px; font-weight:700; margin-top:5px; text-transform:capitalize; }
</style>
</head>
<body>
  <div id="local-clock">--:--:--</div>
  <div id="local-date">Loading date…</div>
<script>
  const clock = document.getElementById('local-clock');
  const date = document.getElementById('local-date');
  const timeFormatter = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' });
  const dateFormatter = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  function updateLocalClock() {
    const now = new Date();
    clock.textContent = timeFormatter.format(now);
    date.textContent = dateFormatter.format(now);
  }
  updateLocalClock();
  setInterval(updateLocalClock, 1000);
</script>
</body>
</html>
            """,
            height=54,
            scrolling=False,
        )


def render_menu() -> None:
    """Muestra un botón de menú nativo de Streamlit que despliega todas las acciones y enlaces."""

    def _url(action: str) -> str:
        current = {k: v for k, v in st.query_params.items()}
        current["action"] = action
        return "?" + urlencode(current)

    # El popover de Streamlit guarda su estado "abierto/cerrado" ligado a su
    # key/label. Si un botón DE ADENTRO del popover dispara un st.rerun()
    # para abrir otro popup (Directorio, Nueva, etc.), el popover se queda
    # marcado como abierto en el siguiente render y ambos quedan visibles a
    # la vez (lo que causaba la confusión). Truco: cambiarle la key al
    # popover cada vez que se elige una opción del menú, para que en el
    # próximo render sea un widget "nuevo" y arranque cerrado.
    menu_nonce = st.session_state.get("main_menu_nonce", 0)

    def _select_and_rerun(**flags) -> None:
        st.session_state["main_menu_nonce"] = menu_nonce + 1
        for key, value in flags.items():
            st.session_state[key] = value
        st.rerun()

    st.markdown(
        """
        <style>
        div[data-testid="stPopover"] > button {
            background: linear-gradient(135deg, #0a0a0a 0%, #0d0d0d 100%) !important;
            border: 1px solid #1a1a1a !important;
            color: #00e5ff !important;
            font-weight: 800 !important;
            font-size: 13px !important;
            letter-spacing: 1.2px !important;
            text-transform: uppercase !important;
            border-radius: 10px !important;
            box-shadow: 0 4px 14px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.06) !important;
        }
        div[data-testid="stPopover"] > button:hover {
            border-color: #00e5ff !important;
            box-shadow: 0 0 16px rgba(0,229,255,.25) !important;
        }
        div[data-testid="stPopoverBody"] {
            background: #050505 !important;
            border: 1px solid #1a1a1a !important;
            border-radius: 14px !important;
            padding: 18px !important;
            box-shadow: 0 24px 60px rgba(0,0,0,.7) !important;
            min-width: 420px !important;
        }
        div[data-testid="stPopoverBody"] button {
            background: #0a0a0a !important;
            border: 1px solid #1a1a1a !important;
            color: #eafaff !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            font-size: 11px !important;
            transition: all .12s ease !important;
        }
        div[data-testid="stPopoverBody"] button:hover {
            filter: brightness(1.15) !important;
            transform: translateY(-1px) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.popover("☰ MENÚ", use_container_width=True, key=f"main_menu_popover_{menu_nonce}"):
        st.markdown("<div style='color:#d4af37;font-size:14px;font-weight:800;letter-spacing:1.5px;text-align:center;margin-bottom:14px;'>CONCIERGE MASTER</div>", unsafe_allow_html=True)

        # ── Operaciones ──
        st.markdown("<div style='color:#8ca4ba;font-size:10px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px;border-left:3px solid #00e5ff;padding-left:8px;'>Operaciones</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        if c1.button("➕ NUEVA", use_container_width=True):
            # Abre el popup sobre el dashboard en vez de navegar a otra pagina.
            st.query_params["skip_splash"] = "1"
            _select_and_rerun(open_nueva=True)
        if c2.button("⬆ IMPORTAR", use_container_width=True):
            st.query_params["skip_splash"] = "1"
            _select_and_rerun(open_importar=True)
        if c3.button("⬇ EXPORTAR", use_container_width=True):
            st.query_params["skip_splash"] = "1"
            _select_and_rerun(open_exportar=True)
        c4, c5, c6 = st.columns(3)
        if c4.button("📊 REPORTE", use_container_width=True):
            st.query_params["skip_splash"] = "1"
            _select_and_rerun(open_reporte=True)
        if c5.button("📅 AGENDA", use_container_width=True):
            st.query_params["skip_splash"] = "1"
            _select_and_rerun(open_agenda=True)
        if c6.button("💰 BONUS", use_container_width=True):
            st.query_params["action"] = "bonus"
            _select_and_rerun()

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        # ── Herramientas ──
        st.markdown("<div style='color:#8ca4ba;font-size:10px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px;border-left:3px solid #a78bfa;padding-left:8px;'>Herramientas</div>", unsafe_allow_html=True)
        h1, h2, h3, h4 = st.columns(4)
        if h1.button("🧮 CALCULADORA", use_container_width=True):
            st.query_params["action"] = "calculadora"
            _select_and_rerun()
        if h2.button("📆 ALMANAQUE", use_container_width=True):
            st.query_params["action"] = "almanaque"
            _select_and_rerun()
        if h3.button("🏷️ FRED WAYNE", use_container_width=True):
            _select_and_rerun(open_logo=True)
        if h4.button("📇 DIRECTORIO", use_container_width=True):
            st.query_params["skip_splash"] = "1"
            _select_and_rerun(open_directorio=True)
        if st.button("🍽️ P. DINNING", use_container_width=True, key="menu_open_pdinning"):
            st.query_params["skip_splash"] = "1"
            _select_and_rerun(open_pdinning=True)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        # ── Enlaces Rápidos ──
        st.markdown("<div style='color:#8ca4ba;font-size:10px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px;border-left:3px solid #4ade80;padding-left:8px;'>Enlaces Rápidos</div>", unsafe_allow_html=True)

        link_style = 'display:block;text-align:center;padding:8px 4px;border-radius:8px;border:1px solid #1a1a1a;background:#0a0a0a;color:#eafaff;text-decoration:none;font-size:11px;font-weight:700;transition:all .12s;'

        l1, l2, l3 = st.columns(3)
        l1.markdown(f'<a href="{html.escape(QUICK_LINKS[0][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#fbbf24;">ACT. CALEND</a>', unsafe_allow_html=True)
        l2.markdown(f'<a href="{html.escape(QUICK_LINKS[1][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#a5b4fc;">ALICE</a>', unsafe_allow_html=True)
        l3.markdown(f'<a href="{html.escape(QUICK_LINKS[2][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#38bdf8;">ARRIVALS</a>', unsafe_allow_html=True)

        l4, l5, l6 = st.columns(3)
        l4.markdown(f'<a href="{html.escape(QUICK_LINKS[3][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#34d399;">LA CERNIA</a>', unsafe_allow_html=True)
        l5.markdown(f'<a href="{html.escape(QUICK_LINKS[4][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#fb923c;">NO LIMIT</a>', unsafe_allow_html=True)
        l6.markdown(f'<a href="{html.escape(QUICK_LINKS[5][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#f87171;">OPEN TABLE</a>', unsafe_allow_html=True)

        l7, l8, l9 = st.columns(3)
        l7.markdown(f'<a href="{html.escape(QUICK_LINKS[6][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#60a5fa;">OUTLOOK-FW</a>', unsafe_allow_html=True)
        l8.markdown(f'<a href="{html.escape(QUICK_LINKS[7][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#38bdf8;">OUTLOOK-PC</a>', unsafe_allow_html=True)
        l9.markdown(f'<a href="{html.escape(QUICK_LINKS[8][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#c4b5fd;">OUTLOOK-RES</a>', unsafe_allow_html=True)

        l10, l11, l12 = st.columns(3)
        l10.markdown(f'<a href="{html.escape(QUICK_LINKS[9][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#f472b6;">RELAXURY</a>', unsafe_allow_html=True)
        if l11.button("Recognition", use_container_width=True, key="menu_open_recognition"):
            st.query_params["skip_splash"] = "1"
            _select_and_rerun(open_recognition=True)
        l12.link_button("📁 BOX FILES", BOX_FOLDER_URL, use_container_width=True)

        st.markdown("<div style='margin-top:12px;padding-top:10px;border-top:1px solid #1a1a1a;text-align:center;color:#4a5a6a;font-size:10px;'>Haz clic fuera del menú para cerrarlo<br>Waldorf Astoria Costa Rica · Concierge Master v5.1</div>", unsafe_allow_html=True)


def render_app_links() -> None:
    """Muestra los 4 botones de acceso rápido a otras apps en el centro del dashboard."""
    apps = [
        ("🏊 Aquatic Reservations", "https://activities-avhsghtxc4ewcdvhqjejrp.streamlit.app/", "#0891B2"),
        ("📋 Operator's Log", "https://hotel-logbook-zu2ywlashxhykapkbxawfc.streamlit.app/", "#D97706"),
        ("✏️ VT Creator", "https://activity-certificate-waldorf-jwxquxl93r5ntvye4w3ftu.streamlit.app/", "#7C3AED"),
        ("🗄️ VT DataBase", "https://activity-certificates-fimphxc9yzupjuoimxrkc7.streamlit.app/", "#059669"),
    ]
    buttons = "".join(
        f'<a class="app-link" href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer" style="background:{bg}">'
        f'<span>{label}</span></a>'
        for label, url, bg in apps
    )
    st.markdown(
        '<style>'
        '.app-links { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:14px 0 4px; }'
        '.app-link { display:flex; align-items:center; justify-content:center; min-height:44px; padding:10px 12px; '
        'border:1px solid rgba(255,255,255,.08); border-radius:10px; color:#fff !important; text-decoration:none !important; '
        'font:800 12px/1.1 "Segoe UI",sans-serif; letter-spacing:.3px; text-align:center; '
        'box-shadow:0 4px 12px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.08); '
        'transition:all .15s ease; }'
        '.app-link:hover, .app-link:visited, .app-link:active { color:#fff !important; text-decoration:none !important; }'
        '.app-link:hover { filter:brightness(1.15); transform:translateY(-2px); border-color:rgba(255,255,255,.25); }'
        '.app-link span { color:#fff !important; text-decoration:none !important; text-shadow:0 1px 2px rgba(0,0,0,.4); }'
        '@media (max-width:980px){ .app-links { grid-template-columns:repeat(2,1fr); } }'
        '</style>'
        f'<div class="app-links">{buttons}</div>',
        unsafe_allow_html=True,
    )


def apply_filters(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    checkout = str(st.query_params.get("checkout_filtro", ""))
    arrival_day = str(st.query_params.get("fecha_date", ""))
    search = st.session_state.get("global_search", "").strip()
    filters: dict[str, str] = {}
    result = df.copy()

    if checkout:
        result = result[result["check_out"] == checkout]
        filters["checkout"] = checkout
    if arrival_day:
        selected = date_from_filter(arrival_day)
        if selected:
            formatted = selected.strftime("%B %d, %Y")
            result = result[result["check_in"] == formatted]
            filters["arrival"] = formatted
    if search:
        text = search.lower()
        mask = result.astype(str).apply(
            lambda row: row.str.lower().str.contains(text, na=False).any(), axis=1
        )
        result = result[mask]
        filters["search"] = search
    return result, filters


# Categorías del panel "Guest categories" (incluye RELAXURY, que tiene su
# propia barra debajo del grid pero comparte la misma lógica de click).
CATEGORY_CHART_COLORS: dict[str, str] = {
    "VIP": "#00E5FF",
    "BIRTHDAY": "#FF5252",
    "HONEYMOON": "#FF9800",
    "BABYMOON": "#A78BFA",
    "ANNIVERSARY": "#4ADE80",
    "TEAM MEMBER": "#FACC15",
    "LEISURE": "#22D3EE",
    "RELAXURY": "#F472B6",
}

# Categorías especiales que "consumen" una reserva (todas menos LEISURE, que
# es la categoría "sobrante": todo lo que no calzó con ninguna otra).
_SPECIAL_CATEGORIES = ["VIP", "BIRTHDAY", "HONEYMOON", "BABYMOON", "ANNIVERSARY", "RELAXURY", "TEAM MEMBER"]


def category_match_mask(df: pd.DataFrame, category: str) -> pd.Series:
    """Devuelve la máscara booleana de las filas de `df` que pertenecen a
    `category`, con la misma lógica usada para contar en el panel de
    Guest categories — así el popup de detalle siempre calza con el número
    mostrado en la tarjeta."""
    if df.empty:
        return pd.Series([], dtype=bool)

    info = df["info"].fillna("").astype(str).str.upper() if "info" in df.columns else pd.Series([""] * len(df), index=df.index)

    if category == "LEISURE":
        has_special = info.apply(lambda text: any(cat in text for cat in _SPECIAL_CATEGORIES) if pd.notna(text) else False)
        has_special = has_special.fillna(False).astype(bool)
        return ~has_special

    if category == "RELAXURY":
        # RELAXURY puede aparecer en cualquier columna (no solo INFORMATION),
        # igual que el conteo ya usado en el dashboard y la tira inferior.
        return df.astype(str).apply(lambda column: column.str.upper().str.contains("RELAXURY", na=False)).any(axis=1)

    return info.str.contains(category, na=False)


def render_category_chart(df: pd.DataFrame) -> None:
    # Categorías que se muestran en el grid (RELAXURY se excluye de aquí;
    # tiene su propia barra debajo).
    chart_categories = {k: v for k, v in CATEGORY_CHART_COLORS.items() if k != "RELAXURY"}

    with st.container(key="category_chart_panel"):
        st.markdown('<div class="category-chart-title">Guest categories</div>', unsafe_allow_html=True)

        counts: dict[str, int] = {}
        for category in chart_categories:
            counts[category] = int(category_match_mask(df, category).sum())
        max_count = max(counts.values()) if counts and max(counts.values()) > 0 else 1

        items = list(chart_categories.items())
        # La primera fila usa cuatro columnas iguales. En la segunda,
        # LEISURE ocupa el ancho de dos columnas, como en el diseño aprobado.
        row1 = st.columns(4, gap="small")
        row2 = st.columns([1, 1, 2], gap="small")
        slots = list(row1) + list(row2)

        style_rules = []
        for (category, color), col in zip(items, slots):
            slug = re.sub(r"[^A-Z0-9]+", "_", category.upper())
            count = counts[category]
            pct = max(4, min(100, round(count / max_count * 100)))
            with col:
                with st.container(key=f"catcard_{slug}"):
                    st.markdown(
                        f'<div class="category-card" style="--category-color:{color};background:{color}14;border:1px solid {color}40;">'
                        f'<div class="category-card-head"><span>{category}</span><span style="padding-right:22px">{count}</span></div>'
                        f'<div class="category-card-track"><div class="category-card-fill" style="width:{pct}%;"></div></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    clicked = st.button("📊", key=f"do_open_cat_{slug}")
                if clicked:
                    st.session_state["category_detail_name"] = category
                    st.session_state["open_category_detail"] = True
                    st.query_params["skip_splash"] = "1"
                    st.rerun()
            style_rules.append(
                f'.st-key-catcard_{slug} {{ position:relative !important; min-height:54px !important; }}'
                f'.st-key-catcard_{slug} [data-testid="stVerticalBlock"] {{ gap:0 !important; }}'
                f'.st-key-do_open_cat_{slug} {{'
                f' position:absolute !important; top:6px !important; right:9px !important;'
                f' width:20px !important; height:20px !important; z-index:5 !important; margin:0 !important;}}'
                f'.st-key-do_open_cat_{slug} button {{'
                f' width:20px !important; height:20px !important; min-height:20px !important; padding:0 !important;'
                f' background:transparent !important; border:none !important; color:{color} !important;'
                f' font-size:11px !important; line-height:1 !important; box-shadow:none !important;}}'
                f'.st-key-do_open_cat_{slug} button:hover {{'
                f' background:{color}33 !important; border-radius:5px !important;}}'
                f'.st-key-do_open_cat_{slug} [data-testid="stTooltipIcon"] {{ display:none !important; }}'
            )
        st.markdown("<style>" + "".join(style_rules) + "</style>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Vistas secundarias
# -----------------------------------------------------------------------------

def render_back_link() -> None:
    current = {k: v for k, v in st.query_params.items()}
    current.pop("action", None)
    current.pop("sel_id", None)
    current["skip_splash"] = "1"
    back_url = "?" + urlencode(current) if current else "?"
    st.markdown(
        f'<a class="action-link" href="{back_url}" target="_self" style="background:#2a2a2a;max-width:185px">REGRESAR A LA TABLA</a>',
        unsafe_allow_html=True,
    )


def _new_reservation_form(context: str = "page") -> None:
    """Formulario de nueva reserva, reutilizable en pagina o en popup."""
    eta_options = generate_eta_options()
    with st.form(f"new_reservation_{context}", clear_on_submit=True):
        r1 = st.columns(3)
        eta = r1[0].selectbox("ETA", options=eta_options, index=0)
        name = r1[1].text_input("Name *", placeholder="Guest name")
        qty = r1[2].number_input("QTY (adultos,niños)", min_value=0.0, step=0.1, format="%.1f", value=0.0)
        r2 = st.columns(3)
        room = r2[0].text_input("Room", placeholder="101")
        email = r2[1].text_input("Email", placeholder="guest@email.com")
        res_number = r2[2].text_input("Reservation #", placeholder="RES-001")
        r3 = st.columns(3)
        check_in = r3[0].date_input("Check In")
        check_out = r3[1].date_input("Check Out", value=datetime.now().date() + timedelta(days=1))
        phone = r3[2].text_input("Phone", placeholder="+1 555 0000")
        r4 = st.columns(3)
        rate = r4[0].text_input("Rate", placeholder="$250")
        ird = r4[1].text_input("IRD")
        hsk = r4[2].text_input("HSK")
        info = st.text_input("Information", placeholder="VIP, Birthday, Honeymoon, Relaxury...")
        trans = st.text_input("Transportation")
        submitted = st.form_submit_button("Guardar Cambios", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("El nombre del huésped es obligatorio.")
            return
        if check_out < check_in:
            st.error("La fecha de check-out no puede ser anterior al check-in.")
            return
        qty_val = float(qty)
        insertar_reserva({
            "eta": eta if eta != "-- Sin hora --" else "", "name": name.strip(), "qty": qty_val,
            "room": normalizar_room(room), "email": email.strip(), "check_in": check_in.strftime("%B %d, %Y"),
            "check_out": check_out.strftime("%B %d, %Y"), "res_number": res_number.strip(),
            "phone": phone.strip(), "info": info.strip(), "ird": ird.strip(), "hsk": hsk.strip(),
            "rate": normalizar_rate(rate), "trans": trans.strip(),
        })
        st.success("Reservación guardada correctamente.")
        clear_page()


@st.dialog("➕ Nueva Reservación", width="large")
def new_reservation_dialog() -> None:
    """Popup flotante para crear una reserva sin salir del dashboard."""
    _new_reservation_form("dialog")
    if st.button("Cerrar", use_container_width=True, key="close_new_dialog"):
        st.rerun()


def render_new_reservation() -> None:
    """Vista legacy en pagina completa (se conserva por compatibilidad)."""
    st.subheader("Nueva Reservación")
    render_back_link()
    _new_reservation_form("page")


def _edit_reservation_form(reservation: dict, context: str = "page") -> None:
    """Formulario de edicion, reutilizable en pagina o en popup."""
    check_in_default = parse_fecha(reservation.get("check_in")) or datetime.now()
    check_out_default = parse_fecha(reservation.get("check_out")) or datetime.now() + timedelta(days=1)
    qty_default = pd.to_numeric(reservation.get("qty", 0), errors="coerce")
    qty_default = 0.0 if pd.isna(qty_default) else float(qty_default)
    # ETA ahora se edita con el mismo selector de horas (cada 30 min,
    # formato 12h AM/PM) que ya usaba "Nueva Reservación", en vez de un
    # cuadro de texto libre — evita horas mal escritas y hace que calce con
    # lo que se importa desde el Excel.
    eta_options = generate_eta_options()
    eta_index = parse_eta_index(str(reservation.get("eta", "")), eta_options)
    recognition_available = recognition_column_available()
    reservation_id = reservation.get("id", "selected")

    # Estilo del botón VIP Alert (rojo, para que no se confunda con Guardar).
    st.markdown(
        """
        <style>
        [class*="st-key-vip_alert_btn_"] button {
            background:#7f1d1d !important; border:1px solid #f43f5e !important;
            color:#ffffff !important; font-weight:800 !important;
            min-height:44px !important; letter-spacing:0.6px !important;
        }
        [class*="st-key-vip_alert_btn_"] button:hover {
            background:#f43f5e !important; color:#fff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Recognition y VIP Alert van fuera del st.form y uno al lado del otro: un
    # botón dentro de un form sólo puede ser un submit, así que el popup de
    # VIP Alert no podría abrirse desde adentro. El valor del checkbox se
    # sigue leyendo igual al guardar, vía session_state (misma key de antes).
    recognition_key = f"recognition_{context}_{reservation_id}"
    reconocimiento_col, vip_col = st.columns([3, 1])
    with reconocimiento_col:
        recognition = st.checkbox(
            "Recognition",
            value=is_recognition_marked(reservation.get(RECOGNITION_COLUMN, False)),
            key=recognition_key,
            disabled=not recognition_available,
        )
        st.caption("Marca esta casilla para guardar al huésped en tu lista de Recognition.")
        if not recognition_available:
            st.caption(
                "Para guardar esta marca, primero agrega la columna `recognition` "
                "en Supabase usando `supabase/migrations/20261004_add_recognition_to_huespedes.sql`."
            )
    with vip_col:
        if st.button(
            "🚨 VIP Alert",
            use_container_width=True,
            key=f"vip_alert_btn_{context}_{reservation_id}",
            help="Llena los datos del VIP Alert y descarga el Word.",
        ):
            st.session_state["vip_alert_prefill"] = _vip_alert_prefill(reservation)
            st.session_state.pop("vip_alert_doc", None)
            st.session_state["open_vip_alert"] = True
            _app_rerun()

    with st.form(f"edit_reservation_{context}"):
        first = st.columns(4)
        eta = first[0].selectbox("ETA", options=eta_options, index=eta_index)
        name = first[1].text_input("Nombre *", value=str(reservation.get("name", "")))
        qty = first[2].number_input("Huéspedes", min_value=0.0, step=0.1, format="%.1f", value=float(qty_default))
        room = first[3].text_input("Habitación", value=str(reservation.get("room", "")))
        second = st.columns(4)
        email = second[0].text_input("Email", value=str(reservation.get("email", "")))
        check_in = second[1].date_input("Check-in", value=check_in_default.date())
        check_out = second[2].date_input("Check-out", value=check_out_default.date())
        res_number = second[3].text_input("Reservation #", value=str(reservation.get("res_number", "")))
        third = st.columns(4)
        phone = third[0].text_input("Teléfono", value=str(reservation.get("phone", "")))
        info = third[1].text_input("Information", value=str(reservation.get("info", "")))
        ird = third[2].text_input("IRD", value=str(reservation.get("ird", "")))
        hsk = third[3].text_input("HSK", value=str(reservation.get("hsk", "")))
        fourth = st.columns(2)
        rate = fourth[0].text_input("Rate", value=str(reservation.get("rate", "")))
        trans = fourth[1].text_input("Transportation", value=str(reservation.get("trans", "")))
        submitted = st.form_submit_button("GUARDAR CAMBIOS", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("El nombre del huésped es obligatorio.")
            return
        if check_out < check_in:
            st.error("La fecha de check-out no puede ser anterior al check-in.")
            return
        update_data = {
            "eta": eta if eta != "-- Sin hora --" else "", "name": name.strip(), "qty": float(qty), "room": normalizar_room(room),
            "email": email.strip(), "check_in": check_in.strftime("%B %d, %Y"),
            "check_out": check_out.strftime("%B %d, %Y"), "res_number": res_number.strip(),
            "phone": phone.strip(), "info": info.strip(), "ird": ird.strip(), "hsk": hsk.strip(),
            "rate": normalizar_rate(rate), "trans": trans.strip(),
        }
        if recognition_available:
            update_data[RECOGNITION_COLUMN] = bool(recognition)
        actualizar_reserva(reservation["id"], update_data)
        st.success("Reserva actualizada correctamente.")
        clear_page()


@st.dialog("✏️ Editar Reservación", width="large")
def edit_reservation_dialog() -> None:
    """Popup flotante de edicion sobre el dashboard."""
    reservation = get_selected_reservation(cargar_reservaciones())
    if not reservation:
        st.error("Selecciona una reserva de la tabla antes de editar.")
        if st.button("Cerrar", use_container_width=True, key="close_edit_dialog_empty"):
            st.rerun()
        return

    st.markdown(
        '<div style="color:#D4AF37;font:800 12px/1.2 \'Segoe UI\',sans-serif;letter-spacing:1.4px;'
        'text-transform:uppercase;margin-bottom:10px;">'
        f'{safe_text(reservation.get("name", ""))} &nbsp;·&nbsp; Room {safe_text(reservation.get("room", "—"))}</div>',
        unsafe_allow_html=True,
    )
    _edit_reservation_form(reservation, "dialog")
    if st.button("Cerrar", use_container_width=True, key="close_edit_dialog"):
        st.rerun()


def render_edit_reservation() -> None:
    """Vista legacy en pagina completa (se conserva por compatibilidad)."""
    reservation = get_selected_reservation(cargar_reservaciones())
    if not reservation:
        st.error("Selecciona una reserva de la tabla antes de editar.")
        render_back_link()
        return
    st.subheader(f"Editar reservación· {safe_text(reservation.get('name', ''))}")
    render_back_link()
    _edit_reservation_form(reservation, "page")


@st.dialog("Recognition", width="large")
def recognition_dialog() -> None:
    """Muestra las reservas que están marcadas como huéspedes memorables."""
    if not recognition_column_available():
        st.warning(
            "Recognition necesita una columna booleana en la tabla `huespedes` "
            "para guardar las marcas de forma permanente."
        )
        st.code(
            "ALTER TABLE public.huespedes "
            "ADD COLUMN IF NOT EXISTS recognition boolean NOT NULL DEFAULT false;",
            language="sql",
        )
        st.caption(
            "Ejecuta esta instrucción una sola vez en el SQL Editor de Supabase. "
            "Después de aplicarla, verifica el campo aquí."
        )
        if st.button(
            "🔄 Verificar columna",
            use_container_width=True,
            key="retry_recognition_schema",
        ):
            recognition_column_available.clear()
            cargar_reservaciones.clear()
            st.rerun()
    else:
        reservations = cargar_reservaciones()
        total_count = len(reservations)
        if reservations.empty:
            recognized = reservations
        else:
            recognized = reservations[
                reservations[RECOGNITION_COLUMN].map(is_recognition_marked)
            ]

        recognized_count = len(recognized)
        percentage_label = recognition_percentage_label(
            recognized_count, total_count
        )
        count_column, percentage_column, _ = st.columns([1.2, 0.8, 1.2])
        count_column.caption(
            f"{recognized_count} de {total_count} reservaciones marcadas como Recognition."
        )
        percentage_column.markdown(
            f"""
            <div style="display:flex;justify-content:center;margin:0 auto 8px;">
              <div style="box-sizing:border-box;min-width:154px;height:60px;padding:8px 16px;
                          border:4px solid #08bff4;border-radius:12px;background:#10151c;
                          color:#20c8ff;text-align:center;font:800 24px/1.3 'Segoe UI',sans-serif;
                          box-shadow:0 0 14px rgba(0,191,255,.38);">
                {percentage_label}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if reservations.empty:
            st.info("Todavía no hay reservaciones registradas.")
        else:
            if recognized.empty:
                st.info(
                    "Todavía no hay reservas marcadas. Abre una reserva, activa "
                    "Recognition y guarda los cambios."
                )
            else:
                visible_columns = [
                    ("eta", "ETA"),
                    ("name", "NOMBRE"),
                    ("room", "HABITACIÓN"),
                    ("check_in", "CHECK-IN"),
                    ("check_out", "CHECK-OUT"),
                    ("res_number", "RESERVA"),
                    ("phone", "TELÉFONO"),
                    ("email", "EMAIL"),
                    ("info", "INFORMACIÓN"),
                ]
                view = recognized[
                    [key for key, _ in visible_columns if key in recognized.columns]
                ].rename(
                    columns={
                        key: label
                        for key, label in visible_columns
                        if key in recognized.columns
                    }
                )
                st.dataframe(view, use_container_width=True, hide_index=True)

    if st.button("Cerrar", use_container_width=True, key="close_recognition_dialog"):
        st.rerun()


# -----------------------------------------------------------------------------
# VIP ALERT — popup de captura (no guarda en base) + exportación a Word
# -----------------------------------------------------------------------------

VIP_ALERT_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Cada sección del Word: (título de la banda gris, [(clave, etiqueta)]).
VIP_ALERT_SECTIONS = [
    (
        "BASIC INFORMATION",
        [
            ("client_name", "CLIENT NAME"),
            ("location", "LOCATION"),
            ("arrival", "ARRIVAL"),
            ("departure", "DEPARTURE"),
            ("company", "COMPANY"),
            ("media_agency", "MEDIA | AGENCY"),
            ("concierge", "PERSONAL CONCIERGE IN CHARGE"),
            ("transportation", "TRANSPORTATION"),
            ("pax", "PAX. NUMBER"),
            ("allergies", "ALLERGIES"),
            ("special_requests", "SPECIAL REQUESTS"),
            ("welcome_amenity", "WELCOME AMENITY"),
        ],
    ),
    ("GUEST PREFERENCES", [("notes", "NOTES")]),
    ("RELEVANT INFORMATION", [("perfil", "PERFIL")]),
]


def vip_alert_docx_available() -> bool:
    """Verifica que `python-docx` esté instalado en el entorno de la app."""
    try:
        import docx  # noqa: F401
    except ImportError:
        return False
    return True


def _vip_alert_date_label(value: object) -> str:
    """Devuelve la fecha en el formato corto del formato oficial: `13 Oct`."""
    parsed = value if isinstance(value, (date, datetime)) else parse_fecha(value)
    if isinstance(parsed, datetime):
        parsed = parsed.date()
    if isinstance(parsed, date):
        return f"{parsed.day} {VIP_ALERT_MONTHS[parsed.month - 1]}"
    return str(value or "").strip()


def _vip_alert_prefill(reservation: object) -> dict:
    """Toma lo que ya sabemos de la reserva seleccionada como punto de partida."""
    reservation = reservation if isinstance(reservation, dict) else {}
    qty_raw = pd.to_numeric(reservation.get("qty", 0), errors="coerce")
    qty_label = ""
    if not pd.isna(qty_raw) and float(qty_raw) != 0:
        qty_label = str(int(round(float(qty_raw))))
    return {
        "client_name": str(reservation.get("name", "") or ""),
        "arrival": parse_fecha(reservation.get("check_in")) or datetime.now(),
        "departure": parse_fecha(reservation.get("check_out")) or datetime.now() + timedelta(days=1),
        "pax": qty_label,
        "transportation": str(reservation.get("trans", "") or ""),
        "room": str(reservation.get("room", "") or ""),
        "reservation_id": reservation.get("id"),
    }


def build_vip_alert_docx(payload: dict) -> bytes:
    """Arma el documento Word del VIP Alert con el mismo formato de plantilla.

    Estructura: título `VIP ALERT <cliente>`, la línea de Details en negrita,
    el rango de fechas centrado y una tabla de dos columnas con las bandas
    grises de sección (BASIC INFORMATION / GUEST PREFERENCES / RELEVANT
    INFORMATION), igual que el formato que ya usan.
    """
    from docx import Document
    from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt

    LABEL_WIDTH = Inches(2.0)
    VALUE_WIDTH = Inches(4.8)
    GRIS_BANDA = "D9D9D9"

    def sombrear(celda, color: str) -> None:
        tc_pr = celda._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), color)
        tc_pr.append(shd)

    def escribir(celda, texto: object, bold: bool = False, centrado: bool = False) -> None:
        celda.text = ""
        parrafo = celda.paragraphs[0]
        parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER if centrado else WD_ALIGN_PARAGRAPH.LEFT
        parrafo.paragraph_format.space_after = Pt(2)
        parrafo.paragraph_format.space_before = Pt(2)
        run = parrafo.add_run("" if texto is None else str(texto))
        run.bold = bold
        run.font.name = "Calibri"
        run.font.size = Pt(10.5)

    def linea_centrada(texto: str, size: float, bold: bool, space_after: float) -> None:
        parrafo = document.add_paragraph()
        parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        parrafo.paragraph_format.space_after = Pt(space_after)
        parrafo.paragraph_format.space_before = Pt(0)
        run = parrafo.add_run(texto)
        run.bold = bold
        run.font.name = "Calibri"
        run.font.size = Pt(size)

    document = Document()
    seccion = document.sections[0]
    seccion.top_margin = Inches(0.7)
    seccion.bottom_margin = Inches(0.7)
    seccion.left_margin = Inches(0.7)
    seccion.right_margin = Inches(0.7)

    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(0)

    client_name = str(payload.get("client_name", "") or "").strip()
    details = str(payload.get("details", "") or "").strip()
    arrival_label = _vip_alert_date_label(payload.get("arrival"))
    departure_label = _vip_alert_date_label(payload.get("departure"))

    titulo = document.add_paragraph()
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    titulo.paragraph_format.space_after = Pt(4)
    run_titulo = titulo.add_run("VIP ALERT" + (f" {client_name}" if client_name else ""))
    run_titulo.bold = True
    run_titulo.font.name = "Calibri"
    run_titulo.font.size = Pt(16)

    if details:
        linea_centrada(details, 11.5, True, 12)

    rango = " – ".join(parte for parte in (arrival_label, departure_label) if parte)
    if rango:
        linea_centrada(rango, 11.5, False, 12)

    # Las fechas se muestran en formato corto ("13 Oct") también dentro de la
    # tabla, no como fecha ISO.
    valores = dict(payload)
    valores["arrival"] = arrival_label
    valores["departure"] = departure_label

    filas: list = []
    for titulo_seccion, campos in VIP_ALERT_SECTIONS:
        filas.append(("banda", titulo_seccion))
        for clave, etiqueta in campos:
            filas.append(("campo", etiqueta, valores.get(clave, "")))

    tabla = document.add_table(rows=0, cols=2)
    tabla.style = "Table Grid"
    tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
    tabla.autofit = False

    for fila_def in filas:
        fila = tabla.add_row()
        if fila_def[0] == "banda":
            celda = fila.cells[0].merge(fila.cells[1])
            sombrear(celda, GRIS_BANDA)
            escribir(celda, fila_def[1], bold=True, centrado=True)
        else:
            escribir(fila.cells[0], fila_def[1], bold=True)
            escribir(fila.cells[1], fila_def[2])
        for indice, celda in enumerate(fila.cells):
            celda.width = LABEL_WIDTH if indice == 0 else VALUE_WIDTH
            celda.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _app_rerun() -> None:
    """Rerun completo de la app.

    Necesario para cambiar de un popup a otro: un `st.rerun()` dentro de un
    dialog solo re-ejecuta el fragmento y el popup nuevo nunca se abriría.
    """
    try:
        st.rerun(scope="app")
    except TypeError:
        st.rerun()


def _fragment_rerun() -> None:
    """Rerun solo del popup actual, sin cerrarlo.

    Un `st.rerun()` normal vuelve a ejecutar toda la app; como la bandera que
    abre el popup ya se consumio, el popup se cerraria. Con scope="fragment"
    se vuelve a dibujar unicamente el contenido del popup y este sigue abierto.

    Si por alguna razon se llama fuera de un fragmento, Streamlit lanza una
    excepcion; en ese caso se cae al rerun normal para no romper la pantalla.
    """
    try:
        st.rerun(scope="fragment")
    except (TypeError, st.errors.StreamlitAPIException):
        st.rerun()


@st.dialog("🚨 VIP Alert", width="large")
def vip_alert_dialog() -> None:
    """Popup para llenar el VIP Alert y descargarlo en Word.

    No guarda nada en Supabase: solo captura los datos y genera el .docx.
    """
    prefill = st.session_state.get("vip_alert_prefill") or {}
    nonce = str(prefill.get("reservation_id", "new"))

    st.markdown(
        "<div style='color:#D4AF37;font:800 12px/1.2 Segoe UI,sans-serif;letter-spacing:1.4px;"
        "text-transform:uppercase;margin-bottom:10px;'>"
        f'VIP ALERT &nbsp;·&nbsp; {safe_text(prefill.get("client_name", "")) or "Nuevo"}'
        f' &nbsp;·&nbsp; Room {safe_text(prefill.get("room", "")) or "—"}</div>',
        unsafe_allow_html=True,
    )

    if not vip_alert_docx_available():
        st.error(
            "Falta la dependencia `python-docx` para generar el Word. "
            "Ejecuta `pip install python-docx` y agrégalo a tu requirements."
        )

    with st.form("vip_alert_form"):
        fila1 = st.columns([1.2, 1.8])
        client_name = fila1[0].text_input(
            "CLIENT NAME *",
            value=str(prefill.get("client_name", "") or ""),
            key=f"vip_client_{nonce}",
        )
        details = fila1[1].text_input(
            "DETAILS (línea bajo el título)",
            value="",
            key=f"vip_details_{nonce}",
            placeholder="Ej: Director of Sponsorship & Activation at Resorts World Las Vegas",
        )

        fila2 = st.columns(2)
        arrival = fila2[0].date_input(
            "ARRIVAL",
            value=(prefill.get("arrival") or datetime.now()).date()
            if isinstance(prefill.get("arrival"), datetime)
            else (prefill.get("arrival") or date.today()),
            key=f"vip_arrival_{nonce}",
        )
        departure = fila2[1].date_input(
            "DEPARTURE",
            value=(prefill.get("departure") or datetime.now() + timedelta(days=1)).date()
            if isinstance(prefill.get("departure"), datetime)
            else (prefill.get("departure") or date.today() + timedelta(days=1)),
            key=f"vip_departure_{nonce}",
        )

        fila3 = st.columns(3)
        location = fila3[0].text_input("LOCATION", value="", key=f"vip_location_{nonce}")
        company = fila3[1].text_input("COMPANY", value="", key=f"vip_company_{nonce}")
        media_agency = fila3[2].text_input("MEDIA | AGENCY", value="", key=f"vip_media_{nonce}")

        fila4 = st.columns(3)
        concierge = fila4[0].text_input(
            "PERSONAL CONCIERGE IN CHARGE", value="", key=f"vip_concierge_{nonce}"
        )
        transportation = fila4[1].text_input(
            "TRANSPORTATION",
            value=str(prefill.get("transportation", "") or ""),
            key=f"vip_transport_{nonce}",
        )
        pax = fila4[2].text_input(
            "PAX. NUMBER",
            value=str(prefill.get("pax", "") or ""),
            key=f"vip_pax_{nonce}",
        )

        fila5 = st.columns(2)
        allergies = fila5[0].text_input("ALLERGIES", value="", key=f"vip_allergies_{nonce}")
        welcome_amenity = fila5[1].text_input(
            "WELCOME AMENITY", value="", key=f"vip_amenity_{nonce}"
        )

        special_requests = st.text_area(
            "SPECIAL REQUESTS", value="", height=70, key=f"vip_requests_{nonce}"
        )
        notes = st.text_area("NOTES", value="", height=70, key=f"vip_notes_{nonce}")
        perfil = st.text_area("PERFIL", value="", height=100, key=f"vip_perfil_{nonce}")

        generado = st.form_submit_button(
            "📄 GENERAR DOCUMENTO WORD", type="primary", use_container_width=True
        )

    if generado:
        if not str(client_name).strip():
            st.error("El CLIENT NAME es obligatorio: es el nombre que va en el título.")
        else:
            payload = {
                "client_name": str(client_name).strip(),
                "details": details,
                "arrival": arrival,
                "departure": departure,
                "location": location,
                "company": company,
                "media_agency": media_agency,
                "concierge": concierge,
                "transportation": transportation,
                "pax": pax,
                "allergies": allergies,
                "special_requests": special_requests,
                "welcome_amenity": welcome_amenity,
                "notes": notes,
                "perfil": perfil,
            }
            try:
                st.session_state["vip_alert_doc"] = build_vip_alert_docx(payload)
                st.session_state["vip_alert_doc_name"] = (
                    f"VIP ALERT {payload['client_name']}.docx"
                )
            except ImportError:
                st.session_state.pop("vip_alert_doc", None)
                st.error(
                    "No se pudo generar el Word: falta `python-docx`. "
                    "Ejecuta `pip install python-docx` en el entorno de la app."
                )
            except Exception as exc:  # noqa: BLE001 - se muestra al usuario
                st.session_state.pop("vip_alert_doc", None)
                st.error(f"No se pudo generar el documento: {exc}")

    if st.session_state.get("vip_alert_doc"):
        st.success("Documento listo. Ábrelo o guárdalo con el botón de abajo.")
        st.download_button(
            "⬇️ DESCARGAR WORD",
            data=st.session_state["vip_alert_doc"],
            file_name=st.session_state.get("vip_alert_doc_name", "VIP ALERT.docx"),
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            type="primary",
            use_container_width=True,
            key=f"vip_alert_download_{nonce}",
        )

    volver_col, cerrar_col = st.columns(2)
    if volver_col.button(
        "← Volver a Editar", use_container_width=True, key=f"vip_back_{nonce}"
    ):
        st.session_state.pop("vip_alert_doc", None)
        st.session_state["open_editar"] = True
        _app_rerun()
    if cerrar_col.button("Cerrar", use_container_width=True, key=f"vip_close_{nonce}"):
        st.session_state.pop("vip_alert_doc", None)
        _app_rerun()


# -----------------------------------------------------------------------------
# P. DINNING  (formulario en Word · no guarda nada en Supabase)
# -----------------------------------------------------------------------------

# Logo Waldorf Astoria Costa Rica · Punta Cacique (blanco sobre azul marino).
# Va embebido para que la app siga siendo un solo archivo .py.
PDINNING_LOGO_B64 = (
    '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'
)

# Estructura de la tabla del formulario. Cada fila es una lista de celdas
# (cuantas columnas ocupa, texto, negrita). La plantilla tiene 10 columnas
# iguales; los "span" reproducen las celdas combinadas de la imagen.
PDINNING_COLUMNAS = 10


def pdinning_row_specs(payload: dict) -> list:
    """Devuelve las 10 filas del formulario con los datos ya colocados."""
    fecha = payload.get("fecha")
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    fecha_label = fecha.strftime("%d/%m/%Y") if isinstance(fecha, date) else str(fecha or "")

    return [
        [
            (1, "Familia:", True), (3, payload.get("familia", ""), False),
            (1, "Room:", True), (2, payload.get("room", ""), False),
            (1, "Fecha:", True), (2, fecha_label, False),
        ],
        [
            (1, "No. Pax:", True), (2, payload.get("pax", ""), False),
            (1, "Hora:", True), (2, payload.get("hora", ""), False),
            (1, "Ubicación:", True), (3, payload.get("ubicacion", ""), False),
        ],
        [(2, "Tipo de menú:", True), (8, payload.get("tipo_menu", ""), False)],
        [(3, "Alergias o restricciones:", True), (7, payload.get("alergias", ""), False)],
        [(2, "Preferencias:", True), (8, payload.get("preferencias", ""), False)],
        [
            (2, "Set Up solicitado:", True), (6, payload.get("setup", ""), False),
            (1, "N/A", False), (1, "", False),
        ],
        [
            (2, "Tipo de flores:", True), (6, payload.get("flores", ""), False),
            (1, "N/A", False), (1, "", False),
        ],
        [(2, "Ocasión especial:", True), (8, payload.get("ocasion", ""), False)],
        [(2, "Bebidas solicitadas:", True), (8, payload.get("bebidas", ""), False)],
        [(2, "Adicionales:", True), (8, payload.get("adicionales", ""), False)],
    ]


def build_pdinning_docx(payload: dict) -> bytes:
    """Arma el formulario P. Dinning en Word con el formato de la plantilla.

    Hoja horizontal, el logo arriba centrado y una tabla de 10 columnas con
    las celdas combinadas igual que en la plantilla en papel.
    """
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import (
        WD_ALIGN_VERTICAL,
        WD_ROW_HEIGHT_RULE,
        WD_TABLE_ALIGNMENT,
    )
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    ALTO_FILA = Inches(0.43)
    ALTO_ULTIMA = Inches(1.75)
    ANCHO_TABLA = Inches(9.60)
    # Division entera: Emu es un int, y una division normal devolveria
    # un float que python-docx rechaza al asignar el ancho de la celda.
    ANCHO_COLUMNA = ANCHO_TABLA // PDINNING_COLUMNAS
    TAMANO_FUENTE = Pt(9)

    document = Document()
    seccion = document.sections[0]
    ancho_pagina, alto_pagina = seccion.page_width, seccion.page_height
    seccion.orientation = WD_ORIENT.LANDSCAPE
    if ancho_pagina < alto_pagina:
        seccion.page_width, seccion.page_height = alto_pagina, ancho_pagina
    seccion.top_margin = Inches(0.45)
    seccion.bottom_margin = Inches(0.45)
    seccion.left_margin = Inches(0.70)
    seccion.right_margin = Inches(0.70)

    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = TAMANO_FUENTE
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.space_before = Pt(0)

    # ── Logo centrado ──
    logo = document.add_paragraph()
    logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    logo.paragraph_format.space_before = Pt(0)
    logo.paragraph_format.space_after = Pt(8)
    if PDINNING_LOGO_B64:
        try:
            logo.add_run().add_picture(
                BytesIO(base64.b64decode(PDINNING_LOGO_B64)), width=Inches(3.60)
            )
        except Exception:  # noqa: BLE001 - si el logo falla, el formulario sigue
            pass

    def escribir(celda, texto: object, negrita: bool, centrado: bool = False) -> None:
        celda.text = ""
        parrafo = celda.paragraphs[0]
        parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER if centrado else WD_ALIGN_PARAGRAPH.LEFT
        parrafo.paragraph_format.space_before = Pt(0)
        parrafo.paragraph_format.space_after = Pt(0)
        run = parrafo.add_run("" if texto is None else str(texto))
        run.bold = negrita
        run.font.name = "Calibri"
        run.font.size = TAMANO_FUENTE
        celda.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    filas = pdinning_row_specs(payload)
    tabla = document.add_table(rows=len(filas), cols=PDINNING_COLUMNAS)
    tabla.style = "Table Grid"
    tabla.autofit = False
    tabla.alignment = WD_TABLE_ALIGNMENT.CENTER

    for columna in tabla.columns:
        columna.width = ANCHO_COLUMNA

    for indice, fila in enumerate(filas):
        es_ultima = indice == len(filas) - 1
        fila_docx = tabla.rows[indice]
        fila_docx.height = ALTO_ULTIMA if es_ultima else ALTO_FILA
        fila_docx.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST

        columna = 0
        for span, texto, negrita in fila:
            celda = tabla.cell(indice, columna)
            if span > 1:
                celda = celda.merge(tabla.cell(indice, columna + span - 1))
            celda.width = ANCHO_COLUMNA * span
            escribir(celda, texto, negrita)
            columna += span

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdinning_file_name(payload: dict) -> str:
    """Nombre del archivo: `P DINNING <familia> <dd-mm-yyyy>.docx`."""
    partes = ["P DINNING"]
    familia = str(payload.get("familia", "") or "").strip()
    if familia:
        partes.append(familia)
    fecha = payload.get("fecha")
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    if isinstance(fecha, date):
        partes.append(fecha.strftime("%d-%m-%Y"))
    return " ".join(partes) + ".docx"


@st.dialog("🍽️ P. Dinning", width="large")
def pdinning_dialog() -> None:
    """Popup para llenar el formulario P. Dinning y descargarlo en Word.

    No guarda nada en Supabase: solo captura los datos y genera el .docx.
    """
    st.markdown(
        "<div style='color:#D4AF37;font:800 12px/1.2 Segoe UI,sans-serif;letter-spacing:1.4px;"
        "text-transform:uppercase;margin-bottom:4px;'>P. DINNING &nbsp;·&nbsp; "
        "WALDORF ASTORIA COSTA RICA · PUNTA CACIQUE</div>"
        "<div style='color:#8ca4ba;font-size:11px;margin-bottom:12px;'>"
        "Llena el formulario y genera el Word. No se guarda nada en la base de datos.</div>",
        unsafe_allow_html=True,
    )

    if not vip_alert_docx_available():
        st.error(
            "Falta la dependencia `python-docx` para generar el Word. "
            "Ejecuta `pip install python-docx` y agrégalo a tu requirements."
        )

    with st.form("pdinning_form"):
        fila1 = st.columns(3)
        familia = fila1[0].text_input(
            "FAMILIA", value="", key="pdin_familia", placeholder="Ej: Familia Schwartz"
        )
        room = fila1[1].text_input("ROOM", value="", key="pdin_room", placeholder="Ej: 811")
        fecha = fila1[2].date_input("FECHA", value=date.today(), key="pdin_fecha")

        fila2 = st.columns(3)
        pax = fila2[0].text_input("NO. PAX", value="", key="pdin_pax", placeholder="Ej: 4")
        hora = fila2[1].text_input("HORA", value="", key="pdin_hora", placeholder="Ej: 7:00 PM")
        ubicacion = fila2[2].text_input(
            "UBICACIÓN", value="", key="pdin_ubicacion", placeholder="Ej: Villa 3"
        )

        fila3 = st.columns(2)
        tipo_menu = fila3[0].text_input(
            "TIPO DE MENÚ", value="", key="pdin_tipo_menu", placeholder="Ej: Cena privada 4 tiempos"
        )
        alergias = fila3[1].text_input(
            "ALERGIAS O RESTRICCIONES", value="", key="pdin_alergias", placeholder="Ej: Sin gluten"
        )

        preferencias = st.text_input(
            "PREFERENCIAS", value="", key="pdin_preferencias", placeholder="Ej: Mesa en la terraza"
        )

        fila4 = st.columns(2)
        setup = fila4[0].text_input(
            "SET UP SOLICITADO", value="", key="pdin_setup", placeholder="Ej: Mesa redonda para 4"
        )
        flores = fila4[1].text_input(
            "TIPO DE FLORES", value="", key="pdin_flores", placeholder="Ej: Orquídeas blancas"
        )

        fila5 = st.columns(2)
        ocasion = fila5[0].text_input(
            "OCASIÓN ESPECIAL", value="", key="pdin_ocasion", placeholder="Ej: Aniversario"
        )
        bebidas = fila5[1].text_input(
            "BEBIDAS SOLICITADAS", value="", key="pdin_bebidas", placeholder="Ej: Vino blanco"
        )

        adicionales = st.text_area(
            "ADICIONALES", value="", height=90, key="pdin_adicionales",
            placeholder="Cualquier detalle extra que deba quedar por escrito.",
        )

        generado = st.form_submit_button(
            "📄 GENERAR DOCUMENTO WORD", type="primary", use_container_width=True
        )

    if generado:
        if not str(familia).strip():
            st.error("El campo FAMILIA es obligatorio: es el nombre que va en el formulario.")
        else:
            payload = {
                "familia": str(familia).strip(),
                "room": room,
                "fecha": fecha,
                "pax": pax,
                "hora": hora,
                "ubicacion": ubicacion,
                "tipo_menu": tipo_menu,
                "alergias": alergias,
                "preferencias": preferencias,
                "setup": setup,
                "flores": flores,
                "ocasion": ocasion,
                "bebidas": bebidas,
                "adicionales": adicionales,
            }
            try:
                st.session_state["pdinning_doc"] = build_pdinning_docx(payload)
                st.session_state["pdinning_doc_name"] = _pdinning_file_name(payload)
            except ImportError:
                st.session_state.pop("pdinning_doc", None)
                st.error(
                    "No se pudo generar el Word: falta `python-docx`. "
                    "Ejecuta `pip install python-docx` en el entorno de la app."
                )
            except Exception as exc:  # noqa: BLE001 - se muestra al usuario
                st.session_state.pop("pdinning_doc", None)
                st.error(f"No se pudo generar el documento: {exc}")

    if st.session_state.get("pdinning_doc"):
        st.success("Documento listo. Ábrelo o guárdalo con el botón de abajo.")
        st.download_button(
            "⬇️ DESCARGAR WORD",
            data=st.session_state["pdinning_doc"],
            file_name=st.session_state.get("pdinning_doc_name", "P DINNING.docx"),
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            type="primary",
            use_container_width=True,
            key="pdinning_download",
        )

    cerrar_col, limpiar_col = st.columns(2)
    if cerrar_col.button("Cerrar", use_container_width=True, key="pdinning_close"):
        st.session_state.pop("pdinning_doc", None)
        _app_rerun()
    if limpiar_col.button(
        "🧹 Limpiar formulario", use_container_width=True, key="pdinning_reset"
    ):
        st.session_state.pop("pdinning_doc", None)
        for clave in (
            "pdin_familia", "pdin_room", "pdin_pax", "pdin_hora", "pdin_ubicacion",
            "pdin_tipo_menu", "pdin_alergias", "pdin_preferencias", "pdin_setup",
            "pdin_flores", "pdin_ocasion", "pdin_bebidas", "pdin_adicionales",
        ):
            st.session_state.pop(clave, None)
        _fragment_rerun()

def _import_body(context: str = "page") -> None:
    """Importador de Excel, reutilizable en pagina o en popup."""
    st.info("Columnas requeridas: " + ", ".join(IMPORT_COLUMNS))
    uploaded = st.file_uploader("Archivo Excel", type=["xlsx", "xls"], key=f"import_uploader_{context}")
    if not uploaded:
        return

    try:
        frame = pd.read_excel(uploaded)
    except Exception as exc:
        st.error(f"No se pudo leer el archivo: {exc}")
        return

    frame.columns = [str(column).strip().lower() for column in frame.columns]
    missing = [column for column in IMPORT_COLUMNS if column not in frame.columns]
    if missing:
        st.error("Faltan estas columnas: " + ", ".join(missing))
        return

    preview = frame[IMPORT_COLUMNS].copy()
    preview["check_in"] = preview["check_in"].map(normalizar_fecha)
    preview["check_out"] = preview["check_out"].map(normalizar_fecha)
    # ETA: acepta "11:00 AM", "09:00 AM", "03:00 PM" (con o sin cero a la
    # izquierda) tal cual vienen en Plantilla_Importar.xlsx, y las deja en
    # el mismo formato que usa el selector de horas del formulario.
    preview["eta"] = preview["eta"].map(normalizar_eta)
    # ROOM: quitar el ".0" que Excel agrega a las celdas numéricas (811.0 -> 811).
    preview["room"] = preview["room"].map(normalizar_room)
    # RATE: dejar siempre el símbolo $, haya venido o no en el archivo.
    preview["rate"] = preview["rate"].map(normalizar_rate)
    # Reemplazar NaN/None por cadena vacia (o 0 para qty) para visualizacion limpia
    for col in preview.columns:
        if col == "qty":
            # CORRECCIÓN: antes se truncaba a entero con int(float(x)), lo
            # que perdía el decimal que indica niños (2.1 -> 2, perdiendo el
            # "+1"). Ahora se conserva 1 decimal para que la tabla lo pueda
            # mostrar como "2+1" (ver `format_qty`).
            preview[col] = preview[col].apply(lambda x: 0.0 if pd.isna(x) or str(x).lower() in ("nan", "none", "null", "") else round(float(x), 1))
        elif col == "eta":
            continue
        else:
            preview[col] = preview[col].apply(lambda x: "" if pd.isna(x) or str(x).lower() in ("nan", "none", "null") else x)
    st.success(f"Archivo válido: {len(preview)} reservaciones detectadas.")
    st.dataframe(preview, use_container_width=True, hide_index=True, height=300)

    if st.button("IMPORTAR A BASE DE DATOS", type="primary", use_container_width=True, key=f"do_import_{context}"):
        records: list[dict] = []
        for _, row in preview.iterrows():
            record = {}
            for column in IMPORT_COLUMNS:
                value = row[column]
                if column == "eta":
                    # Ya viene normalizado arriba; puede ser "" legítimamente.
                    value = "" if pd.isna(value) else str(value).strip()
                elif pd.isna(value) or str(value).lower() in ("nan", "none", "null"):
                    value = ""
                elif column == "qty":
                    # Igual que en el preview: conservar el decimal (2.1),
                    # no truncar a entero.
                    value = round(float(pd.to_numeric(value, errors="coerce") or 0), 1)
                elif column == "room":
                    # Excel entrega la habitación como número (811.0): se
                    # guarda limpia, sin el ".0".
                    value = normalizar_room(value)
                elif column == "rate":
                    # Se guarda con el símbolo $ siempre, así la tabla lo
                    # muestra sin importar cómo venga el archivo.
                    value = normalizar_rate(value)
                else:
                    value = str(value).strip()
                record[column] = value
            records.append(record)
        try:
            insertar_lote(records)
            st.success(f"{len(records)} reservaciones importadas correctamente.")
        except Exception as exc:
            st.error(f"No se completó la importación: {exc}")


@st.dialog("⬆ Importar Reservaciones", width="large")
def import_dialog() -> None:
    """Popup flotante para importar un Excel sin salir del dashboard."""
    _import_body("dialog")
    if st.button("Cerrar", use_container_width=True, key="close_import_dialog"):
        st.rerun()


def render_import() -> None:
    """Vista legacy en pagina completa (se conserva por compatibilidad)."""
    st.subheader("Importar reservaciones desde Excel")
    render_back_link()
    _import_body("page")


def _export_body(df: pd.DataFrame, context: str = "page") -> None:
    """Exportador a Excel, reutilizable en pagina o en popup."""
    filtered, _ = apply_filters(df)
    st.info(f"Se exportarán {len(filtered)} reservaciones, organizadas por categoría.")
    st.dataframe(filtered[DISPLAY_COLUMNS], use_container_width=True, hide_index=True, height=300)

    def _build_excel(data: pd.DataFrame) -> BytesIO:
        """Generador de Excel AUTOCONTENIDO: usa solo dicts de Python, sin acceso por etiquetas de pandas."""
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        export_columns = [
            ("eta", "ETA"), ("name", "NAME"), ("qty", "QTY"),
            ("room", "ROOM"), ("email", "EMAIL"), ("check_in", "CHECK IN"),
            ("check_out", "CHECK OUT"), ("nights", "NIGHTS"),
            ("res_number", "RESERVATION"), ("phone", "PHONE"), ("info", "INFORMATION"),
            ("ird", "IRD"), ("hsk", "HSK"), ("rate", "RATE"), ("trans", "TRANSPORTATION"),
        ]
        export_keys = [key for key, _ in export_columns]

        def _clean(value):
            if value is None:
                return ""
            try:
                if pd.isna(value):
                    return ""
            except Exception:
                pass
            if isinstance(value, (str, int, float, bool)) or hasattr(value, "isoformat"):
                return value
            return str(value)

        # Extraer filas como dicts de Python puros (sin acceso por etiqueta de pandas)
        try:
            raw_records = data.to_dict("records")
        except Exception:
            try:
                normalized = [str(column).strip().lower() for column in data.columns]
                raw_records = [dict(zip(normalized, values)) for values in data.values.tolist()]
            except Exception:
                raw_records = []

        rows = []
        for record in raw_records:
            lowered = {}
            for label, value in record.items():
                try:
                    lowered[str(label).strip().lower()] = value
                except Exception:
                    pass
            row = {}
            for key in export_keys:
                try:
                    row[key] = _clean(lowered.get(key, ""))
                except Exception:
                    row[key] = ""
            try:
                row["_info_upper"] = str(row.get("info") or "").upper()
            except Exception:
                row["_info_upper"] = ""
            rows.append(row)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Arrivals"

        fill_section = PatternFill("solid", fgColor="FCD5B4")
        fill_header = PatternFill("solid", fgColor="4BACC6")
        fill_data = PatternFill("solid", fgColor="F4F7F9")
        section_font = Font(name="Calibri", size=10, bold=True, color="000000")
        header_font = Font(name="Calibri", size=10, bold=True, color="000000")
        black_font = Font(name="Calibri", size=10, color="000000")
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left = Alignment(horizontal="left", vertical="center", wrap_text=True)
        border = Border(*(Side(style="thin", color="D6DEE4") for _ in range(4)))

        groups = [
            ("CUMPLEAÑOS", ("BIRTHDAY", "CUMPLE", "BDAY")),
            ("VIP", ("VIP",)),
            ("HONEYMOON", ("HONEYMOON", "LUNA DE MIEL")),
            ("ANNIVERSARY", ("ANNIVERSARY", "ANIVERSARIO")),
            ("BABYMOON", ("BABYMOON",)),
            ("TEAM MEMBER", ("TEAM MEMBER", "STAFF", "EMPLOYEE")),
            ("GENERAL", ()),
        ]

        row_number = 1
        for title, keywords in groups:
            if keywords:
                selected = [row for row in rows if any(keyword in row["_info_upper"] for keyword in keywords)]
                chosen = {id(row) for row in selected}
                rows = [row for row in rows if id(row) not in chosen]
            else:
                selected = rows
                rows = []
            if not selected:
                continue
            sheet.merge_cells(start_row=row_number, start_column=1, end_row=row_number, end_column=len(export_columns))
            cell = sheet.cell(row=row_number, column=1, value=title)
            cell.fill, cell.font, cell.alignment = fill_section, section_font, center
            row_number += 1
            for column_index, (_, heading) in enumerate(export_columns, 1):
                cell = sheet.cell(row=row_number, column=column_index, value=heading)
                cell.fill, cell.font, cell.alignment, cell.border = fill_header, header_font, center, border
            row_number += 1
            for row in selected:
                for column_index, (key, _) in enumerate(export_columns, 1):
                    cell = sheet.cell(row=row_number, column=column_index, value=row[key])
                    cell.fill, cell.font, cell.alignment, cell.border = fill_data, black_font, left, border
                row_number += 1
            row_number += 1

        widths = [11, 24, 7, 10, 28, 17, 17, 9, 17, 18, 28, 18, 18, 10, 22]
        for index, width in enumerate(widths, 1):
            sheet.column_dimensions[chr(64 + index)].width = width
        sheet.freeze_panes = "A3"

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return output

    if not filtered.empty:
        try:
            excel_data = _build_excel(filtered)
        except Exception as exc:
            st.error(f"No se pudo generar el Excel: {exc!r}")
            st.caption("Columnas detectadas: " + ", ".join(map(str, filtered.columns)))
            return
        st.download_button(
            "DESCARGAR EXCEL",
            data=excel_data,
            file_name=f"Arrivals_{datetime.now():%Y%m%d_%H%M}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"download_export_{context}",
        )


@st.dialog("⬇ Exportar Reservaciones", width="large")
def export_dialog() -> None:
    """Popup flotante para exportar el Excel de llegadas."""
    _export_body(cargar_reservaciones(), "dialog")
    if st.button("Cerrar", use_container_width=True, key="close_export_dialog"):
        st.rerun()


def render_export(df: pd.DataFrame) -> None:
    """Vista legacy en pagina completa (se conserva por compatibilidad)."""
    st.subheader("Exportar reservaciones a Excel")
    render_back_link()
    _export_body(df, "page")


def _agenda_body(df: pd.DataFrame, context: str = "page") -> None:
    """Agenda de llegadas/salidas por fecha, reutilizable en pagina o popup."""
    selected_date = st.date_input("Fecha", value=datetime.now().date(), key=f"agenda_date_{context}")
    formatted = selected_date.strftime("%B %d, %Y")
    arrivals = df[df["check_in"] == formatted]
    departures = df[df["check_out"] == formatted]
    c1, c2, c3 = st.columns(3)
    c1.metric("Llegan", len(arrivals))
    c2.metric("Salen", len(departures))
    c3.metric("Total en base", len(df))
    arrivals_tab, departures_tab = st.tabs(["Llegadas", "Salidas"])
    with arrivals_tab:
        st.dataframe(arrivals[[column for column in DISPLAY_COLUMNS if column in arrivals]], use_container_width=True, hide_index=True)
    with departures_tab:
        st.dataframe(departures[[column for column in DISPLAY_COLUMNS if column in departures]], use_container_width=True, hide_index=True)


@st.dialog("📅 Agenda de Reservaciones", width="large")
def agenda_dialog() -> None:
    """Popup flotante con llegadas y salidas de una fecha."""
    _agenda_body(cargar_reservaciones(), "dialog")
    if st.button("Cerrar", use_container_width=True, key="close_agenda_dialog"):
        st.rerun()


def render_agenda(df: pd.DataFrame) -> None:
    """Vista legacy en pagina completa (se conserva por compatibilidad)."""
    st.subheader("Agenda de reservaciones")
    render_back_link()
    _agenda_body(df, "page")


def _report_body(df: pd.DataFrame, context: str = "page") -> None:
    """Reporte de ocupacion diario, reutilizable en pagina o popup."""
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    today_label, tomorrow_label = today.strftime("%B %d, %Y"), tomorrow.strftime("%B %d, %Y")

    parsed_check_in = df["check_in"].map(parse_fecha)
    parsed_check_out = df["check_out"].map(parse_fecha)
    in_house = df[(parsed_check_in <= today) & (parsed_check_out > today)]
    departures_today = df[df["check_out"] == today_label]
    arrivals_today = df[df["check_in"] == today_label]
    departures_tomorrow = df[df["check_out"] == tomorrow_label]
    arrivals_tomorrow = df[df["check_in"] == tomorrow_label]

    report_data = {
        "En casa": in_house,
        "Salen hoy": departures_today,
        "Salen mañana": departures_tomorrow,
        "Llegan hoy": arrivals_today,
        "Llegan mañana": arrivals_tomorrow,
    }
    metrics = st.columns(5)
    for column, (label, frame) in zip(metrics, report_data.items()):
        column.metric(label, len(frame))
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    report_rows = []
    for label, frame in report_data.items():
        guest_chips = []
        for _, guest in frame.iterrows():
            room_value = guest.get("room", "")
            name_value = guest.get("name", "")
            room = "" if room_value is None or pd.isna(room_value) else str(room_value).strip()
            name = "" if name_value is None or pd.isna(name_value) else str(name_value).strip()
            room_label = safe_text(room or "SIN ROOM")
            name_label = safe_text(name or "SIN NOMBRE")
            guest_chips.append(
                f"<div class='report-guest-chip'>"
                f"<span class='report-room-label'>ROOM {room_label}</span>"
                f"<span class='report-name-label'>{name_label}</span>"
                f"</div>"
            )
        guests_html = "".join(guest_chips) or (
            "<span class='report-empty'>No hay huéspedes en esta categoría</span>"
        )
        report_rows.append(
            f"<div class='report-data-row'>"
            f"<div class='report-category'>{safe_text(label)}</div>"
            f"<div class='report-count'>{len(frame)}</div>"
            f"<div class='report-guest-list'>{guests_html}</div>"
            f"</div>"
        )

    st.markdown(
        """
        <style>
        .occupancy-report-table {
            border:1px solid #252a35; border-radius:9px; overflow:hidden;
            background:#0b0d12; margin-bottom:10px;
        }
        .report-header-row, .report-data-row {
            display:grid; grid-template-columns:1.05fr .55fr 3.25fr;
            align-items:center; column-gap:12px;
        }
        .report-header-row {
            padding:8px 11px; background:#171a22; color:#8ca4ba;
            font-size:10px; font-weight:900; letter-spacing:.55px; text-transform:uppercase;
        }
        .report-data-row {
            min-height:48px; padding:8px 11px; border-top:1px solid #1a1d25;
        }
        .report-category { color:#e6f7ff; font-size:12px; font-weight:800; }
        .report-count { color:#00e5ff; font-size:14px; font-weight:900; text-align:center; }
        .report-guest-list { display:flex; flex-wrap:wrap; gap:5px; min-width:0; }
        .report-guest-chip {
            display:inline-flex; align-items:center; gap:6px; max-width:100%;
            padding:4px 8px; border:1px solid #263342; border-radius:6px;
            background:#101722; color:#dfeff8; font-size:11px; line-height:1.2;
        }
        .report-room-label {
            color:#00e5ff; font-size:9px; font-weight:900; letter-spacing:.35px;
            white-space:nowrap;
        }
        .report-name-label {
            overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        }
        .report-empty { color:#657789; font-size:11px; font-style:italic; }
        @media (max-width: 760px) {
            .report-header-row, .report-data-row {
                grid-template-columns:.95fr .45fr 2fr; column-gap:7px; padding-left:7px; padding-right:7px;
            }
            .report-guest-chip { display:flex; width:100%; }
        }
        </style>
        <div class="occupancy-report-table">
            <div class="report-header-row">
                <div>Categoría</div><div>Reservas</div><div>Guests / Habitaciones</div>
            </div>
        """
        + "".join(report_rows)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.download_button(
        "DESCARGAR REPORTE EXCEL",
        data=exportar_reporte_excel(report_data, today),
        file_name=f"Reporte_Ocupacion_{today:%Y%m%d_%H%M}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key=f"download_report_{context}",
    )


@st.dialog("📊 Reporte de Ocupación", width="large")
def report_dialog() -> None:
    """Popup flotante con el reporte de ocupacion diario."""
    _report_body(cargar_reservaciones(), "dialog")
    if st.button("Cerrar", use_container_width=True, key="close_report_dialog"):
        st.rerun()


def render_report(df: pd.DataFrame) -> None:
    """Vista legacy en pagina completa (se conserva por compatibilidad)."""
    st.subheader("Reporte de ocupación diario")
    render_back_link()
    _report_body(df, "page")


CALCULATOR_HTML = """
<!doctype html>
<html>
<head>
<style>
body{margin:0;background:#000000;font-family:Segoe UI,sans-serif;display:grid;place-items:center;padding:8px;color:#eafaff}
.calculator{width:280px;padding:14px;background:#0d0d0d;border:1px solid #222222;border-radius:16px;box-shadow:0 12px 35px #0008}
#display{background:#000000;border:1px solid #00e5ff;border-radius:10px;color:#00e5ff;font:700 28px monospace;padding:12px;text-align:right;overflow:hidden;margin-bottom:10px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
button{border:0;border-radius:8px;padding:12px 4px;background:#1a1a1a;color:#eafaff;font-weight:800;font-size:15px;cursor:pointer}
button:hover{filter:brightness(1.2)}
button:active{transform:scale(0.96)}
.op{background:#7c3aed}
.equal{background:#00c6df;color:#01171d}
.clear{background:#e11d48}
.hint{color:#8ca4ba;font-size:10px;text-align:center;margin-top:8px}
</style>
</head>
<body tabindex="0">
<div class="calculator">
<div id="display">0</div>
<div class="grid">
<button class="clear" onclick="clearAll()">C</button>
<button onclick="backspace()">⌫</button>
<button class="op" onclick="add('/')">÷</button>
<button class="op" onclick="add('*')">×</button>
<button onclick="add('7')">7</button>
<button onclick="add('8')">8</button>
<button onclick="add('9')">9</button>
<button class="op" onclick="add('-')">−</button>
<button onclick="add('4')">4</button>
<button onclick="add('5')">5</button>
<button onclick="add('6')">6</button>
<button class="op" onclick="add('+')">+</button>
<button onclick="add('1')">1</button>
<button onclick="add('2')">2</button>
<button onclick="add('3')">3</button>
<button onclick="add('.')">.</button>
<button onclick="add('0')">0</button>
<button onclick="add('%')">%</button>
<button onclick="toggleSign()">±</button>
<button class="equal" onclick="calculate()">=</button>
</div>
<div class="hint">⌨️ Teclado activo — usa números, + − × ÷, Enter y Esc</div>
</div>
<script>
let value='';
const out=document.getElementById('display');
function draw(){out.textContent=value||'0'}
function add(v){if('0123456789.'.includes(v)&&out.textContent==='Error')value='';value+=v;draw()}
function clearAll(){value='';draw()}
function backspace(){value=value.slice(0,-1);draw()}
function toggleSign(){value=value.startsWith('-')?value.slice(1):'-'+value;draw()}
function calculate(){
    try{
        let expr=value.replace(/%/g,'/100');
        if(!/^[0-9+*/.() -]+$/.test(expr))throw Error();
        value=String(Function('return ('+expr+')')());
        draw();
    }catch(e){
        value='';
        out.textContent='Error';
    }
}

const KEY_MAP = {
    'Numpad0':'0','Numpad1':'1','Numpad2':'2','Numpad3':'3',
    'Numpad4':'4','Numpad5':'5','Numpad6':'6','Numpad7':'7',
    'Numpad8':'8','Numpad9':'9','NumpadDecimal':'.',
    'NumpadAdd':'+','NumpadSubtract':'-','NumpadMultiply':'*',
    'NumpadDivide':'/','NumpadEnter':'Enter',
    'Digit0':'0','Digit1':'1','Digit2':'2','Digit3':'3',
    'Digit4':'4','Digit5':'5','Digit6':'6','Digit7':'7',
    'Digit8':'8','Digit9':'9',
    'Period':'.','Comma':'.',
    'Slash':'/','Minus':'-','Equal':'+',
};

document.addEventListener('keydown', function(e){
    const mapped = KEY_MAP[e.code] || e.key;
    if('0123456789.+-*/%'.includes(mapped)){
        e.preventDefault();
        e.stopPropagation();
        add(mapped);
    } else if(mapped==='Enter' || e.key==='Enter'){
        e.preventDefault();
        e.stopPropagation();
        calculate();
    } else if(e.key==='Backspace'){
        e.preventDefault();
        e.stopPropagation();
        backspace();
    } else if(e.key==='Escape'){
        e.preventDefault();
        e.stopPropagation();
        clearAll();
    }
});

setTimeout(()=>{ document.body.focus(); }, 300);
</script>
</body>
</html>
"""


@st.dialog("🧮 Calculadora", width="small")
def calculator_dialog() -> None:
    """Muestra la calculadora como un modal flotante sobre el dashboard."""
    st.components.v1.html(CALCULATOR_HTML, height=430, scrolling=False)


CALENDAR_HTML = """
<!doctype html>
<html>
<head>
<style>
body{margin:0;background:#000000;font-family:Segoe UI,sans-serif;display:grid;place-items:center;padding:8px;color:#eafaff}
.calendar-box{width:340px;padding:16px;background:#0d0d0d;border:1px solid #222222;border-radius:16px;box-shadow:0 12px 35px #0008}
.cal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.cal-title{color:#00e5ff;font:800 16px/1.2 "Segoe UI",sans-serif;text-transform:uppercase;letter-spacing:1px}
.cal-nav{display:flex;gap:6px}
.cal-nav button{width:32px;height:32px;border:0;border-radius:8px;background:#1a1a1a;color:#eafaff;font-weight:800;font-size:16px;cursor:pointer}
.cal-nav button:hover{filter:brightness(1.3)}
.cal-nav button:active{transform:scale(0.95)}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;text-align:center}
.cal-day-label{color:#8ca4ba;font-size:10px;font-weight:800;text-transform:uppercase;padding:6px 0}
.cal-day{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;transition:all .12s}
.cal-day:hover{background:#1a1a1a}
.cal-day.other{color:#4a5a6a}
.cal-day.today{background:#00e5ff;color:#00151d;font-weight:900}
.cal-day.selected{background:#D4AF37;color:#1C1300;font-weight:900}
.cal-footer{margin-top:14px;padding-top:12px;border-top:1px solid #1a1a1a;text-align:center;color:#8ca4ba;font-size:11px}
.cal-footer b{color:#00e5ff;font-size:13px}
</style>
</head>
<body>
<div class="calendar-box">
<div class="cal-header">
  <div class="cal-title" id="cal-month">Loading...</div>
  <div class="cal-nav">
    <button onclick="changeMonth(-1)">&#9664;</button>
    <button onclick="goToday()">&#9679;</button>
    <button onclick="changeMonth(1)">&#9654;</button>
  </div>
</div>
<div class="cal-grid" id="cal-grid"></div>
<div class="cal-footer" id="cal-footer">Selecciona una fecha</div>
</div>
<script>
const MONTHS = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const DAYS = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'];
let current = new Date();
let selected = null;

function renderCalendar(){
  const year = current.getFullYear();
  const month = current.getMonth();
  document.getElementById('cal-month').textContent = MONTHS[month] + ' ' + year;

  const grid = document.getElementById('cal-grid');
  grid.innerHTML = '';

  DAYS.forEach(d => {
    const el = document.createElement('div');
    el.className = 'cal-day-label';
    el.textContent = d;
    grid.appendChild(el);
  });

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrev = new Date(year, month, 0).getDate();

  for(let i = firstDay - 1; i >= 0; i--){
    const el = document.createElement('div');
    el.className = 'cal-day other';
    el.textContent = daysInPrev - i;
    grid.appendChild(el);
  }

  const today = new Date();
  for(let d = 1; d <= daysInMonth; d++){
    const el = document.createElement('div');
    el.className = 'cal-day';
    el.textContent = d;
    if(year === today.getFullYear() && month === today.getMonth() && d === today.getDate()){
      el.classList.add('today');
    }
    if(selected && year === selected.getFullYear() && month === selected.getMonth() && d === selected.getDate()){
      el.classList.add('selected');
    }
    el.onclick = function(){
      selected = new Date(year, month, d);
      renderCalendar();
      const opts = { weekday:'long', year:'numeric', month:'long', day:'numeric' };
      document.getElementById('cal-footer').innerHTML = 'Seleccionado: <b>' + selected.toLocaleDateString('es-ES', opts) + '</b>';
    };
    grid.appendChild(el);
  }

  const remaining = (7 - ((firstDay + daysInMonth) % 7)) % 7;
  for(let d = 1; d <= remaining; d++){
    const el = document.createElement('div');
    el.className = 'cal-day other';
    el.textContent = d;
    grid.appendChild(el);
  }
}

function changeMonth(dir){
  current.setMonth(current.getMonth() + dir);
  renderCalendar();
}
function goToday(){
  current = new Date();
  renderCalendar();
}

renderCalendar();
</script>
</body>
</html>
"""


@st.dialog("📅 Almanaque", width="small")
def calendar_dialog() -> None:
    """Muestra el calendario como un modal flotante sobre el dashboard."""
    st.components.v1.html(CALENDAR_HTML, height=460, scrolling=False)


LOGO_FILENAMES = ("fred_wayne.png", "fredwayne.png", "logo_fred_wayne.png", "logo.png")


def _find_logo_path() -> str | None:
    """Devuelve la ruta del archivo de logo si existe junto a la app."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for filename in LOGO_FILENAMES:
        candidate = os.path.join(base_dir, filename)
        if os.path.exists(candidate):
            return candidate
    return None


@st.dialog("🏷️ Fred Wayne", width="small")
def logo_dialog() -> None:
    """Muestra el logo de Fred Wayne como un modal flotante sobre el dashboard."""
    logo_path = _find_logo_path()
    if logo_path:
        encoded = base64.b64encode(open(logo_path, "rb").read()).decode("utf-8")
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;gap:14px;'
            'padding:18px 10px;background:#0d0d0d;border:1px solid #222222;border-radius:16px;">'
            f'<img src="data:image/png;base64,{encoded}" alt="Fred Wayne" '
            'style="max-width:100%;max-height:420px;object-fit:contain;border-radius:12px;">'
            '<div style="color:#D4AF37;font:800 13px/1.2 \'Segoe UI\',sans-serif;'
            'letter-spacing:1.5px;text-transform:uppercase;">Fred Wayne</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning(
            "No se encontro el archivo del logo. Sube `fred_wayne.png` a tu repositorio "
            "junto a este archivo (tambien se aceptan `fredwayne.png`, "
            "`logo_fred_wayne.png` o `logo.png`)."
        )

    if st.button("Cerrar", use_container_width=True, key="close_logo_dialog"):
        st.rerun()


QRCODE_FILENAMES = ("QRCODE.png", "qrcode.png", "QrCode.png", "qr_code.png")


def _find_qrcode_path() -> str | None:
    """Devuelve la ruta del archivo QRCODE.png si existe junto a la app."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for filename in QRCODE_FILENAMES:
        candidate = os.path.join(base_dir, filename)
        if os.path.exists(candidate):
            return candidate
    return None


@st.dialog("🔗 QR Code", width="small")
def qrcode_dialog() -> None:
    """Muestra QRCODE.png como un modal flotante, igual que el popup de Fred Wayne."""
    qr_path = _find_qrcode_path()
    if qr_path:
        encoded = base64.b64encode(open(qr_path, "rb").read()).decode("utf-8")
        st.markdown(
            '<div style="display:flex;flex-direction:column;align-items:center;gap:14px;'
            'padding:18px 10px;background:#0d0d0d;border:1px solid #222222;border-radius:16px;">'
            f'<img src="data:image/png;base64,{encoded}" alt="QR Code" '
            'style="max-width:100%;max-height:420px;object-fit:contain;border-radius:12px;">'
            '<div style="color:#22D3EE;font:800 13px/1.2 \'Segoe UI\',sans-serif;'
            'letter-spacing:1.5px;text-transform:uppercase;">QR Code</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning(
            "No se encontro el archivo `QRCODE.png`. Sube `QRCODE.png` a tu repositorio "
            "junto a este archivo (tambien se aceptan `qrcode.png`, `QrCode.png` o "
            "`qr_code.png`)."
        )

    if st.button("Cerrar", use_container_width=True, key="close_qrcode_dialog"):
        st.rerun()


def _arrival_dates_summary() -> list[tuple[datetime, str, int]]:
    """Devuelve (fecha, etiqueta, cantidad de reservas) por cada check-in existente.

    Toma la columna `check_in` de todas las reservas, la convierte a fecha real
    (con `parse_fecha`, que soporta texto y Timestamp), elimina duplicados y
    ordena cronologicamente de la mas antigua a la mas reciente.
    """
    df = cargar_reservaciones()
    if df.empty or "check_in" not in df.columns:
        return []

    counts: dict[datetime, int] = {}
    for value in df["check_in"].tolist():
        parsed = parse_fecha(value)
        if not parsed:
            continue
        key = datetime(parsed.year, parsed.month, parsed.day)
        counts[key] = counts.get(key, 0) + 1

    return [
        (day, day.strftime("%B %d, %Y"), counts[day])
        for day in sorted(counts)
    ]


def _apply_arrival_date(day: datetime) -> None:
    """Aplica el filtro de check-in de la tabla y vuelve al dashboard."""
    st.query_params["fecha_date"] = day.strftime("%Y-%m-%d")
    st.query_params["skip_splash"] = "1"
    if "action" in st.query_params:
        del st.query_params["action"]
    clear_selection()
    st.rerun()


ARRIVALS_VIEWS = ("lista", "almanaque")

ARRIVALS_CALENDAR_CSS = """
<style>
/* Estilos de las celdas del almanaque de llegadas. Van de lo general a lo
   específico: el último selector con la misma especificidad gana, así que la
   regla base va primero y las variantes (con llegadas / sin llegadas / hoy /
   seleccionado) después. */
[class*="st-key-arrival_cal_"] button {
    min-height:34px !important; padding:2px 0 !important;
    font-size:11px !important; border-radius:8px !important;
}
/* Día CON llegadas: dorado, cursor de mano y hover marcado. */
[class*="st-key-arrival_cal_hit_"] button {
    background:#3a2c00 !important; border:1px solid #D4AF37 !important;
    color:#FFD24A !important; font-weight:800 !important;
}
[class*="st-key-arrival_cal_hit_"] button:hover {
    background:#D4AF37 !important; border-color:#FFE9A8 !important;
    color:#1C1300 !important; transform:scale(1.06);
}
/* Día SIN llegadas: apagado. */
[class*="st-key-arrival_cal_miss_"] button {
    background:#0d0d0d !important; border:1px solid #1c1c1c !important;
    color:#5f7286 !important; font-weight:600 !important;
}
[class*="st-key-arrival_cal_miss_"] button:hover {
    border-color:#2c3a48 !important; color:#8ca4ba !important;
}
/* Hoy (sin llegadas): contorno cian. */
[class*="st-key-arrival_cal_today_"] button {
    background:#06171c !important; border:1px solid #00e5ff !important;
    color:#00e5ff !important; font-weight:800 !important;
}
/* Día ya aplicado como filtro en la tabla. */
[class*="st-key-arrival_cal_sel_"] button {
    background:#00e5ff !important; border:1px solid #00e5ff !important;
    color:#00151d !important; font-weight:900 !important;
}
/* Vista activa en el conmutador Lista / Almanaque: el boton lleva la clave
   terminada en _sel, asi que se puede resaltar sin tocar el HTML de Streamlit. */
[class*="st-key-arrivals_view_list_sel"] button,
[class*="st-key-arrivals_view_cal_sel"] button {
    background:#D4AF37 !important; border:1px solid #FFE9A8 !important;
    color:#1C1300 !important; font-weight:900 !important;
}
.arrivals-cal-head {
    text-align:center; color:#8ca4ba; font-size:10px; font-weight:800;
    text-transform:uppercase; letter-spacing:0.6px; padding-bottom:2px;
}
.arrivals-cal-pad { height:34px; }
</style>
"""


def _arrivals_default_month(dates: list, active: datetime | None) -> str:
    """Mes que se muestra al abrir el almanaque (YYYY-MM).

    Prioridad: el mes del filtro activo; el mes actual si tiene llegadas; el
    mes de la próxima llegada; y si no hay ninguna por delante, el de la
    última registrada. Así nunca se abre en un mes vacío sin motivo.
    """
    today = datetime.now()
    if active:
        return active.strftime("%Y-%m")
    if any(day.strftime("%Y-%m") == today.strftime("%Y-%m") for day, _, _ in dates):
        return today.strftime("%Y-%m")
    hoy = datetime(today.year, today.month, today.day)
    proximas = [day for day, _, _ in dates if day >= hoy]
    if proximas:
        return proximas[0].strftime("%Y-%m")
    return dates[-1][0].strftime("%Y-%m")


def _render_arrivals_calendar(dates: list, active: datetime | None) -> None:
    """Almanaque mensual con las fechas de llegada resaltadas.

    Un día con llegadas se pinta en dorado y al hacer clic filtra la tabla
    principal (mismo `_apply_arrival_date` que usa la lista). Un día sin
    llegadas muestra "Sin coincidencias" al pasar el mouse y, al hacer clic,
    avisa que no hay reservas para esa fecha.
    """
    counts = {day.strftime("%Y-%m-%d"): count for day, _, count in dates}
    active_key = datetime(active.year, active.month, active.day) if active else None
    now = datetime.now()
    today_key = datetime(now.year, now.month, now.day)

    month_key = st.session_state.get("arrivals_cal_month") or _arrivals_default_month(dates, active)
    try:
        month_start = datetime.strptime(month_key, "%Y-%m")
    except (TypeError, ValueError):
        month_start = today_key
    month_start = month_start.replace(day=1)
    st.session_state["arrivals_cal_month"] = month_start.strftime("%Y-%m")

    st.markdown(ARRIVALS_CALENDAR_CSS, unsafe_allow_html=True)

    # ── Navegación de mes ──
    nav_title, nav_prev, nav_today, nav_next = st.columns([3, 1, 1, 1])
    nav_title.markdown(
        "<div style='color:#D4AF37;font:800 15px/2.1 Segoe UI,sans-serif;"
        "letter-spacing:1px;text-transform:uppercase;'>"
        f"{month_start.strftime('%B %Y')}</div>",
        unsafe_allow_html=True,
    )
    if nav_prev.button("◀", key="arrivals_cal_prev", use_container_width=True, help="Mes anterior"):
        anterior = (month_start - timedelta(days=1)).replace(day=1)
        st.session_state["arrivals_cal_month"] = anterior.strftime("%Y-%m")
        st.session_state.pop("arrivals_cal_msg", None)
        _fragment_rerun()
    if nav_today.button("●", key="arrivals_cal_go_today", use_container_width=True, help="Mes actual"):
        st.session_state["arrivals_cal_month"] = today_key.strftime("%Y-%m")
        st.session_state.pop("arrivals_cal_msg", None)
        _fragment_rerun()
    if nav_next.button("▶", key="arrivals_cal_next", use_container_width=True, help="Mes siguiente"):
        siguiente = (month_start + timedelta(days=32)).replace(day=1)
        st.session_state["arrivals_cal_month"] = siguiente.strftime("%Y-%m")
        st.session_state.pop("arrivals_cal_msg", None)
        _fragment_rerun()

    # ── Cuadrícula ──
    for columna, etiqueta in zip(
        st.columns(7), ("Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb")
    ):
        columna.markdown(
            f"<div class='arrivals-cal-head'>{etiqueta}</div>", unsafe_allow_html=True
        )

    dias_del_mes = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    desplazamiento = (month_start.weekday() + 1) % 7  # domingo = columna 0
    semanas = math.ceil((desplazamiento + dias_del_mes.day) / 7)

    for semana in range(semanas):
        columnas = st.columns(7)
        for posicion, columna in enumerate(columnas):
            numero = semana * 7 + posicion - desplazamiento + 1
            with columna:
                if numero < 1 or numero > dias_del_mes.day:
                    st.markdown("<div class='arrivals-cal-pad'></div>", unsafe_allow_html=True)
                    continue

                dia = month_start.replace(day=numero)
                fecha_iso = dia.strftime("%Y-%m-%d")
                llegadas = counts.get(fecha_iso, 0)
                es_hoy = dia == today_key
                es_activo = active_key is not None and dia == active_key
                etiqueta_dia = f"{numero}·{llegadas}" if llegadas else str(numero)

                if es_activo:
                    prefijo = "arrival_cal_sel_"
                    ayuda = f"{llegadas} llegada(s) · este día ya está filtrado en la tabla"
                elif llegadas:
                    prefijo = "arrival_cal_hit_"
                    ayuda = (
                        f"{llegadas} llegada{'s' if llegadas != 1 else ''}"
                        " · clic para ver la tabla"
                    )
                elif es_hoy:
                    prefijo = "arrival_cal_today_"
                    ayuda = "Hoy · sin coincidencias"
                else:
                    prefijo = "arrival_cal_miss_"
                    ayuda = "Sin coincidencias"

                if st.button(
                    etiqueta_dia,
                    key=f"{prefijo}{fecha_iso.replace('-', '')}",
                    help=ayuda,
                    use_container_width=True,
                ):
                    if llegadas:
                        st.session_state.pop("arrivals_cal_msg", None)
                        _apply_arrival_date(dia)
                    else:
                        st.session_state["arrivals_cal_msg"] = (
                            f"No hay reservas para {dia.strftime('%B %d, %Y')}."
                        )

    if not any(clave.startswith(month_start.strftime("%Y-%m")) for clave in counts):
        st.caption("Este mes no tiene llegadas registradas. Usa ◀ ▶ para moverte a otro mes.")

    mensaje = st.session_state.pop("arrivals_cal_msg", "")
    if mensaje:
        st.warning(mensaje)


@st.dialog("📅 Arrivals By Date", width="small")
def arrivals_dates_dialog() -> None:
    """Popup con todas las fechas de check-in; al hacer clic filtra la tabla."""
    # ── Total de reservas en la esquina superior derecha del popup ──
    # Es el mismo dato que el badge "TOTAL RESERVAS" del tablero: si hay un
    # filtro activo (check-out, fecha de llegada o busqueda) pasa a
    # "RESERVAS FILTRADAS" con la cantidad que quedo visible.
    _df_total = cargar_reservaciones()
    _prev_total, _filtros_total = apply_filters(_df_total)
    total_display = len(_prev_total) if _filtros_total else len(_df_total)
    total_label = "RESERVAS FILTRADAS" if _filtros_total else "TOTAL RESERVAS"

    st.markdown(
        """
        <style>
        /* El popup ya es position:relative, asi que el badge se ancla a su
           esquina superior derecha, a la izquierda de la X de cerrar. */
        .st-key-arrivals_total_badge {
            position: absolute !important;
            top: 25px;
            right: 52px;
            width: auto !important;
            max-width: 60% !important;
            z-index: 5;
        }
        .arrivals-total-pill {
            display: inline-flex; align-items: center; gap: 8px;
            background: #080808; border: 1px solid #1e1e1e; border-radius: 999px;
            padding: 4px 11px; white-space: nowrap;
        }
        .arrivals-total-pill .atp-label {
            color: #71879a; font-size: 9px; font-weight: 800;
            letter-spacing: .7px; text-transform: uppercase;
        }
        .arrivals-total-pill .atp-value {
            color: #00e5ff; font-size: 14px; font-weight: 900; line-height: 1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="arrivals_total_badge"):
        st.markdown(
            f'<div class="arrivals-total-pill"><span class="atp-label">{total_label}</span>'
            f'<span class="atp-value">{total_display}</span></div>',
            unsafe_allow_html=True,
        )

    dates = _arrival_dates_summary()

    if not dates:
        st.info("No hay fechas de check-in registradas todavia.")
        if st.button("Cerrar", use_container_width=True, key="close_arrivals_empty"):
            st.rerun()
        return

    active = date_from_filter(str(st.query_params.get("fecha_date", "")))
    active_key = datetime(active.year, active.month, active.day) if active else None

    st.markdown(
        "<div style='color:#8ca4ba;font-size:11px;font-weight:700;letter-spacing:1px;"
        "text-transform:uppercase;text-align:center;margin-bottom:10px;'>"
        f"{len(dates)} fechas de llegada · haz clic para ver las reservas de ese dia</div>",
        unsafe_allow_html=True,
    )

    # ── Selector de vista: lista (como antes) o almanaque ──
    vista = st.session_state.get("arrivals_view", "lista")
    if vista not in ARRIVALS_VIEWS:
        vista = "lista"
    # La clave cambia con la vista activa para que el CSS pueda resaltarla.
    vista_cols = st.columns(2)
    if vista_cols[0].button(
        "📋 Lista",
        key="arrivals_view_list_sel" if vista == "lista" else "arrivals_view_list",
        use_container_width=True,
        help="Ver las fechas como lista",
    ):
        st.session_state["arrivals_view"] = "lista"
        st.session_state.pop("arrivals_cal_msg", None)
    if vista_cols[1].button(
        "📅 Almanaque",
        key="arrivals_view_cal_sel" if vista == "almanaque" else "arrivals_view_calendar",
        use_container_width=True,
        help="Ver las fechas en un calendario mensual",
    ):
        st.session_state["arrivals_view"] = "almanaque"
        st.session_state.pop("arrivals_cal_msg", None)
    vista = st.session_state.get("arrivals_view", "lista")

    if vista == "almanaque":
        _render_arrivals_calendar(dates, active)
    else:
        query = st.text_input(
            "Buscar fecha",
            key="arrivals_date_search",
            placeholder="Ej: March, 2026, 21…",
            label_visibility="collapsed",
        ).strip().lower()

        if query:
            dates = [item for item in dates if query in item[1].lower()]
            if not dates:
                st.warning("Ninguna fecha coincide con la busqueda.")

        st.markdown(
            """
            <style>
            .st-key-arrivals_list button {
                justify-content:flex-start !important;
                text-align:left !important;
                background:#0a0a0a !important;
                border:1px solid #1e1e1e !important;
                color:#eafaff !important;
                font: 600 13px/1.2 'Segoe UI', sans-serif !important;
                padding:7px 12px !important;
                border-radius:8px !important;
            }
            .st-key-arrivals_list button:hover {
                border-color:#00e5ff !important;
                color:#00e5ff !important;
                background:#06171c !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        with st.container(key="arrivals_list", height=380):
            current_month = ""
            for day, label, count in dates:
                month_label = day.strftime("%B %Y").upper()
                if month_label != current_month:
                    current_month = month_label
                    st.markdown(
                        "<div style='color:#D4AF37;font-size:10px;font-weight:800;letter-spacing:1.4px;"
                        "margin:10px 0 6px;border-left:3px solid #D4AF37;padding-left:8px;'>"
                        f"{month_label}</div>",
                        unsafe_allow_html=True,
                    )

                is_active = active_key is not None and day == active_key
                prefix = "▸ " if is_active else ""
                if st.button(
                    f"{prefix}{label}   ·   {count} reserva{'s' if count != 1 else ''}",
                    key=f"arrival_date_{day.strftime('%Y%m%d')}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    _apply_arrival_date(day)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)
    if left.button("🧹 Ver todas", use_container_width=True, key="clear_arrivals_filter"):
        if "fecha_date" in st.query_params:
            del st.query_params["fecha_date"]
        st.query_params["skip_splash"] = "1"
        st.session_state.pop("arrivals_cal_msg", None)
        st.rerun()
    if right.button("Cerrar", use_container_width=True, key="close_arrivals_dialog"):
        st.rerun()


REMINDER_SLOTS = 10


def _reminder_display_date(value: object) -> str:
    parsed = parse_fecha(value)
    return parsed.strftime("%B %d, %Y") if parsed else "—"


def _reminder_input_date(value: object) -> date:
    """Convierte lo que venga de Supabase (string ISO, Timestamp, None) a `date`."""
    parsed = parse_fecha(value)
    if parsed:
        return parsed.date() if isinstance(parsed, datetime) else parsed
    return datetime.today().date()


@st.dialog("🔔 Reminders", width="large")
def reminders_dialog() -> None:
    """Popup con la lista de recordatorios (Activity / Active Date / Due Date).

    Un clic sobre la actividad la pone en modo edicion en la misma fila (sin
    tener que abrir el popup EDIT de 10 filas). Streamlit no distingue doble
    clic de clic simple, asi que un solo clic ya activa la edicion inline.
    """
    df = cargar_reminders()
    editing_id = st.session_state.get("reminder_inline_edit_id")

    st.markdown(
        "<div style='color:#8ca4ba;font-size:11px;font-weight:700;letter-spacing:1px;"
        "text-transform:uppercase;text-align:center;margin-bottom:10px;'>"
        "Avisos y restricciones vigentes · clic en la actividad para editarla</div>",
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("No hay reminders registrados todavia. Usa EDITAR para agregar el primero.")
    else:
        st.markdown(
            """
            <style>
            .reminder-row {
                display:grid;
                grid-template-columns: 2.2fr 1fr 1fr;
                gap:10px;
                padding:9px 12px;
                border:1px solid #2a2205;
                border-radius:8px;
                background:#120e02;
                margin-bottom:6px;
            }
            .reminder-row.head {
                background:transparent;
                border:none;
                color:#D97706;
                font-size:10px;
                font-weight:800;
                letter-spacing:1.2px;
                text-transform:uppercase;
                padding:0 12px;
            }
            .reminder-row .date-cell { color:#eafaff; font-size:13px; font-weight:600; }
            .st-key-reminders_list .st-key-reminder_activity_btn_container button,
            [class*="st-key-reminder_activity_btn_"] button {
                background:transparent !important;
                border:none !important;
                color:#FACC15 !important;
                font-weight:700 !important;
                font-size:13px !important;
                text-align:left !important;
                justify-content:flex-start !important;
                padding:0 !important;
                width:100% !important;
            }
            [class*="st-key-reminder_activity_btn_"] button:hover {
                color:#FFE580 !important;
                text-decoration:underline !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='reminder-row head'><div>ACTIVITY</div><div>ACTIVE DATE</div>"
            "<div>DUE DATE</div></div>",
            unsafe_allow_html=True,
        )
        with st.container(height=420, key="reminders_list"):
            for _, row in df.iterrows():
                row_id = row.get("id")
                if editing_id is not None and row_id == editing_id:
                    _reminder_inline_edit_row(row)
                    continue

                activity = str(row.get("activity", "")).strip() or "—"
                active_date = _reminder_display_date(row.get("active_date"))
                due_date = _reminder_display_date(row.get("due_date"))
                c1, c2, c3 = st.columns([2.2, 1, 1])
                with c1:
                    if st.button(
                        activity, key=f"reminder_activity_btn_{row_id}",
                        use_container_width=True,
                    ):
                        st.session_state["reminder_inline_edit_id"] = row_id
                        st.session_state["open_reminders"] = True
                        st.rerun()
                c2.markdown(f"<div class='date-cell'>{active_date}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='date-cell'>{due_date}</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    left, right = st.columns(2)
    if left.button("✏️ EDIT", use_container_width=True, key="open_reminders_edit_btn"):
        st.session_state["open_reminders_edit"] = True
        st.rerun()
    if right.button("Cerrar", use_container_width=True, key="close_reminders_dialog"):
        st.session_state.pop("reminder_inline_edit_id", None)
        st.rerun()


def _reminder_inline_edit_row(row: dict) -> None:
    """Renderiza la fila `row` en modo edicion inline dentro de reminders_dialog."""
    row_id = row.get("id")
    c1, c2, c3 = st.columns([2.2, 1, 1])
    activity = c1.text_input(
        "Activity", value=str(row.get("activity", "") or ""),
        key=f"reminder_inline_activity_{row_id}", label_visibility="collapsed",
    )
    active_date = c2.date_input(
        "Active Date", value=_reminder_input_date(row.get("active_date")),
        key=f"reminder_inline_active_{row_id}", label_visibility="collapsed",
    )
    due_date = c3.date_input(
        "Due Date", value=_reminder_input_date(row.get("due_date")),
        key=f"reminder_inline_due_{row_id}", label_visibility="collapsed",
    )
    s1, s2, s3 = st.columns(3)
    if s1.button("💾 Guardar", key=f"reminder_inline_save_{row_id}", use_container_width=True):
        activity = (activity or "").strip()
        if activity:
            actualizar_reminder(row_id, activity, active_date, due_date)
        else:
            eliminar_reminder(row_id)
        st.session_state.pop("reminder_inline_edit_id", None)
        st.session_state["open_reminders"] = True
        st.rerun()
    if s2.button("🗑️ Borrar", key=f"reminder_inline_delete_{row_id}", use_container_width=True):
        eliminar_reminder(row_id)
        st.session_state.pop("reminder_inline_edit_id", None)
        st.session_state["open_reminders"] = True
        st.rerun()
    if s3.button("Cancelar", key=f"reminder_inline_cancel_{row_id}", use_container_width=True):
        st.session_state.pop("reminder_inline_edit_id", None)
        st.session_state["open_reminders"] = True
        st.rerun()
    st.markdown("<hr style='border-color:#2a2205;margin:8px 0;'>", unsafe_allow_html=True)


@st.dialog("✏️ Editar Reminders", width="large")
def reminder_edit_dialog() -> None:
    """Formulario con hasta 10 filas para crear/editar/borrar reminders."""
    df = cargar_reminders()
    existing = df.to_dict("records") if not df.empty else []

    st.markdown(
        "<div style='color:#8ca4ba;font-size:11px;font-weight:700;letter-spacing:1px;"
        "text-transform:uppercase;text-align:center;margin-bottom:10px;'>"
        "Completa la actividad para guardar la fila · borra el texto para eliminarla</div>",
        unsafe_allow_html=True,
    )

    with st.form("reminder_edit_form"):
        slots = []
        for i in range(REMINDER_SLOTS):
            row = existing[i] if i < len(existing) else {}
            row_id = row.get("id")
            st.markdown(f"**Fila {i + 1}**")
            c1, c2, c3 = st.columns([2, 1, 1])
            activity = c1.text_input(
                "Activity", value=str(row.get("activity", "") or ""),
                key=f"rem_activity_{i}", label_visibility="collapsed",
                placeholder="Ej: La Finca restaurant cerrado",
            )
            active_date = c2.date_input(
                "Active Date", value=_reminder_input_date(row.get("active_date")),
                key=f"rem_active_{i}",
            )
            due_date = c3.date_input(
                "Due Date", value=_reminder_input_date(row.get("due_date")),
                key=f"rem_due_{i}",
            )
            slots.append((row_id, activity, active_date, due_date))

        submitted = st.form_submit_button("💾 Guardar", use_container_width=True)

    if submitted:
        for row_id, activity, active_date, due_date in slots:
            activity = (activity or "").strip()
            if activity:
                if row_id is not None:
                    actualizar_reminder(row_id, activity, active_date, due_date)
                else:
                    insertar_reminder(activity, active_date, due_date)
            elif row_id is not None:
                eliminar_reminder(row_id)
        st.session_state["open_reminders"] = True
        st.rerun()

    if st.button("Cerrar sin guardar", use_container_width=True, key="close_reminder_edit_dialog"):
        st.session_state["open_reminders"] = True
        st.rerun()


# -----------------------------------------------------------------------------
# Directorio Telefónico — popups
# -----------------------------------------------------------------------------

def _directorio_inline_edit_row(row: dict) -> None:
    """Renderiza `row` en modo edición inline dentro de directorio_dialog()."""
    row_id = row.get("id")
    c1, c2 = st.columns(2)
    colaborador = c1.text_input(
        "Colaborador", value=str(row.get("colaborador", "") or ""),
        key=f"dir_inline_colaborador_{row_id}",
    )
    departamento = c2.text_input(
        "Departamento *", value=str(row.get("departamento", "") or ""),
        key=f"dir_inline_departamento_{row_id}",
    )
    nombre_puesto = st.text_input(
        "Nombre / Puesto *", value=str(row.get("nombre_puesto", "") or ""),
        key=f"dir_inline_puesto_{row_id}",
    )
    c3, c4, c5 = st.columns(3)
    correo = c3.text_input(
        "Correo Electrónico", value=str(row.get("correo_electronico", "") or ""),
        key=f"dir_inline_correo_{row_id}",
    )
    extension = c4.text_input(
        "Extensión", value=str(row.get("extension", "") or ""),
        key=f"dir_inline_ext_{row_id}",
    )
    telefono = c5.text_input(
        "Teléfono de Contacto", value=str(row.get("telefono_contacto", "") or ""),
        key=f"dir_inline_tel_{row_id}",
    )
    s1, s2, s3 = st.columns(3)
    if s1.button("💾 Guardar", key=f"dir_inline_save_{row_id}", use_container_width=True):
        if not departamento.strip() or not nombre_puesto.strip():
            st.error("Departamento y Nombre / Puesto son obligatorios.")
        else:
            actualizar_colaborador(row_id, {
                "colaborador": colaborador.strip(),
                "departamento": departamento.strip(),
                "nombre_puesto": nombre_puesto.strip(),
                "correo_electronico": correo.strip(),
                "extension": extension.strip(),
                "telefono_contacto": telefono.strip(),
            })
            st.session_state.pop("directorio_inline_edit_id", None)
            st.session_state["open_directorio"] = True
            st.rerun()
    if s2.button("🗑️ Borrar", key=f"dir_inline_delete_{row_id}", use_container_width=True):
        eliminar_colaborador(row_id)
        st.session_state.pop("directorio_inline_edit_id", None)
        st.session_state["open_directorio"] = True
        st.rerun()
    if s3.button("Cancelar", key=f"dir_inline_cancel_{row_id}", use_container_width=True):
        st.session_state.pop("directorio_inline_edit_id", None)
        st.session_state["open_directorio"] = True
        st.rerun()
    st.markdown("<hr style='border-color:#1a1a1a;margin:8px 0;'>", unsafe_allow_html=True)


@st.dialog("📇 Directorio Telefónico", width="large")
def directorio_dialog() -> None:
    """Popup con el directorio de personal: ver, buscar, editar y agregar."""
    df = cargar_directorio()
    editing_id = st.session_state.get("directorio_inline_edit_id")

    # Ensanchar SOLO este popup. Streamlit monta el dialogo como
    # div[data-testid="stDialog"] (capa a pantalla completa) y la caja real es
    # su primer hijo: ahi va el ancho. Como los dialogs son exclusivos (solo
    # uno montado a la vez), este CSS aplica únicamente con el Directorio
    # abierto.
    st.markdown(
        """
        <style>
        div[data-testid="stDialog"] > div {
            width: 96vw !important;
            max-width: 1500px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='color:#8ca4ba;font-size:11px;font-weight:700;letter-spacing:1px;"
        "text-transform:uppercase;text-align:center;margin-bottom:10px;'>"
        "Directorio telefónico y de contactos del personal · clic en un nombre para editarlo</div>",
        unsafe_allow_html=True,
    )

    top1, top2, top3 = st.columns([2.4, 1, 1])
    search = top1.text_input(
        "Buscar", key="directorio_search", label_visibility="collapsed",
        placeholder="🔍 Buscar por nombre, departamento, puesto, correo, extensión o teléfono...",
    )
    if top2.button("➕ NUEVO", use_container_width=True, key="open_directorio_new_btn"):
        st.session_state["open_directorio_new"] = True
        st.rerun()
    if top3.button("⬆ IMPORTAR", use_container_width=True, key="open_directorio_import_btn"):
        st.session_state["open_directorio_import"] = True
        st.rerun()

    view = df
    if search and search.strip():
        text = search.strip().lower()
        view = df[df.astype(str).apply(
            lambda row: row.str.lower().str.contains(text, na=False).any(), axis=1
        )]

    count_col, export_xlsx_col, export_pdf_col = st.columns([2.6, 1, 1])
    count_col.markdown(f"<div style='color:#4a5a6a;font-size:10px;margin:4px 0 8px;'>{len(view)} de {len(df)} registros</div>", unsafe_allow_html=True)
    # Exportar EXACTAMENTE lo que se está viendo en la tabla (respeta la
    # búsqueda activa), con los encabezados "bonitos" en español.
    export_headers = {v: k for k, v in DIRECTORIO_EXCEL_HEADERS.items()}
    export_view = view[[c for c in DIRECTORIO_COLUMNS if c in view.columns]] if not view.empty else view
    export_xlsx_col.download_button(
        "⬇ EXCEL", data=exportar_excel_bytes(export_view, headers=export_headers, sheet_name="Directorio"),
        file_name="directorio_telefonico.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True, disabled=view.empty, key="directorio_export_xlsx",
    )
    export_pdf_col.download_button(
        "⬇ PDF", data=exportar_pdf_bytes(export_view, headers=export_headers, title="Directorio Telefónico - Waldorf Astoria"),
        file_name="directorio_telefonico.pdf", mime="application/pdf",
        use_container_width=True, disabled=view.empty, key="directorio_export_pdf",
    )

    if df.empty:
        st.info("No hay colaboradores registrados todavía. Usa ➕ NUEVO o ⬆ IMPORTAR para cargar el directorio.")
    elif view.empty:
        st.warning("Ningún colaborador coincide con la búsqueda.")
    else:
        st.markdown(
            """
            <style>
            /* El encabezado usa las mismas columnas que las filas (antes era
               un grid aparte y los titulos no quedaban sobre su columna). */
            .dir-head {
                color:#00e5ff; font-size:9px; font-weight:800; letter-spacing:1px;
                text-transform:uppercase; padding:4px 0 6px;
            }
            /* Celdas: el texto largo (puesto, correo, extension) se ve completo.
               Si no cabe, baja de linea; ya no se recorta con puntos suspensivos. */
            .dir-cell {
                color:#dfeff8; font-size:12px; line-height:1.35;
                overflow-wrap:anywhere; padding:2px 0;
            }
            .dir-cell.dept { color:#8ca4ba; font-size:11px; }
            [class*="st-key-dir_name_btn_"] button {
                background:transparent !important; border:none !important; color:#00e5ff !important;
                font-weight:700 !important; font-size:12px !important; text-align:left !important;
                justify-content:flex-start !important; padding:0 !important; width:100% !important;
            }
            [class*="st-key-dir_name_btn_"] button:hover { color:#7cf3ff !important; text-decoration:underline !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        head_cols = st.columns(DIRECTORIO_ROW_RATIOS)
        for head_col, titulo in zip(head_cols, DIRECTORIO_HEADERS):
            head_col.markdown(f"<div class='dir-head'>{titulo}</div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='height:1px;background:#1a1a1a;margin:0 0 4px;'></div>",
            unsafe_allow_html=True,
        )
        with st.container(height=430, key="directorio_list"):
            for _, row in view.iterrows():
                row_id = row.get("id")
                if editing_id is not None and row_id == editing_id:
                    _directorio_inline_edit_row(row)
                    continue
                c1, c2, c3, c4, c5, c6 = st.columns(DIRECTORIO_ROW_RATIOS)
                with c1:
                    if st.button(
                        str(row.get("colaborador", "") or "—"),
                        key=f"dir_name_btn_{row_id}", use_container_width=True,
                    ):
                        st.session_state["directorio_inline_edit_id"] = row_id
                        st.session_state["open_directorio"] = True
                        st.rerun()
                c2.markdown(f"<div class='dir-cell dept'>{safe_text(row.get('departamento', ''))}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='dir-cell'>{safe_text(row.get('nombre_puesto', ''))}</div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='dir-cell'>{safe_text(row.get('correo_electronico', ''))}</div>", unsafe_allow_html=True)
                c5.markdown(f"<div class='dir-cell'>{safe_text(row.get('extension', ''))}</div>", unsafe_allow_html=True)
                c6.markdown(f"<div class='dir-cell'>{safe_text(row.get('telefono_contacto', ''))}</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("Cerrar", use_container_width=True, key="close_directorio_dialog"):
        st.session_state.pop("directorio_inline_edit_id", None)
        st.rerun()


@st.dialog("➕ Nuevo Colaborador", width="large")
def directorio_new_dialog() -> None:
    """Popup para agregar un colaborador nuevo al directorio."""
    with st.form("directorio_new_form"):
        c1, c2 = st.columns(2)
        colaborador = c1.text_input("Colaborador", placeholder="Nombre del colaborador")
        departamento = c2.text_input("Departamento *", placeholder="Ej: Human Resources")
        nombre_puesto = st.text_input("Nombre / Puesto *", placeholder="Ej: HR Coordinator")
        c3, c4, c5 = st.columns(3)
        correo = c3.text_input("Correo Electrónico", placeholder="nombre.apellido@waldorfastoria.com")
        extension = c4.text_input("Extensión", placeholder="7210")
        telefono = c5.text_input("Teléfono de Contacto", placeholder="506 8888-8888")
        submitted = st.form_submit_button("💾 GUARDAR", use_container_width=True, type="primary")

    if submitted:
        if not departamento.strip() or not nombre_puesto.strip():
            st.error("Departamento y Nombre / Puesto son obligatorios.")
        else:
            insertar_colaborador({
                "colaborador": colaborador.strip(),
                "departamento": departamento.strip(),
                "nombre_puesto": nombre_puesto.strip(),
                "correo_electronico": correo.strip(),
                "extension": extension.strip(),
                "telefono_contacto": telefono.strip(),
            })
            st.success("Colaborador agregado correctamente.")
            st.session_state["open_directorio"] = True
            st.rerun()

    if st.button("Cerrar sin guardar", use_container_width=True, key="close_directorio_new_dialog"):
        st.session_state["open_directorio"] = True
        st.rerun()


@st.dialog("⬆ Importar Directorio desde Excel", width="large")
def directorio_import_dialog() -> None:
    """Popup para cargar el archivo `Directorio Telefonico.xlsx` (u otro con las
    mismas columnas) directamente a Supabase. Cada importación AGREGA filas
    nuevas; no reemplaza ni actualiza registros existentes."""
    st.markdown(
        "<div style='color:#8ca4ba;font-size:11px;margin-bottom:8px;'>"
        "Sube un archivo .xlsx con las columnas: Colaborador, Departamento, "
        "Nombre / Puesto, Correo Electrónico, Extensión, Teléfono de Contacto "
        "(o sus equivalentes en snake_case). Cada fila se agrega como un registro nuevo.</div>",
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader("Archivo Excel", type=["xlsx", "xls"], key="directorio_import_file")

    if uploaded is not None:
        try:
            raw = pd.read_excel(uploaded)
        except Exception as exc:
            st.error(f"No se pudo leer el archivo: {exc}")
            return

        # Normaliza encabezados: acepta tanto los del Excel original
        # ("Colaborador", "Nombre / Puesto", ...) como snake_case.
        rename_map = {}
        for col in raw.columns:
            key = str(col).strip()
            if key in DIRECTORIO_EXCEL_HEADERS:
                rename_map[col] = DIRECTORIO_EXCEL_HEADERS[key]
            else:
                normalized = key.strip().lower().replace(" ", "_")
                if normalized in DIRECTORIO_COLUMNS:
                    rename_map[col] = normalized
        raw = raw.rename(columns=rename_map)

        missing = [c for c in ("departamento", "nombre_puesto") if c not in raw.columns]
        if missing:
            st.error(f"Al archivo le faltan columnas obligatorias: {', '.join(missing)}.")
            return

        for column in DIRECTORIO_COLUMNS:
            if column not in raw.columns:
                raw[column] = ""

        preview = raw[DIRECTORIO_COLUMNS].copy()
        preview = preview.dropna(subset=["departamento", "nombre_puesto"], how="all")
        for column in DIRECTORIO_COLUMNS:
            preview[column] = preview[column].apply(lambda v: "" if pd.isna(v) else str(v).strip())
        preview = preview[(preview["departamento"] != "") | (preview["nombre_puesto"] != "")]

        st.markdown(f"<div style='color:#00e5ff;font-size:11px;margin:6px 0;'>{len(preview)} filas listas para importar:</div>", unsafe_allow_html=True)
        st.dataframe(preview, use_container_width=True, height=280)

        if st.button(f"⬆ IMPORTAR {len(preview)} REGISTROS", use_container_width=True, type="primary", key="confirm_directorio_import"):
            records = preview.to_dict("records")
            insertar_colaboradores_lote(records)
            st.success(f"{len(records)} colaboradores importados correctamente.")
            st.session_state["open_directorio"] = True
            st.rerun()

    if st.button("Cerrar", use_container_width=True, key="close_directorio_import_dialog"):
        st.session_state["open_directorio"] = True
        st.rerun()


@st.dialog("👥 Huéspedes", width="large")
def guests_dialog() -> None:
    """Popup: lista los nombres de huéspedes que aparecen actualmente en la
    tabla principal (respeta los filtros de fecha/checkout/búsqueda que
    estén activos en ese momento). Clic en un nombre abre su ficha de
    contacto extra (teléfono + detalles), guardada en la tabla `guests`."""
    limpiar_guests_checkout()
    df = cargar_reservaciones()
    filtered, filters = apply_filters(df)

    if filters:
        captions = []
        if "checkout" in filters:
            captions.append("Check-out: " + safe_text(filters["checkout"]))
        if "arrival" in filters:
            captions.append("Check-in: " + safe_text(filters["arrival"]))
        if "search" in filters:
            captions.append("Búsqueda: " + safe_text(filters["search"]))
        st.markdown(
            "<div style='color:#8ca4ba;font-size:11px;margin-bottom:8px;'>Mostrando huéspedes de las reservas "
            "filtradas — " + " | ".join(captions) + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color:#8ca4ba;font-size:11px;margin-bottom:8px;'>Mostrando TODOS los huéspedes "
            "(no hay filtro de fecha/checkout/búsqueda activo).</div>",
            unsafe_allow_html=True,
        )

    # Un mismo nombre puede tener varias reservas en el filtro actual; si
    # AL MENOS una ya hizo checkout, se marca con el mismo icono 🏃 que usa
    # la tabla principal.
    status_by_name: dict[str, bool] = {}
    for _, row in filtered.iterrows():
        nombre = str(row.get("name", "")).strip()
        if not nombre:
            continue
        checked_out = es_checkout_pasado(row.get("check_out"))
        status_by_name[nombre] = status_by_name.get(nombre, False) or checked_out

    names = sorted(status_by_name.keys())

    search = st.text_input(
        "Buscar", key="guests_list_search", label_visibility="collapsed",
        placeholder="🔍 Buscar por nombre...",
    )
    if search and search.strip():
        text = search.strip().lower()
        names = [n for n in names if text in n.lower()]

    st.markdown(
        f"<div style='color:#00e5ff;font-size:12px;font-weight:800;margin:6px 0 10px;'>{len(names)} huésped(es)</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        [class*="st-key-guest_name_btn_"] button {
            background:transparent !important; border:none !important; color:#dfeff8 !important;
            font-weight:600 !important; font-size:13px !important; text-align:left !important;
            justify-content:flex-start !important; padding:7px 4px !important; width:100% !important;
            border-bottom:1px solid #141414 !important; border-radius:0 !important;
        }
        [class*="st-key-guest_name_btn_"] button:hover { color:#00e5ff !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Info (columnas INFORMATION + IRD) por nombre, tomada de las reservas
    # filtradas actuales. Un mismo nombre puede tener varias reservas; se
    # juntan las combinaciones únicas.
    info_by_name: dict[str, str] = {}
    for _, row in filtered.iterrows():
        nombre = str(row.get("name", "")).strip()
        if not nombre:
            continue
        info_txt = str(row.get("info", "") or "").strip()
        ird_txt = str(row.get("ird", "") or "").strip()
        combo = " | ".join(part for part in [info_txt, ird_txt] if part)
        if not combo:
            continue
        existentes = info_by_name.setdefault(nombre, "")
        if combo not in existentes:
            info_by_name[nombre] = (existentes + " || " + combo).strip(" |") if existentes else combo

    info_abiertos: set[str] = st.session_state.setdefault("guests_info_open", set())

    st.markdown(
        """
        <style>
        [class*="st-key-guest_info_btn_"] button {
            background:#1a2733 !important; border:1px solid #00e5ff55 !important; color:#00e5ff !important;
            padding:2px 0 !important; font-size:13px !important; min-height:34px !important;
        }
        [class*="st-key-guest_info_btn_"] button:hover { background:#00e5ff !important; color:#04070d !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not names:
        st.info("No hay huéspedes para mostrar con el filtro actual.")
    else:
        with st.container(height=430, key="guests_list_container"):
            for idx, name in enumerate(names):
                label = f"{name}  🏃" if status_by_name.get(name) else name
                col_name, col_info = st.columns([8, 1])
                with col_name:
                    if st.button(label, key=f"guest_name_btn_{idx}", use_container_width=True):
                        st.session_state["guests_selected_name"] = name
                        st.session_state["guest_detail_edit_mode"] = False
                        st.session_state["open_guests_detail"] = True
                        st.rerun()
                with col_info:
                    if info_by_name.get(name) and st.button("ℹ️", key=f"guest_info_btn_{idx}", use_container_width=True):
                        if name in info_abiertos:
                            info_abiertos.discard(name)
                        else:
                            info_abiertos.add(name)
                        st.session_state["guests_info_open"] = info_abiertos

                if name in info_abiertos and info_by_name.get(name):
                    st.markdown(
                        f"<div style='background:#0a0a0a;border:1px solid #00e5ff55;border-radius:6px;"
                        f"padding:10px 12px;margin:2px 0 8px;color:#dfeff8;font-size:12.5px;font-weight:700;"
                        f"white-space:pre-wrap;'>{safe_text(info_by_name[name])}</div>",
                        unsafe_allow_html=True,
                    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("Cerrar", use_container_width=True, key="close_guests_dialog"):
        st.session_state["guests_info_open"] = set()
        st.rerun()


@st.dialog("📇 Ficha de Huésped", width="large")
def guests_detail_dialog() -> None:
    """Popup con los datos extra (teléfono + detalles) de un huésped puntual,
    guardados en la tabla `guests` de Supabase, ligados por nombre a la fila
    correspondiente de la tabla principal."""
    name = st.session_state.get("guests_selected_name", "")
    guests_df = cargar_guests()
    existing = buscar_guest_por_nombre(name, guests_df)

    st.markdown(
        f"<div style='color:#00e5ff;font-size:16px;font-weight:800;margin-bottom:14px;'>{safe_text(name)}</div>",
        unsafe_allow_html=True,
    )

    telefono = st.text_input(
        "Teléfono",
        value=str(existing.get("telefono", "") or "") if existing else "",
        placeholder="Ej: 506 8888-8888",
        key="guest_detail_telefono",
    )
    detalles = st.text_area(
        "Detalles",
        value=str(existing.get("detalles", "") or "") if existing else "",
        placeholder="Preferencias, notas, alergias, ocasiones especiales, etc.",
        height=180,
        key="guest_detail_detalles",
    )

    c1, c2, c3 = st.columns(3)
    if c1.button("🗑 ELIMINAR", use_container_width=True, disabled=existing is None, key="guest_detail_delete"):
        eliminar_guest(existing["id"])
        st.success("Registro eliminado.")
        st.session_state["open_guests"] = True
        st.rerun()

    if c2.button("💾 GUARDAR", use_container_width=True, type="primary", key="guest_detail_save"):
        data = {"nombre": name.strip(), "telefono": telefono.strip(), "detalles": detalles.strip()}
        if existing is not None:
            actualizar_guest(existing["id"], data)
        else:
            insertar_guest(data)
        st.success("Guardado correctamente.")
        st.session_state["open_guests_detail"] = True
        st.rerun()

    if c3.button("CERRAR", use_container_width=True, key="guest_detail_close"):
        st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    if st.button("« Volver a la lista de huéspedes", use_container_width=True, key="guest_detail_back_to_list"):
        st.session_state["open_guests"] = True
        st.rerun()


@st.dialog("📌 Pending", width="large")
def pending_dialog() -> None:
    """Popup: block de notas con 15 líneas numeradas, guardadas en la
    tabla `block_notas` de Supabase. Cada línea se puede editar y borrar
    (de la base de datos) por separado."""
    data = cargar_pending()
    if "pending_nonce" not in st.session_state:
        st.session_state["pending_nonce"] = 0
    nonce = st.session_state["pending_nonce"]

    st.markdown(
        """
        <style>
        [class*="st-key-pending_del_"] button {
            background:#3a1a1a !important; border:1px solid #E11D48 !important; color:#ff6b81 !important;
            padding:2px 0 !important; font-size:13px !important; min-height:38px !important;
        }
        [class*="st-key-pending_del_"] button:hover { background:#E11D48 !important; color:#fff !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    for numero in range(1, PENDING_LINES + 1):
        valor_actual = data.get(numero, {}).get("contenido", "")
        col_num, col_text, col_del = st.columns([0.5, 5, 0.6])
        with col_num:
            st.markdown(
                f"<div style='color:#00e5ff;font-weight:800;font-size:13px;margin-top:10px;text-align:right;'>{numero}.</div>",
                unsafe_allow_html=True,
            )
        with col_text:
            st.text_input(
                f"linea_{numero}", value=valor_actual, key=f"pending_line_{numero}_{nonce}",
                label_visibility="collapsed", placeholder="Escribe aquí...",
            )
        with col_del:
            if st.button("🗑", key=f"pending_del_{numero}", use_container_width=True):
                try:
                    eliminar_pending_linea(numero)
                    st.session_state.pop(f"pending_line_{numero}_{nonce}", None)
                    st.session_state["pending_nonce"] = nonce + 1
                    st.success(f"Línea {numero} borrada.")
                except Exception as exc:
                    st.error(f"No se pudo borrar la línea {numero}: {exc}")
                st.session_state["open_pending"] = True
                st.rerun()

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if st.session_state.get("pending_confirm_delete_all"):
        st.warning("Se borrarán permanentemente las 15 líneas del Pending. Ingresa la clave de autorización para confirmar.")
        with st.form("pending_delete_all_form"):
            pending_password = st.text_input("Clave de autorización", type="password", key="pending_delete_all_password")
            fc1, fc2 = st.columns(2)
            confirmar = fc1.form_submit_button("CONFIRMAR Y BORRAR", type="primary", use_container_width=True)
            cancelar = fc2.form_submit_button("Cancelar", use_container_width=True)
        if confirmar:
            expected_password = st.secrets.get("DELETE_PASSWORD", "")
            if not expected_password:
                st.error("Configura `DELETE_PASSWORD` en los Secrets antes de habilitar el borrado.")
            elif pending_password != expected_password:
                st.error("Clave incorrecta.")
            else:
                try:
                    eliminar_pending_todo()
                    for numero in range(1, PENDING_LINES + 1):
                        st.session_state.pop(f"pending_line_{numero}_{nonce}", None)
                    st.session_state["pending_nonce"] = nonce + 1
                    st.session_state.pop("pending_confirm_delete_all", None)
                    st.success("Pending vaciado.")
                except Exception as exc:
                    st.error(f"No se pudo vaciar: {exc}")
                st.session_state["open_pending"] = True
                st.rerun()
        if cancelar:
            st.session_state.pop("pending_confirm_delete_all", None)
            st.session_state["open_pending"] = True
            st.rerun()
    else:
        c1, c2, c3 = st.columns(3)
        if c1.button("💾 GUARDAR TODO", use_container_width=True, type="primary", key="pending_save_all"):
            try:
                for numero in range(1, PENDING_LINES + 1):
                    texto = st.session_state.get(f"pending_line_{numero}_{nonce}", "")
                    guardar_pending_linea(numero, texto)
                st.session_state["pending_nonce"] = nonce + 1
                st.success("Pending guardado correctamente.")
            except Exception as exc:
                st.error(f"No se pudo guardar: {exc}")
            st.session_state["open_pending"] = True
            st.rerun()
        if c2.button("🗑 BORRAR TODO", use_container_width=True, key="pending_delete_all"):
            st.session_state["pending_confirm_delete_all"] = True
            st.session_state["open_pending"] = True
            st.rerun()
        if c3.button("CERRAR", use_container_width=True, key="pending_close"):
            st.rerun()


def render_calculator() -> None:
    """Vista legacy de calculadora (redirige al dialog)."""
    st.subheader("Calculadora")
    render_back_link()
    calculator_dialog()


def _letter_body(reservation: dict) -> None:
    """Genera la carta de despedida; reutilizable en pagina o en popup."""
    guest_name = str(reservation.get("name", "")).strip()
    if not guest_name:
        st.error("La reserva seleccionada no tiene un nombre de huesped.")
        return

    # Buscar la plantilla en varios nombres posibles
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_names = ["plantilla_despedida.docx", "plantilla_despedida(1).docx"]
    template_path = None
    for name in possible_names:
        path = os.path.join(base_dir, name)
        if os.path.exists(path):
            template_path = path
            break

    if not template_path:
        st.error("No se encontro la plantilla Word.")
        st.info(
            "Asegurate de subir `plantilla_despedida.docx` a tu repositorio de GitHub "
            "en la misma carpeta que `concierge_master_app.py`."
        )
        return

    try:
        from docx import Document
    except ImportError:
        st.error("Falta `python-docx`. Instalalo con el archivo requirements_streamlit.txt actualizado.")
        return

    try:
        document = Document(template_path)
        replacements = 0

        def replace_paragraph(paragraph) -> None:
            nonlocal replacements
            if "{{NAME}}" not in paragraph.text:
                return
            text = paragraph.text.replace("{{NAME}}", guest_name)
            for run in paragraph.runs:
                run.text = ""
            if paragraph.runs:
                paragraph.runs[0].text = text
            else:
                paragraph.add_run(text)
            replacements += 1

        for paragraph in document.paragraphs:
            replace_paragraph(paragraph)
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        replace_paragraph(paragraph)

        output = BytesIO()
        document.save(output)
        output.seek(0)
        safe_name = "".join(char if char.isalnum() or char in "_-" else "_" for char in guest_name)
        st.success(f"Carta preparada para {guest_name}. Placeholders sustituidos: {replacements}.")
        st.download_button(
            "DESCARGAR CARTA DE DESPEDIDA",
            data=output,
            file_name=f"Carta_Despedida_{safe_name}_{datetime.now():%Y%m%d_%H%M}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"No se pudo generar la carta: {exc}")


@st.dialog("💌 Carta de Despedida", width="small")
def letter_dialog() -> None:
    """Popup flotante con la carta de despedida lista para descargar."""
    reservation = get_selected_reservation(cargar_reservaciones())
    if not reservation:
        st.error("Selecciona una reserva de la tabla antes de crear la carta.")
    else:
        st.markdown(
            '<div style="color:#D4AF37;font:800 12px/1.2 \'Segoe UI\',sans-serif;letter-spacing:1.4px;'
            'text-transform:uppercase;margin-bottom:10px;">'
            f'{safe_text(reservation.get("name", ""))} &nbsp;·&nbsp; Room {safe_text(reservation.get("room", "—"))}</div>',
            unsafe_allow_html=True,
        )
        _letter_body(reservation)

    if st.button("Cerrar", use_container_width=True, key="close_letter_dialog"):
        st.rerun()


def render_letter() -> None:
    """Vista legacy en pagina completa (se conserva por compatibilidad)."""
    st.subheader("Carta de despedida")
    render_back_link()
    reservation = get_selected_reservation(cargar_reservaciones())
    if not reservation:
        st.error("Selecciona una reserva de la tabla antes de crear la carta.")
        return
    _letter_body(reservation)


# -----------------------------------------------------------------------------
# Bonus / Aguinaldo
# -----------------------------------------------------------------------------

def render_bonus() -> None:
    st.subheader("Registro Mensual de Valores")
    render_back_link()

    # -------------------------------------------------------------------------
    # Autenticación de acceso a la sección BONUS
    # -------------------------------------------------------------------------
    if not st.session_state.get("bonus_authenticated", False):
        st.markdown(
            """
            <style>
            .bonus-login-box {
                background: #0a0a0a;
                border: 1px solid #1a1a1a;
                border-radius: 12px;
                padding: 28px 24px;
                max-width: 420px;
                margin: 40px auto;
                text-align: center;
            }
            .bonus-login-box h3 {
                color: #D4AF37;
                font-size: 16px;
                letter-spacing: 1.5px;
                margin-bottom: 18px;
            }
            .bonus-login-box p {
                color: #8ca4ba;
                font-size: 12px;
                margin-bottom: 20px;
            }
            </style>
            <div class="bonus-login-box">
                <h3>🔒 ACCESO RESTRINGIDO</h3>
                <p>Esta sección requiere autorización.<br>Ingresa la clave de administrador para continuar.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("bonus_login_form", clear_on_submit=True):
            login_pwd = st.text_input(
                "Clave de acceso",
                type="password",
                placeholder="Ingresa la clave de admin",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("INGRESAR", type="primary", use_container_width=True)
            if submitted:
                expected = st.secrets.get("DELETE_PASSWORD", "")
                if not expected:
                    st.error("Configura DELETE_PASSWORD en los Secrets de Streamlit.")
                elif login_pwd != expected:
                    st.error("Clave incorrecta. Acceso denegado.")
                else:
                    st.session_state["bonus_authenticated"] = True
                    st.rerun()
        return

    # Si llegó aquí, está autenticado
    logout_col, _ = st.columns([1, 4])
    with logout_col:
        if st.button("🔒 CERRAR SESIÓN", use_container_width=True):
            st.session_state["bonus_authenticated"] = False
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    year = st.selectbox("Año", options=list(range(2024, 2030)), index=list(range(2024, 2030)).index(datetime.now().year), key="bonus_year_select")

    # Cargar desde Supabase (o session_state como cache local)
    cache_key = f"bonus_loaded_{year}"
    if cache_key not in st.session_state:
        st.session_state[f"bonus_{year}"] = cargar_bonus(year)
        st.session_state[cache_key] = True

    data = st.session_state[f"bonus_{year}"]
    months = [
        "DECEMBER", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY",
        "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER"
    ]

    st.markdown(
        """
        <style>
        .bonus-month { background:#0a0a0a; border:1px solid #1a1a1a; border-radius:10px; padding:12px; }
        .bonus-month h4 { color:#D4AF37; font-size:11px; text-align:center; margin:0 0 8px; letter-spacing:1px; }
        .bonus-input { width:100%; background:#0d0d0d; border:1px solid #222222; color:#effaff;
                       border-radius:6px; padding:6px 8px; font-size:13px; margin-bottom:6px; }
        .bonus-input:focus { border-color:#00e5ff; outline:none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    total_sum = 0.0
    cols = st.columns(6)
    for idx, month_name in enumerate(months):
        c = cols[idx % 6]
        with c:
            st.markdown(f'<div class="bonus-month"><h4>{month_name} {year}</h4>', unsafe_allow_html=True)
            v1 = st.text_input(f"M{idx}_1", value=str(data[idx][0]), label_visibility="collapsed", key=f"b_{year}_{idx}_1")
            v2 = st.text_input(f"M{idx}_2", value=str(data[idx][1]), label_visibility="collapsed", key=f"b_{year}_{idx}_2")
            st.markdown('</div>', unsafe_allow_html=True)
            for v in (v1, v2):
                try:
                    total_sum += float(v.replace(",", "").replace("$", "").strip()) if v.strip() else 0
                except ValueError:
                    pass
            data[idx] = [v1, v2]

    aguinaldo = total_sum / 12.0 if total_sum > 0 else 0.0

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([2, 1.2, 1.2, 1.5, 1.5])
    with c1:
        user_name = st.secrets.get("USER_NAME", "CONCIERGE")
        st.markdown(f'<div style="color:#8ca4ba;font-size:11px">USERNAME: <span style="color:#fff;font-weight:700">{user_name}</span></div>', unsafe_allow_html=True)
    with c2:
        if st.button("GUARDAR", type="primary", use_container_width=True):
            guardar_bonus(year, data)
            st.session_state[f"bonus_{year}"] = data
            st.success("✅ Datos guardados en Supabase correctamente.")
    with c3:
        if st.button("BORRAR", use_container_width=True):
            borrar_bonus(year)
            st.session_state[f"bonus_{year}"] = {m: ["", ""] for m in range(12)}
            st.success("🗑️ Todos los datos del año fueron eliminados de Supabase.")
            st.rerun()
    with c4:
        st.markdown(f'<div style="background:#D4AF37;color:#1C1300;padding:8px 12px;border-radius:8px;text-align:center;font-weight:800;font-size:12px">TOTAL SUM<br><span style="font-size:16px">{total_sum:,.2f}</span></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div style="background:#4ADE80;color:#0a0a0a;padding:8px 12px;border-radius:8px;text-align:center;font-weight:800;font-size:12px">AGUINALDO<br><span style="font-size:16px">{aguinaldo:,.2f}</span></div>', unsafe_allow_html=True)


def _delete_form(reservation: dict, context: str = "page") -> None:
    """Confirmacion de borrado, reutilizable en pagina o en popup."""
    st.warning(f"Se eliminará permanentemente la reserva de {reservation.get('name', 'este huésped')}.")
    with st.form(f"delete_reservation_{context}"):
        password = st.text_input("Clave de autorización", type="password")
        confirmed = st.form_submit_button("CONFIRMAR Y BORRAR", type="primary", use_container_width=True)
    if confirmed:
        expected_password = st.secrets.get("DELETE_PASSWORD", "")
        if not expected_password:
            st.error("Configura `DELETE_PASSWORD` en los Secrets antes de habilitar el borrado.")
        elif password != expected_password:
            st.error("Clave incorrecta.")
        else:
            eliminar_reserva(reservation["id"])
            st.success("Reserva eliminada correctamente.")
            clear_page()


@st.dialog("🗑️ Eliminar Reservación", width="small")
def delete_reservation_dialog() -> None:
    """Popup flotante de borrado sobre el dashboard."""
    reservation = get_selected_reservation(cargar_reservaciones())
    if not reservation:
        st.error("Selecciona una reserva antes de solicitar el borrado.")
    else:
        st.markdown(
            '<div style="color:#ff6b6b;font:800 12px/1.2 \'Segoe UI\',sans-serif;letter-spacing:1.4px;'
            'text-transform:uppercase;margin-bottom:10px;">'
            f'{safe_text(reservation.get("name", ""))} &nbsp;·&nbsp; Room {safe_text(reservation.get("room", "—"))}</div>',
            unsafe_allow_html=True,
        )
        _delete_form(reservation, "dialog")

    if st.button("Cancelar", use_container_width=True, key="close_delete_dialog"):
        st.rerun()


def render_delete() -> None:
    """Vista legacy en pagina completa (se conserva por compatibilidad)."""
    st.subheader("Eliminar reservación")
    render_back_link()
    reservation = get_selected_reservation(cargar_reservaciones())
    if not reservation:
        st.error("Selecciona una reserva antes de solicitar el borrado.")
        return
    _delete_form(reservation, "page")


# -----------------------------------------------------------------------------
# Tabla AG Grid
# -----------------------------------------------------------------------------

CATEGORY_CELL_STYLE = JsCode(
    """
function(params) {
  const val = String(params.value || '');
  if (!val || val === 'nan' || val === 'None' || val === 'null') return null;
  const info = String((params.data && params.data.info) || '').toUpperCase();
  const ird = String((params.data && params.data.ird) || '').toUpperCase();
  const trans = String((params.data && params.data.trans) || '').toUpperCase();
  const combined = info + " " + ird + " " + trans;
  const cats = [
    ['VIP', '#00E5FF'],
    ['BIRTHDAY', '#FF5252'],
    ['HONEYMOON', '#FF9800'],
    ['BABYMOON', '#A78BFA'],
    ['ANNIVERSARY', '#4ADE80'],
    ['RELAXURY', '#F472B6'],
    ['TEAM MEMBER', '#FACC15'],
    ['LEISURE', '#22D3EE']
  ];
  for (const [keyword, color] of cats) {
    if (combined.includes(keyword)) {
      return { color: color, fontWeight: '800' };
    }
  }
  return null;
}
"""
)

TRANS_CELL_STYLE = JsCode(
    """
function(params) {
  const val = String(params.value || '');
  if (!val || val === 'nan' || val === 'None' || val === 'null') return null;
  if (val.toUpperCase().includes('RELAXURY')) {
    return { color: '#F472B6', fontWeight: '700' };
  }
  return null;
}
"""
)

ROW_STYLE = JsCode(
    """
function(params) {
  if (params.node && params.node.selected) {
    var bg = (params.rowIndex % 2 === 0) ? '#050505' : '#0e1723';
    return {
      backgroundColor: bg,
      borderTop: '1px solid #00E5FF',
      borderBottom: '1px solid #00E5FF'
    };
  }
  if (String((params.data && params.data.info) || '').toUpperCase().includes('VIP')) {
    return { backgroundColor: '#0a1a1a', borderLeft: '3px solid #00E5FF' };
  }
  return null;
}
"""
)

ROW_CLASS_RULES = JsCode(
    """
function(params) {
  return {
    'selected-transparent': params.node && params.node.selected,
    'vip-row': String((params.data && params.data.info) || '').toUpperCase().includes('VIP')
  };
}
"""
)

QTY_RENDERER = JsCode(
    """
function(params) {
  var val = String(params.value || '');
  if (!val || val === '0') {
    if (params.eGridCell) params.eGridCell.innerHTML = '';
    return null;
  }
  var parts = val.split('+');
  if (parts.length === 1) {
    if (params.eGridCell) params.eGridCell.innerHTML = '<span style="color:#e6f3fb;font-weight:700;font-size:12px;">' + val + '</span>';
  } else {
    if (params.eGridCell) params.eGridCell.innerHTML = '<span style="color:#e6f3fb;font-weight:700;font-size:12px;">' + parts[0] + '</span><span style="color:#00e5ff;font-weight:800;font-size:12px;">+' + parts[1] + '</span>';
  }
  return null;
}
"""
)

NAVIGATE_JS = JsCode(
    """
function(params) {
  var nextCell = params.nextCellPosition;
  if (nextCell) {
    var rowNode = params.api.getDisplayedRowAtIndex(nextCell.rowIndex);
    if (rowNode) {
      rowNode.setSelected(true, true);
    }
  }
  return nextCell;
}
"""
)

GRID_CSS = {
    ".ag-root-wrapper": {
        "--ag-selected-row-background-color": "transparent !important",
        "--ag-range-selection-background-color": "transparent !important",
        "--ag-row-hover-color": "#111111 !important",
        "border": "1px solid #1a1a1a !important",
        "border-radius": "10px !important",
        "overflow": "hidden !important",
        "background-color": "#050505 !important",
    },
    ".ag-header": {
        "background-color": "#000000 !important",
        "border-bottom": "1px solid #1a1a1a !important",
    },
    ".ag-header-cell": {"border-right": "none !important"},
    ".ag-header-cell-label": {"color": "#00E5FF !important", "font-weight": "900 !important", "letter-spacing": ".25px"},
    ".ag-header-cell-text": {"color": "#00E5FF !important"},
    ".ag-row": {"background-color": "#050505 !important", "border-bottom": "none !important"},
    ".ag-row-odd": {"background-color": "#0e1723 !important"},
    ".ag-cell": {"border-right": "none !important", "border-bottom": "none !important", "color": "#e6f3fb", "font-size": "12px"},
    ".ag-cell-focus": {"border": "none !important", "outline": "none !important", "box-shadow": "none !important"},
    ".ag-row-hover": {"background": "#111111 !important"},
    ".vip-row": {"background-color": "#0a1a1a !important", "border-left": "3px solid #00E5FF !important"},
    ".ag-row-selected": {"background-color": "#050505 !important", "border-top": "1px solid #00E5FF !important", "border-bottom": "1px solid #00E5FF !important"},
    ".ag-row-selected.ag-row-odd": {"background-color": "#0e1723 !important", "border-top": "1px solid #00E5FF !important", "border-bottom": "1px solid #00E5FF !important"},
    ".ag-row-selected .ag-cell": {"color": "#e6f3fb !important", "font-weight": "800 !important"},
    ".selected-transparent": {"background-color": "transparent !important", "background": "transparent !important", "border-top": "1px solid #00E5FF !important", "border-bottom": "1px solid #00E5FF !important"},
    ".selected-transparent .ag-cell": {"color": "#e6f3fb !important", "font-weight": "800 !important"},

    ".ag-paging-panel": {"border-top": "none !important", "background-color": "#050505 !important", "color": "#cceaf6 !important"},
    ".ag-header-icon": {"display": "none !important"},
}


def format_qty(value) -> str:
    """Convierte 2.1 → '2+1', 3.0 → '3', 4.2 → '4+2' para mostrar en tabla."""
    if value is None or pd.isna(value):
        return ""
    try:
        x = float(value)
        if x == 0:
            return ""
        adultos = int(x)
        ninos = round((x - adultos) * 10)
        if ninos <= 0:
            return str(adultos)
        return f"{adultos}+{ninos}"
    except (ValueError, TypeError):
        return str(value)


def format_integerish(value) -> str:
    """Quita .0 de valores numéricos sin fallar con datos vacíos o inválidos."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    text = str(value).strip()
    if text.lower() in ("", "nan", "none", "null", "nat"):
        return ""

    try:
        number = float(text)
    except (ValueError, TypeError, OverflowError):
        return text

    if not math.isfinite(number):
        return text
    return str(int(number)) if number.is_integer() else text


def render_reservations_grid(df: pd.DataFrame) -> None:
    visible = df[[column for column in DISPLAY_COLUMNS if column in df.columns]].copy()

    # Reemplazar NaN/None por cadena vacia en columnas de texto
    for col in visible.columns:
        if col not in ("qty",):
            visible[col] = visible[col].apply(lambda x: "" if pd.isna(x) or str(x).lower() in ("nan", "none", "null") else str(x))

    # Mostrar CHECK IN / CHECK OUT en formato corto ("Sep 14, 2026") solo en
    # esta tabla. Lo guardado en Supabase y lo usado por los filtros sigue
    # en formato largo ("September 14, 2026") — ver `formatear_fecha_corta`.
    if "check_in" in visible.columns:
        visible["check_in"] = visible["check_in"].apply(formatear_fecha_corta)

    # Agregar icono de checkout (🏃) solo para reservas que YA hicieron checkout
    if "check_out" in visible.columns:
        def _checkout_with_icon(val):
            if not val or pd.isna(val):
                return val
            val_str = str(val).strip()
            # Quitar todo despues del año (4 digitos) — elimina emojis/iconos guardados
            cleaned = re.sub(r"(\d{4})\s*[^\d]*$", r"\1", val_str).strip()
            corta = formatear_fecha_corta(cleaned)
            if es_checkout_pasado(cleaned):
                return corta + " 🏃"
            return corta
        visible["check_out"] = visible["check_out"].apply(_checkout_with_icon)

    # Formatear QTY como "2+1" en vez de "2.1"
    if "qty" in visible.columns:
        visible["qty"] = visible["qty"].apply(format_qty)

    # Quitar .0 en ROOM y NOCHES. ROOM usa `normalizar_room` (en vez de
    # `format_integerish`) para no perder habitaciones con cero a la
    # izquierda: 0821 se mostraba como 821 al convertirlo a número.
    if "nights" in visible.columns:
        visible["nights"] = visible["nights"].apply(format_integerish)
    if "room" in visible.columns:
        visible["room"] = visible["room"].apply(normalizar_room)

    # RATE: mostrar siempre el símbolo $ en la tabla principal, aunque el
    # valor guardado no lo traiga (reservas viejas o cargadas a mano).
    if "rate" in visible.columns:
        visible["rate"] = visible["rate"].apply(normalizar_rate)

    builder = GridOptionsBuilder.from_dataframe(visible)
    # Solo CHECK IN tiene filtro; el resto no
    builder.configure_default_column(resizable=True, sortable=True, filter=False, minWidth=80)
    builder.configure_selection(selection_mode="single", use_checkbox=False)
    builder.configure_grid_options(
        getRowStyle=ROW_STYLE,
        rowClassRules=ROW_CLASS_RULES,
        rowHeight=34,
        headerHeight=37,
        suppressCellFocus=False,
        suppressRowHoverHighlight=True,
        animateRows=True,
        navigateToNextCell=NAVIGATE_JS,
    )

    fields = {
        # CHECK IN / CHECK OUT ahora se muestran cortos ("Sep 14, 2026"), así
        # que se les reduce el ancho y ese espacio se reparte entre ETA,
        # NAME, RESERVATION, PHONE, RATE y TRANS para que se lean mejor.
        "eta":      ("ETA",          175),
        "name":     ("NAME",         190),
        "qty":      ("QTY",          60),
        "room":     ("ROOM",         70),
        "check_in": ("CHECK IN",     130),
        "check_out":("CHECK OUT",    175),
        "nights":   ("🌙",            60),
        "res_number":("RESERVATION", 220),
        "phone":    ("PHONE",        220),
        "email":    ("EMAIL",        130),
        "info":     ("INFORMATION",  220),
        "ird":      ("IRD",          160),
        "hsk":      ("HSK",          110),
        "rate":     ("RATE",         100),
        "trans":    ("TRANS",        210),
    }
    for field, (header, width) in fields.items():
        if field not in visible.columns:
            continue
        config: dict = {"header_name": header, "width": width}
        if field in {"info", "ird"}:
            config["cellStyle"] = CATEGORY_CELL_STYLE
        if field == "trans":
            config["cellStyle"] = TRANS_CELL_STYLE
        if field == "nights":
            config["type"] = ["numericColumn"]
        if field == "qty":
            config["cellRenderer"] = QTY_RENDERER
        if field == "eta":
            # Ancho ampliado (140 -> 175) porque valores como "11:00 AM" se
            # veían cortados ("11:00 ..."); además se fuerza overflow visible
            # y sin recorte por si el ancho de columna se reduce en pantallas
            # chicas.
            config["cellStyle"] = JsCode(
                "function(params){ return { color: '#D4AF37', fontWeight: '700', "
                "overflow: 'visible', textOverflow: 'unset', whiteSpace: 'nowrap' }; }"
            )
        if field == "check_out":
            # Mismo problema que ETA: el icono de checkout "🏃" quedaba
            # recortado por el ancho fijo de la columna en algunas filas (el
            # texto + icono no calzaba en 150px) y por eso parecía aparecer
            # "a veces sí, a veces no", cuando en realidad se agregaba siempre
            # que el checkout ya pasó — solo que el recorte lo escondía.
            # Ancho ampliado (150 -> 175) y overflow forzado a visible.
            config["cellStyle"] = JsCode(
                "function(params){ return { overflow: 'visible', textOverflow: 'unset', "
                "whiteSpace: 'nowrap' }; }"
            )
        # Solo CHECK IN tiene filtro habilitado
        if field == "check_in":
            config["filter"] = True
        builder.configure_column(field, **config)

    # CORRECCIÓN (tabla en blanco tras Guardar Cambios / Borrar): el `key` de
    # AgGrid incluye ahora `grid_version`, que se incrementa en cada escritura
    # a Supabase (ver `bump_grid_version`). Esto obliga a Streamlit a destruir
    # y volver a montar el iframe del grid en el siguiente rerun, en vez de
    # reutilizar la instancia vieja (que quedaba en blanco porque su fila
    # seleccionada ya no calzaba con los datos actualizados). Antes solo una
    # recarga real de página (el link "APLICAR FECHA") lograba este mismo
    # efecto; ahora ocurre automáticamente tras cada Guardar/Borrar.
    grid_key = f"concierge_reservations_grid_{st.session_state.get('grid_version', 0)}"
    response = AgGrid(
        visible,
        gridOptions=builder.build(),
        custom_css=GRID_CSS,
        theme="alpine",
        height=625,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        key=grid_key,
    )

    selected = response.get("selected_rows", [])
    if isinstance(selected, pd.DataFrame):
        selected = selected.to_dict("records")
    if selected:
        selected_id = selected[0].get("id")
        # AgGrid recibe una vista sin `id`; la buscamos con una combinación estable de datos.
        # CORRECCIÓN: la columna check_in que ve AgGrid ahora está en formato
        # corto ("Sep 14, 2026"), pero `df["check_in"]` sigue en formato largo
        # ("September 14, 2026") — comparar como texto crudo ya nunca calzaba
        # y la selección se perdía (no aparecía el banner EDITAR/CARTA/BORRAR).
        # Se parsea ambos lados a fecha real antes de comparar.
        selected_checkin = parse_fecha(selected[0].get("check_in", ""))
        candidate = df[
            (df["name"].astype(str) == str(selected[0].get("name", "")))
            & (df["res_number"].astype(str) == str(selected[0].get("res_number", "")))
            & (df["check_in"].map(parse_fecha) == selected_checkin)
        ]
        if not candidate.empty:
            row = candidate.iloc[0].to_dict()
            if st.session_state.get("selected_reservation_id") != row.get("id"):
                st.session_state["selected_reservation"] = row
                st.session_state["selected_reservation_id"] = row.get("id")
                st.query_params["sel_id"] = str(row.get("id"))
                st.rerun()


# -----------------------------------------------------------------------------
# Detección de posibles VIP (criterios de tarifa + palabras clave en INFO)
# -----------------------------------------------------------------------------

def _extraer_numeros_rate(rate_value: object) -> list[float]:
    """Extrae todos los números presentes en el campo `rate` (texto libre).

    Soporta formatos como "$250", "1,800", "1000-1700", "USD 900 por noche".
    """
    text = "" if rate_value is None or pd.isna(rate_value) else str(rate_value)
    raw_numbers = re.findall(r"[\d,]+(?:\.\d+)?", text)
    numbers = []
    for raw in raw_numbers:
        cleaned = raw.replace(",", "")
        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue
    return numbers


def _rate_representativo(rate_value: object) -> float | None:
    """Devuelve un único valor numérico representativo de `rate` para comparar
    contra los rangos de tarifa de cada nivel VIP.

    Si el campo trae un rango ("1000-1700"), se usa el promedio; si trae un
    solo número, se usa tal cual.
    """
    numbers = _extraer_numeros_rate(rate_value)
    if not numbers:
        return None
    if len(numbers) == 1:
        return numbers[0]
    return sum(numbers[:2]) / 2


# (nivel, etiqueta, color) — nivel 1 es el más alto/exclusivo.
VIP_LEVELS = {
    1: ("VIP 1", "#FFFFFF"),
    2: ("VIP 2", "#00E5FF"),
    3: ("VIP 3", "#4ADE80"),
    4: ("VIP 4", "#FACC15"),
    5: ("VIP 5", "#F472B6"),
}

# Palabras/frases clave por nivel. Se revisan en orden de especificidad para
# que "DIAMOND RESERVE" y "LIFETIME DIAMOND" no caigan también en el genérico
# "DIAMOND" del nivel 4.
_VIP_KEYWORDS: list[tuple[int, str, tuple[str, ...]]] = [
    (1, "Owner", ("OWNER",)),
    (1, "Inspirato", ("INSPIRATO",)),
    (1, "Centurion", ("CENTURION",)),
    (2, "Diamond Reserve", ("DIAMOND RESERVE",)),
    (3, "Lifetime Diamond", ("LIFETIME DIAMOND",)),
    (3, "Amigo de dueño", ("OWNER'S FRIEND", "OWNERS FRIEND", "FRIEND OF OWNER", "AMIGO DEL DUEÑO", "AMIGO DE DUENO")),
    (3, "Welcome back", ("WELCOME BACK",)),
    (3, "Influencer / celebridad", ("INFLUENCER", "CELEBRITY", "SOCIAL MEDIA")),
    (4, "Diamond", ("DIAMOND",)),
    (4, "Solicitud de agencia de viajes", ("TRAVEL AGENT", "AGENCIA DE VIAJES", "TRAVEL AGENCY")),
    (5, "Gold client", ("GOLD",)),
    (5, "Forbes / Auditor / Amex", ("FORBES", "AUDITOR", "AMERICAN EXPRESS", "AMEX")),
    # Marca manual genérica: si alguien escribió "VIP" a mano en INFORMATION
    # sin que calce con ninguno de los criterios formales de arriba, igual
    # se debe listar como candidato (nivel 5 = el más bajo, ya que no hay
    # forma de saber a cuál nivel formal correspondía cuando se escribió a mano).
    (5, "Mención manual \"VIP\" en Information", ("VIP",)),
]

# Rangos de tarifa (USD por noche) por nivel: (mínimo inclusive, máximo inclusive o None = sin tope).
_VIP_RATE_RANGES: list[tuple[int, float, float | None]] = [
    (1, 3000.0, None),
    (2, 1800.0, 3000.0),
    (3, 1000.0, 1700.0),
    (4, 700.0, 900.0),
]


def evaluar_vip(info_value: object, rate_value: object) -> tuple[int | None, list[str]]:
    """Determina el nivel VIP (1 = más alto) que le corresponde a una reserva
    según las palabras clave del campo INFORMATION y el valor de RATE.

    Devuelve (nivel_mas_alto_o_None, lista_de_razones_detectadas).
    """
    text = "" if info_value is None or pd.isna(info_value) else str(info_value).upper()
    reasons: list[str] = []
    best_level: int | None = None

    for level, label, keywords in _VIP_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            reasons.append(f"{label} (Nivel {level})")
            if best_level is None or level < best_level:
                best_level = level

    rate_number = _rate_representativo(rate_value)
    if rate_number is not None:
        for level, low, high in _VIP_RATE_RANGES:
            if rate_number >= low and (high is None or rate_number <= high):
                reasons.append(f"Tarifa ${rate_number:,.0f}/noche (Nivel {level})")
                if best_level is None or level < best_level:
                    best_level = level
                break

    return best_level, reasons


def calcular_posibles_vip(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve las filas de `df` que califican como posible VIP, con su
    nivel y las razones detectadas, ordenadas del nivel más alto al más bajo."""
    if df.empty:
        return df.assign(vip_nivel=pd.Series(dtype="Int64"), vip_razones=pd.Series(dtype=str))

    niveles, razones = [], []
    for _, row in df.iterrows():
        nivel, motivos = evaluar_vip(row.get("info"), row.get("rate"))
        niveles.append(nivel)
        razones.append(" · ".join(motivos))

    result = df.assign(vip_nivel=niveles, vip_razones=razones)
    result = result[result["vip_nivel"].notna()]
    return result.sort_values(by=["vip_nivel", "name"], na_position="last")


@st.dialog("🌟 Posibles VIP", width="large")
def vip_candidates_dialog() -> None:
    """Popup: analiza las reservas actualmente filtradas y sugiere cuáles
    califican como VIP según tarifa y palabras clave en INFORMATION."""
    df = cargar_reservaciones()
    filtered, filters = apply_filters(df)

    if filters:
        captions = []
        if "checkout" in filters:
            captions.append("Check-out: " + safe_text(filters["checkout"]))
        if "arrival" in filters:
            captions.append("Check-in: " + safe_text(filters["arrival"]))
        if "search" in filters:
            captions.append("Búsqueda: " + safe_text(filters["search"]))
        st.markdown(
            "<div style='color:#8ca4ba;font-size:11px;margin-bottom:8px;'>Analizando reservas filtradas — "
            + " | ".join(captions) + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color:#8ca4ba;font-size:11px;margin-bottom:8px;'>Analizando TODAS las reservas "
            "(no hay filtro de fecha/checkout/búsqueda activo).</div>",
            unsafe_allow_html=True,
        )

    candidatos = calcular_posibles_vip(filtered)

    st.markdown(
        "<div style='color:#8ca4ba;font-size:10px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;"
        "margin-bottom:6px;'>Criterios: Owners / Diamond Reserve / Lifetime Diamond / Amigos de dueño / "
        "Welcome back / Influencers / Gold / Forbes-Auditor-Amex, y tarifa por noche "
        "(&gt;$3000 → VIP1 · $1800–3000 → VIP2 · $1000–1700 → VIP3 · $700–900 → VIP4)</div>",
        unsafe_allow_html=True,
    )

    if candidatos.empty:
        st.info("Ninguna reserva del filtro actual cumple los criterios de VIP.")
    else:
        st.markdown(
            f"<div style='color:#00e5ff;font-size:12px;font-weight:800;margin:6px 0 10px;'>"
            f"{len(candidatos)} posible(s) VIP detectado(s)</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <style>
            .vip-cand-row {
                display:grid; grid-template-columns: .8fr 1.6fr .9fr 1fr 1fr 2.6fr;
                gap:10px; padding:8px 10px; border-bottom:1px solid #141414; align-items:center;
            }
            .vip-cand-row.head {
                color:#00e5ff; font-size:9px; font-weight:800; letter-spacing:1px;
                text-transform:uppercase; border-bottom:1px solid #1a1a1a;
            }
            .vip-cand-row .cell { color:#dfeff8; font-size:12px; overflow:hidden; text-overflow:ellipsis; }
            .vip-cand-row .reasons { color:#8ca4ba; font-size:10.5px; white-space:normal; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='vip-cand-row head'><div>NIVEL</div><div>NOMBRE</div><div>ROOM</div>"
            "<div>CHECK-IN</div><div>RATE</div><div>RAZONES DETECTADAS</div></div>",
            unsafe_allow_html=True,
        )
        with st.container(height=420):
            for _, row in candidatos.iterrows():
                nivel = int(row["vip_nivel"])
                label, color = VIP_LEVELS.get(nivel, (f"VIP {nivel}", "#00E5FF"))
                st.markdown(
                    "<div class='vip-cand-row'>"
                    f"<div class='cell' style='color:{color};font-weight:800;'>{label}</div>"
                    f"<div class='cell'>{safe_text(row.get('name', ''))}</div>"
                    f"<div class='cell'>{safe_text(row.get('room', ''))}</div>"
                    f"<div class='cell'>{safe_text(row.get('check_in', ''))}</div>"
                    f"<div class='cell'>{safe_text(row.get('rate', ''))}</div>"
                    f"<div class='cell reasons'>{safe_text(row.get('vip_razones', ''))}</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("Cerrar", use_container_width=True, key="close_vip_candidates_dialog"):
        st.rerun()


@st.dialog("Categoría", width="large")
def category_detail_dialog() -> None:
    """Popup: muestra las reservas de la tabla actualmente filtrada que
    pertenecen a la categoría en la que se hizo click (VIP, BIRTHDAY,
    HONEYMOON, BABYMOON, ANNIVERSARY, TEAM MEMBER, LEISURE o RELAXURY)."""
    category = st.session_state.get("category_detail_name", "")
    color = CATEGORY_CHART_COLORS.get(category, "#00E5FF")

    df = cargar_reservaciones()
    filtered, filters = apply_filters(df)

    st.markdown(
        f"<div style='color:{color};font-size:16px;font-weight:900;letter-spacing:.6px;"
        f"text-transform:uppercase;margin-bottom:2px;'>{safe_text(category)}</div>",
        unsafe_allow_html=True,
    )

    if filters:
        captions = []
        if "checkout" in filters:
            captions.append("Check-out: " + safe_text(filters["checkout"]))
        if "arrival" in filters:
            captions.append("Check-in: " + safe_text(filters["arrival"]))
        if "search" in filters:
            captions.append("Búsqueda: " + safe_text(filters["search"]))
        st.markdown(
            "<div style='color:#8ca4ba;font-size:11px;margin-bottom:8px;'>Reservas filtradas — "
            + " | ".join(captions) + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color:#8ca4ba;font-size:11px;margin-bottom:8px;'>Todas las reservas "
            "(no hay filtro de fecha/checkout/búsqueda activo).</div>",
            unsafe_allow_html=True,
        )

    mask = category_match_mask(filtered, category)
    rows = filtered[mask] if len(mask) else filtered.iloc[0:0]

    if rows.empty:
        st.info(f"No hay reservas de {category} en la tabla actual.")
    else:
        st.markdown(
            f"<div style='color:{color};font-size:12px;font-weight:800;margin:6px 0 10px;'>"
            f"{len(rows)} reserva(s) de {safe_text(category)}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <style>
            .cat-det-row {
                display:grid; grid-template-columns: .8fr 1.6fr .8fr 1fr 1fr 1.3fr 2.2fr;
                gap:10px; padding:8px 10px; border-bottom:1px solid #141414; align-items:center;
            }
            .cat-det-row.head {
                color:var(--cat-color); font-size:9px; font-weight:800; letter-spacing:1px;
                text-transform:uppercase; border-bottom:1px solid #1a1a1a;
            }
            .cat-det-row .cell { color:#dfeff8; font-size:12px; overflow:hidden; text-overflow:ellipsis; }
            .cat-det-row .info { color:#8ca4ba; font-size:10.5px; white-space:normal; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='cat-det-row head' style='--cat-color:{color}'><div>ETA</div><div>NOMBRE</div>"
            "<div>ROOM</div><div>CHECK-IN</div><div>CHECK-OUT</div><div>PHONE</div><div>INFORMATION</div></div>",
            unsafe_allow_html=True,
        )
        with st.container(height=420):
            for _, row in rows.iterrows():
                st.markdown(
                    "<div class='cat-det-row'>"
                    f"<div class='cell'>{safe_text(row.get('eta', ''))}</div>"
                    f"<div class='cell' style='color:{color};font-weight:700;'>{safe_text(row.get('name', ''))}</div>"
                    f"<div class='cell'>{safe_text(row.get('room', ''))}</div>"
                    f"<div class='cell'>{safe_text(row.get('check_in', ''))}</div>"
                    f"<div class='cell'>{safe_text(row.get('check_out', ''))}</div>"
                    f"<div class='cell'>{safe_text(row.get('phone', ''))}</div>"
                    f"<div class='cell info'>{safe_text(row.get('info', ''))}</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("Cerrar", use_container_width=True, key="close_category_detail_dialog"):
        st.rerun()


def render_dashboard(df: pd.DataFrame) -> None:
    # Borra automáticamente los reminders cuyo Due Date ya pasó (una vez por
    # día por sesión, para no golpear Supabase en cada rerun).
    _hoy_iso = datetime.today().date().isoformat()
    if st.session_state.get("reminders_cleanup_date") != _hoy_iso:
        try:
            limpiar_reminders_vencidos()
        except Exception:
            pass
        st.session_state["reminders_cleanup_date"] = _hoy_iso

    # Calcular métricas filtradas para mostrar en el dashboard
    filtered_preview, active_filters = apply_filters(df)
    total_display = len(filtered_preview) if active_filters else len(df)
    total_label = "RESERVAS FILTRADAS" if active_filters else "TOTAL RESERVAS"

    left, right = st.columns([1.35, 5.65], gap="small")
    filtered, filters = apply_filters(df)

    with left:
        today = datetime.now()
        checkout_links = []
        for offset in range(8):
            date = today + timedelta(days=offset)
            stored = date.strftime("%B %d, %Y")
            count = int((df["check_out"] == stored).sum())
            checkout_links.append(
                f'<a class="quick-link" href="{url_with(checkout_filtro=stored)}" target="_self" style="background:#{"0F766E" if offset % 2 == 0 else "155E75"}">{date:%b %d}: {count}</a>'
            )
        st.markdown('<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:5px">' + "".join(checkout_links) + "</div>", unsafe_allow_html=True)
        st.markdown(f'<div style="margin-top:7px"><a class="action-link" href="{url_with(skip_splash="1")}" target="_self" style="background:#2a2a2a">« VER TODAS »</a></div>', unsafe_allow_html=True)

        # Panel de seleccion masiva
        st.markdown('<div class="panel" style="margin-top:10px"><div class="panel-title">Seleccion masiva</div>', unsafe_allow_html=True)
        if not filtered.empty:
            all_ids_current = filtered["id"].dropna().astype(str).tolist()
            c1, c2 = st.columns(2)
            if c1.button("SELECC. TODO", use_container_width=True):
                st.session_state.bulk_selected_ids = all_ids_current
                st.session_state.pop("selected_reservation", None)
                st.session_state.pop("selected_reservation_id", None)
                st.rerun()
            if c2.button("DESMARCAR", use_container_width=True):
                st.session_state.bulk_selected_ids = []
                st.rerun()
            count_sel = len(st.session_state.get("bulk_selected_ids", []))
            st.markdown(f'<div style="text-align:center;color:#8ca4ba;font-size:10px;margin-top:4px">{count_sel} de {len(all_ids_current)} seleccionadas</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#8ca4ba;font-size:10px;text-align:center">No hay reservas para seleccionar</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


    with right:
        render_category_chart(filtered)
        relaxury = int(category_match_mask(filtered, "RELAXURY").sum())
        with st.container(key="catbtn_RELAXURY_strip"):
            st.markdown(
                f'<div class="total-strip" style="border-color:#f472b6;padding-right:34px">'
                f'RELAXURY <strong style="color:#f472b6">{relaxury}</strong></div>',
                unsafe_allow_html=True,
            )
            if st.button("📊", key="do_open_cat_RELAXURY_strip"):
                st.session_state["category_detail_name"] = "RELAXURY"
                st.session_state["open_category_detail"] = True
                st.query_params["skip_splash"] = "1"
                st.rerun()
        st.markdown(
            """
            <style>
            .st-key-catbtn_RELAXURY_strip { position:relative !important; }
            .st-key-do_open_cat_RELAXURY_strip {
                position:absolute !important; top:6px !important; right:10px !important;
                width:20px !important; height:20px !important; z-index:5 !important; margin:0 !important;
            }
            .st-key-do_open_cat_RELAXURY_strip button {
                width:20px !important; height:20px !important; min-height:20px !important; padding:0 !important;
                background:transparent !important; border:none !important; color:#f472b6 !important;
                font-size:11px !important; line-height:1 !important; box-shadow:none !important;
            }
            .st-key-do_open_cat_RELAXURY_strip button:hover {
                background:#f472b633 !important; border-radius:5px !important;
            }
            .st-key-do_open_cat_RELAXURY_strip [data-testid="stTooltipIcon"] { display:none !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        render_app_links()


    # Fila horizontal: filtros + menú
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([2.2, 1.3, 1.3, 1])

    with f1:
        filter_default = date_from_filter(str(st.query_params.get("fecha_date", "")))
        selected_date = st.date_input("CHECK-IN DATE", value=(filter_default or datetime.now()).date())

    with f2:
        date_link = url_with(fecha_date=selected_date.strftime("%Y-%m-%d"))
        st.markdown(f'<a class="action-link" href="{date_link}" target="_self" style="background:#0891B2;display:flex;align-items:center;justify-content:center;height:38px;margin-top:28px">APLICAR FECHA</a>', unsafe_allow_html=True)

    with f3:
        st.markdown(f'<a class="action-link" href="{url_with(fecha_date="", checkout_filtro="", skip_splash="1")}" target="_self" style="background:#3a3a3a;display:flex;align-items:center;justify-content:center;height:38px;margin-top:28px">LIMPIAR FILTROS</a>', unsafe_allow_html=True)

    with f4:
        render_menu()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .st-key-btn_vip_candidates button {
            background: linear-gradient(135deg,#7C3AED,#00E5FF) !important;
            color:#04070d !important;
            border:1px solid rgba(0,229,255,.5) !important;
            border-radius:8px !important;
            font: 800 11.5px/1.1 'Segoe UI', sans-serif !important;
            letter-spacing:.4px !important;
            text-transform:uppercase !important;
            white-space:nowrap !important;
            padding:0 6px !important;
        }
        .st-key-btn_vip_candidates button:hover {
            filter:brightness(1.15) !important;
            transform:translateY(-1px) !important;
        }
        .st-key-btn_guests_directory button {
            background: linear-gradient(135deg,#0F766E,#00E5FF) !important;
            color:#04070d !important;
            border:1px solid rgba(0,229,255,.5) !important;
            border-radius:8px !important;
            font: 800 11.5px/1.1 'Segoe UI', sans-serif !important;
            letter-spacing:.4px !important;
            text-transform:uppercase !important;
            white-space:nowrap !important;
            padding:0 6px !important;
        }
        .st-key-btn_guests_directory button:hover {
            filter:brightness(1.15) !important;
            transform:translateY(-1px) !important;
        }
        .st-key-btn_pending button {
            background: linear-gradient(135deg,#D97706,#00E5FF) !important;
            color:#04070d !important;
            border:1px solid rgba(0,229,255,.5) !important;
            border-radius:8px !important;
            font: 800 11.5px/1.1 'Segoe UI', sans-serif !important;
            letter-spacing:.4px !important;
            text-transform:uppercase !important;
            white-space:nowrap !important;
            padding:0 6px !important;
        }
        .st-key-btn_pending button:hover {
            filter:brightness(1.15) !important;
            transform:translateY(-1px) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if pending_tiene_contenido():
        st.markdown(
            """
            <style>
            .st-key-btn_pending button {
                background: linear-gradient(135deg,#B91C1C,#FF1744) !important;
                color:#ffffff !important;
                border:1px solid rgba(255,23,68,.7) !important;
                box-shadow:0 0 14px rgba(255,23,68,.55) !important;
                animation: pendingPulse 1.6s ease-in-out infinite;
            }
            @keyframes pendingPulse {
                0%, 100% { box-shadow:0 0 10px rgba(255,23,68,.45); }
                50% { box-shadow:0 0 20px rgba(255,23,68,.85); }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    vip_col, guests_col, pending_col = st.columns(3)
    with vip_col:
        with st.container(key="btn_vip_candidates"):
            if st.button("🌟 POSIBLES VIP", use_container_width=True, key="do_open_vip_candidates"):
                st.session_state["open_vip_candidates"] = True
                st.query_params["skip_splash"] = "1"
                st.rerun()
    with guests_col:
        with st.container(key="btn_guests_directory"):
            if st.button("👥 HUÉSPEDES", use_container_width=True, key="do_open_guests_directory"):
                st.session_state["open_guests"] = True
                st.query_params["skip_splash"] = "1"
                st.rerun()
    with pending_col:
        with st.container(key="btn_pending"):
            _pending_count = pending_contar_lineas()
            _pending_label = f"📌 PENDING  {_pending_count}" if _pending_count > 0 else "📌 PENDING"
            if st.button(_pending_label, use_container_width=True, key="do_open_pending"):
                st.session_state["open_pending"] = True
                st.query_params["skip_splash"] = "1"
                st.rerun()
    st.markdown("<div style='height:3px'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .search-wrapper { position: relative; max-width: 100%; }
        .search-wrapper input {
            padding-left: 36px !important;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%238ca4ba' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E") !important;
            background-repeat: no-repeat !important;
            background-position: 12px center !important;
            background-size: 16px 16px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # "TOTAL RESERVAS" (o "RESERVAS FILTRADAS" si hay filtros activos) se
    # muestra aquí, justo encima del buscador rápido: primero la etiqueta,
    # luego el número — a pedido del usuario.
    st.markdown(
        f'<div class="total-badge"><div class="summary-label">{total_label}</div>'
        f'<div class="summary-value">{total_display}</div></div>',
        unsafe_allow_html=True,
    )
    st.text_input(
        "Búsqueda rápida",
        key="global_search",
        placeholder="🔍 Buscar por nombre, teléfono, reserva, VIP, Relaxury...",
        label_visibility="collapsed",
        on_change=st.rerun,
    )
    filtered, filters = apply_filters(df)

    if filters:
        captions = []
        if "checkout" in filters:
            captions.append("Check-out: " + safe_text(filters["checkout"]))
        if "arrival" in filters:
            captions.append("Check-in: " + safe_text(filters["arrival"]))
        if "search" in filters:
            captions.append("Búsqueda: " + safe_text(filters["search"]))
        st.caption(" | ".join(captions))

    st.markdown("<div style='height:5px'></div>", unsafe_allow_html=True)

    # --- Seleccion masiva ---
    if "bulk_selected_ids" not in st.session_state:
        st.session_state.bulk_selected_ids = []

    bulk_ids = st.session_state.bulk_selected_ids
    all_ids = filtered["id"].dropna().astype(str).tolist() if not filtered.empty else []

    # Banner de seleccion individual o masiva
    selected = st.session_state.get("selected_reservation")
    if selected and not bulk_ids:
        sel_id = safe_text(str(selected.get("id", "")))
        name, room = safe_text(selected.get("name", "N/A")), safe_text(selected.get("room", "—"))
        st.markdown(f'<div class="selection-banner"><b>RESERVA SELECCIONADA</b> &nbsp; {name} &nbsp;|&nbsp; Room: {room}</div>', unsafe_allow_html=True)
        # Botones reales (no links): abren popups flotantes sin cambiar de pagina.
        st.markdown(
            """
            <style>
            .st-key-selection_actions { max-width:700px; }
            .st-key-selection_actions button {
                border:none !important;
                border-radius:8px !important;
                color:#fff !important;
                font: 800 12px/1.1 'Segoe UI', sans-serif !important;
                letter-spacing:1.1px !important;
                text-transform:uppercase !important;
                padding:9px 10px !important;
                transition: all .12s ease !important;
            }
            .st-key-selection_actions button:hover {
                filter:brightness(1.15) !important;
                transform:translateY(-1px) !important;
            }
            .st-key-btn_sel_editar button { background:#D97706 !important; }
            .st-key-btn_sel_carta  button { background:#7C3AED !important; }
            .st-key-btn_sel_borrar button { background:#E11D48 !important; }
            .st-key-btn_sel_deselect button { background:#3a3a3a !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="selection_actions"):
            act1, act2, act3, act4 = st.columns(4)
            with act1:
                with st.container(key="btn_sel_editar"):
                    if st.button("EDITAR", use_container_width=True, key="do_sel_editar"):
                        st.session_state["open_editar"] = True
                        st.rerun()
            with act2:
                with st.container(key="btn_sel_carta"):
                    if st.button("CARTA", use_container_width=True, key="do_sel_carta"):
                        st.session_state["open_carta"] = True
                        st.rerun()
            with act3:
                with st.container(key="btn_sel_borrar"):
                    if st.button("BORRAR", use_container_width=True, key="do_sel_borrar"):
                        st.session_state["open_borrar"] = True
                        st.rerun()
            with act4:
                with st.container(key="btn_sel_deselect"):
                    if st.button("DESELECCIONAR", use_container_width=True, key="do_sel_deselect"):
                        clear_page()
    elif bulk_ids:
        st.markdown(
            f'<div class="selection-banner" style="border-color:#E11D48;background:#1a0000">'
            f'<b>RESERVAS SELECCIONADAS: {len(bulk_ids)}</b> &nbsp; | &nbsp;'
            f'<span style="color:#ff6b6b">Listas para eliminar</span></div>',
            unsafe_allow_html=True,
        )
        with st.form("bulk_delete_form", clear_on_submit=True):
            pwd_col, btn_col = st.columns([2, 3])
            with pwd_col:
                bulk_password = st.text_input("Clave de autorizacion", type="password", label_visibility="collapsed", placeholder="Contrasena de borrado")
            with btn_col:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                submitted_bulk = st.form_submit_button("BORRAR SELECCIONADAS", type="primary", use_container_width=True)
            if submitted_bulk:
                expected = st.secrets.get("DELETE_PASSWORD", "")
                if not expected:
                    st.error("Configura DELETE_PASSWORD en los Secrets.")
                elif bulk_password != expected:
                    st.error("Clave incorrecta.")
                else:
                    eliminar_reservas(bulk_ids)
                    st.session_state.bulk_selected_ids = []
                    st.session_state.pop("selected_reservation", None)
                    st.session_state.pop("selected_reservation_id", None)
                    st.success(f"{len(bulk_ids)} reservas eliminadas correctamente.")
                    clear_page()
        st.markdown(
            '<div class="action-links" style="grid-template-columns:repeat(2,minmax(110px,1fr));max-width:400px">'
            f'<a class="action-link" href="{url_with(skip_splash="1")}" target="_self" style="background:#3a3a3a">CANCELAR SELECCION</a>'
            '</div>',
            unsafe_allow_html=True,
        )

    render_reservations_grid(filtered)


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------

show_header()
reservations = cargar_reservaciones()
action = get_action()

# Auto-abrir calculadora si viene de redirección legacy
if st.session_state.pop("open_calculator", False):
    calculator_dialog()

# Auto-abrir almanaque si viene de redirección
if st.session_state.pop("open_calendar", False):
    calendar_dialog()

# Auto-abrir el logo Fred Wayne desde el menu de Herramientas
if st.session_state.pop("open_logo", False):
    logo_dialog()

# Auto-abrir el formulario P. Dinning desde el menu de Herramientas
if st.session_state.pop("open_pdinning", False):
    pdinning_dialog()

# Auto-abrir los popups del header (arrivals / QR code)
if st.session_state.pop("open_arrivals", False):
    arrivals_dates_dialog()

if st.session_state.pop("open_qrcode", False):
    qrcode_dialog()

# Auto-abrir los popups de reservas (nueva / editar / carta / borrar)
if st.session_state.pop("open_nueva", False):
    new_reservation_dialog()

if st.session_state.pop("open_editar", False):
    edit_reservation_dialog()

if st.session_state.pop("open_carta", False):
    letter_dialog()

if st.session_state.pop("open_borrar", False):
    delete_reservation_dialog()

# Auto-abrir los popups de operaciones (importar / exportar / reporte / agenda)
if st.session_state.pop("open_importar", False):
    import_dialog()

if st.session_state.pop("open_exportar", False):
    export_dialog()

if st.session_state.pop("open_reporte", False):
    report_dialog()

if st.session_state.pop("open_agenda", False):
    agenda_dialog()

# Auto-abrir los popups de reminders (ver / editar)
if st.session_state.pop("open_reminders", False):
    reminders_dialog()

if st.session_state.pop("open_reminders_edit", False):
    reminder_edit_dialog()

# Auto-abrir los popups del directorio telefónico
if st.session_state.pop("open_directorio", False):
    directorio_dialog()

if st.session_state.pop("open_directorio_new", False):
    directorio_new_dialog()

if st.session_state.pop("open_directorio_import", False):
    directorio_import_dialog()

# Auto-abrir el popup de posibles VIP (analiza el filtro actual)
if st.session_state.pop("open_vip_candidates", False):
    vip_candidates_dialog()

# Auto-abrir el popup de detalle de categoría (click en VIP/BIRTHDAY/
# HONEYMOON/BABYMOON/ANNIVERSARY/TEAM MEMBER/LEISURE/RELAXURY en el gráfico)
if st.session_state.pop("open_category_detail", False):
    category_detail_dialog()

# Auto-abrir los popups de Huéspedes (lista + ficha de contacto extra).
# Nunca deben abrirse los dos en el mismo ciclo (Streamlit no permite
# dialogs anidados) — si por algún residuo ambas banderas quedaron en
# True, gana la ficha de detalle (la más específica).
_open_guests = st.session_state.pop("open_guests", False)
_open_guests_detail = st.session_state.pop("open_guests_detail", False)
if _open_guests_detail:
    guests_detail_dialog()
elif _open_guests:
    guests_dialog()

# Auto-abrir el popup de Pending (block de notas de 15 líneas)
if st.session_state.pop("open_pending", False):
    pending_dialog()

# Auto-abrir el popup de reservas Recognition.
if st.session_state.pop("open_recognition", False):
    recognition_dialog()

# Auto-abrir el popup de VIP Alert (captura + descarga en Word). Streamlit
# sólo permite un popup a la vez: al abrirse se limpia la bandera de Editar.
if st.session_state.pop("open_vip_alert", False):
    st.session_state.pop("open_editar", None)
    vip_alert_dialog()


def _redirect_to_dialog(flag: str) -> None:
    """Quita `action` de la URL, conserva filtros y abre el popup en el dashboard."""
    if "action" in st.query_params:
        del st.query_params["action"]
    st.query_params["skip_splash"] = "1"
    st.session_state[flag] = True
    st.rerun()


if action == "nueva":
    _redirect_to_dialog("open_nueva")
elif action == "editar":
    _redirect_to_dialog("open_editar")
elif action == "importar":
    _redirect_to_dialog("open_importar")
elif action == "exportar":
    _redirect_to_dialog("open_exportar")
elif action == "agenda":
    _redirect_to_dialog("open_agenda")
elif action == "reporte":
    _redirect_to_dialog("open_reporte")
elif action == "calculadora":
    # Redirigir al dashboard y abrir dialog automáticamente (preservar filtros)
    for key in list(st.query_params.keys()):
        if key == "action":
            del st.query_params[key]
    st.query_params["skip_splash"] = "1"
    st.session_state["open_calculator"] = True
    st.rerun()
elif action == "almanaque":
    for key in list(st.query_params.keys()):
        if key == "action":
            del st.query_params[key]
    st.query_params["skip_splash"] = "1"
    st.session_state["open_calendar"] = True
    st.rerun()
elif action == "bonus":
    render_bonus()
elif action == "carta":
    _redirect_to_dialog("open_carta")
elif action == "cancelar":
    _redirect_to_dialog("open_borrar")
else:
    render_dashboard(reservations)
