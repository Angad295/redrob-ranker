# Redrob Hackathon — Approach & Architecture

## What We Built

A feature-based candidate ranking system that scores all 100,000 candidates against the **Senior AI Engineer (Founding Team)** role in under 40 seconds on a single CPU core, with no external API calls and no LLM at inference time.

---

## Why Feature-Based, Not LLM-Based

The challenge constraints say 5 minutes, CPU only, no network during ranking. An LLM-based approach would either:
- Need to be distilled offline (pre-embedding) — which we did consider, but the per-candidate context is ~3,000 tokens × 100,000 = 300M tokens just to embed, far beyond the budget.
- Use a small model locally — still too slow for 100K candidates in 5 minutes on CPU.

Feature engineering is deterministic, auditable, and fast. Each component maps directly to a stated JD requirement, making it fully defensible at Stage 5.

---

## Scoring Architecture

Each candidate receives a composite score `[0, 1]`:

```
final_score = profile_fit_score × availability_multiplier
```

### Profile Fit Score (weighted sum)

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| Title match | 28% | Current role title vs. ML engineering vocabulary |
| Career history | 27% | Production ML evidence in role descriptions |
| Skills coverage | 20% | Trusted (endorsed/used) skill coverage of JD requirements |
| Experience years | 10% | Proximity to JD sweet spot (5–9 years) |
| Location | 8%  | India presence; Noida/Pune/Hyderabad/Bangalore primary |
| Behavioral signals | 7%  | Platform engagement (base component) |

### Availability Multiplier

Per the JD's explicit note: *"a perfect-on-paper candidate who hasn't logged in for 6 months and has a 5% response rate is, for hiring purposes, not actually available."*

The multiplier ranges from `0.20` to `1.0` based on:
- `last_active_date` (days since last login)
- `recruiter_response_rate`

A candidate inactive >180 days AND with <10% response rate gets `multiplier = 0.20`.

---

## Title Scoring (28%)

Three tiers based on substring matching against JD-derived vocabulary:

- **Score 1.0 — Strong fit**: `machine learning engineer`, `recommendation systems`, `search engineer`, `senior data scientist`, `applied ml`, `nlp engineer`, `research scientist`, etc. (22 patterns)
- **Score 0.45 — Adjacent**: `software engineer`, `backend engineer`, `full stack` — viable if career history compensates
- **Score 0.05 — Hard disqualified**: `marketing`, `accountant`, `hr manager`, `civil engineer`, etc. (30+ non-tech patterns)

Disqualified titles can score up to 0.30 if career + skills are strong (catches career-changers), but are capped.

---

## Career History Scoring (27%)

This is the key signal per the JD's instruction: *"A Tier 5 candidate may not use the words 'RAG' or 'Pinecone' in their profile, but if their career history shows they built a recommendation system at a product company, they're a fit."*

**Scoring logic:**

1. **ML role count**: +0.33 per ML-titled role (ML Engineer, Data Scientist, Search Engineer, etc.), capped at 1.0
2. **Production evidence density**: Scan each role's `description` field for 30+ phrase patterns signaling shipped work (e.g., `"a/b test"`, `"deployed to production"`, `"ranking model"`, `"semantic search"`, `"ndcg"`, `"offline-to-online"`)
3. **Company type modifier**:
   - Entire career at consulting (TCS/Wipro/Infosys/Accenture/etc.): ×0.20
   - >60% career at consulting: ×0.55
   - "Currently at consulting but prior product experience" (per JD): ×0.80
   - >50% at product/tech companies: ×1.15

---

## Skills Scoring (20%) — With Trust Multiplier

The single most important anti-keyword-stuffing mechanism.

**Trust criterion**: A skill is trusted if `endorsements > 3 OR duration_months > 6`. Untrusted skills score at 0.25× (keyword stuffers have 0 endorsements and 0 duration).

**Critical skill groups** (weighted):

| Group | Weight | Example skills |
|-------|--------|---------------|
| Embeddings & retrieval | 25% | Sentence Transformers, FAISS, Semantic Search, BGE |
| Vector databases | 20% | Pinecone, Weaviate, Qdrant, Milvus, Elasticsearch |
| NLP & Information Retrieval | 15% | NLP, BM25, Text Ranking, Information Retrieval |
| Ranking evaluation | 15% | NDCG, MRR, A/B Testing, Offline Evaluation |
| Modern LLM stack | 10% | LLM, RAG, Transformers, BERT, Cross-Encoder |
| Python | 10% | Python |
| ML fundamentals | 5% | PyTorch, TensorFlow, scikit-learn, XGBoost |

Bonus (up to +0.12) for trusted nice-to-have skills: LoRA/QLoRA, Learning to Rank, MLflow, Recommendation Systems.

---

## Honeypot Detection

Four rules catch the ~80 planted impossible profiles:

1. **Expert + zero duration**: 2+ skills with `proficiency=expert` AND `duration_months=0` → excluded
2. **Mass zero-duration**: ≥75% of skills have `duration_months=0` (with ≥6 skills) → excluded
3. **Title disconnect**: Non-technical title (Marketing Manager, etc.) with 3+ advanced/expert core ML skills → excluded
4. **YoE gap**: Claimed `years_of_experience` exceeds career history sum by >7 years → excluded

In our top 100, **zero honeypots were detected** (verified via `is_honeypot()` post-hoc on all 100 candidates).

---

## Location Scoring (8%)

Per JD: India only, no visa sponsorship.

| Condition | Score |
|-----------|-------|
| Noida / Pune / Hyderabad / Mumbai / Bangalore / Delhi NCR / Gurgaon | 1.00 |
| Other India city + willing to relocate | 0.75 |
| Other India city, no relocation flag | 0.55 |
| Outside India + willing to relocate | 0.12 |
| Outside India, no relocation | 0.05 |

---

## Top 100 Results Overview

Score range of top 100: **0.8419 – 0.9784**

Companies represented include: Sarvam AI, Zomato, Rephrase.ai, Swiggy, Paytm, CRED, Flipkart, Ola, Haptik, Freshworks, Zoho, InMobi, Dream11, Meesho, Yellow.ai, Razorpay, Mad Street Den, Locobuzz, Krutrim, Verloop.io, PhonePe, upGrad, Nykaa, Vedantu, BYJU'S, Niramai, PharmEasy, Saarthi.ai — plus global product companies (Google, Microsoft, Meta, Amazon, Apple, Netflix, LinkedIn, Salesforce).

All 100 candidates have:
- A genuinely ML/AI engineering title (or strong career evidence)
- Evidence of production ML work in their career descriptions
- India location (or willing to relocate)
- Verified skills (endorsements or duration proof)

---

## Runtime Performance

| Metric | Value |
|--------|-------|
| Candidates processed | 100,000 |
| Total runtime (single CPU core) | 36 seconds |
| Memory peak | ~200 MB |
| External API calls | 0 |
| Dependencies | Standard library only |

---

## How to Reproduce

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
python validate_submission.py submission.csv
# → Submission is valid.
```

---

## Design Decisions That Are Interview-Defensible

**Why not LLM embeddings?** Compute constraints (5 min, CPU, no network). Embeddings would require a local model at ~100MB+ and inference time of ~2ms/candidate = 200 seconds just for embeddings, before any scoring.

**Why not full-text semantic search?** The JD-derived vocabulary is deliberately precise. "Embeddings" as a skill name in a profile means exactly what we want it to mean. Semantic drift would harm precision.

**Why career history > skills weight?** The JD explicitly says career history is the primary signal. Skills sections are easily inflated with keywords; career descriptions are harder to fake because they require consistent, specific technical language.

**Why a multiplicative availability modifier instead of additive behavioral term?** Because a zero-availability candidate (inactive for 12 months, never responds) should drop out of consideration regardless of profile quality. A pure additive term allows a great profile to overcome zero availability.
