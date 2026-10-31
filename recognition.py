"""Server-side selection and scoring for the provisional recognition task."""

import random


def make_plan(study_posts: list[dict], new_posts: list[dict], rng=None) -> list[dict]:
    rng = rng or random.SystemRandom()
    if {p["stimulus_id"] for p in study_posts} & {p["stimulus_id"] for p in new_posts}:
        raise ValueError("Recognition lures must not be study stimuli")
    # Equal representation of real and generated faces in each memory condition.
    old = []
    for kind in ("real", "deepfake"):
        candidates = [p for p in study_posts if p["stimulus_type"] == kind]
        lures = [p for p in new_posts if p["stimulus_type"] == kind]
        if len(lures) != 5 or len(candidates) < 5:
            raise ValueError("Expected five new faces and at least five old faces per class")
        old.extend(rng.sample(candidates, 5))
    plan = [{"post_id": p["id"], "target": "OLD"} for p in old]
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
