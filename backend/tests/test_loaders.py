import io

import pandas as pd
import pytest

from app.data.loaders import (
    FileParseError,
    NeedsSheetSelectionError,
    UnsupportedFileTypeError,
    detect_encoding,
    detect_file_type,
    list_excel_sheets,
    load_dataset,
)
from app.models.session import FileType

SAMPLE_DF = pd.DataFrame(
    {
        "id": range(1, 6),
        "name": ["a", "b", "c", "d", "e"],
        "score": [1.5, 2.5, None, 4.5, 5.5],
    }
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("data.csv", FileType.CSV),
        ("data.TSV", FileType.TSV),
        ("data.xlsx", FileType.EXCEL),
        ("data.xls", FileType.EXCEL),
        ("data.json", FileType.JSON),
        ("data.jsonl", FileType.JSON_LINES),
        ("data.ndjson", FileType.JSON_LINES),
        ("data.parquet", FileType.PARQUET),
    ],
)
def test_detect_file_type(filename: str, expected: FileType) -> None:
    assert detect_file_type(filename) == expected


def test_detect_file_type_unsupported() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        detect_file_type("data.exe")


def test_detect_encoding_utf8() -> None:
    assert detect_encoding("héllo wörld".encode()) is not None


def test_detect_encoding_empty() -> None:
    assert detect_encoding(b"") == "utf-8"


def test_load_csv_comma() -> None:
    raw = SAMPLE_DF.to_csv(index=False).encode()
    result = load_dataset(raw, FileType.CSV, sample_threshold=1_000_000, sample_size=100_000)
    assert result.total_rows == 5
    assert not result.is_sampled
    assert list(result.df.columns) == ["id", "name", "score"]


def test_load_csv_semicolon_delimiter_sniffed() -> None:
    raw = SAMPLE_DF.to_csv(index=False, sep=";").encode()
    result = load_dataset(raw, FileType.CSV, sample_threshold=1_000_000, sample_size=100_000)
    assert result.total_rows == 5
    assert list(result.df.columns) == ["id", "name", "score"]


def test_load_tsv() -> None:
    raw = SAMPLE_DF.to_csv(index=False, sep="\t").encode()
    result = load_dataset(raw, FileType.TSV, sample_threshold=1_000_000, sample_size=100_000)
    assert result.total_rows == 5


def test_load_csv_sampling() -> None:
    big_df = pd.DataFrame({"id": range(50), "value": range(50)})
    raw = big_df.to_csv(index=False).encode()
    result = load_dataset(raw, FileType.CSV, sample_threshold=10, sample_size=5)
    assert result.total_rows == 50
    assert result.is_sampled
    assert result.sample_size == 5
    assert len(result.df) == 5


def test_load_json_records() -> None:
    raw = SAMPLE_DF.to_json(orient="records").encode()
    result = load_dataset(raw, FileType.JSON, sample_threshold=1_000_000, sample_size=100_000)
    assert result.total_rows == 5


def test_load_json_lines() -> None:
    raw = SAMPLE_DF.to_json(orient="records", lines=True).encode()
    result = load_dataset(raw, FileType.JSON_LINES, sample_threshold=1_000_000, sample_size=100_000)
    assert result.total_rows == 5


def test_load_json_lines_content_with_json_extension() -> None:
    # A .json file whose content is actually newline-delimited JSON must still parse.
    raw = SAMPLE_DF.to_json(orient="records", lines=True).encode()
    result = load_dataset(raw, FileType.JSON, sample_threshold=1_000_000, sample_size=100_000)
    assert result.total_rows == 5


def test_load_json_garbage_raises() -> None:
    with pytest.raises(FileParseError):
        load_dataset(
            b"not json {{{", FileType.JSON, sample_threshold=1_000_000, sample_size=100_000
        )


def test_load_parquet() -> None:
    buffer = io.BytesIO()
    SAMPLE_DF.to_parquet(buffer, engine="pyarrow")
    result = load_dataset(
        buffer.getvalue(), FileType.PARQUET, sample_threshold=1_000_000, sample_size=100_000
    )
    assert result.total_rows == 5


def _make_excel(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


def test_load_excel_single_sheet() -> None:
    raw = _make_excel({"Sheet1": SAMPLE_DF})
    result = load_dataset(raw, FileType.EXCEL, sample_threshold=1_000_000, sample_size=100_000)
    assert result.total_rows == 5


def test_load_excel_multi_sheet_requires_selection() -> None:
    raw = _make_excel({"First": SAMPLE_DF, "Second": SAMPLE_DF})
    with pytest.raises(NeedsSheetSelectionError) as exc_info:
        load_dataset(raw, FileType.EXCEL, sample_threshold=1_000_000, sample_size=100_000)
    assert exc_info.value.sheet_names == ["First", "Second"]


def test_load_excel_multi_sheet_with_selection() -> None:
    raw = _make_excel({"First": SAMPLE_DF, "Second": SAMPLE_DF.head(2)})
    result = load_dataset(
        raw, FileType.EXCEL, sheet_name="Second", sample_threshold=1_000_000, sample_size=100_000
    )
    assert result.total_rows == 2


def test_list_excel_sheets() -> None:
    raw = _make_excel({"First": SAMPLE_DF, "Second": SAMPLE_DF})
    assert list_excel_sheets(raw) == ["First", "Second"]
