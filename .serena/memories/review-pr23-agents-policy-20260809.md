## PR #23 review note

- Thread `PRRT_kwDOS75RC86XnyMX` claims the vendored skill additions under `.agents/skills/` must move to an OMA source/generator path.
- Repository owner explicitly accepted this as a project-specific exception because these design skills are not provided by OMA and are intentionally vendored in the runtime-discoverable skills directory.
- Remaining risk is operational rather than product-functional: future OMA regeneration could overwrite the vendored skill directories.
- Mitigation landed in `docs/README.md`: list the allowed exception and require preserving those directories during OMA upgrades.
