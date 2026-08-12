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

    Cobre dois tipos de marca d'água:

    1. Clara / cinza (baixa saturação, alto brilho) — ex.: marca translúcida
       cinza sobre fundo branco.
    2. Colorida (vermelha, rosa, azul...) porém clara — ex.: um "TESTE" em
       vermelho translúcido. Esses pixels têm saturação alta, mas continuam
       claros (brilho alto), diferentemente do texto escuro que queremos manter.

    Em ambos os casos o critério comum é: o pixel é **claro** (brilho alto).
    O texto/assinatura a preservar é escuro (brilho baixo) e, por isso, não
    entra na máscara.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    _, s, v = cv2.split(hsv)

    # Limiares deslizam com a sensibilidade.
    sat_limit = int(40 + cfg.sensitivity * 90)     # 40 .. 130

    # (1) Marca clara/cinza: pouco colorida e brilhante.
    val_limit_gray = int(210 - cfg.sensitivity * 90)   # 210 .. 120
    mask_gray = np.logical_and(s < sat_limit, v > val_limit_gray)

    # (2) Marca colorida translúcida: colorida, mas ainda clara.
    #     Quanto maior a sensibilidade, mais escuras (fortes) também são pegas.
    val_limit_color = int(200 - cfg.sensitivity * 120)  # 200 .. 80
    mask_color = np.logical_and(s >= sat_limit, v > val_limit_color)

    return np.logical_or(mask_gray, mask_color)


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

    # 1) Máscara de marca d'água por cor (HSV) — clara/cinza ou colorida translúcida
    watermark_mask = _hsv_watermark_mask(bgr, cfg)

    # 2) Conteúdo a preservar = pixels REALMENTE escuros (tinta preta: texto,
    #    carimbos e assinaturas escuras). Só protegemos o que é escuro de fato,
    #    para não confundir a marca d'água colorida (que é clara) com conteúdo.
    dark_mask = gray < cfg.dark_threshold

    # 3) Limiarização adaptativa: reforça traços escuros em fundos irregulares.
    #    Importante: só conta como "escuro a preservar" onde o pixel também NÃO
    #    é claro (evita proteger marca d'água colorida, que é clara).
    if cfg.use_adaptive_threshold:
        block = 35
        adaptive = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block, 15,
        )
        # traço escuro detectado (adaptive == 0) E genuinamente escuro (gray baixo)
        adaptive_dark = np.logical_and(adaptive == 0, gray < 150)
        dark_mask = np.logical_or(dark_mask, adaptive_dark)

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
