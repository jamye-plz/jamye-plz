# jamye-plz NixOS deploy — locked architecture

Target homelab: github.com/smg1024/homelab (NixOS flake, hosts: yggdrasil/midgard/alfheim).
Deploy jamye-plz to **alfheim** (app host).

## Ingress decision: DELEGATE to yggdrasil (homelab security principle)
- Topology: Cloudflare Tunnel → cloudflared(yggdrasil) → https://localhost:443 (yggdrasil caddy,
  cloudflare DNS ACME TLS) → reverse_proxy http://<apphost>.tail6fc192.ts.net:PORT.
- Principle: "no app port public; firewall stays closed; ingress/monitoring only on yggdrasil;
  apps on app host." alfheim firewall stays closed; reachable only via tailnet.
- All existing services (forgejo→midgard:3000, vault→midgard:8222, home→midgard:8082) follow this.

## jamye-specific routing
- jamye needs static SPA + /api + /api/ws path split = APP-INTERNAL routing (not public ingress).
- Run a thin local caddy on alfheim (site ":8080", auto_https off): /api/* → 127.0.0.1:8000 (uvicorn,
  WS transparent), /* → static SPA Nix store path with try_files index.html.
- Expose ONLY :8080 on tailscale0 interface (networking.firewall.interfaces."tailscale0").
- yggdrasil adds ONE virtualHost reverse_proxy http://alfheim.tail6fc192.ts.net:8080 + ONE cloudflared
  ingress entry + Cloudflare Tunnel CNAME (e.g. jamye.ridewithmin.com).

## Packaging (confirmed forks)
- Backend: uv2nix (pure, reads uv.lock) → venv; uvicorn app.main:app on 127.0.0.1:8000.
- Frontend: bun build → static derivation (FOD bun deps; fill hash on first Linux build).
- Postgres: services.postgresql_18, unix-socket peer auth (user jamye → db jamye),
  DATABASE_URL=postgresql+asyncpg://jamye@/jamye?host=/run/postgresql (no DB password).
- Migrations: jamye-migrate.service oneshot (alembic upgrade head), Before=jamye-backend.
- Runtime: native systemd services on alfheim.

## Secrets: homelab owns them
- jamye-plz nixosModule takes `environmentFile` only (secret-mechanism-agnostic).
- homelab's existing sops-nix renders the env file → pass to services.jamye.environmentFile.
- jamye-plz flake does NOT depend on sops-nix.

## jamye-plz flake shape (consumed as input by homelab flake)
- inputs: nixpkgs, uv2nix, pyproject-nix, pyproject-build-systems.
- outputs: packages.{x86_64-linux,aarch64-linux}.{backend,frontend,backendSrc};
  nixosModules.jamye (references self.packages.${pkgs.system}).
- homelab: add jamye-plz input → hosts/alfheim imports nixosModules.jamye + services.jamye config;
  yggdrasil services/ingress.nix + services/cloudflared.nix get the exposure entries.

## Prod app checklist
- OAuth redirect_uri → https://jamye.ridewithmin.com/api/auth/{kakao,google}/callback (update consoles).
- FRONTEND_ORIGIN=https://jamye.ridewithmin.com (same-origin → CORS trivial).
- JWT cookie Secure in production (APP_ENV=production). Backend sees http (proxied) but browser https.
- MinIO/VAPID deferred to M1 — module options default off.

## IMPL status (files written in jamye-plz repo)
- flake.nix — inputs nixpkgs/uv2nix/pyproject-nix/pyproject-build-systems; outputs packages.{backend,backendSrc,frontend} + nixosModules.jamye.
- infra/backend.nix — uv2nix venv + alembic src (src wrapped in runCommandLocal derivation).
- infra/frontend.nix — bun FOD nodeModules (nodeModulesHash=fakeHash, fill on first Linux build) + static build.
- infra/module.nix — services.jamye options; postgres_18 peer auth; jamye-migrate + jamye-backend systemd; local caddy ":listenPort" auto_https off; NO firewall change (tailscale0 trusted).
- (Nix files live in infra/ alongside docker-compose.yml; flake.nix at repo root imports ./infra/*.nix.)
- flake.lock committed (nixpkgs unstable 2026-06-16, uv2nix/pyproject-nix/build-system-pkgs).
- `nix flake show` on darwin: clean, no warnings. All packages + module evaluate.
- docs/deployment/nixos-alfheim.md — full integration guide + homelab snippets + bootstrap.
- .gitignore — result/result-*/.direnv.
- Domain: jamye-plz.ridewithmin.com (confirmed).
- All 4 nix files parse OK (nix-instantiate --parse). flake eval (nix flake show) on darwin in progress.
- CORRECTION vs earlier note: NO firewall.interfaces.allowedTCPPorts needed; tailscale0 is in
  networking.firewall.trustedInterfaces (modules/tailscale.nix). Public firewall stays closed.
- sops: alfheim NOT yet a recipient in .sops.yaml (only poby/yggdrasil/midgard) → prerequisite:
  ssh-to-age + sops updatekeys before deploy.

## Build caveat
- Authoring host is darwin; Linux-target build (uv2nix venv, bun FOD hash, NixOS activation) must run
  on alfheim or a Linux remote builder. fakeHash bootstrap on first `nix build`.
