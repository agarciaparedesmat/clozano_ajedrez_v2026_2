# ✅ Checklist de pruebas — Torneo Suizo (IDs marcables)

> Marca con [x] cuando completes cada caso. Añade observaciones y adjunta evidencias (capturas, diffs, PDFs, ZIPs).

## A. Backup / Restore (99_Administracion)
- [ ] **A1** Crear backup — ZIP con manifest.json, incluye config/jugadores/meta/standings/admin_log/pairings/flags. Sin excepciones.
- [ ] **A2** Modificar estado/fechas — Cambios reflejados en UI y en `data/meta.json` solo en rondas editadas.
- [ ] **A3** Restaurar backup — Flags y fechas iguales al ZIP; sin backups “fantasma”; sin huérfanos en `data/`.

## B. Fechas de rondas
- [ ] **B1** Editar fecha — `get_round_date(r)` devuelve la nueva fecha; otras fechas intactas.
- [ ] **B2** No-regresión — Editar otro campo no afecta fechas; diff de `meta.json` mínimo.
- [ ] **B3** Post-restore — Fechas coinciden con el backup.
- [ ] **B4** Casos borde — Fechas vacías/invalidas avisan y no corrompen `meta.json`.

## C. Publicación (meta ↔ flags; flujos safe)
- [ ] **C1** Publicar/Despublicar — UI = `meta.rounds[i].published` = existencia `published_Ri.flag`. Sin publicar rondas vacías (o con aviso).
- [ ] **C2** Cerrar/Reabrir — `closed` sincronizado; editor bloquea/avisa si `closed==true`.
- [ ] **C3** Estados cruzados — No se alcanzan estados imposibles (publicada cerrada con huecos, etc.).

## D. PDFs
### D1. Rondas (`pages/10_Rondas.py`)
- [ ] **D1.1** Resultado centrado — entre jugadores en PDF.
- [ ] **D1.2** Doble línea cabecera — trazo doble real.
- [ ] **D1.3** Tipografías fallback — sin tofu; estilo base intacto.
- [ ] **D1.4** Nombres largos/curso — cortes correctos; sin numeración si así se definió.

### D2. Clasificación (`pages/20_Clasificacion.py`)
- [ ] **D2.1** Selector A4/A3 — tamaño correcto; botones alineados.
- [ ] **D2.2** Buchholz opcional — aparece/desaparece en tabla/PDF/CSV.
- [ ] **D2.3** Ancho columnas — sin recortes; orden estable en desempates.

## E. UI global
- [ ] **E1** Navegación consistente — `inject_base_style()` aplicado en todas las páginas.
- [ ] **E2** Cargas/refresh — sin parpadeos que rompan estado.
- [ ] **E3** Accesibilidad — contraste y foco visibles.

## F. Config (`config.json`)
- [ ] **F1** Claves usadas — `pdf_*`, `bg_color`, etc. realmente leídas.
- [ ] **F2** Valores inválidos — aviso y fallback; sin crash.
- [ ] **F3** Compatibilidad — claves opcionales ausentes → defaults sensatos.

## G. Historial / Log
- [ ] **G1** `change_log` — 3 cambios añadidos con timestamp, ronda y tipo (y actor si procede).
- [ ] **G2** Export log — CSV/JSON bien formado (UTF-8).

## H. Datos del torneo (consistencias)
- [ ] **H1** Rondas esperadas — nº de rondas coincide en UI/meta/PDFs.
- [ ] **H2** Duplicados — sin jugadores ni emparejamientos duplicados en la misma ronda.
- [ ] **H3** BYE — BYE 1.0/0.5 coherente en pairings/standings.
- [ ] **H4** Huecos — aviso/bloqueo al publicar/cerrar con resultados incompletos.

## I. CSV/Encoding/Locales
- [ ] **I1** Encoding — tildes/ñ correctas en Excel/LibreOffice (UTF-8).
- [ ] **I2** Formato ES — fechas en UI/PDF según configuración.

## J. Rendimiento
- [ ] **J1** Carga alta — con muchos jugadores, vistas < 2–3 s y PDFs sin desbordes.

---

### Evidencias a adjuntar
- Capturas de UI (antes/después)
- Dif de `data/meta.json`
- PDFs (A4/A3) y CSVs
- ZIP de backup usado
- Notas de tiempos (opcional)