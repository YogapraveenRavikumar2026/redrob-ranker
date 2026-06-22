import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_reasoning(features: Dict[str, Any], score: float, rank: int) -> str:
    """
    Generate candidate-specific reasoning explanation based on rank band and candidate features.
    Must be 1-2 sentences and maximum of 200 characters.
    
    Args:
        features (dict): Extracted CandidateFeatures dict.
        score (float): Candidate's final ranking score.
        rank (int): Candidate's final rank placement.
        
    Returns:
        str: Candidate reasoning description.
    """
    years = int(features.get("years_experience", 0))
    title = str(features.get("current_title", "Engineer")).strip()
    
    # 1. Select strongest signal (Axis 1 helper)
    if features.get("has_embeddings_experience", False):
        strongest_skill = "embedding/retrieval systems"
    elif features.get("has_vector_db_experience", False):
        strongest_skill = "vector search"
    elif features.get("has_ranking_eval_experience", False):
        strongest_skill = "ranking evaluation"
    elif features.get("has_shipped_ranking_system", False):
        strongest_skill = "search/ranking systems"
    else:
        strongest_skill = "ML engineering"

    # 2. Select availability signal (Axis 4 helper)
    notice_days = int(features.get("notice_days", 30))
    is_active = bool(features.get("is_active", False))
    open_to_work = bool(features.get("open_to_work", False))
    location_fit = str(features.get("location_fit", "outside_india"))
    willing_to_relocate = bool(features.get("willing_to_relocate", False))
    
    if is_active and open_to_work and notice_days <= 30:
        availability_signal = "available immediately"
    elif is_active and notice_days <= 60:
        availability_signal = f"{notice_days}d notice"
    elif not is_active:
        availability_signal = "low recent activity (flag)"
    elif location_fit == "outside_india" and not willing_to_relocate:
        availability_signal = "non-India location (risk)"
    else:
        availability_signal = "actively looking"

    # 3. Select biggest gap (Axis 3/5 helper)
    if features.get("consulting_only", False):
        biggest_gap = "entire career in IT services"
    elif not features.get("has_production_ml", False):
        biggest_gap = "no production ML deployment found"
    elif not is_active:
        biggest_gap = "inactive >90 days"
    elif location_fit == "outside_india":
        biggest_gap = "based outside India"
    else:
        biggest_gap = "limited retrieval/ranking experience"

    # Determine template reasoning based on rank
    if rank <= 10:
        # Top tier
        reasoning = f"{years}yr {title} with production {strongest_skill}; {availability_signal}."
    elif 11 <= rank <= 30:
        # Strong candidates
        if features.get("has_embeddings_experience", False) and features.get("has_vector_db_experience", False):
            skill_match = "strong embeddings and vector DB match"
        elif features.get("has_embeddings_experience", False):
            skill_match = "focus on embedding systems"
        elif features.get("has_vector_db_experience", False):
            skill_match = "focus on vector search"
        else:
            skill_match = "general ML skills match"
            
        # Determine positive or concern
        if features.get("job_hopper", False):
            one_concern_or_positive = "noted short tenure history"
        elif features.get("consulting_only", False):
            one_concern_or_positive = "services background"
        elif notice_days > 45:
            one_concern_or_positive = f"notice period {notice_days}d"
        else:
            one_concern_or_positive = "solid career trajectory"
            
        reasoning = f"{years}yr applied ML background; {skill_match}; {one_concern_or_positive}."
    elif 31 <= rank <= 60:
        # Moderate fit
        if features.get("has_python_strong", False) and features.get("has_embeddings_experience", False):
            what_matches = "strong Python & embeddings"
        elif features.get("has_python_strong", False):
            what_matches = "strong Python background"
        elif features.get("has_embeddings_experience", False):
            what_matches = "embedding systems understanding"
        else:
            what_matches = "basic AI/ML skills"
            
        reasoning = f"Partial fit — {what_matches}; concern: {biggest_gap}."
    else:
        # Marginal (rank >= 61)
        if features.get("has_python_strong", False):
            what_they_have = "Python developer"
        elif int(features.get("relevant_skill_count", 0)) > 0:
            what_they_have = f"{features.get('relevant_skill_count')} relevant skills"
        else:
            what_they_have = "general software experience"
            
        # Main disqualifier
        years_exp = features.get("years_experience", 0.0)
        if years_exp < 3:
            main_disqualifier = "under-experienced"
        elif years_exp > 15:
            main_disqualifier = "over-experienced for role"
        elif features.get("consulting_only", False):
            main_disqualifier = "consulting background only"
        elif features.get("keyword_stuffer", False):
            main_disqualifier = "keyword stuffer profile"
        else:
            main_disqualifier = "low overall fit to requirements"
            
        reasoning = f"Adjacent skills only — {what_they_have}; {main_disqualifier}."

    # Force strict character limit cap (200 chars)
    if len(reasoning) > 200:
        reasoning = reasoning[:197] + "..."
        
    return reasoning
