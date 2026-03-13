"""
Task worker using ThreadPoolExecutor.
Processes tasks asynchronously without requiring Redis/Celery infrastructure.
Can be upgraded to Celery later by swapping the executor.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue as PyQueue

from config.settings import Config
from queue.tasks import Task

logger = logging.getLogger(__name__)


class TaskWorker:
    """
    Background task worker using a thread pool.
    Submit tasks and they'll be processed asynchronously.
    """

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or Config.MAX_WORKERS
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        logger.info(f"✅ TaskWorker initialized with {self.max_workers} workers")

    def submit(self, task: Task, work_fn, *args, **kwargs) -> Future:
        """
        Submit a task for background processing.

        Args:
            task: The Task object
            work_fn: The function to execute
            *args, **kwargs: Arguments for work_fn
        """
        task.status = "running"
        logger.info(f"📤 Submitting: {task}")

        def _wrapped():
            try:
                result = work_fn(*args, **kwargs)
                task.result = result
                task.status = "completed"
                if task.callback:
                    task.callback(task)
                return result
            except Exception as e:
                task.error = str(e)
                task.status = "failed"
                logger.error(f"❌ Task failed: {task} — {e}")
                if task.callback:
                    task.callback(task)
                raise

        future = self.executor.submit(_wrapped)

        with self._lock:
            task_key = f"{task.task_type.value}_{task.chat_id}_{id(task)}"
            self._futures[task_key] = future

        return future

    def get_active_count(self) -> int:
        """Get number of currently running tasks."""
        with self._lock:
            return sum(1 for f in self._futures.values() if not f.done())

    def shutdown(self, wait: bool = True):
        """Gracefully shutdown the worker pool."""
        logger.info("🛑 Shutting down TaskWorker...")
        self.executor.shutdown(wait=wait)


# Global singleton
task_worker = TaskWorker()
