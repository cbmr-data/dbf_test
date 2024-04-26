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

import gzip
import itertools
import logging
import multiprocessing
import os
import signal
import sys
from typing import (
    Any,
    ClassVar,
    NamedTuple,
    TypedDict,
)

# Only rinterface can be imported, to prevent initialization of the R embedding
import rpy2.rinterface
import rpy2.rinterface_lib.embedded

from dbf_test.args import Args
from dbf_test.formats import DistanceMatrix, read_name_mapping, read_vcf_samples
from dbf_test.utils import IGzipFile, abort, open_rb, quote, require_file, setup_logging

########################################################################################
# Logging

_LOG = logging.getLogger("dbf-test")
_debug = _LOG.debug
_error = _LOG.error
_info = _LOG.info
_warning = _LOG.warning

########################################################################################
# Analyses helper classes


# Represents a sample in a VCF file
class VCFSample(NamedTuple):
    # Name as recorded in the VCF
    name: str
    # 0-based column in the VCF file (starting at 9)
    column: int


# Per-site statistics required to be in the input VCF
class SiteInfo(NamedTuple):
    # Minor allele frequency
    maf: float
    r2: float


class DBFResults(TypedDict):
    # Chromosome
    CHROM: str
    # Position
    POS: int
    # SNP ID column
    SNP: str
    # Allele 1
    A1: str
    # Allele 2
    A2: str
    # Frequency of allele two in sample subset
    A2_FREQ: str | float
    # MAF for all samples in VCF
    ALL_MAF: str | float
    # R2 for all samples in VCF
    R2: str | float
    # DBF test statistic
    STAT: float | None
    # DBF test p-value
    P: float | None


########################################################################################
# Multiprocessing workers


class WorkerError(RuntimeError):
    pass


# This class groups (read-only) data that is initialized prior to the creation of the
# worker processes and is thereby implicitly shared between the workers
class GlobalState:
    # Command-line arguments
    Args: ClassVar[Args]
    # Row-ordered values from the distance matrix
    MatrixValues: ClassVar[tuple[float, ...]]
    # Samples in the distance matrix and the corresponding column in the VCF
    Samples: ClassVar[tuple[VCFSample, ...]]


# This state is initialized once per worker and then re-used in subsequent calls
class WorkerState:
    # Distance matrix converted to an R `matrix` object
    Matrix: ClassVar[object] = None
    # The `DBF.Test` R function
    DBFTestFunc: ClassVar[Any] = None


class Worker:
    @classmethod
    def process(cls, line: bytes) -> WorkerError | DBFResults:
        try:
            # Handling initialization errors is easier in the main function
            cls._initialize_r()

            return cls._work(line)
        except WorkerError as error:
            return error

    @classmethod
    def _initialize_r(cls) -> None:
        # To ensure that each worker process gets a wholly unique R embedding, the
        # modules are imported late and the status of the embedding is checked.
        if WorkerState.Matrix is not None and WorkerState.DBFTestFunc is not None:
            # Sanity check of _initialized
            if not rpy2.rinterface_lib.embedded.isready():
                raise WorkerError("R not initialized in worker!")

            return
        elif rpy2.rinterface_lib.embedded.isready():
            raise WorkerError("R initialized in main; multiprocessing is not possible!")

        _debug("Initializing worker with PID %i", os.getpid())

        rpy2.rinterface.initr_simple()

        # SIGINTs are handled in the main thread; must be set after rpy2 is initialized
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        cls._setup_r_objects()

    @classmethod
    def _setup_r_objects(cls) -> None:
        # robjects must be loaded after initialization, since importing it implicitly
        # initializes the embedded R in the worker process, preventing sanity checks
        import rpy2.robjects

        if WorkerState.Matrix is None:
            values = rpy2.robjects.FloatVector(GlobalState.MatrixValues)
            WorkerState.Matrix = rpy2.robjects.r.matrix(
                values,
                nrow=len(GlobalState.Samples),
                byrow=True,
            )

        if WorkerState.DBFTestFunc is None:
            rpy2.robjects.r.source(os.fspath(GlobalState.Args.dbf_test_script))
            WorkerState.DBFTestFunc = rpy2.robjects.r("DBF.test")

    @classmethod
    def _work(cls, line: bytes) -> DBFResults:
        import rpy2.rinterface_lib.embedded
        import rpy2.robjects

        statistic: float | str | None = None
        p_value: float = 1.0
        columns = line.rstrip().split(b"\t")
        info = cls._parse_info(columns)
        genotypes: list[int] | None = None

        if (
            info is not None
            and info.r2 > GlobalState.Args.min_r2
            and info.maf >= GlobalState.Args.min_maf
        ):
            genotypes = cls._build_group_labels_vec(columns)
            if genotypes is not None and len(set(genotypes)) > 1:
                group_labels = rpy2.robjects.IntVector(genotypes)

                try:
                    # Workaround for bug in CRAN version of DBF_test; n is accessed
                    # before being set to the number of samples
                    rpy2.robjects.globalenv["n"] = len(genotypes)

                    # Returns a float-vector with two values
                    vector = WorkerState.DBFTestFunc(
                        WorkerState.Matrix,
                        group_labels,
                        len(GlobalState.Samples),
                    )

                    result: dict[str, float] = dict(
                        zip(vector.names, vector, strict=True)
                    )
                    statistic = result["dbf.statistic"]
                    p_value = result["dbf.p.value"]
                except rpy2.rinterface_lib.embedded.RRuntimeError as error:
                    raise WorkerError(f"Error running DBF.test: {error}") from error

        return {
            "CHROM": columns[0].decode(),
            "POS": int(columns[1]),
            "SNP": columns[2].decode(),
            "A1": columns[3].decode(),
            "A2": columns[4].decode(),
            "A2_FREQ": cls._af2_freq(genotypes),
            "ALL_MAF": "NA" if info is None else info.maf,
            "R2": "NA" if info is None else info.r2,
            "STAT": statistic,
            "P": p_value,
        }

    @classmethod
    def _af2_freq(cls, genotypes: list[int] | None) -> float | str:
        return "NA" if genotypes is None else (sum(genotypes) / (2 * len(genotypes)))

    @classmethod
    def _parse_info(cls, columns: list[bytes]) -> SiteInfo | None:
        maf: float | None = None
        r2: float | None = None

        try:
            for field in columns[7].split(b";"):
                if field.startswith(b"MAF="):
                    maf = float(field[4:])
                elif field.startswith(b"R2="):
                    r2 = float(field[3:])
        except ValueError:
            return cls._on_error("Invalid INFO field", columns, columns[7])

        if maf is None or r2 is None:
            return cls._on_error("Missing MAF or R2", columns, columns[7])

        return SiteInfo(maf=maf, r2=r2)

    @classmethod
    def _build_group_labels_vec(cls, columns: list[bytes]) -> list[int] | None:
        groups = {
            b"0|0": 0,
            b"0|1": 1,
            b"1|0": 1,
            b"1|1": 2,
            b"0/0": 0,
            b"0/1": 1,
            b"1/0": 1,
            b"1/1": 2,
        }

        info_field_labels = columns[8].split(b":")
        if b"GT" not in info_field_labels:
            return cls._on_error("No GT field in INFO column", columns, columns[8])
        gt_field_index = info_field_labels.index(b"GT")

        group_labels: list[int] = []
        for sample in GlobalState.Samples:
            info_fields = columns[sample.column].split(b":", gt_field_index + 1)

            gt = info_fields[gt_field_index]
            encoded_gt = groups.get(gt)
            if encoded_gt is None:
                return cls._on_error(f"Bad genotype for {sample.name}", columns, gt)

            group_labels.append(encoded_gt)

        assert len(group_labels) == len(GlobalState.Samples)

        return group_labels

    @classmethod
    def _on_error(cls, message: str, columns: list[bytes], value: bytes) -> None:
        func = _warning if GlobalState.Args.permissive else _error
        func(
            "%s at %s:%s (%s): %r",
            message,
            columns[0].decode(),
            columns[1].decode(),
            columns[2].decode(),
            value.decode(),
        )

        if not GlobalState.Args.permissive:
            raise WorkerError(
                "Terminating due to invalid site; use --permissive to filter such sites"
            )


def main(argv: list[str] = sys.argv[1:]) -> int:
    args = Args.parse(argv)

    setup_logging("%(asctime)s %(levelname)s %(message)s")

    # rpy2 by defaults repeatedly logs information about initialization
    logging.getLogger("rpy2").setLevel(logging.WARNING)
    # TODO: Capture standard/error messages via
    # rpy2.rinterface_lib.callbacks.consolewrite_print = lambda _: None
    # rpy2.rinterface_lib.callbacks.consolewrite_warnerror = lambda _: None

    require_file(args.distance_matrix, "Distance matrix")
    require_file(args.genotypes, "VCF file")
    require_file(args.dbf_test_script, "DBF R-script")
    if args.name_mapping is not None:
        require_file(args.name_mapping, "Name mapping")

    if IGzipFile is gzip.GzipFile:
        _warning("Could not load `isal` module: Reading `*.gz` files will be much, ")
        _warning("much slower! To fix this, run the following command:")
        _warning(f"  $ {quote(sys.executable)} -m pip3 install isal")

    _info("Loading distance matrix from %s", quote(args.distance_matrix))
    matrix = DistanceMatrix.load(args.distance_matrix)
    _info("Loaded %ix%i distance matrix", len(matrix.samples), len(matrix.samples))

    if args.name_mapping is not None:
        _info("Loading sample name mapping from %s", quote(args.name_mapping))
        names_dm_to_vcf = read_name_mapping(
            filepath=args.name_mapping,
            key_column=args.name_column_matrix,
            value_column=args.name_column_genotypes,
        )

        # Replace names in distance matrix with names used in VCF
        matrix.replace_names(names_dm_to_vcf)

    if rpy2.rinterface_lib.embedded.isready():
        abort("R initialized in main; multiprocessing is not possible!")

    _info("Opening VCF file %s", quote(args.genotypes))
    with open_rb(args.genotypes) as handle:
        # Determine columns to use from the VCF and order samples accordingly
        vcf_samples = read_vcf_samples(handle)
        vcf_columns = dict(zip(vcf_samples, itertools.count(start=9)))
        samples = sorted(matrix.samples, key=lambda it: vcf_columns[it])

        # Set (read-only) variables shared between worker processes
        GlobalState.Args = args
        GlobalState.Samples = tuple(VCFSample(key, vcf_columns[key]) for key in samples)
        GlobalState.MatrixValues = matrix.to_tuple(sample_order=samples)
        assert len(GlobalState.MatrixValues) == len(GlobalState.Samples) ** 2

        columns = ("SNP", "A1", "A2", "A2_FREQ", "ALL_MAF", "R2", "STAT", "P")
        if args.positions:
            columns = ("CHROM", "POS", *columns)

        head = float("inf") if args.head is None else args.head

        try:
            print(*columns, sep="\t")
            if head <= 0:
                return 0

            with multiprocessing.Pool(args.threads) as pool:
                for idx, result in enumerate(
                    pool.imap(Worker.process, handle, chunksize=max(10, args.threads))
                ):
                    if isinstance(result, WorkerError):
                        _error("%s", result)
                        break

                    if idx % 100_000 == 0 and idx:
                        _info(
                            "Processed %s records; now at position %s",
                            f"{idx:,}",
                            result["SNP"],
                        )

                    if result["STAT"] is not None:
                        print(*(result[key] for key in columns), sep="\t")

                        head -= 1
                        if head <= 0:
                            break

        except BrokenPipeError:
            _error("Terminating due to broken pipe!")

            return 1
        except KeyboardInterrupt:
            _warning("Interrupted by user!")

            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
