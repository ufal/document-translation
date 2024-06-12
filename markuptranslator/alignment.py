from collections import defaultdict
from typing import Callable, Dict, Iterable, List, Optional, Self, Set, Tuple


class Alignment:
    # TODO (low priority): instead of Set[Tuple[int, int]] we could use something like Dict[Segment, List[Segment]]
    #                      that way the alignment would be invariant to the order of the segments
    def __init__(self, mapping: Optional[Iterable[Tuple[int, int]]] = None):
        if mapping is None:
            mapping = set()
        self.mapping = set(mapping)
        self._src_to_tgt = None
    
    @property
    def src_to_tgt(self) -> Dict[int, List[int]]:
        if self._src_to_tgt is None:
            src_to_tgt: Dict[int, List[int]] = defaultdict(list)
            for i, j in self.mapping:
                src_to_tgt[i].append(j)
            self._src_to_tgt = src_to_tgt
        return self._src_to_tgt
    
    def is_empty(self) -> bool:
        return len(self.mapping) == 0
    
    def add(self, pair: Tuple[int, int]) -> None:
        self._src_to_tgt = None
        self.mapping.add(pair)

    def get_src(self, i: int) -> List[int]:
        return self.src_to_tgt.get(i, [])

    def map(self, f: Callable[[int, int], Tuple[int, int]]):
        return Alignment(map(lambda x: f(*x), self.mapping))

    def filter(self, f: Callable[[int, int], bool]):
        return Alignment(filter(lambda x: f(*x), self.mapping))
    
    def __str__(self) -> str:
        return f"Alignment({sorted(self.mapping)})"
    
    def __add__(self, other: Self):
        return Alignment(self.mapping.union(other.mapping))
    
    def compose(self, other: Self):
        new_alignment: Set[Tuple[int, int]] = set()
        for (i, js) in self.src_to_tgt.items():
            for j in js:
                for k in other.src_to_tgt[j]:
                    new_alignment.add((i, k))
        return Alignment(new_alignment)

