import logging
import numpy as np
from typing import Dict, Any, List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Module-level singletons for model caching
_model = None
_cached_jd_embedding = None
_cached_jd_text = None

def get_model() -> SentenceTransformer:
    """
    Lazy load the sentence-transformers model.
    """
    global _model
    if _model is None:
        logger.info("Initializing SentenceTransformer model: all-MiniLM-L6-v2...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def get_jd_embedding(jd_profile: dict) -> np.ndarray:
    """
    Embed the JD embedding_text once and cache it.
    """
    global _cached_jd_embedding, _cached_jd_text
    jd_text = jd_profile.get("embedding_text", "")
    if _cached_jd_embedding is None or _cached_jd_text != jd_text:
        logger.info("Computing and caching JD embedding...")
        model = get_model()
        emb = model.encode(jd_text, convert_to_tensor=False, show_progress_bar=False)
        _cached_jd_embedding = np.array(emb, dtype=np.float32)
        _cached_jd_text = jd_text
    return _cached_jd_embedding


def _score_axes_and_penalties(features: dict, jd_profile: dict, semantic_score: float) -> float:
    """
    Core scoring logic calculating Axis 2 to 5, applying disqualifiers and experience modifiers.
    """
    # AXIS 2 — Hard requirement match (weight: 0.30)
    hard_match_score = 0.0
    if features.get("has_embeddings_experience", False):
        hard_match_score += 0.20
    if features.get("has_vector_db_experience", False):
        hard_match_score += 0.20
    if features.get("has_ranking_eval_experience", False):
        hard_match_score += 0.15
    if features.get("has_production_ml", False):
        hard_match_score += 0.15
    if features.get("has_python_strong", False):
        hard_match_score += 0.10
    if features.get("product_company_months", 0) > 24:
        hard_match_score += 0.10
    if features.get("has_shipped_ranking_system", False):
        hard_match_score += 0.10
    hard_match_score = min(1.0, max(0.0, hard_match_score))
    
    # AXIS 3 — Career trajectory (weight: 0.15)
    trajectory_score = float(features.get("career_trajectory_score", 0.0))
    if features.get("consulting_only", False):
        trajectory_score *= 0.3
    if features.get("job_hopper", False):
        trajectory_score *= 0.8
        
    # AXIS 4 — Availability signal (weight: 0.15)
    availability_score = 1.0
    if features.get("days_since_active", 9999) > 90:
        availability_score *= 0.0
    if not features.get("open_to_work", False):
        availability_score *= 0.7
        
    notice_days = features.get("notice_days", 30)
    notice_multiplier = 1.0 - max(0, notice_days - 30) / 180.0
    availability_score *= max(0.0, notice_multiplier)
    
    response_rate = features.get("response_rate", 0.8)
    response_multiplier = min(1.0, response_rate * 1.5)
    availability_score *= response_multiplier
    
    if features.get("github_score", -1.0) > 60:
        availability_score *= 1.1
        
    availability_score = min(1.0, max(0.0, availability_score))
    
    # AXIS 5 — Location fit (weight: 0.05)
    loc_fit = features.get("location_fit", "outside_india")
    if loc_fit == "exact":
        loc_score = 1.0
    elif loc_fit == "tier1_india":
        loc_score = 0.8
    elif loc_fit == "india_other":
        loc_score = 0.5
    else: # outside_india
        if features.get("willing_to_relocate", False):
            loc_score = 0.4
        else:
            loc_score = 0.2
            
    # Raw score summation
    raw = (0.35 * semantic_score) + (0.30 * hard_match_score) + (0.15 * trajectory_score) + (0.15 * availability_score) + (0.05 * loc_score)
    
    # DISQUALIFIER PENALTIES:
    penalty = 1.0
    if features.get("consulting_only", False):
        penalty *= 0.05
    if features.get("keyword_stuffer", False):
        penalty *= 0.10
    if features.get("impossible_experience", False):
        penalty *= 0.15
        
    years_exp = features.get("years_experience", 0.0)
    if years_exp < 3.0 or years_exp > 15.0:
        penalty *= 0.60
        
    # EXPERIENCE RANGE BONUS:
    exp_modifier = 1.0
    if 5.0 <= years_exp <= 9.0:
        exp_modifier = 1.0
    elif (4.0 <= years_exp < 5.0) or (9.0 < years_exp <= 10.0):
        exp_modifier = 0.95
    elif (3.0 <= years_exp < 4.0) or (10.0 < years_exp <= 12.0):
        exp_modifier = 0.85
        
    final = raw * penalty * exp_modifier
    return round(float(final), 4)


def score_candidate(features: dict, jd_profile: dict, jd_embedding: np.ndarray) -> float:
    """
    Score a single candidate given their features, the JD profile, and the precomputed JD embedding.
    """
    cand_text = features.get("profile_summary", "")
    
    model = get_model()
    cand_emb = model.encode(cand_text, convert_to_tensor=False, show_progress_bar=False)
    cand_emb = np.array(cand_emb, dtype=np.float32)
    
    # Cosine similarity
    dot = np.dot(jd_embedding, cand_emb)
    norm_jd = np.linalg.norm(jd_embedding)
    norm_cand = np.linalg.norm(cand_emb)
    
    if norm_jd == 0 or norm_cand == 0:
        semantic_score = 0.0
    else:
        semantic_score = float(dot / (norm_jd * norm_cand))
    semantic_score = max(0.0, semantic_score)
    
    return _score_axes_and_penalties(features, jd_profile, semantic_score)


def fast_hard_score(features: dict) -> float:
    """
    Computes only the hard_match axis (no embedding, no sentence-transformers).
    Uses only boolean feature flags.
    """
    hard_match_score = 0.0
    if features.get("has_embeddings_experience", False):
        hard_match_score += 0.20
    if features.get("has_vector_db_experience", False):
        hard_match_score += 0.20
    if features.get("has_ranking_eval_experience", False):
        hard_match_score += 0.15
    if features.get("has_production_ml", False):
        hard_match_score += 0.15
    if features.get("has_python_strong", False):
        hard_match_score += 0.10
    if features.get("product_company_months", 0) > 24:
        hard_match_score += 0.10
    if features.get("has_shipped_ranking_system", False):
        hard_match_score += 0.10
    return min(1.0, max(0.0, hard_match_score))


def score_with_embedding(features: dict, candidate_embedding: np.ndarray, jd_embedding: np.ndarray) -> float:
    """
    Computes the full score including semantic axis using precalculated embeddings.
    """
    dot = np.dot(jd_embedding, candidate_embedding)
    norm_jd = np.linalg.norm(jd_embedding)
    norm_cand = np.linalg.norm(candidate_embedding)
    
    if norm_jd == 0 or norm_cand == 0:
        semantic_score = 0.0
    else:
        semantic_score = float(dot / (norm_jd * norm_cand))
    semantic_score = max(0.0, semantic_score)
    
    return _score_axes_and_penalties(features, {}, semantic_score)


def batch_score_all(all_features: List[dict], jd_profile: dict) -> List[float]:
    """
    Batch score all candidate features using batch embedding for speed.
    """
    if not all_features:
        return []
        
    # 1. Embed the JD ONCE
    jd_emb = get_jd_embedding(jd_profile)
    
    # 2. Extract candidate profile texts
    cand_texts = [f.get("profile_summary", "") for f in all_features]
    
    # 3. Batch encode candidates with size 512
    model = get_model()
    cand_embs = model.encode(cand_texts, batch_size=512, convert_to_tensor=False, show_progress_bar=False)
    
    scores = []
    for f, cand_emb in zip(all_features, cand_embs):
        # Calculate semantic cosine similarity
        cand_emb_arr = np.array(cand_emb, dtype=np.float32)
        dot = np.dot(jd_emb, cand_emb_arr)
        norm_jd = np.linalg.norm(jd_emb)
        norm_cand = np.linalg.norm(cand_emb_arr)
        
        if norm_jd == 0 or norm_cand == 0:
            semantic_score = 0.0
        else:
            semantic_score = float(dot / (norm_jd * norm_cand))
        semantic_score = max(0.0, semantic_score)
        
        # Core score
        final_score = _score_axes_and_penalties(f, jd_profile, semantic_score)
        scores.append(final_score)
        
    return scores


def batch_score_details(all_features: List[dict], jd_profile: dict) -> List[Dict[str, float]]:
    """
    Batch score all candidates and return a dictionary of individual sub-scores and the final composite score.
    Useful for populating columns in output CSV file.
    """
    if not all_features:
        return []
        
    jd_emb = get_jd_embedding(jd_profile)
    cand_texts = [f.get("profile_summary", "") for f in all_features]
    
    model = get_model()
    cand_embs = model.encode(cand_texts, batch_size=512, convert_to_tensor=False, show_progress_bar=False)
    
    details_list = []
    for f, cand_emb in zip(all_features, cand_embs):
        cand_emb_arr = np.array(cand_emb, dtype=np.float32)
        dot = np.dot(jd_emb, cand_emb_arr)
        norm_jd = np.linalg.norm(jd_emb)
        norm_cand = np.linalg.norm(cand_emb_arr)
        
        if norm_jd == 0 or norm_cand == 0:
            semantic_score = 0.0
        else:
            semantic_score = float(dot / (norm_jd * norm_cand))
        semantic_score = max(0.0, semantic_score)
        
        # Compute individual scores
        hard_match_score = 0.0
        if f.get("has_embeddings_experience", False):
            hard_match_score += 0.20
        if f.get("has_vector_db_experience", False):
            hard_match_score += 0.20
        if f.get("has_ranking_eval_experience", False):
            hard_match_score += 0.15
        if f.get("has_production_ml", False):
            hard_match_score += 0.15
        if f.get("has_python_strong", False):
            hard_match_score += 0.10
        if f.get("product_company_months", 0) > 24:
            hard_match_score += 0.10
        if f.get("has_shipped_ranking_system", False):
            hard_match_score += 0.10
        hard_match_score = min(1.0, max(0.0, hard_match_score))
        
        trajectory_score = float(f.get("career_trajectory_score", 0.0))
        if f.get("consulting_only", False):
            trajectory_score *= 0.3
        if f.get("job_hopper", False):
            trajectory_score *= 0.8
            
        availability_score = 1.0
        if f.get("days_since_active", 9999) > 90:
            availability_score *= 0.0
        if not f.get("open_to_work", False):
            availability_score *= 0.7
            
        notice_days = f.get("notice_days", 30)
        notice_multiplier = 1.0 - max(0, notice_days - 30) / 180.0
        availability_score *= max(0.0, notice_multiplier)
        
        response_rate = f.get("response_rate", 0.8)
        response_multiplier = min(1.0, response_rate * 1.5)
        availability_score *= response_multiplier
        
        if f.get("github_score", -1.0) > 60:
            availability_score *= 1.1
            
        availability_score = min(1.0, max(0.0, availability_score))
        
        final_score = _score_axes_and_penalties(f, jd_profile, semantic_score)
        
        details_list.append({
            "score": final_score,
            "semantic_fit_score": round(semantic_score, 4),
            "experience_fit_score": round(hard_match_score, 4),
            "skills_fit_score": round(trajectory_score, 4),
            "education_fit_score": round(availability_score, 4)
        })
        
    return details_list


class CandidateScorer:
    """
    Backward-compatible wrapper class that implements the CandidateScorer interface.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", weights: Dict[str, float] = None):
        pass
        
    def score_candidate(self, candidate_features: Dict[str, Any], parsed_jd: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculates individual sub-scores and the final composite score for a candidate.
        """
        details = batch_score_details([candidate_features], parsed_jd)
        return details[0]
