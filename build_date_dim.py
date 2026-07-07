"""Build a conformed daily date dimension for the semantic model.

Covers full calendar years spanning the data (derived from fact_crime), one
contiguous row per day with no gaps. Keyed by an integer YYYYMMDD `date_key`
that matches fact_crime[date_key]. Mark this as the Date table in Power BI.
"""

import os

import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

OUT = "model"
FACT = os.path.join(OUT, "fact_crime.parquet")

MONTHS_CS = [
    "leden",
    "únor",
    "březen",
    "duben",
    "květen",
    "červen",
    "červenec",
    "srpen",
    "září",
    "říjen",
    "listopad",
    "prosinec",
]
DAYS_CS = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]


def write(df, name):
    df.to_parquet(os.path.join(OUT, f"{name}.parquet"), index=False)
    df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False, encoding="utf-8")
    print(f"  {name}: {len(df):,} rows  ({df['date'].min()} .. {df['date'].max()})")


def main():
    # Full calendar years spanning the fact's date range
    keys = pq.read_table(FACT, columns=["date_key"]).column("date_key")
    mm = pc.min_max(keys).as_py()
    lo, hi = mm["min"], mm["max"]
    start = pd.Timestamp(year=lo // 10000, month=1, day=1)
    end = pd.Timestamp(year=hi // 10000, month=12, day=31)
    print(
        f"Building dim_date {start.date()} .. {end.date()} (data span {lo} .. {hi}) ..."
    )

    d = pd.date_range(start, end, freq="D")
    iso = d.isocalendar()
    df = pd.DataFrame({
        "date_key": (d.year * 10000 + d.month * 100 + d.day).astype("int32"),
        "date": d.date,
        "year": d.year.astype("int32"),
        "quarter": d.quarter.astype("int32"),
        "year_quarter": [f"{y}-Q{q}" for y, q in zip(d.year, d.quarter)],
        "month": d.month.astype("int32"),
        "month_name": d.strftime("%B"),
        "month_name_cs": [MONTHS_CS[m - 1] for m in d.month],
        "year_month": d.strftime("%Y-%m"),
        "month_start": d.to_period("M").to_timestamp().date,
        "day": d.day.astype("int32"),
        "day_of_week": d.dayofweek.astype("int32") + 1,  # 1=Mon..7=Sun
        "day_name": d.strftime("%A"),
        "day_name_cs": [DAYS_CS[wd] for wd in d.dayofweek],
        "day_of_year": d.dayofyear.astype("int32"),
        "iso_week": iso["week"].to_numpy().astype("int32"),
        "iso_year": iso["year"].to_numpy().astype("int32"),
        "is_weekend": (d.dayofweek >= 5),
    })
    os.makedirs(OUT, exist_ok=True)
    write(df, "dim_date")
    print("Done.")


if __name__ == "__main__":
    main()
