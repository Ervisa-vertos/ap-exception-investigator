"""Step 3 tests: the agent's tools are read-only, describe themselves, and reject malformed arguments."""

import pytest

from ap_investigator.tools import READ_TOOLS, get_invoice, get_matching_details


def test_tools_are_read_only():
    names = {t.name for t in READ_TOOLS}
    assert not names & {"release_hold", "request_credit_note", "set_invoice_released"}
    assert all(n.startswith(("get_", "find_", "search_")) for n in names)


def test_every_tool_describes_itself_to_the_model():
    for t in READ_TOOLS:
        spec = t.to_json_schema_spec()["function"]
        assert len(spec["description"]) > 20, t.name     # the model chooses tools by their description
        assert spec["parameters"]["required"], t.name    # every tool says which arguments it needs


def test_invoice_id_format_is_part_of_the_schema():
    params = get_invoice.to_json_schema_spec()["function"]["parameters"]
    assert params["properties"]["invoice_id"]["pattern"] == r"^INV-\d{4}$"


async def test_tool_returns_repository_facts(cases):
    c = next(c for c in cases if c["scenario"] == "qty_mismatch")
    result = await get_matching_details.invoke(arguments={"invoice_id": c["invoice_id"]}, skip_parsing=True)
    assert result["invoice_id"] == c["invoice_id"]
    assert result["lines"][0]["received_qty"] < result["lines"][0]["invoiced_qty"]


async def test_malformed_arguments_are_rejected_before_the_erp_is_called():
    # A model might send "invoice 1001". The framework checks it against the schema and refuses.
    with pytest.raises(TypeError, match="Invalid arguments"):
        await get_invoice.invoke(arguments={"invoice_id": "invoice 1001"})