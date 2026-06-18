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
{ pkgs, lib }:
let
  # Source minus generated/installed dirs (keeps the FOD hash stable).
  src = lib.cleanSourceWith {
    src = ../frontend;
    filter = path: type:
      let base = baseNameOf (toString path); in
      !(builtins.elem base [ "node_modules" "build" ".svelte-kit" ".vercel" ".vite" ]);
  };

  # ⇣ Replace with the hash printed by the first `nix build .#frontend`.
  nodeModulesHash = lib.fakeHash;

  nodeModules = pkgs.stdenv.mkDerivation {
    pname = "jamye-frontend-node-modules";
    version = "0.1.0";
    inherit src;
    nativeBuildInputs = [ pkgs.bun ];
    dontConfigure = true;
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

  nativeBuildInputs = [ pkgs.bun ];

  configurePhase = ''
    runHook preConfigure
    export HOME="$TMPDIR"
    cp -R ${nodeModules}/node_modules ./node_modules
    chmod -R u+w node_modules
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

  passthru = { inherit nodeModules; };

  meta.description = "jamye-plz SvelteKit SPA (static build)";
}
