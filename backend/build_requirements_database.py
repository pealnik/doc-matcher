#!/usr/bin/env python3
"""
Build Requirements Database from Ship Recycling Plan Checklist PDF

This script extracts all 42 requirements from the checklist PDF and enriches
them with metadata using LLM to create a structured requirements database.

Usage:
    python build_requirements_database.py
"""

import json
import logging
import os
import sys
from typing import List, Dict, Any
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('requirements_extraction.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class RequirementsDatabaseBuilder:
    """Builds structured requirements database from checklist."""

    def __init__(self, openai_api_key: str):
        """Initialize the builder with OpenAI client."""
        self.client = OpenAI(api_key=openai_api_key)
        self.model = "gpt-4o-mini"

    def get_raw_requirements(self) -> List[Dict[str, str]]:
        """
        Get raw requirements from Ship Recycling Plan checklist.

        These are manually extracted from the PDF for accuracy.
        Returns list of requirements with their regulation sources.
        """

        # Regulation sources
        reg_source_1 = """The Hong Kong International Convention for the Safe and Environmentally Sound Recycling of Ships- 2009 (ANNEX to the HKC)- Regulation 9, 9.1, 9.3, 9.5, 9.6, 24.2.12
-MEPC.196 (62) Guidelines for the Development of the Ship Recycling Plan,2011
-MEPC.210 (63) Guidelines for Safe and Environmentally Sound Ship Recycling,2012
Bangladesh Ship Recycling Act 2018
Bangladesh Hazardous Waste and Ship-Breaking Waste Management Rules 2011"""

        reg_source_2 = "Ship Breaking and Recycling Rules, 2011, Section Rule 16,16.1, 16.2"

        requirements = [
            # Page 1 - Regulation source 1
            {"requirement": "Ship name, IMO number, flag state, type of ship and owner details clearly stated", "regulation_source": reg_source_1},
            {"requirement": "Ship's particulars added", "regulation_source": reg_source_1},
            {"requirement": "Complete Ship recycling facility information provided", "regulation_source": reg_source_1},
            {"requirement": "Project schedule of the ship recycling added", "regulation_source": reg_source_1},
            {"requirement": "Revision history of the SRP, SRP preparation team, preparation date, Team leader and approver signature appended", "regulation_source": reg_source_1},
            {"requirement": "Identification of responsible parties (ship owner, recycler, IHM provider, etc.)", "regulation_source": reg_source_1},
            {"requirement": "General arrangement Plan(GA) plan added", "regulation_source": reg_source_1},
            {"requirement": "Non-breathable spaces(Enclosed spaces) marked on GA plan and added", "regulation_source": reg_source_1},
            {"requirement": "Inclusion of all information derived from all available plans are summarized", "regulation_source": reg_source_1},
            {"requirement": "Approved Layout of the Facility added", "regulation_source": reg_source_1},
            {"requirement": "Project management organogram included", "regulation_source": reg_source_1},
            {"requirement": "Tentative landing location of the vessel's position marked on the Layout plan", "regulation_source": reg_source_1},
            {"requirement": "Qualification of Management Personnel Experience in same type of vessel dismantling", "regulation_source": reg_source_1},
            {"requirement": "Work Force Summary (Planned)", "regulation_source": reg_source_1},
            {"requirement": "Facility Equipment List including any special tools, equipment required for the specific vessel dismantling are included", "regulation_source": reg_source_1},
            {"requirement": "Personal Protective and Safety Equipment (PPE) including any special type of PPE requirement", "regulation_source": reg_source_1},
            {"requirement": "Details of any previous recycling or major repairs", "regulation_source": reg_source_1},
            {"requirement": "Information of International Certificate of IHM, Updated, approved Inventory of Hazardous Material(IHM) available with Part-I, II and III", "regulation_source": reg_source_1},

            # Page 2 - Regulation source 2
            {"requirement": "Available HAZMATs Storage Facilities for the management of removable HAZMATs(As per Inventory of Hazardous Material-IHM)", "regulation_source": reg_source_2},
            {"requirement": "Facility's capacity and capability to recycle the specific ship-Comparison of ship-specific information with the Ship Recycling Facility Plan (SRFP) and/or Document of Authorization to conduct Ship Recycling (DASR)", "regulation_source": reg_source_2},
            {"requirement": "Facility's compliance with national and international regulations (HKC, MEPC.196(62))- A copy of DASR is attached", "regulation_source": reg_source_2},
            {"requirement": "Facility's emergency response and pollution prevention measures", "regulation_source": reg_source_2},
            {"requirement": "Requirement of any ship specific emergency drill, safety equipment included in SRP", "regulation_source": reg_source_2},
            {"requirement": "Approved Beaching Master been selected and appointed", "regulation_source": reg_source_2},
            {"requirement": "Planning for de-ballasting and sludge removal (if required) included in SRP", "regulation_source": reg_source_2},
            {"requirement": "Summarized the legal authorities to be contacted in SRP", "regulation_source": reg_source_2},
            {"requirement": "Arrival stability data and stability during the demolition have been analyzed and recorded", "regulation_source": reg_source_2},
            {"requirement": "Pre-arrival protocols i.e. Vessel acceptance, SRF application for the inspection by the authorities after arrival, HAZMATs management etc. included in SRP", "regulation_source": reg_source_2},
            {"requirement": "A comprehensive ship-specific risk assessment been conducted in term of cargo, type, age, accident, facility constraints and other related elements and recorded in SRP", "regulation_source": reg_source_2},
            {"requirement": "Vessel securing arrangement after arrival is included in SRP", "regulation_source": reg_source_2},
            {"requirement": "On board Occupational Health and Safety procedures including Safety plan addressing risks and hazards specific to the ship and recycling process, training programs for workers on safety and hazardous materials handling, First aid and medical facilities, Procedures for fire protection and emergency evacuation been included in SRP", "regulation_source": reg_source_2},
            {"requirement": "On board environmental protection measures including measures to prevent pollution of air, water, and soil, procedures for containment and treatment of spills and leaks, monitoring and reporting procedures for environmental impacts, waste management plan for hazardous and non-hazardous waste to be included in SRP", "regulation_source": reg_source_2},
            {"requirement": "Safe access/exit arrangement during the full demolition process been included in SRP", "regulation_source": reg_source_2},
            {"requirement": "HAZMAT management fully elaborated( with reference to Inventory of Hazardous Material-IHM)", "regulation_source": reg_source_2},

            # Page 3 - Regulation source 2 (continued)
            {"requirement": "HAZMAT handling team details with certificate number, experience been included", "regulation_source": reg_source_2},
            {"requirement": "Documentation of hazardous material removal and disposal", "regulation_source": reg_source_2},
            {"requirement": "Measures to prevent accidental release of hazardous substances", "regulation_source": reg_source_2},
            {"requirement": "Safe for entry and safe for Hot work preparation, execution and maintenance been included in SRP", "regulation_source": reg_source_2},
            {"requirement": "Competent person for safe entry and hot work execution been included in SRP", "regulation_source": reg_source_2},
            {"requirement": "Step-by-step description of the recycling process, including: Preparatory work (de-gassing, cleaning, removal of hazardous materials). Dismantling sequence. Handling and storage of materials. Final disposal or recycling of components. All above have been included in SRP", "regulation_source": reg_source_2},
            {"requirement": "Timeline for demolition been included in SRP", "regulation_source": reg_source_2},
            {"requirement": "Reporting- After completion report to BSRB", "regulation_source": reg_source_2},
        ]

        logger.info(f"Loaded {len(requirements)} raw requirements")
        return requirements

    def enrich_requirement(self, requirement_text: str, req_id: str) -> Dict[str, Any]:
        """
        Use LLM to enrich a requirement with metadata.

        Args:
            requirement_text: The requirement text
            req_id: Requirement ID (REQ_001, etc.)

        Returns:
            Dict with category, expected_fields, check_type, search_keywords, severity
        """
        prompt = f"""Analyze this Ship Recycling Plan compliance requirement and extract metadata.

REQUIREMENT: {requirement_text}

Extract the following information and respond with ONLY valid JSON:

{{
  "category": "<one of: Ship Information, Facility Information, Documentation, HAZMAT Management, Safety Procedures, Environmental Protection, Risk Assessment, Personnel & Training, Recycling Process, Compliance & Reporting>",
  "expected_fields": ["<field1>", "<field2>", ...],
  "check_type": "<one of: field_presence, document_presence, data_quality, procedural_compliance>",
  "search_keywords": ["<keyword1>", "<keyword2>", ...],
  "severity": "<one of: critical, high, medium, low>"
}}

Guidelines:
- category: Logical grouping of this requirement
- expected_fields: List of 3-7 specific data points or fields that must be present to satisfy this requirement
- check_type:
  * field_presence: requires specific fields/data to be present
  * document_presence: requires specific documents/plans to be attached
  * data_quality: requires data to meet quality standards
  * procedural_compliance: requires procedures/processes to be described
- search_keywords: 3-8 keywords that would help locate relevant content in a document
- severity:
  * critical: ship identity, IHM, fundamental safety requirements
  * high: HAZMAT management, major safety procedures, key documentation
  * medium: facility details, personnel qualifications, standard procedures
  * low: supplementary information

Respond with ONLY the JSON object, no other text.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in ship recycling compliance regulations. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0,
                seed=42,
                max_tokens=800
            )

            metadata = json.loads(response.choices[0].message.content)
            logger.info(f"✓ Enriched {req_id}: {metadata['category']}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to enrich {req_id}: {e}")
            # Return default metadata
            return {
                "category": "General",
                "expected_fields": ["information", "details"],
                "check_type": "field_presence",
                "search_keywords": ["ship", "recycling", "plan"],
                "severity": "medium"
            }

    def build_database(self, output_path: str = "requirements_database.json") -> Dict[str, Any]:
        """
        Build complete requirements database.

        Args:
            output_path: Path to save the database JSON

        Returns:
            Complete requirements database dict
        """
        logger.info("Starting requirements database build...")

        # Get raw requirements
        raw_requirements = self.get_raw_requirements()

        # Enrich each requirement
        enriched_requirements = []

        for i, req in enumerate(raw_requirements, start=1):
            req_id = f"REQ_{i:03d}"
            logger.info(f"Processing {req_id} ({i}/{len(raw_requirements)})")

            # Get metadata from LLM
            metadata = self.enrich_requirement(req["requirement"], req_id)

            # Build complete requirement entry
            enriched_req = {
                "id": req_id,
                "requirement": req["requirement"],
                "regulation_source": req["regulation_source"],
                "category": metadata["category"],
                "expected_fields": metadata["expected_fields"],
                "check_type": metadata["check_type"],
                "search_keywords": metadata["search_keywords"],
                "severity": metadata["severity"]
            }

            enriched_requirements.append(enriched_req)

        # Build complete database
        database = {
            "checklist_name": "Ship Recycling Plan (SRP) Compliance Checklist",
            "version": "1.0",
            "last_updated": "2025-12-12",
            "regulations": [
                "The Hong Kong International Convention (HKC) - Regulation 9, 9.1, 9.3, 9.5, 9.6, 24.2.12",
                "MEPC.196(62) - Guidelines for SRP Development, 2011",
                "MEPC.210(63) - Guidelines for Safe Ship Recycling, 2012",
                "Bangladesh Ship Recycling Act 2018",
                "Bangladesh Hazardous Waste and Ship-Breaking Waste Management Rules 2011",
                "Ship Breaking and Recycling Rules 2011, Section 16, 16.1, 16.2"
            ],
            "total_requirements": len(enriched_requirements),
            "requirements": enriched_requirements
        }

        # Save to file
        output_path = Path(output_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(database, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ Requirements database saved to {output_path}")
        logger.info(f"✓ Total requirements: {len(enriched_requirements)}")

        # Print summary
        self.print_summary(database)

        return database

    def print_summary(self, database: Dict[str, Any]):
        """Print summary of requirements database."""
        logger.info("\n" + "="*80)
        logger.info("REQUIREMENTS DATABASE SUMMARY")
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

    # Get OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Build database
    builder = RequirementsDatabaseBuilder(openai_api_key=api_key)
    database = builder.build_database(output_path="requirements_database.json")

    logger.info("\n✓ Requirements database build complete!")
    logger.info(f"✓ Output: requirements_database.json")
    logger.info(f"✓ Total: {database['total_requirements']} requirements")


if __name__ == "__main__":
    main()
