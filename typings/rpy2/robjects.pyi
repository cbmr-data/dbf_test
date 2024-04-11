from collections.abc import MutableMapping, Sequence

globalenv: MutableMapping[str, object]

class _R:
    def __call__(self, key: str) -> object: ...
    def matrix(
        self,
        obj: FloatVector,
        *,
        nrow: int = ...,
        ncol: int = ...,
        byrow: bool = False,
    ) -> object: ...
    def source(self, path: str) -> None: ...

r: _R

class FloatVector:
    def __init__(self, obj: Sequence[float]) -> None: ...

class IntVector:
    def __init__(self, obj: Sequence[int]) -> None: ...
