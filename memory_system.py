"""
SchoolBrain.ai — 4-Layer Memory System
  1. WorkingMemory  — in-RAM conversation context per school session
  2. EpisodicMemory — JSONL files, one per school, stores exam events
  3. SemanticMemory — ChromaDB vector store for curriculum / docs (RAG)
  4. ProceduralMemory — placeholder for future LoRA fine-tuned weights
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "./data/schools"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Working Memory
# ─────────────────────────────────────────────────────────────────────────────
class WorkingMemory:
    """
    In-process dict storing current session context per school.
    Cleared on API restart (ephemeral by design).
    """
    def __init__(self):
        self._store: Dict[str, Dict] = {}

    def set(self, school_id: str, key: str, value: Any):
        if school_id not in self._store:
            self._store[school_id] = {}
        self._store[school_id][key] = value

    def get(self, school_id: str, key: str, default=None):
        return self._store.get(school_id, {}).get(key, default)

    def get_context(self, school_id: str) -> Dict:
        return self._store.get(school_id, {})

    def clear(self, school_id: str):
        self._store.pop(school_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Episodic Memory
# ─────────────────────────────────────────────────────────────────────────────
class EpisodicMemory:
    """
    JSONL file per school. Each line = one exam event.
    Format: {student_id, name, class, subject, score, date, exam_name}
    """
    def _path(self, school_id: str) -> Path:
        school_dir = DATA_DIR / school_id
        school_dir.mkdir(parents=True, exist_ok=True)
        return school_dir / "events.jsonl"

    def add_event(self, school_id: str, event: Dict) -> bool:
        event["_recorded_at"] = datetime.utcnow().isoformat()
        try:
            with open(self._path(school_id), "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            return True
        except Exception as e:
            logger.error(f"EpisodicMemory.add_event error: {e}")
            return False

    def get_events(
        self,
        school_id: str,
        limit: int = 500,
        subject: Optional[str] = None,
        student_id: Optional[str] = None,
    ) -> List[Dict]:
        path = self._path(school_id)
        if not path.exists():
            return []
        events = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    ev = json.loads(line)
                    if subject and ev.get("subject") != subject:
                        continue
                    if student_id and ev.get("student_id") != student_id:
                        continue
                    events.append(ev)
        except Exception as e:
            logger.error(f"EpisodicMemory.get_events error: {e}")
        return events[-limit:]

    def get_all_students(self, school_id: str) -> Dict[str, Dict]:
        """Return dict of student_id → {name, class, scores_by_subject}"""
        events = self.get_events(school_id, limit=10000)
        students: Dict[str, Dict] = {}
        for ev in events:
            sid = ev.get("student_id", "")
            if not sid:
                continue
            if sid not in students:
                students[sid] = {
                    "student_id": sid,
                    "name": ev.get("name", sid),
                    "class_name": ev.get("class", "Unknown"),
                    "scores": {},
                }
            subject = ev.get("subject", "General")
            score = ev.get("score", 0)
            if subject not in students[sid]["scores"]:
                students[sid]["scores"][subject] = []
            students[sid]["scores"][subject].append({
                "score": score,
                "date": ev.get("date", ""),
                "exam_name": ev.get("exam_name", ""),
            })
        return students

    def bulk_load(self, school_id: str, events: List[Dict]) -> int:
        """Insert multiple events at once. Returns count inserted."""
        count = 0
        for ev in events:
            if self.add_event(school_id, ev):
                count += 1
        return count


# ─────────────────────────────────────────────────────────────────────────────
# 3. Semantic Memory (ChromaDB RAG)
# ─────────────────────────────────────────────────────────────────────────────
class SemanticMemory:
    """
    ChromaDB vector store for curriculum documents.
    Uses BAAI/bge-small-en-v1.5 embeddings (CPU-friendly).
    Falls back gracefully if ChromaDB is not installed.
    """
    def __init__(self):
        self._client = None
        self._collection = None
        self._ef = None
        self._ready = False
        try:
            import chromadb
            from chromadb.utils import embedding_functions
            self._client = chromadb.PersistentClient(path="./memory/semantic")
            self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-small-en-v1.5"
            )
            self._collection = self._client.get_or_create_collection(
                name="school_memory",
                embedding_function=self._ef,
                metadata={"hnsw:space": "cosine"},
            )
            self._ready = True
            logger.info("SemanticMemory: ChromaDB ready.")
        except ImportError:
            logger.warning("ChromaDB not installed — SemanticMemory disabled. pip install chromadb sentence-transformers")
        except Exception as e:
            logger.error(f"SemanticMemory init error: {e}")

    def index(self, text: str, metadata: Dict, doc_id: Optional[str] = None) -> bool:
        if not self._ready:
            return False
        try:
            # Chunk text into 512-char pieces with 64-char overlap
            chunks = self._chunk(text, size=512, overlap=64)
            ids, docs, metas = [], [], []
            for i, chunk in enumerate(chunks):
                chunk_id = doc_id or f"{metadata.get('school_id','x')}_{datetime.utcnow().timestamp()}_{i}"
                ids.append(f"{chunk_id}_{i}")
                docs.append(chunk)
                metas.append({**metadata, "chunk_index": i})
            self._collection.upsert(ids=ids, documents=docs, metadatas=metas)
            return True
        except Exception as e:
            logger.error(f"SemanticMemory.index error: {e}")
            return False

    def search(self, query: str, school_id: str, n: int = 3) -> List[Dict]:
        if not self._ready:
            return []
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n,
                where={"school_id": school_id},
            )
            out = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                out.append({"text": doc, "score": 1 - dist, "metadata": meta})
            return out
        except Exception as e:
            logger.error(f"SemanticMemory.search error: {e}")
            return []

    @staticmethod
    def _chunk(text: str, size: int = 512, overlap: int = 64) -> List[str]:
        chunks, start = [], 0
        while start < len(text):
            end = start + size
            chunks.append(text[start:end])
            start += size - overlap
        return [c for c in chunks if c.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Procedural Memory (LoRA placeholder)
# ─────────────────────────────────────────────────────────────────────────────
class ProceduralMemory:
    """
    Placeholder for future per-school LoRA fine-tuned model weights.
    After 3 months of usage, the AI is fine-tuned on the school's curriculum.
    Training runs on Lambda Labs GPU; weights sync back to VPS via rsync.
    """
    def __init__(self):
        self._weights_dir = Path("./memory/procedural")
        self._weights_dir.mkdir(parents=True, exist_ok=True)

    def load_weights(self, school_id: str) -> Optional[str]:
        """Return path to LoRA adapter weights if they exist."""
        weights_path = self._weights_dir / f"{school_id}_lora"
        if weights_path.exists():
            return str(weights_path)
        logger.info(f"No LoRA weights for {school_id} — using base model.")
        return None

    def fine_tune(self, school_id: str) -> Dict:
        """
        Stub — in production, this triggers a nightly Lambda Labs job:
        1. Export school JSONL + ChromaDB chunks to S3
        2. Run LoRA fine-tuning on A10 GPU (2hrs @ $0.75/hr)
        3. rsync weights back to VPS
        4. Reload Ollama with new adapter
        """
        return {
            "status": "not_implemented",
            "message": "LoRA training runs nightly on Lambda Labs GPU. See Day 19 setup.",
            "school_id": school_id,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Singleton exports
# ─────────────────────────────────────────────────────────────────────────────
working   = WorkingMemory()
episodic  = EpisodicMemory()
semantic  = SemanticMemory()
procedural = ProceduralMemory()

memory = {
    "working":    working,
    "episodic":   episodic,
    "semantic":   semantic,
    "procedural": procedural,
}
