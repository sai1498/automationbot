"""
Task definitions for the queue system.
Wraps heavy operations (AI, image gen, publishing) as discrete tasks.
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    CONTENT_GENERATION = "content_generation"
    IMAGE_GENERATION = "image_generation"
    PUBLISHING = "publishing"


class Task:
    """A unit of work to be processed by a worker."""

    def __init__(self, task_type: TaskType, payload: dict, user_id: int = None,
                 chat_id: int = None, callback=None):
        self.task_type = task_type
        self.payload = payload
        self.user_id = user_id
        self.chat_id = chat_id
        self.callback = callback  # Function to call when task completes
        self.status = "pending"  # pending, running, completed, failed
        self.result = None
        self.error = None

    def __repr__(self):
        return f"<Task {self.task_type.value} [{self.status}] user={self.user_id}>"
