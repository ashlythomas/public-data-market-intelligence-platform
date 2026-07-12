"""Deduplication utilities."""

import hashlib
from dataclasses import dataclass


@dataclass
class DeduplicationResult:
    is_duplicate: bool
    method: str
    score: float
    canonical_hash: str | None = None


def exact_hash_dedup(content_hash: str, known_hashes: set[str]) -> DeduplicationResult:
    is_dup = content_hash in known_hashes
    return DeduplicationResult(
        is_duplicate=is_dup,
        method="exact_hash",
        score=1.0 if is_dup else 0.0,
        canonical_hash=content_hash if not is_dup else None,
    )


def simhash(text: str, hashbits: int = 64) -> int:
    """Compute SimHash for near-duplicate detection."""
    tokens = text.lower().split()
    v = [0] * hashbits
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)  # noqa: S324
        for i in range(hashbits):
            bitmask = 1 << i
            if h & bitmask:
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(hashbits):
        if v[i] >= 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def near_duplicate_check(
    text: str,
    known_fingerprints: list[tuple[str, int]],
    threshold: int = 3,
) -> DeduplicationResult:
    fp = simhash(text)
    for doc_id, known_fp in known_fingerprints:
        distance = hamming_distance(fp, known_fp)
        if distance <= threshold:
            return DeduplicationResult(
                is_duplicate=True,
                method="simhash",
                score=1.0 - (distance / 64.0),
                canonical_hash=doc_id,
            )
    return DeduplicationResult(is_duplicate=False, method="simhash", score=0.0)
