from pathlib import Path
from typing import Any

import pandas as pd


def load_structured_file(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)
    if suffix == ".json":
        return _load_json_as_dataframe(file_path)

    raise ValueError(f"Unsupported file type: {suffix}")


def _load_json_as_dataframe(path: Path) -> pd.DataFrame:
    data: Any = pd.read_json(path)
    if isinstance(data, pd.DataFrame):
        return data
    return pd.DataFrame(data)
