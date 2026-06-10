from typing import Protocol, Self, Tuple, runtime_checkable
from .asDict import TopKAsDict
from .base import TopKBase
from .decorator import topKComponent
from .innerState import InnerState

@runtime_checkable
@topKComponent
class TopKRankedRegistry[T](TopKAsDict[T],Protocol):
    """
    A high-performance Lazy Top-K ranking manager with Dirty Window pruning.

    This class implements a memory-efficient ranking system that defers
    sorting costs until strictly necessary. It uses a 'dirty window'
    strategy (O(N) merge) to maintain a stabilized Top-K set while allowing
    fast O(1) or O(log N) insertions for most cases.

    The class behaves like a Python MutableMapping, exposing only the
    stabilized Top-K elements through standard dictionary APIs, while
    internal raw storage may temporarily hold additional candidates.

    Type Args:
        T: The type of elements being ranked.

    Access Control and Ingestion/Retrieval Phasing:
    The engine operates under a strict 'AccessContract' policy to regulate
    data flow and ensure internal consistency during high-speed execution:

    1. LAZY_AUTO_FREEZE_MODE: Transitions permanently to read-only upon the first read(*).
    2. MUTUAL_EXCLUSIVE_MODE: Strict XOR behavior. Enabling ingestion disables
       retrieval, and enabling retrieval disables ingestion.
    3. CUMULATIVE_MODE: Open OR behavior. Ingestion and retrieval states can
       accumulate and operate independently. (**)

    The programmer controls these phases via the 'ingestionEnabled' and
    'retrievalEnabled' properties. Internal guard checks (_ingestionAllowed and
    _retrievalAllowed) protect entry points, raising a RuntimeError on violations.

    (*)CRITICAL: This structure uses dynamic states. Once data is read
    via iterators, values, or get(), the structure changes to read-only
    and subsequent pushes will raise a RuntimeError.
    Call activateLoading() to unlock.

    (**)CRITICAL: You must be aware each read rebuild state (ordering) in worst case.
    It's your responsability to build algorithm with the right approach.

    Declaration:
        @topKComponent
        def class TopKUtils[T](Protocol):
    Inherits:
        @runtime_checkable -> for beartype
        @topKComponent: inherited class must use same declaration, don't use __init__
        Protocol: Requires implementation of _buildScore and _getElementId.
        [T]: For strict type hinting of ranked elements.

    Abstract Methods:
        _buildScore
        _getElementId

    Overridable (discouraged):
        _better
            (self, a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
            return (a > b) if self._innerState.maximize else (a < b)
        _worse
            (self, a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
            return self._better(b, a)
    Overridable (performance Need)
        def _copyElement(self, value: T) -> T:
            various approach to copy usaully the standard way: NONE, DEEP (COPY), SHALLOW (COPY), should be enough
            but if in a subclass elemente is a list (or dict, set) list(element) is faster

    DESIGN PHILOSOPHY:
    This class is designed for scenarios where the cost of continuous sorting is
    prohibitive. It accepts a 'dirty' state during massive ingestion phases,
    deferring the O(N + M log M) consolidation only when data access is required.
    It bridges the gap between a fast O(1) buffer and a strictly ordered ranking.

    MEMORY AND DATA INTEGRITY POLICY:
    To prevent external mutation side effects (such as clear() operations on
    incoming collections), this class implements an adaptive defensive copying
    mechanism guided by 'copyStrategy'.

    Subclasses managing specialized or mutable elements are encouraged to
    override the protected '_copyElement' method to implement fine-grained,
    context-aware cloning behaviors without destroying ingestion performance.

    EFFICIENCY STRATEGIES:
    - Bootstrap Phase: Instant insertion until maxSize is reached.
    - Score Shielding: Once full, new elements are discarded in O(1) if they
      don't beat the current 'worstScore'.
    - Lazy Rebuilds: Sorting and pruning are batched, reducing CPU churn
      proportional to the 'dirtyWindowsFactor'.
    - Element Updates: Seamlessly handles re-insertion of existing IDs with
      improved scores.

    USE CASES:
    - Graph Exploration (e.g., Beam Search): Managing a frontier of thousands
      of candidate paths while expanding only the best K.
    - Real-time Stream Ranking: Filtering high-frequency events to maintain
      a live 'Top-N' dashboard.
    - Heavy Object Management: Keeps 'maxSlice' heavy objects in memory
      (2x to 3x maxSize) to minimize frequent allocations/deallocations.

    SPACE COMPLEXITY:
    The raw storage footprint is defined by:
    - Memory: maxSlice * sizeof(T) + maxSize * sizeof(score_tuple).
    - Rebuild Frequency: Occurs every (maxSize * dirtyWindowsFactor) successful pushes.
    """

    @classmethod
    def build(
        cls,
        maxSize: int,
        dirtyWindowsFactor: float = 1.0,
        maximize: bool = True,
        accessContract: TopKBase.AccessContract=TopKBase.AccessContract.LAZY_AUTO_FREEZE_MODE,
        copyStrategy: TopKBase.CopyStrategy=TopKBase.CopyStrategy.ADAPTIVE,
        allowExplicitDataclass: bool = False
    ) -> Self:

        # 1. Initaialize factory
        if not cls._build(cls, allowExplicitDataclass):
            RuntimeError("Build Denied for %s.", cls.__name__)

        # 2. Build class
        return cls(
            _innerState=InnerState[T](
                maxSize=maxSize,
                dirtyWindowsFactor=dirtyWindowsFactor,
                maximize=maximize,
                accessContract=accessContract,
                copyStrategy=copyStrategy
            )
        )




    def __post_init__(self) -> None:

        self._checkInstance()
        # All'inizio il simulatore scrive liberamente
        self.enableIngestion()

    def clear(self) -> None:
        """Reset the entire storage, clearing all elements and ranking data.

        Enable ingestion phase
        disable retrieval phase if contract foresees
        """

        #print(f"DEBUG: tipo di _innerState è {type(self._innerState)}, valore: {self._innerState}")
        self._innerState.clear()
        self.enableIngestion()

    # =========================================================================
    # ACCESS CONTRACT PROPERTIES (The Controller Panel)
    # =========================================================================
    @property
    def ingestionEnabled(self) -> bool:
        """Get the current activation status of the data ingestion phase."""
        return self._innerState.ingestionEnabled

    @property
    def retrievalEnabled(self) -> bool:
        """Get the current activation status of the data retrieval phase."""
        return self._innerState.retrievalEnabled


    def finalize(self) -> None:
        """Wrapper for _rebuildElements
        disable lazy load
        """
        self.enableRetrieval(True)



    # -------------------------
    # score / abstract method
    # -------------------------
    def _buildScore(self, element: T) -> Tuple[float, ...]: ...

    def _getElementId(self, element: T) -> str: ...



