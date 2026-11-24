"""Build a conformed daily date dimension for the semantic model.

Covers full calendar years spanning the data (derived from fact_crime), one
contiguous row per day with no gaps. Keyed by an integer YYYYMMDD `date_key`
that matches fact_crime[date_key]. Mark this as the Date table in Power BI.
"""

import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

from ..config import PROCESSED_DIR
from ..io import write_small

FACT = PROCESSED_DIR / "fact_crime.parquet"

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


def main():
    # Full calendar years spanning the fact's date range
    keys = pq.read_table(str(FACT), columns=["date_key"]).column("date_key")
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
        "day_of_week": d.day_of_week.astype("int32") + 1,  # 1=Mon..7=Sun
        "day_name": d.strftime("%A"),
        "day_name_cs": [DAYS_CS[wd] for wd in d.day_of_week],
        "day_of_year": d.day_of_year.astype("int32"),
        "iso_week": iso["week"].to_numpy().astype("int32"),
        "iso_year": iso["year"].to_numpy().astype("int32"),
        "is_weekend": (d.day_of_week >= 5),
    })
    write_small(df, "dim_date",
                f"  ({df['date'].min()} .. {df['date'].max()})")
    print("Done.")


if __name__ == "__main__":
    main()
