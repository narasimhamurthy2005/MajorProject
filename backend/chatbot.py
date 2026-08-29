"""
chatbot.py -- Retrieval-Augmented Generation chatbot, no external API needed.

RAG has two halves and this implements both:
  1. RETRIEVAL: knowledge/*.txt is chunked and indexed with TF-IDF. A user's
     question is embedded the same way and matched by cosine similarity to
     pull the most relevant chunks -- this is the "retrieval" in RAG.
  2. AUGMENTED GENERATION: those chunks, PLUS live data pulled straight from
     the database (the satellite's latest readings and open anomalies, if
     the question names a satellite), are combined into a templated answer.

This runs fully offline. If you later get an Anthropic/OpenAI API key, the
`generate_answer` function is exactly where you'd swap the templating for
a real LLM call -- pass it the same retrieved context + live data as the
prompt and let the model write the final answer. See the commented example
at the bottom of this file.
"""

import os
import re
import sqlite3
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")


def _load_chunks():
    chunks = []
    for fname in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not fname.endswith(".txt"):
            continue
        path = os.path.join(KNOWLEDGE_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # split into paragraph-sized chunks
        for para in re.split(r"\n\s*\n", text):
            para = para.strip()
            if len(para) > 30:
                chunks.append({"source": fname, "text": para})
    return chunks


class RAGChatbot:
    def __init__(self):
        self.chunks = _load_chunks()
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform([c["text"] for c in self.chunks])

    def retrieve(self, query, top_k=3):
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.matrix).flatten()
        top_idx = sims.argsort()[::-1][:top_k]
        return [self.chunks[i] for i in top_idx if sims[i] > 0.03]

    def _find_mentioned_satellite(self, query, conn):
        cur = conn.cursor()
        cur.execute("SELECT * FROM satellites")
        sats = [dict(r) for r in cur.fetchall()]
        q_lower = query.lower()
        for sat in sats:
            first_word = sat["name"].split("-")[0].lower()
            if sat["name"].lower() in q_lower or first_word in q_lower:
                return sat
        return None

    def _live_context(self, satellite, conn):
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM telemetry WHERE satellite_id = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (satellite["id"],))
        latest = cur.fetchone()
        cur.execute("""
            SELECT * FROM anomalies WHERE satellite_id = ? AND resolved = 0
            ORDER BY timestamp DESC LIMIT 5
        """, (satellite["id"],))
        open_anomalies = [dict(r) for r in cur.fetchall()]

        lines = [f"Live status for {satellite['name']} ({satellite['type']}, {satellite['orbit_type']}):"]
        if latest:
            latest = dict(latest)
            lines.append(
                f"Temperature {latest['temperature']:.1f}°C, "
                f"Battery {latest['battery_voltage']:.1f}V, "
                f"Solar {latest['solar_panel_output']:.1f}W, "
                f"Signal {latest['signal_strength']:.1f}%, "
                f"Fuel {latest['fuel_level']:.1f}%, "
                f"Attitude error {latest['attitude_error']:.2f}°, "
                f"as of {latest['timestamp']}."
            )
        if open_anomalies:
            lines.append(f"{len(open_anomalies)} unresolved anomaly(ies), most recent: "
                          f"[{open_anomalies[0]['severity'].upper()}] {open_anomalies[0]['description']}")
        else:
            lines.append("No unresolved anomalies right now.")
        return "\n".join(lines)

    def generate_answer(self, query, conn):
        retrieved = self.retrieve(query)
        satellite = self._find_mentioned_satellite(query, conn)

        answer_parts = []
        if satellite:
            answer_parts.append(self._live_context(satellite, conn))

        if retrieved:
            for chunk in retrieved[:2]:
                answer_parts.append(chunk["text"])
        elif not satellite:
            answer_parts.append(
                "I don't have specific information on that in my knowledge base yet. "
                "Try asking about a telemetry parameter (temperature, battery, signal, "
                "fuel, attitude), how anomaly detection works, or a specific satellite by name."
            )

        return {
            "answer": "\n\n".join(answer_parts),
            "sources": [c["source"] for c in retrieved],
            "satellite_mentioned": satellite["name"] if satellite else None,
        }


# ---------------------------------------------------------------------------
# OPTIONAL: to use a real LLM (e.g. Anthropic Claude) instead of templating,
# replace generate_answer's return with something like:
#
#   import anthropic
#   client = anthropic.Anthropic(api_key="YOUR_KEY")
#   context = "\n\n".join(answer_parts)
#   msg = client.messages.create(
#       model="claude-sonnet-4-6",
#       max_tokens=400,
#       messages=[{"role": "user", "content":
#           f"Context:\n{context}\n\nQuestion: {query}\n\n"
#           "Answer the question using only the context above."}]
#   )
#   return {"answer": msg.content[0].text, "sources": [...], ...}
# ---------------------------------------------------------------------------
