"""Server-side selection and scoring for the provisional recognition task."""

from collections import Counter
import random

from experiment_protocol import CATEGORIES, GENDERS, FACES_PER_CELL


def make_plan(study_posts: list[dict], new_posts: list[dict], rng=None) -> list[dict]:
    rng = rng or random.SystemRandom()
    if {p["stimulus_id"] for p in study_posts} & {p["stimulus_id"] for p in new_posts}:
        raise ValueError("Recognition lures must not be study stimuli")
    expected = Counter({(category, gender): FACES_PER_CELL
                        for category in CATEGORIES for gender in GENDERS})
    for target, posts in (("OLD", study_posts), ("NEW", new_posts)):
        counts = Counter((p.get("source_type"), p.get("gender")) for p in posts)
        if counts != expected:
            raise ValueError(f"Expected five female and five male faces per category for {target}")
    all_posts = study_posts + new_posts
    if len({p["stimulus_id"] for p in all_posts}) != len(all_posts):
        raise ValueError("Recognition stimulus IDs must be unique")
    # Every feed face is repeated once; lures remain separate from the feed.
    plan = [{"post_id": p["id"], "target": "OLD"} for p in study_posts]
    plan.extend({"post_id": p["id"], "target": "NEW"} for p in new_posts)
    if len({p["post_id"] for p in plan}) != len(plan):
        raise ValueError("Recognition post IDs must be unique")
    rng.shuffle(plan)
    for number, trial in enumerate(plan, 1):
        trial["trial_id"] = f"R{number:03}"
    return plan


def score_response(plan: list[dict], post_id: str, choice: str) -> dict:
    targets = {p["post_id"]: p["target"] for p in plan}
    if post_id not in targets or not isinstance(choice, str) or choice not in {"OLD", "NEW"}:
        raise ValueError("Invalid recognition response")
    return {"response": choice, "target": targets[post_id],
            "correct": choice == targets[post_id]}
