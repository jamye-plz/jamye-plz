# Frontend packaging: build the SvelteKit SPA (adapter-static) with bun into a
# plain directory of static assets, served by Caddy `root`.
#
# Two derivations:
#   nodeModules : fixed-output (FOD) bun install — the ONLY network step.
#   <result>    : offline `bun run build` → $out = the static site (build/).
#
# BOOTSTRAP (one-time, on a Linux builder / alfheim):
#   The FOD hash below is `lib.fakeHash`. Run `nix build .#frontend` once; Nix
#   prints the real `got: sha256-...` — paste it into `nodeModulesHash`.
{
  pkgs,
  lib,
}: let
  # Source minus generated/installed dirs (keeps the FOD hash stable).
  src = lib.cleanSourceWith {
    src = ../frontend;
    filter = path: type: let
      base = baseNameOf (toString path);
    in
      !(builtins.elem base ["node_modules" "build" ".svelte-kit" ".vercel" ".vite"]);
  };

  # bun-install FOD hash, keyed by target system. bun.lock pulls OS/CPU-gated
  # native optionals (@rollup/rollup-linux-*-gnu, @tailwindcss/oxide-linux-*-gnu),
  # so the node_modules tree — and thus this hash — is architecture-dependent.
  # Add an entry after building on a new arch (set to lib.fakeHash, build, paste
  # the `got:`). Unlisted systems fail fast with a clear message.
  nodeModulesHashes = {
    aarch64-linux = "sha256-7tbiTwIGASAwxgIiRRir5jD/5/O7cJHRSmpVI6WBZso=";
  };
  nodeModulesHash =
    nodeModulesHashes.${pkgs.system}
      or (throw "jamye-frontend: no node_modules hash for '${pkgs.system}'. Build it (lib.fakeHash → nix build .#frontend) and add the got: hash to nodeModulesHashes in infra/frontend.nix.");

  nodeModules = pkgs.stdenv.mkDerivation {
    pname = "jamye-frontend-node-modules";
    version = "0.1.0";
    inherit src;
    nativeBuildInputs = [pkgs.bun];
    dontConfigure = true;
    # A FOD output must not reference store paths. stdenv's fixupPhase would
    # run patchShebangs (rewriting node_modules script shebangs to the store's
    # bash) and strip — both inject store refs. Vendored node_modules needs
    # neither, so skip fixup entirely.
    dontFixup = true;
    buildPhase = ''
      runHook preBuild
      export HOME="$TMPDIR"
      bun install --frozen-lockfile --no-progress --ignore-scripts
      runHook postBuild
    '';
    installPhase = ''
      runHook preInstall
      mkdir -p "$out"
      cp -R node_modules "$out/node_modules"
      runHook postInstall
    '';
    # Fixed-output: bun install is the one impure (network) step.
    outputHashMode = "recursive";
    outputHashAlgo = "sha256";
    outputHash = nodeModulesHash;
  };
in
  pkgs.stdenv.mkDerivation {
    pname = "jamye-frontend";
    version = "0.1.0";
    inherit src;

    nativeBuildInputs = [pkgs.bun pkgs.nodejs pkgs.autoPatchelfHook];
    buildInputs = [pkgs.stdenv.cc.cc.lib];

    # We patch node_modules binaries manually below; the output ($out) is only
    # static assets, so skip the automatic post-build pass.
    dontAutoPatchelf = true;
    # node_modules may carry binaries that reference libs we don't provide; warn
    # instead of failing the build (the real toolchain bins get patched fine).
    autoPatchelfIgnoreMissingDeps = true;

    configurePhase = ''
      runHook preConfigure
      export HOME="$TMPDIR"
      cp -R ${nodeModules}/node_modules ./node_modules
      chmod -R u+w node_modules
      # The FOD deliberately left shebangs (#!/usr/bin/env node) and prebuilt
      # ELF binaries (esbuild, @rollup/*-gnu) untouched to stay reference-free.
      # This derivation is NOT fixed-output, so make them runnable here.
      patchShebangs node_modules
      autoPatchelf node_modules
      runHook postConfigure
    '';

    buildPhase = ''
      runHook preBuild
      bun run build
      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall
      mkdir -p "$out"
      cp -R build/. "$out/"
      runHook postInstall
    '';

    passthru = {inherit nodeModules;};

    meta.description = "jamye-plz SvelteKit SPA (static build)";
  }
