
# Torneo Suizo Escolar — v7 Baseline Seguro
- Multipágina con **nombres ASCII** (evita problemas de path/encoding).
- **Sin PDFs** (se pueden añadir luego). Nada crashea por librerías ausentes.
- Admin: seed visible para R1, BYE forzado, publicar/bloquear, eliminar ronda,
  subir/reemplazar pairings CSV, editar resultados, calcular y guardar clasificación.
- Emparejador suizo con preferencia de color y **evita 3 colores seguidos**.

## Despliegue
1. Sube a GitHub y despliega en Streamlit Cloud apuntando a `app.py`.
2. En *Secrets*: `ADMIN_PASS = "tu-clave"`.
3. Sube `data/jugadores.csv` desde Admin.

## Formatos
- `jugadores.csv`: `id,nombre,apellido1,apellido2,curso,grupo,estado`
- `pairings_RN.csv`: `mesa,blancas_id,blancas_nombre,negras_id,negras_nombre,resultado`
