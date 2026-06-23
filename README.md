# 🏆 Redrob Ranker — AI-Driven Candidate Discovery

🔗 **Live 3D Showcase Website**: [https://redrob-ranker-theone.vercel.app](https://redrob-ranker-theone.vercel.app)

Redrob Ranker is an optimized, multi-axis candidate scoring and ranking pipeline designed to evaluate candidates the way a great recruiter would. Instead of simple, error-prone keyword matching, the ranker performs dense semantic searches on complete profile histories, extracts granular behavioral signals, and detects fraud/honeypots.

---

## 🚀 Key Features

* **Context-Aware Semantic Matching**: Parses job descriptions and candidates' work histories into dense vector spaces using `SentenceTransformers` (`all-MiniLM-L6-v2`) to capture context over raw words.
* **5-Axis Composite Scoring**:
  1. **Semantic Profile Fit (35%)**: Evaluates candidate summaries against the job description.
  2. **Hard Technical Requirements (30%)**: Scores experience with Python, ML production, vector DBs, ranking evaluations, and shipped ranking systems.
  3. **Career Trajectory (15%)**: Assesses job stability, average tenure, and experience at product companies vs. consulting services.
  4. **Availability & Platform Activity (15%)**: Factor in `open_to_work` flags, daily activity recency, response rate, and notice periods.
  5. **Location Fit (5%)**: Checks candidate locations against specified cities or checks relocation willingness.
* **Honeypot & Fraud Prevention**: Flags candidates stuffing profiles with fake experience or impossible dates, penalizing their scores by $95\%$ to keep the shortlist trustworthy.
* **Explainable AI**: Automatically generates natural language reasonings explaining precisely why a candidate was ranked on the shortlist.
* **Two-Stage CPU Performance Optimization**: Handles processing a large $100K$ candidates dataset in **under 2.5 minutes on CPU** using a fast rule-based pre-filter (Stage 1) before running batch embedding scoring (Stage 2).

---

## 📁 Repository Structure

```text
├── docs/                     # 3D Showcase Website (GitHub Pages)
│   ├── index.html
│   ├── style.css
│   └── script.js
├── src/
│   ├── jd_parser.py          # Extracts requirements, filters, and signals from JDs
│   ├── feature_extractor.py  # Parallel extraction of candidate work history, skills, and activity
│   ├── scorer.py             # Computes semantic similarity and composite axis scoring
│   ├── honeypot_detector.py  # Flags keyword stuffers and impossible timeline profiles
│   ├── reasoning_generator.py # Generates text justifications for top candidates
│   ├── output_writer.py      # Standardizes validation and exports final submission CSV
│   └── loader.py             # Data loading utilities
├── .streamlit/
│   └── config.toml           # Streamlit theme configuration
├── app.py                    # Streamlit SaaS dashboard sandbox
├── rank.py                   # Main CLI entry point for executing the batch pipeline
├── validate_and_test.py      # Integration testing and verification script
├── requirements.txt          # Python library dependencies
└── packages.txt              # System level dependencies for deployment
```

---

## 🛠️ Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YogapraveenRavikumar2026/redrob-ranker.git
   cd redrob-ranker
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 How to Run

### 1. Execute via Command Line (CLI)
To run the full candidate ranking pipeline on a dataset file and write the output CSV:
```bash
python rank.py --candidates <path_to_candidates.jsonl> --jd <path_to_jd.docx> --out submission.csv
```

### 2. Launch the Streamlit Sandbox Dashboard
To open the interactive, premium SaaS-style user interface in your web browser:
```bash
streamlit run app.py
```
*Upload the Job Description `.docx` and Candidates `.json` or `.jsonl` file in the sidebar, click **Run Ranking**, and explore the candidate analytics and download button under the tabs.*

---

## 🔍 Validation & Testing
To ensure the output CSV complies with the submission requirements, run:
```bash
python validate_and_test.py
```
This runs checks verifying that the shortlist contains exactly 100 rows, unique and non-overlapping rankings, monotonic scores, and unique reasonings.
