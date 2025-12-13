#!/usr/bin/env python3
"""
Generate/Enhance Checklist JSON from MEPC Guideline PDF

This script extracts requirements from MEPC guideline PDFs (like MEPC.379(80) IHM.pdf)
and creates a structured JSON checklist file compatible with the compliance checker.
It can also take an existing checklist (JSON) or a PDF as a base, and enhance its
requirements with additional context from a guideline PDF.

Usage Examples:
1. Generate a new checklist from a guideline PDF (original functionality):
   python generate_checklist_from_mepc.py output/mepc_379_80_ihm.json --enhancement_pdf "report/RES.MEPC.379(80) IHM.pdf"

2. Generate a checklist from a base PDF, without additional enhancement:
   python generate_checklist_from_mepc.py output/base_from_pdf.json --base_source "report/MyCustomGuideline.pdf"

3. Enhance an existing JSON checklist with a guideline PDF:
   python generate_checklist_from_mepc.py output/enhanced_checklist.json --base_source "data/guidelines/Checklist.json" --enhancement_pdf "report/RES.MEPC.379(80) IHM.pdf"
"""

import argparse
import json
import logging
import os
import sys
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv
import pdfplumber

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('checklist_generation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class MEPCChecklistGenerator:
    """Generates structured checklist from MEPC guideline PDFs."""

    def __init__(self, openai_api_key: str, model: str = "gpt-4o"):
        """Initialize the generator with OpenAI client."""
        self.client = OpenAI(api_key=openai_api_key)
        self.model = model

    def extract_text_from_pdf(self, pdf_path: str, max_pages: int = None) -> str:
        """
        Extract text from PDF file.

        Args:
            pdf_path: Path to the MEPC guideline PDF
            max_pages: Maximum pages to extract (None = all pages)

        Returns:
            Extracted text from the PDF
        """
        logger.info(f"Extracting text from PDF: {pdf_path}")

        text_content = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages) if max_pages is None else min(len(pdf.pages), max_pages)
                pages_to_process = pdf.pages if max_pages is None else pdf.pages[:max_pages]
                logger.info(f"Processing {total_pages} pages (total in PDF: {len(pdf.pages)})...")

                for i, page in enumerate(pages_to_process, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(f"\n--- Page {i} ---\n{page_text}")

                    if i % 5 == 0:
                        logger.info(f"  Processed {i}/{total_pages} pages")

        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise

        full_text = "\n".join(text_content)
        logger.info(f"✓ Extracted {len(full_text)} characters from PDF")
        return full_text

    def extract_requirements_from_text(self, pdf_text: str, guideline_name: str) -> List[Dict[str, str]]:
        """
        Use LLM to extract requirements from the PDF text.
        Processes text in chunks to ensure comprehensive coverage.

        Args:
            pdf_text: Extracted text from the MEPC PDF
            guideline_name: Name of the guideline (e.g., "MEPC.379(80)")

        Returns:
            List of requirements with basic info
        """
        logger.info("Using LLM to extract requirements from PDF text...")

        # Split text into overlapping chunks to ensure no requirements are missed
        chunk_size = 40000  # chars per chunk (leaving room for prompt)
        overlap = 5000      # overlap between chunks to catch split requirements
        chunks = []

        for i in range(0, len(pdf_text), chunk_size - overlap):
            chunk = pdf_text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk)

        logger.info(f"Processing document in {len(chunks)} chunks for comprehensive extraction...")

        all_requirements = []

        for chunk_idx, chunk in enumerate(chunks, 1):
            logger.info(f"Extracting from chunk {chunk_idx}/{len(chunks)}...")

            prompt = f"""You are analyzing a maritime regulation guideline document: {guideline_name}.

Your task is to extract ALL COMPLIANCE REQUIREMENTS from this section of the document. These are specific obligations, checks, or items that must be verified for a ship to be compliant.

Document text (Part {chunk_idx} of {len(chunks)}):
{chunk}

Please extract ALL compliance requirements from this section (do not limit the number).

For each requirement, provide:
1. A clear, concise requirement statement (what must be checked/verified)
2. The regulation source or section reference

Focus on:
- Part I requirements (materials in structure/equipment)
- Part II requirements (operational wastes)
- Part III requirements (stores)
- Specific hazardous materials that must be checked (Tables A, B, C, D)
- Documentation requirements
- Maintenance and updating requirements
- Verification and testing requirements
- Any SHALL, MUST, or SHOULD statements indicating obligations

Format your response as a JSON array with this structure:
{{
  "requirements": [
    {{
      "requirement": "Clear statement of what must be checked or verified",
      "regulation_source": "Reference to the regulation or section (e.g., MEPC.379(80) Section 3.2.1)"
    }}
  ]
}}

Respond with ONLY the JSON object, no other text."""

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert in maritime regulations and compliance requirements extraction. Respond only with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,  # Lower temperature for more consistent extraction
                    max_tokens=6000   # Increased to handle more requirements
                )

                result = json.loads(response.choices[0].message.content)
                chunk_requirements = result.get("requirements", [])
                all_requirements.extend(chunk_requirements)

                logger.info(f"  ✓ Extracted {len(chunk_requirements)} requirements from chunk {chunk_idx}")

            except Exception as e:
                logger.error(f"Error extracting requirements from chunk {chunk_idx}: {e}")
                # Continue with other chunks even if one fails

        # Deduplicate requirements
        logger.info(f"Total requirements before deduplication: {len(all_requirements)}")
        deduplicated = self._deduplicate_requirements(all_requirements)
        logger.info(f"✓ Total requirements after deduplication: {len(deduplicated)}")

        return deduplicated

    def _deduplicate_requirements(self, requirements: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Deduplicate requirements using LLM to identify semantically similar items.

        Args:
            requirements: List of requirements that may contain duplicates

        Returns:
            Deduplicated list of requirements
        """
        if len(requirements) <= 1:
            return requirements

        logger.info("Deduplicating requirements using semantic analysis...")

        # First pass: simple text matching
        seen = {}
        for req in requirements:
            req_text = req["requirement"].strip().lower()
            if req_text not in seen:
                seen[req_text] = req

        simple_dedup = list(seen.values())
        logger.info(f"  After simple deduplication: {len(simple_dedup)} requirements")

        # If still too many, use LLM for semantic deduplication
        if len(simple_dedup) > 100:
            logger.info("  Performing semantic deduplication with LLM...")
            return self._llm_deduplicate(simple_dedup)

        return simple_dedup

    def _llm_deduplicate(self, requirements: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Use LLM to semantically deduplicate requirements.

        Args:
            requirements: List of requirements

        Returns:
            Deduplicated requirements
        """
        # Group requirements by first few words for batch processing
        batches = []
        batch_size = 50

        for i in range(0, len(requirements), batch_size):
            batch = requirements[i:i + batch_size]
            batches.append(batch)

        deduplicated = []

        for batch_idx, batch in enumerate(batches, 1):
            logger.info(f"  Deduplicating batch {batch_idx}/{len(batches)}...")

            # Create a compact representation
            req_list = "\n".join([f"{i+1}. {req['requirement']}" for i, req in enumerate(batch)])

            prompt = f"""You are analyzing a list of compliance requirements that may contain duplicates or very similar items.

Requirements:
{req_list}

Identify which requirements are duplicates or substantially similar (>80% overlap in meaning).
Return the indices of requirements to KEEP (remove duplicates, keep the most comprehensive version).

Respond with ONLY a JSON object:
{{
  "keep_indices": [1, 3, 5, ...]
}}"""

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert in identifying duplicate requirements. Respond only with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_tokens=1000
                )

                result = json.loads(response.choices[0].message.content)
                keep_indices = result.get("keep_indices", list(range(1, len(batch) + 1)))

                # Keep only specified requirements
                for idx in keep_indices:
                    if 1 <= idx <= len(batch):
                        deduplicated.append(batch[idx - 1])

            except Exception as e:
                logger.error(f"Error in semantic deduplication: {e}")
                # If LLM fails, keep all from this batch
                deduplicated.extend(batch)

        logger.info(f"  After semantic deduplication: {len(deduplicated)} requirements")
        return deduplicated

    def batch_enrich_requirements(self, requirements_batch: List[Dict[str, Any]], pdf_context: str = None) -> List[Dict[str, Any]]:
        """
        Use LLM to enrich a batch of requirements with metadata in a single API call.

        Args:
            requirements_batch: A list of requirement dictionaries to be enriched.
            pdf_context: Optional additional PDF text to use for enrichment.

        Returns:
            A list of metadata dictionaries corresponding to the input batch.
        """
        if not requirements_batch:
            return []

        context_instruction = ""
        if pdf_context:
            context_instruction = f"""
Additional context from a guideline PDF to help with enrichment:
<PDF_CONTEXT>
{pdf_context[:5000]} # Limit context to avoid token overflow
</PDF_CONTEXT>
Use this context to provide more accurate and detailed metadata for each requirement."""

        # Prepare a JSON-compatible string of the requirements batch
        batch_json_string = json.dumps(
            [{"id": req["id"], "requirement": req["requirement"]} for req in requirements_batch],
            indent=2
        )

        prompt = f"""You are an expert in IHM compliance and maritime regulations.
Analyze this BATCH of compliance requirements and extract metadata for EACH ONE.
{context_instruction}

**REQUIREMENTS BATCH:**
{batch_json_string}

For EACH requirement in the batch, provide its metadata. Respond with ONLY a valid JSON object in this exact format, containing a list of objects under the "enriched_requirements" key. Ensure the 'id' of each result matches the 'id' from the input batch.

{{
  "enriched_requirements": [
    {{
      "id": "<id from input, e.g., REQ_001>",
      "metadata": {{
        "category": "<one of: Ship Information, Hazardous Materials - Table A, Hazardous Materials - Table B, Hazardous Materials - Table C/D, IHM Part I, IHM Part II, IHM Part III, Documentation & Maintenance, Material Declarations, Verification & Testing, Facility Information, General>",
        "expected_fields": ["<field1>", "<field2>", ...],
        "check_type": "<one of: field_presence, document_presence, material_testing, procedural_compliance, declaration_verification>",
        "search_keywords": ["<keyword1>", "<keyword2>", ...],
        "severity": "<one of: critical, high, medium, low>"
      }}
    }}
  ]
}}

Guidelines for metadata:
- category: Logical grouping of the requirement.
- expected_fields: 3-7 specific data points or items that must be present/checked.
- check_type: The nature of the compliance check.
- search_keywords: 3-8 keywords to locate relevant content.
- severity: Criticality of the requirement (critical, high, medium, low).

Respond with ONLY the JSON object.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in IHM compliance. Respond only with valid JSON that strictly follows the requested format."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0,
                seed=42,
                max_tokens=4096  # Allow more tokens for batch response
            )

            result = json.loads(response.choices[0].message.content)
            
            # Validate and structure the output
            if "enriched_requirements" not in result or not isinstance(result["enriched_requirements"], list):
                raise ValueError("LLM response is missing 'enriched_requirements' list.")

            # Create a mapping from ID to metadata for easy lookup
            metadata_map = {item['id']: item['metadata'] for item in result["enriched_requirements"]}
            
            # Return a list of metadata in the same order as the input batch
            ordered_metadata = []
            for req in requirements_batch:
                req_id = req["id"]
                if req_id in metadata_map:
                    ordered_metadata.append(metadata_map[req_id])
                else:
                    # If LLM failed to return metadata for a specific req, add a default
                    logger.warning(f"Missing metadata for {req_id} in batch response. Using default.")
                    ordered_metadata.append({
                        "category": "General", "expected_fields": [],
                        "check_type": "field_presence", "search_keywords": [], "severity": "medium"
                    })
            
            logger.info(f"✓ Enriched batch of {len(requirements_batch)} requirements.")
            return ordered_metadata

        except Exception as e:
            logger.error(f"Failed to enrich batch: {e}. Returning default metadata for all items in batch.")
            # Return default metadata for the entire batch on failure
            return [{
                "category": "General", "expected_fields": ["information", "details"],
                "check_type": "field_presence", "search_keywords": ["IHM", "inventory"], "severity": "medium"
            }] * len(requirements_batch)


    def print_summary(self, database: Dict[str, Any]):
        """Print summary of checklist database."""
        logger.info("\n" + "="*80)
        logger.info("CHECKLIST GENERATION SUMMARY")
        logger.info("="*80)

        requirements = database["requirements"]

        # Category breakdown
        categories = {}
        for req in requirements:
            cat = req["category"]
            categories[cat] = categories.get(cat, 0) + 1

        logger.info("\nCategory Breakdown:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  - {cat}: {count} requirements")

        # Severity breakdown
        severities = {}
        for req in requirements:
            sev = req["severity"]
            severities[sev] = severities.get(sev, 0) + 1

        logger.info("\nSeverity Breakdown:")
        for sev in ["critical", "high", "medium", "low"]:
            count = severities.get(sev, 0)
            logger.info(f"  - {sev.upper()}: {count} requirements")

        # Check type breakdown
        check_types = {}
        for req in requirements:
            ct = req["check_type"]
            check_types[ct] = check_types.get(ct, 0) + 1

        logger.info("\nCheck Type Breakdown:")
        for ct, count in sorted(check_types.items()):
            logger.info(f"  - {ct}: {count} requirements")

        logger.info("\n" + "="*80)


def main():
    """Main entry point."""

    parser = argparse.ArgumentParser(
        description="Generate/Enhance Checklist JSON from MEPC Guideline PDF or existing checklist."
    )
    parser.add_argument(
        "output_json_path",
        help="Path to save the generated or enhanced JSON checklist."
    )
    parser.add_argument(
        "--enhancement_pdf",
        dest="enhancement_pdf_path",
        help="Path to a MEPC guideline PDF to extract requirements from (default mode) or to enhance existing requirements with."
    )
    parser.add_argument(
        "--base_source",
        dest="base_source_path",
        help="Path to an existing JSON checklist file or a PDF file whose requirements will form the base of the checklist."
    )

    args = parser.parse_args()

    output_path = args.output_json_path
    enhancement_pdf_path = args.enhancement_pdf_path
    base_source_path = args.base_source_path

    if not enhancement_pdf_path and not base_source_path:
        parser.error("Either --enhancement_pdf or --base_source must be provided.")

    if enhancement_pdf_path and not os.path.exists(enhancement_pdf_path):
        logger.error(f"Enhancement PDF file not found: {enhancement_pdf_path}")
        sys.exit(1)
    
    if base_source_path and not os.path.exists(base_source_path):
        logger.error(f"Base source file not found: {base_source_path}")
        sys.exit(1)


    # Get OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Initialize generator
    generator = MEPCChecklistGenerator(openai_api_key=api_key)

    raw_requirements: List[Dict[str, str]] = []
    checklist_name: str = "Generated Checklist"
    regulations: List[str] = []

    # --- Step 1: Determine raw_requirements from base_source or enhancement_pdf ---
    if base_source_path:
        if base_source_path.endswith(".json"):
            logger.info(f"Loading base requirements from JSON: {base_source_path}")
            try:
                with open(base_source_path, 'r', encoding='utf-8') as f:
                    base_data = json.load(f)
                raw_requirements = base_data.get("requirements", [])
                checklist_name = base_data.get("checklist_name", f"Checklist from {os.path.basename(base_source_path)}")
                regulations = base_data.get("regulations", [os.path.basename(base_source_path)])
                # Normalize raw_requirements to ensure they have 'requirement' and 'regulation_source'
                raw_requirements = [{
                    "requirement": req.get("requirement", ""),
                    "regulation_source": req.get("regulation_source", "Unknown")
                } for req in raw_requirements if req.get("requirement")]

            except Exception as e:
                logger.error(f"Error loading or parsing JSON base source {base_source_path}: {e}")
                sys.exit(1)

        elif base_source_path.endswith(".pdf"):
            logger.info(f"Extracting raw requirements from base PDF: {base_source_path}")
            base_pdf_text = generator.extract_text_from_pdf(base_source_path)
            raw_requirements = generator.extract_requirements_from_text(base_pdf_text, guideline_name=f"Base: {os.path.basename(base_source_path)}")
            checklist_name = f"Checklist from {os.path.basename(base_source_path).replace('.pdf', '')}"
            regulations = [os.path.basename(base_source_path).replace('.pdf', '')]
        else:
            logger.error(f"Unsupported --base_source file type: {base_source_path}. Must be .json or .pdf")
            sys.exit(1)
    elif enhancement_pdf_path: # Default mode, only enhancement_pdf provided
        logger.info(f"Extracting raw requirements from enhancement PDF: {enhancement_pdf_path} (default mode)")
        pdf_text = generator.extract_text_from_pdf(enhancement_pdf_path)
        raw_requirements = generator.extract_requirements_from_text(pdf_text, guideline_name=f"Guideline: {os.path.basename(enhancement_pdf_path)}")
        # Determine checklist details based on filename (similar to original logic)
        pdf_filename = os.path.basename(enhancement_pdf_path)
        if "379" in pdf_filename and "IHM" in pdf_filename:
            checklist_name = "Inventory of Hazardous Materials (IHM) Compliance Checklist"
            regulations = ["RESOLUTION MEPC.379(80) - 2023 Guidelines for the development of the Inventory of Hazardous Materials"]
        else:
            checklist_name = f"Maritime Compliance Checklist - {pdf_filename}"
            regulations = [pdf_filename.replace('.pdf', '')]
    
    if not raw_requirements:
        logger.error("No requirements found to process. Exiting.")
        sys.exit(1)


    # --- Step 2: Prepare enhancement_pdf_text if provided ---
    enhancement_pdf_text = None
    if enhancement_pdf_path:
        logger.info(f"Loading enhancement context from PDF: {enhancement_pdf_path}")
        enhancement_pdf_text = generator.extract_text_from_pdf(enhancement_pdf_path)


    # --- Step 3: Enrich/Enhance each requirement in batches ---
    enriched_requirements = []
    total = len(raw_requirements)
    logger.info(f"Starting enrichment of {total} requirements in batches...")

    batch_size = 10  # Process 10 requirements per API call
    
    # Assign temporary IDs to each requirement for processing
    reqs_with_ids = [
        {"id": f"REQ_{i:03d}", **req} for i, req in enumerate(raw_requirements, 1)
    ]

    for i in range(0, total, batch_size):
        batch = reqs_with_ids[i:i + batch_size]
        batch_start_num = i + 1
        batch_end_num = i + len(batch)
        total_batches = (total + batch_size - 1) // batch_size
        current_batch_num = (i // batch_size) + 1

        logger.info(
            f"Processing batch {current_batch_num}/{total_batches} "
            f"(requirements {batch_start_num}-{batch_end_num} of {total})..."
        )
        
        # Get the enriched metadata for the entire batch
        enriched_metadata_list = generator.batch_enrich_requirements(
            batch,
            pdf_context=enhancement_pdf_text
        )

        # Merge the original requirement with its new metadata
        for original_req, enriched_metadata in zip(batch, enriched_metadata_list):
            enriched_req = {
                **original_req,
                **enriched_metadata
            }
            enriched_requirements.append(enriched_req)
    
    logger.info(f"✓ Enrichment of {total} requirements complete.")


    # --- Step 4: Build complete database ---
    database = {
        "checklist_name": checklist_name,
        "version": "1.0",
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "regulations": regulations,
        "total_requirements": len(enriched_requirements),
        "requirements": enriched_requirements
    }

    # --- Step 5: Save to file ---
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)

    logger.info(f"\n✓ Checklist saved to {output_path}")
    logger.info(f"✓ Total: {len(enriched_requirements)} requirements")

    # Print summary
    generator.print_summary(database)

    logger.info("\n✓ Checklist generation/enhancement complete!")



if __name__ == "__main__":
    main()
