# Importable NixOS module for the jamye-plz stack.
#
# Designed for a homelab where a separate ingress node (e.g. yggdrasil) owns the
# public Cloudflare Tunnel + Caddy(TLS). This module therefore runs NO public
# TLS/ACME and opens NO public ports. It exposes a single plain-HTTP port on the
# host, reachable over the tailnet (tailscale0 is a trusted firewall interface),
# which the ingress node reverse-proxies to.
#
#   imports = [ inputs.jamye-plz.nixosModules.default ];
#   services.jamye-plz = {
#     enable = true;
#     listenPort = 8080;                       # ingress → http://<host>.tailnet:8080
#     environmentFile = config.sops.templates."jamye.env".path;  # secrets
#   };
{ self }:
{ config, lib, pkgs, ... }:
let
  cfg = config.services.jamye-plz;
  pkg = self.packages.${pkgs.system};

  # No-password connection: Unix-socket peer auth (OS user → DB role of same name).
  defaultDatabaseUrl =
    "postgresql+asyncpg://${cfg.database.user}@/${cfg.database.name}?host=/run/postgresql";

  # APP_ENV and DATABASE_URL are exported inside the ExecStart wrappers rather
  # than via Environment=, because systemd's EnvironmentFile= overrides
  # Environment=. A supplied env file (e.g. copied from .env.example) carrying
  # APP_ENV=development or a TCP/password DATABASE_URL would otherwise silently
  # disable the production guards or bypass the peer-auth socket DSN. Exporting
  # after the env file is loaded, right before exec, makes them authoritative.
  # (DATABASE_URL is configured via services.jamye-plz.databaseUrl, NOT the
  # secrets file; the default peer-auth DSN carries no password.)
  exports = ''
    export APP_ENV=production
    export DATABASE_URL=${lib.escapeShellArg cfg.databaseUrl}
  '';
  startBackend = pkgs.writeShellScript "jamye-plz-backend-start" ''
    ${exports}
    exec ${pkg.backend}/bin/uvicorn app.main:app --host 127.0.0.1 --port ${toString cfg.backendPort}
  '';
  startMigrate = pkgs.writeShellScript "jamye-plz-migrate-start" ''
    ${exports}
    exec ${pkg.backend}/bin/alembic upgrade head
  '';
in
{
  options.services.jamye-plz = {
    enable = lib.mkEnableOption "the jamye-plz application stack";

    listenPort = lib.mkOption {
      type = lib.types.port;
      default = 8080;
      description = "Plain-HTTP port the local Caddy listens on (proxied by the ingress node over tailnet).";
    };

    backendPort = lib.mkOption {
      type = lib.types.port;
      default = 8000;
      description = "Loopback port for the uvicorn backend.";
    };

    stateDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/jamye-plz";
      description = "Writable state directory for the backend service.";
    };

    user = lib.mkOption {
      type = lib.types.str;
      default = "jamye";
      description = "System user the backend and migrations run as (also the DB role for peer auth).";
    };

    environmentFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      example = ''config.sops.templates."jamye.env".path'';
      description = ''
        Path to an env file with secrets and per-deploy config (JWT_SECRET,
        KAKAO_*, GOOGLE_*, FRONTEND_ORIGIN, *_REDIRECT_URI, ...). Typically
        rendered by sops-nix on the host. NOT placed in the Nix store.
      '';
    };

    databaseUrl = lib.mkOption {
      type = lib.types.str;
      default = defaultDatabaseUrl;
      description = "SQLAlchemy async DSN. Default uses a passwordless Unix-socket peer connection.";
    };

    database = {
      createLocally = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Provision a local PostgreSQL with the database and (peer-auth) role.";
      };
      name = lib.mkOption {
        type = lib.types.str;
        default = "jamye";
      };
      user = lib.mkOption {
        type = lib.types.str;
        default = "jamye";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    # ── Safety assertions ───────────────────────────────────────────────────
    assertions = [
      {
        # The service always runs APP_ENV=production; without secrets the
        # backend falls back to the public dev JWT secret and empty OAuth keys
        # (→ forgeable tokens + stub logins). Require an env file.
        assertion = cfg.environmentFile != null;
        message = "services.jamye-plz.environmentFile must be set: production needs a real JWT_SECRET and OAuth keys, otherwise the backend uses insecure dev defaults.";
      }
      {
        # Default DSN is passwordless Unix-socket peer auth, so the OS user the
        # units run as (cfg.user) must equal the DB role (cfg.database.user).
        assertion =
          !(cfg.database.createLocally && cfg.databaseUrl == defaultDatabaseUrl)
          || cfg.database.user == cfg.user;
        message = "services.jamye-plz: with the default peer-auth DSN, database.user must equal user (the units run as `user` but connect as `database.user`).";
      }
    ];

    # ── Service user ────────────────────────────────────────────────────────
    users.users.${cfg.user} = {
      isSystemUser = true;
      group = cfg.user;
      home = cfg.stateDir;
    };
    users.groups.${cfg.user} = { };

    # State directory. Derived from the option (StateDirectory= is hard-coded to
    # /var/lib/<name>, so it would not follow an overridden stateDir).
    systemd.tmpfiles.rules = [
      "d ${cfg.stateDir} 0750 ${cfg.user} ${cfg.user} -"
    ];

    # ── PostgreSQL (local, peer auth) ───────────────────────────────────────
    services.postgresql = lib.mkIf cfg.database.createLocally {
      enable = true;
      package = pkgs.postgresql_18;
      ensureDatabases = [ cfg.database.name ];
      ensureUsers = [
        {
          name = cfg.database.user;
          ensureDBOwnership = true;
        }
      ];
    };

    # ── Migrations (alembic upgrade head), before the backend starts ────────
    systemd.services.jamye-plz-migrate = {
      description = "jamye-plz database migrations (alembic upgrade head)";
      after = [ "network.target" ] ++ lib.optional cfg.database.createLocally "postgresql.service";
      requires = lib.optional cfg.database.createLocally "postgresql.service";
      before = [ "jamye-plz-backend.service" ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        Group = cfg.user;
        WorkingDirectory = pkg.backendSrc;
        EnvironmentFile = lib.optional (cfg.environmentFile != null) cfg.environmentFile;
        ExecStart = startMigrate;
      };
    };

    # ── Backend (uvicorn) ───────────────────────────────────────────────────
    systemd.services.jamye-plz-backend = {
      description = "jamye-plz FastAPI backend (uvicorn)";
      after = [ "network.target" "jamye-plz-migrate.service" ]
        ++ lib.optional cfg.database.createLocally "postgresql.service";
      requires = [ "jamye-plz-migrate.service" ]
        ++ lib.optional cfg.database.createLocally "postgresql.service";
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        User = cfg.user;
        Group = cfg.user;
        WorkingDirectory = cfg.stateDir;
        EnvironmentFile = lib.optional (cfg.environmentFile != null) cfg.environmentFile;
        ExecStart = startBackend;
        Restart = "on-failure";
        RestartSec = 2;
        # Hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ReadWritePaths = [ cfg.stateDir ];
      };
    };

    # ── Local Caddy: SPA + /api split on one tailnet HTTP port ──────────────
    # Site address ":PORT" (no hostname) ⇒ plain HTTP, Caddy makes no TLS/ACME
    # attempt. Public exposure + TLS live on the ingress node.
    services.caddy = {
      enable = true;
      virtualHosts.":${toString cfg.listenPort}".extraConfig = ''
        encode zstd gzip

        # Cross-origin isolation for on-device AI (multithreaded WASM /
        # SharedArrayBuffer → self.crossOriginIsolated), per
        # docs/architecture/{deployment,on-device-ai}.md. COEP=credentialless
        # (not require-corp) so cross-origin avatar images (Kakao/Google profile
        # photos) keep loading without CORP headers.
        header {
          Cross-Origin-Opener-Policy "same-origin"
          Cross-Origin-Embedder-Policy "credentialless"
        }

        @api path /api/*
        handle @api {
          reverse_proxy 127.0.0.1:${toString cfg.backendPort}
        }

        handle {
          root * ${pkg.frontend}
          try_files {path} /index.html
          file_server
        }
      '';
    };

    # NOTE: no networking.firewall changes. On this homelab tailscale0 is a
    # trusted interface, so the ingress node reaches :listenPort over the
    # tailnet while the public firewall stays closed. If your host does NOT
    # trust tailscale0, add:
    #   networking.firewall.interfaces."tailscale0".allowedTCPPorts = [ cfg.listenPort ];
  };
}
