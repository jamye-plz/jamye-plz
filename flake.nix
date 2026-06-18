{
  description = "jamye-plz — closed-group social PWA (backend + frontend + NixOS module)";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    uv2nix,
    pyproject-nix,
    pyproject-build-systems,
    ...
  }: let
    # Build packages only for the deploy architecture. The frontend FOD hash is
    # architecture-specific (bun.lock pulls OS/CPU-gated native optionals), so
    # exposing systems without a hash would break `nix flake {show,check}`. Add
    # a system here only once infra/frontend.nix has a matching hash entry.
    packageSystems = ["aarch64-linux"];
    # Broader set is fine for system-agnostic outputs (formatter).
    allSystems = ["x86_64-linux" "aarch64-linux" "aarch64-darwin"];
    forPackageSystems = nixpkgs.lib.genAttrs packageSystems;
    forAllSystems = nixpkgs.lib.genAttrs allSystems;
    pkgsFor = system: nixpkgs.legacyPackages.${system};
  in {
    packages = forPackageSystems (system: let
      pkgs = pkgsFor system;
      lib = pkgs.lib;
      backend = import ./infra/backend.nix {
        inherit pkgs lib uv2nix pyproject-nix pyproject-build-systems;
      };
      frontend = import ./infra/frontend.nix {inherit pkgs lib;};
    in {
      # Python virtualenv closure (uvicorn + alembic + app). Pure, offline.
      backend = backend.venv;
      # Source tree needed at runtime for Alembic migrations (alembic.ini + alembic/).
      backendSrc = backend.src;
      # Static SvelteKit SPA (adapter-static). Served by Caddy `root`.
      frontend = frontend;
      default = backend.venv;
    });

    # Importable NixOS module — wire into an existing host config:
    #   imports = [ inputs.jamye-plz.nixosModules.default ];
    #   services.jamye-plz = { enable = true; ... };
    nixosModules.jamye-plz = import ./infra/module.nix {inherit self;};
    nixosModules.default = self.nixosModules.jamye-plz;

    formatter = forAllSystems (system: (pkgsFor system).nixpkgs-fmt);
  };
}
