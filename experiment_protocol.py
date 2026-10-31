"""Shared quotas for the balanced feed and recognition protocol."""

PROTOCOL_VERSION = "feed30-memory60-balanced-v1"
CATEGORIES = ("real", "gan", "transformer")
GENDERS = ("F", "M")
FACES_PER_CELL = 5
FEED_SIZE = len(CATEGORIES) * len(GENDERS) * FACES_PER_CELL
NEW_SIZE = FEED_SIZE
MEMORY_SIZE = FEED_SIZE + NEW_SIZE
