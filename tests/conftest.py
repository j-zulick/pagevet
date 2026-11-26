"""Shared test helpers."""

import io

import pytest


def _make_pdf(page_text: str, title: str = "", note: str = "") -> bytes:
    """A one-page PDF with ``page_text`` drawn on it, optional title metadata and a text annotation."""
    stream = f"BT /F1 12 Tf 72 720 Td ({page_text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    out.write(b"".join(b"%010d 00000 n \n" % o for o in offsets))
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(out.getvalue()))
    writer = pypdf.PdfWriter(clone_from=reader)
    if title:
        writer.add_metadata({"/Title": title})
    if note:
        from pypdf.annotations import Text
        writer.add_annotation(0, Text(text=note, rect=(50, 550, 200, 650)))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()




@pytest.fixture
def make_pdf():
    """Build a one-page PDF in memory (needs pypdf, a dev dependency)."""
    pytest.importorskip("pypdf")
    return _make_pdf
