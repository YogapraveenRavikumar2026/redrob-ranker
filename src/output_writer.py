import os
import csv
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def write_submission(ranked_results: List[Dict[str, Any]], output_path: str) -> None:
    """
    Assign ranks, validate results, write to CSV, and output summary statistics to stdout.
    
    Args:
        ranked_results (List[Dict[str, Any]]): List of dicts, each with keys:
            - candidate_id: str
            - score: float
            - reasoning: str
            - features: dict (optional, used for signals and statistics)
            - candidate: dict (optional)
        output_path (str): CSV file path.
    """
    # 1. Sort by score descending, then candidate_id ascending to break ties
    # Stable sort: first by candidate_id ascending
    ranked_results.sort(key=lambda x: str(x.get("candidate_id", "")))
    # Then by score descending
    ranked_results.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    
    # 2. Slice to top 100
    top_100 = ranked_results[:100]
    
    # 3. Assign ranks
    for rank, item in enumerate(top_100, 1):
        item["rank"] = rank
        
    # 4. Strict Validation
    if len(top_100) != 100:
        raise ValueError(f"Validation Error: Expected exactly 100 candidates in top tier, got {len(top_100)}.")
        
    candidate_ids = [item.get("candidate_id") for item in top_100]
    if len(set(candidate_ids)) != 100:
        raise ValueError("Validation Error: Candidate IDs are not unique in top 100.")
        
    ranks = [item.get("rank") for item in top_100]
    if set(ranks) != set(range(1, 101)):
        raise ValueError("Validation Error: Ranks are not uniquely covering 1-100.")
        
    # Monotonically non-increasing scores verification
    for i in range(len(top_100) - 1):
        if float(top_100[i]["score"]) < float(top_100[i+1]["score"]):
            raise ValueError(f"Validation Error: Scores are not monotonically non-increasing at index {i} "
                             f"({top_100[i]['score']} < {top_100[i+1]['score']}).")
            
    # 5. Write to CSV in UTF-8
    dir_name = os.path.dirname(output_path)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
        
    with open(output_path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        # Write rows
        for item in top_100:
            writer.writerow([
                item.get("candidate_id"),
                item.get("rank"),
                item.get("score"),
                item.get("reasoning")
            ])
            
    logger.info(f"Successfully wrote exactly 100 rows to CSV: {output_path}")
    
    # 6. Write Summary to stdout
    print("\n" + "="*50)
    print("SUBMISSION SUMMARY STATS")
    print("="*50)
    
    # Top 5 candidates with key signals
    print("\n--- TOP 5 CANDIDATES ---")
    for item in top_100[:5]:
        feats = item.get("features", {})
        cand = item.get("candidate", {})
        cand_name = cand.get("name", "Unknown")
        title = feats.get("current_title", "N/A")
        exp = feats.get("years_experience", 0.0)
        loc = feats.get("location_fit", "N/A")
        print(f"Rank {item['rank']}: ID={item['candidate_id']} | Name={cand_name} | Score={item['score']:.4f} | Title='{title}' | Exp={exp:.1f}yr | LocationFit={loc}")
        
    # Score distribution (min, max, mean, median)
    scores = [float(item["score"]) for item in top_100]
    min_score = min(scores)
    max_score = max(scores)
    mean_score = sum(scores) / len(scores)
    sorted_scores = sorted(scores)
    median_score = (sorted_scores[49] + sorted_scores[50]) / 2.0
    
    print("\n--- SCORE DISTRIBUTION ---")
    print(f"Max Score:    {max_score:.4f}")
    print(f"Min Score:    {min_score:.4f}")
    print(f"Mean Score:   {mean_score:.4f}")
    print(f"Median Score: {median_score:.4f}")
    
    # % of top 100 open_to_work
    open_count = sum(1 for item in top_100 if item.get("features", {}).get("open_to_work", False))
    pct_open = (open_count / 100.0) * 100.0
    print(f"\nOpen to Work:  {pct_open:.1f}%")
    
    # % of top 100 based in India
    india_count = sum(1 for item in top_100 if "india" in str(item.get("features", {}).get("country", "")).lower() or item.get("features", {}).get("location_fit", "") in ["exact", "tier1_india", "india_other"])
    pct_india = (india_count / 100.0) * 100.0
    print(f"Based in India: {pct_india:.1f}%")
    print("="*50 + "\n")


def write_output_csv(results: List[Dict[str, Any]], output_path: str) -> None:
    """
    Backward-compatible wrapper. Filters out honeypot candidates and calls write_submission.
    """
    ranked_results = []
    for item in results:
        if not item.get("is_honeypot", False):
            # Map item keys
            ranked_results.append({
                "candidate_id": item.get("features", {}).get("candidate_id", item.get("candidate", {}).get("id")),
                "score": item.get("scores", {}).get("score", 0.0),
                "reasoning": item.get("reasoning", ""),
                "features": item.get("features", {}),
                "candidate": item.get("candidate", {})
            })
            
    # Note: write_submission expects exactly 100 rows. If results are less than 100 (e.g. during dev/mock testing),
    # we bypass strict 100 validation to avoid breaking dev/mock tests, but run normally in production.
    # To check if we are in testing, if length is less than 100, we log a warning but write what we have.
    # However, to be fully safe, let's keep validation inside write_submission, but let's allow it to run 
    # if it's explicitly generated with 100 rows in verification scripts.
    write_submission(ranked_results, output_path)
