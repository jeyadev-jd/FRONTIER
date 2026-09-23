"""Relevance and credibility scoring for discovered content."""
import re
import structlog
from datetime import datetime, timezone

logger = structlog.get_logger()

# High-signal domains for credibility
CREDIBLE_DOMAINS = {
    "arxiv.org": 0.95,
    "github.com": 0.90,
    "huggingface.co": 0.92,
    "papers.with.code": 0.90,
    "openai.com": 0.88,
    "anthropic.com": 0.88,
    "deepmind.com": 0.90,
    "pytorch.org": 0.92,
    "tensorflow.org": 0.92,
    "devpost.com": 0.88,
    "mlh.io": 0.88,
    "kaggle.com": 0.85,
    "towardsdatascience.com": 0.78,
    "machinelearningmastery.com": 0.75,
    "realpython.com": 0.82,
    "medium.com": 0.65,
    "substack.com": 0.60,
    "reddit.com": 0.55,
    "twitter.com": 0.50,
    "x.com": 0.50,
}

# Keywords that indicate student relevance
STUDENT_RELEVANCE_KEYWORDS = {
    "high": [
        "hackathon", "student", "open source", "tutorial", "beginner",
        "learn", "build", "project", "free", "github", "paper",
        "research", "competition", "prize", "deadline", "registration",
        "workshop", "course", "dataset", "model", "deploy", "vibe coding",
    ],
    "medium": [
        "AI", "machine learning", "deep learning", "LLM", "transformer",
        "python", "javascript", "typescript", "react", "fastapi",
        "tool", "library", "framework", "API", "code", "debug",
    ],
    "low": [
        "technology", "software", "developer", "engineering",
        "data", "algorithm", "system", "platform",
    ],
}

CATEGORY_KEYWORDS = {
    "AI": ["AI", "LLM", "language model", "GPT", "Claude", "Gemini", "transformer",
            "neural", "machine learning", "deep learning", "fine-tuning", "embeddings",
            "diffusion", "multimodal", "RAG", "agents", "inference", "Ollama", "HuggingFace"],
    "BUILD": ["github", "open source", "library", "framework", "tool", "build",
               "deploy", "vibe coding", "typescript", "react", "fastapi", "api",
               "tutorial", "project", "code", "developer"],
    "RESEARCH": ["paper", "arxiv", "research", "study", "findings", "dataset",
                  "benchmark", "academic", "overleaf", "conference", "NeurIPS",
                  "ICML", "ICLR", "CVPR", "ACL"],
    "HACKATHON": ["hackathon", "competition", "devpost", "MLH", "prize", "deadline",
                   "submission", "team", "challenge", "award", "register"],
    "DEBUGGING": ["error", "bug", "fix", "traceback", "exception", "crash",
                   "debug", "stack overflow", "issue", "problem", "solution"],
    "OPPORTUNITY": ["internship", "job", "fellowship", "grant", "scholarship",
                     "opportunity", "apply", "application", "hiring"],
}

IGNORE_PATTERNS = [
    r"\bbet\b", r"\bgambl", r"\bcasino\b", r"\bNSFW\b",
    r"\bcryptocurrency buy\b", r"\binvest now\b", r"\bget rich\b",
    r"click here to win", r"limited time offer",
]


def classify_content(text: str, title: str = "") -> str:
    """Classify content into a FRONTIER category."""
    combined = (title + " " + text).lower()

    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in combined)
        scores[category] = score

    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "GENERAL"

    # Check ignore patterns
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, combined, re.I):
            return "IGNORE"

    return best


def score_relevance(
    text: str,
    title: str = "",
    url: str = "",
    published_date: datetime | None = None,
) -> dict:
    """
    Score content relevance for FRONTIER community.
    Returns dict with individual scores and overall_score.
    """
    combined = (title + " " + text).lower()
    scores = {}

    # Student relevance
    high_hits = sum(1 for kw in STUDENT_RELEVANCE_KEYWORDS["high"] if kw.lower() in combined)
    med_hits = sum(1 for kw in STUDENT_RELEVANCE_KEYWORDS["medium"] if kw.lower() in combined)
    low_hits = sum(1 for kw in STUDENT_RELEVANCE_KEYWORDS["low"] if kw.lower() in combined)
    student_raw = (high_hits * 3 + med_hits * 1.5 + low_hits * 0.5) / 20
    scores["student_relevance"] = min(student_raw, 1.0)

    # Technical value
    tech_terms = sum(1 for kw in CATEGORY_KEYWORDS.get("AI", []) + CATEGORY_KEYWORDS.get("BUILD", [])
                     if kw.lower() in combined)
    scores["technical_value"] = min(tech_terms / 8, 1.0)

    # Freshness (if we have a date)
    if published_date:
        now = datetime.now(timezone.utc)
        if published_date.tzinfo is None:
            published_date = published_date.replace(tzinfo=timezone.utc)
        age_days = (now - published_date).days
        scores["freshness"] = max(0.0, 1.0 - (age_days / 30))
    else:
        scores["freshness"] = 0.70  # unknown age = moderate

    # Credibility from domain
    from urllib.parse import urlparse
    try:
        domain = urlparse(url).netloc.replace("www.", "")
        cred = 0.0
        for cred_domain, cred_score in CREDIBLE_DOMAINS.items():
            if domain == cred_domain or domain.endswith("." + cred_domain):
                cred = cred_score
                break
        scores["credibility"] = cred if cred > 0 else 0.60
    except Exception:
        scores["credibility"] = 0.60

    # Actionability — does it have something students can DO?
    action_keywords = ["try", "use", "build", "learn", "apply", "register",
                        "submit", "download", "install", "check out", "github.com", "arxiv.org"]
    action_hits = sum(1 for kw in action_keywords if kw in combined)
    scores["actionability"] = min(action_hits / 4, 1.0)

    # Overall weighted score
    weights = {
        "student_relevance": 0.35,
        "technical_value": 0.20,
        "freshness": 0.15,
        "credibility": 0.20,
        "actionability": 0.10,
    }
    overall = sum(scores[k] * weights[k] for k in weights)
    scores["overall"] = round(overall, 3)

    return scores


def passes_quality_gate(scores: dict, min_relevance: float = 0.65, min_credibility: float = 0.55) -> bool:
    return (
        scores.get("overall", 0) >= min_relevance
        and scores.get("credibility", 0) >= min_credibility
    )
