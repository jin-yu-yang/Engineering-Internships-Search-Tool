from internship_research_demo.models import Candidate


def make_candidate(**overrides) -> Candidate:
    data = {
        "company": "Acme",
        "title": "Software Engineer Intern",
        "url": "https://acme.com/jobs/1",
        "location": "Austin, TX",
        "work_mode": "hybrid",
        "field_fit": "Backend services work",
        "degree_level_evidence": "BS/MS students eligible",
        "internship_evidence": "12-week summer internship",
        "cpt_opt_evidence": "direct",
        "cpt_opt_note": "Posting says CPT/OPT accepted",
        "open_status_evidence": "Apply button is active",
        "source_urls": ["https://acme.com/jobs/1"],
    }
    data.update(overrides)
    return Candidate(**data)
