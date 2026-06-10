import random
import sys
import time
from dataclasses import dataclass

from typing import Tuple

from topK.decorator import topKComponent
from topK import TopKRankedRegistry



# -------------------------
# Fake domain object
# -------------------------
@dataclass(slots=True)
class Candidate:
    id: str
    gain: float
    depth: int


# -------------------------
# Concrete implementation
#

@topKComponent
class CandidateTopK(TopKRankedRegistry[Candidate]):

    def _buildScore(self, element: Candidate) -> Tuple[float, ...]:
        return (
            element.gain,
            -element.depth
        )

    def _getElementId(self, element: Candidate) -> str:
        return element.id



def getCandidateTopK(maxSize:int,maxmize:bool ) -> CandidateTopK:
    
    return CandidateTopK.build(
        maxSize=maxSize,
        maximize=maxmize
    )




# -------------------------
# Test generator
# -------------------------
def generate_candidate(i: int) -> Candidate:

    return Candidate(
        id=f"node_{i}",
        gain=round(random.uniform(0, 100), 2),
        depth=random.randint(1, 30)
    )


# -------------------------
# Helpers
# -------------------------
def build_score(c: Candidate):
    return (
        c.gain,
        -c.depth
    )


# -------------------------
# Main
# -------------------------
def main(vers:int=1):

    if len(sys.argv) < 2:
        print("Usage: python test_topk.py <N> [TOTAL]")
        sys.exit(1)

    max_size = int(sys.argv[1])

    total = (
        int(sys.argv[2])
        if len(sys.argv) > 2
        else max_size * 10
    )

    random.seed(42)

    # -------------------------
    # structures
    # -------------------------
    topk_max = getCandidateTopK(maxSize=max_size,maxmize=True, vers=vers)
    topk_min = getCandidateTopK(maxSize=max_size,maxmize=False, vers=vers)

    all_candidates: list[Candidate] = []
    removed_ids: set[str] = set()

    last_id: str | None = None

    #topk_max.clear()
    # -------------------------
    # generation phase
    # -------------------------

    if topk_max._pushHandler == topk_max._disabledPush:
        print("TOPK ERROR")
        return

    for i in range(total):

        candidate = generate_candidate(i)

        all_candidates.append(candidate)

        eid1 = topk_max.push(candidate)
        eid2 = topk_min.push(candidate)

        if eid1 is not None:
            last_id = eid1

        # random delete previous id
        if last_id is not None and random.random() < 0.15:

            topk_max.pop(last_id)
            topk_min.pop(last_id)

            removed_ids.add(last_id)
            last_id = None

    # -------------------------
    # random invalid removals
    # -------------------------
    for _ in range(max_size):

        fake_id = f"fake_{random.randint(0, 999999)}"

        topk_max.pop(fake_id)
        topk_min.pop(fake_id)

    # -------------------------
    # expected lists
    # -------------------------
    remaining = [
        c for c in all_candidates
        if c.id not in removed_ids
    ]

    expected_max = sorted(
        remaining,
        key=build_score,
        reverse=True
    )[:max_size]

    expected_min = sorted(
        remaining,
        key=build_score,
        reverse=False
    )[:max_size]

    actual_max = list(topk_max.values())
    actual_min = list(topk_min.values())

    # -------------------------
    # validation
    # -------------------------
    ok_max = [c.id for c in expected_max] == [c.id for c in actual_max]
    ok_min = [c.id for c in expected_min] == [c.id for c in actual_min]

    # -------------------------
    # output
    # -------------------------
    print()
    print("========================")
    print("VALIDATION")
    print("========================")
    print()

    print(f"MAX TOPK OK : {ok_max}")
    print(f"MIN TOPK OK : {ok_min}")

    print()
    print("========================")
    print("TOP MAX")
    print("========================")
    print()

    for idx, c in enumerate(actual_max, start=1):
        print(
            f"{idx:03d} | "
            f"id={c.id} | "
            f"gain={c.gain:.2f} | "
            f"depth={c.depth} | "
            f"score={build_score(c)}"
        )

    print()
    print("========================")
    print("TOP MIN")
    print("========================")
    print()

    for idx, c in enumerate(actual_min, start=1):
        print(
            f"{idx:03d} | "
            f"id={c.id} | "
            f"gain={c.gain:.2f} | "
            f"depth={c.depth} | "
            f"score={build_score(c)}"
        )

    print()
    print("========================")
    print("STATS")
    print("========================")
    print()

    print(f"Generated : {len(all_candidates)}")
    print(f"Removed   : {len(removed_ids)}")
    print(f"Top size  : {max_size}")


if __name__ == "__main__":
    tempo_esecuzione1: int=0
    tempo_esecuzione2: int=0
    ts_start:float = time.perf_counter()
    main(1)
    ts_end:float = time.perf_counter()
    tempo_esecuzione1 = ts_end - ts_start
    
    """ For comparision
    ts_start = time.perf_counter()
    main(1)
    ts_end = time.perf_counter()
    # 3. Calcola il tempo totale trascorso
    tempo_esecuzione2 = ts_end - ts_start"""
    print(f"Tempo di esecuzione\n\t1: {tempo_esecuzione1:.6f} secondi\n\t2: {tempo_esecuzione2:.6f} secondi")

"""
## Esempio esecuzione
    python test_topk.py 10
oppure:
    ython test_topk.py 50 10000
Dove:
* `10` oppure `50` = N
* `10000` = numero totale elementi generati
"""
