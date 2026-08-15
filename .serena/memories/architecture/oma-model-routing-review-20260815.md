# OMA model-routing architecture review — 2026-08-15

Decision: Direct edits to .agents/config/defaults.yaml are not an effective runtime configuration in OMA CLI 12.2.1.

Evidence:
- The edited YAML parses and contains Sonnet 5 / Opus 5 / GPT-5.6 entries.
- oma doctor --profile still returns the compiled mixed preset: Sonnet 4.6, Opus 4.7, GPT-5.5, GPT-5.4-mini.
- Installed CLI resolver uses compiled built-in presets and merges only oma-config.yaml custom_presets/agents/models.
- oma link independently sources native model metadata from .agents/agents/variants.
- Current native Codex agents use Terra/high or Luna/max; Claude agents all use sonnet.
- No active models/custom_presets exist in oma-config.yaml; defaults role maps omit refactor and docs.

Recommendation:
- Use user-owned oma-config.yaml custom models plus a complete custom preset or agents overrides for resolver dispatch.
- Treat native projection parity as a separate OMA generator/variant concern; do not rely on editing generated vendor files.
- Full report: .agents/results/architecture/architecture-review-oma-model-routing.md
