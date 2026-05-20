import fitz
from fastapi import HTTPException, UploadFile


ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/tiff",
    "image/bmp",
}


async def to_ocr_image_bytes(upload: UploadFile) -> bytes:
    raw = await upload.read()
    name = (upload.filename or "").lower()
    ctype = (upload.content_type or "").lower()

    is_pdf = name.endswith(".pdf") or ctype == "application/pdf"
    if is_pdf:
        try:
            pdf = fitz.open(stream=raw, filetype="pdf")
            if pdf.page_count < 1:
                raise HTTPException(status_code=400, detail="Uploaded PDF has no pages")
            page = pdf.load_page(0)
            # Lower render scale keeps text legible while reducing processing time.
            pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
            return pix.tobytes("png")
        except HTTPException:
            raise
        except Exception as ex:
            raise HTTPException(status_code=400, detail=f"Invalid PDF upload: {type(ex).__name__}") from ex

    is_image = ctype in ALLOWED_IMAGE_TYPES or name.endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif", ".bmp")
    )
    if not is_image:
        raise HTTPException(status_code=400, detail="Only image or PDF files are supported")

    return raw
