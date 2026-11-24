"""Build the real code-list dimensions from reference/codelists/*.json.

  reference/codelists/types.json     -> data/processed/dim_type.*      (132 rows, hierarchical)
  reference/codelists/states.json    -> data/processed/dim_state.*     (4 rows)  -> fact_crime[state]
  reference/codelists/relevance.json -> data/processed/dim_relevance.* (6 rows)  -> fact_crime[relevance]

dim_type is flattened from the source tree (iri_1/2/3 = ancestor codes at
levels 1-3) into code + description + class + immediate parent + level +
top-level category, so Power BI can roll every type up to one of 12 categories.
"""
import json
import re

import pandas as pd

from ..config import CODELISTS_DIR
from ..io import write_small


def load_items(path):
    return json.loads(path.read_text(encoding="utf-8"))["polozky"]


def code_from_iri(iri):
    if not iri:
        return None
    m = re.search(r"/(\d+)$", iri)
    return int(m.group(1)) if m else None


def build_dim_type():
    items = load_items(CODELISTS_DIR / "types.json")
    by_code = {it["kod"]: it for it in items}
    rows = []
    for it in items:
        kod = it["kod"]
        # level & immediate parent from the ancestor chain (root first)
        chain = [a for a in (code_from_iri(it.get(f"iri_{n}")) for n in (1, 2, 3))
                 if a is not None]
        level = len(chain) + 1
        parent = chain[-1] if chain else None
        category = chain[0] if chain else kod   # every code rolls up to a root
        rows.append({
            "type_code": kod,
            "type_name": it["popis"]["cs"],          # specific description
            "type_class": it["nazev"]["cs"],         # short class label
            "parent_code": parent,
            "level": level,
            "category_code": category,
            "category_name": by_code[category]["nazev"]["cs"],
        })
    df = pd.DataFrame(rows).astype({
        "type_code": "int32", "level": "int32", "category_code": "int32",
        "parent_code": "Int32",
    })
    write_small(df, "dim_type")


def build_simple(src, code_col, name_col, out_name):
    items = load_items(src)
    df = pd.DataFrame([{code_col: it["kod"], name_col: it["nazev"]["cs"]}
                       for it in items]).astype({code_col: "int32"})
    write_small(df, out_name)


def main():
    print("Building code-list dimensions ...")
    build_dim_type()
    build_simple(CODELISTS_DIR / "states.json", "state_code", "state_name", "dim_state")
    build_simple(CODELISTS_DIR / "relevance.json", "relevance_code",
                 "relevance_name", "dim_relevance")
    print("Done.")


if __name__ == "__main__":
    main()
