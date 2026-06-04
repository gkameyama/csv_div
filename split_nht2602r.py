from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


@dataclass(frozen=True)
class OutputSpec:
    suffix: str
    cats: set[str]
    hindo_columns: tuple[str, ...]
    ranges: tuple[tuple[str, str], ...]


COMMON_COLUMNS = ("SAMPLENUMBER",)
FILTER_COLUMNS = ("CAT",)

COMMON_RANGES = (("SC1", "SC14.2-7"),)

V_RANGE = ("V1-1", "V11.42")
HINDO_SOURCE_COLUMNS = ("HINDO1", "HINDO2", "HINDO3", "HINDO4")

OUTPUT_SPECS = (
    OutputSpec("A", {"1"}, ("HINDO1",), (("A1.1", "E2.15"), V_RANGE, ("P1", "R4-14"))),
    OutputSpec("B", {"2"}, ("HINDO2",), (("AA1.1", "F4.7"), V_RANGE)),
    OutputSpec("C", {"3"}, ("HINDO3",), (("AAA1.101", "G5.10"), V_RANGE)),
    OutputSpec("D", {"4"}, ("HINDO4",), (("AAAA0", "H5.5"), V_RANGE)),
    OutputSpec("E", {"1", "2", "3", "4"}, ("HINDO1", "HINDO2", "HINDO3", "HINDO4"), (V_RANGE,)),
)


def column_index(header: list[str], name: str) -> int:
    try:
        return header.index(name)
    except ValueError as exc:
        raise ValueError(f"Column not found: {name}") from exc


def column_range(header: list[str], start: str, end: str) -> list[int]:
    try:
        start_index = header.index(start)
        end_index = header.index(end)
    except ValueError as exc:
        raise ValueError(f"Column not found while resolving range {start} -> {end}") from exc

    if start_index > end_index:
        raise ValueError(f"Invalid range: {start} appears after {end}")
    return list(range(start_index, end_index + 1))


def build_indices(header: list[str], spec: OutputSpec) -> list[int]:
    indices: list[int] = []
    indices.extend(column_index(header, name) for name in COMMON_COLUMNS)
    indices.extend(column_index(header, name) for name in FILTER_COLUMNS)
    indices.extend(column_index(header, name) for name in spec.hindo_columns)
    for start, end in (*COMMON_RANGES, *spec.ranges):
        indices.extend(
            index
            for index in column_range(header, start, end)
            if header[index] not in HINDO_SOURCE_COLUMNS
        )
    unique_indices: list[int] = []
    seen = set()
    for index in indices:
        if index not in seen:
            unique_indices.append(index)
            seen.add(index)
    return unique_indices


def output_header_name(name: str, spec: OutputSpec) -> str:
    if len(spec.hindo_columns) == 1 and name == spec.hindo_columns[0]:
        return "HINDO"
    return name.replace("-", "_")


def samplenumber_sort_key(row: list[str]) -> tuple[int, int | str]:
    value = row[0].strip()
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


def input_path_from_args() -> Path:
    parser = argparse.ArgumentParser(description="Split survey CSV into five CAT-based files.")
    parser.add_argument(
        "input_file",
        nargs="?",
        default="NHT2602R.CSV",
        help="CSV file to read. Relative paths are resolved from this script's folder.",
    )
    args = parser.parse_args()
    path = Path(args.input_file)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def split_csv(input_file: Path) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    with input_file.open("r", newline="", encoding="utf-8-sig") as in_f:
        reader = csv.reader(in_f)
        header = next(reader)
        cat_index = header.index("CAT")

        output_indices = {spec.suffix: build_indices(header, spec) for spec in OUTPUT_SPECS}
        output_rows = {spec.suffix: [] for spec in OUTPUT_SPECS}

        for row in reader:
            cat = row[cat_index]
            for spec in OUTPUT_SPECS:
                if cat in spec.cats:
                    output_rows[spec.suffix].append([row[i] for i in output_indices[spec.suffix]])

    counts = {}
    for spec in OUTPUT_SPECS:
        rows = output_rows[spec.suffix]
        rows.sort(key=samplenumber_sort_key)
        path = OUTPUT_DIR / f"{input_file.stem}{spec.suffix}{input_file.suffix}"
        with path.open("w", newline="", encoding="utf-8-sig") as out_f:
            writer = csv.writer(out_f, lineterminator="\n")
            writer.writerow([output_header_name(header[i], spec) for i in output_indices[spec.suffix]])
            writer.writerows(rows)
        counts[spec.suffix] = len(rows)

    for suffix, count in counts.items():
        print(f"{input_file.stem}{suffix}{input_file.suffix}: {count} rows")


if __name__ == "__main__":
    split_csv(input_path_from_args())
