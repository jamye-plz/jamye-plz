# 배포

NixOS 홈랩에 배포한다. 외부 노출은 cloudflared 터널.

> 최초 v1 2026-06-16 (설계) · 갱신 2026-08-05
>
> ## ⚠️ 이 문서는 v1 **설계안**이고, 실제 구현은 두 곳에서 달라졌다
>
> 1. **앱도 nix native로 배포한다 — podman OCI는 채택하지 않았다.** 백엔드는
>    `uv2nix`(uv.lock을 그대로 읽음)로 venv를 만들고, 프론트는 bun FOD로 정적 빌드해
>    Caddy가 서빙한다. 아래 §1·§앱 컨테이너 절의 podman 서술은 **채택되지 않은 설계**다.
> 2. **인그레스는 단일 서버가 아니라 2노드다.** Cloudflare Tunnel → yggdrasil(Caddy, TLS 종단)
>    → tailnet → alfheim(앱). 아래 다이어그램의 단일 호스트 전제와 다르다.
>
> **실제로 돌아가는 구성과 절차는 [`../deployment/nixos-alfheim.md`](../deployment/nixos-alfheim.md)를
> 보라.** 이 문서는 당시 판단 근거를 남기기 위해 보존한다.
>
> 또한 **Redis는 아직 배포돼 있지 않다** — M4a(음성 STT)에서 arq와 함께 들어온다.

---

## 1. 하이브리드 전략

| 계층 | 구성요소 | 배포 방식 | 이유 |
|------|----------|-----------|------|
| 인프라 | PostgreSQL, MinIO, Caddy, Redis | NixOS native services | nix 모듈이 성숙. 선언적 백업·자동 ACME를 그대로 누림 |
| 앱 | FastAPI, SvelteKit | ~~podman OCI~~ → **실제로는 nix native** (uv2nix venv + 정적 SPA) | 아래 "앱을 컨테이너로 두는 이유"는 결국 기각됐다 — 하단 주석 참조 |

- **인프라를 native로 두는 이유**: `services.postgresql` + `services.postgresqlBackup`로 DB와 정기 덤프를 선언 한 줄로 잡고, `services.caddy`가 ACME 인증서를 자동 발급·갱신한다. 검증된 모듈이라 운영 마찰이 작다.
- ~~**앱을 컨테이너로 두는 이유**: Python/Node 의존성을 nix로 패키징하면 lockfile 해시를 변경마다 다시 맞춰야 해 개발 흐름이 끊긴다.~~
  **→ 실제로는 그 마찰이 예상보다 작았다.** `uv2nix`는 `uv.lock`을 그대로 읽어 백엔드 쪽 재해시가
  아예 없고, 프론트만 **bun.lock이 바뀔 때 FOD 해시를 Linux 빌더에서 재생성**하면 된다
  (`infra/frontend.nix`). 그 대가로 podman 레이어가 통째로 사라졌다.
  `infra/docker-compose.yml`은 **로컬 개발용**으로만 남아 있다.
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

    # 백엔드(REST + WebSocket): /api/* 전부 FastAPI로 프록시.
    # reverse_proxy가 WebSocket 업그레이드를 자동 처리하므로 /api/ws도 이 한 블록으로 통과한다.
    # API 계약의 모든 경로가 /api prefix를 쓰므로(see ./api-contract.md), 이 매처와 정확히 일치한다.
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

### 앱 컨테이너 (podman OCI) — ⚠️ 미채택 설계

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
│   ├── modules/          # postgres / minio / caddy / app / secrets
│   └── overlays/         # 패키지 오버레이
├── frontend/             # SvelteKit (adapter-static SPA)
├── backend/              # FastAPI (router→service→repository)
└── packages/             # jamye-frontend(buildNpmPackage), jamye-api 이미지 정의
```

> ⚠️ **실제 레포 구조는 다르다.** `nix/`·`packages/`는 없고 `flake.nix` + `infra/{backend,frontend,module}.nix`
> 구성이며, 시크릿은 이 레포가 아니라 homelab의 sops-nix가 소유한다(모듈은 `environmentFile` 경로만 받는다).

---

## 6. 관련 문서

- 스택·배포 결정 근거(ADR-6) → [`./tech-stack.md`](./tech-stack.md)
- DB 스키마·백업 대상 → [`./data-model.md`](./data-model.md)
- 온디바이스 AI·COOP/COEP 요구 → [`./on-device-ai.md`](./on-device-ai.md)
- 태스크(T15 배포) → [`../planning/milestone.md`](../planning/milestone.md)
