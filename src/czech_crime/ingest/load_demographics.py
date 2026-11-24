"""Build the f_populace demographics fact from the CZSO "pohyb obyvatel" Excel files.

Usage: python -m czech_crime.ingest.load_demographics INPUT_DIR

INPUT_DIR holds the yearly *.xlsx/*.xls files. Output goes to data/processed.
Grain: (year, kod_obec). 2026 is a PLACEHOLDER copied from 2025.
"""
import argparse
from pathlib import Path

import pandas as pd

from ..io import write_small

COL_MAP = {
    "Rok": "year",
    "Číslo\nobce": "kod_obec",
    "Narození": "narozeni",
    "Zemřelí": "zemreli",
    "Přistě-\nhovalí": "pristehovali",
    "Vystě-\nhovalí": "vystehovali",
    "Přírůstek přirozený": "prirustek_prirozeny",
    "Přírůstek migrační": "prirustek_migracni",
    "Přírůstek celkový": "prirustek_celkovy",
    "Stav 31.12.": "populace",
}


def main(folder: Path) -> None:
    files = [*folder.glob("*.xlsx"), *folder.glob("*.xls")]
    df = (
        pd.concat((pd.read_excel(f, usecols=list(COL_MAP)) for f in files),
                  ignore_index=True)
        .rename(columns=COL_MAP)
        .apply(pd.to_numeric, errors="coerce")
        .astype("Int64")
    )
    df = df[df["year"].between(2013, 2025)]

    dup_2026 = df[df["year"].eq(2025)].copy()
    dup_2026["year"] = 2026
    df = (pd.concat([df, dup_2026], ignore_index=True)
          .sort_values(["kod_obec", "year"]).reset_index(drop=True))

    write_small(df, "F_populace", f"  (years {df['year'].min()}-{df['year'].max()})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", type=Path)
    main(ap.parse_args().input_dir)
