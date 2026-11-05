"""Try the policy search from the command line:  python scripts\\try_search.py "your question" """

import sys

from ap_investigator.retrieval.policy_index import LocalPolicyIndex

ix = LocalPolicyIndex()
for query in sys.argv[1:]:
    hits = [f"{h['section_id']} ({h['score']})" for h in ix.search(query)]
    print(f"{query:50} -> {hits or 'NO RESULTS'}")