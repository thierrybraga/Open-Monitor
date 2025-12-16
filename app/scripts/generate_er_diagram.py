import sys
from pathlib import Path
import argparse
import requests
import sqlalchemy as sa
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.app import create_app
from app.extensions import db

def _type_to_str(t) -> str:
    try:
        return str(t)
    except Exception:
        return type(t).__name__

def build_dot_from_db() -> str:
    inspector = sa.inspect(db.engine)
    tables = sorted([t for t in inspector.get_table_names() if t != 'alembic_version'])
    lines = []
    lines.append('digraph ER {')
    lines.append('  rankdir=LR;')
    lines.append('  node [shape=record, fontsize=10];')
    # Preprocess constraints for FK/UQ flags
    fk_cols_map = {}
    uq_constraints = {}
    for t in tables:
        fk_cols_map[t] = set()
        for fk in inspector.get_foreign_keys(t) or []:
            for c in (fk.get('constrained_columns') or []):
                fk_cols_map[t].add(c)
        uq_constraints[t] = inspector.get_unique_constraints(t) or []

    for t in tables:
        cols = inspector.get_columns(t)
        pk = inspector.get_pk_constraint(t) or {}
        pk_cols = set(pk.get('constrained_columns') or [])
        # Identify single-column UQs
        single_uq_cols = set()
        multi_uq_labels = []
        for uq in uq_constraints.get(t, []):
            cols_uq = uq.get('column_names') or []
            if len(cols_uq) == 1:
                single_uq_cols.add(cols_uq[0])
            elif cols_uq:
                multi_uq_labels.append(f"UNIQUE({','.join(cols_uq)})")

        col_lines = []
        for c in cols:
            name = c.get('name')
            ctype = _type_to_str(c.get('type'))
            nullable = c.get('nullable', True)
            flags = []
            if name in pk_cols:
                flags.append('PK')
            if name in fk_cols_map.get(t, set()):
                flags.append('FK')
            if name in single_uq_cols:
                flags.append('UQ')
            nn = '' if nullable else ' NOT NULL'
            suffix = (' [' + ' '.join(flags) + ']') if flags else ''
            col_lines.append(f"{name}: {ctype}{nn}{suffix}")
        # Append multi-column UQ indicators
        for uq_label in multi_uq_labels:
            col_lines.append(uq_label)

        label = '{' + t + '|' + '\\l'.join(col_lines) + '\\l}'
        lines.append(f'  {t} [label="{label}"];')
    for t in tables:
        fks = inspector.get_foreign_keys(t) or []
        for fk in fks:
            rt = fk.get('referred_table')
            if not rt:
                continue
            src_cols = fk.get('constrained_columns') or []
            dst_cols = fk.get('referred_columns') or []
            if src_cols and dst_cols and len(src_cols) == len(dst_cols):
                pairs = [f"{s}->{d}" for s, d in zip(src_cols, dst_cols)]
                label = '; '.join(pairs)
            else:
                label = ','.join(src_cols) or 'FK'
            lines.append(f'  {t} -> {rt} [label="{label}"];')
    lines.append('}')
    return '\n'.join(lines)

def render_png(dot: str, output_path: Path, timeout: int = 30) -> None:
    payload = {
        'diagram_source': dot,
        'diagram_type': 'graphviz',
        'output_format': 'png',
    }
    resp = requests.post('https://kroki.io/', json=payload, timeout=timeout)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(Path(__file__).resolve().parents[2] / 'er_diagram.png'))
    args = parser.parse_args()
    app = create_app('development')
    with app.app_context():
        dot = build_dot_from_db()
    render_png(dot, Path(args.out))
    print(args.out)

if __name__ == '__main__':
    main()
