# Redrob Hackathon — Intelligent Candidate Ranking

**Challenge:** Intelligent Candidate Discovery & Ranking  
**Role ranked for:** Senior AI Engineer (Founding Team), Redrob AI  
**Dataset:** 100,000 candidates · 465 MB JSONL  
**Runtime:** ~36 seconds · CPU only · zero external dependencies  

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/redrob-ranker.git
cd redrob-ranker

# Run the ranker (Python 3.10+ required, no pip installs needed)
python rank.py --candidates ./candidates.jsonl --out ./submission.csv

# Validate output
python validate_submission.py submission.csv
# → Submission is valid.
```

---

## File Structure

```
redrob-ranker/
├── rank.py              # Main ranker — run this
├── submission.csv       # Our final ranked output (top 100)
├── APPROACH.md          # Architecture writeup
├── requirements.txt     # No external deps required
└── README.md            # This file
```

---

## Architecture

The ranker scores every candidate against 6 components derived directly from the JD:

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| Title match | 28% | Current role title vs. ML engineering vocabulary |
| Career history | 27% | Production ML evidence in role descriptions |
| Skills coverage | 20% | Trusted (endorsed/used) skills vs. JD requirements |
| Experience years | 10% | Fit with JD sweet spot (5–9 years) |
| Location | 8% | India presence; Noida/Pune/Hyderabad primary |
| Behavioral signals | 7% | Platform activity (also used as availability multiplier) |

```
final_score = profile_fit_score × availability_multiplier
```

The **availability multiplier** (0.20–1.0) down-weights candidates inactive >180 days with <10% recruiter response rate — per the JD's explicit note that such candidates are "not actually available."

---

## Key Design Decisions

### Why feature-based, not LLM-based?

Compute constraints: 5 minutes, CPU only, no network. An LLM inference approach at 100K candidates would blow the budget by 5×. Feature engineering is faster, deterministic, and fully auditable at Stage 5.

### Anti-keyword-stuffing: the trust multiplier

Skills only count at full weight if `endorsements > 3 OR duration_months > 6`. Skills with both at zero score at 0.25× only. This directly catches profiles that list "Pinecone: expert" with 0 months used.

### Why career history outweighs skills?

The JD says it explicitly: *"A Tier 5 candidate may not use the words 'RAG' or 'Pinecone' in their profile, but if their career history shows they built a recommendation system at a product company, they're a fit."* Career descriptions are harder to inflate than skill tags.

### Consulting company penalty

If >85% of a candidate's career is at TCS/Wipro/Infosys/Accenture/Cognizant/Capgemini (and they haven't had prior product experience), their career score is multiplied by 0.20 — a near-disqualification, per the JD's explicit warning.

### Honeypot detection

Four rules catch the ~80 planted impossible profiles:
1. 2+ expert skills with `duration_months = 0`
2. ≥75% of skills have `duration_months = 0` (with ≥6 total skills)
3. Non-technical title (Marketing Manager, etc.) with 3+ advanced ML skills
4. Claimed YoE exceeds career history sum by >7 years

**Result: 0 honeypots in our top 100.**

---

## Top 10 Results

| Rank | Candidate | Title | Company | Score |
|------|-----------|-------|---------|-------|
| 1 | CAND_0064326 | Search Engineer | Sarvam AI | 0.9784 |
| 2 | CAND_0018499 | Senior ML Engineer | Zomato | 0.9765 |
| 3 | CAND_0029367 | Senior Data Scientist | Rephrase.ai | 0.9691 |
| 4 | CAND_0005649 | Senior Data Scientist | Sarvam AI | 0.9637 |
| 5 | CAND_0077337 | Staff ML Engineer | Paytm | 0.9584 |
| 6 | CAND_0000031 | Recommendation Systems Engineer | Swiggy | 0.9582 |
| 7 | CAND_0007009 | Recommendation Systems Engineer | Wysa | 0.9499 |
| 8 | CAND_0070398 | ML Engineer | Genpact AI | 0.9439 |
| 9 | CAND_0079387 | AI Engineer | Microsoft | 0.9424 |
| 10 | CAND_0041669 | Recommendation Systems Engineer | CRED | 0.9396 |

Score range of full top 100: **0.8419 – 0.9784**

---

## Performance

```
Dataset:   100,000 candidates (465 MB JSONL)
Runtime:   36.1 seconds (single CPU core)
Memory:    ~200 MB peak (streaming — no full load)
Deps:      Standard library only (json, csv, datetime, argparse)
GPU:       Not used
Network:   Not used
```

---

## Reproduce Exactly

```bash
python rank.py \
  --candidates ./candidates.jsonl \
  --out ./submission.csv
```

Output is deterministic — same input always produces the same ranking.

---

## AI Tools Declaration

Architecture was designed and validated with assistance from Claude (Anthropic). No candidate data was fed to any LLM during ranking. The ranker itself makes zero API calls and runs entirely offline.
