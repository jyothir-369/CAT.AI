"""
CSV / XLSX parser — converts tabular data to readable text for embedding.
"""
from typing import Optional


def parse_tabular(raw_bytes: bytes, ext: str = "csv") -> str:
    """
    Extract and format tabular data as readable text.
    Each row becomes a sentence: "Column1: val1, Column2: val2, ..."
    """
    try:
        import pandas as pd
        from io import BytesIO

        buf = BytesIO(raw_bytes)

        if ext in ("xlsx", "xls"):
            df = pd.read_excel(buf, nrows=1000)
        else:
            # CSV / TSV
            try:
                df = pd.read_csv(buf, nrows=1000)
            except Exception:
                buf.seek(0)
                df = pd.read_csv(buf, sep="\t", nrows=1000)

        if df.empty:
            return ""

        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]

        lines = []
        # Header summary
        lines.append(f"Table with {len(df)} rows and columns: {', '.join(df.columns)}")
        lines.append("")

        # Convert each row to text
        for _, row in df.head(200).iterrows():
            parts = []
            for col in df.columns:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    parts.append(f"{col}: {val}")
            if parts:
                lines.append(", ".join(parts))

        return "\n".join(lines)

    except ImportError:
        print("[Parser/CSV_XLSX] pandas not installed")
        return ""
    except Exception as exc:
        print(f"[Parser/CSV_XLSX] Failed: {exc}")
        return ""