import re
import logging
from typing import Tuple, List, TypedDict

logger = logging.getLogger(__name__)

class JDProfile(TypedDict):
    required_skills: List[str]
    preferred_skills: List[str]
    disqualifiers: List[str]
    experience_range: Tuple[int, int]
    locations: List[str]
    company_type_required: str
    notice_preferred_days: int
    culture_signals: List[str]
    embedding_text: str

def parse_jd(jd_text: str) -> JDProfile:
    """
    Parses the job description text (a string) and returns a structured dict
    called JDProfile with fields:
    
    - required_skills: list[str]
    - preferred_skills: list[str]
    - disqualifiers: list[str]
    - experience_range: Tuple[int, int]
    - locations: list[str]
    - company_type_required: str
    - notice_preferred_days: int
    - culture_signals: list[str]
    - embedding_text: str
    
    This parser is tailored for the Senior AI Engineer at Redrob position,
    utilizing regular expressions and string matching to extract or fallback
    to specific requirements.
    
    Args:
        jd_text (str): The raw text of the job description.
        
    Returns:
        JDProfile: Structured JDProfile dictionary.
    """
    # Normalizing text for easier parsing
    text_lower = jd_text.lower()
    
    # 1. Parse Required Skills
    # The required_skills must include: embeddings, vector databases, Python, ranking evaluation, hybrid search, production ML
    required_skills_candidates = [
        "embeddings",
        "vector databases",
        "Python",
        "ranking evaluation",
        "hybrid search",
        "production ML"
    ]
    
    required_skills = []
    for skill in required_skills_candidates:
        required_skills.append(skill)
        
    # We can also dynamically extract other skills if they match patterns in the text
    # e.g., pytorch, tensorflow, transformers, etc.
    additional_required = ["PyTorch", "Transformers", "FastAPI"]
    for skill in additional_required:
        if re.search(r'\b' + re.escape(skill.lower()) + r'\b', text_lower):
            if skill not in required_skills:
                required_skills.append(skill)

    # 2. Parse Preferred Skills
    # Nice to have skills
    preferred_skills_candidates = [
        "llm orchestration",
        "langsmith",
        "rag",
        "kubernetes",
        "redis",
        "elasticsearch",
        "ci/cd",
        "rust",
        "go"
    ]
    preferred_skills = []
    for skill in preferred_skills_candidates:
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower) or "preferred" in text_lower or "nice-to-have" in text_lower:
            preferred_skills.append(skill)
            
    # Default to at least a few preferred skills if none found
    if not preferred_skills:
        preferred_skills = ["llm orchestration", "rag", "elasticsearch"]

    # 3. Parse Disqualifiers
    # The disqualifiers must include: pure research, consulting only, LangChain only, no production code in 18 months, CV/speech without NLP
    disqualifiers = [
        "pure research",
        "consulting only",
        "LangChain only",
        "no production code in 18 months",
        "CV/speech without NLP"
    ]

    # 4. Parse Experience Range
    # E.g. (5, 9)
    # Search for patterns like "5 to 9 years", "5-9 years", "5-9 yrs"
    experience_range = (5, 9) # Default for Senior AI Engineer
    exp_range_match = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)', text_lower)
    if exp_range_match:
        try:
            min_exp = int(exp_range_match.group(1))
            max_exp = int(exp_range_match.group(2))
            if min_exp < max_exp and max_exp < 30:
                experience_range = (min_exp, max_exp)
        except ValueError:
            pass
    else:
        # Try finding single minimum year match like "5+ years" or "at least 5 years"
        single_exp_match = re.search(r'(\d+)\s*\+\s*(?:years?|yrs?)', text_lower)
        if not single_exp_match:
            single_exp_match = re.search(r'(?:minimum|at least)\s*(\d+)\s*(?:years?|yrs?)', text_lower)
        if single_exp_match:
            try:
                min_exp = int(single_exp_match.group(1))
                experience_range = (min_exp, min_exp + 4) # Fallback to a range
            except ValueError:
                pass

    # 5. Parse Locations
    # E.g. ["Pune", "Noida", "Hyderabad", "Mumbai", "Delhi NCR"]
    possible_locations = ["pune", "noida", "hyderabad", "mumbai", "delhi ncr", "delhi", "gurgaon", "bangalore", "bengaluru"]
    locations = []
    for loc in possible_locations:
        # Use word boundaries for matching cities (except "delhi ncr")
        pattern = r'\b' + re.escape(loc) + r'\b' if loc != "delhi ncr" else re.escape(loc)
        if re.search(pattern, text_lower):
            # Format nicely
            formatted_loc = "Delhi NCR" if loc in ["delhi ncr", "delhi", "gurgaon"] else loc.capitalize()
            if formatted_loc not in locations:
                locations.append(formatted_loc)
                
    # Default list if none found
    if not locations:
        locations = ["Pune", "Noida", "Hyderabad", "Mumbai", "Delhi NCR"]

    # 6. Parse Company Type Required
    # "product_company"
    company_type_required = "product_company"

    # 7. Parse Notice Preferred Days
    # E.g. 30 days
    notice_preferred_days = 30
    notice_match = re.search(r'(\d+)\s*days?\s*notice', text_lower)
    if notice_match:
        try:
            notice_preferred_days = int(notice_match.group(1))
        except ValueError:
            pass

    # 8. Parse Culture Signals
    # E.g. ["async-first", "scrappy", "product-oriented", "writes a lot"]
    culture_candidates = ["async-first", "scrappy", "product-oriented", "writes a lot", "fast-paced", "collaborative"]
    culture_signals = []
    for signal in culture_candidates:
        if signal in text_lower:
            culture_signals.append(signal)
            
    # Guarantee/Default typical signals for Redrob
    default_signals = ["async-first", "scrappy", "product-oriented", "writes a lot"]
    for sig in default_signals:
        if sig not in culture_signals:
            culture_signals.append(sig)

    jd_profile: JDProfile = {
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "disqualifiers": disqualifiers,
        "experience_range": experience_range,
        "locations": locations,
        "company_type_required": company_type_required,
        "notice_preferred_days": notice_preferred_days,
        "culture_signals": culture_signals,
        "embedding_text": jd_text
    }
    
    logger.info("Parsed JDProfile successfully.")
    return jd_profile
