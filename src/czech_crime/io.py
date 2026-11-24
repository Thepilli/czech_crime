"""Shared output helpers."""
import pandas as pd

from .config import PROCESSED_DIR


def write_small(df: pd.DataFrame, name: str, note: str = "") -> None:
    """Write a small table as both parquet and csv under data/processed."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
    df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False, encoding="utf-8")
    print(f"  {name}: {len(df):,} rows{note}")
