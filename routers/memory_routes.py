"""SchoolBrain.ai — Memory / RAG Index Router"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from models.schemas import IndexRequest, IndexResponse
from auth_utils import get_current_user, require_role
from memory_system import semantic, episodic
from database import get_db, User

router = APIRouter()


@router.post("/index", response_model=IndexResponse)
def index_text(
    req: IndexRequest,
    current_user: User = Depends(get_current_user),
):
    """Index plain text into ChromaDB for RAG retrieval."""
    school_id = current_user.school_id
    metadata = {
        "school_id": school_id,
        "source": req.source,
        "subject": req.subject or "general",
        "grade": req.grade or "all",
    }
    ok = semantic.index(req.text, metadata=metadata)
    chunks = max(1, len(req.text) // 512)
    return IndexResponse(indexed=ok, chunks=chunks, school_id=school_id)


@router.post("/index/pdf")
async def index_pdf(
    school_id: str = Form(...),
    subject: str = Form(default="general"),
    grade: str = Form(default="all"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF and index its text into ChromaDB."""
    try:
        import pypdf
        content = await file.read()
        import io
        reader = pypdf.PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        return {"error": "pypdf not installed. pip install pypdf"}
    except Exception as e:
        return {"error": f"PDF read failed: {e}"}

    metadata = {
        "school_id": current_user.school_id,
        "source": file.filename,
        "subject": subject,
        "grade": grade,
    }
    ok = semantic.index(text, metadata=metadata, doc_id=file.filename)
    chunks = max(1, len(text) // 512)
    return IndexResponse(indexed=ok, chunks=chunks, school_id=current_user.school_id)


@router.post("/events/bulk")
def bulk_insert_events(
    events: list,
    current_user: User = Depends(get_current_user),
):
    """Bulk insert exam events into JSONL episodic memory."""
    count = episodic.bulk_load(current_user.school_id, events)
    return {"inserted": count, "school_id": current_user.school_id}
