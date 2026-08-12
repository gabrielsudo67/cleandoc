# 🧼 Removedor de Marca d'Água

Aplicação web para **remoção de marcas d'água** de documentos e imagens, com
interface moderna, responsiva e processamento **100% local**.

Usa filtro de cor no espaço **HSV** e **limiarização adaptativa** para apagar
marcas d'água translúcidas/claras, preservando texto e assinaturas escuras.

---

## ✨ Recursos

- **Upload em lote por arrastar e soltar** — vários arquivos `PDF`, `PNG`, `JPG` de uma vez.
- **Ajustes na barra lateral**
  - *Sensibilidade da limpeza* (suave → agressiva)
  - *Manter assinaturas / texto escuro*
  - *Formato de saída das imagens*: **PNG** ou **JPG** (com controle de qualidade)
  - Opções avançadas: limiarização adaptativa, limiar de escuro, DPI do PDF,
    forçar rasterização.
- **Visualização lado a lado** (Antes × Depois) por arquivo.
- **Download individual** de cada resultado + **download de todos em `.zip`**.
- **Detecção automática** de PDF vetorial vs. digitalizado.
- Falha em um arquivo não interrompe o lote.

---

## 🏗️ Estrutura do projeto

```
watermark-remover/
├── app.py                    # Interface Streamlit
├── requirements.txt
├── README.md
└── src/
    └── engine/
        ├── __init__.py
        ├── image_cleaner.py  # Limpeza de imagens (HSV + adaptive threshold)
        └── pdf_cleaner.py    # Limpeza de PDF (PyMuPDF + rasterização OpenCV)
```

---

## 🚀 Como rodar localmente

### 1. Pré-requisitos
- Python 3.10 ou superior

### 2. Criar ambiente virtual (recomendado)

**Windows (PowerShell):**
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Executar a aplicação
```bash
streamlit run app.py
```

O navegador abrirá automaticamente em `http://localhost:8501`.

---

## 🔧 Como funciona

### Imagens e PDFs digitalizados
1. **Filtro HSV** — pixels de baixa saturação e alto brilho (típicos de marca
   d'água translúcida) são substituídos por branco.
2. **Limiarização adaptativa** — reforça a detecção de traços escuros (texto,
   carimbos, assinaturas) para que nunca sejam apagados.

### PDFs vetoriais
1. Remoção de anotações do tipo *watermark* / *stamp*.
2. Desativação de camadas de conteúdo opcional (OCG).
3. Como reforço, cada página pode ser rasterizada e limpa pela pipeline de
   imagem, preservando o conteúdo escuro.

O controle **Sensibilidade** desloca dinamicamente os limiares de saturação e
brilho; **Manter assinaturas / texto escuro** protege pixels escuros.

---

## ⚠️ Aviso legal

Utilize esta ferramenta apenas em documentos e imagens sobre os quais você
possui direitos ou autorização. A remoção de marcas d'água de conteúdo de
terceiros pode violar direitos autorais e/ou termos de uso.
