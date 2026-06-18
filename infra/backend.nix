# Backend packaging via uv2nix.
#
# Reads backend/uv.lock and builds a pure, offline Python virtualenv closure
# containing the app plus uvicorn and alembic. Returns:
#   venv : the virtualenv derivation (${venv}/bin/{uvicorn,alembic} available)
#   src  : the minimal source tree needed at runtime for Alembic migrations
#          (alembic.ini + alembic/ — the app itself is imported from the venv)
{
  pkgs,
  lib,
  uv2nix,
  pyproject-nix,
  pyproject-build-systems,
}: let
  python = pkgs.python312;

  workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ../backend;};

  # Prefer prebuilt wheels (manylinux) — asyncpg, uvloop, cryptography, etc. all
  # ship wheels, so no compilers are pulled in for the common case.
  overlay = workspace.mkPyprojectOverlay {sourcePreference = "wheel";};

  # Per-package build-system fixups for sdist-only deps that build from source
  # but don't declare their build backend in [build-system].requires.
  #
  # http-ece is the only sdist-only dependency (via pywebpush). It builds with
  # legacy setuptools but never declares it, so the isolated build fails with
  # "ModuleNotFoundError: No module named 'setuptools'". Inject setuptools+wheel.
  pyprojectOverrides = final: _prev: {
    http-ece = _prev.http-ece.overrideAttrs (old: {
      nativeBuildInputs =
        (old.nativeBuildInputs or [])
        ++ final.resolveBuildSystem {
          setuptools = [];
          wheel = [];
        };
    });
  };

  pythonSet =
    (pkgs.callPackage pyproject-nix.build.packages {inherit python;}).overrideScope
    (lib.composeManyExtensions [
      pyproject-build-systems.overlays.default
      overlay
      pyprojectOverrides
    ]);

  venv = pythonSet.mkVirtualEnv "jamye-backend-env" workspace.deps.default;

  # Alembic needs alembic.ini + the alembic/ migration tree on disk at runtime.
  # The `app` package (incl. app.models referenced by env.py) is resolved from
  # the venv's site-packages, so it is intentionally NOT copied here.
  # Wrapped in a derivation (not a bare source path) so it is a proper package.
  src = pkgs.runCommandLocal "jamye-backend-src" {} ''
    mkdir -p "$out"
    cp -R ${../backend/alembic} "$out/alembic"
    cp ${../backend/alembic.ini} "$out/alembic.ini"
  '';
in {
  inherit venv src;
}
