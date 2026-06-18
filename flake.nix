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
    # Linux only for deploy; darwin kept for local `nix flake show`/eval.
    systems = ["x86_64-linux" "aarch64-linux" "aarch64-darwin"];
    forAllSystems = nixpkgs.lib.genAttrs systems;
    pkgsFor = system: nixpkgs.legacyPackages.${system};
  in {
    packages = forAllSystems (system: let
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
    #   imports = [ inputs.jamye-plz.nixosModules.jamye ];
    #   services.jamye = { enable = true; ... };
    nixosModules.jamye = import ./infra/module.nix {inherit self;};
    nixosModules.default = self.nixosModules.jamye;

    formatter = forAllSystems (system: (pkgsFor system).nixpkgs-fmt);
  };
}
