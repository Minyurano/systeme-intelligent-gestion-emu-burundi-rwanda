"""
Extraction du texte des archives numérisées, pour l'assistant documentaire.
- .txt / .md : lecture directe
- .pdf : texte intégré (pypdf) ; si la page est une image scannée, OCR (Tesseract)
- .docx : python-docx
- images (.jpg, .png) : OCR Tesseract en français
Les bibliothèques sont optionnelles : si l'une manque, on renvoie un texte vide.
"""
from pathlib import Path


def extraire_texte(fichier) -> str:
    ext = Path(fichier.name).suffix.lower()
    try:
        if ext in (".txt", ".md", ".csv"):
            fichier.seek(0)
            return fichier.read().decode("utf-8", errors="ignore")
        if ext == ".pdf":
            return _pdf(fichier)
        if ext == ".docx":
            import docx

            fichier.seek(0)
            return "\n".join(p.text for p in docx.Document(fichier).paragraphs)
        if ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            return _ocr_image(fichier)
    except Exception:
        return ""
    return ""


def _pdf(fichier):
    from pypdf import PdfReader

    fichier.seek(0)
    lecteur = PdfReader(fichier)
    pages = [p.extract_text() or "" for p in lecteur.pages]
    texte = "\n".join(pages).strip()
    if len(texte) > 50:
        return texte
    # PDF scanné : on tente l'OCR sur les images intégrées
    morceaux = []
    for page in lecteur.pages:
        for image in page.images:
            morceaux.append(_ocr_octets(image.data))
    return "\n".join(morceaux)


def _ocr_image(fichier):
    fichier.seek(0)
    return _ocr_octets(fichier.read())


def _ocr_octets(octets):
    import io

    import pytesseract
    from PIL import Image

    try:
        return pytesseract.image_to_string(Image.open(io.BytesIO(octets)), lang="fra")
    except pytesseract.TesseractError:
        return pytesseract.image_to_string(Image.open(io.BytesIO(octets)))
