from fastapi import APIRouter, UploadFile, HTTPException, Depends

from app.db.storage import upload_pdf, list_files, get_signed_url, delete_file
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload")
async def upload_document(file: UploadFile, user: dict = Depends(get_current_user)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    result = upload_pdf(contents, file.filename, user["user_id"])
    return {"message": "File uploaded successfully", **result}


@router.get("/")
async def list_documents(user: dict = Depends(get_current_user)):
    files = list_files(user["user_id"])
    return {"files": files}


@router.get("/url")
async def get_document_url(path: str, user: dict = Depends(get_current_user)):
    url = get_signed_url(path)
    return {"url": url}


@router.delete("/")
async def delete_document(path: str, user: dict = Depends(get_current_user)):
    delete_file(path)
    return {"message": "File deleted successfully"}
