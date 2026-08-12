"""
exporters.py — Geração dos arquivos de saída em diferentes formatos.

Suporta: PNG, JPG, PDF e Word (DOCX).

A ideia central: qualquer resultado limpo é representado como uma lista de
imagens de páginas (`list[PIL.Image]`). A partir dela montamos o formato pedido.
Para PDFs de entrada vetoriais, o chamador pode preferir passar os bytes do PDF
já limpo (que preservam texto pesquisável) diretamente ao usuário.
"""

from __future__ import annotations

import io

from docx import Document
from docx.shared import Inches
from PIL import Image

# MIME types úteis para os botões de download do Streamlit.
MIME = {
    "PNG": "image/png",
    "JPG": "image/jpeg",
    "PDF": "application/pdf",
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def image_to_bytes(img: Image.Image, fmt: str, quality: int = 92) -> bytes:
    """Serializa uma única imagem para PNG ou JPG."""
    buf = io.BytesIO()
    if fmt.upper() == "JPG":
        img.convert("RGB").save(buf, format="JPEG", quality=quality)
    else:
        img.save(buf, format="PNG")
    return buf.getvalue()


def images_to_pdf_bytes(images: list[Image.Image]) -> bytes:
    """Monta um PDF (multipágina) a partir de uma lista de imagens."""
    rgb = [im.convert("RGB") for im in images]
    buf = io.BytesIO()
    rgb[0].save(buf, format="PDF", save_all=True, append_images=rgb[1:])
    return buf.getvalue()


def images_to_docx_bytes(images: list[Image.Image], page_width_in: float = 6.3) -> bytes:
    """
    Monta um documento Word (.docx) inserindo cada imagem de página em uma
    página do documento. As páginas são incorporadas como figuras.
    """
    doc = Document()

    # Margens enxutas para a imagem ocupar bem a página.
    for section in doc.sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)

    for i, im in enumerate(images):
        rgb = im.convert("RGB")
        img_buf = io.BytesIO()
        rgb.save(img_buf, format="PNG")
        img_buf.seek(0)
        doc.add_picture(img_buf, width=Inches(page_width_in))
        if i < len(images) - 1:
            doc.add_page_break()

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def images_to_zip_bytes(images: list[Image.Image], fmt: str, quality: int = 92) -> bytes:
    """Empacota várias páginas como imagens (PNG/JPG) dentro de um .zip."""
    import zipfile

    ext = "jpg" if fmt.upper() == "JPG" else "png"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, im in enumerate(images, start=1):
            zf.writestr(f"pagina_{i:02d}.{ext}", image_to_bytes(im, fmt, quality))
    return buf.getvalue()


def build_output(
    out_format: str,
    cleaned_images: list[Image.Image],
    *,
    is_pdf_input: bool,
    cleaned_pdf_bytes: bytes | None = None,
    stem: str = "documento",
    jpg_quality: int = 92,
    multipage_image_fallback: str = "pdf",  # "pdf" (premium) ou "zip" (grátis)
) -> tuple[str, bytes, str, str | None]:
    """
    Constrói o arquivo de saída no formato pedido.

    Returns
    -------
    (nome_arquivo, bytes, mime, aviso)
        `aviso` é None ou uma mensagem curta (ex.: formato ajustado).
    """
    fmt = out_format.upper()
    note = None
    multipage = len(cleaned_images) > 1

    if fmt in ("WORD (DOCX)", "DOCX", "WORD"):
        return f"limpo_{stem}.docx", images_to_docx_bytes(cleaned_images), MIME["DOCX"], note

    if fmt == "PDF":
        if is_pdf_input and cleaned_pdf_bytes is not None:
            return f"limpo_{stem}.pdf", cleaned_pdf_bytes, MIME["PDF"], note
        return f"limpo_{stem}.pdf", images_to_pdf_bytes(cleaned_images), MIME["PDF"], note

    # PNG / JPG
    if multipage:
        if multipage_image_fallback == "zip":
            note = "Documento com várias páginas — exportado como .zip de imagens."
            return (f"limpo_{stem}.zip",
                    images_to_zip_bytes(cleaned_images, fmt, jpg_quality),
                    "application/zip", note)
        # fallback padrão (premium): PDF
        note = "Documento com várias páginas — exportado como PDF."
        if is_pdf_input and cleaned_pdf_bytes is not None:
            return f"limpo_{stem}.pdf", cleaned_pdf_bytes, MIME["PDF"], note
        return f"limpo_{stem}.pdf", images_to_pdf_bytes(cleaned_images), MIME["PDF"], note

    ext = "jpg" if fmt == "JPG" else "png"
    data = image_to_bytes(cleaned_images[0], fmt, jpg_quality)
    return f"limpo_{stem}.{ext}", data, MIME[fmt], note
