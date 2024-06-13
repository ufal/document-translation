from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Self, Set, Tuple

from markuptranslator.segmentedtext import Segment


class Alignment:
    def __init__(self, src_to_tgt: Optional[Dict[Segment, Set[Segment]]] = None):
        if src_to_tgt is None:
            self._src_to_tgt: defaultdict[Segment, Set[Segment]] = defaultdict(set)
        else:
            self._src_to_tgt = defaultdict(set, src_to_tgt)
        self.init_aligned_sets()
    
    def init_aligned_sets(self) -> None:
        self.aligned_tgts: Counter[Segment] = Counter()
        for _, tgt_set in self._src_to_tgt.items():
            self.aligned_tgts.update(tgt_set)

    @classmethod
    def from_iterable(cls, alignment: Iterable[Tuple[Segment, Segment]]) -> Self:
        instance = cls()
        instance.update_from_iterable(alignment)
        return instance
    
    def update_from_iterable(self, alignment: Iterable[Tuple[Segment, Segment]]) -> None:
        for (src_seg, tgt_seg) in alignment:
            self._src_to_tgt[src_seg].add(tgt_seg)
            self.aligned_tgts[tgt_seg] += 1

    def is_src_aligned(self, src: Segment) -> bool:
        return bool(self.get(src))
    
    def is_tgt_aligned(self, tgt: Segment) -> bool:
        return tgt in self.aligned_tgts and self.aligned_tgts[tgt] > 0

    def is_empty(self) -> bool:
        return len(self._src_to_tgt) == 0 or all(len(s) == 0 for s in self._src_to_tgt.values())
    
    def add(self, src: Segment, tgt: Segment) -> None:
        self._src_to_tgt[src].add(tgt)
        self.aligned_tgts[tgt] += 1
    
    def remove(self, src: Segment, tgt: Segment) -> None:
        self._src_to_tgt[src].remove(tgt)
        self.aligned_tgts[tgt] -= 1

    def get(self, src: Segment) -> Set[Segment]:
        return self._src_to_tgt[src]

    def to_list(self) -> List[Tuple[Segment, Segment]]:
        return [(src, tgt) for (src, tgt_set) in self._src_to_tgt.items() for tgt in tgt_set]

    def __str__(self) -> str:
        return f"Alignment({self.to_list()})"

    def __add__(self, other: Self):
        new_alignment = Alignment(self._src_to_tgt)
        for (src, tgt_set) in other._src_to_tgt.items():
            for tgt in tgt_set:
                new_alignment.add(src, tgt)
        return new_alignment
    
    def swap(self) -> "Alignment":
        new_alignment = Alignment()
        for (src, tgt_set) in self._src_to_tgt.items():
            for tgt in tgt_set:
                new_alignment.add(tgt, src)
        return new_alignment

    def compose(self, other: Self):
        composed_alignment = Alignment()
        for (src, tgt_set) in self._src_to_tgt.items():
            for tgt in tgt_set:
                for other_tgt in other.get(tgt):
                    composed_alignment.add(src, other_tgt)
        return composed_alignment
