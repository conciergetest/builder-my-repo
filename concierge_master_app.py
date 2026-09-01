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
from datetime import datetime, timedelta
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


def parse_fecha(value: object) -> datetime | None:
    if value is None or pd.isna(value) or not str(value).strip():
        return None
    value = str(value).strip()
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%B %d", "%b %d"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None


def normalizar_fecha(value: object) -> str:
    date = parse_fecha(value)
    if date:
        if date.year == 1900:
            date = date.replace(year=datetime.now().year)
        return date.strftime("%B %d, %Y")
    return "" if value is None or pd.isna(value) else str(value).strip()


def generate_eta_options() -> list[str]:
    """Genera lista de horas cada 30 min en formato 12h AM/PM."""
    options = ["-- Sin hora --"]
    for hour in range(24):
        for minute in (0, 30):
            t = datetime.strptime(f"{hour}:{minute:02d}", "%H:%M")
            options.append(t.strftime("%I:%M %p").lstrip("0"))
    return options


def parse_eta_index(current: str, options: list[str]) -> int:
    """Devuelve el indice de la opcion que coincida con current, o 0."""
    if not current or current.strip() in ("", "nan", "none"):
        return 0
    current_clean = current.strip().upper()
    for i, opt in enumerate(options):
        if opt.upper() == current_clean:
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


def clear_page() -> None:
    clear_selection()
    st.session_state.bulk_selected_ids = []
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


def actualizar_reserva(reservation_id: object, data: dict) -> None:
    supabase.table(TABLE_NAME).update(data).eq("id", reservation_id).execute()
    st.cache_data.clear()


def eliminar_reserva(reservation_id: object) -> None:
    supabase.table(TABLE_NAME).delete().eq("id", reservation_id).execute()
    st.cache_data.clear()


def eliminar_reservas(reservation_ids: list) -> None:
    if reservation_ids:
        supabase.table(TABLE_NAME).delete().in_("id", reservation_ids).execute()
        st.cache_data.clear()


def insertar_lote(records: list[dict]) -> None:
    if records:
        supabase.table(TABLE_NAME).insert(records).execute()
        st.cache_data.clear()


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

    header_left, header_center, header_right = st.columns([1.4, 0.5, 1])
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
        st.markdown(
            '<div style="display:flex;justify-content:center;align-items:center;height:100%;">'
            '<img src="https://raw.githubusercontent.com/conciergetest/builder-my-repo/main/FredWayneLOGO.jpeg" '
            'style="max-height:52px;width:auto;border-radius:8px;opacity:.95;box-shadow:0 4px 12px rgba(0,0,0,.5);" '
            'alt="Fred Wayne Logo">'
            '</div>',
            unsafe_allow_html=True,
        )
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

    with st.popover("☰ MENÚ", use_container_width=True):
        st.markdown("<div style='color:#d4af37;font-size:14px;font-weight:800;letter-spacing:1.5px;text-align:center;margin-bottom:14px;'>CONCIERGE MASTER</div>", unsafe_allow_html=True)

        # ── Operaciones ──
        st.markdown("<div style='color:#8ca4ba;font-size:10px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px;border-left:3px solid #00e5ff;padding-left:8px;'>Operaciones</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        if c1.button("➕ NUEVA", use_container_width=True):
            st.query_params["action"] = "nueva"
            st.rerun()
        if c2.button("⬆ IMPORTAR", use_container_width=True):
            st.query_params["action"] = "importar"
            st.rerun()
        if c3.button("⬇ EXPORTAR", use_container_width=True):
            st.query_params["action"] = "exportar"
            st.rerun()
        c4, c5, c6 = st.columns(3)
        if c4.button("📊 REPORTE", use_container_width=True):
            st.query_params["action"] = "reporte"
            st.rerun()
        if c5.button("📅 AGENDA", use_container_width=True):
            st.query_params["action"] = "agenda"
            st.rerun()
        if c6.button("💰 BONUS", use_container_width=True):
            st.query_params["action"] = "bonus"
            st.rerun()

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        # ── Herramientas ──
        st.markdown("<div style='color:#8ca4ba;font-size:10px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:8px;border-left:3px solid #a78bfa;padding-left:8px;'>Herramientas</div>", unsafe_allow_html=True)
        h1, h2 = st.columns(2)
        if h1.button("🧮 CALCULADORA", use_container_width=True):
            st.query_params["action"] = "calculadora"
            st.rerun()
        if h2.button("📆 ALMANAQUE", use_container_width=True):
            st.query_params["action"] = "almanaque"
            st.rerun()

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
        l9.markdown(f'<a href="{html.escape(QUICK_LINKS[8][1], quote=True)}" target="_blank" rel="noopener noreferrer" style="{link_style}color:#f472b6;">RELAXURY</a>', unsafe_allow_html=True)

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


def render_new_reservation() -> None:
    st.subheader("Nueva Reservación")
    render_back_link()
    eta_options = generate_eta_options()
    with st.form("new_reservation", clear_on_submit=True):
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


def render_edit_reservation() -> None:
    reservations = cargar_reservaciones()
    reservation = get_selected_reservation(reservations)
    if not reservation:
        st.error("Selecciona una reserva de la tabla antes de editar.")
        render_back_link()
        return

    st.subheader(f"Editar reservación· {safe_text(reservation.get('name', ''))}")
    render_back_link()
    check_in_default = parse_fecha(reservation.get("check_in")) or datetime.now()
    check_out_default = parse_fecha(reservation.get("check_out")) or datetime.now() + timedelta(days=1)
    qty_default = pd.to_numeric(reservation.get("qty", 0), errors="coerce")
    qty_default = 0.0 if pd.isna(qty_default) else float(qty_default)

    with st.form("edit_reservation"):
        first = st.columns(4)
        eta = first[0].text_input("ETA", value=str(reservation.get("eta", "")))
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
            "eta": eta.strip(), "name": name.strip(), "qty": float(qty), "room": room.strip(),
            "email": email.strip(), "check_in": check_in.strftime("%B %d, %Y"),
            "check_out": check_out.strftime("%B %d, %Y"), "res_number": res_number.strip(),
            "phone": phone.strip(), "info": info.strip(), "ird": ird.strip(), "hsk": hsk.strip(),
            "rate": rate.strip(), "trans": trans.strip(),
        })
        st.success("Reserva actualizada correctamente.")
        clear_page()


def render_import() -> None:
    st.subheader("Importar reservaciones desde Excel")
    render_back_link()
    st.info("Columnas requeridas: " + ", ".join(IMPORT_COLUMNS))
    uploaded = st.file_uploader("Archivo Excel", type=["xlsx", "xls"])
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
    # Reemplazar NaN/None por cadena vacia (o 0 para qty) para visualizacion limpia
    for col in preview.columns:
        if col == "qty":
            preview[col] = preview[col].apply(lambda x: 0 if pd.isna(x) or str(x).lower() in ("nan", "none", "null", "") else int(float(x)))
        else:
            preview[col] = preview[col].apply(lambda x: "" if pd.isna(x) or str(x).lower() in ("nan", "none", "null") else x)
    st.success(f"Archivo válido: {len(preview)} reservaciones detectadas.")
    st.dataframe(preview, use_container_width=True, hide_index=True, height=300)

    if st.button("IMPORTAR A BASE DE DATOS", type="primary", use_container_width=True):
        records: list[dict] = []
        for _, row in preview.iterrows():
            record = {}
            for column in IMPORT_COLUMNS:
                value = row[column]
                if pd.isna(value) or str(value).lower() in ("nan", "none", "null"):
                    value = ""
                elif column == "qty":
                    value = int(pd.to_numeric(value, errors="coerce") or 0)
                else:
                    value = str(value).strip()
                record[column] = value
            records.append(record)
        try:
            insertar_lote(records)
            st.success(f"{len(records)} reservaciones importadas correctamente.")
        except Exception as exc:
            st.error(f"No se completó la importación: {exc}")


def render_export(df: pd.DataFrame) -> None:
    st.subheader("Exportar reservaciones a Excel")
    render_back_link()
    filtered, _ = apply_filters(df)
    st.info(f"Se exportarán {len(filtered)} reservaciones, organizadas por categoría.")
    st.dataframe(filtered[DISPLAY_COLUMNS], use_container_width=True, hide_index=True, height=300)

    def _build_excel(data: pd.DataFrame) -> BytesIO:
        """Generador de Excel AUTOCONTENIDO: no depende de ninguna otra función del archivo."""
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        export_columns = [
            ("eta", "ETA"), ("name", "NAME"), ("qty", "QTY"),
            ("room", "ROOM"), ("email", "EMAIL"), ("check_in", "CHECK IN"),
            ("check_out", "CHECK OUT"), ("nights", "NIGHTS"),
            ("res_number", "RESERVATION"), ("phone", "PHONE"), ("info", "INFORMATION"),
            ("ird", "IRD"), ("hsk", "HSK"), ("rate", "RATE"), ("trans", "TRANSPORTATION"),
        ]

        data = data.copy()
        # Normalizar nombres de columnas: sin espacios y en minúsculas
        data.columns = [str(column).strip().lower() for column in data.columns]
        # Eliminar columnas duplicadas (conserva la primera aparición)
        data = data.loc[:, ~pd.Index(data.columns).duplicated(keep="first")]
        # DEFENSA: crear como vacía cualquier columna faltante (incluida "info")
        for key, _ in export_columns:
            if key not in data.columns:
                data[key] = ""

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

        remaining = data
        row_number = 1
        for title, keywords in groups:
            if keywords:
                info_series = remaining["info"].fillna("").astype(str).str.upper()
                mask = info_series.apply(lambda value: any(keyword in value for keyword in keywords))
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

            for _, record in rows.iterrows():
                for column_index, (key, _) in enumerate(export_columns, 1):
                    value = record.get(key, "")
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
        )


def render_agenda(df: pd.DataFrame) -> None:
    st.subheader("Agenda de reservaciones")
    render_back_link()
    selected_date = st.date_input("Fecha", value=datetime.now().date())
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


def render_report(df: pd.DataFrame) -> None:
    st.subheader("Reporte de ocupación diario")
    render_back_link()
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
    )


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


def render_calculator() -> None:
    """Vista legacy de calculadora (redirige al dialog)."""
    st.subheader("Calculadora")
    render_back_link()
    calculator_dialog()


def render_letter() -> None:
    st.subheader("Carta de despedida")
    render_back_link()
    reservations = cargar_reservaciones()
    reservation = get_selected_reservation(reservations)
    if not reservation:
        st.error("Selecciona una reserva de la tabla antes de crear la carta.")
        return

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


def render_delete() -> None:
    st.subheader("Eliminar reservación")
    render_back_link()
    reservations = cargar_reservaciones()
    reservation = get_selected_reservation(reservations)
    if not reservation:
        st.error("Selecciona una reserva antes de solicitar el borrado.")
        return
    st.warning(f"Se eliminará permanentemente la reserva de {reservation.get('name', 'este huésped')}.")
    with st.form("delete_reservation"):
        password = st.text_input("Clave de autorización", type="password")
        confirmed = st.form_submit_button("CONFIRMAR Y BORRAR", type="primary")
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

    # Agregar icono de checkout (🏃) solo para reservas que YA hicieron checkout
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if "check_out" in visible.columns:
        def _checkout_with_icon(val):
            if not val or pd.isna(val):
                return val
            val_str = str(val).strip()
            # Quitar todo despues del año (4 digitos) — elimina emojis/iconos guardados
            cleaned = re.sub(r"(\d{4})\s*[^\d]*$", r"\1", val_str).strip()
            dt = parse_fecha(cleaned)
            if dt and dt.replace(hour=0, minute=0, second=0, microsecond=0) <= today:
                return cleaned + " 🏃"
            return cleaned
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
        "eta":      ("ETA",          110),
        "name":     ("NAME",         170),
        "qty":      ("QTY",          60),
        "room":     ("ROOM",         70),
        "check_in": ("CHECK IN",     155),
        "check_out":("CHECK OUT",    175),
        "nights":   ("🌙",            60),
        "res_number":("RESERVATION", 170),
        "phone":    ("PHONE",        175),
        "email":    ("EMAIL",        140),
        "info":     ("INFORMATION",  220),
        "ird":      ("IRD",          160),
        "hsk":      ("HSK",          110),
        "rate":     ("RATE",         80),
        "trans":    ("TRANS",        200),
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
            config["cellStyle"] = JsCode("function(params){ return { color: '#D4AF37', fontWeight: '700' }; }")
        # Solo CHECK IN tiene filtro habilitado
        if field == "check_in":
            config["filter"] = True
        builder.configure_column(field, **config)

    response = AgGrid(
        visible,
        gridOptions=builder.build(),
        custom_css=GRID_CSS,
        theme="alpine",
        height=625,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        key="concierge_reservations_grid",
    )

    selected = response.get("selected_rows", [])
    if isinstance(selected, pd.DataFrame):
        selected = selected.to_dict("records")
    if selected:
        selected_id = selected[0].get("id")
        # AgGrid recibe una vista sin `id`; la buscamos con una combinación estable de datos.
        candidate = df[
            (df["name"].astype(str) == str(selected[0].get("name", "")))
            & (df["res_number"].astype(str) == str(selected[0].get("res_number", "")))
            & (df["check_in"].astype(str) == str(selected[0].get("check_in", "")))
        ]
        if not candidate.empty:
            row = candidate.iloc[0].to_dict()
            if st.session_state.get("selected_reservation_id") != row.get("id"):
                st.session_state["selected_reservation"] = row
                st.session_state["selected_reservation_id"] = row.get("id")
                st.query_params["sel_id"] = str(row.get("id"))
                st.rerun()


def render_dashboard(df: pd.DataFrame) -> None:
    vip_count = int(df["info"].fillna("").astype(str).str.upper().str.contains("VIP", na=False).sum())
    relaxury_count = int(df.astype(str).apply(lambda column: column.str.upper().str.contains("RELAXURY", na=False)).any(axis=1).sum())
    nights_count = int(pd.to_numeric(df["nights"], errors="coerce").fillna(0).sum())

    # Calcular métricas filtradas para mostrar en el dashboard
    filtered_preview, active_filters = apply_filters(df)
    total_display = len(filtered_preview) if active_filters else len(df)
    total_label = "RESERVAS FILTRADAS" if active_filters else "TOTAL RESERVAS"

    st.markdown(
        f'<div class="summary-grid">'
        f'<div class="summary-card"><div class="summary-label">{total_label} <span></span></div><div class="summary-value">{total_display}</div></div>'
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
        st.markdown(
            '<div class="action-links" style="grid-template-columns:repeat(4,minmax(110px,1fr));max-width:700px">'
            f'<a class="action-link" href="{url_with(action="editar", sel_id=sel_id)}" target="_self" style="background:#D97706">EDITAR</a>'
            f'<a class="action-link" href="{url_with(action="carta", sel_id=sel_id)}" target="_self" style="background:#7C3AED">CARTA</a>'
            f'<a class="action-link" href="{url_with(action="cancelar", sel_id=sel_id)}" target="_self" style="background:#E11D48">BORRAR</a>'
            f'<a class="action-link" href="{url_with(skip_splash="1")}" target="_self" style="background:#3a3a3a">DESELECCIONAR</a>'
            '</div>',
            unsafe_allow_html=True,
        )
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

if action == "nueva":
    render_new_reservation()
elif action == "editar":
    render_edit_reservation()
elif action == "importar":
    render_import()
elif action == "exportar":
    render_export(reservations)
elif action == "agenda":
    render_agenda(reservations)
elif action == "reporte":
    render_report(reservations)
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
    render_letter()
elif action == "cancelar":
    render_delete()
else:
    render_dashboard(reservations)
