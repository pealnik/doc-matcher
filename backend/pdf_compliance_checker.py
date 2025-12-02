#!/usr/bin/env python3
"""
PDF Compliance Checker using RAG and Gemini API

This script compares a large report PDF against a guideline PDF to check compliance.
Uses RAG (Retrieval-Augmented Generation) to find relevant guideline sections and
Gemini to perform detailed compliance analysis.

Usage:
    python pdf_compliance_checker.py --guideline guideline.pdf --report report.pdf --api_key YOUR_GEMINI_KEY
"""

import argparse
import json
import logging
import os
import sys
from typing import List, Dict, Any, Tuple
from pathlib import Path

# PDF processing
import pdfplumber
import pandas as pd

# RAG components
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

# LLM
import google.generativeai as genai

# Environment variables
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('compliance_checker.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PDFExtractor:
    """Handles PDF text and table extraction using pdfplumber."""

    @staticmethod
    def extract_page_content(page) -> str:
        """
        Extract text and tables from a single PDF page.

        Args:
            page: pdfplumber page object

        Returns:
            Markdown-formatted string with page content
        """
        content = []
        page_num = page.page_number

        # Extract text
        text = page.extract_text()
        if text:
            content.append(f"## Page {page_num}\n")
            content.append(text.strip())

        # Extract tables and convert to markdown
        tables = page.extract_tables()
        if tables:
            for idx, table in enumerate(tables, 1):
                try:
                    # Convert table to DataFrame for better formatting
                    df = pd.DataFrame(table[1:], columns=table[0] if table else None)
                    # Clean up None values
                    df = df.fillna('')
                    table_md = df.to_markdown(index=False)
                    content.append(f"\n### Table {idx} (Page {page_num})\n")
                    content.append(table_md)
                except Exception as e:
                    logger.warning(f"Failed to convert table {idx} on page {page_num}: {e}")
                    # Fallback: simple text representation
                    content.append(f"\n### Table {idx} (Page {page_num})\n")
                    for row in table:
                        content.append(" | ".join(str(cell) if cell else '' for cell in row))

        return "\n".join(content)

    @staticmethod
    def extract_pdf_by_pages(pdf_path: str, start_page: int = 1, end_page: int = None) -> List[str]:
        """
        Extract content from PDF pages in a memory-efficient way.

        Args:
            pdf_path: Path to PDF file
            start_page: Starting page number (1-indexed)
            end_page: Ending page number (1-indexed), None for all pages

        Returns:
            List of page contents as markdown strings
        """
        pages_content = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                end = end_page if end_page else total_pages

                for page_num in range(start_page - 1, min(end, total_pages)):
                    try:
                        page = pdf.pages[page_num]
                        content = PDFExtractor.extract_page_content(page)
                        pages_content.append(content)
                    except Exception as e:
                        logger.error(f"Error extracting page {page_num + 1}: {e}")
                        pages_content.append(f"## Page {page_num + 1}\n[Error extracting content]")

        except Exception as e:
            logger.error(f"Error opening PDF {pdf_path}: {e}")
            raise

        return pages_content

    @staticmethod
    def get_pdf_page_count(pdf_path: str) -> int:
        """Get total number of pages in PDF."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logger.error(f"Error getting page count for {pdf_path}: {e}")
            raise


class GuidelineRAG:
    """Handles RAG setup for guideline PDF using FAISS and OpenAI embeddings."""

    def __init__(self, openai_api_key: str, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize RAG components.

        Args:
            openai_api_key: OpenAI API key for embeddings
            chunk_size: Size of text chunks for embedding
            chunk_overlap: Overlap between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.vectorstore = None

        # Initialize embeddings model (OpenAI - cloud-based, no local processing)
        logger.info("Initializing OpenAI embeddings (text-embedding-3-small)...")
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=openai_api_key
        )

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def build_vectorstore(self, guideline_pdf_path: str, save_path: str = "guideline_vectorstore"):
        """
        Build FAISS vectorstore from guideline PDF.

        Args:
            guideline_pdf_path: Path to guideline PDF
            save_path: Path to save FAISS index for reuse
        """
        logger.info(f"Extracting guideline PDF: {guideline_pdf_path}")

        # Extract all pages from guideline
        pages_content = PDFExtractor.extract_pdf_by_pages(guideline_pdf_path)

        # Split each page into chunks while preserving page numbers
        logger.info("Chunking guideline text...")
        documents = []

        for page_num, page_text in enumerate(pages_content, start=1):
            # Split this page's content
            page_chunks = self.text_splitter.split_text(page_text)

            # Create documents with page number metadata
            for chunk_idx, chunk in enumerate(page_chunks):
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "source": "guideline",
                            "page": page_num,
                            "chunk_id": len(documents)
                        }
                    )
                )

        logger.info(f"Created {len(documents)} chunks from guideline PDF")

        # Build FAISS vectorstore
        logger.info("Building FAISS vectorstore...")
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)

        # Save to disk for reuse
        if save_path:
            logger.info(f"Saving vectorstore to {save_path}")
            self.vectorstore.save_local(save_path)

    def load_vectorstore(self, load_path: str = "guideline_vectorstore"):
        """Load pre-built FAISS vectorstore from disk."""
        logger.info(f"Loading vectorstore from {load_path}")
        self.vectorstore = FAISS.load_local(
            load_path,
            self.embeddings,
            allow_dangerous_deserialization=True  # Required for FAISS
        )

    def retrieve_relevant_chunks(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve top-k relevant guideline chunks for a query.

        Args:
            query: Query text (report chunk content)
            k: Number of chunks to retrieve

        Returns:
            List of dicts with 'content' and 'page' keys
        """
        if not self.vectorstore:
            raise ValueError("Vectorstore not initialized. Build or load first.")

        # Perform similarity search
        docs = self.vectorstore.similarity_search(query, k=k)

        # Return content with page numbers
        return [
            {
                "content": doc.page_content,
                "page": doc.metadata.get("page", "?")
            }
            for doc in docs
        ]


class ComplianceChecker:
    """Handles compliance checking using Gemini API."""

    def __init__(self, api_key: str, model_name: str = None):
        """
        Initialize Gemini API client.

        Args:
            api_key: Gemini API key
            model_name: Gemini model to use (defaults to GEMINI_MODEL env var or gemini-1.5-flash)
        """
        if model_name is None:
            model_name = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        logger.info(f"Initialized Gemini model: {model_name}")

    def check_compliance(self, report_chunk: str, guideline_context: List[Dict[str, Any]],
                        chunk_start_page: int, chunk_end_page: int) -> Dict[str, Any]:
        """
        Check compliance of a report chunk against guideline context.

        Args:
            report_chunk: Report content to check
            guideline_context: Retrieved relevant guideline chunks with page numbers
            chunk_start_page: Starting page number of chunk
            chunk_end_page: Ending page number of chunk

        Returns:
            Parsed compliance result as dict
        """
        # Construct prompt with page numbers
        guideline_sections = []
        for idx, chunk in enumerate(guideline_context, 1):
            page_num = chunk.get("page", "?")
            content = chunk.get("content", "")
            guideline_sections.append(f"[Guideline Page {page_num}]\n{content}")

        guideline_text = "\n\n---\n\n".join(guideline_sections)

        prompt = f"""You are a compliance auditor reviewing a report against guidelines.

**Guidelines Context (relevant sections with page numbers):**
{guideline_text}

**Report Chunk (Pages {chunk_start_page}-{chunk_end_page}):**
{report_chunk}

**Task:**
Carefully analyze the report chunk for compliance with the guidelines. Check for:
- Values that exceed specified limits or thresholds
- Missing required tables, sections, or data
- Violations of rules or requirements
- Inconsistencies with guideline specifications

**IMPORTANT:** When citing guideline references, ALWAYS include the specific guideline page number in the format "Page X: description" or "Guideline Page X, Section Y".

**Output Format:**
Respond with ONLY a valid JSON object (no markdown code blocks) in this exact format:
{{
    "compliance": "compliant" or "non-compliant" or "partial",
    "issues": [
        {{
            "page": <report page number as integer>,
            "description": "<brief description of issue>",
            "guideline_ref": "Page X: <specific section/table/requirement>",
            "reasoning": "<detailed explanation referencing specific guideline page>"
        }}
    ]
}}

If compliant, return an empty issues array [].
"""

        try:
            # Call Gemini API
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]  # Remove ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remove ```
            response_text = response_text.strip()

            # Parse JSON response
            result = json.loads(response_text)

            # Validate response structure
            if "compliance" not in result:
                result["compliance"] = "partial"
            if "issues" not in result:
                result["issues"] = []

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Response text: {response_text}")
            # Return fallback result
            return {
                "compliance": "partial",
                "issues": [{
                    "page": chunk_start_page,
                    "description": "Error parsing compliance check response",
                    "guideline_ref": "N/A",
                    "reasoning": f"JSON parsing error: {str(e)}"
                }]
            }
        except Exception as e:
            logger.error(f"Error during compliance check: {e}")
            return {
                "compliance": "partial",
                "issues": [{
                    "page": chunk_start_page,
                    "description": "Error during compliance analysis",
                    "guideline_ref": "N/A",
                    "reasoning": f"API error: {str(e)}"
                }]
            }


def format_single_chunk_result(result: Dict[str, Any]) -> str:
    """
    Format a single chunk result for output.

    Args:
        result: Single chunk result dict

    Returns:
        Formatted string for this chunk
    """
    output_lines = []
    start_page = result["start_page"]
    end_page = result["end_page"]
    compliance = result["compliance"]
    issues = result["issues"]

    # Format status
    if compliance == "compliant":
        output_lines.append(f"Pages {start_page}-{end_page}: Compliant.")
    elif compliance == "non-compliant":
        output_lines.append(f"Pages {start_page}-{end_page}: Non-compliant.")
    else:
        output_lines.append(f"Pages {start_page}-{end_page}: Partial compliance.")

    # Format issues
    if issues:
        output_lines.append(f"  Issues found ({len(issues)}):")
        for issue in issues:
            page = issue.get("page", "?")
            desc = issue.get("description", "No description")
            ref = issue.get("guideline_ref", "N/A")
            reasoning = issue.get("reasoning", "No reasoning provided")

            output_lines.append(f"    - Page {page}: {desc}")
            output_lines.append(f"      Guideline Reference: {ref}")
            output_lines.append(f"      Reasoning: {reasoning}")

    output_lines.append("")  # Blank line
    return "\n".join(output_lines)


def format_compliance_output(results: List[Dict[str, Any]]) -> str:
    """
    Format compliance results for output file.

    Args:
        results: List of compliance check results

    Returns:
        Formatted output string
    """
    output_lines = ["# PDF Compliance Check Report\n"]
    total_issues = 0

    for result in results:
        start_page = result["start_page"]
        end_page = result["end_page"]
        compliance = result["compliance"]
        issues = result["issues"]

        # Format status
        if compliance == "compliant":
            output_lines.append(f"Pages {start_page}-{end_page}: Compliant.")
        elif compliance == "non-compliant":
            output_lines.append(f"Pages {start_page}-{end_page}: Non-compliant.")
        else:
            output_lines.append(f"Pages {start_page}-{end_page}: Partial compliance.")

        # Format issues
        if issues:
            output_lines.append(f"  Issues found ({len(issues)}):")
            for issue in issues:
                page = issue.get("page", "?")
                desc = issue.get("description", "No description")
                ref = issue.get("guideline_ref", "N/A")
                reasoning = issue.get("reasoning", "No reasoning provided")

                output_lines.append(f"    - Page {page}: {desc}")
                output_lines.append(f"      Guideline Reference: {ref}")
                output_lines.append(f"      Reasoning: {reasoning}")

            total_issues += len(issues)

        output_lines.append("")  # Blank line between chunks

    # Summary
    output_lines.append("\n" + "=" * 60)
    output_lines.append(f"SUMMARY: Total issues found: {total_issues}")
    output_lines.append(f"Total chunks analyzed: {len(results)}")
    output_lines.append("=" * 60)

    return "\n".join(output_lines)


def main():
    """Main execution function."""
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="PDF Compliance Checker using RAG and Gemini"
    )
    parser.add_argument(
        "--guideline",
        required=True,
        help="Path to guideline PDF file"
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to report PDF file to check"
    )
    parser.add_argument(
        "--gemini_key",
        default=None,
        help="Gemini API key (or set GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--openai_key",
        default=None,
        help="OpenAI API key for embeddings (or set OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--chunk_pages",
        type=int,
        default=4,
        help="Number of pages per report chunk (default: 4)"
    )
    parser.add_argument(
        "--output",
        default="compliance_report.txt",
        help="Output file path (default: compliance_report.txt)"
    )
    parser.add_argument(
        "--rebuild_vectorstore",
        action="store_true",
        help="Force rebuild of guideline vectorstore"
    )
    parser.add_argument(
        "--vectorstore_path",
        default="guideline_vectorstore",
        help="Path to save/load vectorstore (default: guideline_vectorstore)"
    )

    args = parser.parse_args()

    # Get API keys from env if not provided
    if args.gemini_key is None:
        args.gemini_key = os.environ.get('GEMINI_API_KEY')
        if args.gemini_key is None:
            logger.error("Gemini API key not provided. Set GEMINI_API_KEY env var or use --gemini_key")
            sys.exit(1)

    if args.openai_key is None:
        args.openai_key = os.environ.get('OPENAI_API_KEY')
        if args.openai_key is None:
            logger.error("OpenAI API key not provided. Set OPENAI_API_KEY env var or use --openai_key")
            sys.exit(1)

    # Validate input files
    if not os.path.exists(args.guideline):
        logger.error(f"Guideline PDF not found: {args.guideline}")
        sys.exit(1)

    if not os.path.exists(args.report):
        logger.error(f"Report PDF not found: {args.report}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("PDF Compliance Checker")
    logger.info("=" * 60)
    logger.info(f"Guideline: {args.guideline}")
    logger.info(f"Report: {args.report}")
    logger.info(f"Output: {args.output}")
    logger.info("=" * 60)

    try:
        # Step 1: Setup RAG for guideline
        logger.info("\n[STEP 1/4] Setting up RAG system for guideline PDF...")
        rag = GuidelineRAG(
            openai_api_key=args.openai_key,
            chunk_size=1000,
            chunk_overlap=200
        )

        # Check if we should rebuild vectorstore
        if args.rebuild_vectorstore or not os.path.exists(args.vectorstore_path):
            rag.build_vectorstore(args.guideline, args.vectorstore_path)
        else:
            logger.info("Loading existing vectorstore...")
            rag.load_vectorstore(args.vectorstore_path)

        # Step 2: Initialize compliance checker
        logger.info("\n[STEP 2/4] Initializing Gemini API...")
        checker = ComplianceChecker(args.gemini_key)

        # Step 3: Process report in chunks
        logger.info("\n[STEP 3/4] Processing report PDF in chunks...")

        # Get total pages in report
        total_pages = PDFExtractor.get_pdf_page_count(args.report)
        logger.info(f"Report has {total_pages} pages")

        # Initialize output file with header
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write("# PDF Compliance Check Report\n\n")
        logger.info(f"Writing results to: {args.output}")

        results = []
        chunk_num = 0

        # Process in chunks of specified pages
        for start_page in range(1, total_pages + 1, args.chunk_pages):
            chunk_num += 1
            end_page = min(start_page + args.chunk_pages - 1, total_pages)

            logger.info(f"\nProcessing chunk {chunk_num}: Pages {start_page}-{end_page}")

            try:
                # Extract report chunk
                logger.info("  - Extracting pages...")
                chunk_pages = PDFExtractor.extract_pdf_by_pages(
                    args.report, start_page, end_page
                )
                report_chunk = "\n\n".join(chunk_pages)

                # Retrieve relevant guideline chunks
                logger.info("  - Retrieving relevant guideline sections...")
                guideline_context = rag.retrieve_relevant_chunks(report_chunk, k=5)

                # Check compliance
                logger.info("  - Analyzing compliance with Gemini...")
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

                # Append result to file immediately
                chunk_output = format_single_chunk_result(result)
                with open(args.output, 'a', encoding='utf-8') as f:
                    f.write(chunk_output + "\n")

                # Log result summary
                status = compliance_result["compliance"]
                issue_count = len(compliance_result["issues"])
                logger.info(f"  ✓ Status: {status.upper()}, Issues: {issue_count}")

            except Exception as e:
                logger.error(f"  ✗ Error processing chunk {chunk_num}: {e}")
                # Add error result
                result = {
                    "start_page": start_page,
                    "end_page": end_page,
                    "compliance": "partial",
                    "issues": [{
                        "page": start_page,
                        "description": "Error processing chunk",
                        "guideline_ref": "N/A",
                        "reasoning": str(e)
                    }]
                }
                results.append(result)

                # Append error result to file immediately
                chunk_output = format_single_chunk_result(result)
                with open(args.output, 'a', encoding='utf-8') as f:
                    f.write(chunk_output + "\n")

        # Step 4: Write summary to output file
        logger.info("\n[STEP 4/4] Writing summary...")

        # Calculate summary
        total_issues = sum(len(r["issues"]) for r in results)

        # Append summary to file
        summary_lines = [
            "\n" + "=" * 60,
            f"SUMMARY: Total issues found: {total_issues}",
            f"Total chunks analyzed: {chunk_num}",
            "=" * 60
        ]

        with open(args.output, 'a', encoding='utf-8') as f:
            f.write("\n".join(summary_lines) + "\n")

        logger.info(f"✓ Compliance report saved to: {args.output}")

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info(f"COMPLETED: {chunk_num} chunks analyzed, {total_issues} issues found")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n✗ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
