import copy
from dataclasses import field, dataclass
from typing import Tuple, final, Callable, Protocol
from .inspection import TopKInspection
from .decorator import topKComponent


#@dataclass(slots=True, kw_only=True, eq=False,repr=False,unsafe_hash=False)
@topKComponent
class TopKInteraction[T](TopKInspection[T],Protocol):

    # 📌 I DUE STRUMENTI DINAMICI: Memorizzati qui dentro, invisibili all'utente
    _pushHandler: Callable[[T], str|None] = field(init=False, repr=False, compare=False)
    _popHandler: Callable[[str], T|None] = field(init=False, repr=False, compare=False)

    # ------------------------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------------------

    @property
    def isMoreThanHalf(self) -> bool:
        """Check if the storage has reached more than 50% of its capacity.

        Note:
            This check is performed against raw storage (including dirty window)
            to provide a responsive metric during the bootstrap phase.

        :return: bool
        """
        return len(self._innerState.elements) > (self._innerState.maxSize / 2)

    @property
    def maxSize(self) -> int:
        """
        :return: int: The maximum number of elements allowed in the stabilized ranking.
        """

        return self._innerState.maxSize

    @property
    def topElement(self) -> T:
        """Retrieve top element from raw storage without triggering a rebuild.

        :return: T
        """
        eid: str = next(iter(self._innerState.orderedScore.keys()))
        return self._innerState.elements[eid]

    @property
    def bottomElement(self) -> T:
        """Retrieve bottom element from raw storage without triggering a rebuild.

        :return: T
        """
        eid: str = next(reversed(self._innerState.orderedScore.keys()))
        return self._innerState.elements[eid]


    def push(self, element: T) -> str | None:
        """Insert or update an element in the storage.

         The element is ranked and added to a 'dirty window':

             - if the window exceeds the safety threshold (maxSlice), a pruning process is triggered.
             - if element already inserted, will be updated only if new score is better of the old one
             - if len(elements) < maxSize, each element will be inserted
             - otherwise elements I inserted only if the score is better of the worst

         CRITICAL: This structure uses dynamic states. Once data is read
         via iterators, values, or get(), the structure changes to read-only
         and subsequent pushes will raise a RuntimeError.
         Call activateLoading() to unlock.


         :param element: T -> element to be ranked and to insert or update

         :return: str | None: The element ID if accepted/updated, None if immediately discarded.

         """

        return self._pushHandler(element)

    def pop(self, eid: str) -> T | None:
        """Remove and return an element from the TopK structure by its key.
        CRITICAL: This structure uses dynamic states. Once data is read
        via iterators, values, or get(), the structure changes to read-only
        and subsequent pushes will raise a RuntimeError.
        Call activateLoading() to unlock.

        :param eid: The element ID to remove
        :return: T | None: the element removed if exists. None otherwise
        """

        return self._popHandler(eid)

    #=============================================================================
    # inner Method
    # =============================================================================

    @final
    def _validateAbstractMethod(self, eid, score):
        """Ensure the override methods return the right objects

        :param eid: The id of the element
        :param score: The score
        :raises TypeError: objects are of the wrong type
        :raises ValueError: element id is empty

        """
        if not isinstance(eid, str):
            raise TypeError(
                f"_getElementId must return str, got {type(eid)}"
            )
        if not eid:
            raise ValueError(
                "_getElementId returned empty id"
            )
        if not isinstance(score, tuple):
            raise TypeError(
                f"_buildScore must return tuple, got {type(score)}"
            )

    def _copyElement(self, value: T) -> T:
        match self._innerState.copyStrategy:
            case self.CopyStrategy.NONE:
                return value
            case self.CopyStrategy.DEEP:
                return copy.deepcopy(value)
            case self.CopyStrategy.SHALLOW:
                return copy.copy(value)

        # self.CopyStrategy.ADAPTIVE

        v_type = type(value)

        # 1. VELOCISSIMO: Rimbalza subito se il tipo è immutabile (0 ns overhead)
        if v_type in self.IMMUTABLE_TYPES:
            return value

        # 2. MICRO-OTTIMIZZAZIONE: Costruttore C nativo per i tipi classici (list, dict, set)
        if v_type in (list, dict, set):
            return v_type(value)

        # 3. VERIFICA DEI CONGELATI: Salta la copia se l'oggetto custom è esplicitamente frozen
        if hasattr(value, "_is_frozen") and value._is_frozen is True:  # type: ignore
            return value
        if hasattr(value, "__dataclass_params__") and getattr(value.__dataclass_params__, "frozen",
                                                              False):  # type: ignore
            return value

        # 4. UNIVERSALE: Per qualsiasi classe custom mutabile non classica, copy.copy() ci salva la vita
        return copy.copy(value)



    def _getElementId(self, element: T) -> str:
        """
        Abstract hook to extract the unique identifier from an element.
        MUST be implemented by the end-programmer in the final subclass.

        Returns the stable unique id for the element.

         Contract:
         - id must be stable across pushes
         - id must uniquely identify the logical element
         - must be a string

         Override required.

         :param element: T -> element to get id for
         :return: string representing unique id for the element

         e.g.
            return element.id -> must be a string
        """
        raise NotImplementedError(
            f"Subclass validation failed: Your custom class must implement "
            f"the '_getElementId' method to extract keys from {type(element).__name__}."
        )

    def _buildScore(self, element: T) -> Tuple[float, ...]:
        """
        Abstract hook to extract the unique identifier from an element.
        MUST be implemented by the end-programmer in the final subclass.

        Builds the ranking score for the element.

        Contract:
            - returned scores must support lexicographic ordering
            - ordering must be consistent across all elements
            - higher scores are considered better if maximize=True

        Override required: Must be implemented by subclasses to define the sorting criteria.

        e.g.:
            return (
                element.rank1,
                -elmento.rank2
            )
        :arg element: T : The object to evaluate.
        :return: Tuple[float, ...]: A tuple representing the score for lexicographical comparison.

        """
        raise NotImplementedError(
            f"Subclass validation failed: Your custom class must implement "
            f"the '_buildScore' method to compute score of the element."
        )


    def _disabledPush(self, value: T) -> str | None:
        raise RuntimeError(
            "Operation denied: The Top-K structure is currently frozen in read-only mode. "
            "Cannot execute push() after data consolidation. Call activateLoading() to unlock."
        )

    def _enabledPush(self, element: T) -> str | None:

        assert self._innerState.ingestionEnabled

        eid = self._getElementId(element)
        new_score = self._buildScore(element)

        # Controlla che i dati generati dalla classe reale siano confrontabili
        self._validateAbstractMethod(eid, new_score)

        #Se esiste già una chiave per questo eid aggiorno solo se migliorativo
        match self._innerState.indexScore.get(eid):
            case self.Status.DIRTY:
                old_score = self._innerState.dirtyScore.get(eid)

                assert old_score is not None

                if self._innerWorse(new_score, old_score):
                    return eid
            case self.Status.ORDERED:
                old_score = self._innerState.orderedScore.get(eid)
                assert old_score is not None, "old_Score non può essere None"
                if self._innerWorse(new_score, old_score):
                    return eid
                self._innerState.orderedScore.pop(eid)

        # Nuovo peggiore
        # Vale solo se ho orderedScore saturo, altrimenti
        # non è detto che ci siano dati buoni
        if len(self._innerState.orderedScore) > self._innerState.maxSize:
            if self._innerWorse(new_score, self._innerState.worstScore):
                #Se non c'è un spazio escludo
                return None

        #store with copy
        self._innerState.elements[eid] = self._copyElement(element)
        self._innerState.dirtyScore[eid] = new_score
        self._innerState.indexScore[eid] = self.Status.DIRTY
        self._innerState.state = self.Status.DIRTY
        self._maybePrune()

        if __debug__: self._debugCheck()

        return eid


    def _disabledPop(self, id: str) -> T | None:
        raise RuntimeError(
            "Operation denied: The Top-K structure is currently frozen in read-only mode. "
            "Cannot execute pop() after data consolidation. Call activateLoading() to unlock."
        )


    def _enabledPop(self, id: str) -> T | None:

        assert self._innerState.ingestionEnabled


        match self._innerState.indexScore.get(id, None):
            case self.Status.DIRTY:
                self._innerState.dirtyScore.pop(id, None)
            case self.Status.ORDERED:
                self._innerState.orderedScore.pop(id, None)

        el: T = self._innerState.elements.pop(id, None)
        self._innerState.indexScore.pop(id, None)

        if __debug__: self._debugCheck()

        return el

        """
        Non è più così utile
        # Ho rimosso il peggiore
        if old_score == self._innerState.worstScore:
            self._innerState.worstScore=None
            for currScore in self._innerState.score:
                if self._innerState.worstScore==None or self._worster(currScore, self._innerState.worstScore):
                    self._innerState.worstScore=currScore
        """

    # =========================================================================
    # Setter
    # =========================================================================
    def enableRetrieval(self, deep:bool=False)-> None:
        """
        Set the activation status of the data retrieval phase.
        Enforcing MUTUAL_EXCLUSIVE_MODE will automatically turn off ingestion.
        Triggers an internal score rebuild before allowing access.

        :param deep: bool Activate complete rebuild and ranking
        """

        self._innerState.retrievalEnabled=True
        
        
        
        if self._innerState.accessContract < self.AccessContract.CUMULATIVE_MODE:
            if deep: self._rebuildElements()
            else: self._rebuildScores()

            self._innerState.ingestionEnabled= False
            self._popHandler = self._disabledPop
            self._pushHandler = self._disabledPush
            
            
    def enableIngestion(self) -> None:
        """
        Set the activation status of the data ingestion phase.
        Enforcing MUTUAL_EXCLUSIVE_MODE will automatically turn off retrieval.
        """

        self._innerState.ingestionEnabled=True
        self._popHandler = self._enabledPop
        self._pushHandler = self._enabledPush

        assert self._pushHandler == self._enabledPush

        if self._innerState.accessContract < self.AccessContract.CUMULATIVE_MODE:
            self._innerState.retrievalEnabled = False
