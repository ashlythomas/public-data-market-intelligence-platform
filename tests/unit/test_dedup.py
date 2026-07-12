"""Unit tests for deduplication."""

from mip_normalizer.dedup import exact_hash_dedup, hamming_distance, near_duplicate_check, simhash


def test_exact_hash_dedup_new():
    result = exact_hash_dedup("hash1", set())
    assert not result.is_duplicate
    assert result.method == "exact_hash"


def test_exact_hash_dedup_duplicate():
    result = exact_hash_dedup("hash1", {"hash1"})
    assert result.is_duplicate
    assert result.score == 1.0


def test_simhash_identical():
    text = "The Federal Reserve announced monetary policy changes today"
    assert simhash(text) == simhash(text)


def test_near_duplicate_similar():
    text1 = "Federal Reserve maintains interest rates unchanged policy"
    text2 = "Federal Reserve maintains interest rates unchanged policy today"
    fp1 = ("doc1", simhash(text1))
    result = near_duplicate_check(text2, [fp1], threshold=8)
    assert result.is_duplicate


def test_hamming_distance():
    assert hamming_distance(0, 0) == 0
    assert hamming_distance(1, 0) == 1
