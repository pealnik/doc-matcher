#!/usr/bin/env python3
"""
FastAPI backend for PDF Compliance Checker
Provides REST API for guideline management and compliance checking
"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import shutil

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import from local backend module
from pdf_compliance_checker import PDFExtractor, GuidelineRAG, ComplianceChecker

# Initialize FastAPI app
app = FastAPI(title="PDF Compliance Checker API")

# Configure CORS
# Add your production frontend URL to allow_origins when deploying
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        # Add your production frontend URL here:
        # "https://yourdomain.com",
        # "https://www.yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = Path("./uploads")
GUIDELINES_DIR = UPLOAD_DIR / "guidelines"
REPORTS_DIR = UPLOAD_DIR / "reports"
VECTORSTORE_DIR = Path("./vectorstores")

# Create directories
for directory in [GUIDELINES_DIR, REPORTS_DIR, VECTORSTORE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# In-memory storage for tasks and guidelines
tasks_db: Dict[str, Dict[str, Any]] = {}
guidelines_db: Dict[str, Dict[str, Any]] = {}

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not OPENAI_API_KEY or not GEMINI_API_KEY:
    print("Warning: API keys not found in environment")


# Pydantic models
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


# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "PDF Compliance Checker API"}


@app.post("/api/guidelines/upload", response_model=GuidelineResponse)
async def upload_guideline(file: UploadFile = File(...)):
    """Upload a guideline PDF"""

    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Generate unique ID
    guideline_id = str(uuid.uuid4())

    # Save file
    file_path = GUIDELINES_DIR / f"{guideline_id}.pdf"

    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Get file info
        file_size = file_path.stat().st_size

        # Try to get page count
        try:
            page_count = PDFExtractor.get_pdf_page_count(str(file_path))
        except Exception:
            page_count = None

        # Store metadata
        guideline_data = {
            "id": guideline_id,
            "filename": file.filename,
            "uploaded_at": datetime.now().isoformat(),
            "size": file_size,
            "pages": page_count,
            "file_path": str(file_path),
            "vectorstore_ready": False  # Will be updated when indexing completes
        }
        guidelines_db[guideline_id] = guideline_data

        # Build vectorstore in background
        asyncio.create_task(build_vectorstore_async(guideline_id, str(file_path)))

        return GuidelineResponse(**guideline_data)

    except Exception as e:
        # Clean up on error
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@app.get("/api/guidelines", response_model=List[GuidelineResponse])
async def list_guidelines():
    """List all uploaded guidelines"""
    return [GuidelineResponse(**g) for g in guidelines_db.values()]


@app.delete("/api/guidelines/{guideline_id}")
async def delete_guideline(guideline_id: str):
    """Delete a guideline"""

    if guideline_id not in guidelines_db:
        raise HTTPException(status_code=404, detail="Guideline not found")

    guideline = guidelines_db[guideline_id]

    # Delete file
    file_path = Path(guideline["file_path"])
    if file_path.exists():
        file_path.unlink()

    # Delete vectorstore
    vectorstore_path = VECTORSTORE_DIR / guideline_id
    if vectorstore_path.exists():
        shutil.rmtree(vectorstore_path)

    # Remove from database
    del guidelines_db[guideline_id]

    return {"message": "Guideline deleted successfully"}


@app.post("/api/match", response_model=TaskStatus)
async def start_match(
    background_tasks: BackgroundTasks,
    report: UploadFile = File(...),
    guideline_ids: str = Form(...)
):
    """Start a compliance matching task"""

    # Parse guideline IDs
    try:
        guideline_ids_list = json.loads(guideline_ids)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid guideline_ids format")

    # Validate guidelines exist
    for gid in guideline_ids_list:
        if gid not in guidelines_db:
            raise HTTPException(status_code=404, detail=f"Guideline {gid} not found")

    # Validate file type
    if not report.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Save report file
    report_path = REPORTS_DIR / f"{task_id}.pdf"

    try:
        with open(report_path, "wb") as buffer:
            content = await report.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save report: {str(e)}")

    # Create task
    task_data = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task created, starting processing...",
        "result": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "report_filename": report.filename,
        "report_path": str(report_path),
        "guideline_ids": guideline_ids_list
    }
    tasks_db[task_id] = task_data

    # Start background task
    background_tasks.add_task(
        process_compliance_check,
        task_id,
        str(report_path),
        guideline_ids_list
    )

    return TaskStatus(**task_data)


@app.get("/api/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get status of a matching task"""

    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks_db[task_id]
    return TaskStatus(**task)


@app.get("/api/tasks", response_model=List[TaskStatus])
async def list_tasks():
    """List all tasks"""
    return [TaskStatus(**t) for t in tasks_db.values()]


# Background task functions

async def build_vectorstore_async(guideline_id: str, pdf_path: str):
    """Build vectorstore for a guideline PDF in the background"""
    try:
        vectorstore_path = VECTORSTORE_DIR / guideline_id

        # Build vectorstore
        rag = GuidelineRAG(openai_api_key=OPENAI_API_KEY)
        rag.build_vectorstore(pdf_path, str(vectorstore_path))

        # Update guideline with vectorstore status
        if guideline_id in guidelines_db:
            guidelines_db[guideline_id]["vectorstore_ready"] = True

    except Exception as e:
        print(f"Error building vectorstore for {guideline_id}: {e}")
        if guideline_id in guidelines_db:
            guidelines_db[guideline_id]["vectorstore_ready"] = False


def update_task(task_id: str, **updates):
    """Update task in database"""
    if task_id in tasks_db:
        tasks_db[task_id].update(updates)
        tasks_db[task_id]["updated_at"] = datetime.now().isoformat()


async def process_compliance_check(task_id: str, report_path: str, guideline_ids: List[str]):
    """Process compliance check in the background"""

    try:
        update_task(task_id, status="processing", progress=5, message="Initializing...")

        # For now, we'll process with the first guideline
        # TODO: Support multiple guidelines
        guideline_id = guideline_ids[0]
        guideline = guidelines_db[guideline_id]
        guideline_path = guideline["file_path"]
        vectorstore_path = VECTORSTORE_DIR / guideline_id

        update_task(task_id, progress=10, message="Loading guideline vectorstore...")

        # Initialize RAG
        rag = GuidelineRAG(openai_api_key=OPENAI_API_KEY)

        # Load or build vectorstore
        if vectorstore_path.exists():
            rag.load_vectorstore(str(vectorstore_path))
        else:
            rag.build_vectorstore(guideline_path, str(vectorstore_path))

        update_task(task_id, progress=20, message="Initializing compliance checker...")

        # Initialize checker
        checker = ComplianceChecker(api_key=GEMINI_API_KEY)

        update_task(task_id, progress=30, message="Processing report...")

        # Get total pages
        total_pages = PDFExtractor.get_pdf_page_count(report_path)
        chunk_pages = 4
        results = []

        # Process in chunks
        chunk_num = 0
        total_chunks = (total_pages + chunk_pages - 1) // chunk_pages

        for start_page in range(1, total_pages + 1, chunk_pages):
            chunk_num += 1
            end_page = min(start_page + chunk_pages - 1, total_pages)

            # Update progress
            progress = 30 + int((chunk_num / total_chunks) * 60)
            update_task(
                task_id,
                progress=progress,
                message=f"Processing pages {start_page}-{end_page} ({chunk_num}/{total_chunks})"
            )

            # Extract report chunk
            chunk_pages_content = PDFExtractor.extract_pdf_by_pages(
                report_path, start_page, end_page
            )
            report_chunk = "\n\n".join(chunk_pages_content)

            # Retrieve relevant guideline chunks
            guideline_context = rag.retrieve_relevant_chunks(report_chunk, k=5)

            # Check compliance
            compliance_result = checker.check_compliance(
                report_chunk, guideline_context, start_page, end_page
            )

            # Store result
            result = {
                "start_page": start_page,
                "end_page": end_page,
                "compliance": compliance_result["compliance"],
                "issues": compliance_result["issues"]
            }
            results.append(result)

        # Calculate summary
        total_issues = sum(len(r["issues"]) for r in results)

        update_task(
            task_id,
            status="completed",
            progress=100,
            message=f"Completed! Found {total_issues} issues across {total_chunks} chunks",
            result={
                "chunks": results,
                "summary": {
                    "total_issues": total_issues,
                    "total_chunks": total_chunks,
                    "total_pages": total_pages
                }
            }
        )

    except Exception as e:
        update_task(
            task_id,
            status="failed",
            message=f"Error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
