"""Run the crime pipeline end to end (demographics are separate: see ingest/load_demographics)."""
from .ingest import download_months
from .transform import assign_areas, build_date_dim, build_dims, build_fact_and_groups


def main() -> None:
    for step in (download_months, assign_areas, build_dims,
                 build_fact_and_groups, build_date_dim):
        print(f"\n=== {step.__name__} ===")
        step.main()


if __name__ == "__main__":
    main()
