from dataclasses import dataclass, field
from typing import Tuple, TypeVar

from .base import TopKBase
T = TypeVar(
    "T",
    covariant=True
)

@dataclass(slots=True, kw_only=True)
class InnerState[T]:
    """
    Internal container for the Top-K state and data structures.

    Encapsulates the raw storage and ranking buffers to keep the main class
    logic clean. Uses slots for memory efficiency.

    Attributes:
        maxSize: Target number of top elements to retain.
        maxSlice: Hard limit for raw storage before forced pruning.
        elements: Map of all current candidates (Top-K + Dirty Window).
        orderedScore: Validated Top-K scores in sorted order.
        dirtyScore: Buffer for new or updated scores awaiting merge.
        state: DIRTY / ORDERED / FULL_SORTED
        indexScore: Map tracking if an ID is in DIRTY or ORDERED state.
        scoreDirtySize: size of dirty window
        worstScore: worst element, barrier to new push
        ingestionEnabled: flag to trace if ingestion is disabled
        copyStrategy: how to copy element before ingestion
        retrievalEnabled: flag to trace if retrieval i

    """

    maxSize: int
    maximize: bool = field(default=True)
    dirtyWindowsFactor: float = 1.0
    # Inizializza questi campi come non inclusi nell'init automatico
    maxSlice: int = field(default=0)
    elements: dict[str, T] = field(default_factory=dict)
    orderedScore: dict[str, Tuple[float, ...]] = field(default_factory=dict)
    dirtyScore: dict[str, Tuple[float, ...]] = field(default_factory=dict)
    indexScore: dict[str, int] = field(default_factory=dict)
    state: TopKBase.Status = field(default=0)
    scoreDirtySize: int = field(default=0)
    worstScore: Tuple[float, ...] = field(default_factory=tuple)

    copyStrategy: TopKBase.CopyStrategy= field(compare=False, default=TopKBase.CopyStrategy.ADAPTIVE)
    accessContract: TopKBase.AccessContract= field(compare=False, default=TopKBase.AccessContract.LAZY_AUTO_FREEZE_MODE)
    retrievalEnabled: bool = field(default=False, compare=False)
    ingestionEnabled: bool = field(default=True, compare=False)


    def __post_init__(self):
        # Logica di calcolo che avevi nell'init
        dwf = max(self.dirtyWindowsFactor, 0.3)
        self.maxSlice = int(round(self.maxSize * (1 + dwf), 0))
        self.clear()
        qMax = int(round((self.maxSlice - self.maxSize) / 2, 0))
        q = int(round(1.2 * self.maxSize ** 0.65, 0))
        self.scoreDirtySize = max(2, min(q, qMax))

    def clear(self) -> None:
        """Reset storage"""
        self.elements.clear()
        # self.score = {}
        self.dirtyScore.clear()
        self.indexScore.clear()
        self.orderedScore.clear()
        self.state = TopKBase.Status.DIRTY
        self.ingestionEnabled = False
        self.retrievalEnabled = False