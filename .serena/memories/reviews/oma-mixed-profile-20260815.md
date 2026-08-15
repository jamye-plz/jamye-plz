# OMA update/link mixed-profile review — 2026-08-15

Verdict: FAIL

Scope: read-only inspection of OMA CLI/content versions, model resolver, Claude/Codex native projections, authentication, and MCP link health. No OMA configuration or generated vendor files were modified by this review.

Evidence:
- npm registry latest and installed OMA CLI: 12.2.1.
- Project content bundle: 12.3.0 at .agents/skills/_version.json; oma doctor reports it as the project install with no dual-install warning.
- Claude Code 2.1.233 and Codex CLI 0.147.0 match their current npm latest versions and both are authenticated.
- .agents/oma-config.yaml selects model_preset: mixed and vendors claude/codex.
- oma doctor --profile resolves mixed to Claude Sonnet 4.6 / Opus 4.7 and OpenAI GPT-5.5 / GPT-5.4-mini, not Sonnet 5 / Opus 5 and GPT-5.6 Terra / Sol.
- oma model:check reports Claude 5 and GPT-5.6 models as live-new relative to the bundled registry; the built-in registry/preset is stale.
- Codex native projection uses gpt-5.6-terra high for most agents and gpt-5.6-luna max for docs/research; no gpt-5.6-sol appears.
- Claude native projection uses the generic sonnet alias for all agents; no opus override appears.
- Codex MCP is present in .codex/config.toml. Claude project MCP is present in .mcp.json, but oma doctor reports Claude MCP not configured because the project has not enabled any mcp.json servers.
- oma doctor overall: ok=false, 12 issues; relevant issues include Claude MCP not configured and invalid hook order due to absent AgentMemory. Other warnings include 135 AgentMemory retry records, Git recommendations, and optional Serena reaper advice.

Findings:
- HIGH — .agents/config/defaults.yaml:59-72: built-in mixed resolver uses stale models, blocking the requested latest-model policy. Remediation: define registered custom model slugs plus explicit agents/custom preset in the user-owned oma-config, or wait for an upstream preset/registry update; do not edit defaults.yaml.
- HIGH — .agents/agents/variants/codex.json:5-67 and .agents/agents/variants/claude.json:5: native same-vendor agents diverge from the requested general/advanced split. Codex has Terra/Luna but no Sol; Claude has Sonnet only and no Opus. Remediation: update through the supported OMA source/config mechanism and rerun oma link; do not hand-edit generated .codex/.claude files.
- MEDIUM — .mcp.json:16-25 plus Claude project state: Serena config was generated but is not enabled in Claude, so oma doctor does not consider Claude MCP configured. Remediation: open Claude Code in the trusted project and approve/enable project MCP servers, then rerun oma doctor.
- MEDIUM — .agents/oma-config.yaml:222-224: eval points to claude-sonnet-5 while model:check treats that slug as new/unbundled and there is no models block. Remediation: register the slug in models before relying on resolver-based eval dispatch.
- LOW — .agents/oma-config.yaml:149,217-224: mixed selection, vendor list, and both vendor authentications are correct.

Security: no embedded secrets found in reviewed OMA config; telemetry remains disabled.
Performance/accessibility: not applicable to this configuration-only review.
