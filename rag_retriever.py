"""
Prayash — Lightweight RAG Context Retriever
============================================
Inspired by SAHAY_AI's LangChain + FAISS + HuggingFace RAG pipeline.

SAHAY_AI uses heavy dependencies (LangChain, FAISS, sentence-transformers)
for semantic retrieval. This module provides the same functionality with
scikit-learn's TfidfVectorizer (already installed), chunking resume text
into meaningful segments, indexing them via TF-IDF, and retrieving the
most relevant chunks to enrich the career chat LLM prompt.

Components:
  - chunk_resume()        – split resume text into overlapping chunks
  - ResumeRetriever       – class that builds a TF-IDF index and retrieves
  - format_rag_context()  – convert retrieved chunks into an LLM-ready string
  - RAGService            – session-cached service (SAHAY_AI-inspired)
  - build_rag_context()   – one-shot convenience pipeline
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

log = logging.getLogger("prayash.rag")

# ── Default chunking parameters ──────────────────────────────────
_DEFAULT_CHUNK_SIZE = 300      # characters per chunk
_DEFAULT_CHUNK_OVERLAP = 60    # overlap between adjacent chunks
_DEFAULT_TOP_K = 5             # number of chunks to retrieve


# ── 1. Resume Chunking ───────────────────────────────────────────


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using simple regex.

    Handles common abbreviations (Mr., Dr., Inc., etc.) to avoid
    splitting on periods that aren't sentence boundaries.
    """
    # Protect common abbreviations
    _abbrev = re.compile(r"(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|Ave|Blvd|Inc|Ltd|Co|Corp|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec|vs|etc)\.", re.IGNORECASE)
    placeholder = "\x00ABBR\x00"
    text = _abbrev.sub(lambda m: m.group(0).replace(".", placeholder), text)

    # Split on sentence-ending punctuation followed by whitespace+uppercase
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)

    # Restore abbreviation periods
    return [s.replace(placeholder, ".").strip() for s in sentences if s.strip()]


def chunk_resume(
    text: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Split resume text into overlapping chunks for retrieval.

    First attempts section-aware chunking (by detecting known resume
    section headers), then falls back to sentence-based chunking
    within each section.

    Args:
        text: Raw or cleaned resume text.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap characters between adjacent chunks.

    Returns:
        List of dicts: [{ "text": str, "index": int, "section": str }]
    """
    if not text or len(text.strip()) < 20:
        return [{"text": text, "index": 0, "section": "general"}]

    # Known resume section headers to split on
    _section_patterns = re.compile(
        r"(?i)^\s*("
        r"education|experience|work\s*experience|professional\s*experience|"
        r"projects|skills|technical\s*skills|certifications|achievements|"
        r"awards|publications|summary|professional\s*summary|objective|"
        r"career\s*objective|qualifications|academic|employment|"
        r"leadership|volunteer|extracurricular|"
        r"languages|interests|references|contact"
        r")\s*[:\-]?\s*$"
    )

    lines = text.split("\n")
    sections: list[tuple[str, str]] = []  # [(section_name, text)]

    current_section = "general"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_lines.append(line)
            continue
        match = _section_patterns.match(stripped)
        if match:
            if current_lines:
                sections.append((current_section, "\n".join(current_lines).strip()))
            current_section = match.group(1).lower().replace(" ", "_")
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_section, "\n".join(current_lines).strip()))

    # Now create chunks from each section, with overlap
    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for section_name, section_text in sections:
        if not section_text:
            continue

        # For short sections, keep as one chunk
        if len(section_text) <= chunk_size:
            chunks.append({
                "text": section_text,
                "index": chunk_index,
                "section": section_name,
            })
            chunk_index += 1
            continue

        # For longer sections, split into overlapping sentence chunks
        sentences = _split_sentences(section_text)
        current_chunk: list[str] = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            # If adding this sentence exceeds chunk size, finalize the chunk
            if current_len + sentence_len > chunk_size and current_chunk:
                chunks.append({
                    "text": " ".join(current_chunk),
                    "index": chunk_index,
                    "section": section_name,
                })
                chunk_index += 1
                # Keep some sentences for overlap
                overlap_text = current_chunk
                overlap_len = current_len
                while overlap_len > chunk_overlap and overlap_text:
                    removed = overlap_text.pop(0)
                    overlap_len -= len(removed)
                current_chunk = overlap_text
                current_len = overlap_len

            current_chunk.append(sentence)
            current_len += sentence_len

        # Final chunk from this section
        if current_chunk:
            chunks.append({
                "text": " ".join(current_chunk),
                "index": chunk_index,
                "section": section_name,
            })
            chunk_index += 1

    if not chunks:
        # Fallback: single chunk with all text
        chunks.append({"text": text, "index": 0, "section": "general"})

    return chunks


# ── 2. ResumeRetriever ────────────────────────────────────────────


class ResumeRetriever:
    """Lightweight RAG retriever using TF-IDF vectorisation.

    Builds an in-memory TF-IDF index from resume chunks and retrieves
    the most relevant chunks given a user query.  Designed for low
    latency and zero external dependencies beyond scikit-learn.

    Usage:
        retriever = ResumeRetriever()
        retriever.index_resume(resume_text)
        results = retriever.retrieve("What skills should I learn?")
    """

    def __init__(self, top_k: int = _DEFAULT_TOP_K) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._chunks: list[dict[str, Any]] = []
        self._tfidf_matrix = None
        self._top_k = top_k
        self._is_indexed = False
        log.debug("ResumeRetriever initialised (top_k=%d)", top_k)

    # ── Public API ──────────────────────────────────────────────

    def index_resume(
        self,
        resume_text: str,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
    ) -> int:
        """Build a searchable TF-IDF index from resume text.

        Args:
            resume_text: The full resume text to index.
            chunk_size: Max characters per chunk.
            chunk_overlap: Overlap between chunks.

        Returns:
            Number of chunks indexed.
        """
        if not resume_text or len(resume_text.strip()) < 20:
            self._is_indexed = False
            return 0

        self._chunks = chunk_resume(resume_text, chunk_size, chunk_overlap)
        if not self._chunks:
            self._is_indexed = False
            return 0

        texts = [c["text"] for c in self._chunks]
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            max_features=5000,
            ngram_range=(1, 2),  # unigrams + bigrams for better matching
            sublinear_tf=True,    # use 1 + log(tf) scaling
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(texts)
        self._is_indexed = True
        log.debug(
            "Indexed %d chunks (%d features) from resume text (%d chars)",
            len(self._chunks),
            len(self._vectorizer.get_feature_names_out()),
            len(resume_text),
        )
        return len(self._chunks)

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Retrieve the top-K most relevant chunks for *query*.

        Args:
            query: The user's question or search text.
            top_k: Number of results to return (defaults to self._top_k).

        Returns:
            List of dicts sorted by descending relevance score:
              [{ "text": str, "score": float, "section": str, "index": int }]
            Returns an empty list if no index has been built.
        """
        if not self._is_indexed or self._vectorizer is None or self._tfidf_matrix is None:
            return []

        k = top_k or self._top_k
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

        top_indices = scores.argsort()[::-1][:k]
        results: list[dict[str, Any]] = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < 0.01:  # noise threshold
                continue
            results.append({
                "text": self._chunks[idx]["text"],
                "score": round(score, 4),
                "section": self._chunks[idx].get("section", "general"),
                "index": int(idx),
            })

        return results

    @property
    def is_indexed(self) -> bool:
        """True iff a resume has been indexed and is ready for retrieval."""
        return self._is_indexed

    @property
    def chunk_count(self) -> int:
        """Number of indexed chunks."""
        return len(self._chunks)

    def clear(self) -> None:
        """Clear the index and chunks (e.g. when a new resume is uploaded)."""
        self._vectorizer = None
        self._chunks = []
        self._tfidf_matrix = None
        self._is_indexed = False
        log.debug("ResumeRetriever cleared")


# ── 3. Context Formatting ─────────────────────────────────────────


def format_rag_context(
    results: list[dict[str, Any]],
    max_chars: int = 2000,
) -> str:
    """Format retrieved chunks into a compact, LLM-ready context string.

    Each chunk is prefixed with its section label and relevance score,
    so the LLM can weigh sources appropriately.

    Args:
        results: Output of ResumeRetriever.retrieve().
        max_chars: Total maximum characters for the context block.

    Returns:
        A formatted string like:
          [Relevant Resume Context]
          ── Education (score: 0.85)──
          BSc in Computer Science ...
          ── Skills (score: 0.72) ──
          Python, TensorFlow ...
    """
    if not results:
        return ""

    parts: list[str] = []
    total_len = 0

    for r in results:
        section = r.get("section", "general").replace("_", " ").title()
        text = r.get("text", "").strip()
        score = r.get("score", 0.0)
        header = f"── {section} (relevance: {score:.0%}) ──"
        entry = f"{header}\n{text}"

        if total_len + len(entry) > max_chars:
            # Truncate the last entry to fit
            remaining = max_chars - total_len - len(header) - 2
            if remaining > 40:
                entry = f"{header}\n{text[:remaining]}..."
                parts.append(entry)
            break

        parts.append(entry)
        total_len += len(entry) + 1  # +1 for newline

    if not parts:
        return ""

    return "[Relevant Resume Context]\n" + "\n\n".join(parts)


# ── 4. RAGService (session-cached, SAHAY_AI-inspired) ─────────────


class RAGService:
    """Session-based cache for :class:`ResumeRetriever` instances.

    SAHAY_AI-inspired service that keeps indexed retrievers in memory
    keyed by session ID, so the TF-IDF vectorizer is not rebuilt on
    every chat turn when the resume hasn't changed.  Idle sessions
    are evicted after *ttl_seconds*.

    Usage:
        service = RAGService()
        retriever = service.get_or_create("session-123", resume_text)
        results = retriever.retrieve("What skills should I learn?")
        status = service.get_status()  # for monitoring endpoint
    """

    _TTL = 1800  # 30 minutes in seconds

    def __init__(self) -> None:
        self._instances: dict[str, dict[str, Any]] = {}
        log.info("RAGService initialised (TTL=%ds)", self._TTL)

    # ── Public API ────────────────────────────────────────────────

    def get_or_create(
        self,
        session_id: str,
        resume_text: str,
        top_k: int = _DEFAULT_TOP_K,
    ) -> ResumeRetriever | None:
        """Return a cached :class:`ResumeRetriever` for *session_id*,
        or create and index a new one if the resume has changed or
        no cached entry exists.

        Args:
            session_id: Unique conversation/session identifier.
            resume_text: Full resume text to index if not cached.
            top_k: Top-K retrieval count for the retriever.

        Returns:
            A ready-to-use :class:`ResumeRetriever`, or ``None`` if
            *resume_text* is empty/too short to index.
        """
        self._evict_stale()

        if not resume_text or len(resume_text.strip()) < 20:
            return None

        resume_hash = hashlib.md5(resume_text.encode("utf-8")).hexdigest()
        entry = self._instances.get(session_id)

        # Return cached retriever if the resume hasn't changed
        if entry and entry.get("resume_hash") == resume_hash:
            entry["last_active"] = time.time()
            log.debug("RAG cache hit for session %s", session_id[:8])
            return entry["retriever"]

        # Build a new retriever and cache it
        retriever = ResumeRetriever(top_k=top_k)
        chunk_count = retriever.index_resume(resume_text)

        if chunk_count == 0:
            return None

        self._instances[session_id] = {
            "retriever": retriever,
            "resume_hash": resume_hash,
            "last_active": time.time(),
            "created_at": time.time(),
        }
        log.info(
            "RAG cache created for session %s (%d chunks, %d chars)",
            session_id[:8], chunk_count, len(resume_text),
        )
        return retriever

    def get_status(self) -> dict[str, Any]:
        """Return cache status for the performance monitoring endpoint.

        SAHAY_AI's ``RAGService.get_cache_info()`` inspired this;
        it tracks active sessions, TTL, and caching activity.

        Returns:
            dict with keys:
              - cached_sessions  (int)
              - ttl_seconds      (int)
              - active           (bool)
              - oldest_session_s (float – seconds since oldest entry)
        """
        now = time.time()
        ages = [now - e["created_at"] for e in self._instances.values()]
        oldest = max(ages) if ages else 0.0
        return {
            "cached_sessions": len(self._instances),
            "ttl_seconds": self._TTL,
            "active": True,
            "oldest_session_seconds": round(oldest, 1),
        }

    def evict(self, session_id: str) -> None:
        """Remove a specific session from the cache."""
        self._instances.pop(session_id, None)
        log.debug("RAG cache evicted for session %s", session_id[:8])

    def clear_all(self) -> None:
        """Clear all cached retrievers."""
        count = len(self._instances)
        self._instances.clear()
        log.info("RAG cache cleared (%d sessions)", count)

    # ── Internal ──────────────────────────────────────────────────

    def _evict_stale(self) -> None:
        """Remove sessions that have been idle for longer than TTL."""
        now = time.time()
        stale = [
            sid for sid, data in self._instances.items()
            if now - data.get("last_active", 0) > self._TTL
        ]
        for sid in stale:
            self._instances.pop(sid, None)
        if stale:
            log.debug("Evicted %d stale RAG cache session(s)", len(stale))


# Global singleton — mirrors SAHAY_AI's ``rag_service = RAGService()`` pattern
rag_service = RAGService()


# ── 5. Updated Convenience Pipeline (uses RAGService) ──────────────


def build_rag_context(
    resume_text: str,
    query: str,
    top_k: int = _DEFAULT_TOP_K,
    max_context_chars: int = 2000,
    session_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """One-shot pipeline: chunk resume → index → retrieve → format.

    When *session_id* is provided, the pipeline uses the global
    :class:`RAGService` singleton so the TF-IDF index is cached
    and not rebuilt on consecutive calls with the same resume.

    Args:
        resume_text: Full resume text.
        query: The user's career question.
        top_k: Number of chunks to retrieve.
        max_context_chars: Max chars for the formatted context.
        session_id: Optional session ID for cache reuse.

    Returns:
        Tuple of (formatted_context_string, metadata_dict).
        The metadata dict contains chunk_count, top_score, and
        whether the result was served from cache.
    """
    # Use session-cached retriever if session_id is provided
    if session_id:
        retriever = rag_service.get_or_create(session_id, resume_text, top_k=top_k)
        if retriever is None:
            return "", {"chunk_count": 0, "top_score": 0.0, "cached": False}
        results = retriever.retrieve(query, top_k=top_k)
        metadata: dict[str, Any] = {
            "chunk_count": retriever.chunk_count,
            "retrieved_count": len(results),
            "top_score": results[0]["score"] if results else 0.0,
            "cached": True,
        }
    else:
        # One-shot fallback (no session caching)
        retriever = ResumeRetriever(top_k=top_k)
        chunk_count = retriever.index_resume(resume_text)
        if chunk_count == 0:
            return "", {"chunk_count": 0, "top_score": 0.0, "cached": False}
        results = retriever.retrieve(query, top_k=top_k)
        metadata = {
            "chunk_count": chunk_count,
            "retrieved_count": len(results),
            "top_score": results[0]["score"] if results else 0.0,
            "cached": False,
        }

    context = format_rag_context(results, max_chars=max_context_chars)
    return context, metadata
