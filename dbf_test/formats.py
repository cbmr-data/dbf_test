#
# Copyright (c) 2024 Mikkel Schubert <MikkelSch@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
from __future__ import annotations

from dataclasses import dataclass
from typing import (
    IO,
    TYPE_CHECKING,
)

from dbf_test.utils import abort, quote, read_csv

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class DistanceMatrix:
    samples: tuple[str, ...]
    matrix: dict[str, dict[str, float]]

    def replace_names(self, mapping: dict[str, str]) -> None:
        missing_keys = set(self.samples) - set(mapping)
        if missing_keys:
            abort(
                "Missing samples in name mapping: %s, ...",
                ", ".join(sorted(missing_keys)[:5]),
            )

        self.samples = tuple(mapping[key] for key in self.samples)
        self.matrix = {
            mapping[row_key]: {
                mapping[column_key]: value for column_key, value in row.items()
            }
            for row_key, row in self.matrix.items()
        }

    def to_tuple(self, sample_order: list[str]) -> tuple[float, ...]:
        values: list[float] = []
        for row_key in sample_order:
            row = self.matrix[row_key]
            values.extend(row[key] for key in sample_order)

        return tuple(values)

    @staticmethod
    def load(filepath: Path) -> DistanceMatrix:
        rows: list[dict[str, float]] = []
        row_names: list[str] = []

        for linenum, (row_name, row) in enumerate(read_csv(filepath), start=1):
            row_names.append(row_name)

            try:
                rows.append({key: float(value) for key, value in row.items()})
            except ValueError as error:
                abort("Invalid value at %s:%i: %s", quote(filepath), linenum, error)

        columns = tuple(rows[0])
        if set(row_names) != set(columns):
            abort("Mismatch between row and column names in %s", quote(filepath))

        try:
            matrix = {
                row_name: {col_name: float(value) for col_name, value in row.items()}
                for row_name, row in zip(row_names, rows, strict=True)
            }
        except ValueError as error:
            abort("Invalid value %s in %s", error, quote(filepath))

        return DistanceMatrix(
            samples=columns,
            matrix=matrix,
        )


def read_name_mapping(
    filepath: Path,
    key_column: str,
    value_column: str,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used_values: set[str] = set()

    try:
        for _, row in read_csv(filepath):
            if row[key_column] in mapping:
                abort("Duplicate mapping from sample %r", row[key_column])
            elif row[value_column] in used_values:
                abort("Duplicate mapping to sample %r", row[value_column])

            mapping[row[key_column]] = row[value_column]
    except KeyError as error:
        abort("Missing column in %s: %s", quote(filepath), error)

    return mapping


def read_vcf_samples(handle: IO[bytes]) -> list[str]:
    samples: list[bytes] = []
    for line in handle:
        if line.startswith(b"##"):
            continue
        elif line.startswith(b"#CHROM"):
            samples = line.rstrip(b"\r\n").split(b"\t")[9:]
            break
        else:
            abort("VCF header with sample names not found")

    if not samples:
        abort("`#CHROM` header did not contain sample names in VCF")

    return [name.decode() for name in samples]
