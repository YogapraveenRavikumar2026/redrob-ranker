import logging
import re
from datetime import datetime
from typing import Dict, Any, Tuple, List
from src.feature_extractor import parse_date, calculate_job_months, calculate_experience_years

logger = logging.getLogger(__name__)

def is_honeypot(candidate: Dict[str, Any]) -> Tuple[bool, float]:
    """
    Check if a candidate profile is a honeypot based on 5 specific rules.
    
    Args:
        candidate (Dict[str, Any]): The candidate profile dictionary.
        
    Returns:
        Tuple[bool, float]:
            - bool: hard honeypot flag (True if any Rule 1-4 triggered)
            - float: honeypot_confidence (0.0 to 1.0)
    """
    jobs = candidate.get("career_history", candidate.get("experience", []))
    if not isinstance(jobs, list):
        jobs = []
        
    # --- Rule 1 — Impossible tenure ---
    # Claims 8+ years (96 months) at a company size "1-10" or "11-50"
    rule1_flag = False
    for job in jobs:
        if not isinstance(job, dict):
            continue
        comp_size = str(job.get("company_size", "")).strip()
        if comp_size in ["1-10", "11-50"]:
            months = calculate_job_months(job)
            if months >= 96:
                rule1_flag = True
                break

    # --- Rule 2 — Expert skill explosion ---
    # Count expert skills
    expert_count = 0
    skills_list = candidate.get("skills", [])
    if not isinstance(skills_list, list):
        skills_list = []
        
    for skill in skills_list:
        if isinstance(skill, dict):
            prof = str(skill.get("proficiency", skill.get("level", ""))).strip().lower()
            if prof == "expert":
                expert_count += 1
                
    years_exp = calculate_experience_years([j for j in jobs if isinstance(j, dict)])
    
    rule2_flag = False
    if expert_count >= 8 and years_exp < 5.0:
        rule2_flag = True
    if expert_count >= 12:
        rule2_flag = True

    # --- Rule 3 — Title-skill mismatch ---
    # Current title matches mismatch list AND has 5+ AI expert skills
    rule3_flag = False
    sorted_jobs = []
    for job in jobs:
        if isinstance(job, dict):
            sorted_jobs.append(job)
    sorted_jobs.sort(key=lambda x: parse_date(x.get("start_date", x.get("start"))), reverse=True)
    
    current_title = ""
    if sorted_jobs:
        current_title = str(sorted_jobs[0].get("title", sorted_jobs[0].get("role", "")))
        
    mismatch_titles = ["Marketing", "HR", "Sales", "Graphic", "Content Writer", "Finance"]
    title_matches_mismatch = any(t.lower() in current_title.lower() for t in mismatch_titles)
    
    if title_matches_mismatch:
        ai_keywords = ["ai", "machine learning", "ml", "nlp", "deep learning", "neural", "pytorch", "tensorflow", "transformers", "embeddings", "vector", "search", "ranking", "computer vision"]
        expert_ai_count = 0
        for skill in skills_list:
            if isinstance(skill, dict):
                name = str(skill.get("name", "")).lower()
                prof = str(skill.get("proficiency", skill.get("level", ""))).strip().lower()
                if prof == "expert" and any(kw in name for kw in ai_keywords):
                    expert_ai_count += 1
        if expert_ai_count >= 5:
            rule3_flag = True

    # --- Rule 4 — Date inconsistency ---
    # end_date < start_date OR simple duration sum > years_experience * 12 + 24
    rule4_flag = False
    total_simple_months = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        start_val = job.get("start_date", job.get("start"))
        end_val = job.get("end_date", job.get("end"))
        if start_val:
            start_dt = parse_date(start_val)
            end_dt = parse_date(end_val) if end_val else datetime.now()
            if end_dt < start_dt:
                rule4_flag = True
                break
            total_simple_months += calculate_job_months(job)
            
    if total_simple_months > (years_exp * 12 + 24):
        rule4_flag = True

    # --- Rule 5 — Profile completeness + zero activity ---
    # profile_completeness_score > 95 AND last_active_date > 180 days ago AND github_activity_score == -1 AND applications_submitted_30d == 0
    rule5_flag = False
    signals = candidate.get("redrob_signals", {})
    if not isinstance(signals, dict):
        signals = {}
        
    comp_score = signals.get("profile_completeness_score", signals.get("profile_completeness", 0.0))
    # Handle ratio vs percentage
    if comp_score <= 1.0:
        comp_score *= 100.0
        
    github = signals.get("github_activity_score", signals.get("github_score", -1.0))
    apps = signals.get("applications_submitted_30d", signals.get("applications_30d", 0))
    
    last_active = signals.get("last_active_date", "")
    active_more_than_180 = False
    if last_active:
        try:
            dt = parse_date(last_active)
            delta = datetime.now() - dt
            if delta.days > 180:
                active_more_than_180 = True
        except Exception:
            pass
            
    if comp_score > 95.0 and active_more_than_180 and github == -1.0 and apps == 0:
        rule5_flag = True

    # Hard honeypot if Rule 1-4 triggered
    hard_honeypot = rule1_flag or rule2_flag or rule3_flag or rule4_flag
    
    # Confidence calculation
    if hard_honeypot:
        confidence = 1.0
    elif rule5_flag:
        confidence = 0.5
    else:
        confidence = 0.0
        
    return hard_honeypot, confidence


def detect_honeypot(candidate: Dict[str, Any], features: Dict[str, Any] = None) -> Tuple[bool, List[str]]:
    """
    Detect if a candidate is a honeypot (backward-compatible wrapper).
    """
    hard_flag, confidence = is_honeypot(candidate)
    
    reasons = []
    if hard_flag or confidence > 0:
        # Check specific rule details to output to log/reasons
        jobs = candidate.get("career_history", candidate.get("experience", []))
        
        # Rule 1 detail
        for job in jobs:
            if isinstance(job, dict):
                comp_size = str(job.get("company_size", "")).strip()
                if comp_size in ["1-10", "11-50"] and calculate_job_months(job) >= 96:
                    reasons.append("Impossible small company tenure (Rule 1)")
                    break
                    
        # Rule 2 detail
        expert_count = sum(1 for s in candidate.get("skills", []) if isinstance(s, dict) and str(s.get("proficiency", s.get("level", ""))).strip().lower() == "expert")
        years_exp = calculate_experience_years([j for j in jobs if isinstance(j, dict)])
        if expert_count >= 8 and years_exp < 5.0:
            reasons.append(f"Expert skill explosion with low experience (Rule 2: {expert_count} experts, {years_exp:.1f} yrs)")
        elif expert_count >= 12:
            reasons.append(f"Excessive expert skills (Rule 2: {expert_count} experts)")
            
        # Rule 3 detail
        sorted_jobs = sorted([j for j in jobs if isinstance(j, dict)], key=lambda x: parse_date(x.get("start_date", x.get("start"))), reverse=True)
        if sorted_jobs:
            title = str(sorted_jobs[0].get("title", sorted_jobs[0].get("role", "")))
            if any(t.lower() in title.lower() for t in ["Marketing", "HR", "Sales", "Graphic", "Content Writer", "Finance"]):
                reasons.append(f"Title-skill mismatch (Rule 3: role '{title}')")
                
        # Rule 4 detail
        date_err = False
        for job in jobs:
            if isinstance(job, dict):
                s_val = job.get("start_date", job.get("start"))
                e_val = job.get("end_date", job.get("end"))
                if s_val and e_val and parse_date(e_val) < parse_date(s_val):
                    date_err = True
                    break
        if date_err:
            reasons.append("Date inconsistency: end date before start date (Rule 4)")
        else:
            total_simple_months = sum(calculate_job_months(j) for j in jobs if isinstance(j, dict))
            if total_simple_months > (years_exp * 12 + 24):
                reasons.append(f"Overlapping employment dates exceed threshold (Rule 4: {total_simple_months} simple months vs {years_exp:.1f} yrs actual)")
                
        # Rule 5 detail
        if not hard_flag and confidence == 0.5:
            reasons.append("Suspicious profile completeness with zero activity (Rule 5)")
            
    is_honeypot_flag = hard_flag
    
    return is_honeypot_flag, reasons
