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

def inject_base_style(bg_color: str | None = None) -> None:
    """
    Inyecta CSS base para toda la app, incluyendo:
      - color de fondo global (o gradient) tomado de config.json (clave 'bg_color')
      - header con leve degradado y blur
      - pequeños ajustes de padding
    Puedes forzar un color pasando bg_color="...".
    """
    if bg_color is None:
        try:
            # Importamos aquí para evitar dependencias circulares a nivel de módulo
            from lib.tournament import load_config
            cfg = load_config()
            bg_color = (cfg.get("bg_color") or "#F7F5F0").strip()
        except Exception:
            bg_color = "#F7F5F0"

    css = f"""
    <style>
    :root {{
      --app-bg: {bg_color};
    }}
    /* Área principal */
    [data-testid="stAppViewContainer"] {{
      background: var(--app-bg) !important;
    }}
    /* Header translúcido */
    [data-testid="stHeader"] {{
      background: linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0)) !important;
      backdrop-filter: blur(6px);
    }}
    /* Un poco de aire en el contenido */
    .block-container {{
      padding-top: 1.2rem;
      padding-bottom: 2rem;
    }}
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



def sidebar_title(text: str | None = None) -> None:
    """
    Muestra un título en la barra lateral. Si no se pasa texto,
    usa cfg['titulo'] desde config.json.
    """
    if text is None:
        try:
            from lib.tournament import load_config
            cfg = load_config()
            text = (cfg.get("titulo") or "Ajedrez en los recreos").strip()
        except Exception:
            text = "Ajedrez en los recreos"
    # Estilo compacto y consistente
    st.sidebar.markdown(
        f"""
        <div style="font-weight:800; font-size:1.05rem; line-height:1.2; margin:.25rem 0 .6rem 0;">
          {text}
        </div>
        <hr style="margin:.2rem 0 .9rem 0; border:none; border-top:1px solid var(--border);" />
        """,
        unsafe_allow_html=True,
    )
