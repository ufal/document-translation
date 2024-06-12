import sys
from typing import Any, Callable, List
from tqdm import tqdm

class BatchRequest:
    def __init__(self, batch_max_bytes: int, callback: Callable[[List[Any]], List[Any]], compute_size: Callable[[Any], int]):
        self.batch: List[str] = []
        self.batch_current_bytes = 0
        self.batch_max_bytes = batch_max_bytes
        self.callback = callback
        self.compute_size = compute_size
        self.show_progress = True

        self.results: List[str] = []

    def _send_batch(self) -> None:
        self.results += self.callback(self.batch)
        self.batch = []
        self.batch_current_bytes = 0

    def __call__(self, line: str) -> None:
        size = self.compute_size(line)
        # print(f"Adding {size} bytes to batch of {len(self.batch)} lines", file=sys.stderr)
        if self.batch_current_bytes + size > self.batch_max_bytes:
            print(f"Sending batch of {len(self.batch)} lines", file=sys.stderr)
            self._send_batch()
        self.batch.append(line)
        self.batch_current_bytes += size

    def flush(self) -> None:
        if self.batch:
            self._send_batch()

    def batch_process(self, lines: List[Any]) -> List[Any]:
        sizes = [self.compute_size(line) for line in lines]
        total_size = sum(sizes)
        with tqdm(total=total_size, disable=not self.show_progress) as pbar:
            for size, line in zip(sizes, lines):
                self(line)
                pbar.update(size)
            self.flush()
        return self.results