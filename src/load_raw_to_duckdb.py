import duckdb
import pandas as pd

DB_PATH = "data/duckdb/iod_dash.duckdb"

# Map of DuckDB table name -> CSV path
FACT_CSVS = {
    "gdp_facts": "data/raw/GDP - gdp_facts.csv",
    "inflation_facts": "data/raw/Inflation - inflation_facts.csv",
    "labour_force_facts": "data/raw/Labour_Force - labour_force_facts.csv",
    "monetary_facts": "data/raw/Monetary - monetary_facts.csv",
    "social_facts": "data/raw/Social - social_facts.csv"
    }


def load_table_from_csv(con: duckdb.DuckDBPyConnection, csv_path: str, table_name: str):
    """
    Load a CSV into DuckDB using DuckDB's native CSV reader.
    This is faster and avoids Pandas-to-DuckDB type conversion errors.
    """
    # Use DuckDB's native read_csv_auto
    con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{csv_path}')")
    
    # Get row count for the print statement
    count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"[LOAD] {table_name} <- {csv_path} ({count} rows)")


def build_econ_facts(con: duckdb.DuckDBPyConnection):
    """
    Build unified econ_facts as UNION ALL of all *_facts tables.

    This keeps whatever columns exist in the fact tables, including
    detail / detail_fa, time_id, value, etc., and adds a fact_table
    column so you know the origin.
    """
    selects = []
    for table_name in FACT_CSVS.keys():
        selects.append(f"SELECT *, '{table_name}' AS fact_table FROM {table_name}")
    union_sql = " UNION ALL ".join(selects)
    con.execute(f"CREATE OR REPLACE TABLE econ_facts AS {union_sql}")
    n = con.execute("SELECT COUNT(*) FROM econ_facts").fetchone()[0]

    print(f"[BUILD] econ_facts created with {n} rows")


if __name__ == "__main__":

    con = duckdb.connect(DB_PATH)

    # Masters (English + Farsi) and geo and sub lookup – same schema, different language in values
    load_table_from_csv(con, "data/raw/master - master_en.csv", "master_en")
    load_table_from_csv(con, "data/raw/master - master_fa.csv", "master_fa")
    load_table_from_csv(con, "data/raw/geo - geo.csv", "geo")
    load_table_from_csv(con, "data/raw/master - sub.csv", "sub")

    # Individual fact tables
    for table_name, csv_path in FACT_CSVS.items():
        load_table_from_csv(con, csv_path, table_name)

    # Unified econ_facts
    build_econ_facts(con)

    con.close()
    print("Done loading all tables into DuckDB.")