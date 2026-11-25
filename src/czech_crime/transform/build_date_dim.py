"""Build a conformed daily date dimension for the semantic model.

Covers full calendar years spanning the data (derived from fact_crime), one
contiguous row per day with no gaps. Joins fact_crime[crime_date] on `Date`.
Column names are final (they are what the semantic model shows), so the
crime.mv_d_date lake view is a pass-through. Mark this as the Date table in
Power BI.
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

# Invisible suffixes that keep repeated initials distinct (J/J/J, L/L, Č/Č):
# Power BI's sort-by-column needs exactly one Month per label.
_SPACERS = ["", "\u2009", "\u200a"]  # none, thin space, hair space


def month_letters(names):
    """Map 12 month names to unique one-letter labels, in month order."""
    seen, out = {}, []
    for name in names:
        letter = name[0].upper()
        n = seen.get(letter, 0)
        seen[letter] = n + 1
        out.append(letter + _SPACERS[n])
    return out


def main():
    # Full calendar years spanning the fact's date range
    dates = pq.read_table(str(FACT), columns=["crime_date"]).column("crime_date")
    mm = pc.min_max(dates).as_py()
    lo, hi = mm["min"], mm["max"]
    start = pd.Timestamp(year=lo.year, month=1, day=1)
    end = pd.Timestamp(year=hi.year, month=12, day=31)
    print(f"Building dim_date {start.date()} .. {end.date()} (data span {lo} .. {hi}) ...")

    d = pd.date_range(start, end, freq="D")
    letters = month_letters(pd.date_range("2000-01-01", periods=12, freq="MS").strftime("%B"))
    letters_cs = month_letters(MONTHS_CS)
    df = pd.DataFrame({
        "Date": d.date,
        "Year": d.year.astype("int32"),
        "YearQuarter": [f"{y}-Q{q}" for y, q in zip(d.year, d.quarter)],
        "Quarter": d.quarter.astype("int32"),
        "yearmonth": d.strftime("%Y-%m"),
        "YearMonthNumber": (d.year * 100 + d.month).astype("int32"),
        "Month": d.month.astype("int32"),
        "MonthName": d.strftime("%B"),
        "MonthNameCs": [MONTHS_CS[m - 1] for m in d.month],
        "MonthLetter": [letters[m - 1] for m in d.month],
        "MonthLetterCs": [letters_cs[m - 1] for m in d.month],
        "DayofMonth": d.day.astype("int32"),
        "DayofWeek": d.day_of_week.astype("int32") + 1,  # 1=Mon..7=Sun
        "DayName": d.strftime("%A"),
        "DayNameCs": [DAYS_CS[wd] for wd in d.day_of_week],
        "isWeekend": d.day_of_week >= 5,
    })
    write_small(df, "dim_date", f"  ({df['Date'].min()} .. {df['Date'].max()})")
    print("Done.")


if __name__ == "__main__":
    main()
