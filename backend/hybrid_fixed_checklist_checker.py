#!/usr/bin/env python3
"""
Hybrid Fixed Checklist Compliance Checker
"""
import json
import logging
import os
import sys
from typing import List, Dict, Any, Optional, Callable, Awaitable
from pathlib import Path
from datetime import datetime
import asyncio

# PDF processing
# This is a local import, so it needs to be relative
from pdf_compliance_checker import PDFExtractor

# RAG components
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

# LLM
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HybridFixedChecklistChecker:
    """
    Deterministic compliance checker using:
    - Fixed 42-requirement checklist (from requirements_database.json)
    - RAG retrieval per requirement (not per report chunk)
    - Full document vectorstore for targeted context extraction
    """

    def __init__(
        self,
        requirements_db_path: str,
        openai_api_key: str,
        model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small"
    ):
        """
        Initialize the hybrid checker.

        Args:
            requirements_db_path: Path to requirements_database.json
            openai_api_key: OpenAI API key
            model: LLM model to use for compliance checking
            embedding_model: Embedding model for RAG
        """
        # Load fixed requirements database
        with open(requirements_db_path, 'r', encoding='utf-8') as f:
            self.requirements_db = json.load(f)

        self.requirements = self.requirements_db["requirements"]
        self.total_requirements = len(self.requirements)

        logger.info(f"✓ Loaded {self.total_requirements} requirements from database")
        logger.info(f"  Version: {self.requirements_db['version']}")
        logger.info(f"  Checklist: {self.requirements_db['checklist_name']}")

        # Initialize OpenAI client
        self.client = OpenAI(api_key=openai_api_key)
        self.model = model

        # Initialize embeddings for RAG
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=openai_api_key
        )

        # Text splitter for report chunks
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )

        logger.info(f"✓ Initialized with model: {model}, embeddings: {embedding_model}")

    async def process_document(
        self,
        pdf_path: str,
        task_id: str,
        queue: asyncio.Queue,
        retrieval_k: int = 10,
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process a Ship Recycling Plan document against all requirements.
        This is the main entry point for compliance checking.

        Args:
            pdf_path: Path to the SRP document PDF
            task_id: The ID of the current task for progress reporting.
            queue: The asyncio Queue for sending progress updates.
            retrieval_k: Number of chunks to retrieve per requirement (default: 10)

        Returns:
            A tuple containing the list of results and a final summary dict.
        """
        logger.info("="*80)
        logger.info(f"Processing document: {pdf_path}")
        logger.info("="*80)

        # Step 1: Build report vectorstore (one-time per document)
        await queue.put({"task_id": task_id, "status": "processing", "progress": 5, "message": "Indexing report..."})
        report_vectorstore, total_pages = await asyncio.to_thread(
            self._build_report_vectorstore, pdf_path, task_id, queue
        )
        await queue.put({"task_id": task_id, "status": "processing", "progress": 20, "message": f"Report indexed ({total_pages} pages). Starting analysis..."})


        # Step 2: Check each requirement using targeted RAG retrieval
        logger.info(f"\n[Step 2/3] Checking {self.total_requirements} requirements...")
        results = []

        for i, requirement in enumerate(self.requirements, start=1):
            logger.info(f"\n--- Checking {requirement['id']} ({i}/{self.total_requirements}) ---")
            logger.info(f"Category: {requirement['category']}, Severity: {requirement['severity']}")

            try:
                # Retrieve relevant context for THIS requirement
                relevant_chunks = await asyncio.to_thread(
                    self._retrieve_relevant_chunks,
                    requirement=requirement,
                    vectorstore=report_vectorstore,
                    k=retrieval_k
                )

                # Check requirement with targeted context
                result = await asyncio.to_thread(
                    self._check_requirement_with_context,
                    requirement=requirement,
                    relevant_chunks=relevant_chunks
                )

                results.append(result)
                logger.info(f"✓ Status: {result['status']}")
                
                # Send progress update to the queue
                partial_summary = self._calculate_summary(results)
                progress = 20 + int((i / self.total_requirements) * 75)  # Progress from 20% to 95%
                await queue.put({
                    "task_id": task_id,
                    "status": "processing",
                    "progress": progress,
                    "message": f"Checked requirement {i}/{self.total_requirements}: {result.get('requirement_id')}",
                    "result": {"latest_row": result, "summary": partial_summary}
                })

            except Exception as e:
                logger.error(f"✗ Failed to check {requirement['id']}: {e}")
                # Add error result
                error_result = {
                    "requirement_id": requirement["id"],
                    "requirement_text": requirement["requirement"],
                    "regulation_source": requirement["regulation_source"],
                    "category": requirement["category"],
                    "status": "Error",
                    "evidence": f"Error during checking: {str(e)}",
                    "evidence_pages": [],
                    "remarks": "An error occurred during compliance checking"
                }
                results.append(error_result)
                await queue.put({
                    "task_id": task_id,
                    "status": "processing",
                    "progress": progress, # Keep progress where it was
                    "message": f"Error checking requirement {i}/{self.total_requirements}",
                    "result": {"latest_row": error_result, "summary": self._calculate_summary(results)}
                })


        # Step 3: Generate summary
        logger.info(f"\n[Step 3/3] Generating summary...")
        summary = self._calculate_summary(results)

        logger.info("="*80)
        logger.info("COMPLIANCE CHECK COMPLETE")
        logger.info("="*80)
        logger.info(f"Total Requirements Checked: {self.total_requirements}")
        logger.info(f"Compliant: {summary['compliant']}")
        logger.info(f"Non-Compliant: {summary['non_compliant']}")
        logger.info(f"Partially Compliant: {summary['partially_compliant']}")
        logger.info(f"Compliance Rate: {summary['compliance_rate']:.1f}%")
        logger.info("="*80)

        return results, summary

    def _build_report_vectorstore(self, pdf_path: str, task_id: str, queue: asyncio.Queue) -> tuple[FAISS, int]:
        """
        Build FAISS vectorstore from full report document, with progress reporting.
        This method is run in a thread, so it uses queue.put_nowait().
        """
        def _progress_callback(current, total):
            progress = 5 + int((current / total) * 10) # Extraction is from 5% to 15%
            queue.put_nowait({
                "task_id": task_id,
                "status": "processing",
                "progress": progress,
                "message": f"Indexing: Extracting page {current}/{total}"
            })

        logger.info("  Extracting pages from PDF...")
        pages_content = PDFExtractor.extract_pdf_by_pages(
            pdf_path, progress_callback=_progress_callback
        )
        total_pages = len(pages_content)
        logger.info(f"  Extracted {total_pages} pages from PDF")

        queue.put_nowait({"task_id": task_id, "status": "processing", "progress": 15, "message": "Chunking document..."})
        documents = []
        for page_num, page_text in enumerate(pages_content, start=1):
            chunks = self.text_splitter.split_text(page_text)
            for chunk_idx, chunk in enumerate(chunks):
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "page": page_num,
                            "chunk_index": chunk_idx,
                            "source": pdf_path
                        }
                    )
                )
        logger.info(f"  Created {len(documents)} chunks from {total_pages} pages")

        queue.put_nowait({"task_id": task_id, "status": "processing", "progress": 18, "message": "Creating vector embeddings..."})
        vectorstore = FAISS.from_documents(documents, self.embeddings)
        logger.info(f"  ✓ FAISS vectorstore built (Flat index for determinism)")
        
        return vectorstore, total_pages

    def _retrieve_relevant_chunks(
        self,
        requirement: Dict[str, Any],
        vectorstore: FAISS,
        k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a specific requirement.
        """
        query_parts = [
            requirement["requirement"],
            "Keywords: " + ", ".join(requirement["search_keywords"])
        ]
        query = "\n".join(query_parts)
        logger.info(f"  Retrieving top-{k} chunks for: {requirement['id']}")
        docs = vectorstore.max_marginal_relevance_search(query, k=k, lambda_mult=0.5)
        chunks = []
        seen_pages = set()
        for doc in docs:
            page = doc.metadata.get("page", "?")
            chunks.append({"content": doc.page_content, "page": page})
            seen_pages.add(page)
        logger.info(f"  ✓ Retrieved {len(chunks)} chunks from pages: {sorted(seen_pages)}")
        return chunks

    def _check_requirement_with_context(
        self,
        requirement: Dict[str, Any],
        relevant_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check a single requirement with targeted context.
        """
        context_parts = []
        for i, chunk in enumerate(relevant_chunks, 1):
            context_parts.append(
                f"[Excerpt {i} - Page {chunk['page']}]\n{chunk['content']}"
            )
        context = "\n\n---\n\n".join(context_parts)

        prompt = f"""
You are checking ONE specific requirement for a Ship Recycling Plan.

**REQUIREMENT ID:** {requirement['id']} (out of {self.total_requirements} total requirements)

**REQUIREMENT:**
{requirement['requirement']}

**EXPECTED FIELDS/INFORMATION:**
{', '.join(requirement['expected_fields'])}

**REGULATION SOURCE:**
{requirement['regulation_source']}

**CHECK TYPE:** {requirement['check_type']}
**SEVERITY:** {requirement['severity']}

**RELEVANT EXCERPTS FROM REPORT:**
{context}

**TASK:**
Based on the excerpts above, determine if this requirement is satisfied in the Ship Recycling Plan.

**RESPONSE FORMAT (JSON only):**
{{
  "status": "Compliant" | "Non-Compliant" | "Partially Compliant",
  "evidence": "<exact quote from excerpts showing compliance/non-compliance, or 'Not found'>",
  "evidence_pages": [<page numbers where evidence found>],
  "remarks": "<brief explanation of status (max 2 sentences)>"
}}

**RULES:**
1. "Compliant" = All expected fields/information present and adequate
2. "Non-Compliant" = Required information missing or inadequate
3. "Partially Compliant" = Some but not all expected fields present, or information incomplete
4. If excerpts don't contain relevant information, state "Not found" in evidence and mark Non-Compliant
5. Evidence must quote exact text from excerpts or state "Not found"
6. Remarks must be concise, specific, and explain the status

Respond with ONLY the JSON object, no other text.
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a compliance auditor for ship recycling plans. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0,
            seed=42,
            max_tokens=1000
        )
        result = json.loads(response.choices[0].message.content)

        result["requirement_id"] = requirement["id"]
        result["requirement_text"] = requirement["requirement"]
        result["regulation_source"] = requirement["regulation_source"]
        result["category"] = requirement["category"]
        result["severity"] = requirement["severity"]
        result["check_type"] = requirement["check_type"]
        self._validate_result_schema(result)
        # Normalize and enrich evidence pages and remarks with local information when possible.
        # If evidence was found, try to determine which pages contain the quoted evidence.
        try:
            evidence_text = (result.get("evidence") or "").strip()
            pages = set()

            # Prefer explicit pages returned by the model (normalize to int when possible)
            for p in result.get("evidence_pages", []):
                try:
                    pages.add(int(p))
                except Exception:
                    # ignore non-integer values
                    continue

            # If model didn't supply pages but provided evidence text, try to match it in the retrieved chunks
            if not pages and evidence_text and evidence_text.lower() != "not found":
                for chunk in relevant_chunks:
                    chunk_content = chunk.get("content", "")
                    if not chunk_content:
                        continue
                    # Try exact match first
                    if evidence_text in chunk_content:
                        pages.add(int(chunk.get("page", -1)))
                    else:
                        # Try a fuzzy-ish match using first/last parts of the evidence
                        snippet = evidence_text[:120]
                        if snippet and snippet in chunk_content:
                            pages.add(int(chunk.get("page", -1)))

            # Update result evidence_pages with any discovered pages (sorted)
            if pages:
                result["evidence_pages"] = sorted(pages)

                # Append page information to remarks if evidence was found
                remarks = result.get("remarks", "")
                page_list_str = ", ".join(str(p) for p in sorted(pages))
                # Only append if not already mentioned
                if f"page" not in remarks.lower():
                    if remarks and not remarks.endswith("."):
                        remarks = remarks + "."
                    remarks = f"{remarks} Found on page(s): {page_list_str}."
                    result["remarks"] = remarks
        except Exception as e:
            # Don't fail the whole check on enrichment errors; log and continue
            logger.debug(f"Failed to enrich result with page info: {e}")

        return result

    def _validate_result_schema(self, result: Dict[str, Any]) -> None:
        """Validate that result has required fields and valid values."""
        required_fields = ["status", "evidence", "evidence_pages", "remarks"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        valid_statuses = ["Compliant", "Non-Compliant", "Partially Compliant", "Error"]
        if result["status"] not in valid_statuses:
            raise ValueError(f"Invalid status: {result['status']}")
        if not isinstance(result["evidence_pages"], list):
            raise ValueError("evidence_pages must be a list")

    def _calculate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate compliance statistics from results."""
        summary = {
            "total": len(results),
            "compliant": 0,
            "non_compliant": 0,
            "partially_compliant": 0,
            "error": 0
        }
        for result in results:
            status = result.get("status")
            if status == "Compliant":
                summary["compliant"] += 1
            elif status == "Non-Compliant":
                summary["non_compliant"] += 1
            elif status == "Partially Compliant":
                summary["partially_compliant"] += 1
            elif status == "Error":
                summary["error"] += 1
        summary["compliance_rate"] = (summary["compliant"] / summary["total"] * 100) if summary["total"] > 0 else 0
        return summary
