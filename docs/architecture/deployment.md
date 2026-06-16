# 배포

NixOS 홈랩 단일 서버에 하이브리드로 배포한다. 인프라는 NixOS native services로 선언하고, 앱은 podman OCI 컨테이너로 띄운다. 외부 노출은 cloudflared 터널.

> 버전 v1 · 2026-06-16 · SSOT: plan.json

---

## 1. 하이브리드 전략

| 계층 | 구성요소 | 배포 방식 | 이유 |
|------|----------|-----------|------|
| 인프라 | PostgreSQL, MinIO, Caddy, Redis | NixOS native services | nix 모듈이 성숙. 선언적 백업·자동 ACME를 그대로 누림 |
| 앱 | FastAPI, SvelteKit | podman OCI (`virtualisation.oci-containers`, backend=podman) | nix 패키징 시 `uv.lock`/`npmDepsHash` 재해시 마찰이 커 컨테이너로 우회 |

- **인프라를 native로 두는 이유**: `services.postgresql` + `services.postgresqlBackup`로 DB와 정기 덤프를 선언 한 줄로 잡고, `services.caddy`가 ACME 인증서를 자동 발급·갱신한다. 검증된 모듈이라 운영 마찰이 작다.
- **앱을 컨테이너로 두는 이유**: Python/Node 의존성을 nix로 패키징하면 lockfile 해시(`uv.lock`, `npmDepsHash`)를 변경마다 다시 맞춰야 해 개발 흐름이 끊긴다. OCI 이미지로 빌드하면 이 마찰을 피하면서 배포는 여전히 nix 선언으로 관리한다.
- **단일 서버**라 `deploy-rs`/`colmena` 없이 `nixos-rebuild`로 충분하다(over-engineering 회피).

---

## 2. 핵심 nix 설정 스니펫

아래는 모듈별 핵심 골자다. 실제 값(도메인·경로)은 환경에 맞게 채운다.

### PostgreSQL + 백업

```nix
services.postgresql = {
  enable = true;
  ensureDatabases = [ "jamye" ];
  ensureUsers = [{
    name = "jamye";
    ensureDBOwnership = true;
  }];
};

# 선언적 정기 덤프
services.postgresqlBackup = {
  enable = true;
  databases = [ "jamye" ];
  startAt = "*-*-* 03:00:00";
};
```

### MinIO

```nix
services.minio = {
  enable = true;
  # 루트 자격증명은 store 평문 금지 → 파일 경로로 주입
  rootCredentialsFile = config.age.secrets.minio-root.path;
};
```

### Caddy — 자동 ACME + WebSocket 패스스루 + SPA fallback + COOP/COEP

```nix
services.caddy = {
  enable = true;
  virtualHosts."jamye.example.com".extraConfig = ''
    # WASM 멀티스레드(SharedArrayBuffer) 활성화에 필수
    header {
      Cross-Origin-Opener-Policy "same-origin"
      Cross-Origin-Embedder-Policy "require-corp"
    }

    # FastAPI WebSocket 패스스루 (native WS)
    @ws {
      header Connection *Upgrade*
      header Upgrade websocket
    }
    handle /ws {
      reverse_proxy @ws 127.0.0.1:8000
    }

    # REST API
    handle /api/* {
      reverse_proxy 127.0.0.1:8000
    }

    # SvelteKit SPA — 정적 파일, 없으면 index.html로 폴백
    handle {
      root * /var/lib/jamye/frontend
      try_files {path} /index.html
      file_server
    }
  '';
};
```

> COOP/COEP 헤더는 **WASM 멀티스레드(SharedArrayBuffer)** 를 켜기 위해 반드시 필요하다. `Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Embedder-Policy: require-corp`가 있어야 `self.crossOriginIsolated`가 true가 되고 온디바이스 AI의 멀티스레드 추론이 활성화된다. 헤더가 빠지면 멀티스레드 WASM이 비활성화되고 외부 리소스가 차단된다(상세 [`./on-device-ai.md`](./on-device-ai.md)). 외부 리소스 차단을 완화하려면 `credentialless` 모드를 검토한다.

### 앱 컨테이너 (podman OCI)

```nix
virtualisation.oci-containers = {
  backend = "podman";
  containers = {
    jamye-api = {
      image = "jamye-api:latest";
      ports = [ "127.0.0.1:8000:8000" ];
      environmentFiles = [ config.age.secrets.api-env.path ];
    };
    # SvelteKit은 정적 빌드 산출물을 Caddy가 직접 서빙하므로
    # 별도 런타임 컨테이너 없이 빌드 단계만 필요할 수 있다.
  };
};
```

---

## 3. 시크릿 관리

- **도구**: `agenix` (추후 `sops-nix`로 이전 가능).
- **원칙**: nix store에 평문 시크릿을 절대 두지 않는다. 복호화된 시크릿은 `/run` tmpfs에 놓고 **경로로 주입**한다.
  - DB·API 시크릿 → 컨테이너 `environmentFiles`(`EnvironmentFile`)로 경로 주입.
  - MinIO 루트 자격증명 → `services.minio.rootCredentialsFile`로 경로 주입.
- VAPID 키, OAuth 클라이언트 시크릿, JWT 서명 키 등 민감 값이 모두 여기에 해당한다.

---

## 4. 외부 노출과 배포 명령

- **외부 노출**: `cloudflared` 터널. 홈랩 서버를 직접 포트포워딩하지 않고 Cloudflare 터널로 공개한다.
- **배포**:

  ```bash
  nixos-rebuild switch --flake .#jamye --target-host root@<homelab>
  ```

  flake로 호스트 구성을 선언하고 원격 타깃에 적용한다.

---

## 5. flake 구조 스케치

```
.
├── flake.nix
├── nix/
│   ├── hosts/            # 호스트별 NixOS 구성 (단일 서버)
│   ├── modules/          # postgres / minio / caddy / redis / app / secrets
│   └── overlays/         # 패키지 오버레이
├── frontend/             # SvelteKit (adapter-static SPA)
├── backend/              # FastAPI (router→service→repository)
└── packages/             # jamye-frontend(buildNpmPackage), jamye-api 이미지 정의
```

- `nix/modules/`에 인프라 서비스(postgres·minio·caddy·redis)와 앱 컨테이너(app), 시크릿(secrets) 모듈을 분리한다.
- `packages/`에서 프론트 정적 빌드와 API 컨테이너 이미지를 정의한다.

---

## 6. 관련 문서

- 스택·배포 결정 근거(ADR-6) → [`./tech-stack.md`](./tech-stack.md)
- DB 스키마·백업 대상 → [`./data-model.md`](./data-model.md)
- 온디바이스 AI·COOP/COEP 요구 → [`./on-device-ai.md`](./on-device-ai.md)
- 태스크(T15 배포) → [`../planning/tasks.md`](../planning/tasks.md)
