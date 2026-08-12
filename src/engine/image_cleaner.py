"""
image_cleaner.py
================
Limpeza de marcas d'água em imagens rasterizadas (PNG, JPG) e páginas de PDF
digitalizado.

Estratégia
----------
A maioria das marcas d'água é aplicada com baixa opacidade (cores claras,
pastel ou cinza) sobre um fundo branco, enquanto o conteúdo relevante
(texto, carimbos, assinaturas) tende a ser escuro e saturado. Combinamos
duas técnicas complementares:

1. Filtro de cor no espaço HSV
   Remove pixels de baixa saturação e/ou alto brilho — típicos de marcas
   d'água translúcidas — substituindo-os por branco.

2. Limiarização adaptativa (adaptive threshold)
   Preserva traços escuros (texto e assinaturas) mesmo em fundos com
   iluminação irregular, reforçando o que deve ser mantido.

O parâmetro `sensitivity` (0.0 – 1.0) controla o quão agressiva é a limpeza,
e `keep_dark` garante que texto/assinaturas escuras nunca sejam apagadas.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image


@dataclass
class CleanConfig:
    """Parâmetros de limpeza ajustáveis pela interface."""

    sensitivity: float = 0.5          # 0.0 (suave) .. 1.0 (agressivo)
    keep_dark: bool = True            # preservar texto/assinaturas escuras
    use_adaptive_threshold: bool = True
    dark_threshold: int = 110         # pixels abaixo disso são "conteúdo escuro"

    def clamp(self) -> "CleanConfig":
        self.sensitivity = float(min(max(self.sensitivity, 0.0), 1.0))
        self.dark_threshold = int(min(max(self.dark_threshold, 0), 255))
        return self


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    """Converte PIL (RGB/RGBA/L) para BGR (OpenCV), achatando transparência em branco."""
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")
    rgb = np.array(image)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _hsv_watermark_mask(bgr: np.ndarray, cfg: CleanConfig) -> np.ndarray:
    """
    Retorna máscara booleana (True = pixel considerado marca d'água / fundo).

    Pixels de baixa saturação e alto brilho são candidatos a marca d'água.
    Quanto maior a sensibilidade, mais pixels claros/pastel são removidos.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    _, s, v = cv2.split(hsv)

    # Limiares deslizam com a sensibilidade.
    # sensitivity alta -> tolera saturação maior e brilho menor como "fundo".
    sat_limit = int(40 + cfg.sensitivity * 90)     # 40 .. 130
    val_limit = int(210 - cfg.sensitivity * 90)    # 210 .. 120

    low_saturation = s < sat_limit
    high_value = v > val_limit

    # Marca d'água = claro (alto brilho) E pouco colorido (baixa saturação)
    mask = np.logical_and(low_saturation, high_value)
    return mask


def clean_image(image: Image.Image, cfg: CleanConfig | None = None) -> Image.Image:
    """
    Remove marca d'água de uma imagem PIL e devolve nova imagem PIL (RGB).

    Parameters
    ----------
    image : PIL.Image.Image
        Imagem de entrada.
    cfg : CleanConfig, opcional
        Configuração de limpeza. Usa padrões se omitido.
    """
    cfg = (cfg or CleanConfig()).clamp()
    bgr = _pil_to_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # 1) Máscara de marca d'água por cor (HSV)
    watermark_mask = _hsv_watermark_mask(bgr, cfg)

    # 2) Máscara de conteúdo escuro a preservar (texto / assinaturas)
    dark_mask = gray < cfg.dark_threshold

    # 3) Limiarização adaptativa reforça traços escuros mesmo com fundo irregular
    if cfg.use_adaptive_threshold:
        block = 35
        adaptive = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block, 15,
        )
        # onde adaptive == 0 -> traço escuro detectado
        dark_mask = np.logical_or(dark_mask, adaptive == 0)

    # Resultado começa como cópia; pixels de marca d'água viram branco.
    result = bgr.copy()
    remove = watermark_mask.copy()

    if cfg.keep_dark:
        # Nunca apagar conteúdo escuro que queremos manter.
        remove = np.logical_and(remove, np.logical_not(dark_mask))

    result[remove] = (255, 255, 255)

    return _bgr_to_pil(result)


def clean_image_bytes(data: bytes, cfg: CleanConfig | None = None) -> Image.Image:
    """Conveniência: recebe bytes de imagem e devolve PIL limpa."""
    import io

    image = Image.open(io.BytesIO(data))
    return clean_image(image, cfg)
