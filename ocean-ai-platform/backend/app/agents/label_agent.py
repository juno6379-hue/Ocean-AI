"""Read-only label and dataset reviewer entrypoint for the coordinator."""
from app.services.label_review_agent import propose


def run(db, request, qc_output=None):
    return propose(db, request, qc_output)
