"""One-off converter: maps a richer, externally-authored "cv_knowledge_base"
YAML (structured_profile.* / derived_indexes.* shape, with source-provenance
tracking, canonical/superseded claim resolution per role, and a technologies-
by-employer index) into this app's CandidateProfile schema (schema_version /
person / summary_facts / experience / skills / ...), so it can go through the
normal validated import flow (import_profile_version).

Lossy in places -- drops source_id provenance links, regulatory/product-context
prose, and per-fact "facts" slug arrays, since the app's schema has no fields
for them. Keeps every human-readable statement, every metric, and every
technology, since those are what the CV generation pipeline actually reads.

Usage:
    python scripts/convert_legacy_profile.py <source.yaml> <dest.yaml>
"""

import re
import sys
from pathlib import Path

import yaml


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _metric(m: dict) -> dict:
    unit = m.get("unit", "")
    qualifier = m.get("qualifier")
    return {
        "value": float(m["value"]),
        "unit": f"{qualifier}_{unit}" if qualifier else unit,
        "context": m.get("context", ""),
    }


def _split_metrics(raw_metrics: list[dict]) -> tuple[list[dict], list[str]]:
    """Most metrics are {value, unit, context} and map directly onto the app's
    Metric schema. A few source entries instead give a range ({"range": "4-50x",
    "metric": "..."}) that a single float can't represent -- those get folded
    into the statement text as a parenthetical instead of forcing a fabricated
    single number into the Metric.value field."""
    metrics: list[dict] = []
    notes: list[str] = []
    for m in raw_metrics:
        if "value" in m:
            try:
                metrics.append(_metric(m))
            except (TypeError, ValueError):
                # non-numeric value (e.g. {"value": "zero", "unit": "downtime", ...})
                unit = m.get("unit", "")
                notes.append(f"{m['value']} {unit}".strip() + (f" ({m['context']})" if m.get("context") else ""))
        elif "range" in m:
            label = m.get("metric", "").replace("_", " ")
            notes.append(f"{label}: {m['range']}" if label else m["range"])
    return metrics, notes


def _detail_texts(contrib: dict) -> list[str]:
    """Contributions store their supporting detail under one of a few
    differently-named keys depending on the kind of contribution (regular
    work vs. security controls vs. on-call responsibilities); items are
    either {"exact_text": ...} dicts or bare strings."""
    for key in ("evidence_blocks", "controls", "responsibilities"):
        items = contrib.get(key)
        if not items:
            continue
        texts = []
        for item in items:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict) and item.get("exact_text"):
                texts.append(item["exact_text"])
        return texts
    return []


def _match_tech_context(employer: str, tech_by_context: dict[str, list[str]]) -> list[str]:
    key = _slugify(employer)
    if key in tech_by_context:
        return tech_by_context[key]
    for context_key, techs in tech_by_context.items():
        if context_key in key or key in context_key:
            return techs
    return []


def _convert_experience_entry(exp: dict, tech_by_context: dict[str, list[str]]) -> dict:
    exp_id = exp["id"]
    responsibilities: list[dict] = []
    achievements: list[dict] = []

    crd = exp.get("canonical_role_detail")
    if crd:
        for contrib in crd.get("contributions", []):
            statement = contrib.get("overview_exact_text") or contrib["title"]
            metrics, notes = _split_metrics(contrib.get("metrics", []))
            if notes:
                statement = f"{statement} ({'; '.join(notes)})"
            fact_id = contrib["id"]
            if metrics or notes:
                achievements.append(
                    {"id": fact_id, "statement": statement, "metrics": metrics, "technologies": [], "evidence_level": "verified"}
                )
            else:
                responsibilities.append({"id": fact_id, "statement": statement, "evidence_level": "verified"})

            for i, text in enumerate(_detail_texts(contrib)):
                responsibilities.append(
                    {"id": f"{fact_id}_detail_{i + 1}", "statement": text, "evidence_level": "verified"}
                )
    else:
        # Entries without a canonical_role_detail reconstruction store their
        # content either under superseded_cv_summary_claims.claims (same shape,
        # explicitly marked superseded elsewhere) or directly as a top-level
        # "contributions" list (category/exact_text/facts/metrics) -- both are
        # the only source of truth for that entry when present, so use whichever exists.
        claims = exp.get("superseded_cv_summary_claims", {}).get("claims") or exp.get("contributions") or []
        for i, claim in enumerate(claims):
            fact_id = f"{exp_id}_claim_{i + 1}"
            metrics, notes = _split_metrics(claim.get("metrics", []))
            statement = claim["exact_text"]
            if notes:
                statement = f"{statement} ({'; '.join(notes)})"
            if metrics or notes:
                achievements.append(
                    {"id": fact_id, "statement": statement, "metrics": metrics, "technologies": [], "evidence_level": "verified"}
                )
            else:
                responsibilities.append({"id": fact_id, "statement": statement, "evidence_level": "verified"})

    end = exp.get("end")
    end_date = None if not end or end == "present" else end

    return {
        "id": exp_id,
        "company": exp["employer"],
        "position": exp["role"],
        "start_date": exp["start"],
        "end_date": end_date,
        "location": exp.get("location"),
        "technologies": _match_tech_context(exp["employer"], tech_by_context),
        "responsibilities": responsibilities,
        "achievements": achievements,
    }


# Matches the category labels used in the user's own main.tex template
# (Skills & Technologies section) so the rendered CV's grouping is identical
# to what they already hand-authored, not a re-derived approximation.
_CATEGORY_LABELS = {
    "cloud_and_infrastructure": "Cloud & Infrastructure",
    "ci_cd_and_pipelines": "CI/CD & Pipelines",
    "backend": "Backend",
    "databases": "Databases",
    "observability": "Observability",
    "security": "Security",
    "data_and_analysis": "Data & Analysis",
    "testing": "Testing",
}


def _convert_skills(sp: dict) -> list[dict]:
    seen: dict[str, dict] = {}
    for category_key, category_skills in sp.get("skills", {}).get("categories", {}).items():
        label = _CATEGORY_LABELS.get(category_key, category_key.replace("_", " ").title())
        for name in category_skills:
            key = name.lower()
            if key not in seen:
                seen[key] = {
                    "id": f"skill_{_slugify(name)}",
                    "name": name,
                    "level": "experienced",
                    "category": label,
                    "evidence_refs": [],
                }
    return list(seen.values())


def _convert_languages(sp: dict) -> list[dict]:
    return [
        {"name": lang["language"], "level": lang.get("level", "")}
        for lang in sp.get("skills", {}).get("languages", [])
    ]


def _convert_education(sp: dict) -> list[dict]:
    out = []
    for i, edu in enumerate(sp.get("education", [])):
        degree = edu.get("degree", "")
        if edu.get("specialization"):
            degree = f"{degree}, {edu['specialization']}"
        out.append(
            {
                "id": f"edu_{i + 1}",
                "institution": edu.get("institution", ""),
                "degree": degree,
                "start_date": str(edu["start"]) if edu.get("start") else None,
                "end_date": str(edu["end"]) if edu.get("end") else None,
            }
        )
    return out


def _convert_certifications(sp: dict) -> list[dict]:
    out = []
    for i, cert in enumerate(sp.get("certifications", [])):
        name = cert.get("exact_text") or cert.get("name") or cert.get("acronym") or f"certification_{i + 1}"
        out.append(
            {
                "id": f"cert_{_slugify(cert.get('acronym') or cert.get('name') or str(i + 1))}",
                "name": name,
                "issuer": cert.get("issuing_organization"),
                "issued_date": cert.get("issue_date"),
            }
        )
    return out


def _convert_projects(sp: dict) -> list[dict]:
    out = []
    for proj in sp.get("projects", []):
        text = proj.get("exact_text", "")
        statement = " ".join(text) if isinstance(text, list) else text
        out.append(
            {
                "id": proj["id"],
                "name": proj["name"],
                "statement": statement,
                "technologies": [],
                "evidence_level": "verified",
            }
        )
    return out


def convert(source: dict, photo_path: str | None = None) -> dict:
    sp = source["structured_profile"]
    identity = sp["identity"]
    contact = identity.get("contact", {})

    links = {}
    for platform in ("linkedin", "github"):
        val = contact.get(platform)
        if isinstance(val, dict) and val.get("url"):
            links[platform] = val["url"]
        elif isinstance(val, str):
            links[platform] = val

    person = {
        "full_name": identity["full_name"],
        "location": identity.get("location", {}).get("display"),
        "email": contact.get("email"),
        "phone": contact.get("phone"),
        "certification_tagline": identity.get("certification_tagline"),
        "focus_tagline": identity.get("focus_tagline"),
        "photo_path": photo_path,
        "links": links,
    }

    summary = sp.get("professional_summary", {})
    summary_facts = [
        {"id": f"summary_{i + 1}", "statement": claim, "evidence_level": "verified"}
        for i, claim in enumerate(summary.get("exact_claims", []))
    ]
    if not summary_facts and summary.get("exact_text"):
        summary_facts = [{"id": "summary_1", "statement": summary["exact_text"], "evidence_level": "verified"}]

    tech_by_context = source.get("derived_indexes", {}).get("demonstrated_technologies_by_context", {})
    experience = [_convert_experience_entry(exp, tech_by_context) for exp in sp.get("experience", [])]

    focus_tagline = identity.get("focus_tagline", "")
    target_roles = [p.strip() for p in re.split(r"[·|]", focus_tagline) if p.strip()]

    return {
        "schema_version": 1,
        "person": person,
        "preferences": {
            "target_roles": target_roles,
            "default_cv_language": source.get("schema", {}).get("language", "en"),
            "maximum_pages": 2,
        },
        "summary_facts": summary_facts,
        "experience": experience,
        "skills": _convert_skills(sp),
        "education": _convert_education(sp),
        "certifications": _convert_certifications(sp),
        "languages": _convert_languages(sp),
        "projects": _convert_projects(sp),
    }


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print("usage: convert_legacy_profile.py <source.yaml> <dest.yaml> [photo_path]", file=sys.stderr)
        sys.exit(1)
    source_path, dest_path = Path(sys.argv[1]), Path(sys.argv[2])
    photo_path = sys.argv[3] if len(sys.argv) == 4 else None
    source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    converted = convert(source, photo_path=photo_path)
    dest_path.write_text(yaml.safe_dump(converted, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"wrote {dest_path}")


if __name__ == "__main__":
    main()
