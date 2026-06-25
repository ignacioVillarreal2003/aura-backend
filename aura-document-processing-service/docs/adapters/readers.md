# Readers

Extraen texto crudo de un archivo. El `ReaderFactory` registra los readers disponibles y, por
cada archivo, devuelve **todos los readers capaces en orden de prioridad**; el servicio de
ingestión los prueba **secuencialmente** (si el preferido falla en runtime, cae al siguiente).

## Orden de prioridad (default)

Con `READER_DOCLING_ENABLED=true` (default), Docling va **primero**:

```
docling → digital_pdf → digital_docx → scanned_pdf → scanned_docx → plain_text → csv
```

La API manda `prefer_docling=true` por default, lo que empuja Docling al frente absoluto.
Para `.txt/.md/.csv` Docling no compite (no están en sus extensiones) → van directo al reader plano.

## Readers

| Reader | Formatos | Notas |
| --- | --- | --- |
| **docling** | pdf, docx, pptx, xlsx, imágenes | Estructura-aware (mejor calidad para el splitter `docling_hybrid`). `can_handle` por extensión; el fallback secuencial cubre fallos en runtime. Único que soporta pptx/xlsx. |
| **digital_pdf** | pdf con texto | `can_handle` **content-aware** (sondea texto real) → enruta digital vs escaneado. pypdf. |
| **digital_docx** | docx con texto | Extrae párrafos + tablas. python-docx. |
| **scanned_pdf** | pdf escaneado | OCR (Tesseract + Poppler/pdf2image). Solo si `can_handle` detecta ausencia de texto. |
| **scanned_docx** | docx con imágenes | OCR de las imágenes embebidas (`word/media/`). |
| **plain_text** | txt, md | Cadena de encodings + strip de markdown para `.md`. |
| **csv** | csv | Sniff de dialecto, cap de filas. |

## OCR (readers escaneados)

Los readers de OCR se registran **solo si Tesseract está disponible**. El factory autodetecta
Tesseract/Poppler (PATH, rutas default de Windows) o usa `READER_TESSERACT_PATH` / `READER_POPPLER_PATH`.

| Variable | Default | Descripción |
| --- | --- | --- |
| `READER_TESSERACT_LANG` | `spa` | `spa` \| `eng` \| `spa+eng`. |
| `READER_TESSERACT_TIMEOUT` | `300` | Timeout de OCR por página (s). |
| `READER_PDF_DPI` | `300` | Resolución de rasterización. |
| `READER_PDF_USE_PARALLEL` | `true` | OCR paralelo multipágina. |
| `READER_PDF_MAX_WORKERS` | auto | Procesos de OCR. |
| `READER_PDF_MAX_OCR_PAGES` | `500` | **Cap de páginas**: limita la rasterización+OCR para que un PDF escaneado de miles de páginas no consuma CPU sin límite. |

**Pool de procesos persistente** (`scanned_pdf`): el `ProcessPoolExecutor` se **reutiliza** entre
documentos (la ingesta bulk no paga arranque de procesos por archivo). Si un worker muere
(`BrokenProcessPool`), el pool se **resetea** y se cae a OCR secuencial para ese documento.

## Docling

| Variable | Default | Descripción |
| --- | --- | --- |
| `READER_DOCLING_ENABLED` | `true` | Habilita el reader Docling. |
| `READER_DOCLING_DEVICE` | `auto` | `cpu` \| `cuda` \| `mps` \| `auto`. |
| `READER_DOCLING_NUM_THREADS` | `4` | Threads del pipeline Docling. |

> El factory es resiliente: si un reader falla al inicializar (o Docling no está instalado),
> se loguea y se sigue con el resto — no tumba el arranque.
