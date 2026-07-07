"""Build the real code-list dimensions from dims/*.json.

  dims/types.json     -> model/dim_type.*      (132 rows, hierarchical)
  dims/states.json    -> model/dim_state.*     (4 rows)  -> fact_crime[state]
  dims/relevance.json -> model/dim_relevance.* (6 rows)  -> fact_crime[relevance]

dim_type is flattened from the source tree (iri_1/2/3 = ancestor codes at
levels 1-3) into code + description + class + immediate parent + level +
top-level category, so Power BI can roll every type up to one of 12 categories.
"""
import json
import os
import re

import pandas as pd

OUT = "model"


def code_from_iri(iri):
    if not iri:
        return None
    m = re.search(r"/(\d+)$", iri)
    return int(m.group(1)) if m else None


def write(df, name):
    df.to_parquet(os.path.join(OUT, f"{name}.parquet"), index=False)
    df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False, encoding="utf-8")
    print(f"  {name}: {len(df):,} rows")


def build_dim_type():
    items = json.load(open("dims/types.json", encoding="utf-8"))["polozky"]
    by_code = {it["kod"]: it for it in items}
    rows = []
    for it in items:
        kod = it["kod"]
        a1 = code_from_iri(it.get("iri_1"))   # level-1 ancestor (root)
        a2 = code_from_iri(it.get("iri_2"))
        a3 = code_from_iri(it.get("iri_3"))
        # level & immediate parent from the ancestor chain
        chain = [a for a in (a1, a2, a3) if a is not None]
        level = len(chain) + 1
        parent = chain[-1] if chain else None
        category = a1 if a1 is not None else kod   # every code rolls up to a root
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
    write(df, "dim_type")


def build_simple(src, code_col, name_col, out_name):
    items = json.load(open(src, encoding="utf-8"))["polozky"]
    df = pd.DataFrame([{code_col: it["kod"], name_col: it["nazev"]["cs"]}
                       for it in items]).astype({code_col: "int32"})
    write(df, out_name)


def main():
    os.makedirs(OUT, exist_ok=True)
    print("Building code-list dimensions ...")
    build_dim_type()
    build_simple("dims/states.json", "state_code", "state_name", "dim_state")
    build_simple("dims/relevance.json", "relevance_code", "relevance_name",
                 "dim_relevance")
    print("Done.")


if __name__ == "__main__":
    main()
