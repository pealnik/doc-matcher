#!/usr/bin/env python3
"""
Example usage demonstrating individual components of the PDF Compliance Checker.
This script shows how each part works independently, useful for debugging or customization.

Usage:
    python example_usage.py --guideline guideline.pdf --report report.pdf --gemini_key YOUR_GEMINI_KEY --openai_key YOUR_OPENAI_KEY
"""

import argparse
from pdf_compliance_checker import PDFExtractor, GuidelineRAG, ComplianceChecker


def example_pdf_extraction(pdf_path: str):
    """Example: Extract content from specific pages of a PDF."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: PDF Extraction")
    print("=" * 60)

    # Get total pages
    total_pages = PDFExtractor.get_pdf_page_count(pdf_path)
    print(f"Total pages in PDF: {total_pages}")

    # Extract first 2 pages
    print("\nExtracting first 2 pages...")
    pages = PDFExtractor.extract_pdf_by_pages(pdf_path, start_page=1, end_page=2)

    for i, content in enumerate(pages, 1):
        print(f"\n--- Page {i} Content (first 500 chars) ---")
        print(content[:500])
        print("...")


def example_rag_setup(guideline_path: str, openai_key: str):
    """Example: Build and query RAG system."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: RAG System Setup and Query")
    print("=" * 60)

    # Initialize RAG
    rag = GuidelineRAG(openai_api_key=openai_key, chunk_size=800, chunk_overlap=150)

    # Build vectorstore
    print("\nBuilding vectorstore from guideline PDF...")
    rag.build_vectorstore(guideline_path, save_path="example_vectorstore")

    # Test query
    test_query = "What are the maximum allowable values for temperature measurements?"
    print(f"\nTest Query: '{test_query}'")
    print("\nTop 3 relevant guideline sections:")

    relevant_chunks = rag.retrieve_relevant_chunks(test_query, k=3)

    for i, chunk in enumerate(relevant_chunks, 1):
        print(f"\n--- Relevant Chunk {i} (first 300 chars) ---")
        print(chunk[:300])
        print("...")


def example_compliance_check(api_key: str):
    """Example: Single compliance check with Gemini."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Compliance Check with Gemini")
    print("=" * 60)

    # Initialize checker
    checker = ComplianceChecker(api_key)

    # Sample data
    guideline_context = [
        """
        Section 2.1 - Temperature Requirements
        All temperature measurements must be within the range of 15-25 degrees Celsius.
        Values outside this range must be flagged as non-compliant.
        Table 1 shows acceptable ranges for different zones.
        """,
        """
        Section 3.2 - Reporting Format
        All reports must include:
        1. Summary table with key metrics
        2. Detailed analysis section
        3. References to guideline sections
        Missing any of these components is considered non-compliant.
        """
    ]

    report_chunk = """
    ## Page 1
    Temperature Reading Analysis

    Zone A: 28 degrees Celsius
    Zone B: 22 degrees Celsius
    Zone C: 19 degrees Celsius

    ## Page 2
    Analysis:
    Zone A shows elevated temperature outside normal range.
    Further investigation required.
    """

    # Perform check
    print("\nChecking compliance...")
    result = checker.check_compliance(
        report_chunk=report_chunk,
        guideline_context=guideline_context,
        chunk_start_page=1,
        chunk_end_page=2
    )

    # Display result
    print(f"\nCompliance Status: {result['compliance']}")
    print(f"Number of Issues: {len(result['issues'])}")

    if result['issues']:
        print("\nIssues Found:")
        for i, issue in enumerate(result['issues'], 1):
            print(f"\n  Issue {i}:")
            print(f"    Page: {issue.get('page', 'N/A')}")
            print(f"    Description: {issue.get('description', 'N/A')}")
            print(f"    Guideline Ref: {issue.get('guideline_ref', 'N/A')}")
            print(f"    Reasoning: {issue.get('reasoning', 'N/A')[:200]}...")


def example_end_to_end(guideline_path: str, report_path: str, gemini_key: str, openai_key: str):
    """Example: Complete workflow for a small section."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: End-to-End Workflow (First 4 Pages)")
    print("=" * 60)

    # Step 1: Setup RAG
    print("\nStep 1: Setting up RAG...")
    rag = GuidelineRAG(openai_api_key=openai_key)
    rag.build_vectorstore(guideline_path, save_path="example_e2e_vectorstore")

    # Step 2: Initialize checker
    print("Step 2: Initializing Gemini...")
    checker = ComplianceChecker(gemini_key)

    # Step 3: Process first chunk
    print("Step 3: Processing first 4 pages of report...")
    report_pages = PDFExtractor.extract_pdf_by_pages(report_path, 1, 4)
    report_chunk = "\n\n".join(report_pages)

    print(f"  Report chunk size: {len(report_chunk)} characters")

    # Step 4: Retrieve relevant guidelines
    print("Step 4: Retrieving relevant guideline sections...")
    guideline_context = rag.retrieve_relevant_chunks(report_chunk, k=5)

    print(f"  Retrieved {len(guideline_context)} guideline chunks")

    # Step 5: Check compliance
    print("Step 5: Checking compliance...")
    result = checker.check_compliance(
        report_chunk=report_chunk,
        guideline_context=guideline_context,
        chunk_start_page=1,
        chunk_end_page=4
    )

    # Step 6: Display results
    print("\n" + "-" * 60)
    print("RESULTS")
    print("-" * 60)
    print(f"Pages 1-4: {result['compliance'].upper()}")

    if result['issues']:
        print(f"\nIssues found: {len(result['issues'])}")
        for i, issue in enumerate(result['issues'], 1):
            print(f"\n  {i}. Page {issue.get('page', 'N/A')}: {issue.get('description', 'N/A')}")
            print(f"     Guideline: {issue.get('guideline_ref', 'N/A')}")
            print(f"     Reason: {issue.get('reasoning', 'N/A')[:150]}...")
    else:
        print("\n✅ No issues found - fully compliant!")


def main():
    """Run examples based on command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Example usage of PDF Compliance Checker components"
    )
    parser.add_argument("--guideline", help="Path to guideline PDF")
    parser.add_argument("--report", help="Path to report PDF")
    parser.add_argument("--gemini_key", help="Gemini API key")
    parser.add_argument("--openai_key", help="OpenAI API key")
    parser.add_argument(
        "--example",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Which example to run (1-4, or 'all')"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("PDF Compliance Checker - Usage Examples")
    print("=" * 60)

    examples = {
        "1": ("PDF Extraction", lambda: example_pdf_extraction(args.report or args.guideline)),
        "2": ("RAG Setup", lambda: example_rag_setup(args.guideline, args.openai_key)),
        "3": ("Compliance Check", lambda: example_compliance_check(args.gemini_key)),
        "4": ("End-to-End", lambda: example_end_to_end(args.guideline, args.report, args.gemini_key, args.openai_key))
    }

    # Validate requirements for each example
    requirements = {
        "1": (args.report or args.guideline, "Need --guideline or --report"),
        "2": (args.guideline and args.openai_key, "Need --guideline and --openai_key"),
        "3": (args.gemini_key, "Need --gemini_key"),
        "4": (args.guideline and args.report and args.gemini_key and args.openai_key,
              "Need --guideline, --report, --gemini_key, and --openai_key")
    }

    # Run selected examples
    examples_to_run = list(examples.keys()) if args.example == "all" else [args.example]

    for ex_num in examples_to_run:
        requirement, error_msg = requirements[ex_num]

        if not requirement:
            print(f"\n⚠ Skipping Example {ex_num}: {error_msg}")
            continue

        try:
            name, func = examples[ex_num]
            func()
        except Exception as e:
            print(f"\n✗ Error in Example {ex_num} ({name}): {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60)
    print("\nFor full compliance check, run:")
    print("python pdf_compliance_checker.py --guideline <file> --report <file> --gemini_key <key> --openai_key <key>")


if __name__ == "__main__":
    main()
