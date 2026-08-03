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
#     storage.publicUrl = "https://minio.example.com";           # ingress → :9000
#     storage.rootCredentialsFile = config.sops.secrets."jamye-plz/minio_root".path;
#   };
#
# The module provisions the full stack: PostgreSQL (peer auth), MinIO (media
# objects, private bucket), alembic migrations, the uvicorn backend and a local
# Caddy serving the SPA. The ingress node publishes two hostnames — the app on
# listenPort and the S3 endpoint on storage.port (a separate subdomain, since
# presigned URLs are SigV4-signed over the host+path and cannot be re-rooted
# under a path prefix).
{ self }:
{ config, lib, pkgs, ... }:
let
  cfg = config.services.jamye-plz;
  pkg = self.packages.${pkgs.system};

  # No-password connection: Unix-socket peer auth (OS user → DB role of same name).
  defaultDatabaseUrl =
    "postgresql+asyncpg://${cfg.database.user}@/${cfg.database.name}?host=/run/postgresql";

  # APP_ENV (and the non-secret default DATABASE_URL) are exported inside the
  # ExecStart wrappers rather than via Environment=, because systemd's
  # EnvironmentFile= overrides Environment=. A supplied env file (e.g. copied
  # from .env.example) carrying APP_ENV=development or a TCP/password
  # DATABASE_URL would otherwise silently disable the production guards or
  # bypass the peer-auth socket DSN. Exporting after the env file is loaded,
  # right before exec, makes them authoritative.
  #
  # DATABASE_URL is exported here ONLY when databaseUrl != null (the default
  # peer-auth DSN, which has no password). For an external DB whose DSN carries
  # credentials, set databaseUrl = null and put DATABASE_URL in environmentFile
  # so the secret never enters the world-readable Nix store / binary caches.
  # MINIO_ENDPOINT/MINIO_BUCKET are non-secret deploy config, so they are
  # exported here like DATABASE_URL. The credentials (MINIO_ACCESS_KEY/
  # MINIO_SECRET_KEY) are NOT — they stay in environmentFile so they never
  # enter the world-readable Nix store.
  exports =
    "export APP_ENV=production\n"
    + lib.optionalString (cfg.databaseUrl != null)
      "export DATABASE_URL=${lib.escapeShellArg cfg.databaseUrl}\n"
    + lib.optionalString (cfg.storage.publicUrl != null)
      "export MINIO_ENDPOINT=${lib.escapeShellArg cfg.storage.publicUrl}\n"
    + "export MINIO_BUCKET=${lib.escapeShellArg cfg.storage.bucket}\n";
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
      type = lib.types.nullOr lib.types.str;
      default = defaultDatabaseUrl;
      description = ''
        Non-secret SQLAlchemy async DSN, exported into the unit's environment.
        Default is a passwordless Unix-socket peer connection. For an external
        database whose DSN carries credentials, set this to null and provide
        DATABASE_URL via environmentFile instead, so the password never enters
        the world-readable Nix store.
      '';
    };

    database = {
      createLocally = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Provision a local PostgreSQL with the database and (peer-auth) role.";
      };
      package = lib.mkOption {
        type = lib.types.package;
        default = pkgs.postgresql_18;
        defaultText = lib.literalExpression "pkgs.postgresql_18";
        description = ''
          PostgreSQL package for the local cluster. Applied with mkDefault, so a
          host that already pins services.postgresql.package keeps its version
          (the host runs a single cluster) — override here only on a dedicated host.
        '';
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

    storage = {
      createLocally = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Provision a local MinIO for media objects (topic images). The S3 API
          listens on `port` so the ingress node can publish it under
          `publicUrl` over the tailnet; the console stays on loopback.
        '';
      };
      port = lib.mkOption {
        type = lib.types.port;
        default = 9000;
        description = "Plain-HTTP S3 API port, reverse-proxied by the ingress node (tailnet only).";
      };
      consolePort = lib.mkOption {
        type = lib.types.port;
        default = 9001;
        description = "MinIO web console port. Bound to loopback — never published by the ingress node.";
      };
      rootCredentialsFile = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        example = ''config.sops.secrets."jamye-plz/minio_root".path'';
        description = ''
          EnvironmentFile (systemd format) with MINIO_ROOT_USER and
          MINIO_ROOT_PASSWORD for the local MinIO. Required when
          `createLocally` is true — MinIO would otherwise boot with the
          well-known minioadmin/minioadmin defaults.
        '';
      };
      publicUrl = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "https://minio.example.com";
        description = ''
          Browser-reachable base URL of the S3 endpoint, exported as
          MINIO_ENDPOINT. It is embedded verbatim in every presigned URL, so it
          must be the public ingress address (https) — not a loopback or
          container-internal host. Leave null to supply MINIO_ENDPOINT through
          environmentFile instead.
        '';
      };
      bucket = lib.mkOption {
        type = lib.types.str;
        default = "jamye";
        description = "Bucket holding media objects. Created on first start when `createLocally` is true.";
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
      {
        # databaseUrl is exported into the Nix store, so it must not embed a
        # password (userinfo `user:pass@`). Credentialed DSNs belong in
        # environmentFile (set databaseUrl = null).
        assertion =
          cfg.databaseUrl == null
          || builtins.match ".*://[^/@]*:[^/@]*@.*" cfg.databaseUrl == null;
        message = "services.jamye-plz.databaseUrl must not contain a password (it is written to the world-readable Nix store). Set databaseUrl = null and pass a credentialed DATABASE_URL via environmentFile.";
      }
      {
        # A local peer-auth DB needs the socket DSN exported; null would leave
        # the backend with no DATABASE_URL (or a stale config default).
        assertion = !cfg.database.createLocally || cfg.databaseUrl != null;
        message = "services.jamye-plz: database.createLocally needs databaseUrl set (the peer-auth socket DSN). Leave it at the default, or set createLocally = false for an external DB via environmentFile.";
      }
      {
        # With no local cluster, the default Unix-socket DSN points at a socket
        # that is never created. Require an explicit external DSN, or null so
        # DATABASE_URL comes from environmentFile.
        assertion = cfg.database.createLocally || cfg.databaseUrl != defaultDatabaseUrl;
        message = "services.jamye-plz: with database.createLocally = false, set databaseUrl to the external DSN (or null + DATABASE_URL via environmentFile); the default Unix-socket DSN targets a local cluster that is not provisioned.";
      }
      {
        # Without a credentials file MinIO boots with the documented
        # minioadmin/minioadmin defaults — on a host whose S3 port is reachable
        # from the ingress node that is an open object store.
        assertion = !cfg.storage.createLocally || cfg.storage.rootCredentialsFile != null;
        message = "services.jamye-plz.storage.rootCredentialsFile must be set when storage.createLocally = true: MinIO would otherwise start with the default minioadmin credentials.";
      }
      {
        # The backend runs APP_ENV=production, where core/config.py rejects a
        # non-https or localhost MINIO_ENDPOINT (it is embedded in presigned
        # URLs handed to browsers). Fail at build time instead of at startup.
        assertion =
          cfg.storage.publicUrl == null
          || (lib.hasPrefix "https://" cfg.storage.publicUrl
          && builtins.match ".*(localhost|127\\.0\\.0\\.1).*" cfg.storage.publicUrl == null);
        message = "services.jamye-plz.storage.publicUrl must be a browser-reachable https:// URL (not localhost): it is embedded verbatim in presigned URLs, and the backend refuses to start otherwise in production.";
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
      # Priority 900 sits between an explicit host pin (100) and both nixpkgs'
      # and our own mkDefault (1000): we still override nixpkgs' stateVersion
      # default (so the cluster stays on cfg.database.package), but a host that
      # already runs services.postgresql for other data and pins its package
      # keeps that pin — its single cluster is not forced to this major version.
      package = lib.mkOverride 900 cfg.database.package;
      ensureDatabases = [ cfg.database.name ];
      ensureUsers = [
        {
          name = cfg.database.user;
          ensureDBOwnership = true;
        }
      ];
    };

    # ── MinIO (local object storage for media) ──────────────────────────────
    # The S3 API binds all interfaces so the ingress node reaches it over the
    # tailnet (same trust model as listenPort); the console is loopback-only so
    # it is never publishable. The bucket itself stays PRIVATE — reads go
    # through short-TTL presigned GETs the backend issues after a membership
    # check (see docs/architecture/api-contract.md).
    services.minio = lib.mkIf cfg.storage.createLocally {
      enable = true;
      listenAddress = ":${toString cfg.storage.port}";
      consoleAddress = "127.0.0.1:${toString cfg.storage.consolePort}";
      rootCredentialsFile = cfg.storage.rootCredentialsFile;
    };

    # Create the media bucket once MinIO is up. The backend also calls
    # ensure_bucket() at startup, but that goes through MINIO_ENDPOINT — the
    # PUBLIC ingress URL — which would hairpin out through Cloudflare and back.
    # Doing it here over loopback keeps first boot self-contained (and the
    # backend's own attempt is warn-only, so it stays harmless).
    systemd.services.jamye-plz-minio-bucket = lib.mkIf cfg.storage.createLocally {
      description = "jamye-plz: ensure the MinIO media bucket exists";
      after = [ "minio.service" ];
      requires = [ "minio.service" ];
      before = [ "jamye-plz-backend.service" ];
      wantedBy = [ "multi-user.target" ];
      path = [ pkgs.curl pkgs.minio-client ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        # MINIO_ROOT_USER / MINIO_ROOT_PASSWORD for the mc alias below.
        EnvironmentFile = cfg.storage.rootCredentialsFile;
        DynamicUser = true;
        # mc writes a config file that embeds the root credentials. Keep it in
        # tmpfs for the lifetime of the unit rather than a StateDirectory: with
        # DynamicUser the latter is created under /var/lib/private (root-owned,
        # 0700) and reached through a symlink, which the dynamic UID cannot
        # reliably traverse — and it would leave credentials on disk between
        # runs for no benefit, since the alias is re-created every start.
        RuntimeDirectory = "jamye-plz-mc";
        RuntimeDirectoryMode = "0700";
        Environment = "MC_CONFIG_DIR=/run/jamye-plz-mc";
        # Slightly above the in-script deadline so systemd reports the script's
        # own diagnostics instead of killing it mid-retry.
        TimeoutStartSec = "150s";
      };
      script = ''
        set -euo pipefail

        endpoint="http://127.0.0.1:${toString cfg.storage.port}"
        bucket=${lib.escapeShellArg cfg.storage.bucket}
        deadline=$((SECONDS + 120))
        attempts=0
        last_error=""

        # One complete provisioning pass. Every step is retried as a unit:
        # minio.service is Type=simple, so it goes active before the S3 port
        # accepts connections, and a successful alias followed by a transient
        # `mb` failure must not leave the bucket unverified.
        # `|| return 1` on every step is load-bearing: bash disables errexit
        # inside a function invoked from a condition context (the `if` below),
        # so `set -e` alone would let a failed health check fall through to the
        # next command and report success.
        provision() {
          curl -fsS --max-time 5 "$endpoint/minio/health/ready" >/dev/null || return 1
          mc --quiet alias set local "$endpoint" \
            "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null || return 1
          mc --quiet mb --ignore-existing "local/$bucket" >/dev/null || return 1
          mc --quiet stat "local/$bucket" >/dev/null || return 1
        }

        while [ "$SECONDS" -lt "$deadline" ]; do
          attempts=$((attempts + 1))
          if last_error=$(provision 2>&1); then
            echo "MinIO bucket '$bucket' ready after $attempts attempt(s)."
            exit 0
          fi
          sleep 1
        done

        # Surface the real curl/mc diagnostics: a bare timeout message is what
        # made the previous failure mode unactionable. Neither tool echoes the
        # credentials, and they are passed as arguments, never printed here.
        echo "Timed out provisioning MinIO bucket '$bucket' at $endpoint after $attempts attempt(s)." >&2
        echo "Last error: ''${last_error:-<no output captured>}" >&2
        exit 1
      '';
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
        ++ lib.optional cfg.database.createLocally "postgresql.service"
        ++ lib.optional cfg.storage.createLocally "jamye-plz-minio-bucket.service";
      requires = [ "jamye-plz-migrate.service" ]
        ++ lib.optional cfg.database.createLocally "postgresql.service"
        ++ lib.optional cfg.storage.createLocally "jamye-plz-minio-bucket.service";
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
