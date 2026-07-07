# Pipeline d'extraction des jugements PDF

## Fonctionnement

1. `extract_text.py` valide le chemin et l'extension du PDF.
2. `app/ocr/pdf_detector.py` analyse le texte natif de chaque page.
3. Un PDF natif sain est lu par PyMuPDF dans `pdf_reader.py`.
4. Un scan ou un texte natif corrompu est rendu en PNG a 300 DPI, puis lu par
   Tesseract dans `tesseract_service.py`.
5. Tesseract teste les modes PSM 6 et PSM 11. Une variante trop courte est
   rejetee ; la confiance OCR et le nombre de mots departagent les autres.
6. `text_cleaner.py` supprime les marqueurs invisibles, diacritiques parasites,
   tatweels et espaces anormaux.
7. `legal_corrector.py` repare de facon contextuelle les listes d'articles
   (`الفصول 10 و11 و60`) sans remplacer globalement les lettres arabes.
8. Le resultat UTF-8 est ecrit dans `output/<nom>.txt`.

## Modele arabe

Le projet utilise `tessdata_best/ara.traineddata`. Si ce modele est absent, le
service utilise le modele `ara` installe avec Tesseract.

## Installation

```powershell
python -m pip install -r requirements.txt
```

Prerequis systeme : Tesseract OCR 5 avec la langue arabe et Poppler.

Variables disponibles :

- `TESSERACT_CMD` : chemin de `tesseract.exe` ;
- `POPPLER_PATH` : dossier `bin` de Poppler ;
- `TESSDATA_DIR` : dossier contenant `ara.traineddata` ;
- `TESSERACT_PSM_MODES` : modes OCR, par defaut `6,11`.

## Commandes

```powershell
python extract_text.py
python extract_text.py uploads/68182.pdf
python extract_text.py uploads/68182.pdf --output-dir output
python extract_text.py uploads/68182.pdf --force-ocr
python extract_text.py uploads/68182.pdf --keep-page-markers
```

## Limite de precision

Tesseract ne garantit pas une copie juridique mot a mot. Les noms propres,
dates, chiffres et scans faibles doivent etre controles. Pour une fidelite
absolue, ajouter une validation humaine ou une correction linguistique apres
l'OCR.
