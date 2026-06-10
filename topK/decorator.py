from dataclasses import dataclass
from typing import Type, TypeVar, dataclass_transform
from ._reg import _setDC
T = TypeVar("T")


@dataclass_transform()
def topKComponent(cls: Type[T]) -> Type[T]:
    """Framework decorator that enforces TopK constraints and tags the class."""
    # Applichiamo la dataclass rigida
    decoratedCls: Type[T] = dataclass(
        slots=True,
        kw_only=True,
        eq=False,
        repr=False,
        unsafe_hash=False
    )(cls)


    # 2. Registers the exact object-class reference to isolate it from clashing sibling names
    _setDC(decoratedCls)

    return decoratedCls  # type: ignore
