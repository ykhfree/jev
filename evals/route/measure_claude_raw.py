"""Claude on the raw transcript tails (raw_contexts.json): accuracy and latency, to set beside
`jev_raw` in report.md. eval_route.py runs Claude on the summarized context only.

Calls run one at a time so duration_ms is not inflated by concurrent calls. Cached in
claude_raw_cache.json, so re-runs are free.
Run with the jev venv: ~/.local/pipx/venvs/jev/bin/python measure_claude_raw.py
"""

import json
from statistics import median

from eval_route import CLAUDE_MODEL, CLAUDE_SYSTEM, HERE, claude_input, parse_label
from evalkit import Cache, run_claude


def main():
    cases = {c["id"]: c for c in json.loads((HERE / "cases.json").read_text())}
    raw_contexts = json.loads((HERE / "raw_contexts.json").read_text())
    independent = {
        x["id"]: (x["label"], x["ambiguous"]) for x in json.loads((HERE / "labels_independent.json").read_text())
    }
    jev_raw = {r["id"]: r["jev_raw"] for r in json.loads((HERE / "results.json").read_text())}
    cache = Cache(HERE / "claude_raw_cache.json")

    rows = []
    for case_id, context in raw_contexts.items():
        case = cases[case_id]
        text = claude_input({**case, "context": context})
        out = cache.get(
            ["claude_raw", CLAUDE_MODEL, CLAUDE_SYSTEM, text],
            lambda: run_claude(CLAUDE_SYSTEM, text, CLAUDE_MODEL, json_output=True),
        )
        rows.append({
            "id": case_id,
            "gold": case["gold"],
            "clear": independent.get(case_id) == (case["gold"], False),
            "claude_raw": parse_label(out["text"]),
            "jev_raw": jev_raw.get(case_id),
            **{k: out[k] for k in ("input_tokens", "cache_read_tokens", "cache_creation_tokens",
                                   "output_tokens", "cost_usd", "duration_ms")},
        })

    for arm in ("claude_raw", "jev_raw"):
        for name, subset in (("all", rows), ("clear", [r for r in rows if r["clear"]])):
            hits = sum(r[arm] == r["gold"] for r in subset)
            print(f"{arm} {name}: {hits}/{len(subset)}")
    for field in ("duration_ms", "cost_usd", "cache_creation_tokens", "output_tokens"):
        values = [r[field] for r in rows]
        print(f"{field}: median {median(values)}, min {min(values)}, max {max(values)}")
    for r in rows:
        if r["claude_raw"] != r["gold"]:
            print(f"miss {r['id']}: gold {r['gold']}, claude_raw {r['claude_raw']}, clear {r['clear']}")
    (HERE / "claude_raw_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
