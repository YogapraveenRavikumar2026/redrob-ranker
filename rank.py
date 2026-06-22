import argparse
import sys
import time
import logging
from multiprocessing import Pool, cpu_count
from tqdm import tqdm

import src.loader as loader
import src.jd_parser as jd_parser
import src.honeypot_detector as honeypot_detector
import src.feature_extractor as feature_extractor
import src.scorer as scorer
import src.reasoning_generator as reasoning_generator
import src.output_writer as output_writer

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger("ranker")

    parser = argparse.ArgumentParser(description="RedRob Ranker CLI Entry Point")
    parser.add_argument("--candidates", required=True, help="Path to candidates .jsonl or .jsonl.gz file")
    parser.add_argument("--jd", required=True, help="Path to job description .docx file")
    parser.add_argument("--out", required=True, help="Path to output final CSV")
    args = parser.parse_args()

    logger.info("Initializing RedRob Ranker pipeline...")
    
    # 1. Load candidates and JD text
    t_start_total = time.time()
    candidates, jd_text = loader.load_all(args.candidates, args.jd)
    
    # 2. Parse JD
    jd_profile = jd_parser.parse_jd(jd_text)
    
    # === STAGE 1 — Fast pre-filter (no embeddings, pure features, ~10 seconds) ===
    t_stage1_start = time.time()
    logger.info("Stage 1: Extracting candidate features in parallel...")
    with Pool(cpu_count()) as pool:
        features_list = list(tqdm(
            pool.imap(feature_extractor.extract_features, candidates, chunksize=100),
            total=len(candidates),
            desc="Extracting features"
        ))
        
    logger.info("Stage 1: Applying hard filters and fast_hard_score...")
    stage1_survivors = []
    
    # Compile rejection titles for case-insensitive substring checking
    rejection_titles = [
        "Marketing", "HR Manager", "Sales", "Graphic Designer", 
        "Content Writer", "Finance", "Recruiter", "Teacher", "Doctor", "Lawyer"
    ]
    rejection_titles_lower = [t.lower() for t in rejection_titles]
    
    # Map candidate_id to candidate dict for fast lookup in Stage 2
    cand_lookup = {str(c.get("id", c.get("candidate_id", ""))): c for c in candidates}
    
    for feat in features_list:
        cand_id = feat["candidate_id"]
        cand = cand_lookup.get(cand_id)
        if not cand:
            continue
            
        # Filter 1: years_experience < 2 or years_experience > 20
        years_exp = feat.get("years_experience", 0.0)
        if years_exp < 2.0 or years_exp > 20.0:
            continue
            
        # Filter 2: consulting_only == True
        if feat.get("consulting_only", False):
            continue
            
        # Filter 3: is_active == False (last_active > 120 days ago)
        if feat.get("days_since_active", 9999) > 120:
            continue
            
        # Filter 4: keyword_stuffer == True
        if feat.get("keyword_stuffer", False):
            continue
            
        # Filter 5: impossible_experience == True (honeypot)
        if feat.get("impossible_experience", False):
            continue
            
        # Filter 6: country != "India" AND willing_to_relocate == False
        country_lower = feat.get("country", "").strip().lower()
        willing = feat.get("willing_to_relocate", False)
        if country_lower != "india" and not willing:
            continue
            
        # Filter 7: current_title matches any of the rejection titles
        title_lower = feat.get("current_title", "").strip().lower()
        if any(rt in title_lower for rt in rejection_titles_lower):
            continue
            
        # Calculate hard_match_score using only rule-based features (no embeddings)
        h_score = scorer.fast_hard_score(feat)
        
        stage1_survivors.append({
            "candidate": cand,
            "features": feat,
            "hard_match_score": h_score
        })
        
    # Validation check: Raise error if fewer than 100 valid candidates remain
    if len(stage1_survivors) < 100:
        raise ValueError(f"Validation Error: Fewer than 100 valid candidates remain after filtering. "
                         f"Total valid: {len(stage1_survivors)}.")
                         
    # Keep top 3000 by hard_match_score
    # Sort: hard_match_score descending, candidate_id ascending
    stage1_survivors.sort(key=lambda x: str(x["features"]["candidate_id"]))
    stage1_survivors.sort(key=lambda x: float(x["hard_match_score"]), reverse=True)
    
    top_3000 = stage1_survivors[:3000]
    
    t_stage1_end = time.time()
    t_stage1_elapsed = t_stage1_end - t_stage1_start
    print(f"[Stage 1] Feature extraction + pre-filter: {t_stage1_elapsed:.2f}s, kept {len(top_3000)}/{len(candidates)}")
    
    # === STAGE 2 — Deep scoring with embeddings (~60 seconds for 3000 candidates) ===
    t_stage2_start = time.time()
    logger.info("Stage 2: Batch embedding and scoring top 3000...")
    
    top_3000_features = [item["features"] for item in top_3000]
    scores_list = scorer.batch_score_all(top_3000_features, jd_profile)
    
    # Apply honeypot checks and penalties (only on survivors to save time)
    scored_candidates = []
    for item, score in zip(top_3000, scores_list):
        cand = item["candidate"]
        feat = item["features"]
        
        is_hard_hp, confidence = honeypot_detector.is_honeypot(cand)
        final_score = round(score * 0.05, 4) if is_hard_hp else score
        
        scored_candidates.append({
            "candidate_id": feat["candidate_id"],
            "score": final_score,
            "features": feat,
            "candidate": cand,
            "is_hard_hp": is_hard_hp,
            "confidence": confidence
        })
        
    # Sort: score descending, candidate_id ascending (tiebreaker)
    scored_candidates.sort(key=lambda x: str(x["candidate_id"]))
    scored_candidates.sort(key=lambda x: float(x["score"]), reverse=True)
    
    top_100 = scored_candidates[:100]
    
    t_stage2_end = time.time()
    t_stage2_elapsed = t_stage2_end - t_stage2_start
    print(f"[Stage 2] Embedding + scoring top 3000: {t_stage2_elapsed:.2f}s")
    
    # === STAGE 3 — Reasoning + output (fast) ===
    t_stage3_start = time.time()
    logger.info("Stage 3: Generating candidate reasoning for top 100...")
    seen_reasonings = set()
    for rank, item in enumerate(top_100, 1):
        reason = reasoning_generator.generate_reasoning(item["features"], item["score"], rank)
        
        # Deduplicate
        if reason in seen_reasonings:
            suffix = f" [{item['candidate_id']}]"
            if len(reason) + len(suffix) <= 200:
                reason = reason.rstrip(".") + suffix + "."
            else:
                reason = reason[:200 - len(suffix)] + suffix
        seen_reasonings.add(reason)
        
        if item["is_hard_hp"]:
            reason = f"FILTERED (hard): Flagged honeypot. " + reason
            if len(reason) > 200:
                reason = reason[:197] + "..."
        item["reasoning"] = reason
        
    logger.info("Stage 3: Writing submission CSV...")
    output_writer.write_submission(top_100, args.out)
    
    t_stage3_end = time.time()
    t_stage3_elapsed = t_stage3_end - t_stage3_start
    print(f"[Stage 3] Reasoning + output: {t_stage3_elapsed:.2f}s")
    
    t_total_elapsed = time.time() - t_start_total
    print(f"Total: {t_total_elapsed:.2f}s")

if __name__ == "__main__":
    main()
