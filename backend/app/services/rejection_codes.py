"""
ATON Rejection Code dictionary and per-code confidence scores.

Confidence score semantics:
  High (≥ 0.70) → Routine fix; AI suggestion is safe and reversible
                   (e.g. name spelling correction).
  Mid  (0.50–0.69) → Moderate risk; fix requires account-level data change
                      or partial liquidation.
  Low  (< 0.50) → High-risk / irreversible action (taxable event, liquidation)
                  — human must scrutinise carefully before approving.
"""

REJECTION_CODES: dict[str, str] = {
    "CDSX-ATON-NM-001": (
        "LEGAL NAME MISMATCH BETWEEN DELIVERING AND RECEIVING RECORDS"
    ),
    "FS-ATON-RA-002": (
        "REGISTERED ACCOUNT TYPE MISMATCH"
    ),
    "FS-ATON-IA-003": (
        "FRACTIONAL SHARES DETECTED — IN-KIND TRANSFER NOT PERMITTED"
    ),
    "FS-ATON-MF-004": (
        "PROPRIETARY MUTUAL FUND / ASSET TYPE NOT SUPPORTED"
    ),
}

CONFIDENCE_MAP: dict[str, float] = {
    "CDSX-ATON-NM-001": 0.88,   # Name fix — low risk, easy to verify
    "FS-ATON-RA-002":   0.75,   # Account type change — requires ops attention
    "FS-ATON-IA-003":   0.55,   # Fractional share rounding — moderate risk
    "FS-ATON-MF-004":   0.30,   # Forced liquidation — potential taxable event
}

DEFAULT_CONFIDENCE: float = 0.40  # Unknown codes default to conservative score


def get_code_description(code: str) -> str:
    """Return human-readable description for a rejection code."""
    return REJECTION_CODES.get(code, f"Unknown rejection code: {code}")


def get_code_confidence(code: str) -> float:
    """Return confidence score for a rejection code."""
    return CONFIDENCE_MAP.get(code, DEFAULT_CONFIDENCE)


def compute_confidence(codes: list[str]) -> float:
    """
    Compute the aggregate confidence score as the mean of each code's score.
    A single low-risk code drives the score down conservatively.
    """
    if not codes:
        return DEFAULT_CONFIDENCE
    scores = [get_code_confidence(c) for c in codes]
    return round(sum(scores) / len(scores), 4)
