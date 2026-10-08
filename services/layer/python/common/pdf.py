"""A dependency-free single-font PDF writer, enough for a Letter Before Action."""
from __future__ import annotations

import textwrap

_PAGE_W, _PAGE_H, _MARGIN, _LEADING, _SIZE = 595, 842, 56, 15, 11


def _esc(s: str) -> str:
    s = s.replace("£", "\xa3")   # WinAnsi pound sign
    return s.encode("cp1252", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_pdf(title: str, body: str) -> bytes:
    lines = [title, ""]
    for para in body.splitlines():
        lines += textwrap.wrap(para, 90) or [""]
    per_page = (_PAGE_H - 2 * _MARGIN) // _LEADING
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    objs: list[bytes] = []
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, pg in enumerate(pages):
        stream = ["BT", f"/F1 {_SIZE} Tf", f"{_LEADING} TL", f"{_MARGIN} {_PAGE_H - _MARGIN} Td"]
        stream += [f"({_esc(l)}) Tj T*" for l in pg] + ["ET"]
        data = "\n".join(stream).encode("latin-1")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_W} {_PAGE_H}] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
