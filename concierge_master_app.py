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

    # CSS para pantalla completa
    st.markdown(
        """
        <style>
        header, [data-testid="stHeader"] { display: none !important; }
        .stApp { background: #000 !important; }
        .main .block-container { padding: 0 !important; max-width: 100% !important; }
        .splash-img-container { width: 100vw; height: 100vh; position: fixed; top: 0; left: 0; z-index: 9999; }
        .splash-img-container img { width: 100%; height: 100%; object-fit: cover; }
        .splash-bar {
            position: fixed; bottom: 60px; left: 50%; transform: translateX(-50%);
            width: 380px; height: 4px; background: #1a1a1a; border-radius: 2px;
            overflow: hidden; border: 1px solid #333; z-index: 10000;
        }
        .splash-bar-fill {
            height: 100%; background: #D4AF37; width: 0%;
            animation: splashFill 5s linear forwards;
            box-shadow: 0 0 12px #D4AF37, 0 0 24px rgba(212,175,55,0.5);
        }
        @keyframes splashFill { to { width: 100%; } }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if os.path.exists(splash_path):
        st.markdown(
            f'<div class="splash-img-container"><img src="data:image/png;base64,'
            + base64.b64encode(open(splash_path, "rb").read()).decode("utf-8")
            + '" alt="Splash"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.warning("No se encontro `splashscreen.png`. Subelo a tu repositorio junto a este archivo.")

    st.markdown(
        '<div class="splash-bar"><div class="splash-bar-fill"></div></div>',
        unsafe_allow_html=True,
    )

    import time
    time.sleep(5)
    st.session_state.splash_shown = True
    st.rerun()

TABLE_NAME = "huespedes"
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
        "https://outlook.cloud.microsoft/mail/Lirgu.conciergeresidencias@waldorfasroria.com/",
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
        return pd.DataFrame(columns=DB_COLUMNS + ["nights"])

    for column in DB_COLUMNS:
        if column not in df.columns:
            df[column] = "" if column != "qty" else 0

    df["nights"] = df.apply(
        lambda row: calcular_noches(row.get("check_in"), row.get("check_out")), axis=1
    )
    sort_date = df["check_in"].map(parse_fecha)
    return df.assign(_sort_date=sort_date).sort_values(
        by=["_sort_date", "name"], na_position="last"
    ).drop(columns="_sort_date")


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

    fill_section = PatternFill("solid", fgColor="00B0F0")
    fill_header = PatternFill("solid", fgColor="123047")
    fill_data = PatternFill("solid", fgColor="F4F7F9")
    white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
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
        cell.fill, cell.font, cell.alignment = fill_section, white_bold, center
        row_number += 1

        for column_index, (_, heading) in enumerate(export_columns, 1):
            cell = sheet.cell(row=row_number, column=column_index, value=heading)
            cell.fill, cell.font, cell.alignment, cell.border = fill_header, white_bold, center, border
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

        l10, _l11, _l12 = st.columns(3)
        l10.markdown(f'<a href="{html.escape(QUICK_LINKS[9][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#f472b6;">RELAXURY</a>', unsafe_allow_html=True)

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


def render_category_chart(df: pd.DataFrame) -> None:
    info = df["info"].fillna("").astype(str).str.upper() if "info" in df.columns else pd.Series(dtype=str)
    cards = []

    # Categorías que se muestran en el gráfico (RELAXURY se excluye; tiene su propia barra debajo)
    chart_categories = {
        "VIP": "#00E5FF",
        "BIRTHDAY": "#FF5252",
        "HONEYMOON": "#FF9800",
        "BABYMOON": "#A78BFA",
        "ANNIVERSARY": "#4ADE80",
        "TEAM MEMBER": "#FACC15",
        "LEISURE": "#22D3EE",
    }

    # Categorías especiales que "consumen" una reserva (excluyendo LEISURE)
    special_categories = ["VIP", "BIRTHDAY", "HONEYMOON", "BABYMOON", "ANNIVERSARY", "RELAXURY", "TEAM MEMBER"]
    has_special = info.apply(lambda text: any(cat in text for cat in special_categories) if pd.notna(text) else False)
    # Asegurar tipo bool para evitar ValueError con operador ~ en Series vacías
    has_special = has_special.fillna(False).astype(bool)

    for category, color in chart_categories.items():
        if category == "LEISURE":
            count = int((~has_special).sum())
        else:
            count = int(info.str.contains(category, na=False).sum())
        width = count / max(len(df), 1) * 100
        cards.append(
            f'<div class="category-card" style="--category-color:{color};background:{color}22">'
            f'<div class="category-card-head"><span>{category}</span><span>{count}</span></div>'
            f'<div class="category-card-track"><div class="category-card-fill" style="width:{width:.1f}%"></div></div></div>'
        )
    st.markdown(
        '<div class="panel"><div class="panel-title">Guest categories</div>'
        '<div class="category-grid">' + "".join(cards) + '</div></div>',
        unsafe_allow_html=True,
    )


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
            "room": room.strip(), "email": email.strip(), "check_in": check_in.strftime("%B %d, %Y"),
            "check_out": check_out.strftime("%B %d, %Y"), "res_number": res_number.strip(),
            "phone": phone.strip(), "info": info.strip(), "ird": ird.strip(), "hsk": hsk.strip(),
            "rate": rate.strip(), "trans": trans.strip(),
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
        actualizar_reserva(reservation["id"], {
            "eta": eta if eta != "-- Sin hora --" else "", "name": name.strip(), "qty": float(qty), "room": room.strip(),
            "email": email.strip(), "check_in": check_in.strftime("%B %d, %Y"),
            "check_out": check_out.strftime("%B %d, %Y"), "res_number": res_number.strip(),
            "phone": phone.strip(), "info": info.strip(), "ird": ird.strip(), "hsk": hsk.strip(),
            "rate": rate.strip(), "trans": trans.strip(),
        })
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

        fill_section = PatternFill("solid", fgColor="00B0F0")
        fill_header = PatternFill("solid", fgColor="123047")
        fill_data = PatternFill("solid", fgColor="F4F7F9")
        white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
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
            cell.fill, cell.font, cell.alignment = fill_section, white_bold, center
            row_number += 1
            for column_index, (_, heading) in enumerate(export_columns, 1):
                cell = sheet.cell(row=row_number, column=column_index, value=heading)
                cell.fill, cell.font, cell.alignment, cell.border = fill_header, white_bold, center, border
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
    st.dataframe(
        pd.DataFrame([
            {"Categoría": label, "Reservas": len(frame), "Habitaciones": ", ".join(frame["room"].dropna().astype(str).tolist()) or "—"}
            for label, frame in report_data.items()
        ]),
        use_container_width=True,
        hide_index=True,
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


@st.dialog("📅 Arrivals By Date", width="small")
def arrivals_dates_dialog() -> None:
    """Popup con todas las fechas de check-in; al hacer clic filtra la tabla."""
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
        f"{len(dates)} fechas · haz clic para ver las reservas de ese dia</div>",
        unsafe_allow_html=True,
    )

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

    # Ensanchar SOLO este popup (Streamlit tope en width="large" ~800px).
    # Como los dialogs son exclusivos (solo uno montado a la vez), este CSS
    # aplica únicamente mientras el Directorio está abierto.
    st.markdown(
        """
        <style>
        div[role="dialog"] {
            width: 96vw !important;
            max-width: 1400px !important;
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
            .directorio-row {
                display:grid;
                grid-template-columns: 1.6fr 1.4fr 1.8fr 1.8fr .7fr 1.1fr;
                gap:8px;
                padding:7px 10px;
                border-bottom:1px solid #141414;
                align-items:center;
            }
            .directorio-row.head {
                color:#00e5ff; font-size:9px; font-weight:800; letter-spacing:1px;
                text-transform:uppercase; border-bottom:1px solid #1a1a1a;
            }
            .directorio-row .cell { color:#dfeff8; font-size:12px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
            .directorio-row .dept { color:#8ca4ba; font-size:11px; }
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
        st.markdown(
            "<div class='directorio-row head'><div>COLABORADOR</div><div>DEPARTAMENTO</div>"
            "<div>PUESTO</div><div>CORREO</div><div>EXT.</div><div>TELÉFONO</div></div>",
            unsafe_allow_html=True,
        )
        with st.container(height=430, key="directorio_list"):
            for _, row in view.iterrows():
                row_id = row.get("id")
                if editing_id is not None and row_id == editing_id:
                    _directorio_inline_edit_row(row)
                    continue
                c1, c2, c3, c4, c5, c6 = st.columns([1.6, 1.4, 1.8, 1.8, .7, 1.1])
                with c1:
                    if st.button(
                        str(row.get("colaborador", "") or "—"),
                        key=f"dir_name_btn_{row_id}", use_container_width=True,
                    ):
                        st.session_state["directorio_inline_edit_id"] = row_id
                        st.session_state["open_directorio"] = True
                        st.rerun()
                c2.markdown(f"<div class='cell dept'>{safe_text(row.get('departamento', ''))}</div>", unsafe_allow_html=True)
                c3.markdown(f"<div class='cell'>{safe_text(row.get('nombre_puesto', ''))}</div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='cell'>{safe_text(row.get('correo_electronico', ''))}</div>", unsafe_allow_html=True)
                c5.markdown(f"<div class='cell'>{safe_text(row.get('extension', ''))}</div>", unsafe_allow_html=True)
                c6.markdown(f"<div class='cell'>{safe_text(row.get('telefono_contacto', ''))}</div>", unsafe_allow_html=True)

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

    # Quitar .0 en ROOM y NOCHES
    for col in ("room", "nights"):
        if col in visible.columns:
            visible[col] = visible[col].apply(
                lambda x: str(int(float(x))) if str(x).replace(".", "").replace("-", "").isdigit() else str(x)
            )

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

    vip_count = int(df["info"].fillna("").astype(str).str.upper().str.contains("VIP", na=False).sum())
    relaxury_count = int(df.astype(str).apply(lambda column: column.str.upper().str.contains("RELAXURY", na=False)).any(axis=1).sum())
    nights_count = int(pd.to_numeric(df["nights"], errors="coerce").fillna(0).sum())

    # Calcular métricas filtradas para mostrar en el dashboard
    filtered_preview, active_filters = apply_filters(df)
    total_display = len(filtered_preview) if active_filters else len(df)
    total_label = "RESERVAS FILTRADAS" if active_filters else "TOTAL RESERVAS"

    # NOTA: "TOTAL RESERVAS" / "RESERVAS FILTRADAS" ya no va en esta fila de
    # arriba — a pedido del usuario se movió justo encima del buscador rápido
    # (ver más abajo, cerca de `st.text_input("Búsqueda rápida", ...)`).
    st.markdown(
        f'<div class="summary-grid-3">'
        f'<div class="summary-card gold"><div class="summary-label">VIP ARRIVALS <span></span></div><div class="summary-value">{vip_count}</div></div>'
        f'<div class="summary-card pink"><div class="summary-label">RELAXURY <span></span></div><div class="summary-value">{relaxury_count}</div></div>'
        f'<div class="summary-card purple"><div class="summary-label">NOCHES RESERVADAS <span></span></div><div class="summary-value">{nights_count}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

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
        relaxury = int(filtered.astype(str).apply(lambda column: column.str.upper().str.contains("RELAXURY", na=False)).any(axis=1).sum())
        st.markdown(f'<div class="total-strip" style="border-color:#f472b6">RELAXURY <strong style="color:#f472b6">{relaxury}</strong></div>', unsafe_allow_html=True)
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
