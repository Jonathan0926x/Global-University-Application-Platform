"""
Published Course Catalog, Articulation Agreement & Tier 1/Tier 2 Equivalency Seeder.

Populates course-level descriptions, learning outcomes, credit systems (US semester, US quarter,
Canadian FCE, European ECTS), published California CC -> UC/CSU Tier 1 agreements, and Tier 2
historically observed transfer records — strictly idempotently.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.articulation import ArticulationAgreement, CourseCatalog, CourseEquivalency
from app.models.institution import Institution
from app.services.embeddings import embed_text


VERIFIED_AT = datetime(2026, 11, 24, 19, 0, 0, tzinfo=timezone.utc)
CYCLE = "2026-2027"

ASSIST_DEANZA_UCB_URL = "https://assist.org/transfer/results?year=75&institution=113&agreement=79"
ASSIST_DEANZA_UCLA_URL = "https://assist.org/transfer/results?year=75&institution=113&agreement=117"
ASSIST_DEANZA_SFSU_URL = "https://assist.org/transfer/results?year=75&institution=113&agreement=23"
ASSIST_SMC_UCB_URL = "https://assist.org/transfer/results?year=75&institution=137&agreement=79"
UMICH_EQUIV_URL = "https://admissions.umich.edu/apply/transfer-applicants/transfer-credit"


def normalize_course_code(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def _find_inst(db: Session, ipeds: Optional[str] = None, name: Optional[str] = None) -> Optional[Institution]:
    if ipeds:
        inst = db.query(Institution).filter(Institution.ipeds_unit_id == ipeds).first()
        if inst:
            return inst
    if name:
        return db.query(Institution).filter(Institution.official_name == name).first()
    return None


def _upsert_course(db: Session, inst: Institution, data: Dict[str, Any]) -> tuple[CourseCatalog, bool]:
    existing = (
        db.query(CourseCatalog)
        .filter(
            CourseCatalog.institution_id == inst.id,
            CourseCatalog.course_code == data["course_code"],
            CourseCatalog.catalog_year == CYCLE,
        )
        .first()
    )
    if existing:
        return existing, False

    full_text = " ".join(
        [
            data["course_code"],
            data["course_name"],
            data.get("department") or "",
            data.get("description") or "",
            " ".join(data.get("learning_outcomes") or []),
        ]
    )
    course = CourseCatalog(
        institution_id=inst.id,
        course_code=data["course_code"],
        normalized_code=normalize_course_code(data["course_code"]),
        course_name=data["course_name"],
        department=data.get("department"),
        subject_area=data.get("subject_area"),
        description=data.get("description"),
        learning_outcomes=data.get("learning_outcomes") or [],
        prerequisites=data.get("prerequisites"),
        credit_hours=data.get("credit_hours"),
        contact_hours=data.get("contact_hours"),
        credit_system=data.get("credit_system", "us_semester"),
        course_level=data.get("course_level", "lower_division"),
        is_lab=data.get("is_lab", False),
        description_embedding=embed_text(full_text),
        catalog_year=CYCLE,
        source_name=data["source_name"],
        source_url=data.get("source_url"),
        retrieved_at=VERIFIED_AT,
    )
    db.add(course)
    db.flush()
    return course, True


def _upsert_agreement(
    db: Session,
    src: Institution,
    tgt: Institution,
    spec: Dict[str, Any],
) -> tuple[ArticulationAgreement, bool]:
    existing = (
        db.query(ArticulationAgreement)
        .filter(
            ArticulationAgreement.source_institution_id == src.id,
            ArticulationAgreement.target_institution_id == tgt.id,
            ArticulationAgreement.program_name == spec.get("program_name"),
            ArticulationAgreement.academic_year == CYCLE,
        )
        .first()
    )
    if existing:
        return existing, False

    ag = ArticulationAgreement(
        source_institution_id=src.id,
        target_institution_id=tgt.id,
        agreement_type=spec.get("agreement_type", "major_articulation"),
        program_name=spec.get("program_name"),
        cip_code=spec.get("cip_code"),
        academic_year=CYCLE,
        notes=spec.get("notes"),
        source_name=spec["source_name"],
        source_url=spec["source_url"],
        retrieved_at=VERIFIED_AT,
        verified_at=VERIFIED_AT,
        verification_status="verified",
    )
    db.add(ag)
    db.flush()
    return ag, True


def _upsert_equivalency(
    db: Session,
    src_inst: Institution,
    tgt_inst: Institution,
    src_map: Dict[str, CourseCatalog],
    tgt_map: Dict[str, CourseCatalog],
    agreement: Optional[ArticulationAgreement],
    spec: Dict[str, Any],
) -> bool:
    existing = (
        db.query(CourseEquivalency)
        .filter(
            CourseEquivalency.source_institution_id == src_inst.id,
            CourseEquivalency.target_institution_id == tgt_inst.id,
            CourseEquivalency.source_course_code == spec["source_code"],
            CourseEquivalency.target_course_code == spec.get("target_code"),
            CourseEquivalency.equivalency_tier == spec["tier"],
            CourseEquivalency.academic_year == CYCLE,
        )
        .first()
    )
    if existing:
        return False

    src_course = src_map.get(spec["source_code"])
    tgt_course = tgt_map.get(spec.get("target_code") or "")

    eq = CourseEquivalency(
        source_institution_id=src_inst.id,
        source_course_id=src_course.id if src_course else None,
        source_course_code=spec["source_code"],
        source_course_name=spec["source_name_txt"],
        target_institution_id=tgt_inst.id,
        target_course_id=tgt_course.id if tgt_course else None,
        target_course_code=spec.get("target_code"),
        target_course_name=spec.get("target_name_txt"),
        equivalency_tier=spec["tier"],
        equivalency_type=spec.get("type", "direct"),
        confidence_score=spec.get("confidence", 1.0 if spec["tier"] == 1 else 0.85),
        source_credits=spec.get("source_credits"),
        source_credit_system=spec.get("source_credit_system", "us_quarter"),
        target_credits=spec.get("target_credits"),
        target_credit_system=spec.get("target_credit_system", "us_semester"),
        credits_transferable=spec.get("credits_transferable"),
        satisfies_major_requirement=spec.get("major_req", False),
        satisfies_ge_requirement=spec.get("ge_req", False),
        ge_category=spec.get("ge_category"),
        satisfies_prerequisite=spec.get("prereq", False),
        elective_only=spec.get("elective_only", False),
        applies_to_degree_programs=spec.get("programs", []),
        source_type="assist_org" if spec["tier"] == 1 else "historical_transfer_outcome",
        source_name=spec.get("eq_source_name", "ASSIST.org Published Articulation"),
        source_url=spec.get("source_url"),
        articulation_agreement_id=agreement.id if agreement else None,
        supporting_evidence=spec.get("evidence"),
        verified_at=VERIFIED_AT if spec["tier"] == 1 else None,
        academic_year=CYCLE,
        is_current=True,
    )
    db.add(eq)
    return True


def seed_articulation_intelligence(db: Session) -> Dict[str, int]:
    """
    Seeds published California & international course catalogs, articulation agreements,
    and Tier 1 / Tier 2 equivalencies cleanly and idempotently.
    """
    stats = {
        "catalog_courses_created": 0,
        "agreements_created": 0,
        "equivalencies_created": 0,
    }

    de_anza = _find_inst(db, ipeds="113333")
    smc = _find_inst(db, ipeds="122977")
    ucb = _find_inst(db, ipeds="110635")
    ucla = _find_inst(db, ipeds="110662")
    sfsu = _find_inst(db, ipeds="122597")
    umich = _find_inst(db, ipeds="170976")
    uoft = _find_inst(db, name="University of Toronto")
    tum = _find_inst(db, name="Technical University of Munich")
    sorbonne = _find_inst(db, name="Sorbonne Université")

    # 1. Course Catalog Entries
    catalog_specs: List[tuple[Optional[Institution], List[Dict[str, Any]]]] = [
        (
            de_anza,
            [
                {"course_code": "EWRT 1A", "course_name": "Composition and Reading", "department": "English", "subject_area": "english_composition", "credit_hours": 5.0, "credit_system": "us_quarter", "course_level": "100", "description": "Expository writing, critical reading, analytical essays, rhetoric, and academic research.", "learning_outcomes": ["Write well-structured analytical essays", "Evaluate scholarly sources", "Apply rhetorical strategies"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "EWRT 2", "course_name": "Critical Reading, Writing and Thinking", "department": "English", "subject_area": "english_composition", "credit_hours": 5.0, "credit_system": "us_quarter", "course_level": "100", "prerequisites": "EWRT 1A", "description": "Advanced critical thinking, inductive/deductive logic, persuasive research writing.", "learning_outcomes": ["Analyze complex arguments", "Compose sustained researched essays"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "MATH 1A", "course_name": "Calculus", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 5.0, "credit_system": "us_quarter", "course_level": "100", "description": "Limits, continuity, derivatives, differentiation rules, implicit differentiation, optimization, related rates.", "learning_outcomes": ["Compute limits and derivatives", "Solve optimization and rate problems"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "MATH 1B", "course_name": "Calculus", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 5.0, "credit_system": "us_quarter", "course_level": "100", "prerequisites": "MATH 1A", "description": "Definite and indefinite integrals, Fundamental Theorem of Calculus, techniques of integration, volumes.", "learning_outcomes": ["Evaluate integrals using substitution and integration by parts", "Calculate areas and volumes"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "MATH 1C", "course_name": "Calculus", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 5.0, "credit_system": "us_quarter", "course_level": "100", "prerequisites": "MATH 1B", "description": "Infinite sequences and series, Taylor polynomials, parametric equations, vectors in space.", "learning_outcomes": ["Test convergence of power series", "Compute Taylor approximations"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "MATH 2B", "course_name": "Linear Algebra", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 5.0, "credit_system": "us_quarter", "course_level": "200", "prerequisites": "MATH 1C", "description": "Matrices, determinants, vector spaces, eigenvalues, eigenvectors, orthogonality, linear transformations.", "learning_outcomes": ["Solve linear systems via Gaussian elimination", "Compute eigenvalues and diagonalize matrices"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "MATH 22", "course_name": "Discrete Mathematics", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 5.0, "credit_system": "us_quarter", "course_level": "200", "description": "Propositional logic, mathematical induction, set theory, combinatorics, graph theory, recurrence relations.", "learning_outcomes": ["Construct formal induction proofs", "Analyze graphs and discrete structures"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "CIS 22A", "course_name": "Beginning Programming Methodologies in C++", "department": "Computer Information Systems", "subject_area": "computer_science", "credit_hours": 4.5, "credit_system": "us_quarter", "course_level": "100", "is_lab": True, "description": "Structured programming, variables, control flow, functions, arrays, file I/O, debugging in C++.", "learning_outcomes": ["Design procedural programs in C++", "Debug control structures and arrays"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "CIS 22B", "course_name": "Intermediate Programming Methodologies in C++", "department": "Computer Information Systems", "subject_area": "computer_science", "credit_hours": 4.5, "credit_system": "us_quarter", "course_level": "100", "is_lab": True, "prerequisites": "CIS 22A", "description": "Object-oriented programming, pointers, dynamic memory allocation, classes, inheritance, polymorphism.", "learning_outcomes": ["Implement OOP classes and inheritance hierarchies", "Manage dynamic pointers safely"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "CIS 22C", "course_name": "Data Abstraction and Structures", "department": "Computer Information Systems", "subject_area": "computer_science", "credit_hours": 4.5, "credit_system": "us_quarter", "course_level": "200", "is_lab": True, "prerequisites": "CIS 22B", "description": "Abstract data types, linked lists, stacks, queues, binary search trees, balanced trees, hash tables, graphs, sorting.", "learning_outcomes": ["Implement trees, heaps, and graphs", "Analyze asymptotic Big-O algorithm complexity"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "ECON 1", "course_name": "Principles of Macroeconomics", "department": "Economics", "subject_area": "economics", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "100", "description": "National income accounting, GDP, inflation, unemployment, monetary policy, fiscal policy, aggregate supply/demand.", "learning_outcomes": ["Analyze macroeconomic fiscal and monetary policy", "Interpret GDP and inflation indicators"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "ECON 2", "course_name": "Principles of Microeconomics", "department": "Economics", "subject_area": "economics", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "100", "description": "Supply and demand, price elasticity, consumer utility, production costs, perfect competition, monopoly.", "learning_outcomes": ["Model supply, demand, and market equilibrium", "Evaluate firm cost structures and competition"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "PHYS 4A", "course_name": "Physics for Scientists and Engineers: Mechanics", "department": "Physics", "subject_area": "physics", "credit_hours": 6.0, "credit_system": "us_quarter", "course_level": "100", "is_lab": True, "description": "Calculus-based mechanics, kinematics, Newton's laws, conservation of energy and momentum, rotational dynamics.", "learning_outcomes": ["Apply Newton's laws and conservation principles using calculus"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "ART 1A", "course_name": "History of Art: Prehistoric through Gothic", "department": "Art History", "subject_area": "humanities", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "100", "description": "Survey of Western painting, sculpture, and architecture from prehistoric times through the Gothic period.", "learning_outcomes": ["Analyze visual artworks in historical context"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
                {"course_code": "PE 1", "course_name": "Lifetime Fitness & Conditioning", "department": "Physical Education", "subject_area": "elective_activity", "credit_hours": 1.0, "credit_system": "us_quarter", "course_level": "100", "description": "Cardiovascular conditioning and personal physical fitness activity course.", "learning_outcomes": ["Develop personal wellness training plan"], "source_name": "De Anza College Catalog", "source_url": "https://www.deanza.edu/catalog/"},
            ],
        ),
        (
            smc,
            [
                {"course_code": "ENGL 1", "course_name": "Reading and Composition 1", "department": "English", "subject_area": "english_composition", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "100", "description": "Introductory college expository writing and rhetorical reading.", "learning_outcomes": ["Compose thesis-driven academic essays"], "source_name": "Santa Monica College Catalog", "source_url": "https://www.smc.edu/"},
                {"course_code": "MATH 7", "course_name": "Calculus 1", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 5.0, "credit_system": "us_semester", "course_level": "100", "description": "Differential and integral calculus of one variable, limits, derivatives, Fundamental Theorem.", "learning_outcomes": ["Solve differential and basic integral calculus problems"], "source_name": "Santa Monica College Catalog", "source_url": "https://www.smc.edu/"},
                {"course_code": "MATH 8", "course_name": "Calculus 2", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 5.0, "credit_system": "us_semester", "course_level": "100", "prerequisites": "MATH 7", "description": "Integration techniques, improper integrals, infinite sequences and series, Taylor series.", "learning_outcomes": ["Master integration techniques and series convergence"], "source_name": "Santa Monica College Catalog", "source_url": "https://www.smc.edu/"},
                {"course_code": "ECON 1", "course_name": "Principles of Microeconomics", "department": "Economics", "subject_area": "economics", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "100", "description": "Microeconomic market pricing, elasticity, consumer choice, firm production and market structures.", "learning_outcomes": ["Evaluate supply, demand, and market competition"], "source_name": "Santa Monica College Catalog", "source_url": "https://www.smc.edu/"},
                {"course_code": "ECON 2", "course_name": "Principles of Macroeconomics", "department": "Economics", "subject_area": "economics", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "100", "description": "Macroeconomic GDP, inflation, unemployment, central bank monetary policy, fiscal policy.", "learning_outcomes": ["Analyze macroeconomic stabilization policies"], "source_name": "Santa Monica College Catalog", "source_url": "https://www.smc.edu/"},
            ],
        ),
        (
            ucb,
            [
                {"course_code": "ENGLISH R1A", "course_name": "Reading and Composition", "department": "English", "subject_area": "english_composition", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Training in expository composition and analytical reading of literature and rhetoric.", "learning_outcomes": ["Write analytical essays with textual evidence"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/english/"},
                {"course_code": "ENGLISH R1B", "course_name": "Reading and Composition", "department": "English", "subject_area": "english_composition", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Research-oriented reading and writing sequence fulfilling Reading & Composition part B.", "learning_outcomes": ["Conduct independent critical research writing"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/english/"},
                {"course_code": "MATH 1A", "course_name": "Calculus", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Functions, limits, derivatives, definite and indefinite integrals of one variable, optimization.", "learning_outcomes": ["Apply differential and integral calculus of one variable"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/math/"},
                {"course_code": "MATH 1B", "course_name": "Calculus", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Techniques of integration, infinite series, Taylor series, differential equations.", "learning_outcomes": ["Evaluate advanced integrals and infinite series"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/math/"},
                {"course_code": "MATH 54", "course_name": "Linear Algebra and Differential Equations", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "200", "description": "Vector spaces, matrices, determinants, eigenvalues, linear differential equations.", "learning_outcomes": ["Solve linear systems, eigenvalue problems, and ODEs"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/math/"},
                {"course_code": "COMPSCI 61A", "course_name": "The Structure and Interpretation of Computer Programs", "department": "Computer Science", "subject_area": "computer_science", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Programming paradigms, higher-order functions, recursion, data abstraction, OOP, interpreters.", "learning_outcomes": ["Design abstractions using functional and object-oriented programming"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/compsci/"},
                {"course_code": "COMPSCI 61B", "course_name": "Data Structures", "department": "Computer Science", "subject_area": "computer_science", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "200", "description": "Fundamental data structures, linked lists, trees, hash tables, graphs, sorting algorithms, asymptotic complexity.", "learning_outcomes": ["Implement efficient trees, hash tables, graphs, and sorting algorithms"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/compsci/"},
                {"course_code": "ECON 1", "course_name": "Introduction to Economics", "department": "Economics", "subject_area": "economics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Unified introduction to microeconomic supply/demand and macroeconomic GDP, inflation, monetary/fiscal policy.", "learning_outcomes": ["Analyze microeconomic markets and macroeconomic policy"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/econ/"},
                {"course_code": "PHYSICS 7A", "course_name": "Physics for Scientists and Engineers", "department": "Physics", "subject_area": "physics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "is_lab": True, "description": "Mechanics and wave motion using calculus.", "learning_outcomes": ["Model physical mechanics problems with calculus"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/physics/"},
                {"course_code": "HISTART 1A", "course_name": "Introduction to Western Art: Ancient through Medieval", "department": "History of Art", "subject_area": "humanities", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Historical survey of ancient and medieval art and architecture.", "learning_outcomes": ["Interpret historical artistic movements"], "source_name": "UC Berkeley Guide", "source_url": "https://guide.berkeley.edu/courses/histart/"},
            ],
        ),
        (
            ucla,
            [
                {"course_code": "ENGCOMP 3", "course_name": "English Composition, Rhetoric, and Language", "department": "Writing Programs", "subject_area": "english_composition", "credit_hours": 5.0, "credit_system": "us_quarter", "course_level": "100", "description": "Expository writing, critical reading, rhetorical argument.", "learning_outcomes": ["Write college-level rhetorical essays"], "source_name": "UCLA Catalog", "source_url": "https://catalog.registrar.ucla.edu/"},
                {"course_code": "MATH 31A", "course_name": "Differential and Integral Calculus", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "100", "description": "Differential calculus and basic integral calculus of one variable.", "learning_outcomes": ["Compute derivatives and fundamental integrals"], "source_name": "UCLA Catalog", "source_url": "https://catalog.registrar.ucla.edu/"},
                {"course_code": "MATH 31B", "course_name": "Integration and Infinite Series", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "100", "description": "Integration techniques, improper integrals, infinite sequences and series.", "learning_outcomes": ["Analyze Taylor series and integration techniques"], "source_name": "UCLA Catalog", "source_url": "https://catalog.registrar.ucla.edu/"},
                {"course_code": "COM SCI 31", "course_name": "Introduction to Computer Science I", "department": "Computer Science", "subject_area": "computer_science", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "100", "description": "Introduction to algorithmic thinking and object-oriented programming in C++.", "learning_outcomes": ["Build modular C++ programs using arrays, pointers, classes"], "source_name": "UCLA Catalog", "source_url": "https://catalog.registrar.ucla.edu/"},
                {"course_code": "COM SCI 32", "course_name": "Introduction to Computer Science II", "department": "Computer Science", "subject_area": "computer_science", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "200", "description": "Object-oriented software development, data structures, recursion, sorting, graphs, asymptotic analysis.", "learning_outcomes": ["Design data structures including trees, hash tables, graphs"], "source_name": "UCLA Catalog", "source_url": "https://catalog.registrar.ucla.edu/"},
                {"course_code": "ECON 1", "course_name": "Principles of Economics (Microeconomics)", "department": "Economics", "subject_area": "economics", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "100", "description": "Microeconomic theory of markets, supply, demand, consumer and firm decisions.", "learning_outcomes": ["Analyze market pricing and competition"], "source_name": "UCLA Catalog", "source_url": "https://catalog.registrar.ucla.edu/"},
                {"course_code": "ECON 2", "course_name": "Principles of Economics (Macroeconomics)", "department": "Economics", "subject_area": "economics", "credit_hours": 4.0, "credit_system": "us_quarter", "course_level": "100", "description": "Macroeconomic output, inflation, unemployment, monetary and fiscal policies.", "learning_outcomes": ["Evaluate national income and monetary policy"], "source_name": "UCLA Catalog", "source_url": "https://catalog.registrar.ucla.edu/"},
            ],
        ),
        (
            sfsu,
            [
                {"course_code": "ENG 114", "course_name": "Writing the First Year: Finding Your Voice", "department": "English", "subject_area": "english_composition", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "100", "description": "College composition, reading, rhetoric, and critical thinking.", "learning_outcomes": ["Compose critical academic essays"], "source_name": "SFSU Bulletin", "source_url": "https://bulletin.sfsu.edu/"},
                {"course_code": "ENG 214", "course_name": "Second Year Written Composition", "department": "English", "subject_area": "english_composition", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "200", "description": "Analytical and researched writing across disciplines.", "learning_outcomes": ["Synthesize academic sources into research writing"], "source_name": "SFSU Bulletin", "source_url": "https://bulletin.sfsu.edu/"},
                {"course_code": "MATH 226", "course_name": "Calculus I", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "200", "description": "Limits, derivatives, optimization, and fundamental integral calculus.", "learning_outcomes": ["Differentiate and integrate single-variable functions"], "source_name": "SFSU Bulletin", "source_url": "https://bulletin.sfsu.edu/"},
                {"course_code": "CSC 210", "course_name": "Introduction to Computer Programming", "department": "Computer Science", "subject_area": "computer_science", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "200", "description": "Design, implementation, testing, and debugging of structured programs.", "learning_outcomes": ["Write modular programs using control structures and arrays"], "source_name": "SFSU Bulletin", "source_url": "https://bulletin.sfsu.edu/"},
                {"course_code": "CSC 220", "course_name": "Data Structures", "department": "Computer Science", "subject_area": "computer_science", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "200", "description": "Abstract data types, trees, graphs, hash tables, recursion, sorting algorithms.", "learning_outcomes": ["Implement fundamental data structures and algorithms"], "source_name": "SFSU Bulletin", "source_url": "https://bulletin.sfsu.edu/"},
                {"course_code": "ECON 101", "course_name": "Introduction to Microeconomic Analysis", "department": "Economics", "subject_area": "economics", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "100", "description": "Consumer behavior, price determination, firm cost curves, market competition.", "learning_outcomes": ["Apply microeconomic tools to resource allocation"], "source_name": "SFSU Bulletin", "source_url": "https://bulletin.sfsu.edu/"},
                {"course_code": "ECON 102", "course_name": "Introduction to Macroeconomic Analysis", "department": "Economics", "subject_area": "economics", "credit_hours": 3.0, "credit_system": "us_semester", "course_level": "100", "description": "GDP, inflation, unemployment, fiscal and monetary stabilization.", "learning_outcomes": ["Explain aggregate economic fluctuations"], "source_name": "SFSU Bulletin", "source_url": "https://bulletin.sfsu.edu/"},
            ],
        ),
        (
            umich,
            [
                {"course_code": "MATH 115", "course_name": "Calculus I", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Functions, limits, derivatives, definite integrals, and applications.", "learning_outcomes": ["Model change using differential calculus"], "source_name": "UMich LSA Guide", "source_url": "https://lsa.umich.edu/"},
                {"course_code": "ECON 101", "course_name": "Principles of Economics I (Microeconomics)", "department": "Economics", "subject_area": "economics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Microeconomic market theory, supply/demand, firm decisions, welfare.", "learning_outcomes": ["Evaluate competitive and monopolistic markets"], "source_name": "UMich LSA Guide", "source_url": "https://lsa.umich.edu/"},
                {"course_code": "ECON 102", "course_name": "Principles of Economics II (Macroeconomics)", "department": "Economics", "subject_area": "economics", "credit_hours": 4.0, "credit_system": "us_semester", "course_level": "100", "description": "Macroeconomic growth, inflation, monetary policy, open economy.", "learning_outcomes": ["Analyze macroeconomic fluctuations and central bank policy"], "source_name": "UMich LSA Guide", "source_url": "https://lsa.umich.edu/"},
            ],
        ),
        (
            uoft,
            [
                {"course_code": "MAT137Y1", "course_name": "Calculus with Proofs", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 1.0, "credit_system": "ca_credit", "course_level": "100", "description": "Rigorous differential and integral calculus with formal epsilon-delta proofs and infinite series.", "learning_outcomes": ["Write rigorous mathematical proofs in single-variable calculus"], "source_name": "U of T Arts & Science Calendar", "source_url": "https://artsci.calendar.utoronto.ca/"},
                {"course_code": "CSC148H1", "course_name": "Introduction to Computer Science", "department": "Computer Science", "subject_area": "computer_science", "credit_hours": 0.5, "credit_system": "ca_credit", "course_level": "100", "description": "Abstract data types, recursion, linked lists, trees, algorithmic complexity analysis.", "learning_outcomes": ["Implement recursive data structures in Python/OOP"], "source_name": "U of T Arts & Science Calendar", "source_url": "https://artsci.calendar.utoronto.ca/"},
            ],
        ),
        (
            tum,
            [
                {"course_code": "IN0007", "course_name": "Fundamentals of Algorithms and Data Structures", "department": "Informatics", "subject_area": "computer_science", "credit_hours": 6.0, "credit_system": "ects", "course_level": "100", "description": "Asymptotic complexity, sorting, search trees, hashing, graph traversal, dynamic programming.", "learning_outcomes": ["Design and analyze classic algorithms and data structures"], "source_name": "TUM Module Catalog", "source_url": "https://www.tum.de/en/studies"},
                {"course_code": "MA0901", "course_name": "Linear Algebra for Informatics", "department": "Mathematics", "subject_area": "mathematics", "credit_hours": 8.0, "credit_system": "ects", "course_level": "100", "description": "Vector spaces, matrices, linear maps, eigenvalues, inner products.", "learning_outcomes": ["Prove linear algebraic properties and compute decompositions"], "source_name": "TUM Module Catalog", "source_url": "https://www.tum.de/en/studies"},
            ],
        ),
        (
            sorbonne,
            [
                {"course_code": "LU1MA001", "course_name": "Mathématiques pour les sciences (Calcul différentiel et intégral)", "department": "Mathématiques", "subject_area": "mathematics", "credit_hours": 9.0, "credit_system": "ects", "course_level": "100", "description": "Limites, dérivation, calcul intégral, séries et vecteurs pour les sciences.", "learning_outcomes": ["Maîtriser le calcul différentiel et intégral"], "source_name": "Sorbonne Université Catalogue", "source_url": "https://www.sorbonne-universite.fr/"},
            ],
        ),
    ]

    catalog_maps: Dict[str, Dict[str, CourseCatalog]] = {}
    for inst, items in catalog_specs:
        if not inst:
            continue
        c_map: Dict[str, CourseCatalog] = {}
        for item in items:
            obj, created = _upsert_course(db, inst, item)
            c_map[item["course_code"]] = obj
            if created:
                stats["catalog_courses_created"] += 1
        catalog_maps[str(inst.id)] = c_map

    # 2. Published Articulation Agreements & Tier 1 / Tier 2 Equivalencies
    if de_anza and ucb:
        ag_ucb, ag_c = _upsert_agreement(
            db, de_anza, ucb,
            {
                "agreement_type": "major_articulation",
                "program_name": "Economics & Computer Science / UC General Articulation",
                "cip_code": "45",
                "notes": "Quarter-to-semester conversion factor is 2/3 (e.g., 5.0 quarter units = 3.33 semester units). Multi-part math series must be completed at the same campus.",
                "source_name": "ASSIST.org De Anza to UC Berkeley Articulation",
                "source_url": ASSIST_DEANZA_UCB_URL,
            },
        )
        if ag_c:
            stats["agreements_created"] += 1

        ucb_eqs = [
            {"source_code": "EWRT 1A", "source_name_txt": "Composition and Reading", "target_code": "ENGLISH R1A", "target_name_txt": "Reading and Composition (Part A)", "tier": 1, "type": "direct", "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 3.33, "ge_req": True, "ge_category": "UC 7-Course: English Composition / IGETC 1A", "prereq": True, "programs": ["All", "Economics", "Computer Science"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Officially articulated in ASSIST IGETC Area 1A & UC Berkeley R&C Part A."},
            {"source_code": "EWRT 2", "source_name_txt": "Critical Reading, Writing and Thinking", "target_code": "ENGLISH R1B", "target_name_txt": "Reading and Composition (Part B)", "tier": 1, "type": "direct", "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 3.33, "ge_req": True, "ge_category": "UC 7-Course: English Composition / IGETC 1B", "prereq": True, "programs": ["All", "Economics", "Computer Science"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Officially articulated for UC Berkeley R&C Part B."},
            {"source_code": "MATH 1A", "source_name_txt": "Calculus I (Series Part 1)", "target_code": "MATH 1A", "target_name_txt": "Calculus I (Requires De Anza MATH 1A + 1B for full equiv)", "tier": 1, "type": "combined", "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 3.33, "major_req": True, "ge_req": True, "ge_category": "UC 7-Course: Mathematical Concepts", "prereq": True, "programs": ["Economics", "Computer Science"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Quarter-to-semester sequence rule: complete MATH 1A + MATH 1B at De Anza for UC Berkeley MATH 1A."},
            {"source_code": "MATH 1B", "source_name_txt": "Calculus II (Integrals)", "target_code": "MATH 1A", "target_name_txt": "Completes UC Berkeley MATH 1A w/ De Anza MATH 1A", "tier": 1, "type": "combined", "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 3.33, "major_req": True, "ge_req": True, "ge_category": "UC 7-Course: Mathematical Concepts", "prereq": True, "programs": ["Economics", "Computer Science"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Completes single-variable Differential/Integral Calculus sequence w/ MATH 1A."},
            {"source_code": "MATH 1C", "source_name_txt": "Calculus III (Series & Sequences)", "target_code": "MATH 1B", "target_name_txt": "Calculus II (Series equiv when paired w/ MATH 1D)", "tier": 1, "type": "combined", "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 3.33, "major_req": True, "prereq": True, "programs": ["Economics", "Computer Science"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Covers infinite series and Taylor expansions required for Berkeley MATH 1B."},
            {"source_code": "MATH 2B", "source_name_txt": "Linear Algebra", "target_code": "MATH 54", "target_name_txt": "Linear Algebra & Differential Equations (Partial — Linear Algebra half)", "tier": 1, "type": "partial", "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 3.33, "major_req": True, "prereq": True, "programs": ["Computer Science"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Satisfies linear algebra component of Berkeley MATH 54 (Differential Equations MATH 2A also required for full MATH 54)."},
            {"source_code": "ECON 1", "source_name_txt": "Principles of Macroeconomics", "target_code": "ECON 1", "target_name_txt": "Introduction to Economics (Macro half — requires ECON 1 + ECON 2)", "tier": 1, "type": "combined", "source_credits": 4.0, "target_credits": 4.0, "credits_transferable": 2.67, "major_req": True, "ge_req": True, "ge_category": "Social & Behavioral Sciences", "prereq": True, "programs": ["Economics"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "UC Berkeley combines Micro and Macro into ECON 1; both De Anza ECON 1 & ECON 2 must be completed."},
            {"source_code": "ECON 2", "source_name_txt": "Principles of Microeconomics", "target_code": "ECON 1", "target_name_txt": "Introduction to Economics (Micro half — requires ECON 1 + ECON 2)", "tier": 1, "type": "combined", "source_credits": 4.0, "target_credits": 4.0, "credits_transferable": 2.67, "major_req": True, "ge_req": True, "ge_category": "Social & Behavioral Sciences", "prereq": True, "programs": ["Economics"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Completes UC Berkeley ECON 1 requirement when paired with De Anza ECON 1."},
            {"source_code": "CIS 22C", "source_name_txt": "Data Abstraction and Structures", "target_code": "COMPSCI 61B", "target_name_txt": "Data Structures (Partial articulation — requires CS 47B bridge at Berkeley)", "tier": 1, "type": "partial", "confidence": 0.90, "source_credits": 4.5, "target_credits": 4.0, "credits_transferable": 3.0, "major_req": False, "prereq": True, "programs": ["Computer Science"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "ASSIST lists CIS 22C as partial match for COMPSCI 61B; UC Berkeley requires self-paced COMPSCI 47B post-transfer unless full Java/Git series articulated."},
            {"source_code": "PHYS 4A", "source_name_txt": "Physics: Mechanics", "target_code": "PHYSICS 7A", "target_name_txt": "Physics for Scientists and Engineers", "tier": 1, "type": "direct", "source_credits": 6.0, "target_credits": 4.0, "credits_transferable": 4.0, "ge_req": True, "ge_category": "UC 7-Course: Physical Sciences", "programs": ["All", "Computer Science"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Direct UC transferable calculus-based mechanics lab course."},
            {"source_code": "ART 1A", "source_name_txt": "History of Art", "target_code": "HISTART 1A", "target_name_txt": "Western Art: Ancient through Medieval", "tier": 1, "type": "direct", "source_credits": 4.0, "target_credits": 4.0, "credits_transferable": 2.67, "ge_req": True, "ge_category": "UC 7-Course: Arts & Humanities", "major_req": False, "programs": ["All"], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "Satisfies Arts & Humanities GE breadth; does not count toward Economics or CS major requirements."},
            {"source_code": "PE 1", "source_name_txt": "Lifetime Fitness & Conditioning", "target_code": None, "target_name_txt": "UC Elective Activity Credit Only (Subject to 4-unit PE cap)", "tier": 1, "type": "elective_only", "source_credits": 1.0, "target_credits": 0.67, "credits_transferable": 0.67, "elective_only": True, "major_req": False, "ge_req": False, "programs": [], "source_url": ASSIST_DEANZA_UCB_URL, "evidence": "UC accepts up to 4 semester units of Physical Education activity courses toward total units only; does not satisfy GE or major requirements."},
        ]
        for eq_s in ucb_eqs:
            if _upsert_equivalency(db, de_anza, ucb, catalog_maps.get(str(de_anza.id), {}), catalog_maps.get(str(ucb.id), {}), ag_ucb, eq_s):
                stats["equivalencies_created"] += 1

    if de_anza and ucla:
        ag_ucla, ag_c = _upsert_agreement(
            db, de_anza, ucla,
            {"agreement_type": "major_articulation", "program_name": "Computer Science & Economics Articulation", "source_name": "ASSIST.org De Anza to UCLA", "source_url": ASSIST_DEANZA_UCLA_URL},
        )
        if ag_c:
            stats["agreements_created"] += 1
        ucla_eqs = [
            {"source_code": "EWRT 1A", "source_name_txt": "Composition and Reading", "target_code": "ENGCOMP 3", "target_name_txt": "English Composition, Rhetoric, and Language", "tier": 1, "type": "direct", "source_credits": 5.0, "target_credits": 5.0, "credits_transferable": 5.0, "target_credit_system": "us_quarter", "ge_req": True, "ge_category": "UC 7-Course: English Composition", "programs": ["All"], "source_url": ASSIST_DEANZA_UCLA_URL, "evidence": "Both institutions operate on quarter units (5.0 quarter units transfer 1:1)."},
            {"source_code": "MATH 1A", "source_name_txt": "Calculus I", "target_code": "MATH 31A", "target_name_txt": "Differential and Integral Calculus", "tier": 1, "type": "direct", "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 4.0, "target_credit_system": "us_quarter", "major_req": True, "ge_req": True, "ge_category": "Quantitative Reasoning", "prereq": True, "programs": ["Economics", "Computer Science"], "source_url": ASSIST_DEANZA_UCLA_URL, "evidence": "Published ASSIST direct equivalent for UCLA MATH 31A."},
            {"source_code": "MATH 1B", "source_name_txt": "Calculus II", "target_code": "MATH 31B", "target_name_txt": "Integration and Infinite Series", "tier": 1, "type": "combined", "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 4.0, "target_credit_system": "us_quarter", "major_req": True, "prereq": True, "programs": ["Economics", "Computer Science"], "source_url": ASSIST_DEANZA_UCLA_URL, "evidence": "Combined De Anza MATH 1B + 1C maps to UCLA MATH 31B."},
            {"source_code": "CIS 22B", "source_name_txt": "Intermediate Programming in C++", "target_code": "COM SCI 31", "target_name_txt": "Introduction to Computer Science I", "tier": 1, "type": "combined", "source_credits": 4.5, "target_credits": 4.0, "credits_transferable": 4.5, "target_credit_system": "us_quarter", "major_req": True, "prereq": True, "programs": ["Computer Science"], "source_url": ASSIST_DEANZA_UCLA_URL, "evidence": "De Anza CIS 22A + CIS 22B articulates to UCLA COM SCI 31."},
            {"source_code": "CIS 22C", "source_name_txt": "Data Abstraction and Structures", "target_code": "COM SCI 32", "target_name_txt": "Introduction to Computer Science II", "tier": 1, "type": "direct", "source_credits": 4.5, "target_credits": 4.0, "credits_transferable": 4.5, "target_credit_system": "us_quarter", "major_req": True, "prereq": True, "programs": ["Computer Science"], "source_url": ASSIST_DEANZA_UCLA_URL, "evidence": "Direct C++ Data Structures articulation per ASSIST UCLA CS agreement."},
            {"source_code": "ECON 1", "source_name_txt": "Principles of Macroeconomics", "target_code": "ECON 2", "target_name_txt": "Principles of Economics (Macro)", "tier": 1, "type": "direct", "source_credits": 4.0, "target_credits": 4.0, "credits_transferable": 4.0, "target_credit_system": "us_quarter", "major_req": True, "ge_req": True, "ge_category": "Social Sciences", "prereq": True, "programs": ["Economics"], "source_url": ASSIST_DEANZA_UCLA_URL, "evidence": "Note numbering swap: De Anza ECON 1 (Macro) = UCLA ECON 2 (Macro)."},
            {"source_code": "ECON 2", "source_name_txt": "Principles of Microeconomics", "target_code": "ECON 1", "target_name_txt": "Principles of Economics (Micro)", "tier": 1, "type": "direct", "source_credits": 4.0, "target_credits": 4.0, "credits_transferable": 4.0, "target_credit_system": "us_quarter", "major_req": True, "ge_req": True, "ge_category": "Social Sciences", "prereq": True, "programs": ["Economics"], "source_url": ASSIST_DEANZA_UCLA_URL, "evidence": "De Anza ECON 2 (Micro) = UCLA ECON 1 (Micro)."},
        ]
        for eq_s in ucla_eqs:
            if _upsert_equivalency(db, de_anza, ucla, catalog_maps.get(str(de_anza.id), {}), catalog_maps.get(str(ucla.id), {}), ag_ucla, eq_s):
                stats["equivalencies_created"] += 1

    if de_anza and sfsu:
        ag_sfsu, ag_c = _upsert_agreement(
            db, de_anza, sfsu,
            {"agreement_type": "major_articulation", "program_name": "Computer Science & Economics (CSU Transfer)", "source_name": "ASSIST.org De Anza to SFSU", "source_url": ASSIST_DEANZA_SFSU_URL},
        )
        if ag_c:
            stats["agreements_created"] += 1
        sfsu_eqs = [
            {"source_code": "EWRT 1A", "source_name_txt": "Composition and Reading", "target_code": "ENG 114", "target_name_txt": "Writing the First Year", "tier": 1, "type": "direct", "source_credits": 5.0, "target_credits": 3.0, "credits_transferable": 3.33, "ge_req": True, "ge_category": "CSU GE Area A2", "programs": ["All"], "source_url": ASSIST_DEANZA_SFSU_URL, "evidence": "Satisfies CSU Golden Four Area A2 Written Communication."},
            {"source_code": "EWRT 2", "source_name_txt": "Critical Reading, Writing and Thinking", "target_code": "ENG 214", "target_name_txt": "Second Year Written Composition", "tier": 1, "type": "direct", "source_credits": 5.0, "target_credits": 3.0, "credits_transferable": 3.33, "ge_req": True, "ge_category": "CSU GE Area A3", "programs": ["All"], "source_url": ASSIST_DEANZA_SFSU_URL, "evidence": "Satisfies CSU GE Area A3 Critical Thinking."},
            {"source_code": "CIS 22A", "source_name_txt": "Beginning Programming Methodologies in C++", "target_code": "CSC 210", "target_name_txt": "Introduction to Computer Programming", "tier": 1, "type": "direct", "source_credits": 4.5, "target_credits": 3.0, "credits_transferable": 3.0, "major_req": True, "prereq": True, "programs": ["Computer Science"], "source_url": ASSIST_DEANZA_SFSU_URL, "evidence": "Direct CS core programming equivalent at SFSU."},
            {"source_code": "CIS 22C", "source_name_txt": "Data Abstraction and Structures", "target_code": "CSC 220", "target_name_txt": "Data Structures", "tier": 1, "type": "direct", "source_credits": 4.5, "target_credits": 3.0, "credits_transferable": 3.0, "major_req": True, "prereq": True, "programs": ["Computer Science"], "source_url": ASSIST_DEANZA_SFSU_URL, "evidence": "Direct CS Data Structures equivalent when preceded by CIS 22B."},
            {"source_code": "ECON 1", "source_name_txt": "Principles of Macroeconomics", "target_code": "ECON 102", "target_name_txt": "Introduction to Macroeconomic Analysis", "tier": 1, "type": "direct", "source_credits": 4.0, "target_credits": 3.0, "credits_transferable": 2.67, "major_req": True, "ge_req": True, "ge_category": "CSU GE Area D", "prereq": True, "programs": ["Economics"], "source_url": ASSIST_DEANZA_SFSU_URL, "evidence": "Direct Macro Economics equivalent for SFSU B.A. Economics."},
            {"source_code": "ECON 2", "source_name_txt": "Principles of Microeconomics", "target_code": "ECON 101", "target_name_txt": "Introduction to Microeconomic Analysis", "tier": 1, "type": "direct", "source_credits": 4.0, "target_credits": 3.0, "credits_transferable": 2.67, "major_req": True, "ge_req": True, "ge_category": "CSU GE Area D", "prereq": True, "programs": ["Economics"], "source_url": ASSIST_DEANZA_SFSU_URL, "evidence": "Direct Micro Economics equivalent for SFSU B.A. Economics."},
        ]
        for eq_s in sfsu_eqs:
            if _upsert_equivalency(db, de_anza, sfsu, catalog_maps.get(str(de_anza.id), {}), catalog_maps.get(str(sfsu.id), {}), ag_sfsu, eq_s):
                stats["equivalencies_created"] += 1

    if smc and ucb:
        ag_smc, ag_c = _upsert_agreement(
            db, smc, ucb,
            {"agreement_type": "major_articulation", "program_name": "Santa Monica College -> UC Berkeley", "source_name": "ASSIST.org SMC to UC Berkeley", "source_url": ASSIST_SMC_UCB_URL},
        )
        if ag_c:
            stats["agreements_created"] += 1
        smc_eqs = [
            {"source_code": "ENGL 1", "source_name_txt": "Reading and Composition 1", "target_code": "ENGLISH R1A", "target_name_txt": "Reading and Composition (Part A)", "tier": 1, "type": "direct", "source_credits": 3.0, "source_credit_system": "us_semester", "target_credits": 4.0, "credits_transferable": 3.0, "ge_req": True, "ge_category": "UC 7-Course: English Composition", "programs": ["All"], "source_url": ASSIST_SMC_UCB_URL, "evidence": "Semester-to-semester direct articulation."},
            {"source_code": "MATH 7", "source_name_txt": "Calculus 1", "target_code": "MATH 1A", "target_name_txt": "Calculus I", "tier": 1, "type": "direct", "source_credits": 5.0, "source_credit_system": "us_semester", "target_credits": 4.0, "credits_transferable": 5.0, "major_req": True, "ge_req": True, "ge_category": "UC 7-Course: Mathematical Concepts", "prereq": True, "programs": ["Economics", "Computer Science"], "source_url": ASSIST_SMC_UCB_URL, "evidence": "Direct single-variable Calculus I articulation."},
            {"source_code": "MATH 8", "source_name_txt": "Calculus 2", "target_code": "MATH 1B", "target_name_txt": "Calculus II", "tier": 1, "type": "direct", "source_credits": 5.0, "source_credit_system": "us_semester", "target_credits": 4.0, "credits_transferable": 5.0, "major_req": True, "prereq": True, "programs": ["Economics", "Computer Science"], "source_url": ASSIST_SMC_UCB_URL, "evidence": "Direct single-variable Calculus II articulation."},
            {"source_code": "ECON 1", "source_name_txt": "Principles of Microeconomics", "target_code": "ECON 1", "target_name_txt": "Introduction to Economics (Micro half w/ ECON 2)", "tier": 1, "type": "combined", "source_credits": 3.0, "source_credit_system": "us_semester", "target_credits": 4.0, "credits_transferable": 3.0, "major_req": True, "ge_req": True, "ge_category": "Social Sciences", "prereq": True, "programs": ["Economics"], "source_url": ASSIST_SMC_UCB_URL, "evidence": "Pair SMC ECON 1 + ECON 2 for UC Berkeley ECON 1."},
            {"source_code": "ECON 2", "source_name_txt": "Principles of Macroeconomics", "target_code": "ECON 1", "target_name_txt": "Introduction to Economics (Macro half w/ ECON 1)", "tier": 1, "type": "combined", "source_credits": 3.0, "source_credit_system": "us_semester", "target_credits": 4.0, "credits_transferable": 3.0, "major_req": True, "ge_req": True, "ge_category": "Social Sciences", "prereq": True, "programs": ["Economics"], "source_url": ASSIST_SMC_UCB_URL, "evidence": "Completes UC Berkeley ECON 1 when paired with SMC ECON 1."},
        ]
        for eq_s in smc_eqs:
            if _upsert_equivalency(db, smc, ucb, catalog_maps.get(str(smc.id), {}), catalog_maps.get(str(ucb.id), {}), ag_smc, eq_s):
                stats["equivalencies_created"] += 1

    # Tier 2 Historically Observed Records (Out-of-state CC -> Research University)
    if de_anza and umich:
        um_eqs = [
            {"source_code": "MATH 1A", "source_name_txt": "Calculus I", "target_code": "MATH 115", "target_name_txt": "Calculus I", "tier": 2, "type": "combined", "confidence": 0.85, "source_credits": 5.0, "target_credits": 4.0, "credits_transferable": 3.33, "major_req": True, "ge_req": True, "ge_category": "Mathematical Sciences", "prereq": True, "programs": ["Economics", "Computer Science"], "eq_source_name": "UMich Historical Transfer Credit Pattern", "source_url": UMICH_EQUIV_URL, "evidence": "Historically observed quarter Calculus sequence transferring for UMich MATH 115 (subject to faculty review)."},
            {"source_code": "ECON 1", "source_name_txt": "Principles of Macroeconomics", "target_code": "ECON 102", "target_name_txt": "Principles of Economics II (Macro)", "tier": 2, "type": "direct", "confidence": 0.84, "source_credits": 4.0, "target_credits": 4.0, "credits_transferable": 2.67, "major_req": True, "ge_req": True, "ge_category": "Social Sciences", "prereq": True, "programs": ["Economics"], "eq_source_name": "UMich Historical Transfer Credit Pattern", "source_url": UMICH_EQUIV_URL, "evidence": "Historically accepted as 2.67 semester credits toward ECON 102."},
            {"source_code": "ECON 2", "source_name_txt": "Principles of Microeconomics", "target_code": "ECON 101", "target_name_txt": "Principles of Economics I (Micro)", "tier": 2, "type": "direct", "confidence": 0.84, "source_credits": 4.0, "target_credits": 4.0, "credits_transferable": 2.67, "major_req": True, "ge_req": True, "ge_category": "Social Sciences", "prereq": True, "programs": ["Economics"], "eq_source_name": "UMich Historical Transfer Credit Pattern", "source_url": UMICH_EQUIV_URL, "evidence": "Historically accepted as 2.67 semester credits toward ECON 101."},
        ]
        for eq_s in um_eqs:
            if _upsert_equivalency(db, de_anza, umich, catalog_maps.get(str(de_anza.id), {}), catalog_maps.get(str(umich.id), {}), None, eq_s):
                stats["equivalencies_created"] += 1

    db.commit()
    return stats
