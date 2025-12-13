from typing import Dict, Any, List
import asyncio

# In-memory store for API keys and other global configurations.
# In a real-world scenario, this would be a proper database.
API_KEYS: Dict[str, str] = {}

# In-memory store for active guidelines/checklists
# Key: guideline_id (str), Value: dict of guideline metadata and requirements
guidelines_db: Dict[str, Dict[str, Any]] = {}

# In-memory store for uploaded reports
# Key: report_id (str), Value: dict of report metadata
reports_db: Dict[str, Dict[str, Any]] = {}

# In-memory store for task statuses
# Key: task_id (str), Value: dict of task status, progress, result etc.
tasks_db: Dict[str, Dict[str, Any]] = {}

# In-memory store for task progress queues (for SSE)
# Key: task_id (str), Value: asyncio.Queue
task_queues: Dict[str, asyncio.Queue] = {}

# In-memory store for running asyncio.Task objects (for cancellation)
# Key: task_id (str), Value: asyncio.Task
running_async_tasks: Dict[str, asyncio.Task] = {}