"""
SchoolBrain.ai — Ollama AI Helper
Handles: chat, structured JSON generation, retry on invalid JSON, RAG prompt building
"""

import json
import logging
import re
from typing import Optional, List, Dict, Any, Type
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MODEL = "qwen2.5:1.5b"
MAX_RETRIES = 3


def _ollama_chat(messages: List[Dict], temperature: float = 0.7) -> str:
    """Raw call to local Ollama. Returns response text."""
    try:
        import ollama
        response = ollama.chat(
            model=MODEL,
            messages=messages,
            options={"temperature": temperature},
        )
        return response["message"]["content"].strip()
    except ImportError:
        logger.warning("ollama package not installed — returning stub response")
        return '{"stub": true}'
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise


def chat_with_context(message: str, school_id: str, rag_docs: List[Dict] = []) -> Dict:
    """
    Chat endpoint call.
    Builds RAG-augmented prompt → calls Ollama → returns {response, sources}.
    """
    context_text = ""
    sources = []
    if rag_docs:
        context_parts = []
        for doc in rag_docs:
            context_parts.append(doc["text"])
            src = doc.get("metadata", {}).get("source", "curriculum")
            if src not in sources:
                sources.append(src)
        context_text = "\n\n".join(context_parts)

    system_prompt = (
        "You are SchoolBrain, an AI assistant for school teachers and administrators. "
        "You help identify weak students, generate quizzes, and create intervention plans. "
        "Be concise, professional, and always focused on student improvement."
    )

    user_content = message
    if context_text:
        user_content = (
            f"Use the following school curriculum context to answer:\n\n"
            f"CONTEXT:\n{context_text}\n\n"
            f"QUESTION: {message}"
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content},
    ]

    response_text = _ollama_chat(messages, temperature=0.6)
    return {"response": response_text, "sources": sources}


def generate_json(
    prompt: str,
    schema_hint: str,
    pydantic_model: Optional[Type[BaseModel]] = None,
    temperature: float = 0.3,
) -> Any:
    """
    Ask Ollama to return ONLY valid JSON.
    Retries up to MAX_RETRIES times with increasingly strict prompts.
    Returns parsed dict/list (or validated Pydantic model if provided).
    """
    system = (
        "You are a structured data generator. "
        "Respond ONLY with valid JSON matching the schema. "
        "No explanation, no markdown, no extra text. Only raw JSON."
    )

    for attempt in range(1, MAX_RETRIES + 1):
        strictness = ""
        if attempt == 2:
            strictness = " IMPORTANT: Output ONLY the JSON object/array, nothing else."
        elif attempt == 3:
            strictness = " CRITICAL: Your response must start with { or [ and be valid JSON."

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": f"{prompt}\n\nExpected schema: {schema_hint}{strictness}"},
        ]

        raw = _ollama_chat(messages, temperature=temperature)

        # Strip markdown code fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        # Extract first JSON object or array
        match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
        if match:
            raw = match.group(1)

        try:
            parsed = json.loads(raw)
            if pydantic_model:
                if isinstance(parsed, list):
                    return [pydantic_model(**item) for item in parsed]
                return pydantic_model(**parsed)
            return parsed
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"JSON parse attempt {attempt}/{MAX_RETRIES} failed: {e}. Raw: {raw[:200]}")

    raise ValueError(f"Failed to get valid JSON from AI after {MAX_RETRIES} attempts.")


def build_weak_student_prompt(student_summary: str) -> str:
    return f"""
Analyse the following school student exam data and identify at-risk students.

STUDENT DATA:
{student_summary}

Return a JSON array of at-risk students. Each item must have:
- student_id (string)
- name (string)
- risk_level ("High", "Medium", or "Low")
- weakest_subject (string)
- avg_score (number, 0-100)
- trend ("dropping", "stable", or "improving")
- recommendation (string, 1 sentence advice for teacher)

Include ALL students with avg_score < 65 or a clearly dropping trend.
Sort by risk_level descending (High first).
Return ONLY the JSON array.
"""


def build_quiz_prompt(topic: str, difficulty: str, count: int) -> str:
    return f"""
Generate {count} multiple-choice questions on the topic: "{topic}".
Difficulty level: {difficulty}.

Return a JSON array. Each item must have:
- question (string)
- options (array of exactly 4 strings, labelled A, B, C, D)
- answer (string: "A", "B", "C", or "D")
- explanation (string, 1-2 sentences explaining the correct answer)

Return ONLY the JSON array, no extra text.
"""


def build_intervention_prompt(student_name: str, weakest_subject: str, avg_score: float) -> str:
    return f"""
Create a personalised 7-day intervention plan for student {student_name}.
Weakest subject: {weakest_subject}. Current average score: {avg_score:.1f}/100.

Return a JSON array of 7 items. Each item must have:
- day (integer 1-7)
- activity (string, specific learning activity)
- goal (string, measurable learning goal for the day)
- resource (string, specific textbook/YouTube/exercise suggestion)

Return ONLY the JSON array.
"""


def build_lesson_plan_prompt(topic: str, class_grade: str, duration_mins: int, board: str) -> str:
    return f"""
Create a complete lesson plan for a {board} {class_grade} class.
Topic: {topic}. Duration: {duration_mins} minutes.

Return a JSON object with these exact keys:
- objective (string, what students will learn)
- warm_up (string, 5-minute activity to engage students)
- main_activity (string, core teaching content and method)
- guided_practice (string, teacher-led practice activity)
- assessment (string, how to check understanding)
- homework (string, take-home task)

Return ONLY the JSON object.
"""
