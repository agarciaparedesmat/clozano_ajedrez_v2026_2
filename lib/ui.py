# lib/ui.py
# -*- coding: utf-8 -*-
import streamlit as st

# Paleta dominante extraída de tus imágenes:
# #242024 (texto), #545663 (muted), #8A847B (taupe),
# #D4A680 (acento arena), #73C0EE (azul), #C2BFC7 (gris claro), #EBE6DD (crema)

_BASE_CSS = """
<style>
/* Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Nunito:wght@600;700;800&display=swap');

/* Variables de marca */
:root{
  --brand: #73C0EE;
  --brand-600: #4BAAE4;
  --brand-700: #2E9BD6;
  --accent: #D4A680;
  --text: #242024;
  --muted: #545663;
  --panel: #F6F4EF;
  --chip-green: #16A34A;
  --chip-yellow: #F59E0B;
  --chip-red: #DC2626;
}

/* Tipografías */
html, body, [class*="css"] {
  font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial, "Noto Sans", sans-serif !important;
  color: var(--text);
}

/* Titulares un pelín más marcados */
h1, h2, h3 {
  font-family: 'Nunito', 'Inter', sans-serif !important;
}

/* Paneles */
.block-container {
  padding-top: 1.2rem;
}

/* Botones Streamlit (button, download_button, link_button) */
.stButton > button, .stDownloadButton > button, .stLinkButton > a, .stLinkButton > button {
  background: linear-gradient(180deg, var(--brand) 0%, var(--brand-600) 100%);
  color: #0b1220;
  border: 1px solid rgba(36,32,36,0.08);
  border-radius: 12px;
  padding: 0.6rem 1rem;
  font-weight: 700;
  letter-spacing: 0.2px;
  box-shadow: 0 6px 14px rgba(115,192,238,0.25);
}
.stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover, .stLinkButton > button:hover {
  background: linear-gradient(180deg, var(--brand-600) 0%, var(--brand-700) 100%);
  transform: translateY(-1px);
}

/* Chips simples (para HTML manual) */
.app-chip {
  display:inline-block; padding:0.25rem 0.55rem; border-radius:999px;
  font-size:0.85rem; font-weight:700; line-height:1; margin-right:0.25rem;
}
.app-chip.green  { background: rgba(22,163,74,0.12); color: var(--chip-green); border:1px solid rgba(22,163,74,0.25);}
.app-chip.yellow { background: rgba(245,158,11,0.12); color: var(--chip-yellow); border:1px solid rgba(245,158,11,0.25);}
.app-chip.red    { background: rgba(220,38,38,0.12); color: var(--chip-red); border:1px solid rgba(220,38,38,0.25);}

/* Cabecera reutilizable */
.app-header {
  padding: 1rem 1.25rem;
  border-radius: 14px;
  background: linear-gradient(90deg, rgba(115,192,238,0.16) 0%, rgba(210,225,238,0.10) 100%);
  border: 1px solid rgba(36,32,36,0.08);
  margin-bottom: 0.9rem;
}
.app-header h1 {
  font-size: 1.4rem; margin:0; line-height:1.25;
}
.app-header p {
  margin: 0.35rem 0 0 0; color: var(--muted); font-size: 0.98rem;
}

/* Tarjetas de portada */
.hero {
  border-radius: 18px; padding: 1.2rem 1.4rem;
  background: linear-gradient(135deg, #EBF5FD 0%, #FFFDF7 100%);
  border: 1px solid rgba(36,32,36,0.06);
  margin-bottom: 1rem;
}
.hero h1 { font-size: 1.9rem; margin: 0 0 0.3rem 0;}
.hero p  { margin: 0; color: var(--muted); }

.card-link {
  display:block; text-decoration:none; color:inherit;
  background: var(--panel);
  border:1px solid rgba(36,32,36,0.08);
  border-radius: 14px; padding: 1rem;
  transition: transform .08s ease, box-shadow .2s ease;
}
.card-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(36,32,36,0.10);
}
.card-title { font-family:'Nunito', 'Inter', sans-serif; font-weight:800; font-size:1.1rem; margin:0 0 0.25rem 0;}
.card-desc  { color: var(--muted); font-size:0.95rem; margin:0; }
</style>
"""

# lib/ui.py
import streamlit as st

def inject_base_style(bg_color: str | None = None) -> None:
    """
    Inyecta CSS base (fondo + paleta) para toda la app.
    Lee de config.json:
      - theme_mode: "system" | "light" | "dark" | "auto_by_hour"
      - bg_color (claro) y bg_color_dark (oscuro)
    Si theme_mode="system", respeta el ajuste del SO (prefers-color-scheme).
    Si theme_mode="auto_by_hour", usa hora local de Europa/Madrid (20:00–07:59 = oscuro).
    """
    # Cargar configuración sin depender a nivel de módulo (evita ciclos)
    try:
        from lib.tournament import load_config
        cfg = load_config()
    except Exception:
        cfg = {}

    # Paletas por defecto
    light = {
        "bg": (bg_color or cfg.get("bg_color") or "#F7F5F0").strip(),
        "panel": "#FFFFFF",
        "text": "#222222",
        "muted": "rgba(34,34,34,.65)",
        "link": "#0B74DE",
        "border": "rgba(36,32,36,.10)",
    }
    dark = {
        "bg": (cfg.get("bg_color_dark") or "#0D1117").strip(),
        "panel": "#10161F",
        "text": "#EDEEF0",
        "muted": "rgba(237,238,240,.65)",
        "link": "#58A6FF",
        "border": "rgba(255,255,255,.12)",
    }

    mode = (cfg.get("theme_mode") or "system").lower()

    def _css_vars(p):  # genera bloque :root con variables de una paleta
        return f"""
        :root {{
          --app-bg: {p["bg"]};
          --panel: {p["panel"]};
          --text: {p["text"]};
          --muted: {p["muted"]};
          --link: {p["link"]};
          --border: {p["border"]};
        }}
        """

    css = "<style>"

    if mode == "dark":
        css += _css_vars(dark)
    elif mode == "light":
        css += _css_vars(light)
    elif mode == "auto_by_hour":
        # Oscuro entre 20:00 y 08:00 en Europa/Madrid
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo  # Py3.9+
            hour = datetime.now(ZoneInfo("Europe/Madrid")).hour
        except Exception:
            hour = datetime.now().hour  # Fallback al TZ del servidor
        palette = dark if (hour >= 20 or hour < 8) else light
        css += _css_vars(palette)
    else:
        # "system": claro por defecto + override si el SO/ navegador está en oscuro
        css += _css_vars(light)
        css += f"""
        @media (prefers-color-scheme: dark) {{
          {_css_vars(dark)}
        }}
        """

    # Estilos comunes
    css += """
    /* Fondo global + colores de texto/enlaces */
    [data-testid="stAppViewContainer"] { background: var(--app-bg) !important; }
    .stApp, .block-container { color: var(--text); }
    a, .stLinkButton a { color: var(--link) !important; }

    /* Paneles */
    .stButton>button, .stDownloadButton>button,
    .stTextInput>div>div>input, .stSelectbox>div>div>div,
    .stDataFrame, .stDataEditor, .stAlert, .stExpander,
    .st-emotion-cache-16txtl3, .st-emotion-cache-1r4qj8v {
      border-color: var(--border) !important;
    }
    [data-testid="stSidebar"] > div:first-child {
      background: var(--panel) !important;
      border-right: 1px solid var(--border);
    }

    /* Header translúcido */
    [data-testid="stHeader"] {
      background: linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0)) !important;
      backdrop-filter: blur(6px);
    }

    /* Tablas sencillas tuyas */
    .state-table thead th { background: rgba(115,192,238,0.12); color: var(--text); }
    .state-table tbody td { background: #fff; }

    /* Botones tipo tarjeta (page_link) */
    .stLinkButton { width: 100% !important; }
    .stLinkButton > a {
      display: block !important;
      width: 100% !important;
      text-decoration: none !important;
      color: var(--text) !important;
      background: var(--panel) !important;
      border: 1px solid var(--border) !important;
      border-radius: 14px !important;
      padding: 1rem 1.1rem !important;
      font-weight: 800 !important;
      font-size: 1.05rem !important;
      box-shadow: none !important;
      transition: transform .08s ease, box-shadow .2s ease;
    }
    .stLinkButton > a:hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 22px rgba(36,32,36,0.10);
    }

    .card-desc { color: var(--muted); font-size: .95rem; margin-top: .35rem; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    inject_base_style()
    html = f"<div class='app-header'><h1>{title}</h1>"
    if subtitle:
        html += f"<p>{subtitle}</p>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def hero_portada(title: str, subtitle: str = ""):
    inject_base_style()
    html = f"<div class='hero'><h1>{title}</h1>"
    if subtitle:
        html += f"<p>{subtitle}</p>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def chip(text: str, kind: str = "green"):
    kind = kind if kind in ("green","yellow","red") else "green"
    st.markdown(f"<span class='app-chip {kind}'>{text}</span>", unsafe_allow_html=True)
