"""Clearly labelled demonstration PDF for a simulated prescription."""

from __future__ import annotations

from fpdf import FPDF

from app_pages.prescription_service import SIMULATION_NOTICE, STATUS_DRAFT, STATUS_VOIDED

MEDICATION_COLUMNS = [
    ("Medication", "name", 40),
    ("Dosage", "dosage", 28),
    ("Frequency", "frequency", 32),
    ("Duration", "duration", 26),
    ("Instructions", "instructions", 64),
]


_ASCII_PUNCTUATION = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
                                    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00a0": " "})


def _latin1(value) -> str:
    """The built-in PDF fonts only cover Latin-1, so map common punctuation and replace anything else."""
    text = str(value if value is not None else "").translate(_ASCII_PUNCTUATION)
    return text.encode("latin-1", "replace").decode("latin-1")


def _format_date(value) -> str:
    return value.strftime("%b %d, %Y") if hasattr(value, "strftime") else "-"


class _SimulatedPrescriptionPDF(FPDF):
    def __init__(self, watermark: str) -> None:
        super().__init__()
        self.watermark = watermark
        self.set_auto_page_break(auto=True, margin=25)

    def header(self) -> None:
        # Large diagonal watermark behind the content on every page.
        self.set_font("Helvetica", "B", 60)
        self.set_text_color(235, 200, 200)
        with self.rotation(45, x=self.w / 2, y=self.h / 2):
            self.text(x=self.w / 2 - self.get_string_width(self.watermark) / 2, y=self.h / 2, text=self.watermark)

        self.set_fill_color(178, 34, 34)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 9, "SIMULATED PRESCRIPTION - EDUCATIONAL DEMONSTRATION ONLY", align="C", fill=True,
                  new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def footer(self) -> None:
        self.set_y(-20)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.multi_cell(0, 4, _latin1(SIMULATION_NOTICE), align="C")
        self.cell(0, 4, f"Page {self.page_no()}", align="C")


def build_prescription_pdf(prescription: dict) -> bytes:
    """Return the PDF bytes for a prescription, labelled simulated on every page."""
    status = str(prescription.get("status") or "").lower()
    watermark = {STATUS_DRAFT: "DRAFT - SIMULATED", STATUS_VOIDED: "VOIDED - SIMULATED"}.get(status, "SIMULATED")

    pdf = _SimulatedPrescriptionPDF(watermark)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 9, "Simulated Prescription", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    rows = [
        ("Prescription ID", prescription.get("prescription_id")),
        ("Status", status.upper()),
        ("Created", _format_date(prescription.get("created_at"))),
        ("Finalized", _format_date(prescription.get("finalized_at"))),
        ("Patient", f"{prescription.get('patient_name')} (ID: {prescription.get('patient_id')})"),
        ("Doctor", f"{prescription.get('doctor_name')} (ID: {prescription.get('doctor_id')})"),
    ]
    if status == STATUS_VOIDED:
        rows += [("Voided", _format_date(prescription.get("voided_at"))), ("Void reason", prescription.get("void_reason"))]
    for label, value in rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(35, 6, _latin1(label))
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _latin1(value if value not in (None, "") else "-"), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Medications (manually entered demonstration data)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    with pdf.table(col_widths=[width for _, _, width in MEDICATION_COLUMNS], text_align="LEFT") as table:
        header = table.row()
        for title, _, _ in MEDICATION_COLUMNS:
            header.cell(title)
        for medication in prescription.get("medications") or []:
            row = table.row()
            for _, field, _ in MEDICATION_COLUMNS:
                row.cell(_latin1(medication.get(field) or "-"))

    if prescription.get("doctor_note"):
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Doctor's note", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _latin1(prescription["doctor_note"]))

    return bytes(pdf.output())


def prescription_pdf_filename(prescription: dict) -> str:
    return f"{prescription.get('prescription_id') or 'prescription'}_SIMULATED.pdf"
