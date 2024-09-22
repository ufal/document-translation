import logging
from typing import Any, Callable, List
from tqdm import tqdm

logger = logging.getLogger(__name__)

class BatchRequest:
    def __init__(self, batch_max_bytes: int, callback: Callable[[List[Any]], List[Any]], compute_size: Callable[[Any], int], show_progress):
        self.batch: List[str] = []
        self.batch_current_bytes = 0

        self.batch_max_bytes = batch_max_bytes
        self.callback = callback
        self.compute_size = compute_size
        self.show_progress = show_progress

        self.results: List[str] = []
    
    def clean(self) -> None:
        self.batch = []
        self.batch_current_bytes = 0
        self.results = []

    def _send_batch(self) -> None:
        self.results += self.callback(self.batch)
        self.batch = []
        self.batch_current_bytes = 0

    def __call__(self, line: str) -> None:
        size = self.compute_size(line)
        logger.debug(f"Adding {size} bytes to batch of {len(self.batch)} lines")
        # TODO: handle the case where a single line is larger than the batch size
        if self.batch_current_bytes + size > self.batch_max_bytes:
            logger.debug(f"Sending batch of {len(self.batch)} lines")
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
        results = self.results
        self.clean()
        return results