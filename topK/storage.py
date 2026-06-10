from dataclasses import field, dataclass
from typing import TypeVar, Tuple, final, Protocol

from .base import TopKBase
from .innerState import InnerState
from .decorator import topKComponent


T = TypeVar(
    "T",
    covariant=True
)


#@dataclass(slots=True, kw_only=True, eq=False,repr=False,unsafe_hash=False)
@topKComponent
class TopKStorage[T](TopKBase,Protocol):
    _innerState: InnerState[T] = field(repr=False, compare=False)


    @final
    def _innerBetter(self, a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
        """Internal wrapper for _better

        :param a: T: The object to evaluate.
        :param b: T: The object to evaluate.
        :return: Tuple[float, ...]: A tuple representing the score for lexicographical comparison.

        """
        try:
            return self._better(a, b)
        except TypeError as e:
            raise TypeError(
                f"Incompatible scores: {a} vs {b}"
            ) from e

    @final
    def _innerWorse(self, a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
        """Internal wrapper for _worse

        :arg a: T: The object to evaluate.
        :arg b: T: The object to evaluate.

        :return: Tuple[float, ...]: A tuple representing the score for lexicographical comparison.
        """
        try:
            return self._worse(a, b)
        except TypeError as e:
            raise TypeError(
                f"Incompatible scores: {a} vs {b}"
            ) from e

    def _better(self, a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
        """
        Compares two scores.

        Can be overridden to implement custom ranking strategies.

        Default implementation uses lexicographic tuple ordering.

        :arg a: T: The object to evaluate.
        :arg b: T: The object to evaluate.

        :return: Tuple[float, ...]: A tuple representing the score for lexicographical comparison.
        """
        return (a > b) if self._innerState.maximize else (a < b)

    def _worse(self, a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
        """
        Compares two scores.

        Could be overridden to implement custom ranking strategies, but it's discouraged
        because: by default call _better(b,a).

        :arg a: T: The object to evaluate.
        :arg b: T: The object to evaluate.

        :return: Tuple[float, ...]: A tuple representing the score for lexicographical comparison.
        """
        return self._better(b, a)

    # -------------------------
    # watermark pruning
    # -------------------------
    def _maybePrune(self) -> None:
        """
        Check if the raw storage has exceeded the safety watermark (maxSlice).

        If the limit is reached, it triggers an immediate _rebuildElements to
        evict the worst candidates and restore the K-size constraint.
        """

        # soglia di attivazione pruning aggressivo
        if len(self._innerState.elements) > self._innerState.maxSlice:
            self._rebuildElements()
        # bootstrap
        elif len(self._innerState.indexScore) < self._innerState.maxSize:
            return
        # maintenance
        elif len(self._innerState.dirtyScore) > self._innerState.scoreDirtySize:
            self._rebuildScores()

    # -------------------------
    # rebuild score ordering
    # -------------------------
    def _rebuildScores(self) -> None:
        """
        Synchronizes the ranking by merging dirty updates into the ordered set.

        Algorithm Logic (Lazy Merge):
        1. If state is ORDERED, exits immediately (O(1)).
        2. Collects all scores from the 'dirty' buffer.
        3. Merges new scores with existing ordered scores.
        4. Sorts the consolidated set and truncates to maxSize.
        5. Updates the worstScore and sets state to ORDERED.

        Complexity: O(N + M log M) where M is the dirty window size and N is maxSize. Usually M<<N
        e.g.
            N=1000, M=150 ->  complexity= 1000 + (150*7.23)= 2084 -> O(2N)
            N=10000, M=500 ->  complexity= 10000 + (500*8.97)=14482  -> O(1.5*N)
        """

        # score già pronto, niente da fare qui
        if len(self._innerState.dirtyScore) == 0:
            return

        ordered_items: list[tuple[str, Tuple[float, ...]]] = list(self._innerState.orderedScore.items())

        #Ordino Q
        dirty_sorted: list[tuple[str, Tuple[float, ...]]] = sorted(
            self._innerState.dirtyScore.items(),
            key=lambda x: x[1],
            reverse=self._innerState.maximize
        )

        new_ordered: dict[str, Tuple[float, ...]] = {}
        new_index: dict[str, int] = {}

        i = 0
        j = 0
        lno: int = len(ordered_items)
        lnd: int = len(dirty_sorted)

        # costruisco i primi N elementi
        while (
                len(new_ordered) < self._innerState.maxSize
                and i < lno
                and j < lnd
        ):
            if self._innerBetter(dirty_sorted[j][1], ordered_items[i][1]):
                eid, score = dirty_sorted[j]
                j += 1
            else:
                eid, score = ordered_items[i]
                i += 1
            new_ordered[eid] = score
            new_index[eid] = self.Status.ORDERED

        # Se non ho completato al passo prima aggiungo Orderd (se ci sono)
        while len(new_ordered) < self._innerState.maxSize and i < lno:
            eid, score = ordered_items[i]

            new_ordered[eid] = score
            new_index[eid] = self.Status.ORDERED

            i += 1

        # Se non ho completato al passo prima aggiungo Dirty (se ci sono)
        while len(new_ordered) < self._innerState.maxSize and j < lnd:
            eid, score = dirty_sorted[j]

            new_ordered[eid] = score
            new_index[eid] = self.Status.ORDERED

            j += 1

        # ricomposizione finale
        self._innerState.orderedScore = new_ordered
        self._innerState.dirtyScore.clear()
        self._innerState.indexScore = new_index

        self._innerState.worstScore = next(reversed(self._innerState.orderedScore.values()))

        self._innerState.state= self.Status.ORDERED

    # -------------------------
    # full sort cache
    # -------------------------

    def _rebuildElements(self) -> None:
        """
        Hard pruning of the physical storage.

        Synchronizes scores first, then removes any element from the 'elements'
        dictionary that is no longer present in the 'orderedScore' ranking.
        Ensures memory is reclaimed by dropping sub-optimal candidates.
        """

        if self._innerState.state == self.Status.FULL_SORTED:
            return

        # pruning: tieni solo top-N
        self._rebuildScores()

        new_elements: dict[str, T] = {}
        for i in self._innerState.orderedScore.keys():
            try:
                new_elements[i] = self._innerState.elements[i]

            except KeyError:
                print("chiave non trovata")

        self._innerState.elements = new_elements

        self._innerState.state = self.Status.FULL_SORTED

        return

    def elementTypeReport(self) -> dict[str, int]:
        """Scansiona gli elementi presenti nel Top-K a richiesta.
        Restituisce il conteggio esatto dei tipi, ispezionando l'interno di liste/collezioni.

        :return: dict[str, int]: list of elment
        """

        tipo_counter: dict[str, int] = {}

        for element in self._innerState.elements.values():
            # 1. Se l'elemento è una lista (o tupla/set) ed è popolata, ispezioniamo l'interno
            if isinstance(element, (list, tuple, set)) and len(element) > 0:
                # Estraiamo il tipo del primo sotto-elemento (es. "ProbeActionPlan")
                # Usiamo un iteratore per supportare anche i set che non hanno indici
                primo_figlio = next(iter(element))
                nome_sottotipo = type(primo_figlio).__name__

                # Componiamo la stringa descrittiva (es. "list[ProbeActionPlan]")
                nome_tipo_completo = f"{type(element).__name__}[{nome_sottotipo}]"

            # 2. Se l'elemento è un dizionario popolato, mappiamo chiave e valore
            elif isinstance(element, dict) and len(element) > 0:
                prima_chiave = next(iter(element))
                nome_chiave = type(prima_chiave).__name__
                nome_valore = type(element[prima_chiave]).__name__
                nome_tipo_completo = f"dict[{nome_chiave}, {nome_valore}]"

            # 3. Se l'elemento è un oggetto standard (o una collezione vuota)
            else:
                nome_tipo_completo = type(element).__name__

            # Incrementiamo il contatore per questa specifica struttura
            tipo_counter[nome_tipo_completo] += 1

        # Restituiamo il dizionario con la distribuzione reale delle strutture
        return tipo_counter

  
    
    def _debugCheck(self):
        """Debug function called only in debug mode"""

        # -------------------------
        # key sets
        # -------------------------
        elements_keys = set(self._innerState.elements.keys())
        ordered_keys = set(self._innerState.orderedScore.keys())
        dirty_keys = set(self._innerState.dirtyScore.keys())
        index_keys = set(self._innerState.indexScore.keys())

        score_keys = ordered_keys | dirty_keys

        # -------------------------
        # basic consistency
        # -------------------------
        if not index_keys.issubset(elements_keys):
            raise RuntimeError(
                f"indexScore contains orphan keys: {index_keys - elements_keys}"
            )

        if not score_keys.issubset(index_keys):
            raise RuntimeError(
                f"score_keys contains orphan key: {score_keys - index_keys}"
            )

        if not dirty_keys.issubset(index_keys):
            raise RuntimeError(
                f"dirty_keys contains orphan key: {dirty_keys - index_keys}"
            )

        score_dirty_keys = ordered_keys | dirty_keys

        if index_keys != score_dirty_keys:
            raise RuntimeError(
                f"indexScore mismatch\n"
                f"missing in index: {score_keys - index_keys}\n"
                f"orphan in index: {index_keys - score_keys}"
            )

        # -------------------------
        # overlap forbidden
        # -------------------------
        overlap = ordered_keys & dirty_keys

        if overlap:
            raise RuntimeError(
                f"keys present in both ordered and dirty: {overlap}"
            )

        # -------------------------
        # validate indexScore mapping
        # -------------------------
        for k in ordered_keys:

            state = self._innerState.indexScore.get(k)

            if state != self.Status.ORDERED:
                raise RuntimeError(
                    f"wrong state for ordered key {k}: {state}"
                )

        for k in dirty_keys:

            state = self._innerState.indexScore.get(k)

            if state != self.Status.DIRTY:
                raise RuntimeError(
                    f"wrong state for dirty key {k}: {state}"
                )

        # -------------------------
        # maxValue size invariant
        # -------------------------
        if len(self._innerState.orderedScore) > self._innerState.maxSize:
            raise RuntimeError(
                f"orderedScore overflow: "
                f"{len(self._innerState.orderedScore)} > {self._innerState.maxSize}"
            )

        # -------------------------
        # ordering invariant
        # -------------------------
        ordered_values = list(self._innerState.orderedScore.values())

        for i in range(1, len(ordered_values)):

            prev_score = ordered_values[i - 1]
            curr_score = ordered_values[i]

            if self._innerBetter(curr_score, prev_score):
                raise RuntimeError(
                    f"orderedScore not ordered at position {i}\n"
                    f"prev={prev_score}\n"
                    f"curr={curr_score}"
                )

        # -------------------------
        # worst score invariant
        # -------------------------
        if len(self._innerState.orderedScore) > 0:

            expected_worst = next(
                reversed(self._innerState.orderedScore.values())
            )

            if expected_worst != self._innerState.worstScore:
                if len(self._innerState.orderedScore) < self._innerState.maxSize:
                    print(
                        f"wrong worstScore, but pop element in ordered\n"
                        f"expected={expected_worst}\n"
                        f"actual={self._innerState.worstScore}"
                    )
                else:
                    raise RuntimeError(
                        f"wrong worstScore\n"
                        f"expected={expected_worst}\n"
                        f"actual={self._innerState.worstScore}"
                    )
