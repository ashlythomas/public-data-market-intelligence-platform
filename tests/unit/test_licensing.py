"""Unit tests for source licensing."""

from mip_source_licensing import LicencePolicy, can_serve_full_content, filter_document_body


def test_filter_restricted_source():
    policy = LicencePolicy(
        licence_type="restricted",
        redistribution_allowed=False,
        commercial_use_allowed=False,
        quotation_allowed=True,
        quotation_limit=100,
    )
    body = "A" * 500
    filtered = filter_document_body(body, policy)
    assert len(filtered) <= 103


def test_filter_commercial_restricted():
    policy = LicencePolicy(
        licence_type="cc-by-nc",
        redistribution_allowed=True,
        commercial_use_allowed=False,
        quotation_allowed=True,
        quotation_limit=200,
    )
    body = "B" * 500
    filtered = filter_document_body(body, policy, is_commercial=True)
    assert len(filtered) <= 203


def test_can_serve_full_content():
    policy = LicencePolicy(
        licence_type="public_domain",
        redistribution_allowed=True,
        commercial_use_allowed=True,
    )
    assert can_serve_full_content(policy)
    assert can_serve_full_content(policy, is_commercial=True)
