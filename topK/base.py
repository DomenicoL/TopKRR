import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Set, Type, ClassVar, Protocol, final

from ._reg import _isDC, _popACF, _setACF
from .decorator import topKComponent


#@dataclass(slots=True, kw_only=True, eq=False,repr=False,unsafe_hash=False)
@topKComponent
class TopKBase(Protocol):
    class Status(IntEnum):
        """Inner status of storage"""
        DIRTY = 0
        ORDERED = 1
        FULL_SORTED = 2

    class CopyStrategy(IntEnum):
        NONE = 0
        SHALLOW = 1
        ADAPTIVE = 2
        DEEP = 3

    class AccessContract(IntEnum):
        LAZY_AUTO_FREEZE_MODE = 0
        MUTUAL_EXCLUSIVE_MODE = 1
        CUMULATIVE_MODE = 2

    IMMUTABLE_TYPES: ClassVar[Set[Type[Any]]] = {int, float, str, bool, tuple, frozenset, bytes, type(None)}

    # -------------------------------------
    # 📌 ATTRIBUTI DI ISTANZA: Sono campi della dataclass!


    # -------------------------------------
    # 📌 METODI MAGICI: disattivato, non è un attributo
    __hash__ = None

    # =========================================================================
    # FRAMEWORK INTERNAL IMPLEMENTATIONS (Mimetized and hidden)
    # =========================================================================

    @final
    @classmethod
    def _build(cls, currentCls:Type, allowExplicitDataclass: bool) -> bool:
        _setACF(currentCls, allowExplicitDataclass)
        return True

    @final
    def _checkInstance(self) -> None:
        """
              Rigidly validates the creation contract and structural configuration.
              Burns the temporary passport immediately to enforce a single-use lifecycle.
              """
        currentCls = self.__class__


        # 🛡️ BARRIER 1: Constructor Authorization Validation (Anti-Junior Proxy)
        # Consume the passport immediately to prevent subsequent hacks or reuses
        acf=_popACF(currentCls)

        if acf is None:
            raise RuntimeError(
                f"Instantiation Denied: Direct construction of '{currentCls.__name__}' is forbidden. "
                f"You must use the authorized factory method: {currentCls.__name__}.build(...)"
            )

        # Consume the passport immediately to prevent subsequent hacks or reuses
        if (time.time() - acf.authTime) > 0.1:
            raise RuntimeError(f"Instantiation Expired: Construction session for '{currentCls.__name__}' timed out.")

        # 🛡️ BARRIER 2: Decorator Framework Alignment Check
        # Inspects the global object-set. If the subclass used standard @dataclass
        # without our custom decorator, it blocks boot unless manual failover is on.

        if not _isDC(currentCls) and not acf.allowExplicit:
            raise TypeError(
                f"Architecture Violation in '{currentCls.__name__}': "
                f"The class must be directly decorated with '@topKComponent'. "
                f"If you intentionally intend to use an explicit standard @dataclass, "
                f"you must pass: .build(..., allowExplicitDataclass=True)."
            )


        # 🛡️ BARRIER 3: Structural Dataclass Parameters Verification
        params = getattr(self, "__dataclass_params__")

        if params is None:
            raise TypeError(
                f"Architecture Violation in '{self.__class__.__name__}': Must be decorated with @dataclass.")

        #print(params)

        if not params.slots:
            raise TypeError(f"Architecture Violation in '{self.__class__.__name__}': Must enforce 'slots=True'.\nHINT: use @topKComponent")
        if not params.kw_only:
            raise TypeError(f"Architecture Violation in '{self.__class__.__name__}': Must enforce 'kw_only=True'.\nHINT: use @topKComponent")
        if params.eq:
            raise TypeError(f"Architecture Violation in '{self.__class__.__name__}': Must enforce 'eq=False'.\nHINT: use @topKComponent")
        #if params.repr:
        #    raise TypeError(f"Architecture Violation in '{self.__class__.__name__}': Must enforce 'repr=False'.\nHINT: use @topKComponent")
        if params.unsafe_hash:
            raise TypeError(f"Architecture Violation in '{self.__class__.__name__}': Must enforce 'unsafe_hash=False'.\nHINT: use @topKComponent")