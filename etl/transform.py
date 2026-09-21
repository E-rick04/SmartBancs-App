from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "etl_test_transaction.csv"
OUTPUT_DIR = BASE_DIR / "output"

def run_etl(input_file: Path = INPUT_FILE, output_dir: Path = OUTPUT_DIR) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(input_file)

    df["currency"] = df["currency"].astype("string").str.strip().str.upper()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True, format="mixed")

    duplicate_mask = df.duplicated(subset=["transaction_id"], keep="first")
    issues = {
        "missing_transaction_id": int(df["transaction_id"].isna().sum()),
        "missing_or_invalid_amount": int(df["amount"].isna().sum()),
        "non_positive_amount": int((df["amount"] <= 0).sum()),
        "invalid_date": int(df["date"].isna().sum()),
        "invalid_currency": int((df["currency"].isna() | ~df["currency"].str.fullmatch(r"[A-Z]{3}").fillna(False)).sum()),
        "duplicate_transaction_id": int(duplicate_mask.sum()),
    }
    invalid_mask = (
        df["transaction_id"].isna()
        | df["amount"].isna()
        | (df["amount"] <= 0)
        | df["date"].isna()
        | df["currency"].isna()
        | ~df["currency"].str.fullmatch(r"[A-Z]{3}").fillna(False)
        | duplicate_mask
    )

    valid = df.loc[~invalid_mask].copy()
    rejected = df.loc[invalid_mask].copy()
    valid["date"] = valid["date"].dt.strftime("%Y-%m-%d")
    rejected["date"] = rejected["date"].dt.strftime("%Y-%m-%d")
    valid.to_csv(output_dir / "clean_transactions.csv", index=False)
    rejected.to_csv(output_dir / "rejected_transactions.csv", index=False)

    return {
        "input_rows": len(df),
        "valid_rows": len(valid),
        "rejected_rows": len(rejected),
        "duplicates": int(duplicate_mask.sum()),
        "issues": issues,
    }


if __name__ == "__main__":
    print(run_etl())
