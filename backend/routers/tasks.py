import asyncio
import uuid
import json
import logging
from typing import List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel # Import BaseModel for new request/response schemas
from sse_starlette.sse import EventSourceResponse

import schemas, config, database, services
from pdf_generator import generate_compliance_pdf

logger = logging.getLogger(__name__)
router = APIRouter()

# New Pydantic models for the revised workflow
class ReportUploadResponse(BaseModel):
    report_id: str
    filename: str

class ComplianceMatchRequest(BaseModel):
    report_id: str | None = None  # ID of the previously uploaded report (optional)
    guideline_ids: List[str] # IDs of the selected checklists


@router.post("/reports/upload", response_model=ReportUploadResponse)
async def upload_report(file: UploadFile = File(...)):
    """Upload a report PDF and return its ID."""
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    report_id = str(uuid.uuid4())
    save_path = config.REPORTS_DIR / f"{report_id}.pdf" # Save with internal ID
    
    try:
        with open(save_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Store metadata about the uploaded report
        database.reports_db[report_id] = {
            "id": report_id,
            "filename": file.filename,
            "file_path": str(save_path),
            "uploaded_at": datetime.now().isoformat(),
        }

        return ReportUploadResponse(report_id=report_id, filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save report: {str(e)}")


@router.post("/match", response_model=schemas.TaskStatus)
async def start_match(request: Request, report: UploadFile | None = File(None), guideline_ids: str | None = Form(None)):
    """Start a compliance matching task against selected checklists."""

    # Determine incoming format: multipart form with file OR JSON body
    report_path = None
    selected_guidelines: list[str] = []

    try:
        if report is not None:
            # Client sent a file directly in the /match request (legacy or convenience flow)
            if not report.filename or not report.filename.endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are allowed for `report` uploads")

            # Save uploaded report temporarily (same behavior as /reports/upload)
            report_id = str(uuid.uuid4())
            save_path = config.REPORTS_DIR / f"{report_id}.pdf"
            with open(save_path, 'wb') as f:
                f.write(await report.read())

            database.reports_db[report_id] = {
                "id": report_id,
                "filename": report.filename,
                "file_path": str(save_path),
                "uploaded_at": datetime.now().isoformat(),
            }
            uploaded_report = database.reports_db[report_id]
            report_path = str(save_path)

            if not guideline_ids:
                raise HTTPException(status_code=400, detail="`guideline_ids` form field is required when uploading a report file")

            # guideline_ids comes in as a JSON string in the form - parse it
            try:
                selected_guidelines = json.loads(guideline_ids)
            except Exception:
                raise HTTPException(status_code=400, detail="`guideline_ids` must be a JSON array string")
        else:
            # Expect JSON body following the ComplianceMatchRequest schema
            body = await request.json()
            cmr = ComplianceMatchRequest(**body)
            uploaded_report = database.reports_db.get(cmr.report_id)
            if not uploaded_report:
                raise HTTPException(status_code=404, detail="Uploaded report not found.")
            report_path = uploaded_report["file_path"]
            selected_guidelines = cmr.guideline_ids
    except HTTPException:
        # Re-raise HTTPExceptions so FastAPI handles them normally
        raise
    except Exception as e:
        # Catch unexpected parsing errors and return a 400 with a clear message
        raise HTTPException(status_code=400, detail=f"Invalid request payload: {e}")

    # 2. Validate guidelines (checklists) exist
    for gid in selected_guidelines:
        if gid not in database.guidelines_db:
            raise HTTPException(status_code=404, detail=f"Checklist {gid} not found.")
        # Checklists are always vectorstore_ready=True once loaded
    
    # 3. Create a unique task ID
    task_id = str(uuid.uuid4())

    # 4. Initialize task status
    task_data = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task created, starting processing...",
        "result": {"rows": [], "summary": {}},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "report_filename": uploaded_report["filename"], # Use original filename from uploaded report
        "guideline_ids": selected_guidelines,
    }
    database.tasks_db[task_id] = task_data
    database.task_queues[task_id] = asyncio.Queue()

    # 5. Schedule background processing and store the task reference
    background_task = asyncio.create_task(
        services.process_compliance_check(task_id, report_path, selected_guidelines)
    )
    database.running_async_tasks[task_id] = background_task

    return schemas.TaskStatus(**task_data)

@router.get("/tasks", response_model=List[schemas.TaskStatus])
async def list_tasks():
    """List all tasks in the in-memory database."""
    return [schemas.TaskStatus(**t) for t in database.tasks_db.values()]

@router.get("/tasks/{task_id}", response_model=schemas.TaskStatus)
async def get_task_status(task_id: str):
    """Get the current status of a single matching task."""
    if task_id not in database.tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return schemas.TaskStatus(**database.tasks_db[task_id])

@router.get("/tasks/{task_id}/stream")
async def stream_task_status(request: Request, task_id: str):
    """Stream status updates for a matching task using Server-Sent Events."""
    if task_id not in database.task_queues:
        raise HTTPException(status_code=404, detail="Task queue not found or task already completed.")

    async def event_generator():
        queue = database.task_queues.get(task_id)
        if not queue:
            logger.error(f"Event generator for task {task_id}: Queue not found.")
            return # Exit if queue is unexpectedly missing
        
        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    logger.warning(f"Client disconnected from task {task_id} stream. Attempting to cancel background task.")
                    if task_id in database.running_async_tasks:
                        background_task = database.running_async_tasks[task_id]
                        if not background_task.done(): # Only cancel if still running
                            background_task.cancel()
                            logger.info(f"Background task {task_id} cancelled.")
                        else:
                            logger.info(f"Background task {task_id} was already done.")
                        # Remove from running_async_tasks once handled
                        del database.running_async_tasks[task_id]
                    else:
                        logger.warning(f"No running background task found for {task_id} to cancel.")
                    break # Exit generator loop
                
                update = await queue.get()
                if update is None: # Signal for end of stream
                    break
                
                # Update the main task db and yield the update
                update_copy = {k: v for k, v in update.items() if k != 'task_id'}
                services.update_task(task_id, **update_copy)
                yield json.dumps(update)
        except asyncio.CancelledError:
            logger.info(f"Event generator for task {task_id} was cancelled.")
        except Exception as e:
            logger.error(f"Error in event generator for task {task_id}: {e}", exc_info=True)
        finally:
            logger.info(f"SSE stream for task {task_id} closed. Ensuring cleanup.")
            # Ensure task is removed from queues and running tasks
            if task_id in database.task_queues:
                del database.task_queues[task_id]
            # If the task is still in running_async_tasks, it means it wasn't cancelled by disconnect
            # but the SSE stream ended (e.g., normal completion). We should remove it.
            if task_id in database.running_async_tasks and database.running_async_tasks[task_id].done():
                del database.running_async_tasks[task_id]


    return EventSourceResponse(event_generator())

@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Request cancellation of a running matching task."""
    if task_id not in database.tasks_db:
        raise HTTPException(status_code=404, detail="Task not found in database.")
    
    task_status_entry = database.tasks_db[task_id]
    if task_status_entry["status"] not in ["pending", "processing"]:
        raise HTTPException(status_code=400, detail=f"Task {task_id} is already {task_status_entry['status']} and cannot be cancelled.")

    if task_id in database.running_async_tasks:
        background_task = database.running_async_tasks[task_id]
        if not background_task.done():
            background_task.cancel()
            logger.info(f"Cancellation requested for background task {task_id}.")
            return {"message": f"Cancellation requested for task {task_id}."}
        else:
            # Task is done but still in running_async_tasks (should be cleaned up quickly)
            logger.warning(f"Task {task_id} was already done but still in running_async_tasks. Removing.")
            del database.running_async_tasks[task_id]
            raise HTTPException(status_code=400, detail=f"Task {task_id} is already complete or failed.")
    else:
        logger.warning(f"Task {task_id} not found in running_async_tasks. It might have finished or failed already.")
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found as currently running.")

@router.get("/tasks/{task_id}/download")
async def download_compliance_report(task_id: str):
    """Generates and streams a PDF compliance report for a completed task."""
    result_file_path = config.RESULTS_DIR / f"{task_id}.json"
    if not result_file_path.exists():
        raise HTTPException(status_code=404, detail="Task results not found. The task may still be running or has failed.")

    try:
        with open(result_file_path, 'r', encoding='utf-8') as f:
            task_data = json.load(f)

        if task_data.get("status") != "completed":
            raise HTTPException(status_code=400, detail="Task is not yet complete.")
        
        # Prepare data for PDF generator
        pdf_task_data = {
            "report_filename": task_data.get("report_filename", "N/A"),
            "created_at": task_data.get("completed_at", datetime.now().isoformat()),
            "output_report_title": task_data.get("output_report_title"),
            "result": {
                "rows": task_data.get("results", []),
                "summary": task_data.get("summary", {})
            }
        }

        # Generate PDF in memory (use output_report_title if present, otherwise generator will fall back)
        pdf_buffer = generate_compliance_pdf(pdf_task_data)

        filename = f"compliance_report_{task_id}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error generating PDF for task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {e}")
