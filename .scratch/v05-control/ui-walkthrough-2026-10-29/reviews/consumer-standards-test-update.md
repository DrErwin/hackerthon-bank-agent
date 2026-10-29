# Standards addendum: fixed consumer UNKNOWN test

Reviewed test-update commit: 7d9d817e (relative to affd96d289f60841396b05e5e6729c960a3de2b1)
API tree: 9bd64f4dbe33fbf7b2df286034a5053775ad5e50
Backend tree: d27249f6d2fd9bd5b568630f59c45b6f93c027cd

Result remains 0 documented-standard violations and 0 actionable baseline smells.

The only source delta is in the new UNKNOWN-transfer test. It now checks that query is available, resume is absent, and the exact originally published action set remains unchanged, rather than requiring the view to expose only query. This matches the existing API's controlled cancel action whose UNKNOWN handling queries the original operation. No production runtime behavior, permission, bank submission or recovery gate changed.

The independent Spec run's original 7 pass / 1 new-test expectation failure and corrected-node 1 pass are separate evidence; they do not constitute a new single eight-case green batch. Standards independently reviewed the test delta and did not rerun or relabel those tests. Final PR evidence-only source must preserve these API/backend trees. The earlier production Standards report remains valid for the unchanged service.py.
