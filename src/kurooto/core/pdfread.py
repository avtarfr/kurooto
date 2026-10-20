"""Reading PDFs with nothing but Python: how many pages there are, each page's text layer, the bookmarks (chapters),
and the picture on a scanned page. That's enough to pick how each page of a book is read. When Poppler (pdftotext,
pdftoppm) is installed, Books uses it first: it reads more kinds of PDF and draws any page as a picture.

What this reader handles: ordinary and compressed PDFs (object streams, Flate, ASCII hex and 85), text in fonts with a
ToUnicode map or a simple encoding, and scanned pages stored as JPEG, Flate or CCITT fax pictures. Not encrypted PDFs
(even ones that open without a password), JBIG2 or JPEG 2000 pictures: Poppler reads those.
"""

from __future__ import annotations

import base64
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WS = b" \t\r\n\x0c\x00"
DELIM = b"()<>[]{}/%"
OBJ = re.compile(rb"(?<![0-9])(\d{1,10})\s+(\d{1,5})\s+obj\b")
MAX_DEPTH = 40
KEYWORDS = {"true": True, "false": False, "null": None}
IMAGE_FILTERS = {"DCTDecode", "DCT", "CCITTFaxDecode", "CCF", "JBIG2Decode", "JPXDecode"}
# glyph names a font's /Differences uses, for the letters and symbols maths books need most
GLYPHS = {
    "fi": "fi",
    "fl": "fl",
    "ff": "ff",
    "ffi": "ffi",
    "ffl": "ffl",
    "quoteleft": "‘",
    "quoteright": "’",
    "quotedblleft": "“",
    "quotedblright": "”",
    "endash": "–",
    "emdash": "—",
    "bullet": "•",
    "minus": "−",
    "space": " ",
    "period": ".",
    "comma": ",",
    "colon": ":",
    "semicolon": ";",
    "hyphen": "-",
    "parenleft": "(",
    "parenright": ")",
    "bracketleft": "[",
    "bracketright": "]",
    "braceleft": "{",
    "braceright": "}",
    "equal": "=",
    "plus": "+",
    "slash": "/",
    "less": "<",
    "greater": ">",
    "exclam": "!",
    "question": "?",
    "quotesingle": "'",
    "quotedbl": '"',
    "infinity": "∞",
    "integral": "∫",
    "summation": "∑",
    "product": "∏",
    "radical": "√",
    "partialdiff": "∂",
    "lessequal": "≤",
    "greaterequal": "≥",
    "notequal": "≠",
    "element": "∈",
    "universal": "∀",
    "existential": "∃",
    "arrowright": "→",
    "multiply": "×",
    "periodcentered": "·",
    **{d: str(i) for i, d in enumerate("zero one two three four five six seven eight nine".split())},
}
GREEK = (
    "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi "
    "chi psi omega"
).split()
for _i, _g in enumerate(GREEK):
    GLYPHS[_g] = chr(0x3B1 + _i + (1 if _i >= 17 else 0))  # skips final sigma
    GLYPHS[_g.capitalize()] = chr(0x391 + _i + (1 if _i >= 17 else 0))


class Name(str):
    """A PDF name (/Type) as a string without the slash."""


@dataclass(frozen=True)
class Ref:
    num: int
    gen: int = 0


@dataclass(frozen=True)
class Op:
    """An operator in a content stream (Tj, BT, ...), or a keyword that isn't a value."""

    word: str


class PdfError(Exception):
    pass


# ----------------------------------------------------------------------------------------------- lexing
class Lexer:
    def __init__(self, data: bytes, pos: int = 0):
        self.data, self.pos = data, pos

    def skip(self) -> None:
        d, n = self.data, len(self.data)
        while self.pos < n:
            c = d[self.pos]
            if c in WS:
                self.pos += 1
            elif c == 0x25:  # % comment to the end of the line
                while self.pos < n and d[self.pos] not in b"\r\n":
                    self.pos += 1
            else:
                return

    def value(self, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise PdfError("nested too deep")
        self.skip()
        d = self.data
        if self.pos >= len(d):
            raise PdfError("end of data")
        c = d[self.pos : self.pos + 1]
        if d.startswith(b"<<", self.pos):
            self.pos += 2
            out: dict = {}
            while True:
                self.skip()
                if d.startswith(b">>", self.pos):
                    self.pos += 2
                    return out
                k = self.value(depth + 1)
                if not isinstance(k, Name):
                    raise PdfError("a dictionary key must be a name")
                out[str(k)] = self.value(depth + 1)
        if c == b"[":
            self.pos += 1
            arr = []
            while True:
                self.skip()
                if d.startswith(b"]", self.pos):
                    self.pos += 1
                    return arr
                arr.append(self.value(depth + 1))
        if c == b"(":
            return self._literal()
        if c == b"<":
            end = d.find(b">", self.pos)
            if end < 0:
                raise PdfError("unterminated hex string")
            hx = re.sub(rb"[^0-9A-Fa-f]", b"", d[self.pos + 1 : end])
            self.pos = end + 1
            return bytes.fromhex((hx + b"0" if len(hx) % 2 else hx).decode())
        if c == b"/":
            self.pos += 1
            start = self.pos
            while self.pos < len(d) and d[self.pos] not in WS and d[self.pos] not in DELIM:
                self.pos += 1
            raw = d[start : self.pos]
            raw = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m[1], 16)]), raw)
            return Name(raw.decode("latin-1"))
        m = re.compile(rb"[+-]?(\d+\.?\d*|\.\d+)").match(d, self.pos)
        if m:
            self.pos = m.end()
            tok = m.group()
            if b"." in tok:
                return float(tok)
            num = int(tok)
            ref = re.compile(rb"\s+(\d+)\s+R(?![^ \t\r\n\x0c\x00()<>\[\]{}/%])").match(d, self.pos)
            if ref and num >= 0:
                self.pos = ref.end()
                return Ref(num, int(ref[1]))
            return num
        start = self.pos
        while self.pos < len(d) and d[self.pos] not in WS and d[self.pos] not in DELIM:
            self.pos += 1
        if self.pos == start:  # a stray delimiter: step over it
            self.pos += 1
            return Op(d[start : self.pos].decode("latin-1"))
        word = d[start : self.pos].decode("latin-1")
        if word in KEYWORDS:
            return KEYWORDS[word]
        return Op(word)

    def _literal(self) -> bytes:
        d, out, depth = self.data, bytearray(), 0
        self.pos += 1
        esc = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
        while self.pos < len(d):
            c = d[self.pos]
            self.pos += 1
            if c == 0x5C:  # backslash
                if self.pos >= len(d):
                    break
                e = d[self.pos]
                self.pos += 1
                if e in esc:
                    out.append(esc[e])
                elif 0x30 <= e <= 0x37:
                    digits = bytes([e])
                    while len(digits) < 3 and self.pos < len(d) and 0x30 <= d[self.pos] <= 0x37:
                        digits += d[self.pos : self.pos + 1]
                        self.pos += 1
                    out.append(int(digits, 8) & 0xFF)
                elif e in b"\r\n":  # a line continuation
                    if e == 0x0D and d[self.pos : self.pos + 1] == b"\n":
                        self.pos += 1
                else:
                    out.append(e)
            elif c == 0x28:
                depth += 1
                out.append(c)
            elif c == 0x29:
                if depth == 0:
                    return bytes(out)
                depth -= 1
                out.append(c)
            else:
                out.append(c)
        return bytes(out)


def operations(content: bytes):
    """A content stream as (operator, operands) pairs; inline pictures (BI ... ID ... EI) are stepped over."""
    lx, args = Lexer(content), []
    while True:
        lx.skip()
        if lx.pos >= len(content):
            return
        try:
            v = lx.value()
        except PdfError:
            return
        if isinstance(v, Op):
            if v.word == "BI":  # inline image: its data runs from "ID " to "EI"
                i = content.find(b"ID", lx.pos)
                j = re.compile(rb"\sEI(?=[\s]|$)").search(content, i + 3 if i >= 0 else lx.pos)
                lx.pos = j.end() if j else len(content)
                yield "BI", []
                args = []
                continue
            yield v.word, args
            args = []
        else:
            args.append(v)


# --------------------------------------------------------------------------------------------- decoding
def _unpredict(data: bytes, parms: dict) -> bytes:
    pred = int(parms.get("Predictor", 1) or 1)
    if pred < 10:
        return data
    colors = int(parms.get("Colors", 1) or 1)
    bpc = int(parms.get("BitsPerComponent", 8) or 8)
    cols = int(parms.get("Columns", 1) or 1)
    bpp = max(1, colors * bpc // 8)
    row = (colors * bpc * cols + 7) // 8
    out, prev = bytearray(), bytearray(row)
    for i in range(0, len(data), row + 1):
        ft, line = data[i], bytearray(data[i + 1 : i + 1 + row])
        line += bytes(row - len(line))
        for x in range(row):
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], prev[x - bpp] if x >= bpp else 0
            if ft == 1:
                line[x] = (line[x] + a) & 0xFF
            elif ft == 2:
                line[x] = (line[x] + b) & 0xFF
            elif ft == 3:
                line[x] = (line[x] + (a + b) // 2) & 0xFF
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        out += line
        prev = line
    return bytes(out)


def _inflate(data: bytes) -> bytes:
    try:
        return zlib.decompress(data)
    except zlib.error:
        d = zlib.decompressobj()  # a damaged stream: keep what can be read
        try:
            return d.decompress(data)
        except zlib.error:
            return b""


def _a85(data: bytes) -> bytes:
    data = re.sub(rb"\s", b"", data)
    data = data.removeprefix(b"<~")
    end = data.find(b"~>")
    return base64.a85decode(data[: end if end >= 0 else len(data)])


# ------------------------------------------------------------------------------------------- the reader
@dataclass
class Font:
    cmap: dict[int, str] | None
    width: int  # bytes per character code
    encoding: str  # a Python codec for simple fonts
    diffs: dict[int, str]


class Pdf:
    """One PDF file, parsed on demand. Page numbers are 1-based, in reading order."""

    def __init__(self, path: Path | str | None = None, data: bytes | None = None):
        self.data = data if data is not None else Path(path).read_bytes()
        if not self.data.lstrip()[:5].startswith(b"%PDF"):
            raise PdfError("not a PDF")
        self.objs: dict[int, tuple[Any, tuple[int, int] | None, int]] = {}  # num -> (value, stream span, position)
        self._scan()
        self.trailer = self._trailer()
        self.encrypted = "Encrypt" in self.trailer
        self._pages: list[dict] | None = None
        self._page_of: dict[int, int] = {}
        self._fonts: dict[int, Font] = {}

    # ---------------------------------------------------------------------------------------- objects
    def _scan(self) -> None:
        d, stream_end = self.data, -1
        for m in OBJ.finditer(d):
            if m.start() < stream_end:  # digits inside a stream's data
                continue
            lx = Lexer(d, m.end())
            try:
                val = lx.value()
            except (PdfError, ValueError, IndexError):
                continue
            span = None
            lx.skip()
            if isinstance(val, dict) and d.startswith(b"stream", lx.pos):
                p = lx.pos + 6
                if d[p : p + 2] == b"\r\n":
                    p += 2
                elif d[p : p + 1] in (b"\n", b"\r"):
                    p += 1
                n = val.get("Length")
                if isinstance(n, int) and d[p + n : p + n + 40].lstrip(WS).startswith(b"endstream"):
                    end = p + n
                else:
                    end = d.find(b"endstream", p)
                    end = len(d) if end < 0 else end
                    while end > p and d[end - 1] in b"\r\n":
                        end -= 1
                span = (p, end)
                stream_end = end
            self.objs[int(m[1])] = (val, span, m.start())  # later ones (incremental updates) win
        for val, span, pos in list(self.objs.values()):  # objects packed in object streams
            if isinstance(val, dict) and val.get("Type") == "ObjStm" and span:
                self._unpack(val, span, pos)

    def _unpack(self, head: dict, span: tuple[int, int], pos: int) -> None:
        raw, _ = self.decode(head, span)
        if raw is None:
            return
        try:
            n, first = int(head.get("N", 0)), int(head.get("First", 0))
            nums = [int(x) for x in raw[:first].split()[: 2 * n]]
        except ValueError:
            return
        for i in range(0, len(nums) - 1, 2):
            num, off = nums[i], nums[i + 1]
            have = self.objs.get(num)
            if have and have[2] > pos:  # a later direct object replaces it
                continue
            try:
                self.objs[num] = (Lexer(raw, first + off).value(), None, pos)
            except (PdfError, ValueError, IndexError):
                continue

    def _trailer(self) -> dict:
        out: dict = {}
        for m in re.finditer(rb"trailer\s*<<", self.data):
            try:
                t = Lexer(self.data, m.end() - 2).value()
            except (PdfError, ValueError, IndexError):
                continue
            if isinstance(t, dict):
                out = {**out, **t}
        for val, _, _ in sorted(self.objs.values(), key=lambda o: o[2]):
            if isinstance(val, dict) and val.get("Type") == "XRef":
                out = {**out, **{k: v for k, v in val.items() if k in ("Root", "Encrypt", "Info")}}
        return out

    def get(self, v: Any, depth: int = 0) -> Any:
        while isinstance(v, Ref) and depth < MAX_DEPTH:
            o = self.objs.get(v.num)
            v = o[0] if o else None
            depth += 1
        return v

    def stream(self, ref: Any) -> tuple[bytes | None, str | None]:
        """A stream's data with its filters undone, up to a picture format (returned as the second value)."""
        if isinstance(ref, Ref):
            o = self.objs.get(ref.num)
            if not o or not o[1]:
                return None, None
            return self.decode(o[0], o[1])
        return None, None

    def decode(self, head: dict, span: tuple[int, int]) -> tuple[bytes | None, str | None]:
        raw = self.data[span[0] : span[1]]
        filters = self.get(head.get("Filter"))
        parms = self.get(head.get("DecodeParms"))
        filters = filters if isinstance(filters, list) else [filters] if filters else []
        parms = parms if isinstance(parms, list) else [parms] * len(filters)
        for f, p in zip([str(self.get(x)) for x in filters], parms, strict=False):
            p = self.get(p) if isinstance(self.get(p), dict) else {}
            if f in ("FlateDecode", "Fl"):
                raw = _unpredict(_inflate(raw), p)
            elif f in ("ASCIIHexDecode", "AHx"):
                hx = re.sub(rb"[^0-9A-Fa-f]", b"", raw.split(b">")[0])
                raw = bytes.fromhex((hx + b"0" if len(hx) % 2 else hx).decode())
            elif f in ("ASCII85Decode", "A85"):
                try:
                    raw = _a85(raw)
                except ValueError:
                    return None, None
            elif f in IMAGE_FILTERS:
                return raw, f
            else:  # LZW, run length, crypt: not handled here
                return None, None
        return raw, None

    # ------------------------------------------------------------------------------------------ pages
    def pages(self) -> list[dict]:
        if self._pages is not None:
            return self._pages
        out: list[dict] = []
        root = self.get(self.trailer.get("Root"))
        top = self.get(root.get("Pages")) if isinstance(root, dict) else None
        seen: set[int] = set()

        def walk(node_ref: Any, inherit: dict, depth: int) -> None:
            node = self.get(node_ref)
            if not isinstance(node, dict) or depth > MAX_DEPTH:
                return
            if isinstance(node_ref, Ref):
                if node_ref.num in seen:
                    return
                seen.add(node_ref.num)
            here = {**inherit, **{k: node[k] for k in ("Resources", "MediaBox", "Rotate") if k in node}}
            kids = self.get(node.get("Kids"))
            if node.get("Type") == "Pages" or (isinstance(kids, list) and node.get("Type") != "Page"):
                for k in kids or []:
                    walk(k, here, depth + 1)
            else:
                if isinstance(node_ref, Ref):
                    self._page_of[node_ref.num] = len(out) + 1
                out.append({**here, **node})

        if isinstance(top, dict):
            walk(root.get("Pages"), {}, 0)
        if not out:  # no usable page tree: every page object, in file order
            for num, (val, _, _) in sorted(self.objs.items(), key=lambda kv: kv[1][2]):
                if isinstance(val, dict) and val.get("Type") == "Page":
                    self._page_of[num] = len(out) + 1
                    out.append(val)
        self._pages = out
        return out

    def page_count(self) -> int:
        return len(self.pages())

    def _page(self, n: int) -> dict:
        ps = self.pages()
        if not 1 <= n <= len(ps):
            raise PdfError(f"no page {n}")
        return ps[n - 1]

    def content(self, holder: dict) -> bytes:
        parts = self.get(holder.get("Contents"))
        refs = parts if isinstance(parts, list) else [holder.get("Contents")]
        out = []
        for r in refs:
            data, _ = self.stream(r)
            if data:
                out.append(data)
        return b"\n".join(out)

    def _resources(self, holder: dict, kind: str) -> dict:
        res = self.get(holder.get("Resources"))
        d = self.get(res.get(kind)) if isinstance(res, dict) else None
        return d if isinstance(d, dict) else {}

    # ------------------------------------------------------------------------------------------- text
    def _font(self, ref: Any) -> Font:
        key = ref.num if isinstance(ref, Ref) else id(ref)
        if key in self._fonts:
            return self._fonts[key]
        f = self.get(ref)
        f = f if isinstance(f, dict) else {}
        two = f.get("Subtype") == "Type0"  # composite fonts use 2-byte codes (their map says)
        cmap, width = None, 2 if two else 1
        tu = f.get("ToUnicode")
        if isinstance(tu, Ref):
            data, _ = self.stream(tu)
            if data:
                cmap, cw = parse_cmap(data)
                width = cw if two else 1
        enc = self.get(f.get("Encoding"))
        diffs: dict[int, str] = {}
        codec = "latin-1"
        base = enc.get("BaseEncoding") if isinstance(enc, dict) else enc
        if base == "WinAnsiEncoding":
            codec = "cp1252"
        elif base == "MacRomanEncoding":
            codec = "mac_roman"
        if isinstance(enc, dict):
            code = 0
            for item in self.get(enc.get("Differences")) or []:
                if isinstance(item, int):
                    code = item
                elif isinstance(item, Name):
                    g = _glyph(str(item))
                    if g is not None:
                        diffs[code] = g
                    code += 1
        font = Font(cmap, width, codec, diffs)
        self._fonts[key] = font
        return font

    def _show(self, font: Font | None, s: bytes) -> str:
        if font is None:
            return s.decode("latin-1")
        if font.cmap:
            out, w = [], font.width
            for i in range(0, len(s) - w + 1, w):
                out.append(font.cmap.get(int.from_bytes(s[i : i + w], "big"), "�"))
            return "".join(out)
        if font.width == 2:  # a composite font with no map to Unicode: can't be read reliably
            return "�" * (len(s) // 2)
        return "".join(font.diffs.get(b) or bytes([b]).decode(font.encoding, errors="replace") for b in s)

    def page_text(self, n: int) -> str:
        """The page's text layer as plain text ("" if it has none)."""
        return self._text(self._page(n), 0).strip()

    def _text(self, holder: dict, depth: int, stream: bytes | None = None) -> str:
        if depth > 3:
            return ""
        fonts = self._resources(holder, "Font")
        xobjs = self._resources(holder, "XObject")
        out: list[str] = []
        font, y = None, None
        for op, args in operations(self.content(holder) if stream is None else stream):
            if op == "Tf" and args:
                font = self._font(fonts.get(str(args[0]))) if str(args[0]) in fonts else None
            elif op in ("Td", "TD") and len(args) >= 2:
                if isinstance(args[1], (int, float)) and abs(args[1]) > 0.5:
                    out.append("\n")
                elif isinstance(args[0], (int, float)) and args[0] > 0 and out and not out[-1].endswith((" ", "\n")):
                    out.append(" ")
            elif op == "Tm" and len(args) >= 6:
                ny = args[5] if isinstance(args[5], (int, float)) else None
                if y is not None and ny is not None and abs(ny - y) > 0.5:
                    out.append("\n")
                y = ny
            elif op in ("T*", "'", '"', "ET"):
                if op != "ET" or (out and not out[-1].endswith("\n")):
                    out.append("\n")
                if op in ("'", '"') and args and isinstance(args[-1], bytes):
                    out.append(self._show(font, args[-1]))
            elif op == "Tj" and args and isinstance(args[0], bytes):
                out.append(self._show(font, args[0]))
            elif op == "TJ" and args and isinstance(args[0], list):
                for item in args[0]:
                    if isinstance(item, bytes):
                        out.append(self._show(font, item))
                    elif isinstance(item, (int, float)) and item < -180:
                        out.append(" ")
            elif op == "Do" and args:
                x = self.get(xobjs.get(str(args[0])))
                if isinstance(x, dict) and x.get("Subtype") == "Form":
                    ref = xobjs.get(str(args[0]))
                    data, _ = self.stream(ref)
                    if data:
                        sub = {"Resources": x.get("Resources") or holder.get("Resources")}
                        out.append(self._text(sub, depth + 1, data))
        text = "".join(out)
        return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", text))

    # --------------------------------------------------------------------------------------- pictures
    def _images(self, holder: dict, depth: int = 0) -> list[tuple[Any, dict]]:
        out = []
        for ref in self._resources(holder, "XObject").values():
            x = self.get(ref)
            if not isinstance(x, dict):
                continue
            if x.get("Subtype") == "Image":
                out.append((ref, x))
            elif x.get("Subtype") == "Form" and depth < 2:
                out += self._images({"Resources": x.get("Resources")}, depth + 1)
        return out

    def has_images(self, n: int) -> bool:
        page = self._page(n)
        if self._images(page):
            return True
        return any(op == "BI" for op, _ in operations(self.content(page)))

    def page_image(self, n: int) -> tuple[bytes, str] | None:
        """The biggest picture on the page (a scanned page is one picture), as JPEG, PNG or TIFF bytes and its type;
        None if there's none this reader can hand over."""
        imgs = self._images(self._page(n))
        if not imgs:
            return None
        ref, x = max(imgs, key=lambda i: _num(self.get(i[1].get("Width"))) * _num(self.get(i[1].get("Height"))))
        data, kind = self.stream(ref)
        if data is None:
            return None
        w, h = _num(self.get(x.get("Width"))), _num(self.get(x.get("Height")))
        if kind in ("DCTDecode", "DCT"):
            return data, "image/jpeg"
        if kind in ("CCITTFaxDecode", "CCF"):
            p = self.get(x.get("DecodeParms"))
            p = self.get(p[-1]) if isinstance(p, list) and p else p
            return ccitt_tiff(data, w, h, p if isinstance(p, dict) else {}), "image/tiff"
        if kind is not None:
            return None
        bpc = _num(self.get(x.get("BitsPerComponent"))) or 8
        if x.get("ImageMask"):
            bpc, comps = 1, 1
        else:
            comps = self._components(self.get(x.get("ColorSpace")))
        if not comps or bpc not in (1, 8) or (bpc == 1 and comps != 1):
            return None
        return png(data, w, h, bpc, comps), "image/png"

    def _components(self, cs: Any) -> int | None:
        if isinstance(cs, Name):
            return {"DeviceGray": 1, "CalGray": 1, "G": 1, "DeviceRGB": 3, "CalRGB": 3, "RGB": 3}.get(str(cs))
        if isinstance(cs, list) and cs:
            kind = str(self.get(cs[0]))
            if kind == "ICCBased" and len(cs) > 1:
                d = self.get(cs[1])
                n = _num(self.get(d.get("N"))) if isinstance(d, dict) else 0
                return n if n in (1, 3) else None
            if kind in ("CalGray", "CalRGB"):
                return 1 if kind == "CalGray" else 3
        return None

    # ---------------------------------------------------------------------------------------- outline
    def outline(self, limit: int = 2000) -> list[tuple[int, str, int | None]]:
        """The bookmarks: (level, title, page or None), in order."""
        self.pages()
        root = self.get(self.trailer.get("Root"))
        if not isinstance(root, dict):
            return []
        top = self.get(root.get("Outlines"))
        if not isinstance(top, dict):
            return []
        names = self._named_dests(root)
        out: list[tuple[int, str, int | None]] = []
        seen: set[int] = set()

        def walk(ref: Any, level: int) -> None:
            while isinstance(ref, Ref) and ref.num not in seen and len(out) < limit and level < 12:
                seen.add(ref.num)
                item = self.get(ref)
                if not isinstance(item, dict):
                    return
                title = text_string(self.get(item.get("Title")))
                dest = self.get(item.get("Dest"))
                action = self.get(item.get("A"))
                if dest is None and isinstance(action, dict) and action.get("S") == "GoTo":
                    dest = self.get(action.get("D"))
                if isinstance(dest, (bytes, Name)):
                    dest = self.get(names.get(dest.decode("latin-1") if isinstance(dest, bytes) else str(dest)))
                if isinstance(dest, dict):
                    dest = self.get(dest.get("D"))
                page = None
                if isinstance(dest, list) and dest:
                    if isinstance(dest[0], Ref):
                        page = self._page_of.get(dest[0].num)
                    elif isinstance(dest[0], int):
                        page = dest[0] + 1
                if title.strip():
                    out.append((level, re.sub(r"\s+", " ", title).strip(), page))
                walk(item.get("First"), level + 1)
                ref = item.get("Next")

        walk(top.get("First"), 1)
        return out

    def _named_dests(self, root: dict) -> dict[str, Any]:
        out: dict[str, Any] = {}
        old = self.get(root.get("Dests"))
        if isinstance(old, dict):
            out.update(old)
        names = self.get(root.get("Names"))
        tree = self.get(names.get("Dests")) if isinstance(names, dict) else None
        stack, n = [tree], 0
        while stack and n < 5000:
            node = self.get(stack.pop())
            n += 1
            if not isinstance(node, dict):
                continue
            arr = self.get(node.get("Names")) or []
            for i in range(0, len(arr) - 1, 2):
                k = self.get(arr[i])
                out[k.decode("latin-1") if isinstance(k, bytes) else str(k)] = arr[i + 1]
            stack += list(self.get(node.get("Kids")) or [])
        return out


# ----------------------------------------------------------------------------------------------- helpers
def _num(v: Any) -> int:
    return int(v) if isinstance(v, (int, float)) else 0


def _glyph(name: str) -> str | None:
    if name in GLYPHS:
        return GLYPHS[name]
    if len(name) == 1:
        return name
    m = re.fullmatch(r"uni([0-9A-Fa-f]{4})", name)
    if m:
        return chr(int(m[1], 16))
    return None


def _utf16(b: bytes) -> str:
    return b.decode("utf-16-be", errors="replace") if len(b) % 2 == 0 else b.decode("latin-1")


def parse_cmap(data: bytes) -> tuple[dict[int, str], int]:
    """A ToUnicode map: character code -> text, and the code width in bytes."""
    out: dict[int, str] = {}
    width = 1
    for block in re.findall(rb"begincodespacerange(.*?)endcodespacerange", data, re.S):
        hx = re.findall(rb"<([0-9A-Fa-f]+)>", block)
        if hx:
            width = max(width, max(len(h) // 2 for h in hx))
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            out[int(src, 16)] = _utf16(bytes.fromhex(dst.decode()))
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, rest in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)", block):
            a, b = int(lo, 16), int(hi, 16)
            if b - a > 65535:
                continue
            if rest.startswith(b"["):
                for i, dst in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", rest)):
                    out[a + i] = _utf16(bytes.fromhex(dst.decode()))
            else:
                base = bytes.fromhex(rest[1:-1].decode())
                if not base:
                    continue
                head, last = base[:-2], int.from_bytes(base[-2:], "big") if len(base) >= 2 else base[-1]
                for i in range(b - a + 1):
                    out[a + i] = _utf16(head + (last + i).to_bytes(2, "big")) if len(base) >= 2 else chr(last + i)
    return out, width


def text_string(v: Any) -> str:
    """A PDF text string (bookmark titles): UTF-16 with a byte-order mark, else PDFDocEncoding (about Latin-1)."""
    if isinstance(v, bytes):
        if v.startswith(b"\xfe\xff"):
            return v[2:].decode("utf-16-be", errors="replace")
        if v.startswith(b"\xef\xbb\xbf"):
            return v[3:].decode("utf-8", errors="replace")
        return v.decode("latin-1")
    return str(v or "")


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def png(pixels: bytes, w: int, h: int, bpc: int = 8, comps: int = 1) -> bytes:
    """Raw pixel rows (gray or RGB, 1 or 8 bits) as a PNG file."""
    row = (w * comps * bpc + 7) // 8
    rows = b"".join(b"\x00" + pixels[i * row : (i + 1) * row].ljust(row, b"\xff") for i in range(h))
    ctype = 0 if comps == 1 else 2
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, bpc, ctype, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(rows, 6))
        + _chunk(b"IEND", b"")
    )


def ccitt_tiff(data: bytes, w: int, h: int, parms: dict) -> bytes:
    """CCITT fax data (how many scanned black-and-white pages are stored) wrapped as a TIFF file OCR can open."""
    k = parms.get("K", 0) if isinstance(parms.get("K", 0), int) else 0
    w = int(parms.get("Columns", w) or w)
    h = int(parms.get("Rows", h) or h) or h
    comp = 4 if k < 0 else 3
    photometric = 1 if parms.get("BlackIs1") else 0
    tags = [
        (256, 4, w),  # width
        (257, 4, h),  # height
        (258, 3, 1),  # bits per sample
        (259, 3, comp),  # compression: 3 = fax group 3, 4 = group 4
        (262, 3, photometric),
        (273, 4, 0),  # where the data starts (filled in below)
        (277, 3, 1),  # samples per pixel
        (278, 4, h),  # rows per strip
        (279, 4, len(data)),  # strip byte count
    ]
    if comp == 3:
        tags.append((292, 4, 0))
    tags.sort()
    ifd_len = 2 + 12 * len(tags) + 4
    start = 8 + ifd_len
    body = struct.pack("<H", len(tags))
    for tag, typ, val in tags:
        val = start if tag == 273 else val
        body += struct.pack("<HHI", tag, typ, 1) + (struct.pack("<HH", val, 0) if typ == 3 else struct.pack("<I", val))
    return b"II*\x00" + struct.pack("<I", 8) + body + b"\x00\x00\x00\x00" + data
