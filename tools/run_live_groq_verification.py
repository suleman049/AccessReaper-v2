"""
Live verification script:
Generates AI explanations for the latest audit run using Groq (openai/gpt-oss-120b)
with the key loaded from .env.
Reports success, model, token usage, and status.
CRITICAL: Zero secret keys are logged or printed.
"""

import sys

sys.path.insert(0, "D:/AccessReaper-v2/backend")

from app.db.models import AIExplanation, Assignment, AuditRun
from app.db.session import SessionLocal
from app.services.llm.budget import get_daily_token_usage
from app.services.llm.manager import llm_manager


def main():
    db = SessionLocal()
    latest_run = db.query(AuditRun).order_by(AuditRun.completed_at.desc()).first()
    if not latest_run:
        print("Error: No audit runs found.")
        sys.exit(1)

    print(f"Targeting audit run: {latest_run.id}")

    # Clear prior cached explanations for this run so live Groq is called
    deleted_count = db.query(AIExplanation).filter(AIExplanation.run_id == latest_run.id).delete()
    db.commit()
    print(f"Cleared {deleted_count} cached explanation(s) for {latest_run.id}")

    # Fetch assignments matching the audit run data origin
    if latest_run.sample:
        assignments = db.query(Assignment).filter(Assignment.origin == "sample").all()
    else:
        assignments = db.query(Assignment).filter(Assignment.origin == "github").all()
    print(f"Evaluating across {len(assignments)} assignments (sample={latest_run.sample})")

    tokens_before = get_daily_token_usage(db)

    try:
        # Generate explanations
        summary_obj, finding_objs = llm_manager.generate_explanations(db, latest_run, assignments)
        db.commit()
    except Exception as e:
        import traceback
        print("Exception during generate_explanations:", e)
        traceback.print_exc()
        raise

    tokens_after = get_daily_token_usage(db)
    tokens_used = tokens_after - tokens_before

    print("\n--- Live Groq Explanation Results ---")
    print(f"Run ID: {latest_run.id}")
    print(f"Explanation Status: {summary_obj.status}")
    print(f"Model Recorded: {summary_obj.model}")
    print(f"Tokens Consumed: {tokens_used}")
    print(f"Total Daily Tokens: {tokens_after}")
    print(f"Findings Generated: {len(finding_objs)}")
    print(f"Executive Summary:\n{summary_obj.summary_text}")
    print("--------------------------------------")


if __name__ == "__main__":
    main()
