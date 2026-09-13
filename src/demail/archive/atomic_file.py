"""Atomic filesystem sink for one archived message."""

import hashlib
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Self


@dataclass(frozen=True, slots=True)
class ArchivedFile:
    path: Path
    byte_size: int
    sha256: str


class AtomicArchiveFile:
    """Write, hash, sync, close, then atomically promote a `.partial` file."""

    def __init__(self, final_path: Path) -> None:
        self.final_path = final_path
        self.partial_path = final_path.with_name(f"{final_path.name}.partial")
        self._stream: BinaryIO | None = None
        self._digest = hashlib.sha256()
        self._byte_size = 0
        self._result: ArchivedFile | None = None

    def __enter__(self) -> Self:
        self.final_path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.partial_path.open("wb")
        return self

    def write(self, data: bytes | bytearray) -> int:
        if self._stream is None:
            raise RuntimeError("Archive file is not open")
        written = self._stream.write(data)
        if written != len(data):
            raise OSError(f"Short archive write: expected {len(data)} bytes, wrote {written}")
        self._digest.update(memoryview(data)[:written])
        self._byte_size += written
        return written

    def finish(self) -> ArchivedFile:
        if self._result is not None:
            return self._result
        if self._stream is None:
            raise RuntimeError("Archive file is not open")
        self._stream.flush()
        os.fsync(self._stream.fileno())
        self._stream.close()
        self._stream = None
        os.replace(self.partial_path, self.final_path)
        self._result = ArchivedFile(self.final_path, self._byte_size, self._digest.hexdigest())
        return self._result

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exception_type is None:
            try:
                self.finish()
            except Exception:
                if self._stream is not None:
                    self._stream.close()
                    self._stream = None
                with suppress(OSError):
                    self.partial_path.unlink(missing_ok=True)
                raise
            return
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        with suppress(OSError):
            self.partial_path.unlink(missing_ok=True)
