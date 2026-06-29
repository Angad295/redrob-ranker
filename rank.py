#!/usr/bin/env python3
"""
rank.py — Redrob Hackathon Candidate Ranker
Role: Senior AI Engineer (Founding Team) at Redrob AI, Pune/Noida
Architecture: Feature-based, no-API, streams 100K candidates in < 5 min on CPU.

Design principles (all defensible at Stage-5 interview):
  1. Title & career history dominate scoring (not keyword presence in skills).
  2. Skill trust multiplier: endorsements>3 OR duration>6 months required.
  3. Behavioral signals used as an availability multiplier, not just another term.
  4. Hard disqualifiers per JD (consulting-only career, non-tech titles, outside India).
  5. Honeypot detection: expert skills with zero duration, profile inconsistencies.

Usage:
  python rank.py --candidates ./candidates.jsonl --out ./submission.csv
"""

import argparse
import csv
import json
import time
from datetime import date, datetime
from pathlib import Path

# ─── Reference date ────────────────────────────────────────────────────────────
REFERENCE_DATE = date(2026, 5, 25)

# ═══════════════════════════════════════════════════════════════════════════════
# VOCABULARIES — derived directly from the JD
# ═══════════════════════════════════════════════════════════════════════════════

# Titles that map directly to the Senior AI Engineer role
STRONG_ML_TITLE_KWS = {
    "machine learning engineer", "ml engineer", "ai engineer",
    "applied ml", "applied ai", "applied scientist", "research engineer",
    "nlp engineer", "search engineer", "recommendation engineer",
    "ranking engineer", "retrieval engineer", "information retrieval engineer",
    "ml platform", "ml infrastructure", "ml systems", "mlops engineer",
    "senior ml", "staff ml", "principal ml", "lead ml",
    "senior ai", "staff ai", "principal ai",
    "senior data scientist", "staff data scientist",
    "lead data scientist", "principal data scientist",
    "deep learning engineer", "ml scientist", "ai scientist",
    # Compound patterns: catch "Recommendation Systems Engineer", etc.
    "recommendation systems", "recommendation engineer",
    "ranking engineer", "ranking scientist",
    "research scientist",   # common at product cos (Amazon, Google, etc.)
    "ml researcher", "ai researcher",
    "conversational ai", "dialogue systems",
    "search scientist", "search engineer",
    "personalization engineer", "personalization scientist",
}

# Adjacent technical roles — viable IF career history is strong
ADJACENT_TITLE_KWS = {
    "software engineer", "senior software engineer", "backend engineer",
    "backend developer", "full stack engineer", "full stack developer",
    "platform engineer", "systems engineer",
}

# Hard disqualifiers per JD — these roles cannot be redeemed by skills alone
# (The JD explicitly warns about "keyword stuffers" with non-technical careers)
DISQUALIFIER_TITLE_KWS = {
    "marketing manager", "marketing executive", "marketing analyst",
    "accountant", "finance manager", "finance executive", "finance analyst",
    "hr manager", "hr executive", "human resources", "talent acquisition",
    "civil engineer", "mechanical engineer", "electrical engineer",
    "operations manager", "operations executive",
    "customer support", "customer service", "customer success manager",
    "sales manager", "sales executive", "business development",
    "graphic designer", "ux designer", "ui designer", "product designer",
    "project manager", "program manager", "scrum master",
    "business analyst",
    "supply chain", "procurement", "logistics manager",
    "legal", "compliance",
    ".net developer", "java developer",
    "android developer", "ios developer", "mobile developer",
    "qa engineer", "test engineer", "quality engineer",
    "frontend engineer", "frontend developer",
    "content writer", "technical writer",
}

# Services/consulting firms: disqualifier if ENTIRE career spent here (per JD)
CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "tech mahindra", "hcl", "hcltech", "hexaware", "mphasis", "ltimindtree",
    "mindtree", "l&t infotech", "zensar", "birlasoft", "coforge", "cyient",
    "mastech", "dxc technology", "unisys", "niit technologies",
}

# ─── Skill vocabularies ────────────────────────────────────────────────────────

# Critical Group 1: Embeddings & semantic retrieval (MUST HAVE per JD)
EMBED_KWS = {
    "sentence transformers", "sentence-transformers", "text embeddings",
    "embeddings", "dense retrieval", "semantic search", "bge",
    "e5 model", "text-embedding", "bi-encoder", "hybrid retrieval",
    "hybrid search", "dense vector",
}

# Critical Group 2: Vector databases (MUST HAVE per JD)
VDB_KWS = {
    "pinecone", "weaviate", "qdrant", "milvus", "faiss", "elasticsearch",
    "opensearch", "chroma", "chromadb", "annoy", "hnswlib", "vespa",
    "typesense", "pgvector", "vector search",
    "vector database", "approximate nearest neighbor",
}

# Critical Group 3: NLP & Information Retrieval (MUST HAVE per JD)
NLP_KWS = {
    "nlp", "natural language processing", "information retrieval",
    "text classification", "named entity recognition",
    "question answering", "text ranking", "document retrieval",
    "bm25", "tf-idf", "inverted index",
}

# Critical Group 4: Ranking evaluation (MUST HAVE per JD)
EVAL_KWS = {
    "ndcg", "mrr", "mean average precision", "mean reciprocal rank",
    "ranking evaluation", "relevance evaluation", "offline evaluation",
    "online evaluation", "a/b testing", "a/b test", "offline-to-online",
    "click-through rate", "relevance judgment",
}

# Group 5: Modern LLM stack (strong plus)
LLM_KWS = {
    "llm", "large language model", "transformers", "bert", "gpt",
    "hugging face", "hugging face transformers", "rag",
    "retrieval augmented generation", "reranking", "re-ranking",
    "cross-encoder", "colbert", "splade",
}

# Group 6: Python (MUST HAVE per JD — "Strong Python")
PYTHON_KWS = {"python"}

# Group 7: ML fundamentals
ML_KWS = {
    "machine learning", "deep learning", "pytorch", "tensorflow",
    "scikit-learn", "xgboost", "lightgbm", "gradient boosting",
    "feature engineering", "model training",
}

# Nice-to-have bonus skills
BONUS_KWS = {
    "lora", "qlora", "peft", "fine-tuning llms", "fine-tune", "finetuning",
    "instruction tuning", "rlhf",
    "learning to rank", "ltr", "listwise ranking", "pairwise ranking",
    "lambdamart", "ranknet",
    "recommendation systems", "collaborative filtering",
    "mlflow", "mlops", "feature store", "model serving", "bentoml",
    "weights & biases",
}

# ─── Career evidence phrases (production ML work) ───────────────────────────
PROD_ML_PHRASES = [
    "deployed to production", "shipped to production", "production system",
    "live system", "real users", "production traffic",
    "ranking system", "retrieval system", "recommendation system",
    "search engine", "search system", "search ranking",
    "a/b test", "online experiment", "experimentation",
    "embedding", "dense retrieval", "hybrid search", "semantic search",
    "learning to rank", "ranking model", "rerank", "re-rank",
    "vector search", "approximate nearest neighbor", "faiss", "pinecone",
    "qdrant", "milvus", "weaviate", "elasticsearch",
    "ndcg", "mrr", "relevance metric", "offline metric", "online metric",
    "offline-to-online", "offline to online",
    "feature pipeline", "training pipeline",
    "inference latency", "model serving",
    "cross encoder", "bi-encoder", "sentence transformer",
    "language model", "fine-tun", "rag",
]

# Product industry signals (positive — career at tech product companies)
PRODUCT_INDUSTRIES = {
    "software", "technology", "e-commerce", "fintech", "saas",
    "food delivery", "transportation", "ai/ml", "internet",
    "healthtech", "edtech", "media", "telecommunications",
}

# ─── Location preferences (from JD) ──────────────────────────────────────────
PREFERRED_LOCS = {
    "noida", "pune", "hyderabad", "mumbai", "bangalore", "bengaluru",
    "gurgaon", "gurugram", "delhi", "new delhi", "ncr", "greater noida",
}
ANY_INDIA_LOCS = {
    "india", "chennai", "kolkata", "ahmedabad", "indore", "bhubaneswar",
    "trivandrum", "thiruvananthapuram", "chandigarh", "kochi", "coimbatore",
    "vizag", "visakhapatnam", "jaipur", "surat", "nagpur", "lucknow",
    "bhopal", "patna", "vadodara", "mysore", "mysuru", "raipur", "ranchi",
    "kanpur", "agra", "jabalpur", "rajkot",
}


# ═══════════════════════════════════════════════════════════════════════════════
# HONEYPOT DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

def is_honeypot(c: dict) -> bool:
    """
    Detect candidates with subtly impossible profiles.
    Rules per submission_spec.md Section 7:
      - Expert proficiency in many skills with 0 years used
      - 8 years at a company founded 3 years ago
      - Non-tech title with many expert ML skills
      - Claimed YoE far exceeds career history sum
    """
    profile = c.get("profile", {})
    skills  = c.get("skills", [])
    career  = c.get("career_history", [])

    # Rule 1: 2+ expert skills with zero duration_months
    expert_zero = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and s.get("duration_months", 1) == 0
    )
    if expert_zero >= 2:
        return True

    # Rule 2: ≥75% of skills have zero duration (mass keyword stuffing)
    if len(skills) >= 6:
        zero_dur = sum(1 for s in skills if s.get("duration_months", 0) == 0)
        if zero_dur / len(skills) >= 0.75:
            return True

    # Rule 3: Non-technical title + 3+ advanced/expert ML skills
    title = profile.get("current_title", "").lower()
    is_nontechnical = any(kw in title for kw in DISQUALIFIER_TITLE_KWS)
    if is_nontechnical:
        expert_ml = sum(
            1 for s in skills
            if s.get("proficiency") in ("expert", "advanced")
            and any(kw in s["name"].lower() for kw in (
                "pinecone", "faiss", "qdrant", "milvus", "weaviate",
                "embedding", "bert", "transformer", "rag", "vector", "llm",
                "sentence transformer", "deep learning", "pytorch",
            ))
        )
        if expert_ml >= 3:
            return True

    # Rule 4: Claimed YoE exceeds career history by > 7 years
    claimed_yoe   = profile.get("years_of_experience", 0)
    career_months = sum(j.get("duration_months", 0) for j in career)
    if claimed_yoe > 2 and career_months > 6:
        if claimed_yoe - career_months / 12.0 > 7.0:
            return True

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def _matches(skill_name_lower: str, kw_set: set) -> bool:
    """
    Bidirectional substring match between a skill name and a keyword set.
    Handles both 'embeddings' in 'text embeddings' and exact matches.
    """
    return any(kw in skill_name_lower or skill_name_lower in kw for kw in kw_set)


def score_title(profile: dict) -> float:
    """0.0–1.0: How well does current title match the target role?"""
    title = profile.get("current_title", "").lower()

    # Hard disqualifier check first
    if any(kw in title for kw in DISQUALIFIER_TITLE_KWS):
        return 0.05

    # Strong fit (direct ML/AI engineering titles)
    for kw in STRONG_ML_TITLE_KWS:
        if kw in title:
            return 1.0

    # 'data scientist' without senior/staff (slightly less specific but good)
    if "data scientist" in title:
        return 0.90

    # ML/AI in title not caught above
    if any(kw in title for kw in ("machine learning", "deep learning", "ai ", " ai")):
        return 0.85

    # Adjacent technical roles
    for kw in ADJACENT_TITLE_KWS:
        if kw in title:
            return 0.45

    # Data engineer — adjacent but not target
    if "data engineer" in title or "data infrastructure" in title:
        return 0.25

    # DevOps / cloud  —  could have infra ML exposure
    if "devops" in title or "cloud engineer" in title or "platform engineer" in title:
        return 0.20

    return 0.10   # Unrecognized / irrelevant


def score_career(career: list) -> tuple:
    """
    0.0–1.0: Quality of career history for production ML fit.
    Key signals: ML roles at product companies + evidence of production systems.
    Returns (score, evidence_snippet_str).
    """
    if not career:
        return 0.0, "no career history"

    total_months     = 0
    consulting_months = 0
    product_months   = 0
    ml_role_count    = 0
    evidence_hits    = 0
    evidence_list    = []
    current_is_consulting = False
    has_prior_product     = False

    for job in career:
        desc     = (job.get("description") or "").lower()
        company  = (job.get("company")     or "").lower()
        title    = (job.get("title")       or "").lower()
        dur      = job.get("duration_months", 0)
        industry = (job.get("industry")    or "").lower()
        is_curr  = job.get("is_current", False)

        total_months += dur

        is_consulting = any(cf in company for cf in CONSULTING_FIRMS)
        is_product    = (
            industry in PRODUCT_INDUSTRIES
            or not is_consulting
            and industry not in {"it services", "paper products", "manufacturing",
                                  "conglomerate", "real estate", "healthcare",
                                  "agriculture", "fmcg", "retail", "banking"}
        )

        if is_consulting:
            consulting_months += dur
            if is_curr:
                current_is_consulting = True
        elif is_product:
            product_months += dur
            if not is_curr:
                has_prior_product = True

        # Is this role ML/AI-relevant?
        ml_title = any(kw in title for kw in {
            "machine learning", "ml ", " ml", "ai ", " ai", "nlp",
            "deep learning", "data scientist", "recommendation",
            "ranking", "search engineer", "retrieval", "applied scientist",
            "research engineer", "recommendation",
        })
        if ml_title:
            ml_role_count += 1

        # Production ML evidence in description
        hits = [p for p in PROD_ML_PHRASES if p in desc]
        evidence_hits += len(hits)
        if hits and ml_title:
            evidence_list.extend(hits[:2])

    if total_months == 0:
        return 0.0, "no career data"

    consulting_frac = consulting_months / total_months
    product_frac    = product_months    / total_months

    # Base: 0.33 per ML role (cap at 1.0 after 3 roles)
    base = min(1.0, ml_role_count * 0.33)

    # Evidence from descriptions (0.07 per hit, cap 0.50)
    evidence = min(0.50, evidence_hits * 0.07)

    raw = base * 0.60 + evidence * 0.40

    # Consulting modifier — per JD: "entire career at consulting" is disqualifier
    if consulting_frac > 0.85 and total_months > 12:
        if current_is_consulting and has_prior_product:
            # JD says: "currently at consulting but prior product experience → fine"
            raw *= 0.80
        else:
            raw *= 0.20   # Entire career at consulting = strong penalty
    elif consulting_frac > 0.60:
        raw *= 0.55

    # Product company multiplier
    if product_frac > 0.50:
        raw = min(1.0, raw * 1.15)

    snippet = ", ".join(list(dict.fromkeys(evidence_list))[:3])
    return round(min(1.0, raw), 4), snippet


def score_skills(skills: list, signals: dict) -> float:
    """
    0.0–1.0: Trusted skill coverage of JD requirements.
    Trust criterion: endorsements > 3 OR duration_months > 6.
    Untrusted skills (both = 0) score at 0.25x (keyword stuffing penalty).
    """
    if not skills:
        return 0.0

    trusted   = set()
    untrusted = set()
    assessments = {k.lower(): v for k, v in
                   signals.get("skill_assessment_scores", {}).items()}

    for s in skills:
        nm   = s["name"].lower()
        endr = s.get("endorsements",   0)
        dur  = s.get("duration_months", 0)
        if endr > 3 or dur > 6:
            trusted.add(nm)
        else:
            untrusted.add(nm)

    def grp(kw_set):
        trusted_hit   = any(_matches(nm, kw_set) for nm in trusted)
        untrusted_hit = any(_matches(nm, kw_set) for nm in untrusted)
        if trusted_hit:
            return 1.00
        if untrusted_hit:
            return 0.25   # Unverified — keyword stuffer penalty
        return 0.00

    group_scores = {
        "embed":  grp(EMBED_KWS),
        "vdb":    grp(VDB_KWS),
        "nlpir":  grp(NLP_KWS),
        "eval":   grp(EVAL_KWS),
        "llm":    grp(LLM_KWS),
        "python": grp(PYTHON_KWS),
        "ml":     grp(ML_KWS),
    }

    weights = {
        "embed": 0.25, "vdb": 0.20, "nlpir": 0.15,
        "eval":  0.15, "llm": 0.10, "python": 0.10, "ml": 0.05,
    }

    critical = sum(group_scores[g] * w for g, w in weights.items())

    # Bonus: trusted skills matching nice-to-have keywords
    bonus = min(0.12, sum(
        0.025 for nm in trusted if _matches(nm, BONUS_KWS)
    ))

    # Assessment score bonus (verified platform performance)
    assess_bonus = min(0.08, sum(
        0.04 for nm in trusted
        if nm in assessments and assessments[nm] >= 65
    ))

    return round(min(1.0, critical + bonus + assess_bonus), 4)


def score_experience(yoe: float) -> float:
    """0.0–1.0: Years of experience vs JD target range (5–9 years)."""
    if yoe < 2:   return 0.05
    if yoe < 3:   return 0.20
    if yoe < 4:   return 0.40
    if yoe < 5:   return 0.65
    if yoe <= 9:  return 1.00   # Sweet spot per JD
    if yoe <= 11: return 0.75
    if yoe <= 13: return 0.55
    return 0.35


def score_location(profile: dict, signals: dict) -> float:
    """0.0–1.0: Location fit (Pune/Noida primary, India only; no visa sponsorship)."""
    loc      = profile.get("location", "").lower()
    country  = profile.get("country",  "").lower()
    relocate = signals.get("willing_to_relocate", False)

    # Outside India: JD explicitly says no visa sponsorship
    if country not in ("india", "in") and not relocate:
        return 0.05
    if country not in ("india", "in"):
        return 0.12   # Willing to relocate but no visa — very hard

    # In India: preferred cities
    if any(city in loc for city in PREFERRED_LOCS):
        return 1.00

    # Other India cities
    if relocate:
        return 0.75
    # Not preferred city + won't relocate (could work hybrid)
    return 0.55


def score_behavioral(signals: dict) -> float:
    """
    0.0–1.0: Platform engagement / availability.
    Per JD: 'inactive >6 months + 5% response rate = not actually available.'
    Used as a multiplier modifier, not an independent additive component.
    """
    # Recency of last login
    recency = 0.50
    lad = signals.get("last_active_date", "")
    if lad:
        try:
            days = (REFERENCE_DATE -
                    datetime.strptime(lad, "%Y-%m-%d").date()).days
            recency = (1.00 if days <=  14 else
                       0.90 if days <=  30 else
                       0.75 if days <=  60 else
                       0.50 if days <=  90 else
                       0.22 if days <= 180 else
                       0.07)
        except ValueError:
            pass

    # Recruiter response rate
    rr = signals.get("recruiter_response_rate", 0.40)
    resp = (1.00 if rr >= 0.80 else
            0.80 if rr >= 0.50 else
            0.50 if rr >= 0.30 else
            0.20 if rr >= 0.10 else
            0.05)

    # Open-to-work flag
    otw = 1.00 if signals.get("open_to_work_flag", False) else 0.50

    # Notice period (JD: sub-30 ideal; can buy out up to 30 days)
    nd = signals.get("notice_period_days", 60)
    notice = (1.00 if nd <= 30 else
              0.75 if nd <= 60 else
              0.50 if nd <= 90 else
              0.30)

    # Interview completion rate (reliability signal)
    icr = signals.get("interview_completion_rate", 0.50)

    # GitHub activity bonus (engineering depth)
    gh = signals.get("github_activity_score", -1)
    gh_bonus = (0.08 if gh >= 50 else
                0.04 if gh >= 20 else
                0.00)

    raw = (0.35 * recency +
           0.25 * resp   +
           0.20 * otw    +
           0.15 * notice +
           0.05 * icr)   + gh_bonus

    return round(min(1.0, raw), 4)


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER SCORER
# ═══════════════════════════════════════════════════════════════════════════════

def score_candidate(c: dict) -> tuple:
    """
    Returns (score_float, reasoning_string).

    Weights:
        Title          28% — what the person actually does day-to-day
        Career         27% — production ML evidence in history
        Skills         20% — trusted (endorsed/used) skill coverage
        Experience     10% — YoE in JD sweet-spot 5–9 years
        Location        8% — India preferred; Noida/Pune primary
        Behavioral      7% — platform availability; applied as multiplier too
    """
    profile = c.get("profile",         {})
    career  = c.get("career_history",  [])
    skills  = c.get("skills",          [])
    signals = c.get("redrob_signals",  {})
    yoe     = profile.get("years_of_experience", 0)

    # ── Honeypot gate ─────────────────────────────────────────────────────────
    if is_honeypot(c):
        title = profile.get("current_title", "?")
        return 0.01, (
            f"Honeypot signals: expert skills with 0 duration_months or "
            f"YoE/career mismatch ({title}). Excluded from ranking."
        )

    # ── Component scores ──────────────────────────────────────────────────────
    t_s         = score_title(profile)
    c_s, c_ev   = score_career(career)
    s_s         = score_skills(skills, signals)
    e_s         = score_experience(yoe)
    l_s         = score_location(profile, signals)
    b_s         = score_behavioral(signals)

    # ── Availability multiplier ───────────────────────────────────────────────
    # Per JD: "inactive + unresponsive = not actually available"
    avail_mult = 1.0
    lad = signals.get("last_active_date", "")
    rr  = signals.get("recruiter_response_rate", 0.5)
    if lad:
        try:
            days_inactive = (REFERENCE_DATE -
                             datetime.strptime(lad, "%Y-%m-%d").date()).days
            if days_inactive > 180 and rr < 0.10:
                avail_mult = 0.20
            elif days_inactive > 180:
                avail_mult = 0.50
            elif days_inactive > 90 and rr < 0.10:
                avail_mult = 0.60
        except ValueError:
            pass

    # ── Hard disqualifier: title + weak career + weak skills ─────────────────
    if t_s <= 0.10 and c_s <= 0.25 and s_s <= 0.25:
        raw = 0.03
    elif t_s <= 0.10:
        # Title is disqualifying but career/skills partially redeem
        raw = min(0.30, 0.35 * c_s + 0.35 * s_s + 0.15 * e_s + 0.10 * l_s + 0.05 * b_s)
    else:
        # Normal weighted formula
        raw = (0.28 * t_s +
               0.27 * c_s +
               0.20 * s_s +
               0.10 * e_s +
               0.08 * l_s +
               0.07 * b_s)

    final = round(min(1.0, max(0.0, raw * avail_mult)), 4)

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = _build_reasoning(
        profile, career, skills, signals,
        t_s, c_s, s_s, e_s, l_s, b_s,
        c_ev, avail_mult, final
    )

    return final, reasoning


def _build_reasoning(profile, career, skills, signals,
                     t_s, c_s, s_s, e_s, l_s, b_s,
                     c_ev, avail_mult, final) -> str:
    """
    Generate an honest, specific, non-hallucinating 1–2 sentence reasoning.
    Satisfies Stage-4 checks: specific facts, JD connection, honest concerns,
    no invented claims, variation across candidates, rank-consistent tone.
    """
    title   = profile.get("current_title",   "?")
    company = profile.get("current_company", "?")
    loc     = profile.get("location",        "?")
    yoe     = profile.get("years_of_experience", 0)
    lad     = signals.get("last_active_date", "N/A")
    rr      = signals.get("recruiter_response_rate", 0)
    notice  = signals.get("notice_period_days", "?")
    otw     = signals.get("open_to_work_flag", False)
    gh      = signals.get("github_activity_score", -1)

    # Trusted skills for mention
    trusted_skills = [
        s["name"] for s in skills
        if s.get("endorsements", 0) > 3 or s.get("duration_months", 0) > 6
    ]

    # Build strengths
    parts = []
    if t_s >= 0.85:
        parts.append(f"{title} at {company}")
    elif t_s >= 0.40:
        parts.append(f"{title} at {company} (adjacent)")
    else:
        parts.append(f"{title}")

    if c_ev and c_s >= 0.40:
        parts.append(f"career evidence: {c_ev[:50]}")
    elif c_s >= 0.60:
        parts.append("strong production ML history")
    elif c_s >= 0.30:
        parts.append("some ML career exposure")

    if trusted_skills and s_s >= 0.45:
        parts.append(f"skills: {', '.join(trusted_skills[:3])}")

    if e_s == 1.0:
        parts.append(f"{yoe:.0f}yr exp (target range)")
    elif e_s < 0.40:
        parts.append(f"{yoe:.1f}yr exp (below target)")

    # Concerns
    concerns = []
    if t_s < 0.20:
        concerns.append(f"title mismatch ({title})")
    if c_s < 0.25:
        concerns.append("limited prod ML evidence")
    if avail_mult < 0.60:
        concerns.append(f"inactive since {lad}, resp_rate={rr:.0%}")
    elif avail_mult < 0.90:
        concerns.append(f"last active {lad}")
    if isinstance(notice, int) and notice > 90:
        concerns.append(f"{notice}d notice")
    if l_s < 0.30:
        concerns.append(f"location ({loc}) / no visa sponsorship")
    if gh == -1:
        pass  # No GitHub is common, don't penalise in text
    if rr < 0.20 and avail_mult >= 0.60:
        concerns.append(f"low recruiter response rate ({rr:.0%})")

    sentence1 = "; ".join(parts)
    sentence2 = ("Concerns: " + ", ".join(concerns)) if concerns else (
        "Actively engaged (open-to-work, recent activity)." if otw and avail_mult >= 0.90
        else ""
    )

    text = (sentence1 + ". " + sentence2).strip().rstrip(".")
    if not text:
        text = f"{title} at {company}, {yoe:.0f}yr, {loc}."

    return text[:220]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Redrob Hackathon — Candidate Ranker")
    ap.add_argument("--candidates", default="/mnt/user-data/uploads/candidates.jsonl",
                    help="Path to candidates.jsonl (or .jsonl.gz)")
    ap.add_argument("--out", default="/mnt/user-data/outputs/submission.csv",
                    help="Output CSV path")
    args = ap.parse_args()

    print(f"[rank.py] Scoring from: {args.candidates}")
    t0 = time.time()

    scored = []
    n = 0

    with open(args.candidates, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                c   = json.loads(line)
                sc, rsn = score_candidate(c)
                scored.append((sc, c["candidate_id"], rsn))
                n += 1
                if n % 20_000 == 0:
                    print(f"  {n:,} scored … {time.time() - t0:.1f}s")
            except Exception as exc:
                print(f"  WARN: {exc!r} on line {n+1}")

    elapsed = time.time() - t0
    print(f"[rank.py] Scored {n:,} candidates in {elapsed:.1f}s")

    # Sort: descending score, then ascending candidate_id (tie-break per spec)
    scored.sort(key=lambda x: (-x[0], x[1]))
    top100 = scored[:100]

    print("\nTop-15 preview:")
    for i, (sc, cid, rsn) in enumerate(top100[:15], 1):
        print(f"  {i:3d}. {cid}  {sc:.4f}  {rsn[:75]}")

    # Score distribution sanity check
    scores_only = [x[0] for x in scored if x[0] > 0.05]
    if scores_only:
        buckets = [0]*11
        for s in scores_only:
            buckets[min(10, int(s * 10))] += 1
        print("\nScore distribution (>0.05):")
        for i, cnt in enumerate(buckets):
            print(f"  {i/10:.1f}-{(i+1)/10:.1f}: {cnt:,}")

    # Write CSV
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, (sc, cid, rsn) in enumerate(top100, 1):
            w.writerow([cid, rank, sc, rsn])

    print(f"\n[rank.py] Output: {out}  ({len(top100)} rows)")
    print(f"[rank.py] Total: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
