from dataclasses import dataclass


@dataclass
class LicencePolicy:
    licence_type: str
    redistribution_allowed: bool
    commercial_use_allowed: bool
    quotation_allowed: bool = True
    quotation_limit: int | None = None
    attribution_required: bool = False


def filter_document_body(body: str, policy: LicencePolicy, *, is_commercial: bool = False) -> str:
    if not policy.redistribution_allowed:
        if policy.quotation_allowed and policy.quotation_limit:
            return body[: policy.quotation_limit] + "..."
        return ""
    if is_commercial and not policy.commercial_use_allowed:
        if policy.quotation_allowed and policy.quotation_limit:
            return body[: policy.quotation_limit] + "..."
        return ""
    return body


def can_serve_full_content(policy: LicencePolicy, *, is_commercial: bool = False) -> bool:
    if not policy.redistribution_allowed:
        return False
    return not (is_commercial and not policy.commercial_use_allowed)
