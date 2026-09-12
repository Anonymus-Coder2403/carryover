# Research behind Carryover

Compiled 12 Sep 2026. Everything here was verified by web search during the session that
produced this repo. Treat it as the reason the design looks the way it does.

## Finding 1, the one that shapes the product

Context degradation starts long before the context window fills.

- Chroma's 2025 context rot study tested 18 frontier models including GPT 4.1, Claude 4,
  Gemini 2.5 and Qwen3. Every model tested degrades as input length grows. Not most. All.
- Rot is not overflow. A model with a 200K window can show significant degradation at 50K
  tokens. The decline is continuous, not a cliff at the limit.
- A 2026 arXiv analysis found a model holding F1 around 0.55 to 0.58 up to roughly 40% of
  maximum context, then collapsing to about 0.30 at 50%, a 45% drop, with the relevant
  information still present in context.
- Stanford's lost in the middle result: accuracy is highest when relevant information sits
  at the start or end of context and degrades by more than 30% when it sits in the middle.
  Replicated across six model families.
- Degradation is worse on multi hop reasoning than on simple lookup, so it hits hardest on
  exactly the long complex work people care about.
- Chroma also showed distractors compound the effect, and that a single distractor already
  measurably reduces performance.

Product consequence: Carryover is a hygiene tool, not a recovery tool. The pitch is "move
before quality drops", not "rescue a dead thread". This is what the health meter encodes
and why the 40% and 60% thresholds exist.

## Finding 2, the space is crowded

Direct competitors, all found on the first pass:

| Project | What it is | Why we are not it |
|---|---|---|
| OpenMemory MCP (mem0), May 2025 | local first shared memory layer across MCP clients, explicitly markets context handoff across tools | profile memory, who you are. Developer install. Funded company |
| mcp-memory-keeper | built for Claude Code context window loss, persists decisions and progress | repo and CLI scoped |
| handoff-mcp (two unrelated projects) | saves tasks, decisions, blockers, file pointers to a local `.handoff/` dir | coding agents only |
| SessionFS | capture, sync, resume sessions across 8 coding tools, team handoff, billing | coding agents only |
| devctx | CLI carrying context across Cursor, Windsurf, Claude Code, Antigravity | repo and branch scoped |
| cognee MCP, Memory Nexus | memory servers with more tools | developer audience |

GitHub topic pages `session-handoff`, `agent-handoff` and `project-context` each hold
dozens more.

Chat app migration is also occupied:

- `midweste/chatgpt-to-claude`, a Chrome extension that migrates conversations, memories
  and custom instructions client side, mapping ChatGPT folders to Claude projects.
- Anthropic ships a native memory import flow at claude.com/import-memory.
- Critically, Claude's import moves preferences and profile facts, explicitly not
  conversation continuity. Every guide says full chat history does not transfer and will
  not shape the new assistant.

## Finding 3, the gap

Everything above is one of two things:

1. profile memory, who I am, my tools, my tone
2. repo scoped developer memory, a dot directory, a git remote, a CLI

Nobody is doing task level continuity for the non developer chat user. The person midway
through a legal analysis, a financial model or a research synthesis, with no repo, no CLI
and no terminal. That is our v1 user.

Positioning line: "OpenMemory remembers who you are. Carryover carries what you were
doing."

## Finding 4, why MCP is out of scope today

- OpenAI requires developer mode for custom MCP connectors as of 25 March 2026, and there
  are no local servers on consumer ChatGPT without a tunnel product.
- Reliability through 2026 is uneven. Reported issues include custom apps vanishing from
  the directory and OAuth completing without the connector appearing in chat.
- A judge cannot install an MCP server during a five minute demo, so an MCP first build
  forfeits the Live Run and Finish the Job points.

MCP is still the right long term surface. It is a roadmap slide, not code.

## Finding 5, sandboxing is correct but invisible

The original idea included running the server in a sandbox for privacy. The instinct is
right on the merits:

- Microsoft's 2026 guidance is to sandbox local MCP servers in containers with only the
  filesystem and network access they need, and block outbound traffic by default.
- In January 2026 a researcher published an exploit chain against Anthropic's own Git MCP
  server achieving remote code execution through prompt injection alone. If the reference
  implementation shipped with that, third party servers deserve suspicion.
- CVE-2025-6514 in `mcp-remote`, CVSS 9.6, was the first real world full remote code
  execution on a client OS from connecting to an untrusted remote MCP server.

But sandboxing is a hardening property and scores zero in a five minute demo because
nobody can see it. The demo equivalent that is visible: we never write the transcript to
the database, only the capsule. Say that, and make sure the code makes it true.

## Finding 6, the manual workaround people already use

The common user workaround found in the wild is to prompt the assistant to summarize the
conversation, then paste the summary and goals into a fresh chat. People describe treating
each chat like a consultant who needs fresh context every time.

That is the behaviour Carryover automates. It is validation, not a threat, and it is worth
saying in the demo because everyone in the room has done it.
