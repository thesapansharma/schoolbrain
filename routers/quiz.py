"""SchoolBrain.ai — Quiz Generation Router"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.schemas import QuizRequest, QuizResponse, MCQItem
from auth_utils import get_current_user
from ai_helper import generate_json, build_quiz_prompt
from database import get_db, UsageLog, User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=QuizResponse)
def generate_quiz(
    req: QuizRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = build_quiz_prompt(req.topic, req.difficulty, req.count)
    schema = '[{question, options:[A,B,C,D strings], answer:"A"|"B"|"C"|"D", explanation}]'

    raw_list = generate_json(prompt, schema_hint=schema)

    questions = []
    for item in raw_list:
        try:
            # Normalise options — handle both list and dict formats
            opts = item.get("options", [])
            if isinstance(opts, dict):
                opts = [opts.get("A", ""), opts.get("B", ""), opts.get("C", ""), opts.get("D", "")]
            questions.append(MCQItem(
                question=item["question"],
                options=opts[:4],
                answer=item.get("answer", "A"),
                explanation=item.get("explanation", ""),
            ))
        except Exception as e:
            logger.warning(f"Skipping invalid MCQ: {e}")

    db.add(UsageLog(school_id=current_user.school_id, endpoint="/quiz/generate", latency_ms=0, user_id=current_user.id))
    db.commit()

    return QuizResponse(topic=req.topic, difficulty=req.difficulty, questions=questions)
