"""
Zero-cost ($0) Local Semantic Text Embedding & Similarity Utilities.

Generates deterministic, L2-normalized 384-dimensional feature-hashed vectors enriched with
multilingual academic concept synonyms (English / French / Spanish / German) so pgvector
cosine similarity works cleanly without paid external embedding APIs.
"""

import hashlib
import math
import re
from typing import Dict, List, Sequence


EMBEDDING_DIM = 384

_CONCEPT_EXPANSIONS: Dict[str, List[str]] = {
    "calculus": ["calculus", "derivative", "integral", "differentiation", "integration", "limits", "analyz"],
    "calcul": ["calculus", "derivative", "integral", "math"],
    "différentiel": ["calculus", "derivative", "math"],
    "intégral": ["calculus", "integral", "math"],
    "linear": ["linear", "matrix", "matrices", "vector", "eigenvalue", "algebra"],
    "algebra": ["algebra", "linear", "equations", "polynomials"],
    "discrete": ["discrete", "logic", "proofs", "combinatorics", "graphs", "sets"],
    "microeconomics": ["microeconomics", "micro", "supply", "demand", "elasticity", "consumer", "firm", "economics"],
    "macroeconomics": ["macroeconomics", "macro", "gdp", "inflation", "monetary", "fiscal", "economics"],
    "economics": ["economics", "microeconomics", "macroeconomics", "markets"],
    "économie": ["economics", "microeconomics", "macroeconomics"],
    "programming": ["programming", "algorithms", "coding", "software", "computer", "functions", "recursion"],
    "programmation": ["programming", "algorithms", "computer", "software"],
    "informatique": ["computer", "programming", "algorithms", "informatics", "data"],
    "structures": ["data structures", "trees", "graphs", "sorting", "recursion", "algorithms"],
    "algorithms": ["algorithms", "complexity", "data structures", "sorting", "graphs"],
    "composition": ["composition", "writing", "rhetoric", "essay", "reading", "argumentation"],
    "rhetoric": ["composition", "writing", "rhetoric", "critical"],
    "writing": ["composition", "writing", "essay", "expository"],
    "physics": ["physics", "mechanics", "kinematics", "newton", "electromagnetism", "waves"],
    "physique": ["physics", "mechanics", "kinematics"],
    "biology": ["biology", "cellular", "genetics", "evolution", "ecology"],
    "psychology": ["psychology", "behavior", "cognition", "perception", "mental"],
}


def _tokenize(text: str) -> List[str]:
    words = re.findall(r"[a-z0-9àâäéèêëïîôöùûüç]+", (text or "").lower())
    tokens: List[str] = []
    for w in words:
        tokens.append(w)
        if w in _CONCEPT_EXPANSIONS:
            tokens.extend(_CONCEPT_EXPANSIONS[w])
    # Add adjacent word bigrams for phrase alignment
    for i in range(len(words) - 1):
        tokens.append(f"{words[i]}_{words[i + 1]}")
    return tokens


def embed_text(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 6) for v in vec]
    return vec


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(float(a) * float(a) for a in v1))
    n2 = math.sqrt(sum(float(b) * float(b) for b in v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (n1 * n2)))
