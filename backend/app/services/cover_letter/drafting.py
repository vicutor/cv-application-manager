"""Cover-letter drafting: a very short (~110-160 word), evidence-bound letter
tailored to one specific posting. Same anti-fabrication discipline as CV
drafting (Etap C) -- every paragraph must cite real fact id(s) -- reused from
there via the shared fact-catalog/evidence-text formatting helpers, since the
input shape is identical.

Unlike CV bullets, an invalid citation here can't be dropped and salvaged: a
3-paragraph letter missing a paragraph reads as broken, not just shorter. See
validate_cover_letter_draft() in this package's __init__ for how a bad
citation fails the whole draft instead.
"""

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.job_analysis import EvidenceMatch
from app.models.job_posting import JobPosting
from app.services.candidate_profile.schema import CandidateProfile
from app.services.cv_generation.drafting import (
    _confirmed_evidence_text,
    _fact_catalog_by_experience,
    _skills_text,
    _summary_facts_text,
)
from app.services.cv_generation.llm_client import call_structured

PROMPT_VERSION = "cover-letter-drafting-v1"

_SYSTEM_PROMPT = """You are writing a very short, sharp cover letter for one
specific job application -- the kind that makes a recruiter reading dozens of
generic letters actually stop and read, because it's obviously written by
someone who read the posting and has real, well-matched experience. It must
read like a sharp, understated human wrote it in five focused minutes, not
like a template with the company name swapped in.

You will receive the same job requirements, confirmed evidence, and candidate
fact catalog used for CV generation.

HARD RULES -- same discipline as CV generation, no exceptions:
- Every paragraph must be traceable to real fact id(s) you cite in
  source_fact_ids. Never invent a company, metric, date, technology, or
  outcome not in the candidate's own fact catalog.
- Never upgrade a proof-of-concept, personal project, or "familiar with" fact
  into hands-on production experience.
- The letter is not the place to repeat the whole CV -- it exists to make one
  sharp case, not to list everything.

VOICE -- this matters as much as the content:
The candidate is laid-back and easygoing, and that needs to actually come
through, not just avoid sounding corporate. Write like a chill, confident
engineer talking to another engineer over coffee, not like a technical
report or a resume bullet list stretched into sentences. Use contractions
("I've", "that's", "here's", "didn't"). A little genuine wit, a wry
aside, or an understated joke is welcome if it grows naturally out of a real
detail -- you don't have to stay deadpan-serious the whole letter. What's
NOT welcome: forcing a joke that isn't earned, wordplay for its own sake, or
emoji. The test isn't "did I avoid AI-sounding words", it's "would a
recruiter reading this picture a specific, likeable person, not a
well-optimized paragraph." If the whole letter could be read aloud in a flat
monotone and still sound the same, rewrite it.

DENSITY -- the single most common way this goes wrong: cramming.
A paragraph that lists four or five technical facts back to back, separated
by commas, reads like an inventory no matter how good the individual facts
are -- that's true even when every fact is real and relevant. Each paragraph
gets ONE idea and enough room to actually land it. If you're tempted to
connect three achievements with commas in one sentence, that's the signal to
cut two of them, not to write a longer sentence.

LENGTH AND STRUCTURE -- exactly 3 paragraphs, ~110-160 words total:
- No greeting line ("Dear Hiring Manager"), no subject line, no sign-off
  ("Best regards," / name) -- the surrounding template handles those, you
  only write the body paragraphs.
- Paragraph 1: ONE sharp, specific, true hook -- a real, well-chosen detail
  from the candidate's background connected directly to what this job
  actually needs, told like a small story or observation, not a claim
  ("I spent a week chasing X" beats "I have experience with X"). This is
  where personality shows up first. Never open with "I am writing to express
  my interest" or any variant of it.
- Paragraph 2: the ONE strongest concrete proof point for this job's actual
  requirements -- a single achievement, told with enough specific detail to
  be vivid, not a list of everything that's technically relevant. Confident,
  not a pitch.
- Paragraph 3 (short, 1-2 sentences): a confident, specific close that shows
  a genuine read of what this role or company needs -- and is allowed to be
  the most casual, human line in the letter. Never "I look forward to
  hearing from you" or "please don't hesitate to contact me" or similar
  boilerplate.

STACK-GAP BRIDGING -- only when it actually applies:
Compare what this job requires (must-have/nice-to-have requirements, ATS
keywords, listed technologies) against the candidate's own fact catalog and
technologies. If the job wants a technology the candidate hasn't personally
used, but the candidate has real, demonstrated hands-on experience with a
closely equivalent one in the same category -- cloud platforms (GCP / AWS /
Azure), managed Kubernetes (GKE / EKS / AKS), CI/CD engines (GitHub Actions /
GitLab CI / Jenkins), and similar well-known sibling pairs -- then name the
candidate's REAL technology explicitly, state plainly that the underlying
concepts and skills transfer directly, and express genuine confidence about
ramping up fast on the specific tool. Never claim hands-on experience with
the job's specific requested technology if the candidate hasn't used it --
bridge the gap with an honest, confident comparison, not a false claim. If
there's no meaningful stack gap, don't force this device in at all -- set
stack_gap_bridged to false and skip it.

WORD CHOICE -- must not read as AI-written:
- No em dashes as connective tissue -- use a comma or two sentences instead.
- Cut hollow intensifiers ("truly", "genuinely", "really"), hedging filler
  ("it's worth noting that"), and generic transitions ("moreover",
  "furthermore", "additionally").
- Replace on sight: "leverage" -> use, "robust" -> strong/reliable,
  "seamless(ly)" -> smooth/easy, "cutting-edge" -> latest, "comprehensive" ->
  thorough, "spearheaded" -> led/drove/ran, "streamlined" -> simplified,
  "utilize(d)" -> use(d), "passionate about" -> cut it, state the concrete
  interest instead.
- Avoid resume-cliche filler entirely: "results-driven", "detail-oriented",
  "proven track record", "dynamic professional", "team player", "go-getter".
- Avoid the rule-of-three ("adjective, adjective, and adjective") pattern.
- Vary sentence length and rhythm across the three paragraphs. Short
  sentences are good. Don't start every sentence the same way.
- State the concrete action and result, never abstract significance
  ("played a key role in", "was instrumental in").

Return exactly the paragraphs described above, each with the fact id(s) it
draws from, and stack_gap_bridged set to whether you actually used that
device."""


class CoverLetterParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    source_fact_ids: list[str]


class CoverLetterDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paragraphs: list[CoverLetterParagraph]
    stack_gap_bridged: bool


def run_cover_letter_draft(
    db: Session,
    settings: Settings,
    *,
    job: JobPosting,
    profile: CandidateProfile,
    requirements: list[dict],
    evidence_matches: list[EvidenceMatch],
    cover_letter_id: str | None = None,
) -> tuple[CoverLetterDraft, float]:
    user_content = "\n\n".join(
        [
            f"Job: {job.position_title} at {job.company_name}",
            "Requirements:\n" + "\n".join(f"- {r['id']}: {r['text']}" for r in requirements),
            "Confirmed evidence per requirement:\n" + _confirmed_evidence_text(requirements, evidence_matches),
            "Job's listed technologies:\n" + (", ".join(job.technologies) if job.technologies else "(none listed)"),
            "Candidate summary facts:\n" + _summary_facts_text(profile),
            "Candidate experience fact catalog:\n" + _fact_catalog_by_experience(profile),
            "Candidate skills:\n" + _skills_text(profile),
        ]
    )
    return call_structured(
        db,
        settings,
        stage="cover_letter_drafting",
        model=settings.llm_model_drafting,
        system_prompt=_SYSTEM_PROMPT,
        user_content=user_content,
        response_model=CoverLetterDraft,
        prompt_version=PROMPT_VERSION,
        job_posting_id=job.id,
        cover_letter_id=cover_letter_id,
        max_tokens=4096,
        effort="medium",
    )
