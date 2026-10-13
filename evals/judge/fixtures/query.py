"""Phase 2: keyword search over past runs, with prompt-pasteable output."""

import math
import re

from .store import MemoryStore

# Small set of low-signal English words excluded from matching. Verbs like
# "add" or "fix" are kept on purpose: they distinguish task types.
STOPWORDS = frozenset(
    "a an the to for in of and or with on at by from as "
    "is are was be been it this that these those".split()
)


def tokenize(text: str) -> set[str]:
    """Lowercased word tokens (Unicode-aware), minus stopwords and 1-char tokens."""
    return {t for t in re.findall(r"\w+", text.lower())
            if len(t) > 1 and t not in STOPWORDS}


def _idf(doc_freq: int, total: int) -> float:
    """Smoothed inverse document frequency: rarer tokens (low doc_freq) weigh
    more. Always positive — a token in every task still keeps weight 1.0."""
    return math.log((total + 1) / (doc_freq + 1)) + 1


def search(store: MemoryStore, task: str, limit: int = 5) -> list[tuple[float, dict]]:
    """Return up to `limit` (score, index entry) pairs, best match first.

    score = (IDF-weighted overlap) / (IDF-weighted query tokens): the fraction
    of the new task's keyword *signal* already seen in a past task, where common
    tokens (seen across many tasks) count for less than rare, distinctive ones.
    A full match still scores 1.0. Ties are broken by recency.
    """
    return [(score, entry)
            for score, entry, _, _ in search_stores([("", store)], task, limit)]


def search_stores(stores: list[tuple[str, MemoryStore]], task: str,
                  limit: int = 5) -> list[tuple[float, dict, str, MemoryStore]]:
    """Federated `search` over (app, store) pairs, best match first.

    Scoring matches `search`, but document frequencies span the combined
    corpus and there is no per-app boost. Each match carries its origin app
    tag (empty = untagged single-store mode) and its owning store — run ids
    are only unique within one store, so full records must be loaded from
    the store the match came from. Ties: score, then recency, then app name.
    """
    query_tokens = tokenize(task)
    if not query_tokens:
        return []
    corpus = [(entry, tokenize(entry["task"]), app, store)
              for app, store in stores for entry in store.load_index()]
    total = len(corpus)
    if total == 0:
        return []
    # Weight each query token by how rare it is across all past tasks.
    weight = {
        token: _idf(sum(token in toks for _, toks, _, _ in corpus), total)
        for token in query_tokens
    }
    query_weight = sum(weight.values())
    scored = []
    for entry, toks, app, store in corpus:
        overlap = query_tokens & toks
        if overlap:
            scored.append((sum(weight[t] for t in overlap) / query_weight,
                           entry, app, store))
    scored.sort(key=lambda match: match[2])
    scored.sort(key=lambda match: match[1]["timestamp"], reverse=True)
    scored.sort(key=lambda match: match[0], reverse=True)
    return scored[:limit]


def format_query_output(store: MemoryStore, task: str, limit: int = 5, *,
                        stores: list[tuple[str, MemoryStore]] | None = None) -> str:
    """Render search results as markdown ready to paste into a prompt.

    With `stores` (see federation.resolve_stores) the search federates across
    all of them: items gain an [app] origin tag and the header total counts
    every store's runs. Without it, single-store output is unchanged.
    """
    stores = stores or [("", store)]
    matches = search_stores(stores, task, limit)
    if not matches:
        return "No relevant past runs found for this task."
    total = sum(len(s.load_index()) for _, s in stores)
    lines = [f"## Relevant past runs ({len(matches)} of {total} in memory)", ""]
    for i, (score, entry, app, owner) in enumerate(matches, 1):
        record = owner.load_run(entry["id"]) or entry
        date = entry["timestamp"][:10]
        tag = f" [{app}]" if app else ""
        lines.append(f'{i}. [{entry["outcome"].upper()}] {date}{tag} — '
                     f'"{entry["task"]}" (match {score:.2f})')
        if record.get("result"):
            lines.append(f"   Result: {record['result']}")
        learnings = record.get("learnings") or []
        if learnings:
            lines.append("   Learnings:")
            lines.extend(f"   - {learning}" for learning in learnings)
    return "\n".join(lines)
