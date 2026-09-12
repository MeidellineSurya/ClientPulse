from fastapi import APIRouter, HTTPException, UploadFile

from app.schemas import CsvIngestResult
from app.services.csv_ingest import parse_invoice_csv

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/csv", response_model=CsvIngestResult)
async def ingest_csv(file: UploadFile) -> CsvIngestResult:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        return parse_invoice_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
