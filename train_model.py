from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "ml_models"
MODEL_DIR.mkdir(exist_ok=True)


def read_csv_any(*relative_paths: str) -> pd.DataFrame:
    for relative_path in relative_paths:
        candidate = DATA_DIR / relative_path
        if candidate.exists():
            frame = pd.read_csv(candidate, sep=None, engine="python")
            frame.columns = [normalize_text(column) for column in frame.columns]
            return frame
    raise FileNotFoundError(f"None of the expected files were found: {', '.join(relative_paths)}")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return "" if text.lower() == "nan" else text


def parse_listish(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return [normalize_text(item) for item in value if normalize_text(item)]
    text = normalize_text(value)
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [normalize_text(item) for item in parsed if normalize_text(item)]
    except Exception:
        pass
    parts = [part.strip(" []\"'") for part in re.split(r"[,;/|]", text)]
    return [part for part in parts if part]


def build_job_text(row: pd.Series) -> str:
    pieces = [
        row.get("job_role", ""),
        row.get("industry", ""),
        row.get("education_level", ""),
        f"experience {row.get('experience_required_years', '')}",
        f"salary {row.get('avg_salary_usd', '')}",
        f"repetition {row.get('task_repetition_level', '')}",
        f"creativity {row.get('creativity_requirement', '')}",
        f"physical {row.get('physical_labor_level', '')}",
        f"analysis {row.get('analytical_complexity', '')}",
        f"social {row.get('social_interaction_level', '')}",
        f"skills {row.get('skill_complexity_score', '')}",
        f"communication {row.get('communication_requirement', '')}",
        f"domain {row.get('domain_specific_knowledge_level', '')}",
        f"team {row.get('team_collaboration_level', '')}",
    ]
    return normalize_text(" ".join(map(str, pieces)))


def build_resume_text(row: pd.Series) -> str:
    pieces = [
        row.get("career_objective", ""),
        " ".join(parse_listish(row.get("skills"))),
        " ".join(parse_listish(row.get("related_skils_in_job"))),
        " ".join(parse_listish(row.get("responsibilities"))),
        " ".join(parse_listish(row.get("responsibilities.1"))),
        " ".join(parse_listish(row.get("skills_required"))),
        " ".join(parse_listish(row.get("professional_company_names"))),
        " ".join(parse_listish(row.get("positions"))),
        " ".join(parse_listish(row.get("role_positions"))),
        " ".join(parse_listish(row.get("major_field_of_studies"))),
        " ".join(parse_listish(row.get("certification_skills"))),
    ]
    return normalize_text(" ".join(normalize_text(piece) for piece in pieces if normalize_text(piece)))


def build_onet_texts(skills_df: pd.DataFrame, interests_df: pd.DataFrame, keyword_df: pd.DataFrame) -> list[dict[str, Any]]:
    interest_map: dict[str, list[str]] = {}
    for soc_code, group in interests_df.groupby("O*NET-SOC Code"):
        labels = [f"{row['Element Name']} {row['Data Value']}" for _, row in group.iterrows() if normalize_text(row.get("Scale ID")) == "OI"]
        interest_map[str(soc_code)] = labels

    keyword_map: dict[str, list[str]] = {}
    for element_id, group in keyword_df.groupby("Element ID"):
        keyword_map[str(element_id)] = [normalize_text(keyword) for keyword in group["Keyword"].dropna().tolist() if normalize_text(keyword)]

    profiles: list[dict[str, Any]] = []
    for soc_code, group in skills_df.groupby("O*NET-SOC Code"):
        skill_names = sorted({normalize_text(name) for name in group["Element Name"].dropna().tolist() if normalize_text(name)})
        element_ids = sorted({normalize_text(name) for name in group["Element ID"].dropna().tolist() if normalize_text(name)})
        keywords: list[str] = []
        for element_id in element_ids:
            keywords.extend(keyword_map.get(element_id, []))
        interests = interest_map.get(str(soc_code), [])
        text = normalize_text(" ".join([str(soc_code), *skill_names, *keywords, *interests]))
        profiles.append(
            {
                "soc_code": str(soc_code),
                "title": str(skill_names[0]) if skill_names else str(soc_code),
                "skills": skill_names[:25],
                "interests": interests[:10],
                "text": text,
            }
        )
    return profiles


def build_courses_index(coursera_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    columns = {column.lower(): column for column in coursera_df.columns}
    skill_col = columns.get("skills")
    title_col = columns.get("title") or columns.get("course title") or columns.get("course")
    url_col = columns.get("url") or columns.get("course url")
    intro_col = columns.get("short intro") or columns.get("course short intro") or columns.get("what you learn")
    provider_col = columns.get("school")
    level_col = columns.get("level")

    course_index: dict[str, list[dict[str, Any]]] = {}
    for _, row in coursera_df.iterrows():
        raw_skills = normalize_text(row.get(skill_col, "")) if skill_col else ""
        skill_tokens = [token.strip().lower() for token in re.split(r"[,;/|]", raw_skills) if token.strip()]
        course = {
            "title": normalize_text(row.get(title_col, "")) if title_col else "",
            "url": normalize_text(row.get(url_col, "")) if url_col else "",
            "short_intro": normalize_text(row.get(intro_col, "")) if intro_col else "",
            "provider": normalize_text(row.get(provider_col, "")) if provider_col else "",
            "level": normalize_text(row.get(level_col, "")) if level_col else "",
        }
        for token in skill_tokens:
            if not course["title"]:
                continue
            course_index.setdefault(token, []).append(course)

    for token, courses in course_index.items():
        deduped: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for course in courses:
            if course["title"] in seen_titles:
                continue
            seen_titles.add(course["title"])
            deduped.append(course)
        course_index[token] = deduped[:8]
    return course_index


def main() -> None:
    automation = read_csv_any("automation_risk.csv")
    resumes = read_csv_any("resume_corpus.csv")
    coursera = read_csv_any("coursera_catalog.csv")
    onet_skills = read_csv_any("onet_skils.csv", "onet_skills.csv")
    onet_interests = read_csv_any("onet_interests.csv")
    onet_keywords = read_csv_any("onet_interest_keywords.csv")

    job_texts = [build_job_text(row) for _, row in automation.iterrows()]
    resume_texts = [build_resume_text(row) for _, row in resumes.iterrows()]
    onet_profiles = build_onet_texts(onet_skills, onet_interests, onet_keywords)
    onet_texts = [profile["text"] for profile in onet_profiles]

    corpus = [*job_texts, *resume_texts, *onet_texts]
    vectorizer = TfidfVectorizer(max_features=7000, ngram_range=(1, 2), stop_words="english")
    vectorizer.fit(corpus)

    job_vectors = vectorizer.transform(job_texts)
    cluster_vectors = vectorizer.transform(onet_texts)
    risk_targets = automation["automation_risk_score"].astype(float).clip(0.0, 1.0).to_numpy()
    risk_model = Ridge(alpha=1.2)
    risk_model.fit(job_vectors, risk_targets)

    bundle = {
        "vectorizer": vectorizer,
        "risk_model": risk_model,
        "job_vectors": job_vectors,
        "job_profiles": [
            {
                "job_role": normalize_text(row.get("job_role", "")),
                "industry": normalize_text(row.get("industry", "")),
                "risk_score": float(row.get("automation_risk_score", 0.0)),
                "salary_usd": float(row.get("avg_salary_usd", 0.0)),
                "skills": [
                    normalize_text(row.get("skill_complexity_score", "")),
                    normalize_text(row.get("domain_specific_knowledge_level", "")),
                    normalize_text(row.get("communication_requirement", "")),
                    normalize_text(row.get("team_collaboration_level", "")),
                ],
                "text": text,
            }
            for text, (_, row) in zip(job_texts, automation.iterrows())
        ],
        "cluster_vectors": cluster_vectors,
        "cluster_profiles": onet_profiles,
    }

    joblib.dump(bundle, MODEL_DIR / "model.pkl")
    joblib.dump(build_courses_index(coursera), MODEL_DIR / "courses.pkl")
    print(f"Saved model bundle to {MODEL_DIR / 'model.pkl'}")


if __name__ == "__main__":
    main()