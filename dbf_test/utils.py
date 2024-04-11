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

import csv
import gzip
import io
import logging
import shlex
import sys
from collections import Counter
from typing import (
    IO,
    TYPE_CHECKING,
    NoReturn,
    TypeVar,
    cast,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path


try:
    # The isal library is able to decompress gzipped files in a fraction of the time
    # used by standard gzip (e.g. 1.6 GB decompressed in 6s vs 34s) and should therefore
    # be used if available
    import isal.igzip
except ImportError:
    IGzipFile = gzip.GzipFile
else:
    IGzipFile = isal.igzip.IGzipFile


try:
    # Colored logs are preferred but not required
    import coloredlogs
except ImportError:

    def setup_logging(fmt: str) -> None:
        logging.basicConfig(format=fmt)

else:

    def setup_logging(fmt: str) -> None:
        coloredlogs.install(fmt=fmt)


T = TypeVar("T")


_LOG = logging.getLogger("dbf-test")
_debug = _LOG.debug
_error = _LOG.error
_info = _LOG.info
_warning = _LOG.warning


class IGzipFileCloser(IGzipFile):  #  pyright: ignore[reportGeneralTypeIssues,reportUntypedBaseClass]
    """Wrapper class that ensures that the underlying file handle is closed"""

    def close(self) -> None:
        with self.fileobj:  # pyright: ignore[reportUnknownMemberType]
            super().close()  # pyright: ignore[reportUnknownMemberType]


def abort(message: str, *values: object) -> NoReturn:
    _error(message, *values)
    sys.exit(1)


def quote(value: object) -> str:
    return shlex.quote(str(value))


def require_file(filepath: Path, desc: str) -> None:
    if not filepath.exists():
        abort("%s is missing: %s", desc, quote(filepath))
    elif not filepath.is_file():
        abort("%s is not a file: %s", desc, quote(filepath))


def open_rb(filepath: Path) -> IO[bytes]:
    """Opens a file for reading, transparently handling
    GZip and BZip2 compressed files. Returns a file handle."""
    handle = filepath.open("rb")

    try:
        header = handle.peek(2)

        if header.startswith(b"\x1f\x8b"):
            return cast(IO[bytes], IGzipFileCloser(mode="rb", fileobj=handle))
        else:
            return handle
    except:
        handle.close()
        raise


def open_rt(filepath: Path) -> IO[str]:
    return io.TextIOWrapper(open_rb(filepath))


def read_csv(filepath: Path) -> Iterator[tuple[str, dict[str, str]]]:
    with open_rt(filepath) as handle:
        reader = csv.reader(handle)
        try:
            columns = next(reader)[1:]
        except StopIteration:
            abort("CSV file is empty: %s", quote(filepath))

        row_names: list[str] = []
        for linenum, row in enumerate(reader, start=1):
            if len(row) != len(columns) + 1:
                abort("Wrong number of columns at %s:%i", quote(filepath), linenum)

            yield row[0], dict(zip(columns, row[1:], strict=True))
            row_names.append(row[0])

        if not row_names:
            abort("CSV file is empty: %s", quote(filepath))

    duplicates = collect_duplicates(columns)
    if duplicates:
        abort("Duplicate columns in %s: %s", quote(filepath), ",".join(duplicates))

    duplicates = collect_duplicates(row_names)
    if duplicates:
        abort("Duplicate rows in %s: %s", quote(filepath), ",".join(duplicates))


def collect_duplicates(items: Iterable[T]) -> list[T]:
    return [key for key, value in Counter(items).items() if value > 1]
