import time
from dataclasses import dataclass, field
from collections import deque
from threading import Lock

# 📌 LOCK DI CONCORRENZA: Protegge l'accesso ai registri globali in multi-threading
_REGISTRY_LOCK = Lock()

@dataclass(slots=True, kw_only=True)
class AuthPassport:
    authTime: float
    allowExplicit: bool

@dataclass(slots=True, kw_only=True)
class ClassPassport:
    decorated: bool = field(default=False)
    # 📌 OTTIMIZZAZIONE O(1): Usiamo deque invece di list per pop FIFO fulminei
    authorizedBuilds: deque[AuthPassport] = field(default_factory=deque)


_PASSPORT_CLASSES: dict[str, ClassPassport] = {}

def _fqdn(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"

def _setDC(cls: type) -> None:
    """Registra il qualificatore completo della classe decorata custom."""
    fqdn = _fqdn(cls)
    with _REGISTRY_LOCK:  # 🛡️ Thread-safe
        if fqdn not in _PASSPORT_CLASSES:
            _PASSPORT_CLASSES[fqdn] = ClassPassport(decorated=True)
        else:
            _PASSPORT_CLASSES[fqdn].decorated = True


def _isDC(cls: type) -> bool:
    """Verifica se la classe è presente nel registro delle decorate."""
    fqdn = _fqdn(cls)
    with _REGISTRY_LOCK:
        if fqdn not in _PASSPORT_CLASSES:
            return False
        return _PASSPORT_CLASSES[fqdn].decorated


def _setACF(cls: type, allowExplicitDataclass: bool) -> None:
    """Autorizza temporaneamente il boot memorizzando timestamp e flag di failover."""
    fqdn = _fqdn(cls)
    with _REGISTRY_LOCK:  # 🛡️ Evita collisioni se due build partono insieme in parallelo
        if fqdn not in _PASSPORT_CLASSES:
            _PASSPORT_CLASSES[fqdn] = ClassPassport(decorated=False)

        _PASSPORT_CLASSES[fqdn].authorizedBuilds.append(
            AuthPassport(
                authTime=time.time(),
                allowExplicit=allowExplicitDataclass
            )
        )


def _popACF(cls: type) -> AuthPassport | None:
    """Estrae e consuma il passaporto, cancellandolo per sempre dal modulo."""
    fqdn = _fqdn(cls)
    with _REGISTRY_LOCK:  # 🛡️ Garantisce che il Thread che ha fatto build prenda il SUO passaporto
        if fqdn not in _PASSPORT_CLASSES:
            return None
        if len(_PASSPORT_CLASSES[fqdn].authorizedBuilds) == 0:
            return None
        # popleft() su deque è l'equivalente atomico e veloce O(1) di pop(0) su list
        return _PASSPORT_CLASSES[fqdn].authorizedBuilds.popleft()


def _ACFCount() -> int:
    with _REGISTRY_LOCK:
        return sum(len(x.authorizedBuilds) for x in _PASSPORT_CLASSES.values())
