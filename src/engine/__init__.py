"""
Engine de processamento para remoção de marcas d'água.

Módulos:
    - image_cleaner: limpeza de imagens (PNG/JPG) via filtro HSV e limiarização adaptativa.
    - pdf_cleaner: limpeza de PDFs vetoriais (PyMuPDF) e digitalizados (rasterização + OpenCV).
"""

from .image_cleaner import clean_image, CleanConfig
from .pdf_cleaner import clean_pdf, is_pdf_scanned

__all__ = ["clean_image", "CleanConfig", "clean_pdf", "is_pdf_scanned"]
