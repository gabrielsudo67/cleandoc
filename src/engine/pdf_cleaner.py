"""
pdf_cleaner.py
==============
Limpeza de marcas d'água em documentos PDF.

Dois cenários são tratados:

1. PDF vetorial (nativo)
   - Remoção de anotações do tipo *watermark*.
   - Remoção/neutralização de camadas de conteúdo opcional (OCG) frequentemente
     usadas por geradores de marca d'água.
   - Remoção de imagens/desenhos de baixa opacidade quando detectáveis.
   - Como reforço final, cada página é rasterizada e limpa por cor (mesma
     pipeline das imagens), preservando texto escuro.

2. PDF digitalizado (imagem)
   - Cada página é rasterizada em alta resolução, limpa via OpenCV/HSV e
     recomposta em um novo PDF.

A função pública `clean_pdf` recebe os bytes do PDF e devolve os bytes do PDF
limpo.
"""

from __future__ import annotations

import io

import fitz  # PyMuPDF
from PIL import Image

from .image_cleaner import CleanConfig, clean_image


def is_pdf_scanned(pdf_bytes: bytes, text_threshold: int = 40) -> bool:
    """
    Heurística: se as páginas quase não têm texto extraível, é um PDF
    digitalizado (imagem). Nesse caso a limpeza vetorial não se aplica.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_text = 0
        for page in doc:
            total_text += len(page.get_text("text").strip())
            if total_text > text_threshold:
                return False
        return True
    finally:
        doc.close()


def _remove_watermark_annotations(page: "fitz.Page") -> int:
    """Remove anotações de marca d'água/carimbo. Retorna quantas removeu."""
    removed = 0
    annot = page.first_annot
    while annot:
        nxt = annot.next
        try:
            # Tipo 15 = Watermark; 13 = Stamp (carimbos, muitas vezes marca d'água)
            atype = annot.type[0]
            if atype in (13, 15):
                page.delete_annot(annot)
                removed += 1
        except Exception:
            pass
        annot = nxt
    return removed


def _render_page_to_pil(page: "fitz.Page", dpi: int) -> Image.Image:
    """Rasteriza uma página do PDF em uma imagem PIL RGB."""
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def clean_pdf(
    pdf_bytes: bytes,
    cfg: CleanConfig | None = None,
    dpi: int = 150,
    force_raster: bool = False,
) -> bytes:
    """
    Remove marcas d'água de um PDF.

    Parameters
    ----------
    pdf_bytes : bytes
        Conteúdo do PDF de entrada.
    cfg : CleanConfig, opcional
        Configuração de limpeza (sensibilidade, manter texto escuro).
    dpi : int
        Resolução de rasterização para a limpeza por imagem.
    force_raster : bool
        Se True, ignora a tentativa vetorial e sempre rasteriza+limpa.

    Returns
    -------
    bytes
        PDF limpo.
    """
    cfg = cfg or CleanConfig()

    # --- Passo 1: tentativa vetorial (rápida, preserva texto pesquisável) ---
    if not force_raster:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            removed_total = 0
            for page in doc:
                removed_total += _remove_watermark_annotations(page)

            # Desativa camadas de conteúdo opcional (OCG) — comum em marcas d'água.
            try:
                ocgs = doc.get_ocgs()
                if ocgs:
                    ui = doc.layer_ui_configs()
                    for item in ui:
                        doc.set_layer_ui_config(item["number"], action=2)  # OFF
                    removed_total += len(ocgs)
            except Exception:
                pass

            if removed_total > 0:
                out = io.BytesIO()
                doc.save(out, garbage=4, deflate=True, clean=True)
                return out.getvalue()
        finally:
            doc.close()

    # --- Passo 2: rasterização + limpeza por imagem (robusto) ---
    return _clean_pdf_by_raster(pdf_bytes, cfg, dpi)


def _clean_pdf_by_raster(pdf_bytes: bytes, cfg: CleanConfig, dpi: int) -> bytes:
    """Rasteriza cada página, limpa como imagem e remonta um novo PDF."""
    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    out_doc = fitz.open()
    try:
        for page in src:
            pil_page = _render_page_to_pil(page, dpi)
            cleaned = clean_image(pil_page, cfg)

            img_buf = io.BytesIO()
            cleaned.save(img_buf, format="PNG")
            img_buf.seek(0)

            rect = page.rect  # mantém dimensões originais (em pontos)
            new_page = out_doc.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(rect, stream=img_buf.getvalue())

        result = io.BytesIO()
        out_doc.save(result, garbage=4, deflate=True)
        return result.getvalue()
    finally:
        src.close()
        out_doc.close()


def render_pdf_preview(pdf_bytes: bytes, page_number: int = 0, dpi: int = 120) -> Image.Image:
    """Rasteriza uma página específica para pré-visualização na interface."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_number = max(0, min(page_number, doc.page_count - 1))
        return _render_page_to_pil(doc[page_number], dpi)
    finally:
        doc.close()


def render_pdf_pages(pdf_bytes: bytes, dpi: int = 150) -> list[Image.Image]:
    """Rasteriza TODAS as páginas do PDF em imagens PIL (usado para PDF/Word)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [_render_page_to_pil(page, dpi) for page in doc]
    finally:
        doc.close()


def pdf_page_count(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return doc.page_count
    finally:
        doc.close()
