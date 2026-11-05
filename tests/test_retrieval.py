"""Step 4 tests: policies split into citable sections, search finds the right one, and the agent's tool returns it."""

from ap_investigator.domain import POLICY_FOR_CAUSE
from ap_investigator.retrieval.policy_index import LocalPolicyIndex, load_sections
from ap_investigator.tools import search_policy


def test_policies_are_split_into_citable_sections():
    sections = load_sections()
    ids = [s.section_id for s in sections]
    assert len(sections) > 20
    assert len(ids) == len(set(ids))                  # every section ID is unique
    assert "AP-POL-03 §2.1" in ids                    # the bank-change rule is one citable chunk


def test_every_policy_the_agent_must_cite_exists():
    ix = LocalPolicyIndex()
    for cause, section in POLICY_FOR_CAUSE.items():
        assert ix.get(section) is not None, f"{cause.value} needs {section}, which does not exist"


def test_search_finds_the_right_section_in_top3():
    ix = LocalPolicyIndex()
    queries = {   # plain-language questions, not copied from the policy text
        "invoiced more units than we received": "AP-POL-01 §2.2",
        "price on invoice higher than purchase order": "AP-POL-01 §3.1",
        "goods receipt missing": "AP-POL-01 §2.3",
        "same vendor invoice number submitted twice": "AP-POL-02 §2.1",
        "vendor blocked compliance documents expired": "AP-POL-06 §2.1",
        "vendor bank account changed last week": "AP-POL-03 §2.1",
        "invoice over approval limit needs budget owner": "AP-POL-04 §2.1",
        "invoice in USD but PO in EUR": "AP-POL-05 §2.1",
        "Peppol e-invoice failed BR-CO-15": "AP-POL-07 §2.1",
        "who is allowed to release a hold": "AP-POL-08 §3.1",
    }
    misses = [q for q, expected in queries.items()
              if expected not in [h["section_id"] for h in ix.search(q)]]
    assert len(misses) <= 1, f"not in top 3: {misses}"   # target from the plan: at least 90%


async def test_search_policy_tool_returns_citable_hits():
    result = await search_policy.invoke(arguments={"query": "bank account changed recently"}, skip_parsing=True)
    hits = result["results"]
    assert "AP-POL-03 §2.1" in [h["section_id"] for h in hits]   # the rule is in the top 3...
    assert all(h["text"] for h in hits)                         # ...with text the agent can quote