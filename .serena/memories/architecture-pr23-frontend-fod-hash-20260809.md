# PR #23 frontend FOD hash decision

- Mode: Recommendation (concrete, low-risk binary decision).
- PR base/head: `e57e959e009b4d70320057a31b80fc47a0405061` → `3bc46fc34c758d4fb35a09bed03d70bc5be71c36`.
- `frontend/package.json` changes only by adding the `test` script (`bun test`).
- The complete dependency and devDependency maps are identical.
- `frontend/bun.lock` has the same blob ID at both refs: `a24392097baea66b2c2d2c99101a3c97b80e1acd`.
- `infra/frontend.nix` is unchanged; its blob ID is `fc614d593b570d37c516a21f7f1326eeea052083` at both refs.
- Decision: keep the current `aarch64-linux` nodeModules output hash. The FOD hash covers the recursive `$out/node_modules` content, not arbitrary `package.json` text. A root test script does not affect `bun install --frozen-lockfile --ignore-scripts` output.
- Recalculate only if the lockfile, dependency maps, Bun version, architecture, install flags, or FOD output changes.
- Durable artifact: `.agents/results/architecture/architecture-recommendation-pr23-frontend-fod-hash.md`.
