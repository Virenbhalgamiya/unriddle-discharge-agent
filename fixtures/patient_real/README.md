# Reviewer real patient PDF

Place the reviewer sample chart here:

```powershell
copy "C:\Users\Viren\Downloads\patient 2 (1).pdf" fixtures\patient_real\
```

This is a **71-page scanned chart** (image-only PDF). Processing requires [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki):

```powershell
winget install UB-Mannheim.TesseractOCR
```

Then run:

```powershell
$env:PYTHONPATH='.'
python scripts/run_real_patient_test.py
```

Or upload the file in Streamlit (**Load Reviewer Sample** in the sidebar).
