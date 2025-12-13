from typing import List
from datetime import datetime # Still used for uploaded_at placeholder
import json

from fastapi import APIRouter, HTTPException

import schemas, database # services no longer directly used here

router = APIRouter()

# Schema change for GuidelineResponse to reflect JSON checklist metadata
class GuidelineResponse(schemas.BaseModel):
    id: str
    filename: str
    uploaded_at: str
    size: int
    pages: int # Represents number of requirements for checklists
    vectorstore_ready: bool = True # Always true for loaded checklists
    description: str # The checklist name

@router.get("/guidelines", response_model=List[GuidelineResponse])
async def list_guidelines():
    """List all available pre-defined JSON checklists."""
    return [GuidelineResponse(**g) for g in database.guidelines_db.values()]

@router.get("/guidelines/{guideline_id}/details")
async def get_guideline_details(guideline_id: str):
    """Get detailed checklist information including all requirements."""
    if guideline_id not in database.guidelines_db:
        raise HTTPException(status_code=404, detail="Guideline not found")

    guideline = database.guidelines_db[guideline_id]
    file_path = guideline.get("file_path")

    if not file_path:
        raise HTTPException(status_code=500, detail="Guideline file path not found")

    try:
        # Read the full JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            checklist_data = json.load(f)

        # Return the complete checklist data
        return {
            "checklist_name": checklist_data.get("checklist_name", "Unknown"),
            "version": checklist_data.get("version", "1.0"),
            "last_updated": checklist_data.get("last_updated", ""),
            "regulations": checklist_data.get("regulations", []),
            "total_requirements": checklist_data.get("total_requirements", len(checklist_data.get("requirements", []))),
            "requirements": checklist_data.get("requirements", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read checklist file: {str(e)}")
