"""
PDF Report Generator for Compliance Results
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from datetime import datetime
from typing import List, Dict, Any
import io


def generate_compliance_pdf(task_data: Dict[str, Any]) -> io.BytesIO:
    """
    Generate a PDF report from compliance check results

    Args:
        task_data: Task data including result rows and summary

    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = io.BytesIO()

    # Use landscape orientation for better table fit
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    # Container for the 'Flowable' objects
    elements = []

    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#374151'),
        spaceAfter=12,
        alignment=TA_LEFT
    )

    # Title
    title = Paragraph("IHM Compliance Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))

    # Report metadata
    result = task_data.get("result", {})
    summary = result.get("summary", {})

    metadata = [
        ["Report File:", task_data.get("report_filename", "N/A")],
        ["Generated:", datetime.fromisoformat(task_data["created_at"]).strftime("%Y-%m-%d %H:%M:%S")],
        ["Total Checks:", str(summary.get("total_rows", 0))],
        ["Total Pages:", str(summary.get("total_pages", 0))],
    ]

    metadata_table = Table(metadata, colWidths=[2*inch, 4*inch])
    metadata_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1f2937')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(metadata_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Summary section
    summary_heading = Paragraph("Summary", heading_style)
    elements.append(summary_heading)

    summary_data = [
        ["Status", "Count"],
        ["Compliant", str(summary.get("total_compliant", 0))],
        ["Non-Compliant", str(summary.get("total_non_compliant", 0))],
        ["Partially Compliant", str(summary.get("total_partial", 0))],
    ]

    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4 * inch))

    # Detailed results
    results_heading = Paragraph("Detailed Compliance Results", heading_style)
    elements.append(results_heading)
    elements.append(Spacer(1, 0.1 * inch))

    rows = result.get("rows", [])

    if rows:
        # Table header
        table_data = [[
            "MEPC Requirement",
            "IHM Output",
            "Status",
            "Remarks"
        ]]

        # Add data rows
        for row in rows:
            status = row.get("status", "Unknown")

            table_data.append([
                Paragraph(row.get("mepc_reference", "N/A"), styles['Normal']),
                Paragraph(row.get("ihm_output", "N/A"), styles['Normal']),
                status,
                Paragraph(row.get("remarks", "N/A"), styles['Normal'])
            ])

        # Create table
        col_widths = [2.5*inch, 3*inch, 1.5*inch, 3*inch]
        results_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Style the table
        table_style = [
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]

        # Add status-specific coloring
        for idx, row in enumerate(rows, start=1):
            status = row.get("status", "")
            if status == "Non-Compliant":
                table_style.append(('BACKGROUND', (2, idx), (2, idx), colors.HexColor('#fee2e2')))
                table_style.append(('TEXTCOLOR', (2, idx), (2, idx), colors.HexColor('#991b1b')))
            elif status == "Compliant":
                table_style.append(('BACKGROUND', (2, idx), (2, idx), colors.HexColor('#d1fae5')))
                table_style.append(('TEXTCOLOR', (2, idx), (2, idx), colors.HexColor('#065f46')))
            elif status == "Partially Compliant":
                table_style.append(('BACKGROUND', (2, idx), (2, idx), colors.HexColor('#fed7aa')))
                table_style.append(('TEXTCOLOR', (2, idx), (2, idx), colors.HexColor('#92400e')))

        results_table.setStyle(TableStyle(table_style))
        elements.append(results_table)
    else:
        no_data = Paragraph("No compliance data available.", styles['Normal'])
        elements.append(no_data)

    # Footer
    elements.append(Spacer(1, 0.4 * inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER
    )
    footer = Paragraph(
        f"Generated by PDF Compliance Checker • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        footer_style
    )
    elements.append(footer)

    # Build PDF
    doc.build(elements)

    # Get the value from the BytesIO buffer
    buffer.seek(0)
    return buffer
