# Competitive & Community Feedback Refresh (Delta vs 2026-05-31)
# 2026-06-01

**Purpose:** The 2026-05-31 survey (`agent-market-ux-survey-2026-05-31.md`) is
thorough and remains the baseline. This is a short **delta** pass — one day later —
to (a) honor the standing instruction to re-run competitive research before release
claims, and (b) capture *new, specific* signal that sharpens the code-grounded
findings in `daily-driver-code-grounded-ux-findings-2026-06-01.md`. It is not a
re-survey; read the baseline first.

**Method:** Fresh web search (June 2026), read-only. Sources linked inline. Claims
are attributed; inferences are marked `[inference]`.

---

## Delta D-1 — Cost/token display has moved from "nice to have" to a primary axis

The baseline ranked cost transparency #2 and #10 on the wishlist. New signal shows it
is now a category where dedicated tools compete on *accuracy and granularity*, not
mere presence:

- **DeepSeek-TUI** ships a live cost tracker showing **per-turn and session-level**
  token usage with a **cache hit/miss breakdown** — because cached input is 1/10th
  the price, cache utilization is itself a surfaced economic signal.
  ([silenceper](https://silenceper.com/en/article/2026-05-08-deepseek-tui-terminal-agent/),
  [Efficient Coder](https://www.xugj520.cn/en/archives/deepseek-tui-terminal-coding-agent-guide.html))
- **`tokscale`** is a standalone CLI whose entire purpose is tracking token usage
  *across* OpenCode, Claude Code, Codex, Gemini, Cursor, Factory Droid, Kimi, etc. —
  evidence that built-in cost display is so untrusted/absent that an aggregator
  market exists. ([tokscale](https://github.com/junhoyeo/tokscale))
- **Codeburn** reads Claude Code / Cursor local session logs to render a live token-
  spend dashboard — same gap, different vendor.
  ([Developers Digest](https://www.developersdigest.tech/blog/codeburn-tui-dashboard-for-claude-code-token-spend))
- **Hermes-Agent #504** debates the right *source* for token counts:
  server-reported (accurate, delayed) vs local tiktoken (immediate, approximate).
  ([GitHub #504](https://github.com/NousResearch/hermes-agent/issues/504))

**Implication for teaagent:** Finding **CG-03** (both surfaces display fabricated /
zero cost) is not a cosmetic bug — it puts teaagent *behind the table stakes* of a
category competitors are actively differentiating on. Because `RunResult` already
carries real `cost_cents` + token counts, teaagent can leap from "fabricated" to
"server-reported with cache awareness" in one focused change, and should label the
source (the Hermes debate) so the number is trusted.

---

## Delta D-2 — REPL rendering fragility is a named reason developers switch TUIs

- Claude Code's REPL is criticized because *"resizing your window mid-response can
  break the rendering, and scrolling back far enough creates messy display issues."*
  ([Nimbalyst](https://nimbalyst.com/blog/claude-code-vs-codex-vs-opencode-definitive-comparison/))
- Reviewers cite OpenCode's **OpenTUI** (TypeScript layer + native Zig renderer) as
  "better for extended sessions compared to Claude Code's REPL approach."
  ([Thomas Wiegold](https://thomas-wiegold.com/blog/i-switched-from-claude-code-to-opencode/),
  [Nimbalyst](https://nimbalyst.com/blog/claude-code-vs-codex-vs-opencode-definitive-comparison/))

**Implication for teaagent:** Finding **CG-06** (TUI clears the screen every prompt
for terminals ≥120×30) is the *same failure class reviewers already punish*, except
teaagent auto-enables it for large terminals — the exact configuration power users
run. This is a switching-trigger, not a polish item. `[inference]` A real
prompt_toolkit fixed-region layout would turn a liability into the "good for extended
sessions" property reviewers reward.

---

## Delta D-3 — Defection narratives are fast and multi-surface

- DeepSeek-TUI gained **+580 GitHub stars in 24h** (May 1, 2026), riding an
  "I switched from Claude" narrative that hit AI YouTube, X, and GitHub the same
  morning. ([AgentConn](https://agentconn.com/agents/deepseek-tui/),
  [GitHub](https://github.com/DeepSeekTUI/DeepSeek-TUI))
- "OpenCode vs Codex vs Claude Code" is now *the* comparison developers face; all
  three are considered mature.
  ([builder.io](https://www.builder.io/blog/opencode-vs-claude-code))

**Implication for teaagent:** First-impression correctness matters
disproportionately. A new user who runs `teaagent chat` and sees CG-01 ("every task
failed, no answer shown") forms the switching judgment in the first 60 seconds. The
baseline survey's onboarding theme (**UX-F5**, "visible value in the first 5
minutes") is gated entirely on CG-01 being fixed.

---

## What did NOT change since 2026-05-31

- Governance-first positioning remains the durable differentiator (NIST agent-
  identity standardization, Gravitee enterprise security data). No new evidence
  contradicts the baseline here.
- No new entrant displaces the Claude Code / Cursor / OpenCode / Codex top tier.
- The verification-bottleneck thesis ("less capability, more reliability") holds.

---

## Sources

- [Hermes-Agent issue #504 — Enhanced CLI TUI token tracking](https://github.com/NousResearch/hermes-agent/issues/504)
- [DeepSeek-TUI terminal agent (silenceper)](https://silenceper.com/en/article/2026-05-08-deepseek-tui-terminal-agent/)
- [DeepSeek-TUI review (AgentConn)](https://agentconn.com/agents/deepseek-tui/)
- [DeepSeek-TUI (GitHub)](https://github.com/DeepSeekTUI/DeepSeek-TUI)
- [DeepSeek-TUI 2026 guide (Efficient Coder)](https://www.xugj520.cn/en/archives/deepseek-tui-terminal-coding-agent-guide.html)
- [Codeburn token-spend dashboard (Developers Digest)](https://www.developersdigest.tech/blog/codeburn-tui-dashboard-for-claude-code-token-spend)
- [tokscale (GitHub)](https://github.com/junhoyeo/tokscale)
- [OpenCode vs Codex vs Claude Code (Nimbalyst)](https://nimbalyst.com/blog/claude-code-vs-codex-vs-opencode-definitive-comparison/)
- [I switched from Claude Code to OpenCode (Thomas Wiegold)](https://thomas-wiegold.com/blog/i-switched-from-claude-code-to-opencode/)
- [OpenCode vs Claude Code (builder.io)](https://www.builder.io/blog/opencode-vs-claude-code)
</content>
