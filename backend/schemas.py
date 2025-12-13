from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class GuidelineResponse(BaseModel):
    id: str
    filename: str
    uploaded_at: str
    size: int
    pages: Optional[int] = None
    vectorstore_ready: Optional[bool] = None


class MatchRequest(BaseModel):
    guideline_ids: List[str]


class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    message: str
    result: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str
