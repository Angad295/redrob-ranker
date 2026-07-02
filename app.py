import streamlit as st
import json, csv, io, sys
sys.path.insert(0, '.')
from rank import score_candidate

st.set_page_config(page_title="Redrob Candidate Ranker", page_icon="🤖")
st.title("🤖 Redrob Candidate Ranker")
st.write("Upload a candidates JSON or JSONL file to get the top-ranked candidates.")

uploaded = st.file_uploader("Upload candidates file", type=["jsonl", "json"])

if uploaded:
    content = uploaded.read().decode("utf-8").strip()
    try:
        candidates = [json.loads(l) for l in content.splitlines() if l.strip()]
    except:
        candidates = json.loads(content)

    st.info(f"Loaded {len(candidates)} candidates. Scoring...")
    results = []
    bar = st.progress(0)
    for i, c in enumerate(candidates):
        sc, rsn = score_candidate(c)
        results.append({
            "rank": 0,
            "candidate_id": c["candidate_id"],
            "score": round(sc, 4),
            "title": c["profile"]["current_title"],
            "company": c["profile"]["current_company"],
            "location": c["profile"]["location"],
            "reasoning": rsn
        })
        bar.progress((i + 1) / len(candidates))

    results.sort(key=lambda x: -x["score"])
    top = results[:min(100, len(results))]
    for i, r in enumerate(top, 1):
        r["rank"] = i

    st.success(f"✅ Top {len(top)} candidates ranked!")
    st.dataframe(top, use_container_width=True)

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["candidate_id","rank","score","reasoning"])
    w.writeheader()
    for r in top:
        w.writerow({"candidate_id": r["candidate_id"], "rank": r["rank"],
                    "score": r["score"], "reasoning": r["reasoning"]})
    st.download_button("⬇️ Download submission.csv", buf.getvalue(),
                       "submission.csv", "text/csv")
