import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import config, database
from hybrid_fixed_checklist_checker import HybridFixedChecklistChecker
from pdf_compliance_checker import PDFExtractor # Still needed by HybridFixedChecklistChecker
from pdf_generator import generate_compliance_pdf

# Module logger
logger = logging.getLogger(__name__)

def update_task(task_id: str, **updates):
    """Update task in the in-memory database."""
    if task_id in database.tasks_db:
        database.tasks_db[task_id].update(updates)
        database.tasks_db[task_id]["updated_at"] = datetime.now().isoformat()
        logger.info(f"Task {task_id} updated: {updates}")

def load_existing_guidelines():
    """
    Load existing JSON checklist files from disk on startup.
    These are now the "guidelines" and are immediately ready if valid.
    """
    logger.info("Loading existing checklists from disk...")

    # Always use the configured checklist directory (no fallback to backend/data)
    search_dir = config.CHECKLISTS_DIR

    # Ensure the configured directory exists. If it's missing, create it and return
    # (no fallback to backend/data/guidelines — user requested strict repo-root behavior).
    if not search_dir.exists():
        search_dir.mkdir(parents=True, exist_ok=True)
        logger.warning(f"  Created missing CHECKLISTS_DIR: {search_dir}")
        # Directory was just created and will be empty, nothing to load now
        return

    loaded_count = 0
    logger.info(f"  Scanning for checklist JSON files at: {search_dir}")
    for json_file in search_dir.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                checklist_data = json.load(f)

                guideline_id = json_file.stem
            # Assuming the JSON has at least a "checklist_name" and "requirements"
            if "checklist_name" not in checklist_data or "requirements" not in checklist_data:
                logger.warning(f"  ✗ Skipping invalid checklist file (missing name or requirements): {json_file.name}")
                continue

            # Store basic metadata
            database.guidelines_db[guideline_id] = {
                "id": guideline_id,
                "filename": json_file.name,
                "uploaded_at": datetime.fromtimestamp(json_file.stat().st_mtime).isoformat(),
                "size": json_file.stat().st_size,
                "pages": len(checklist_data.get("requirements", [])), # Using num requirements as 'pages'
                "file_path": str(json_file),
                "vectorstore_ready": True, # Always true for loaded JSON checklists
                "description": checklist_data.get("checklist_name", "N/A"),
                # Optional custom output report title (if present in checklist JSON)
                "output_report_title": checklist_data.get("output_report_title"),
                "requirements": checklist_data["requirements"] # Store actual requirements
            }
            loaded_count += 1
            logger.info(f"  ✓ Loaded checklist: {checklist_data['checklist_name']} ({len(checklist_data['requirements'])} requirements)")

        except json.JSONDecodeError as e:
            logger.error(f"  ✗ Failed to parse JSON checklist {json_file.name}: {e}")
        except Exception as e:
            logger.error(f"  ✗ Error loading checklist {json_file.name}: {e}")

    logger.info(f"✓ Checklist loading complete. Found {loaded_count} valid checklists.")

async def process_compliance_check(task_id: str, report_path: str | None, guideline_ids: List[str]):
    """
    Process compliance check using HybridFixedChecklistChecker and push updates to the queue.
    """
    queue = database.task_queues.get(task_id)
    if not queue:
        logger.error(f"No queue found for task {task_id}. Aborting.")
        return

    temp_requirements_path = config.RESULTS_DIR / f"{task_id}_requirements.json" # Define early for finally block
    
    try:
        # First message from the background task: File received and processing is about to begin.
        await queue.put({"task_id": task_id, "status": "processing", "progress": 2, "message": "File received. Initializing processing..."})

        # Consolidate requirements from selected checklists
        all_requirements = []
        for gid in guideline_ids:
            guideline = database.guidelines_db.get(gid)
            if guideline and "requirements" in guideline:
                all_requirements.extend(guideline["requirements"])
            else:
                raise ValueError(f"Guideline {gid} not found or has no requirements.")

        # Temporarily save consolidated requirements to a file for HybridFixedChecklistChecker
        
        temp_checklist_data = {
            "checklist_name": "Consolidated Checklist",
            "version": "1.0",
            "requirements": all_requirements
        }
        with open(temp_requirements_path, 'w', encoding='utf-8') as f:
            json.dump(temp_checklist_data, f, indent=2, ensure_ascii=False)

        # If no PDF/report was provided, do a guideline-only flow:
        results_list = []

        if not report_path:
            # Guideline-only processing: iterate requirements and mark as not-checked
            total = len(all_requirements)
            await queue.put({"task_id": task_id, "status": "processing", "progress": 5, "message": "Processing selected checklist(s) (no report supplied)..."})
            for i, requirement in enumerate(all_requirements, start=1):
                result = {
                    "requirement_id": requirement.get("id"),
                    "requirement_text": requirement.get("requirement"),
                    "regulation_source": requirement.get("regulation_source", ""),
                    "category": requirement.get("category", ""),
                    "status": "Not Checked",
                    "evidence": "No report provided",
                    "evidence_pages": [],
                    "remarks": "No document supplied; requirement listed only."
                }
                results_list.append(result)

                # Send a progress update for each requirement
                progress = 5 + int((i / total) * 90) if total > 0 else 100
                await queue.put({
                    "task_id": task_id,
                    "status": "processing",
                    "progress": progress,
                    "message": f"Listed requirement {i}/{total}: {result.get('requirement_id')}",
                    "result": {"latest_row": result, "summary": {}}
                })

            # Build a simple summary for guideline-only run
            final_results = results_list
            final_summary = {
                "total": len(final_results),
                "compliant": 0,
                "non_compliant": 0,
                "partially_compliant": 0,
                "error": 0,
                "compliance_rate": 0.0
            }

        else:
            # Run full checker when report path is present
            # Initialize the checker
            checker = HybridFixedChecklistChecker(
                requirements_db_path=str(temp_requirements_path), # Pass the temporary file path
                openai_api_key=config.OPENAI_API_KEY,
            )

            # Run the checker's main method, passing the queue for progress updates
            final_results, final_summary = await checker.process_document(
                pdf_path=report_path,
                task_id=task_id,
                queue=queue
            )

        # Persist final results to a JSON file for the download endpoint
        result_file_path = config.RESULTS_DIR / f"{task_id}.json"
        task_data = database.tasks_db.get(task_id, {})
        output_json = {
            "task_id": task_id,
            "report_filename": task_data.get("report_filename"),
            "guideline_ids": guideline_ids,
            # If a single guideline was selected and it defines an output_report_title, persist it here
            "output_report_title": (
                database.guidelines_db.get(guideline_ids[0], {}).get("output_report_title")
                if len(guideline_ids) == 1
                else "Consolidated Compliance Report"
            ),
            "completed_at": datetime.now().isoformat(),
            "status": "completed",
            "results": final_results,
            "summary": final_summary,
        }
        with open(result_file_path, 'w', encoding='utf-8') as f:
            json.dump(output_json, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved final results to: {result_file_path}")

        await queue.put({
            "task_id": task_id, # Added task_id here
            "status": "completed",
            "progress": 100,
            "message": "Compliance check complete.",
            "result": {"rows": final_results, "summary": final_summary}
        })

    except asyncio.CancelledError:
        logger.warning(f"Task {task_id} was cancelled due to client disconnect.")
        # Update the task status in the database
        update_task(task_id, status="failed", message="Task cancelled by user.")
        # Send a final update to the queue for the client
        if queue:
            await queue.put({"task_id": task_id, "status": "failed", "message": "Task cancelled by user."})
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        await queue.put({"task_id": task_id, "status": "failed", "message": str(e)}) # Added task_id here
        update_task(task_id, status="failed", message=str(e)) # Also update main db
    finally:
        logger.info(f"Cleaning up resources for task {task_id}.")
        # Signal end of stream
        if queue:
            await queue.put(None)
        # Clean up temporary files
        if temp_requirements_path.exists():
            temp_requirements_path.unlink()
        # Remove from running_async_tasks and task_queues
        if task_id in database.running_async_tasks:
            del database.running_async_tasks[task_id]
        if task_id in database.task_queues:
            del database.task_queues[task_id]