from dataclasses import dataclass
from types import MappingProxyType
from typing import  Protocol
from .storage import TopKStorage
from .decorator import topKComponent


#@dataclass(slots=True, kw_only=True, eq=False,repr=False,unsafe_hash=False)
@topKComponent
class TopKInspection[T](TopKStorage[T],Protocol):

    # -------------------------
    # API: access by id
    # -------------------------
    def rawGetElement(self, eid: str) -> T:
        """Retrieve an element from raw storage without triggering a rebuild.

        :param: id (str): The identifier of the element.

        :return: T | None: The element if found in any state, otherwise None.
        """
        return self._innerState.elements.get(eid, None)

    # -------------------------
    # API: raw view
    # -------------------------
    def rawGetStorage(self) -> MappingProxyType[str, T]:
        """
        Provide a read-only view of the entire raw storage.

        :return: MappingProxyType[str, T]: The dictionary representation of the raw storage.

        """

        return MappingProxyType(self._innerState.elements)

    @property
    def rawSize(self) -> int:
        """Retrieve the size of raw storage without triggering a rebuild.

        :return: int: The size of raw storage.
        """
        return len(self._innerState.elements)

