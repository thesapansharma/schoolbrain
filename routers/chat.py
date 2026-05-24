"""SchoolBrain.ai — Chat Router (RAG-augmented)"""

import time
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.schemas import ChatRequest, ChatResponse
from auth_utils import get_current_user
from ai_helper import chat_with_context
from memory_system import semantic, working
from database import get_db, UsageLog, User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    school_id = current_user.school_id
    t0 = time.time()

    # RAG: retrieve relevant curriculum context
    rag_docs = semantic.search(req.message, school_id=school_id, n=3)

    # Build and send to Ollama
    result = chat_with_context(req.message, school_id=school_id, rag_docs=rag_docs)

    # Update working memory with last query
    working.set(school_id, "last_query", req.message)

    # Log usage
    latency = (time.time() - t0) * 1000
    db.add(UsageLog(school_id=school_id, endpoint="/chat", latency_ms=latency, user_id=current_user.id))
    db.commit()

    logger.info(f"[{school_id}] /chat latency={latency:.0f}ms sources={result['sources']}")

    return ChatResponse(
        response=result["response"],
        school_id=school_id,
        sources=result["sources"],
    )
