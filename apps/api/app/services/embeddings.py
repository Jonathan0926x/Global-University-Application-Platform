"""
Zero-cost ($0) Multilingual Semantic Text Embedding & Similarity Utilities.

Generates deterministic, L2-normalized 384-dimensional feature-hashed vectors enriched with
multilingual academic, admissions, cost, scholarship, and transfer concept bridges
across English, French, Spanish, Haitian Creole, Arabic, German, Portuguese, Hindi,
Japanese, and Chinese so pgvector cosine similarity works cleanly without paid APIs.
"""

import hashlib
import math
import re
from typing import Dict, List, Sequence


EMBEDDING_DIM = 384

_CONCEPT_EXPANSIONS: Dict[str, List[str]] = {
    # Mathematics & STEM
    "calculus": ["calculus", "derivative", "integral", "differentiation", "integration", "limits", "math"],
    "calcul": ["calculus", "derivative", "integral", "math"],
    "différentiel": ["calculus", "derivative", "math"],
    "intégral": ["calculus", "integral", "math"],
    "linear": ["linear", "matrix", "matrices", "vector", "eigenvalue", "algebra"],
    "algebra": ["algebra", "linear", "equations", "polynomials"],
    "discrete": ["discrete", "logic", "proofs", "combinatorics", "graphs", "sets"],
    "microeconomics": ["microeconomics", "micro", "supply", "demand", "elasticity", "economics"],
    "macroeconomics": ["macroeconomics", "macro", "gdp", "inflation", "monetary", "fiscal", "economics"],
    "economics": ["economics", "microeconomics", "macroeconomics", "markets"],
    "économie": ["economics", "microeconomics", "macroeconomics"],
    "economía": ["economics", "microeconomics", "macroeconomics"],
    "ekonomi": ["economics", "microeconomics", "macroeconomics"],
    "اقتصاد": ["economics", "major", "program"],
    "programming": ["programming", "algorithms", "coding", "software", "computer", "functions"],
    "programmation": ["programming", "algorithms", "computer", "software"],
    "programación": ["programming", "algorithms", "computer", "software"],
    "informatique": ["computer", "programming", "algorithms", "informatics", "data", "science"],
    "informática": ["computer", "programming", "algorithms", "informatics"],
    "structures": ["data structures", "trees", "graphs", "sorting", "recursion", "algorithms"],
    "algorithms": ["algorithms", "complexity", "data structures", "sorting", "graphs"],
    "composition": ["composition", "writing", "rhetoric", "essay", "reading", "argumentation"],
    "rhetoric": ["composition", "writing", "rhetoric", "critical"],
    "writing": ["composition", "writing", "essay", "expository"],
    "physics": ["physics", "mechanics", "kinematics", "newton", "electromagnetism"],
    "physique": ["physics", "mechanics", "kinematics"],
    "biology": ["biology", "cellular", "genetics", "evolution", "ecology"],
    "psychology": ["psychology", "behavior", "cognition", "perception"],
    # Transfer & Articulation
    "transfer": ["transfer", "articulation", "credit", "units", "equivalency", "community college"],
    "transfè": ["transfer", "articulation", "credit", "units", "equivalency", "community college"],
    "transférer": ["transfer", "articulation", "credit", "units", "equivalency"],
    "transferir": ["transfer", "articulation", "credit", "units", "equivalency"],
    "تحويل": ["transfer", "articulation", "credit", "units", "equivalency"],
    "نقل": ["transfer", "articulation", "credit"],
    "credit": ["credit", "credits", "units", "semester", "quarter", "ects", "articulation"],
    "credits": ["credit", "credits", "units", "semester", "quarter", "ects", "articulation"],
    "kredi": ["credit", "credits", "units", "semester", "quarter", "ects"],
    "crédits": ["credit", "credits", "units", "semester", "quarter", "ects"],
    "créditos": ["credit", "credits", "units", "semester", "quarter", "ects"],
    "ساعات": ["credit", "credits", "units", "semester", "quarter", "ects"],
    "معتمدة": ["credit", "credits", "equivalency"],
    # Requirements, Documents, Deadlines & Qualifications
    "requirement": ["requirement", "requirements", "eligibility", "prerequisite", "gpa", "documents"],
    "requirements": ["requirement", "requirements", "eligibility", "prerequisite", "gpa", "documents"],
    "egzijans": ["requirement", "requirements", "eligibility", "documents", "gpa"],
    "exigences": ["requirement", "requirements", "eligibility", "documents", "gpa"],
    "requisitos": ["requirement", "requirements", "eligibility", "documents", "gpa"],
    "متطلبات": ["requirement", "requirements", "eligibility", "documents", "gpa"],
    "شروط": ["requirement", "requirements", "eligibility"],
    "deadline": ["deadline", "deadlines", "date", "intake", "fall", "spring", "summer", "application"],
    "deadlines": ["deadline", "deadlines", "date", "intake", "application"],
    "échéance": ["deadline", "deadlines", "date", "application"],
    "fecha": ["deadline", "deadlines", "date", "application"],
    "dat": ["deadline", "deadlines", "date"],
    "موعد": ["deadline", "deadlines", "date", "application"],
    "مواعيد": ["deadline", "deadlines", "date", "application"],
    "document": ["document", "documents", "transcript", "syllabus", "essay", "recommendation"],
    "documents": ["document", "documents", "transcript", "syllabus", "essay"],
    "dokiman": ["document", "documents", "transcript", "syllabus", "diploma"],
    "transcript": ["transcript", "records", "grades", "gpa", "credential"],
    "relve": ["transcript", "records", "grades", "gpa"],
    "relevé": ["transcript", "records", "grades", "gpa"],
    "وثائق": ["document", "documents", "transcript", "records"],
    "كشف": ["transcript", "grades", "gpa"],
    "baccalauréat": ["baccalauréat", "haiti", "france", "secondary", "qualification", "diploma"],
    "bac": ["baccalauréat", "secondary", "qualification", "diploma"],
    "abitur": ["abitur", "germany", "qualification", "secondary"],
    "gpa": ["gpa", "grade", "grades", "grading", "minimum", "threshold", "academic"],
    "معدل": ["gpa", "grade", "grades", "minimum"],
    # Costs, Tuition, Financial Aid & Scholarships
    "tuition": ["tuition", "cost", "fee", "fees", "coa", "price", "budget", "financial"],
    "cost": ["tuition", "cost", "fee", "coa", "net price", "living", "budget"],
    "costs": ["tuition", "cost", "fee", "coa", "net price", "living", "budget"],
    "frais": ["tuition", "cost", "fee", "fees", "financial"],
    "frè": ["tuition", "cost", "fee", "fees", "financial"],
    "matrícula": ["tuition", "cost", "fee", "fees"],
    "costo": ["tuition", "cost", "fee", "coa", "net price"],
    "رسوم": ["tuition", "cost", "fee", "fees", "financial"],
    "تكلفة": ["tuition", "cost", "fee", "coa", "net price", "financial"],
    "تكاليف": ["tuition", "cost", "fee", "coa", "financial"],
    "scholarship": ["scholarship", "scholarships", "aid", "financial", "grant", "funding", "tuition"],
    "scholarships": ["scholarship", "scholarships", "aid", "financial", "grant", "funding"],
    "bourse": ["scholarship", "scholarships", "aid", "financial", "grant"],
    "bourses": ["scholarship", "scholarships", "aid", "financial", "grant"],
    "bous": ["scholarship", "scholarships", "aid", "financial", "grant"],
    "beca": ["scholarship", "scholarships", "aid", "financial", "grant"],
    "becas": ["scholarship", "scholarships", "aid", "financial", "grant"],
    "منحة": ["scholarship", "scholarships", "aid", "financial", "grant", "funding"],
    "منح": ["scholarship", "scholarships", "aid", "financial", "grant", "funding"],
    "aid": ["scholarship", "aid", "financial", "need_based", "merit", "grant", "fafsa"],
    "international": ["international", "visa", "i-20", "toefl", "ielts", "foreign", "worldwide"],
    "entènasyonal": ["international", "visa", "i-20", "toefl", "ielts", "foreign"],
    "دولي": ["international", "visa", "toefl", "ielts", "foreign"],
    "الدوليين": ["international", "visa", "toefl", "ielts", "foreign"],
    # Programs & First-Year
    "first-year": ["first_year", "freshman", "secondary", "high school", "sat", "act"],
    "freshman": ["first_year", "freshman", "secondary", "high school"],
    "premye": ["first_year", "freshman", "secondary"],
    "major": ["major", "program", "degree", "cip", "curriculum", "department"],
    "pwogram": ["major", "program", "degree", "curriculum"],
    "تخصص": ["major", "program", "degree", "curriculum"],
    "برامج": ["major", "program", "degree"],
}


def _tokenize(text: str) -> List[str]:
    clean = (text or "").lower()
    # Extract Latin/accented words, Arabic scripts, Devanagari, CJK runs
    words = re.findall(
        r"[a-z0-9\u00c0-\u024f]+|[\u0600-\u06ff]+|[\u0900-\u097f]+|[\u4e00-\u9fff\u3040-\u30ff]+",
        clean,
    )
    tokens: List[str] = []
    for w in words:
        tokens.append(w)
        if w in _CONCEPT_EXPANSIONS:
            tokens.extend(_CONCEPT_EXPANSIONS[w])
        # Subword 3-grams for morphological tolerance across accented/Arabic/compound terms
        if len(w) >= 4:
            for j in range(len(w) - 2):
                tokens.append(w[j : j + 3])
    # Adjacent word bigrams for phrase alignment
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
