"""File loaders for supported dataset formats (MASTER_PROMPT.md §4).

Deterministic, no LLM involved. Loaders never execute anything contained in
the uploaded file: pandas/openpyxl/pyarrow only parse tabular data, they do
not evaluate formulas, macros, or arbitrary code.
"""

import csv
import io
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from charset_normalizer import from_bytes
from openpyxl import load_workbook

from app.models.session import FileType

_EXTENSION_MAP: dict[str, FileType] = {
    ".csv": FileType.CSV,
    ".tsv": FileType.TSV,
    ".xlsx": FileType.EXCEL,
    ".xls": FileType.EXCEL,
    ".json": FileType.JSON,
    ".jsonl": FileType.JSON_LINES,
    ".ndjson": FileType.JSON_LINES,
    ".parquet": FileType.PARQUET,
}


class UnsupportedFileTypeError(ValueError):
    pass


class FileParseError(ValueError):
    pass


class NeedsSheetSelectionError(ValueError):
    def __init__(self, sheet_names: list[str]) -> None:
        super().__init__("Excel workbook has multiple sheets; a sheet_name must be chosen")
        self.sheet_names = sheet_names


@dataclass
class LoadResult:
    df: pd.DataFrame
    total_rows: int
    is_sampled: bool
    sample_size: int | None


def detect_file_type(filename: str) -> FileType:
    ext = Path(filename).suffix.lower()
    try:
        return _EXTENSION_MAP[ext]
    except KeyError:
        raise UnsupportedFileTypeError(
            f"Unsupported file extension '{ext}'. Supported: {sorted(_EXTENSION_MAP)}"
        ) from None


def detect_encoding(raw: bytes) -> str:
    if not raw:
        return "utf-8"
    match = from_bytes(raw[:1_000_000]).best()
    return str(match.encoding) if match else "utf-8"


def _sniff_delimiter(sample_text: str, default: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return default


def list_excel_sheets(raw: bytes) -> list[str]:
    wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def _finish(
    df: pd.DataFrame, total_rows: int, sample_threshold: int, sample_size: int, seed: int
) -> LoadResult:
    if total_rows <= sample_threshold:
        return LoadResult(df=df, total_rows=total_rows, is_sampled=False, sample_size=None)
    sampled = df.sample(n=min(sample_size, len(df)), random_state=seed).sort_index()
    return LoadResult(df=sampled, total_rows=total_rows, is_sampled=True, sample_size=len(sampled))


def _load_delimited(
    raw: bytes, *, default_delimiter: str, sample_threshold: int, sample_size: int, seed: int
) -> LoadResult:
    encoding = detect_encoding(raw)
    sample_text = raw[:65_536].decode(encoding, errors="replace")
    delimiter = _sniff_delimiter(sample_text, default_delimiter)
    kwargs: dict[str, object] = {"sep": delimiter, "encoding": encoding, "on_bad_lines": "skip"}

    try:
        total_rows = 0
        for chunk in pd.read_csv(io.BytesIO(raw), chunksize=200_000, **kwargs):
            total_rows += len(chunk)

        if total_rows <= sample_threshold:
            df = pd.read_csv(io.BytesIO(raw), **kwargs)
            return LoadResult(df=df, total_rows=total_rows, is_sampled=False, sample_size=None)

        # Reservoir-sample row indices up front, then let the C parser drop
        # everything else while reading — keeps peak memory near sample_size.
        rng = np.random.default_rng(seed)
        chosen = np.asarray(
            rng.choice(total_rows, size=min(sample_size, total_rows), replace=False)
        )
        keep = {int(i) for i in chosen}
        skip: Callable[[int], bool] = lambda i: i != 0 and (i - 1) not in keep  # noqa: E731
        df = pd.read_csv(io.BytesIO(raw), skiprows=skip, **kwargs)
        return LoadResult(df=df, total_rows=total_rows, is_sampled=True, sample_size=len(df))
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        raise FileParseError(f"Could not parse delimited file: {exc}") from exc


def _load_excel(
    raw: bytes, *, sheet_name: str | None, sample_threshold: int, sample_size: int, seed: int
) -> LoadResult:
    sheets = list_excel_sheets(raw)
    if sheet_name is None:
        if len(sheets) > 1:
            raise NeedsSheetSelectionError(sheets)
        sheet_name = sheets[0]
    try:
        df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name, engine="openpyxl")
    except (ValueError, KeyError) as exc:
        raise FileParseError(f"Could not parse Excel sheet '{sheet_name}': {exc}") from exc
    return _finish(df, len(df), sample_threshold, sample_size, seed)


def _load_json(
    raw: bytes, *, file_type: FileType, sample_threshold: int, sample_size: int, seed: int
) -> LoadResult:
    text = raw.decode(detect_encoding(raw), errors="replace")
    lines_mode = file_type == FileType.JSON_LINES
    if not lines_mode:
        try:
            json.loads(text)
        except json.JSONDecodeError:
            lines_mode = True

    try:
        df = pd.read_json(io.StringIO(text), lines=lines_mode)
    except ValueError as exc:
        raise FileParseError(f"Could not parse JSON file: {exc}") from exc

    if not isinstance(df, pd.DataFrame):
        raise FileParseError("JSON file did not contain a table of records")
    return _finish(df, len(df), sample_threshold, sample_size, seed)


def _load_parquet(raw: bytes, *, sample_threshold: int, sample_size: int, seed: int) -> LoadResult:
    buffer = io.BytesIO(raw)
    try:
        parquet_file = pq.ParquetFile(buffer)
        total_rows = parquet_file.metadata.num_rows
    except (OSError, ValueError) as exc:
        raise FileParseError(f"Could not read Parquet file: {exc}") from exc

    if total_rows <= sample_threshold:
        buffer.seek(0)
        df = pd.read_parquet(buffer, engine="pyarrow")
        return LoadResult(df=df, total_rows=total_rows, is_sampled=False, sample_size=None)

    # Read row groups only until we have enough rows for a sample, instead of
    # materializing the whole file (approximate: drawn from the first groups read).
    frames = []
    collected = 0
    for group_index in range(parquet_file.num_row_groups):
        frame = parquet_file.read_row_group(group_index).to_pandas()
        frames.append(frame)
        collected += len(frame)
        if collected >= sample_size:
            break
    combined = pd.concat(frames, ignore_index=True)
    sampled = combined.sample(n=min(sample_size, len(combined)), random_state=seed)
    return LoadResult(df=sampled, total_rows=total_rows, is_sampled=True, sample_size=len(sampled))


def load_dataset(
    raw: bytes,
    file_type: FileType,
    *,
    sheet_name: str | None = None,
    sample_threshold: int,
    sample_size: int,
    random_seed: int = 42,
) -> LoadResult:
    """Parse an uploaded file into a DataFrame, sampling if it is very large."""
    if file_type == FileType.CSV:
        return _load_delimited(
            raw,
            default_delimiter=",",
            sample_threshold=sample_threshold,
            sample_size=sample_size,
            seed=random_seed,
        )
    if file_type == FileType.TSV:
        return _load_delimited(
            raw,
            default_delimiter="\t",
            sample_threshold=sample_threshold,
            sample_size=sample_size,
            seed=random_seed,
        )
    if file_type == FileType.EXCEL:
        return _load_excel(
            raw,
            sheet_name=sheet_name,
            sample_threshold=sample_threshold,
            sample_size=sample_size,
            seed=random_seed,
        )
    if file_type in (FileType.JSON, FileType.JSON_LINES):
        return _load_json(
            raw,
            file_type=file_type,
            sample_threshold=sample_threshold,
            sample_size=sample_size,
            seed=random_seed,
        )
    if file_type == FileType.PARQUET:
        return _load_parquet(
            raw, sample_threshold=sample_threshold, sample_size=sample_size, seed=random_seed
        )
    raise UnsupportedFileTypeError(f"No loader implemented for {file_type}")
