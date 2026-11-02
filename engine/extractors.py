"""Document discovery and text extraction backends."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath

from .constants import DEFAULT_EXCLUDE_NAMES, DEFAULT_EXCLUDE_PARTS, SUPPORTED_EXTENSIONS

PDF_TEXT_ORDERS = ("auto", "raw")


@dataclass(slots=True)
class Extraction:
    text: str
    backend: str
    warnings: list[str]
    ocr_used: bool = False


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_encoding_warnings(text: str) -> list[str]:
    """Flag uncertain glyph runs, without guessing font codes or altering text.

    Normal newlines, tabs and page breaks are not damaged letters. An embedded
    form feed between Latin letters is ambiguous and merits source inspection.
    Mathematics can also trigger this conservative signal; it is not a diagnosis
    of a corrupted document or a complete font-quality assessment.
    """
    bad = r"[\x00-\x08\x0b\x0e-\x1f\x7f-\x9f\ufffd]"
    runs = list(re.finditer(rf"(?<=[A-Za-z]){bad}+|{bad}+(?=[A-Za-z])|(?<=[A-Za-z])\x0c(?=[A-Za-z])", text))
    if not runs:
        return []
    return [f"Extracted text has {len(runs)} uncertain control/replacement glyph run(s) adjacent to Latin letters; inspect source pages and font mapping before linguistic or copying conclusions. No letters were inferred."]


def discover_papers(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {root}")
    papers = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            continue
        if path.name.casefold() in DEFAULT_EXCLUDE_NAMES:
            continue
        relative_parts = {part.casefold() for part in path.relative_to(root).parts[:-1]}
        if relative_parts & DEFAULT_EXCLUDE_PARTS:
            continue
        papers.append(path)
    return sorted(papers, key=lambda item: item.as_posix().casefold())


def normalize_pdf_order_review(value: dict) -> dict:
    """Validate a source-hashed extraction choice, not a semantic observation."""
    if not isinstance(value, dict):
        raise ValueError("A PDF text-order review must be an object")
    source = value.get("source")
    if not isinstance(source, str) or not source or "\\" in source:
        raise ValueError("PDF text-order source must be a relative POSIX PDF path")
    name = PurePosixPath(source)
    if not name.parts or name.is_absolute() or ".." in name.parts or ":" in name.parts[0] or name.suffix.casefold() != ".pdf":
        raise ValueError("PDF text-order source must stay inside the paper corpus")
    digest = value.get("source_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise ValueError("PDF text-order review needs the source content hash")
    if value.get("pdf_text_order") not in PDF_TEXT_ORDERS:
        raise ValueError("PDF text order must be auto or raw")
    if (value.get("reviewer_kind") not in ("agent", "human")
            or not isinstance(value.get("reviewer"), str) or not value["reviewer"].strip()
            or value.get("review_status") != "complete"
            or not isinstance(value.get("rationale"), str) or len(value["rationale"].strip()) < 20):
        raise ValueError("PDF text-order choice needs an identified reviewer and source-based rationale")
    return {**value, "source_sha256": digest.lower()}


def load_pdf_order_map(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("documents"), list):
        raise ValueError("Unsupported PDF text-order map schema")
    result = {}
    for value in data["documents"]:
        row = normalize_pdf_order_review(value)
        if row["source"] in result:
            raise ValueError("PDF text-order sources must be unique")
        result[row["source"]] = row
    return result


def compare_pdf_text(path: Path, workspace: Path) -> dict:
    """Write private, hash-bound candidates without changing profile state."""
    path = path.resolve()
    if path.suffix.casefold() != ".pdf" or not path.is_file():
        raise ValueError("PDF text comparison needs an existing PDF file")
    source_hash = file_sha256(path)
    directory = workspace.resolve() / ".paper-alchemist" / "extraction-reviews" / source_hash
    candidates, contents = [], []
    for order in ("auto", "raw"):
        extraction = extract_text(path, ocr_mode="never", pdf_text_order=order)
        data = extraction.text.encode("utf-8")
        text_hash = sha256(data).hexdigest()
        target = directory / f"{order}-{text_hash}.txt"
        candidates.append({"pdf_text_order": order, "backend": extraction.backend,
                           "characters": len(extraction.text), "text_path": str(target),
                           "text_sha256": text_hash,
                           "canonical_text_sha256": sha256(extraction.text.replace("\x00", "").strip().encode()).hexdigest(),
                           "warnings": extraction.warnings, "ocr_used": extraction.ocr_used})
        contents.append((target, data))
    if file_sha256(path) != source_hash:
        raise ValueError("PDF source changed during text-order comparison; inspect it again")
    directory.mkdir(parents=True, exist_ok=True)
    for target, data in contents:
        if target.exists() and target.read_bytes() != data:
            raise ValueError("Existing PDF comparison candidate differs from its content hash")
        if not target.exists():
            target.write_bytes(data)
    body = {"schema_version": 1, "source_sha256": source_hash, "candidates": candidates,
            "semantic_review_performed": False, "diagnostic_only": True,
            "notice": "Compare candidates against original PDF pages; this command does not select an order, review paper sections or distill a profile."}
    key = sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    receipt = directory / f"comparison-{key}.json"
    if receipt.exists():
        report = json.loads(receipt.read_text(encoding="utf-8"))
        if {k: v for k, v in report.items() if k != "created_at"} != body:
            raise ValueError("Existing PDF comparison receipt differs from its candidates")
    else:
        report = {**body, "created_at": datetime.now(timezone.utc).isoformat()}
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**report, "source": str(path), "receipt": str(receipt)}


def extract_text(path: Path, ocr_mode: str = "auto", pdf_text_order: str = "auto") -> Extraction:
    if ocr_mode not in {"auto", "never", "always"}:
        raise ValueError("ocr_mode must be auto, never, or always")
    suffix = path.suffix.casefold()
    if pdf_text_order not in PDF_TEXT_ORDERS or (suffix != ".pdf" and pdf_text_order != "auto"):
        raise ValueError("PDF text order must be auto or raw and applies only to PDF files")
    if suffix == ".pdf":
        return _extract_pdf(path, ocr_mode, pdf_text_order)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".tex":
        return Extraction(_extract_tex(path), "latex", [])
    if suffix in {".md", ".txt"}:
        return Extraction(path.read_text(encoding="utf-8", errors="replace"), "text", [])
    raise ValueError(f"Unsupported paper format: {path.suffix}")


def _extract_pdf(path: Path, ocr_mode: str, pdf_text_order: str = "auto") -> Extraction:
    warnings: list[str] = []
    text = ""
    backend = "none"
    executable = shutil.which("pdftotext")
    if pdf_text_order == "raw" and not executable:
        raise ValueError("Content-stream PDF order requires pdftotext; no other order was substituted")
    if executable:
        try:
            completed = subprocess.run(
                # Reading order keeps columns separate. Layout mode interleaves
                # side-by-side prose, corrupting rhetoric and sentence statistics.
                [executable, *(["-raw"] if pdf_text_order == "raw" else []), "-enc", "UTF-8", str(path), "-"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                text = completed.stdout
                backend = "pdftotext-raw" if pdf_text_order == "raw" else "pdftotext"
                # INFORMS manuscript templates have a legal sidebar beside
                # the abstract. Content stream order separates those blocks.
                compact = re.sub(r"\s+", "", text[:25000]).casefold()
                if pdf_text_order == "auto" and "authorsareencouragedtosubmitnew" in compact and "informs" in compact:
                    raw = subprocess.run(
                        [executable, "-raw", "-enc", "UTF-8", str(path), "-"],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=180, check=False,
                    )
                    if raw.returncode == 0 and raw.stdout.strip():
                        text = raw.stdout
                        backend = "pdftotext-raw-template"
                        warnings.append("INFORMS sidebar detected; used content-stream extraction to keep it outside prose")
                    else:
                        warnings.append("Could not recover INFORMS sidebar reading order")
            else:
                if pdf_text_order == "raw":
                    raise ValueError(f"pdftotext content-stream extraction failed with exit code {completed.returncode} or empty text")
                warnings.append(f"pdftotext failed with exit code {completed.returncode}")
        except subprocess.TimeoutExpired:
            if pdf_text_order == "raw":
                raise ValueError("pdftotext content-stream extraction timed out; no other order was substituted") from None
            warnings.append("pdftotext timed out after 180 seconds")
    if not text.strip():
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
            backend = "pypdf"
        except Exception as exc:  # pragma: no cover - backend-specific failures
            warnings.append(f"pypdf failed: {exc}")

    if _should_ocr(text, ocr_mode):
        ocr_text, ocr_warnings = _ocr_pdf(path)
        warnings.extend(ocr_warnings)
        if ocr_text.strip() and len(ocr_text) > len(text):
            return Extraction(ocr_text, f"{backend}+tesseract", warnings + text_encoding_warnings(ocr_text), ocr_used=True)
    return Extraction(text, backend, warnings + text_encoding_warnings(text))


def _should_ocr(text: str, ocr_mode: str) -> bool:
    if ocr_mode == "always":
        return True
    if ocr_mode == "never":
        return False
    return len(text.strip()) < 800


def _ocr_pdf(path: Path) -> tuple[str, list[str]]:
    renderer = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    missing = [
        name for name, value in (("pdftoppm", renderer), ("tesseract", tesseract)) if not value
    ]
    if missing:
        return "", [f"OCR unavailable; missing tool(s): {', '.join(missing)}"]

    warnings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="paper-alchemist-ocr-") as temporary:
        temporary_path = Path(temporary)
        prefix = temporary_path / "page"
        try:
            rendered = subprocess.run(
                [renderer, "-jpeg", "-r", "200", str(path), str(prefix)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "", ["pdftoppm OCR rendering timed out after 600 seconds"]
        if rendered.returncode != 0:
            return "", [f"pdftoppm OCR rendering failed with exit code {rendered.returncode}"]
        images = sorted(temporary_path.glob("page-*.jpg"))
        if not images:
            return "", ["pdftoppm produced no OCR page images"]
        language = _tesseract_language(tesseract)
        pages: list[str] = []
        for page_number, image in enumerate(images, start=1):
            try:
                completed = subprocess.run(
                    [tesseract, str(image), "stdout", "-l", language, "--psm", "3"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                warnings.append(f"tesseract timed out on page {page_number}")
                continue
            if completed.returncode == 0:
                pages.append(completed.stdout)
            else:
                warnings.append(
                    f"tesseract failed on page {page_number} with exit code {completed.returncode}"
                )
        return "\n\n".join(pages), warnings


def _tesseract_language(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--list-langs"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    available = {
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip() and "available languages" not in line.casefold()
    }
    preferred = [language for language in ("eng", "chi_sim") if language in available]
    if preferred:
        return "+".join(preferred)
    return sorted(available)[0] if available else "eng"


def _extract_docx(path: Path) -> Extraction:
    from docx import Document

    document = Document(str(path))
    lines = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            lines.append("")
            continue
        style = paragraph.style.name.casefold() if paragraph.style else ""
        if style.startswith("heading"):
            lines.append(f"# {text}")
        else:
            lines.append(text)
    return Extraction("\n".join(lines), "python-docx", [])


def _extract_tex(path: Path) -> str:
    source = path.read_text(encoding="utf-8", errors="replace")
    source = re.sub(r"(?<!\\)%.*", "", source)
    source = re.sub(r"\\begin\{abstract\}", "\n# Abstract\n", source)
    source = re.sub(r"\\end\{abstract\}", "\n", source)
    source = re.sub(
        r"\\(?:section|section\*|subsection|subsubsection)\{([^{}]+)\}",
        lambda match: f"\n# {match.group(1)}\n",
        source,
    )
    source = re.sub(r"\\(?:label|ref|eqref|url|footnote)\{[^{}]*\}", " ", source)
    source = re.sub(r"\\cite\w*\{([^{}]+)\}", lambda match: f"\\cite{{{match.group(1)}}}", source)
    source = re.sub(
        r"\\begin\{(?:figure|table|equation\*?|align\*?)\}.*?\\end\{[^{}]+\}",
        " ",
        source,
        flags=re.S,
    )
    source = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", source)
    source = source.replace("~", " ").replace("{", "").replace("}", "")
    source = re.sub(r"[ \t]+", " ", source)
    source = re.sub(r"\n{3,}", "\n\n", source)
    return source.strip()
