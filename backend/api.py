#!/usr/bin/env python3
"""
FastAPI backend for PDF Compliance Checker
Provides REST API for guideline management and compliance checking
"""

import os
import uuid
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import shutil
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Import from local backend module
from pdf_compliance_checker import PDFExtractor, GuidelineRAG, ComplianceChecker
from pdf_generator import generate_compliance_pdf

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="PDF Compliance Checker API")

# Configure CORS from environment variable
# Set ALLOWED_ORIGINS in .env as comma-separated URLs
# For production with nginx proxy, you can set to ["*"] or skip CORS since it's same-origin
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")] if allowed_origins_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = Path("./uploads")
GUIDELINES_DIR = UPLOAD_DIR / "guidelines"
REPORTS_DIR = UPLOAD_DIR / "reports"
VECTORSTORE_DIR = Path("./vectorstores")
RESULTS_DIR = Path("./results")

# Create directories
for directory in [GUIDELINES_DIR, REPORTS_DIR, VECTORSTORE_DIR, RESULTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# In-memory storage for tasks and guidelines
tasks_db: Dict[str, Dict[str, Any]] = {}
guidelines_db: Dict[str, Dict[str, Any]] = {}

# Thread pool executor for blocking I/O operations
executor: Optional[ThreadPoolExecutor] = None

def load_existing_guidelines():
    """Load existing guideline PDFs from disk on startup and clean up incomplete ones"""
    logger.info("Loading existing guidelines from disk...")

    if not GUIDELINES_DIR.exists():
        return

    deleted_count = 0
    loaded_count = 0

    for pdf_file in GUIDELINES_DIR.glob("*.pdf"):
        guideline_id = pdf_file.stem  # filename without extension

        if guideline_id in guidelines_db:
            continue  # Already loaded

        try:
            # Check if vectorstore exists
            vectorstore_path = VECTORSTORE_DIR / guideline_id
            vectorstore_ready = vectorstore_path.exists()

            if not vectorstore_ready:
                # Delete incomplete guideline (no vectorstore)
                logger.warning(f"  Deleting incomplete guideline: {pdf_file.name} (no vectorstore)")
                pdf_file.unlink()
                deleted_count += 1

                # Also delete any partial vectorstore if it exists
                if vectorstore_path.exists():
                    logger.warning(f"    Deleting incomplete vectorstore: {vectorstore_path}")
                    shutil.rmtree(vectorstore_path)

                continue

            # Get file info
            file_size = pdf_file.stat().st_size

            # Get page count
            try:
                page_count = PDFExtractor.get_pdf_page_count(str(pdf_file))
            except Exception:
                page_count = None

            # Store metadata (only for complete guidelines)
            guideline_data = {
                "id": guideline_id,
                "filename": pdf_file.name,
                "uploaded_at": datetime.fromtimestamp(pdf_file.stat().st_mtime).isoformat(),
                "size": file_size,
                "pages": page_count,
                "file_path": str(pdf_file),
                "vectorstore_ready": True
            }
            guidelines_db[guideline_id] = guideline_data
            loaded_count += 1
            logger.info(f"  ✓ Loaded guideline: {pdf_file.name}")

        except Exception as e:
            logger.error(f"  Failed to process guideline {pdf_file.name}: {e}")

    if deleted_count > 0:
        logger.info(f"✗ Deleted {deleted_count} incomplete guideline(s)")
    logger.info(f"✓ Loaded {loaded_count} complete guideline(s)")

# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize thread pool and load guidelines
    global executor
    executor = ThreadPoolExecutor(max_workers=4)
    logger.info("✓ Created thread pool executor")
    load_existing_guidelines()
    yield
    # Shutdown: cleanup executor
    if executor:
        executor.shutdown(wait=True)
        logger.info("✓ Shut down thread pool executor")

# Update app with lifespan
app.router.lifespan_context = lifespan

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not OPENAI_API_KEY or not GEMINI_API_KEY:
    print("Warning: API keys not found in environment")
else:
    print(f"✓ OpenAI API key loaded (ends with: ...{OPENAI_API_KEY[-4:]})")
    print(f"✓ Gemini API key loaded (ends with: ...{GEMINI_API_KEY[-4:]})")

# Graceful shutdown handler
def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n⚠️  Shutting down gracefully... (press Ctrl+C again to force quit)")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)


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
    report: UploadFile = File(...),
    guideline_ids: str = Form(...)
):
    """Start a compliance matching task - returns immediately"""

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

    # Create task with initial empty result
    task_data = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task created, starting processing...",
        "result": {
            "rows": [],
            "summary": {
                "total_rows": 0,
                "total_compliant": 0,
                "total_non_compliant": 0,
                "total_partial": 0,
                "total_chunks": 0,
                "total_pages": 0
            }
        },
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "report_filename": report.filename,
        "report_path": str(report_path),
        "guideline_ids": guideline_ids_list
    }
    tasks_db[task_id] = task_data

    # Run in thread pool to avoid blocking the event loop
    # This allows polling requests to be handled while processing continues
    if executor is None:
        raise RuntimeError("Executor not initialized")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor,
        process_compliance_check,
        task_id,
        str(report_path),
        guideline_ids_list
    )

    logger.info(f"✓ Created task {task_id}, returning immediately, processing in background thread")
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


@app.get("/api/tasks/{task_id}/download")
async def download_compliance_report(task_id: str):
    """Download compliance report as PDF"""

    # Check if result file exists
    result_file_path = RESULTS_DIR / f"{task_id}.json"
    if not result_file_path.exists():
        raise HTTPException(status_code=404, detail="Task not found or results not available")

    try:
        # Load results from JSON file
        with open(result_file_path, 'r', encoding='utf-8') as f:
            task_data = json.load(f)

        if task_data.get("status") != "completed":
            raise HTTPException(status_code=400, detail="Task not completed yet")

        if not task_data.get("compliance_check") or not task_data["compliance_check"].get("rows"):
            raise HTTPException(status_code=400, detail="No results available for this task")

        # Transform data to match PDF generator's expected structure
        # PDF generator expects: task_data["result"] and task_data["created_at"]
        # JSON file has: task_data["compliance_check"] and task_data["generated_at"]
        pdf_task_data = {
            "report_filename": task_data.get("report_filename", "N/A"),
            "created_at": task_data.get("generated_at", task_data.get("completed_at", datetime.now().isoformat())),
            "result": task_data["compliance_check"]
        }

        # Generate PDF using the transformed data
        pdf_buffer = generate_compliance_pdf(pdf_task_data)

        # Return as downloadable file
        filename = f"compliance_report_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load task results")
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


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


def process_compliance_check(task_id: str, report_path: str, guideline_ids: List[str]):
    """Process compliance check in the background (runs in thread pool)"""

    try:
        # Check if task was cancelled
        if task_id not in tasks_db:
            logger.warning(f"Task {task_id} not found, cancelling processing")
            return
        # Initialize with empty result so client shows table immediately
        update_task(
            task_id,
            status="processing",
            progress=5,
            message="Initializing...",
            result={
                "rows": [],
                "summary": {
                    "total_rows": 0,
                    "total_compliant": 0,
                    "total_non_compliant": 0,
                    "total_partial": 0,
                    "total_chunks": 0,
                    "total_pages": 0
                }
            }
        )

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

        # Get total pages
        total_pages = PDFExtractor.get_pdf_page_count(report_path)

        update_task(
            task_id,
            progress=30,
            message="Processing report...",
            result={
                "rows": [],
                "summary": {
                    "total_rows": 0,
                    "total_compliant": 0,
                    "total_non_compliant": 0,
                    "total_partial": 0,
                    "total_chunks": 0,
                    "total_pages": total_pages
                }
            }
        )
        chunk_pages = 4
        results = []

        # Initialize result JSON file
        result_file_path = RESULTS_DIR / f"{task_id}.json"
        initial_json = {
            "task_id": task_id,
            "report_filename": tasks_db[task_id].get("report_filename"),
            "guideline_id": guideline_id,
            "guideline_filename": guideline.get("filename"),
            "generated_at": datetime.now().isoformat(),
            "status": "processing",
            "compliance_check": {
                "rows": [],
                "summary": {
                    "total_rows": 0,
                    "total_compliant": 0,
                    "total_non_compliant": 0,
                    "total_partial": 0,
                    "total_chunks": 0,
                    "total_pages": total_pages
                }
            }
        }
        with open(result_file_path, 'w', encoding='utf-8') as f:
            json.dump(initial_json, f, indent=2, ensure_ascii=False)

        # Process in chunks
        chunk_num = 0
        total_chunks = (total_pages + chunk_pages - 1) // chunk_pages

        for start_page in range(1, total_pages + 1, chunk_pages):
            # Check if task still exists (in case of shutdown)
            if task_id not in tasks_db:
                logger.warning(f"Task {task_id} cancelled, stopping processing")
                return

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

            # Get rows from result
            chunk_rows = compliance_result.get("rows", [])

            # Add chunk metadata to each row
            for row in chunk_rows:
                row["chunk_start_page"] = start_page
                row["chunk_end_page"] = end_page

            # Append rows to results
            results.extend(chunk_rows)

            # Update summary incrementally
            total_non_compliant = sum(1 for r in results if r.get("status") == "Non-Compliant")
            total_partial = sum(1 for r in results if r.get("status") == "Partially Compliant")
            total_compliant = sum(1 for r in results if r.get("status") == "Compliant")

            # Update task with partial results for client
            partial_result = {
                "rows": results,
                "summary": {
                    "total_rows": len(results),
                    "total_compliant": total_compliant,
                    "total_non_compliant": total_non_compliant,
                    "total_partial": total_partial,
                    "total_chunks": chunk_num,
                    "total_pages": total_pages
                }
            }
            update_task(task_id, result=partial_result)
            logger.info(f"  Updated task with {len(results)} rows (chunk {chunk_num}/{total_chunks})")

            # Update JSON file incrementally
            try:
                output_json = {
                    "task_id": task_id,
                    "report_filename": tasks_db[task_id].get("report_filename"),
                    "guideline_id": guideline_id,
                    "guideline_filename": guideline.get("filename"),
                    "generated_at": datetime.now().isoformat(),
                    "status": "processing",
                    "compliance_check": partial_result
                }
                with open(result_file_path, 'w', encoding='utf-8') as f:
                    json.dump(output_json, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to update JSON file: {e}")

        # Final summary calculation
        total_non_compliant = sum(1 for r in results if r.get("status") == "Non-Compliant")
        total_partial = sum(1 for r in results if r.get("status") == "Partially Compliant")
        total_compliant = sum(1 for r in results if r.get("status") == "Compliant")

        # Prepare final result data
        result_data = {
            "rows": results,
            "summary": {
                "total_rows": len(results),
                "total_compliant": total_compliant,
                "total_non_compliant": total_non_compliant,
                "total_partial": total_partial,
                "total_chunks": total_chunks,
                "total_pages": total_pages
            }
        }

        # Update JSON file with final completed status
        try:
            output_json = {
                "task_id": task_id,
                "report_filename": tasks_db[task_id].get("report_filename"),
                "guideline_id": guideline_id,
                "guideline_filename": guideline.get("filename"),
                "generated_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "status": "completed",
                "compliance_check": result_data
            }
            with open(result_file_path, 'w', encoding='utf-8') as f:
                json.dump(output_json, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Saved final compliance results to: {result_file_path}")
        except Exception as e:
            logger.error(f"Failed to save final results to JSON: {e}")

        update_task(
            task_id,
            status="completed",
            progress=100,
            message=f"Completed! Found {total_non_compliant} non-compliant items across {total_chunks} chunks",
            result=result_data
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
