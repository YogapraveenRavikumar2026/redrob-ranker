import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, TypedDict

logger = logging.getLogger(__name__)

class CandidateFeatures(TypedDict):
    # --- PROFILE BASICS ---
    candidate_id: str
    years_experience: float
    current_title: str
    location: str
    country: str
    current_company_type: str

    # --- SKILL ANALYSIS ---
    has_embeddings_experience: bool
    has_vector_db_experience: bool
    has_ranking_eval_experience: bool
    has_production_ml: bool
    has_python_strong: bool
    skill_depth_score: float
    relevant_skill_count: int

    # --- CAREER TRAJECTORY ---
    product_company_months: int
    consulting_only: bool
    has_shipped_ranking_system: bool
    career_trajectory_score: float
    avg_tenure_months: float
    job_hopper: bool

    # --- BEHAVIORAL SIGNALS ---
    is_active: bool
    days_since_active: int
    open_to_work: bool
    response_rate: float
    notice_days: int
    willing_to_relocate: bool
    github_score: float
    profile_completeness: float
    interview_completion_rate: float
    applications_30d: int

    # --- LOCATION FIT ---
    location_fit: str

    # --- HONEYPOT FLAGS ---
    impossible_experience: bool
    keyword_stuffer: bool


def parse_date(date_str: Any) -> datetime:
    """
    Parse date string to datetime object.
    Supports formats like 'YYYY-MM', 'YYYY-MM-DD', 'Month YYYY', 'YYYY', or 'Present'/'Current'.
    """
    if not date_str or not isinstance(date_str, str):
        return datetime.now()
        
    date_str_clean = date_str.strip().lower()
    if date_str_clean in ["present", "current", "now", "today", ""]:
        return datetime.now()
        
    # Standardize separator
    date_str_clean = re.sub(r'[\/\s]+', '-', date_str_clean)
    
    # Try different format matches
    try:
        return datetime.strptime(date_str_clean[:10], "%Y-%m-%d")
    except ValueError:
        pass
        
    try:
        return datetime.strptime(date_str_clean[:7], "%Y-%m")
    except ValueError:
        pass
        
    if re.match(r'^\d{4}$', date_str_clean):
        try:
            return datetime.strptime(date_str_clean, "%Y")
        except ValueError:
            pass
            
    for fmt in ("%b-%Y", "%B-%Y", "%b-%y", "%B-%y"):
        try:
            return datetime.strptime(date_str_clean, fmt)
        except ValueError:
            pass
            
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', date_str_clean)
    if year_match:
        try:
            return datetime(int(year_match.group(1)), 1, 1)
        except ValueError:
            pass
            
    return datetime.now()


def calculate_job_months(job: Dict[str, Any]) -> int:
    """
    Calculate the duration of a job in months.
    """
    if "duration_months" in job:
        try:
            return int(job["duration_months"])
        except (ValueError, TypeError):
            pass
            
    start_val = job.get("start_date", job.get("start"))
    end_val = job.get("end_date", job.get("end"))
    
    if not start_val:
        return 0
        
    start_dt = parse_date(start_val)
    end_dt = parse_date(end_val) if end_val else datetime.now()
    
    months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
    return max(1, months)


def calculate_experience_years(jobs: List[Dict[str, Any]]) -> float:
    """
    Calculate the total non-overlapping work experience in years.
    """
    if not jobs:
        return 0.0
        
    intervals: List[Tuple[datetime, datetime]] = []
    
    for job in jobs:
        start_val = job.get("start_date", job.get("start"))
        end_val = job.get("end_date", job.get("end"))
        
        if not start_val:
            continue
            
        start_dt = parse_date(start_val)
        end_dt = parse_date(end_val) if end_val else datetime.now()
        
        if start_dt > end_dt:
            start_dt, end_dt = end_dt, start_dt
            
        intervals.append((start_dt, end_dt))
        
    if not intervals:
        return 0.0
        
    intervals.sort(key=lambda x: x[0])
    merged: List[Tuple[datetime, datetime]] = [intervals[0]]
    
    for current in intervals[1:]:
        prev_start, prev_end = merged[-1]
        curr_start, curr_end = current
        
        if curr_start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, curr_end))
        else:
            merged.append(current)
            
    total_days = 0
    for start, end in merged:
        total_days += (end - start).days
        
    return round(total_days / 365.25, 2)


def classify_company_type(company_name: str, size: str = "", industry: str = "") -> str:
    """
    Classify company as consulting, product, startup or unknown.
    Rule:
    - 'consulting' if company name contains TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini, HCL, Tech Mahindra.
    - 'product' if company_size <= '201-500' (or smaller) or industry is tech/SaaS/AI.
    - 'startup' if company size is small (1-10 or 11-50) as a helper subcategory.
    - Else 'unknown'.
    """
    name_l = str(company_name).lower()
    consulting_firms = ["tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "hcl", "tech mahindra"]
    if any(firm in name_l for firm in consulting_firms):
        return "consulting"
        
    # Check for startup (1-10, 11-50 ranges)
    size_clean = str(size).strip()
    if size_clean in ["1-10", "11-50"]:
        return "startup"
        
    # Check if company_size <= 500
    size_is_small = False
    if size_clean:
        nums = [int(n) for n in re.findall(r'\d+', size_clean)]
        if nums and max(nums) <= 500:
            size_is_small = True
            
    # Check if industry is tech/SaaS/AI
    ind_clean = str(industry).lower()
    is_tech = any(word in ind_clean for word in ["tech", "saas", "software", "ai", "artificial intelligence", "product", "machine learning", "deep learning"])
    
    if size_is_small or is_tech:
        return "product"
        
    return "unknown"


def is_role_relevant(title: str, description: str) -> bool:
    """
    Check if a job role title or description is relevant to AI/ML backend.
    """
    text = (str(title) + " " + str(description)).lower()
    keywords = [
        "ai", "machine learning", "ml", "embeddings", "vector", "search", "ranking", 
        "nlp", "data scientist", "deep learning", "nlp engineer", "retrieval", 
        "information retrieval", "recommendation"
    ]
    return any(re.search(r'\b' + re.escape(kw) + r'\b', text) for kw in keywords) or \
           any(kw in text for kw in ["machine learning", "deep learning", "vector database", "ranking evaluation"])


def extract_features(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main function to extract candidate features according to prompt specifications.
    
    Args:
        candidate (Dict[str, Any]): The candidate profile dictionary.
        
    Returns:
        Dict[str, Any]: Extracted CandidateFeatures dictionary.
    """
    # Pre-sort career history/experience to determine latest roles
    jobs = candidate.get("career_history", candidate.get("experience", []))
    if not isinstance(jobs, list):
        jobs = []
        
    # Sort descending by start date (most recent first)
    sorted_jobs = []
    for job in jobs:
        if isinstance(job, dict):
            sorted_jobs.append(job)
    sorted_jobs.sort(key=lambda x: parse_date(x.get("start_date", x.get("start"))), reverse=True)
    
    # --- PROFILE BASICS ---
    candidate_id = str(candidate.get("id", candidate.get("candidate_id", "")))
    years_experience = calculate_experience_years(sorted_jobs)
    
    current_title = ""
    current_company_type = "unknown"
    if sorted_jobs:
        current_job = sorted_jobs[0]
        current_title = str(current_job.get("title", current_job.get("role", "")))
        current_company_type = classify_company_type(
            current_job.get("company", ""),
            current_job.get("company_size", ""),
            current_job.get("industry", "")
        )
        
    profile = candidate.get("profile", {})
    if not isinstance(profile, dict):
        profile = {}
        
    location = str(candidate.get("location", profile.get("location", "")))
    country = str(candidate.get("country", profile.get("country", "")))

    # --- SKILL DETECTION SEARCH CORPUS ---
    search_texts = []
    
    # 1. skills[].name
    skills_list = candidate.get("skills", [])
    if not isinstance(skills_list, list):
        skills_list = []
        
    for s in skills_list:
        if isinstance(s, dict):
            search_texts.append(str(s.get("name", "")))
        elif isinstance(s, str):
            search_texts.append(s)
            
    # 2. career_history[].description
    for job in sorted_jobs:
        search_texts.append(str(job.get("description", "")))
        
    # 3. profile.summary or general summary
    search_texts.append(str(profile.get("summary", "")))
    search_texts.append(str(candidate.get("summary", "")))
    
    search_corpus = " ".join(search_texts).lower()

    # --- SKILL ANALYSIS ---
    has_embeddings_experience = any(term in search_corpus for term in ["embeddings", "sentence-transformers", "bge", "e5"])
    has_vector_db_experience = any(term in search_corpus for term in ["pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch", "elasticsearch"])
    has_ranking_eval_experience = any(term in search_corpus for term in ["ndcg", "mrr", "map", "a/b testing", "evaluation framework"])
    
    has_production_ml = any(term in search_corpus for term in ["deployed ml to real users", "production ml", "deployed ml", "shipped ml"]) or \
                        ("deployed" in search_corpus and "real users" in search_corpus) or \
                        ("production" in search_corpus and "users" in search_corpus)
                        
    # Check Python listed as advanced/expert with > 12 months
    has_python_strong = False
    for skill in skills_list:
        if not isinstance(skill, dict):
            continue
        skill_name = str(skill.get("name", "")).strip().lower()
        if skill_name == "python":
            level = str(skill.get("level", "")).strip().lower()
            months = skill.get("experience_months", skill.get("months", 0))
            if not months:
                # Fallback to total years
                months = years_experience * 12
            if level in ["advanced", "expert", "lead", "senior"] and months > 12:
                has_python_strong = True
                break

    # Skill depth score: advanced/expert skills / total skills
    total_skills = len(skills_list)
    advanced_skills = 0
    for skill in skills_list:
        if isinstance(skill, dict):
            level = str(skill.get("level", "")).strip().lower()
            if level in ["advanced", "expert", "lead", "senior"]:
                advanced_skills += 1
    skill_depth_score = advanced_skills / total_skills if total_skills > 0 else 0.0

    # Relevant skill count
    relevant_keywords = [
        "python", "embeddings", "vector database", "pinecone", "weaviate", "qdrant", 
        "milvus", "faiss", "opensearch", "elasticsearch", "ndcg", "mrr", "map", 
        "a/b testing", "evaluation", "machine learning", "deep learning", "nlp", 
        "pytorch", "tensorflow", "transformers", "hybrid search", "production ml", 
        "scikit-learn", "keras", "fastapi", "django", "flask", "sql", "nosql", "aws", "docker"
    ]
    relevant_skill_count = 0
    for skill in skills_list:
        if isinstance(skill, dict):
            name = str(skill.get("name", "")).strip().lower()
            if any(kw in name for kw in relevant_keywords):
                relevant_skill_count += 1

    # --- CAREER TRAJECTORY ---
    product_company_months = 0
    for job in sorted_jobs:
        job_type = classify_company_type(
            job.get("company", ""),
            job.get("company_size", ""),
            job.get("industry", "")
        )
        if job_type in ["product", "startup"]:
            product_company_months += calculate_job_months(job)
            
    consulting_only = False
    if sorted_jobs:
        consulting_only = all(
            classify_company_type(j.get("company", ""), j.get("company_size", ""), j.get("industry", "")) == "consulting"
            for j in sorted_jobs
        )
        
    has_shipped_ranking_system = any(term in search_corpus for term in ["ranking system", "search system", "recommendation system", "shipped ranking", "shipped search", "shipped recommendation"]) or \
                                 (any(kw in search_corpus for kw in ["ranking", "search", "recommendation"]) and any(kw in search_corpus for kw in ["shipped", "deployed", "users"]))

    # Career Trajectory Score: weight recent roles more (Last = 3x, 2nd last = 2x, older = 1x)
    weighted_relevant_months = 0.0
    weighted_total_months = 0.0
    
    for idx, job in enumerate(sorted_jobs):
        weight = 1.0
        if idx == 0:
            weight = 3.0
        elif idx == 1:
            weight = 2.0
            
        m = calculate_job_months(job)
        weighted_total_months += weight * m
        
        is_rel = is_role_relevant(job.get("title", job.get("role", "")), job.get("description", ""))
        if is_rel:
            weighted_relevant_months += weight * m
            
    career_trajectory_score = weighted_relevant_months / weighted_total_months if weighted_total_months > 0 else 0.0

    # Tenure analysis
    avg_tenure_months = 0.0
    job_hopper = False
    
    if sorted_jobs:
        total_months = sum(calculate_job_months(j) for j in sorted_jobs)
        avg_tenure_months = round(total_months / len(sorted_jobs), 2)
        
        # Check tenure < 12 months in last 3 roles
        job_hopper = any(calculate_job_months(j) < 12 for j in sorted_jobs[:3])

    # --- BEHAVIORAL SIGNALS ---
    signals = candidate.get("redrob_signals", {})
    if not isinstance(signals, dict):
        signals = {}
        
    # Calculate days since last active and set is_active (active within 90 days)
    days_since_active = 9999
    is_active = False
    last_active = signals.get("last_active_date", "")
    if last_active:
        try:
            dt = parse_date(last_active)
            delta = datetime.now() - dt
            days_since_active = delta.days
            if days_since_active <= 90:
                is_active = True
        except Exception:
            pass
            
    open_to_work = bool(signals.get("open_to_work_flag", signals.get("open_to_work", False)))
    response_rate = float(signals.get("recruiter_response_rate", signals.get("response_rate", 0.0)))
    notice_days = int(signals.get("notice_period_days", signals.get("notice_days", 30)))
    willing_to_relocate = bool(signals.get("willing_to_relocate", False))
    github_score = float(signals.get("github_activity_score", signals.get("github_score", -1.0)))
    profile_completeness = float(signals.get("profile_completeness_score", signals.get("profile_completeness", 0.0)))
    interview_completion_rate = float(signals.get("interview_completion_rate", 0.0))
    applications_30d = int(signals.get("applications_submitted_30d", signals.get("applications_30d", 0)))

    # --- LOCATION FIT ---
    loc_clean = location.strip().lower()
    country_clean = country.strip().lower()
    
    if "pune" in loc_clean or "noida" in loc_clean:
        location_fit = "exact"
    elif any(city in loc_clean for city in ["hyderabad", "hyd", "mumbai", "delhi", "ncr", "gurgaon", "bangalore", "bengaluru"]):
        location_fit = "tier1_india"
    elif "india" in country_clean or "india" in loc_clean or any(city in loc_clean for city in ["chennai", "kolkata", "pune", "noida", "hyderabad", "mumbai", "delhi", "gurgaon", "bangalore", "bengaluru", "ahmedabad", "jaipur", "kochi"]):
        location_fit = "india_other"
    else:
        location_fit = "outside_india"

    # --- HONEYPOT FLAGS ---
    impossible_experience = False
    for job in sorted_jobs:
        tenure_years = calculate_job_months(job) / 12
        comp_size = str(job.get("company_size", "")).strip()
        # Heuristic: worked at a tiny startup for > 15 years
        if tenure_years > 15.0 and any(s in comp_size for s in ["1-10", "11-50"]):
            impossible_experience = True
        # Heuristic: single job tenure > 40 years
        if tenure_years > 40.0:
            impossible_experience = True
            
    # Keyword stuffer: 10+ expert skills but career titles don't match any AI role
    ai_role_patterns = ["ai", "machine learning", "ml", "nlp", "data scientist", "deep learning", "computer vision", "speech", "embeddings", "search", "ranking"]
    has_ai_title = False
    for job in sorted_jobs:
        title = str(job.get("title", job.get("role", ""))).strip().lower()
        if any(pat in title for pat in ai_role_patterns):
            has_ai_title = True
            break
            
    keyword_stuffer = (advanced_skills >= 10) and (not has_ai_title)

    features: CandidateFeatures = {
        "candidate_id": candidate_id,
        "years_experience": years_experience,
        "current_title": current_title,
        "location": location,
        "country": country,
        "current_company_type": current_company_type,
        "has_embeddings_experience": has_embeddings_experience,
        "has_vector_db_experience": has_vector_db_experience,
        "has_ranking_eval_experience": has_ranking_eval_experience,
        "has_production_ml": has_production_ml,
        "has_python_strong": has_python_strong,
        "skill_depth_score": skill_depth_score,
        "relevant_skill_count": relevant_skill_count,
        "product_company_months": product_company_months,
        "consulting_only": consulting_only,
        "has_shipped_ranking_system": has_shipped_ranking_system,
        "career_trajectory_score": career_trajectory_score,
        "avg_tenure_months": avg_tenure_months,
        "job_hopper": job_hopper,
        "is_active": is_active,
        "days_since_active": days_since_active,
        "open_to_work": open_to_work,
        "response_rate": response_rate,
        "notice_days": notice_days,
        "willing_to_relocate": willing_to_relocate,
        "github_score": github_score,
        "profile_completeness": profile_completeness,
        "interview_completion_rate": interview_completion_rate,
        "applications_30d": applications_30d,
        "location_fit": location_fit,
        "impossible_experience": impossible_experience,
        "keyword_stuffer": keyword_stuffer
    }
    
    # Extra field for downstream scoring
    features["profile_summary"] = search_corpus
    
    return features
