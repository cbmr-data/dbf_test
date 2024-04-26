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
# pyright: strict
from __future__ import annotations

import argparse
import os
from functools import partial
from pathlib import Path
from typing import (
    NamedTuple,
)

from dbf_test import __version_str__


class Args(NamedTuple):
    distance_matrix: Path
    genotypes: Path
    name_mapping: Path | None
    name_column_matrix: str
    name_column_genotypes: str
    dbf_test_script: Path
    permissive: bool
    min_r2: float
    min_maf: float
    threads: int
    positions: bool
    head: int | None

    @staticmethod
    def parse(argv: list[str]) -> Args:
        parser = argparse.ArgumentParser(
            formatter_class=partial(
                argparse.ArgumentDefaultsHelpFormatter,
                width=79,
            )
        )

        parser.add_argument(
            "-v",
            "--version",
            version=__version_str__,
            action="version",
            help="Display script version",
        )
        parser.add_argument(
            "--threads",
            default=1,
            metavar="N",
            type=int,
            help="Number of worker threads used to compute the DBF test statistic",
        )

        group = parser.add_argument_group("Input files")
        group.add_argument(
            "--distance-matrix",
            required=True,
            metavar="CSV",
            type=Path,
            help="Path to distance matrix for samples in the VCF file; the matrix is "
            "expected to be comma-separated and have both row and column names. The  "
            "matrix must include all sample names in the VCF but may also contain "
            "samples not found in the VCF",
        )
        group.add_argument(
            "--genotypes",
            required=True,
            metavar="VCF",
            type=Path,
            help="VCF files containing sample genotypes. Sample names must either "
            "match the names in the distance matrix or a name mapping file must be "
            "supplied with --name-mapping",
        )
        parser.add_argument(
            "--dbf-test-script",
            default=Path(os.environ.get("DBF_TEST_SCRIPT", "DBF_test.R")),
            metavar="PATH",
            type=Path,
            help="Path to the `DBF_test.R` script; defaults to the same folder as this "
            "script",
        )

        group = parser.add_argument_group("Sample information")
        group.add_argument(
            "--name-mapping",
            metavar="CSV",
            type=Path,
            help="Path to CSV containing a column with the sample names in the "
            "distance matrix and a column containing the names in the vcf file. If "
            "this file is not specified, then the names in the distance matrix and VCF "
            "must be identical",
        )
        group.add_argument(
            "--name-column-matrix",
            metavar="COLUMN",
            default="SampleID",
            help="The name of the column in the --name-mapping file containing the "
            "names used in the --distance-matrix CSV file",
        )
        group.add_argument(
            "--name-column-genotypes",
            metavar="COLUMN",
            default="IND_ID",
            help="The name of the column in the --name-mapping file containing the "
            "names used in the --genotypes VCF file",
        )

        group = parser.add_argument_group("Site filtering")
        group.add_argument(
            "--permissive",
            action="store_true",
            default=False,
            help="Skip sites containing non-biallelic genotypes or missing R2 or MAF "
            "scores. By default this script will terminate if such a site is found",
        )
        group.add_argument(
            "--min-r2",
            metavar="R2",
            default=0.4,
            type=float,
            help="Require a per-site R2 value > the specified value",
        )
        group.add_argument(
            "--min-maf",
            metavar="MAF",
            default=0.01,
            type=float,
            help="Require a per-site MAF value >= the specified value",
        )

        group = parser.add_argument_group("Misc")
        group.add_argument(
            "--positions",
            action="store_true",
            default=False,
            help="Include CHROM and POS columns in output",
        )
        group.add_argument(
            "--head",
            metavar="N",
            type=int,
            help="Return only the first N results",
        )

        return Args(**vars(parser.parse_args(argv)))
