#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Passive verification script for the Swiss tournament project.

Features:
- Read-only checks (no modifications)
- HTML report with semaphores
- Always-on sections: Notes, Recommendations, Round summary
- Per-round CSV export
- Mini SVG charts
- --zip / --remote-zip snapshot support
- --open to launch the HTML report

Usage (examples):
  python verify_tournament.py --strict --html reports/verify_report.html --rounds-csv reports/rounds_summary.csv --open
  python verify_tournament.py --zip backups/backup_2025-09-19.zip --html reports/verify_report.html --rounds-csv reports/rounds_summary.csv --open
  python verify_tournament.py --remote-zip "https://example.com/backup.zip" --html reports/verify_report.html --rounds-csv reports/rounds_summary.csv --open
"""

import argparse
import csv
import glob
import json
import os
import re
import webbrowser
import tempfile
import zipfile
from collections import Counter
from datetime import datetime
from html import escape


# ------------------------- ZIP / Remote helpers -------------------------
def extract_zip_to_temp(zip_path: str) -> str:
    tmpdir = tempfile.mkdtemp(prefix="torneo_")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(tmpdir)
    return tmpdir


def download_file(url: str, dest_path: str) -> None:
    try:
        import requests  # only required if --remote-zip is used
    except Exception as e:
        raise RuntimeError("The 'requests' package is required for --remote-zip. Install it with: pip install requests") from e
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)


def resolve_project_root(args):
    """
    Return a local project root path to run checks against.
    Priority:
      1) --zip: extract and use that directory
      2) --remote-zip: download, extract and use
      3) --project-root (default '.')
    Additionally returns a short note about the resolution.
    """
    if getattr(args, "zip", None):
        z = os.path.abspath(args.zip)
        tmpdir = extract_zip_to_temp(z)
        return tmpdir, f"[source] Local ZIP extracted: {z} -> {tmpdir}"

    if getattr(args, "remote_zip", None):
        tmpzip = os.path.abspath(os.path.join(tempfile.gettempdir(), "torneo_remote.zip"))
        download_file(args.remote_zip, tmpzip)
        tmpdir = extract_zip_to_temp(tmpzip)
        return tmpdir, f"[source] Remote ZIP downloaded: {args.remote_zip} -> {tmpdir}"

    # default: project root
    root = os.path.abspath(getattr(args, "project_root", "."))
    return root, f"[source] Local project: {root}"


# ------------------------- Generic helpers -------------------------
def load_json_safe(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            txt = f.read()
        # Tolerate BOM and comments / trailing commas
        txt = txt.lstrip('\ufeff')
        txt = re.sub(r'//.*?$', '', txt, flags=re.MULTILINE)
        txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.DOTALL)
        txt = re.sub(r',\s*([}\]])', r'\1', txt)
        return json.loads(txt)
    except FileNotFoundError:
        return None
    except Exception as e:
        return {'__error__': f'JSON parse error in {path}: {e}'}


def list_round_files(data_dir):
    pairings = sorted(glob.glob(os.path.join(data_dir, 'pairings_R*.csv')))
    flags = sorted(glob.glob(os.path.join(data_dir, 'published_R*.flag')))
    return pairings, flags


def round_index_from_filename(path):
    m = re.search(r'_R(\d+)\.', os.path.basename(path))
    return int(m.group(1)) if m else None


def read_csv_rows(path):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader), (reader.fieldnames or [])


def detect_columns(header, candidates):
    for c in candidates:
        if c in header:
            return c
    lower = [h.lower() for h in header]
    for c in candidates:
        if c.lower() in lower:
            return header[lower.index(c.lower())]
    return None


# ------------------------- Checks -------------------------
def check_jugadores(data_dir, issues, notes):
    path = os.path.join(data_dir, 'jugadores.csv')
    if not os.path.exists(path):
        issues.append('jugadores.csv not found in data/')
        return
    rows, header = read_csv_rows(path)
    if not rows:
        issues.append('jugadores.csv is empty')
        return
    col_id = detect_columns(header, ['id', 'ID', 'Id', 'player_id'])
    col_name = detect_columns(header, ['nombre', 'name', 'Nombre', 'NOMBRE'])
    if col_id:
        ids = [(r.get(col_id) or '').strip() for r in rows]
        dup_ids = [k for k, v in Counter(ids).items() if k and v > 1]
        if dup_ids:
            issues.append(f'Duplicate player IDs in jugadores.csv: {dup_ids[:5]}{"..." if len(dup_ids) > 5 else ""}')
    elif col_name:
        names = [(r.get(col_name) or '').strip().lower() for r in rows]
        dup_names = [k for k, v in Counter(names).items() if k and v > 1]
        if dup_names:
            issues.append(f'Possible duplicate player NAMES in jugadores.csv: {dup_names[:5]}{"..." if len(dup_names) > 5 else ""}')
    else:
        notes.append('jugadores.csv: could not detect ID or name column; duplicate check skipped.')


def check_meta(data_dir, issues, notes):
    meta_path = os.path.join(data_dir, 'meta.json')
    meta = load_json_safe(meta_path)
    if meta is None:
        notes.append('meta.json not found (will infer from files).')
        return {}, {}
    if '__error__' in meta:
        issues.append(meta['__error__'])
        return {}, {}
    rounds = meta.get('rounds', {})
    if not isinstance(rounds, dict):
        issues.append("meta.json: 'rounds' must be an object/dict.")
        rounds = {}
    schema_errors = []
    for k, v in rounds.items():
        if not isinstance(v, dict):
            schema_errors.append(f'round {k}: not an object')
            continue
        for key in ['published', 'date', 'closed']:
            if key not in v:
                schema_errors.append(f"round {k}: missing key '{key}'")
    if schema_errors:
        issues.extend([f'meta schema: {e}' for e in schema_errors])
    return meta, rounds


def check_rounds_consistency(data_dir, rounds, issues, notes):
    pairings, flags = list_round_files(data_dir)
    rounds_from_pairings = sorted({round_index_from_filename(p) for p in pairings if round_index_from_filename(p)})
    rounds_from_flags = sorted({round_index_from_filename(p) for p in flags if round_index_from_filename(p)})
    meta_published = sorted([int(k) for k, v in rounds.items() if isinstance(v, dict) and v.get('published') is True])

    if meta_published != rounds_from_flags:
        issues.append(f'Mismatch meta published vs flags. meta={meta_published} flags={rounds_from_flags}')

    missing_pairings_for_published = [r for r in meta_published if r not in rounds_from_pairings]
    if missing_pairings_for_published:
        issues.append(f'Published rounds without pairings CSV: {missing_pairings_for_published}')

    orphan_flags = [r for r in rounds_from_flags if str(r) not in rounds]
    if orphan_flags:
        issues.append(f'Orphan published flags without meta entry: {orphan_flags}')

    orphan_pairings = [r for r in rounds_from_pairings if str(r) not in rounds]
    if orphan_pairings:
        notes.append(f'Pairings exist without meta entry (admin tools should complete meta): {orphan_pairings}')

    # completeness of results where a 'resultado' column exists
    for r in rounds_from_pairings:
        path = os.path.join(data_dir, f'pairings_R{r}.csv')
        try:
            rows, header = read_csv_rows(path)
        except Exception as e:
            issues.append(f'Cannot read pairings_R{r}.csv: {e}')
            continue
        col_res = detect_columns(header, ['resultado', 'result', 'Resultado', 'RESULTADO'])
        if not col_res:
            notes.append(f"pairings_R{r}.csv: no 'resultado' column; completeness check skipped.")
            continue
        empties = [i for i, row in enumerate(rows, start=1) if (row.get(col_res) or '').strip() == '']
        if str(r) in rounds and rounds[str(r)].get('published') is True and empties:
            issues.append(f'Round {r} is published but has empty results in rows: {empties[:5]}{"..." if len(empties) > 5 else ""}')


def check_counts_alignment(rounds, data_dir, issues, notes):
    pairings, _ = list_round_files(data_dir)
    num_meta_rounds = len(rounds)
    num_pairings_rounds = len({round_index_from_filename(p) for p in pairings if round_index_from_filename(p)})
    if num_meta_rounds and num_pairings_rounds and num_pairings_rounds > num_meta_rounds:
        notes.append(f'There are more pairings files ({num_pairings_rounds}) than meta rounds ({num_meta_rounds}).')
    if any(v.get('published') for v in rounds.values() if isinstance(v, dict)):
        standings_path = os.path.join(data_dir, 'standings.csv')
        if not os.path.exists(standings_path):
            notes.append('At least one round is published but standings.csv not found (may be generated later).')


# ------------------------- Summary & recommendations -------------------------
def build_round_summary(data_dir, rounds):
    def round_idx(path):
        m = re.search(r'_R(\d+)\.', os.path.basename(path))
        return int(m.group(1)) if m else None

    pairings_files = sorted(glob.glob(os.path.join(data_dir, 'pairings_R*.csv')))
    flags_files = sorted(glob.glob(os.path.join(data_dir, 'published_R*.flag')))
    set_pair = {round_idx(p) for p in pairings_files if round_idx(p)}
    set_flag = {round_idx(p) for p in flags_files if round_idx(p)}
    set_meta = {int(k) for k in rounds.keys()} if isinstance(rounds, dict) else set()

    all_rounds = sorted(set_pair.union(set_flag).union(set_meta))
    summary = {}

    for r in all_rounds:
        item = {
            'round': r,
            'published_meta': bool(rounds.get(str(r), {}).get('published')) if isinstance(rounds, dict) else False,
            'closed_meta': bool(rounds.get(str(r), {}).get('closed')) if isinstance(rounds, dict) else False,
            'date_meta': rounds.get(str(r), {}).get('date') if isinstance(rounds, dict) else '',
            'has_flag': r in set_flag,
            'has_pairings': r in set_pair,
            'pairings_path': os.path.join(data_dir, f'pairings_R{r}.csv') if r in set_pair else '',
            'flag_path': os.path.join(data_dir, f'published_R{r}.flag') if r in set_flag else '',
            'empty_results_count': None,
            'empty_rows_preview': []
        }
        if item['has_pairings']:
            try:
                rows, header = read_csv_rows(item['pairings_path'])
                col_res = detect_columns(header, ['resultado', 'result', 'Resultado', 'RESULTADO'])
                if not col_res:
                    item['empty_results_count'] = None
                else:
                    empties = [i for i, row in enumerate(rows, start=1) if (row.get(col_res) or '').strip() == '']
                    item['empty_results_count'] = len(empties)
                    item['empty_rows_preview'] = empties[:5]
            except Exception:
                item['empty_results_count'] = None
        summary[r] = item

    return summary


def compute_stats(rounds_summary):
    stats = {"total": 0, "published": 0, "not_published": 0, "complete": 0, "with_holes": 0, "no_pairings": 0}
    if not rounds_summary:
        return stats
    for it in rounds_summary.values():
        stats["total"] += 1
        if it.get("published_meta"):
            stats["published"] += 1
        else:
            stats["not_published"] += 1
        if it.get("has_pairings"):
            holes = it.get("empty_results_count")
            if holes and holes > 0:
                stats["with_holes"] += 1
            else:
                stats["complete"] += 1
        else:
            stats["no_pairings"] += 1
    return stats


def build_recommendations(rounds_summary, issues, notes):
    recs = []
    for r, it in sorted(rounds_summary.items()):
        if it['published_meta'] and not it['has_pairings']:
            recs.append(f"R{r}: faltan pairings pero figura publicada → generar pairings o despublicar.")
        if it['published_meta'] and it['empty_results_count'] not in (None, 0):
            recs.append(f"R{r}: publicada con {it['empty_results_count']} huecos de resultado → completar resultados.")
        if bool(it['has_flag']) != bool(it['published_meta']):
            recs.append(f"R{r}: incoherencia meta ↔ flag → resync flags/meta.")
        if it['closed_meta'] and (it['empty_results_count'] not in (None, 0)):
            recs.append(f"R{r}: cerrada pero con huecos → reabrir o completar.")
    for msg in issues:
        if 'Duplicate player IDs' in msg or 'duplicate player NAMES' in msg:
            recs.append('Duplicados en jugadores.csv → unificar IDs/nombres antes de emparejar.')
    for msg in notes:
        if 'Pairings exist without meta entry' in msg:
            recs.append('Hay pairings sin entrada en meta → completar meta desde Admin.')
    # dedupe
    seen, unique = set(), []
    for r in recs:
        if r not in seen:
            unique.append(r)
            seen.add(r)
    return unique


# ------------------------- HTML rendering -------------------------
def render_html(project_root, issues, notes, data_dir, lib_dir, pages_dir, out_path,
                rounds_summary=None, recs=None, csv_path=None, stats=None):
    css = (
        "body{font-family:system-ui,Segoe UI,Roboto; background:#0b1020; color:#e5e7eb; margin:0}"
        ".wrap{max-width:1100px;margin:40px auto;padding:0 20px}"
        "h1{font-size:24px} h2{font-size:18px;margin-top:24px}"
        "table{width:100%;border-collapse:collapse;margin-top:12px}"
        "th,td{border:1px solid #1f2937;padding:8px 10px;text-align:left}"
        "th{background:#111826} a{color:#93c5fd}"
        ".small{color:#cbd5e1;font-size:12px} .chart{margin:12px 0}"
    )
    status_ok = not issues
    title = '✅ Verificación OK' if status_ok else '⚠️ Incidencias detectadas'

    html = []
    html.append("<!doctype html><html lang='es'><head><meta charset='utf-8'>")
    html.append(f"<title>Verificación Torneo | {escape(project_root)}</title><style>{css}</style></head><body>")
    html.append("<div class='wrap'>")
    html.append(f"<h1>{escape(title)}</h1>")
    html.append(f"<div class='small'>Proyecto: <strong>{escape(project_root)}</strong> · Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>")
    html.append("<p class='small'>")
    html.append(f"Data dir: {escape(data_dir)}<br>Lib dir: {escape(lib_dir)}<br>Pages dir: {escape(pages_dir)}")
    html.append("</p>")
    if csv_path:
        html.append(f"<p class='small'>CSV de resumen por ronda: <a href='{escape(csv_path)}'>{escape(csv_path)}</a></p>")

    # Charts
    if stats and stats.get("total", 0) > 0:
        pub, npub = stats.get("published", 0), stats.get("not_published", 0)
        comp, holes, nop = stats.get("complete", 0), stats.get("with_holes", 0), stats.get("no_pairings", 0)
        total = stats.get("total", 0)

        def bar(vals, cols):
            total_val = sum(vals) or 1
            widths = [100 * v / total_val for v in vals]
            x = 0
            parts = []
            for w, c in zip(widths, cols):
                parts.append(f"<rect x='{x:.2f}%' y='0' width='{w:.2f}%' height='16' fill='{c}'></rect>")
                x += w
            return "<svg viewBox='0 0 100 16' preserveAspectRatio='none'>" + "".join(parts) + "</svg>"

        html.append("<h2>Gráficos rápidos</h2>")
        html.append("<div class='chart'><div class='small'>Publicadas vs No publicadas</div>"
                    + bar([pub, npub], ["#16a34a", "#6b7280"])
                    + f"<div class='small'>Publicadas: {pub} · No publicadas: {npub} · Total: {total}</div></div>")
        html.append("<div class='chart'><div class='small'>Estado de resultados</div>"
                    + bar([comp, holes, nop], ["#16a34a", "#f59e0b", "#374151"])
                    + f"<div class='small'>Completas: {comp} · Con huecos: {holes} · Sin pairings: {nop}</div></div>")

    # Issues
    if issues:
        html.append("<h2>Incidencias (⚠️)</h2><ul>")
        for msg in issues:
            html.append(f"<li>⚠️ {escape(msg)}</li>")
        html.append("</ul>")
    else:
        html.append("<h2>Incidencias</h2><p>✅ Sin incidencias.</p>")

    # Notes (always visible)
    html.append("<h2>Notas (ℹ️)</h2>")
    if notes:
        html.append("<ul>")
        for msg in notes:
            html.append(f"<li>ℹ️ {escape(msg)}</li>")
        html.append("</ul>")
    else:
        html.append("<p>— Ninguna —</p>")

    # Recommendations (always visible)
    html.append("<h2>Recomendaciones automáticas</h2>")
    if recs:
        html.append("<ul>")
        for msg in recs:
            html.append(f"<li>👉 {escape(msg)}</li>")
        html.append("</ul>")
    else:
        html.append("<p>— Ninguna —</p>")

    # Round summary (always)
    html.append("<h2>Resumen por ronda</h2>")
    if rounds_summary:
        html.append("<table><thead><tr>"
                    "<th>Ronda</th><th>Publicado</th><th>Flag</th><th>Cerrada</th><th>Fecha</th><th>Pairings</th><th>Huecos</th>"
                    "</tr></thead><tbody>")
        for r in sorted(rounds_summary.keys()):
            it = rounds_summary[r]
            def b(x): return "Sí" if x else "No"
            pair = f"<a href='{it['pairings_path']}'>{os.path.basename(it['pairings_path'])}</a>" if it['pairings_path'] else "—"
            flag = f"<a href='{it['flag_path']}'>{os.path.basename(it['flag_path'])}</a>" if it['flag_path'] else "—"
            holes = it['empty_results_count']
            if holes is None and it['has_pairings']:
                holes_cell = "?"
            elif not it['has_pairings']:
                holes_cell = "—"
            else:
                prev = ", ".join(map(str, it['empty_rows_preview'])) if holes else ""
                holes_cell = str(holes) + (f" (filas {prev})" if prev else "")
            html.append("<tr>"
                        f"<td>R {it['round']}</td>"
                        f"<td>{b(it['published_meta'])}</td>"
                        f"<td>{b(it['has_flag'])} {flag}</td>"
                        f"<td>{b(it['closed_meta'])}</td>"
                        f"<td>{escape(it['date_meta'] or '—')}</td>"
                        f"<td>{b(it['has_pairings'])} {pair}</td>"
                        f"<td>{holes_cell}</td>"
                        "</tr>")
        html.append("</tbody></table>")
    else:
        html.append("<p>No se detectaron rondas en meta.json ni archivos pairings/flags en data/.</p>")

    html.append("<hr><p class='small'>Generado por verify_tournament.py — HTML con semáforos, recomendaciones, gráficos y resumen por ronda.</p>")
    html.append("</div></body></html>")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("".join(html))


# ------------------------- CSV export -------------------------
def export_rounds_csv(rounds_summary, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fields = ['round', 'published_meta', 'has_flag', 'closed_meta', 'date_meta',
              'has_pairings', 'pairings_path', 'flag_path', 'empty_results_count', 'empty_rows_preview']
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sorted(rounds_summary.keys()):
            it = rounds_summary[r].copy()
            it['empty_rows_preview'] = ','.join(map(str, it.get('empty_rows_preview', [])))
            w.writerow(it)


# ------------------------- Orchestration -------------------------
def run_checks(project_root):
    data_dir = os.path.join(project_root, 'data')
    lib_dir = os.path.join(project_root, 'lib')
    pages_dir = os.path.join(project_root, 'pages')

    issues, notes = [], []

    # Required (bloqueantes)
    required = [
        data_dir,
        os.path.join(project_root, 'config.json'),
        os.path.join(data_dir, 'jugadores.csv')
    ]
    for pth in required:
        if not os.path.exists(pth):
            issues.append(f'Missing required path: {pth}')

    # Opcionales (no bloquean; útiles cuando el ZIP es mínimo de data/)
    if not os.path.exists(lib_dir):
        notes.append(f'Optional path missing (ok for ZIP snapshots): {lib_dir}')
    if not os.path.exists(pages_dir):
        notes.append(f'Optional path missing (ok for ZIP snapshots): {pages_dir}')

    check_jugadores(data_dir, issues, notes)
    meta, rounds = check_meta(data_dir, issues, notes)
    check_rounds_consistency(data_dir, rounds, issues, notes)
    check_counts_alignment(rounds, data_dir, issues, notes)
    return data_dir, lib_dir, pages_dir, issues, notes, rounds


def main():
    ap = argparse.ArgumentParser(description='Passive verifier for Swiss tournament with HTML report + CSV export.')
    ap.add_argument('--project-root', default='.', help='Project root path')
    ap.add_argument('--strict', action='store_true', help='Exit with code 1 if any issues are found')
    ap.add_argument('--html', default=None, help='Path to write an HTML report (e.g., reports/verify_report.html)')
    ap.add_argument('--rounds-csv', default=None, help='Path to write CSV per-round summary (e.g., reports/rounds_summary.csv)')
    ap.add_argument('--zip', default=None, help='Path to a local backup ZIP containing data/, lib/, pages/, config.json')
    ap.add_argument('--remote-zip', default=None, help='URL to download a backup ZIP (requires requests)')
    ap.add_argument('--open', action='store_true', help='Open the HTML report after generation')
    args = ap.parse_args()

    # resolve root (local / zip / remote-zip)
    root, source_note = resolve_project_root(args)

    data_dir, lib_dir, pages_dir, issues, notes, rounds = run_checks(root)

    print('== Swiss Tournament Passive Verification ==')
    print(source_note)
    print(f'Project root : {root}')
    print(f'Data dir     : {data_dir}')
    print(f'Lib dir      : {lib_dir}')
    print(f'Pages dir    : {pages_dir}')
    print('--------------------------------------------------')
    if issues:
        print(f'Issues ({len(issues)}):')
        for i, msg in enumerate(issues, 1):
            print(f'  [{i}] ⚠️  {msg}')
    else:
        print('No blocking issues found. ✅')
    if notes:
        print(f'Notes ({len(notes)}):')
        for i, msg in enumerate(notes, 1):
            print(f'  [{i}] ℹ️  {msg}')

    rounds_summary = build_round_summary(data_dir, rounds)
    recs = build_recommendations(rounds_summary, issues, notes)
    stats = compute_stats(rounds_summary)

    if args.html:
        out_path = os.path.abspath(args.html)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        render_html(root, issues, notes, data_dir, lib_dir, pages_dir, out_path,
                    rounds_summary=rounds_summary, recs=recs, csv_path=args.rounds_csv, stats=stats)
        print(f'\nHTML report written to: {out_path}')
        if args.open:
            try:
                webbrowser.open(out_path)
            except Exception:
                pass

    if args.rounds_csv:
        csv_out = os.path.abspath(args.rounds_csv)
        export_rounds_csv(rounds_summary, csv_out)
        print(f'CSV summary written to: {csv_out}')

    if args.strict and issues:
        raise SystemExit(1)
    else:
        raise SystemExit(0)


if __name__ == '__main__':
    main()
