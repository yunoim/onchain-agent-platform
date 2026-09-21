"""ADR-0001: the package must contain no signing or transaction-submission code.

This is the same check `scripts/check-no-signing.sh` runs in CI, expressed as a test so it
also fails locally before a commit.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "onchain_mcp"

FORBIDDEN = [
    r"\beth_account\b",
    r"\bAccount\.",
    r"\bsign_transaction\b",
    r"\bsign_message\b",
    r"\bsignHash\b",
    r"\bsend_transaction\b",
    r"\bsend_raw_transaction\b",
    r"\beth_sendTransaction\b",
    r"\beth_sendRawTransaction\b",
    r"\bprivate_key\b",
    r"\bPRIVATE_KEY\b",
    r"\bmnemonic\b",
    r"\bconstruct_sign_and_send_raw_middleware\b",
    r"\bSignAndSendRawMiddlewareBuilder\b",
]


def test_no_signing_identifiers_in_source() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(SRC.parent)}:{line}: {match.group(0)}")
    assert not offenders, "signing-related identifiers found:\n" + "\n".join(offenders)


def test_erc20_abi_is_view_only() -> None:
    from onchain_mcp.clients.rpc import ERC20_ABI

    assert ERC20_ABI, "ABI unexpectedly empty"
    assert all(entry["stateMutability"] == "view" for entry in ERC20_ABI)
    assert {entry["name"] for entry in ERC20_ABI} == {
        "name",
        "symbol",
        "decimals",
        "totalSupply",
        "balanceOf",
    }
