# Readers

Este módulo contiene diferentes readers para extraer texto de archivos según su tipo y formato.

## 1. DigitalPDFReaderAdapter

### 📝 Descripción

Reader para PDFs digitales que contienen texto seleccionable.

- Verifica que el archivo tenga extensión `.pdf` y que al menos algunas páginas tengan texto extraíble.
- Extrae todo el texto disponible y lo devuelve como un string unificado.

## 2. DOCXReaderAdapter

### 📝 Descripción

Reader para archivos DOCX (Word).

- Verifica la extensión `.docx`.
- Extrae texto de todos los párrafos no vacíos y devuelve un string concatenado.

## 3. ScannedPDFReaderAdapter

### 📝 Descripción

Reader para PDFs escaneados que requieren OCR.

- Convierte cada página a imagen usando `pdf2image` y extrae texto con `pytesseract`.
- Devuelve todo el texto OCR como un string unificado.