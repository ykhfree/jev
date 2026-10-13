import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/ykhfree/AI/jev")
import jev  # noqa: E402

HERE = Path("/Users/ykhfree/AI/jev/evals/judge")
V, C, U = "verified", "contradicted", "unsupported"

# (id, kind, file, claim, quote, gold_section, gold_file, expected_span, settle_line, note)
RAW = [
    # ---------------- easy ----------------
    ("easy", "jev.py",
     "normalize() folds curly quotes to straight ones and collapses every run of whitespace into a single space.",
     'return re.sub(r"\\s+", " ", text.translate(QUOTE_FOLD)).strip()',
     V, V, (306, 306), None,
     "L306 translates with QUOTE_FOLD and re.sub(r'\\s+', ' ') then strips; L305 docstring says the same"),
    ("easy", "jev.py",
     "CHOICE_SURE 임계값은 0.7이라서, claims 결과는 confidence가 0.7 이상이면 review 없이 채택된다.",
     "CHOICE_SURE = 0.8  # citation_check cookbook: auto-accept at confidence >= 0.8",
     C, C, (20, 20), None,
     "L20 sets CHOICE_SURE = 0.8, not 0.7"),
    ("easy", "jev.py",
     "check_claim은 대상 파일이 없으면 verdict를 file_missing으로 하고 review를 True로 표시한다.",
     'return {**out, "verdict": "file_missing", "review": True}',
     V, V, (336, 336), None,
     "L335-336: FileNotFoundError -> verdict file_missing, review True"),
    ("easy", "jev.py",
     "split_passages merges short consecutive paragraphs into one passage until it reaches PASSAGE_CHARS.",
     "Paragraphs are never merged: an injected paragraph would otherwise take clean evidence down with it.",
     C, C, (368, 369), None,
     "L368-369 docstring: paragraphs are never merged; L371-373 split per paragraph and only cut long ones"),
    ("easy", "store.py",
     "Run records are stored in per-month folders, runs/<YYYY-MM>/<id>.json, with the month taken from the id prefix.",
     'return self.runs_dir / run_id[:7] / f"{run_id}.json"',
     V, V, (87, 87), None,
     "L86-87: runs_dir / run_id[:7] / <id>.json; ids start with YYYY-MM (L95)"),
    ("easy", "distill.py",
     "run_claude는 프롬프트를 `claude -p`의 명령행 인자로 넘긴다.",
     'proc = subprocess.run([claude_cmd, "-p"], input=prompt,',
     C, C, (63, 63), None,
     "L61 docstring and L63: argv is [claude_cmd, '-p'], prompt goes via input= (stdin)"),
    ("easy", "query.py",
     "When no past run matches, format_query_output returns an empty string.",
     'return "No relevant past runs found for this task."',
     C, C, (87, 87), None,
     "L86-87: no matches -> returns 'No relevant past runs found for this task.'"),
    ("easy", "eval_route.py",
     "Cache.get은 모델 호출(compute)을 lock 밖에서 실행하므로 여러 스레드의 모델 호출이 lock 때문에 직렬화되지 않는다.",
     "value = compute()  # outside the lock so model calls still run in parallel",
     V, V, (173, 173), None,
     "L170-176: lock held only for the lookup and the store; L173 compute() runs outside it"),

    # ---------------- subtle: contradicted ----------------
    ("subtle", "jev.py",
     "memgate_verdict는 duplicate를 conflict보다 먼저 검사하므로, duplicate와 conflict 점수가 둘 다 높으면 verdict는 duplicate가 된다.",
     "if any(c >= CONFLICT_MIN for c in conflicts):",
     C, C, (272, 272), None,
     "L270-275: conflict is checked first (L272) and returns before the duplicate check (L274)"),
    ("subtle", "jev.py",
     "check_claim flags review: true when the confidence is exactly CHOICE_SURE.",
     '"review": answer["confidence"] < CHOICE_SURE,',
     C, C, (350, 350), None,
     "L350 uses strict <, so confidence == CHOICE_SURE gives review False"),
    ("subtle", "eval_route.py",
     "suggestion_block treats a route whose confidence equals GATE as below the gate and emits 'No handler stands out'.",
     'if route["confidence"] >= GATE:',
     C, C, (141, 141), None,
     "L141 uses >=, so confidence == GATE takes the suggestion branch (L142-145), not L147"),
    ("subtle", "query.py",
     "search_stores breaks score ties by app name first and only then by recency.",
     "scored.sort(key=lambda match: match[2])",
     C, C, (70, 70), None,
     "L70-72 are stable sorts applied app, then timestamp desc, then score desc, so ties go score > recency > app; "
     "the docstring at L48 says the same but is outside the window"),
    ("subtle", "store.py",
     "같은 분에 두 번째 run이 기록되면 그 id에는 _1 접미사가 붙는다.",
     'candidate = f"{base}_{n}"',
     C, C, (99, 99), None,
     "L96-99: n starts at 1 and is incremented before use, so the first collision gets _2 (docstring L94 agrees)"),
    ("subtle", "sync.py",
     "If CROSS_MEMORY_AUTOSYNC is set but empty, autosync_enabled falls back to its default argument.",
     "return value.strip().lower() not in _FALSEY",
     C, C, (26, 26), None,
     "L23-26: only None returns default; '' is in _FALSEY (L18) so an empty value returns False regardless of default"),
    ("subtle", "query.py",
     "_idf는 모든 과거 task에 등장하는 토큰에 가중치 0을 준다.",
     "return math.log((total + 1) / (doc_freq + 1)) + 1",
     C, C, (25, 25), None,
     "L25: doc_freq == total gives log(1) + 1 = 1.0; docstring L23-24 says a token in every task keeps weight 1.0"),

    # ---------------- subtle: verified ----------------
    ("subtle", "jev.py",
     "When the best exists score is below FIND_FOUND, cmd_find reports 'partial', not 'absent', if that score is exactly FIND_ABSENT.",
     'verdict = "absent" if exists < FIND_ABSENT else "partial"',
     V, V, (226, 226), None,
     "L223-226: below FIND_FOUND the else branch uses strict <, so exists == FIND_ABSENT gives 'partial'"),
    ("subtle", "jev.py",
     "conflict나 duplicate가 없을 때, reuse 점수가 unsure band 하한과 정확히 같으면 memgate_verdict는 uncertain이 아니라 skip을 반환한다.",
     "lo, hi = UNSURE_BAND",
     V, V, (268, 268), None,
     "L276 skip check uses p <= lo and runs before the uncertain check at L278"),
    ("subtle", "jev.py",
     "locate_quote can match a quote that spans a blank line, because blank lines are dropped before the lines are joined.",
     "if not norm:",
     V, V, (317, 317), None,
     "L316-322: blank lines are skipped (continue) and the rest joined with single spaces, so text around a blank line is contiguous"),
    ("subtle", "eval_route.py",
     "parse_label은 출력에 서로 다른 라벨이 두 개 언급되면(예: 'not fast-worker, use self') 첫 번째 라벨이 아니라 None을 반환한다.",
     "return found[0] if len(set(found)) == 1 else None",
     V, V, (158, 158), None,
     "L157-158: findall collects every label; two distinct labels -> len(set) == 2 -> None"),
    ("subtle", "distill.py",
     "approve는 proposed.md의 bullet이 전부 기존 rules와 중복이어도 proposed.md를 삭제한다.",
     "store.proposed_path.unlink()",
     V, V, (113, 113), None,
     "L106-113: unlink at L113 is outside the `if new:` block, so it runs even when new is empty"),
    ("subtle", "sync.py",
     "CROSS_MEMORY_AUTOSYNC=' OFF ' (padded, upper-case) disables autosync.",
     'value = os.environ.get(AUTOSYNC_ENV)',
     V, V, (23, 23), None,
     "L26 strips and lowercases before checking _FALSEY (L18 contains 'off'), so ' OFF ' -> False"),
    ("subtle", "store.py",
     "load_index rebuilds the index from runs/ when index.json is valid JSON but has no 'runs' key.",
     "except (OSError, ValueError, KeyError, TypeError):",
     V, V, (127, 127), None,
     "L126 data['runs'] raises KeyError, caught at L127, which returns rebuild_index() (L128)"),

    # ---------------- outside_window ----------------
    ("outside_window", "jev.py",
     "read_text refuses to send a file named id_ed25519.pub.",
     "if SECRET_NAME.match(p.name):",
     U, V, (180, 180), 42,
     "L180 checks SECRET_NAME; the pattern id_(rsa|dsa|ecdsa|ed25519).* that matches id_ed25519.pub is at L42, outside 165-195"),
    ("outside_window", "jev.py",
     "conflict나 duplicate가 없으면, memgate는 noise 점수가 0.7 이상일 때 skip을 반환한다.",
     'if any(p <= lo for p in wanted) or scores["noise"] >= hi:',
     U, V, (276, 276), 19,
     "L276 skips on noise >= hi; hi = UNSURE_BAND[1] = 0.7 is defined at L19, outside 261-291"),
    ("outside_window", "jev.py",
     "The section check_claim sends to Jev covers 10 lines on each side of the quote.",
     'section = "\\n".join(lines[max(0, first - 1 - CLAIM_CONTEXT_LINES) : last + CLAIM_CONTEXT_LINES])',
     U, C, (343, 343), 38,
     "L343 uses CLAIM_CONTEXT_LINES, which is 15 (L38, outside 328-358), not 10"),
    ("outside_window", "jev.py",
     "screen에서 contains_answer_evidence 점수가 정확히 0.55인 passage는 include로 분류된다.",
     'if answers["contains_answer_evidence"] > SCREEN["evidence_min"]:',
     U, C, (385, 385), 28,
     "L385 needs > evidence_min; evidence_min = 0.55 at L28 (outside 370-400), so 0.55 falls to exclude/no_evidence"),
    ("outside_window", "store.py",
     "rebuild_index가 만드는 인덱스 항목에는 learnings가 없고 id, timestamp, task, outcome 필드만 들어간다.",
     'entries.append({key: record.get(key, "") for key in INDEX_FIELDS})',
     U, V, (138, 138), 14,
     "L138 copies INDEX_FIELDS, defined at L14 as (id, timestamp, task, outcome), outside 123-153"),
    ("outside_window", "eval_route.py",
     "compose_rules는 noul 점수가 0.4 이상이면 해당 규칙을 yes로 본다.",
     "yes = {k: v >= NOUL_YES for k, v in nouls.items()}",
     U, C, (127, 127), 35,
     "L127 compares against NOUL_YES, which is 0.5 at L35 (outside 112-142), so 0.4-0.49 counts as no"),
    ("outside_window", "distill.py",
     "run_claude gives the claude CLI 60 seconds before raising a timeout error.",
     'raise CrossMemoryError(f"claude CLI timed out after {CLAUDE_TIMEOUT}s")',
     U, C, (69, 69), 16,
     "L64/L69 use CLAUDE_TIMEOUT, which is 300 at L16 (outside 54-84), not 60"),
    ("outside_window", "sync.py",
     "sync_to_git gives git push a 30-second timeout.",
     'push = _git(root, "push", timeout=PUSH_TIMEOUT)',
     U, V, (57, 57), 15,
     "L57 passes PUSH_TIMEOUT, defined as 30 at L15, outside 42-72"),

    # ---------------- unrelated ----------------
    ("unrelated", "jev.py",
     "locate_quote는 10만 줄짜리 파일에서도 50ms 안에 끝난다.",
     'hit = " ".join(parts).find(needle)',
     U, U, (323, 323), None,
     "performance claim; no timing or size data anywhere in the file"),
    ("unrelated", "jev.py",
     "cmd_claims is invoked by a git pre-commit hook in this repository.",
     'return {"claims": pmap(lambda c: check_claim(c, ask), claims)}',
     U, U, (363, 363), None,
     "claim about an external caller; the file only wires cmd_claims to the argparse subcommand (L441-443)"),
    ("unrelated", "jev.py",
     "TypeSafeClient는 429 rate limit 응답을 받으면 SDK 내부에서 지수 백오프로 재시도한다.",
     "response = client.system_one(state, questions)",
     U, U, (150, 150), None,
     "behaviour of the external typesafe_sdk client; the file only calls client.system_one"),
    ("unrelated", "eval_route.py",
     "The claude -p calls in this eval usually finish in under 10 seconds.",
     "capture_output=True, text=True, timeout=300, cwd=gettempdir(),",
     U, U, (193, 193), None,
     "typical latency is not in the code; timeout=300 (L193) is only an upper bound"),
    ("unrelated", "eval_route.py",
     "Opus 모델은 이 라우팅 eval의 52개 케이스를 모두 맞혔다.",
     'CLAUDE_MODEL = "opus"',
     U, U, (36, 36), None,
     "results are in results.json/report.md, not in the code"),
    ("unrelated", "store.py",
     "record_run is called by the CLI's `record` subcommand after it validates the arguments.",
     "def record_run(self, task: str, outcome: str, result: str,",
     U, U, (45, 45), None,
     "caller lives in cli.py, not in this file"),
    ("unrelated", "query.py",
     "search_stores는 run이 1만 건인 저장소에서 한 번 조회에 100ms 이상 걸린다.",
     "corpus = [(entry, tokenize(entry[\"task\"]), app, store)",
     U, U, (53, 53), None,
     "performance claim; no timing data in the file"),
    ("unrelated", "query.py",
     "`cross-memory brief` reuses format_query_output to print its past-run section.",
     'record = owner.load_run(entry["id"]) or entry',
     U, U, (91, 91), None,
     "claim about a caller in brief.py, which is not in this file; the file never mentions brief"),
    ("unrelated", "distill.py",
     "distill은 매일 밤 cron 작업으로 자동 실행된다.",
     "def distill(store: MemoryStore, runner: Callable[[str], str] = run_claude,",
     U, U, (80, 80), None,
     "scheduling is outside this module; the file only defines the function"),
    ("unrelated", "sync.py",
     "cross-memory에서 git 명령은 이 sync 모듈을 통해서만 실행되고, 다른 모듈은 git을 직접 호출하지 않는다.",
     'return subprocess.run(["git", "-C", str(cwd), *args],',
     U, U, (74, 74), None,
     "overreach: other modules (cli.py etc.) are not in this file, so 'only through this module' cannot be settled"),
]


def main():
    cases = []
    for i, (kind, name, claim, quote, gs, gf, want, settle, note) in enumerate(RAW, 1):
        path = HERE / "fixtures" / name
        text = path.read_text(encoding="utf-8")
        span = jev.locate_quote(text, quote)
        cid = f"c{i:02d}"
        assert span == want, (cid, span, want)
        first, last = span
        lo, hi = max(1, first - jev.CLAIM_CONTEXT_LINES), last + jev.CLAIM_CONTEXT_LINES
        if kind == "outside_window":
            assert settle < lo or settle > hi, (cid, settle, lo, hi)
            assert gs == U and gf != U, cid
        else:
            assert gs == gf, cid
        cases.append({"id": cid, "kind": kind, "claim": claim, "file": f"fixtures/{name}",
                      "quote": quote, "gold_section": gs, "gold_file": gf, "note": note})
        if "--show" in sys.argv:
            lines = text.splitlines()
            section = lines[max(0, first - 1 - jev.CLAIM_CONTEXT_LINES): last + jev.CLAIM_CONTEXT_LINES]
            print(f"===== {cid} [{kind}] {name} span={span} window={lo}-{min(hi, len(lines))} gold={gs}/{gf}")
            print("CLAIM:", claim)
            for n, line in enumerate(section, lo):
                mark = ">>" if first <= n <= last else "  "
                print(f"{mark}{n:4d}| {line}")
    if "--write" in sys.argv:
        (HERE / "claims_cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1) + "\n")
    print(len(cases), "cases ok")


main()
