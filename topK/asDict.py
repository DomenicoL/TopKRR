from typing import  Any, Iterator, Mapping, Iterable, Protocol

from .interaction import TopKInteraction
from .decorator import topKComponent


#@dataclass(slots=True, kw_only=True, eq=False,repr=False,unsafe_hash=False)
@topKComponent
class TopKAsDict[T](TopKInteraction[T],Protocol):

    
    def __getitem__(self, key) -> T:
        """Retrieve an element by its ID.

        :param key: str: The unique identifier of the element.

        :return: T: The element associated with the given ID.

        :raises: KeyError: If the ID is not present in the stabilized Top-K ranking.
        """
        # Se c'è lo ritorno
        if key in self._innerState.orderedScore:
            return self._innerState.elements[key]

        # se non c'è provo a ricostruire
        self._rankRegistry(False)
        # Se continua a non esserci errore
        if key in self._innerState.orderedScore:
            return self._innerState.elements[key]

        raise KeyError(key)

    
    def __iter__(self) -> Iterator[str]:
        """Iterate over the element IDs in the current ranking order.

        :return: Iterator[str]: The IDs of the elements in the current ranking order.

        """
        self._rankRegistry(False)
        # for eid in self._innerState.orderedScore:
        #    yield self._innerState.elements[eid]
        return iter(self._innerState.orderedScore)

    
    def __len__(self) -> int:
        """Return the number of elements in the stabilized Top-K ranking.

        :return: int: The current size of the Top-K set.
        """
        self._rankRegistry(False)
        return len(self._innerState.orderedScore)

    
    def __repr__(self) -> str:
        """Debug method to represent the object

        :return: str: The string representation of the object.
        """
        # Mostriamo lo stato attuale e quanti elementi ci sono
        info = f"size={len(self._innerState.orderedScore)}/{self._innerState.maxSize}"
        status = "DIRTY" if self._innerState.state == self.Status.DIRTY else "ORDERED"

        # Prendiamo i primi 3 ID per avere un'anteprima
        preview = list(self._innerState.orderedScore.keys())[:3]

        return f"{self.__class__.__name__}({info}, state={status}, top3={preview})"

    
    def __contains__(self, key: object) -> bool:
        """
        Check if an ID exists within the stabilized Top-K ranking.

        :param key: str: The unique identifier of the element.

        :return: bool: True if the element exists in the stabilized Top-K ranking.
        """

        # 0. Key è una stringa
        if not isinstance(key, str):
            return False
        # 1. Assicuriamoci che i punteggi siano aggiornati
        self._rankRegistry(False)
        

        # 2. Controlliamo se la chiave è nel Top-K (NON in elements!)
        # Usiamo orderedScore perché elements contiene anche la dirty window
        return key in self._innerState.orderedScore

    
    def __setitem__(self, key: str, value: T) -> None:
        """Syntactic sugar for the push method. Maps obj[id] = element.

        :param key: str: The unique identifier of the element.
        :param value: T: The element to push.
        :return: None

        :raises KeyError: If the ID is not the same computed by _getElementId(value)
        """

        # Verifica coerenza tra chiave e ID elemento (opzionale ma consigliato)
        if self._getElementId(value) != key:
            raise ValueError(f"La chiave '{key}' non corrisponde all'ID dell'elemento.")
        self.push(value)

    
    def __delitem__(self, key: str) -> None:
        """Syntactic sugar for the pop method. Maps del obj[id].

        :param key: str: The unique identifier of the element.
        :return: None
        :raises KeyError: If the ID is not present in the stabilized Top-K ranking.

        """

        if key not in self._innerState.elements:
            raise KeyError(key)
        self.pop(key)

    
    def __bool__(self) -> bool:
        """
        :return: bool: True if the storage contains at least one element (raw or ordered).
        """

        return len(self._innerState.indexScore) > 0

    
    def keys(self) -> Iterator[str]:
        """
        Standard Mapping API views.
        Each call triggers _rebuildScores to ensure the output is stable and sorted.

        :return: Iterator[str]: An iterator of IDs in the current ranking order.
        """
        self._rankRegistry(False)
        yield from self._innerState.orderedScore

    
    def values(self) -> Iterator[T]:
        """
        Standard Mapping API views.
        Each call triggers _rebuildScores to ensure the output is stable and sorted.

        :return: Iterator[T]: An iterator over the IDs of the elements in the current ranking order.
        """
        self._rankRegistry(False)
        for eid in self._innerState.orderedScore:
            assert self._innerState.elements[eid] is not None
            #element = self._innerState.elements[eid]
            yield self._innerState.elements[eid]

    
    def items(self) -> Iterator[tuple[str, T]]:
        """
        Standard Mapping API views.
        Each call triggers _rebuildScores to ensure the output is stable and sorted.

        :return Iterator[tuple[str, T]]: An iterator over the elements in the current ranking order.
        """
        self._rankRegistry(False)

        for eid in self._innerState.orderedScore:
            yield eid, self._innerState.elements[eid]

    
    def get(self, key: str) -> T | None:
        try:
            return self.__getitem__(key)
        except KeyError:
            return None

    # =========================================================================
    # CONCATENAZIONE E UNIONE (OPERATORI | E |=)
    # =========================================================================

    def __or__(self, other: Any) -> Any:
        """
        The dictionary union operator (|) is explicitly disabled for TopK structures.
        Merging rankings directly breaks copyStrategy consistency and element constraints.
        """

        raise RuntimeError(
            "Operation denied: Direct merging of TopK rankings via the '|' operator is unsupported to protect data integrity. "
            "If you need to combine elements, iterate through the source and feed them manually to respect the copyStrategy: "
            "for element in secondTopK.values: firstTopK.push(element)"
        )

    def __ror__(self, other: Any) -> Any:
        """The reversed dictionary union operator is explicitly disabled."""
        return self.__or__(other)



    # =========================================================================
    # IN-PLACE MUTATION PROTOCOLS (Safely feeding streams)
    # =========================================================================
    def update(self, other: Mapping[str, T] | Iterable[T] | Any) -> None:
        """
        Update the TopK ranking in-place by ingesting elements from another collection.
        Accepts dicts, other TopK structures, lists, sets, or any iterable stream.

        Guarantees that every incoming element passes through the configured copyStrategy.
        
        :param other: Mapping or iterable of elements
        """
        # 1. Ensure the contract allows data insertion before running the loop


        # 2. Case A: It's a dictionary or another TopK structure (Mapping)
        # We extract and feed only the values, ignoring the raw keys
        if hasattr(other, "values") and callable(getattr(other, "values")):
            for element in other.values():
                self.push(element)  # push handles the _copyElement internally

        # 3. Case B: It's a sequential collection or lazy stream (Iterable)
        # This covers list[T], set[T], tuple[T], or generator iterators
        elif isinstance(other, Iterable) and not isinstance(other, (str, bytes)):
            for element in other:
                self.push(element)

        # 4. Fallback: Protect the engine from unsupported object mutations
        else:
            raise TypeError(
                f"Update failed: Unsupported collection type '{type(other).__name__}'. "
                f"Expected an Iterable (e.g., list, set) or a Mapping (e.g., dict, TopK)."
            )

    def __ior__(self, other: Mapping[str, T] | Iterable[T] | Any) -> Any:
        """
        Implement the in-place dictionary union operator (|=).
        Mutates the current ranking instance and returns self.
        
        :param other: Mapping or iterable of elements
        """
        self.update(other)
        return self  # Strict Python requirement for in-place operators

    @property
    def isEmpty(self) -> bool:
        """        
        :return: if registry is empty (not __bool__) 
        """
        return not self.__bool__()


    def _rankRegistry(self, deep:bool=False) -> None:
        """
        Validates if the retrieval operation (get/values/iter) is currently permitted.
        Raises a RuntimeError if the access contract or current state blocks it.
        
        :param deep: bool Activate complete rebuild and ranking
        """
        if not self._innerState.retrievalEnabled:

            if self._innerState.accessContract == self.AccessContract.LAZY_AUTO_FREEZE_MODE:
                self.enableRetrieval(deep)
                return

            raise RuntimeError(
                f"Access Denied: Retrieval phase is disabled. "
                f"Current AccessContract is set to '{self._innerState.accessContract.name}'. "
                f"Please enable retrieval via the 'retrievalEnabled' property before reading data."
            )
        elif self._innerState.state< self.Status.ORDERED:
            self.enableRetrieval(deep)