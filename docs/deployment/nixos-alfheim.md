# jamye-plz를 alfheim에 배포하기 (NixOS 홈랩)

[smg1024/homelab](https://github.com/smg1024/homelab) NixOS flake의 **alfheim**
호스트에 백엔드·프론트엔드·DB·오브젝트 스토리지(MinIO)를 배포하고, 외부 공개는
**yggdrasil** 인그레스 노드에 위임하는 방법입니다.

> 갱신 2026-08-04 — MinIO·Web Push 배선 반영 (PR #17·#19·#20).

## 아키텍처

```
인터넷 → Cloudflare Edge → Cloudflare Tunnel → cloudflared (yggdrasil)
                                                    │  https://localhost:443
                                            caddy (yggdrasil)  ← 여기서 TLS 종단
                                            (cloudflare DNS-ACME 인증서)
                                                    │  reverse_proxy
                                                    │  http://alfheim.tail6fc192.ts.net:8080
                                        ─── tailnet (WireGuard) ───
                                                    │
                         ┌────────────────────── alfheim ───────────────────────┐
                         │  caddy :8080  (auto_https off, 앱 내부 라우팅)         │
                         │    ├ /api/*  → 127.0.0.1:8000  (uvicorn, WS 포함)      │
                         │    └ /*      → 정적 SPA (Nix store), try_files          │
                         │  jamye-plz-backend.service (uvicorn)                       │
                         │  jamye-plz-migrate.service (alembic upgrade head, oneshot) │
                         │  jamye-plz-minio-bucket.service (버킷 생성, oneshot)        │
                         │  postgresql (로컬, Unix-socket peer 인증)              │
                         │  minio  S3 :9000 (tailnet) · 콘솔 127.0.0.1:9001        │
                         └────────────────────────────────────────────────────────┘

미디어(presigned URL)는 앱과 별도 서브도메인을 탄다 — presigned URL에 호스트가
그대로 박히기 때문에 브라우저가 닿는 주소여야 한다:

  브라우저 → minio.ridewithmin.com → Tunnel → caddy(yggdrasil)
                                      → http://alfheim.tail6fc192.ts.net:9000
```

- **유일한 외부 노출점**: Cloudflare Tunnel. 어떤 호스트도 public 포트를 열지 않습니다.
- **yggdrasil → alfheim** 홉은 tailnet을 탑니다. 이 홈랩에서는 `tailscale0`가
  trusted 방화벽 인터페이스라 **alfheim 방화벽은 손댈 필요가 없습니다** — public
  방화벽은 닫힌 채 유지됩니다.
- **시크릿**은 homelab의 기존 sops-nix가 소유합니다. 이 리포의 모듈은 `environmentFile`
  경로만 받습니다.
- **데이터베이스**는 비밀번호 없는 Unix-socket peer 인증을 사용 — 암호화할 게 없습니다.

이 리포가 제공하는 것: `packages.{backend,frontend,backendSrc}` 와
`nixosModules.jamye-plz`. 아래의 배선(wiring)은 **homelab** 리포에 들어갑니다.

---

## 이 리포가 노출하는 출력 (`flake.nix`)

| 출력 | 용도 |
| --- | --- |
| `packages.<sys>.backend` | uv2nix virtualenv (`bin/uvicorn`, `bin/alembic`) |
| `packages.<sys>.backendSrc` | 마이그레이션용 `alembic.ini` + `alembic/` |
| `packages.<sys>.frontend` | 정적 SvelteKit SPA 빌드 |
| `nixosModules.jamye-plz` | systemd + Caddy + PostgreSQL + **MinIO** 배선 |

> **MinIO도 모듈이 띄웁니다** (PR #19·#20). `storage.createLocally = true`(기본값)면
> `services.minio`가 함께 선언되고, 버킷은 `jamye-plz-minio-bucket.service`가 만듭니다.
> 백엔드·마이그레이션 유닛이 이 oneshot을 `Requires`하므로, 버킷 생성이 실패하면
> 앱은 뜨지 않습니다(fail-closed).

---

## 일회성 부트스트랩

### 1. 프론트엔드 node-modules 해시

`infra/frontend.nix`는 `nodeModulesHash = lib.fakeHash`로 시작합니다. Linux
빌더(또는 alfheim 자체)에서 한 번 실행하세요:

```bash
nix build .#frontend
# → error: hash mismatch ... got: sha256-XXXX...
```

`got:` 해시를 `infra/frontend.nix`의 `nodeModulesHash`에 붙여넣고 커밋한 뒤
`nix build .#frontend`를 다시 실행하면, 이후로는 오프라인·재현가능하게 빌드됩니다.

> 작성 머신은 macOS이므로 Linux 타깃 빌드(uv2nix venv, bun FOD, NixOS 활성화)는
> Linux 호스트에서 실행해야 합니다. alfheim 또는 Linux remote builder를 사용하세요
> (`nixos-rebuild ... --build-host`).

### 2. alfheim을 sops recipient로 추가 (homelab 리포)

`.sops.yaml`에는 현재 `poby`, `yggdrasil`, `midgard`만 있고 **alfheim은 없습니다**.
이 작업 없이는 alfheim이 jamye 시크릿을 복호화할 수 없습니다.

```bash
# alfheim의 SSH host key에서 age recipient 도출
ssh-keyscan -t ed25519 alfheim.tail6fc192.ts.net | ssh-to-age
```

`.sops.yaml`에 추가:

```yaml
keys:
  - &poby age1...
  - &yggdrasil age1...
  - &midgard age1...
  - &alfheim age1...            # ← 신규
creation_rules:
  - path_regex: secrets/[^/]+\.yaml$
    key_groups:
      - age: [ *poby, *yggdrasil, *midgard, *alfheim ]   # ← *alfheim 추가
```

기존 파일을 새 recipient용으로 재암호화:

```bash
sops updatekeys secrets/*.yaml
```

### 3. jamye 시크릿 생성 (homelab 리포)

```bash
sops secrets/jamye-plz.yaml
```

```yaml
jamye-plz:
  jwt_secret: "<openssl rand -hex 32>"
  kakao_client_id: "..."
  kakao_client_secret: ""        # Kakao 콘솔에서 "Client Secret"을 켰을 때만
  google_client_id: "..."
  google_client_secret: "..."

  # MinIO 루트 (services.minio 전용, EnvironmentFile 형식으로 따로 렌더)
  minio_root_user: "<openssl rand -hex 12>"
  minio_root_password: "<openssl rand -hex 24>"
  # 백엔드가 S3에 붙을 때 쓰는 키. 홈랩 단순화 시 루트와 동일 값 재사용 가능하나,
  # 최소권한이 필요하면 콘솔에서 jamye 버킷 전용 service account를 발급해 넣는다.
  minio_access_key: "..."
  minio_secret_key: "..."

  # Web Push (VAPID) — 자체 생성(외부 발급 불필요).
  # 생성 스니펫은 backend/.env.example의 "VAPID (Web Push)" 절을 그대로 사용한다
  # (py_vapid는 pywebpush의 전이 의존성이라 추가 설치 없음). 둘 다 base64url.
  vapid_private_key: "..."
  vapid_public_key: "..."
```

> 두 키가 **모두** 설정돼야 실제 발송이 켜집니다(`vapid_enabled`). 하나라도 비면
> 푸시는 조용한 no-op이 되고 UI는 토글을 숨깁니다 — 데모/개발이 막히지 않도록.

---

## homelab flake에 배선하기

### `flake.nix` (homelab) — 입력 추가

```nix
inputs.jamye-plz.url = "github:jamye-plz/jamye-plz";
# 모듈을 갱신할 때: nix flake update jamye-plz
# nixpkgs는 follows 하지 마세요 — uv2nix가 자체 nixpkgs(unstable)를 pin 합니다.
# (백엔드/프론트는 jamye의 nixpkgs로, systemd/caddy/postgres 옵션은 homelab nixpkgs로 평가됩니다.)
```

`inputs`를 호스트 모듈로 전달하세요(이 flake는 이미 호스트에 `specialArgs`/
`extraSpecialArgs`를 쓰므로 그대로 재사용해 `hosts/alfheim/default.nix` 안에서
`inputs.jamye-plz`가 보이게 합니다).

### `services/jamye-plz.nix` (신규) + `hosts/alfheim`에서 import

add-service 규약대로 호스트에 직접 선언하지 않고 `services/jamye-plz.nix`에 모아
선언한 뒤, alfheim에서 import 합니다. (`inputs`는 `specialArgs`로 모든 모듈에서
보입니다.)

**`services/jamye-plz.nix`** (신규):

```nix
{ config, inputs, ... }:
{
  imports = [ inputs.jamye-plz.nixosModules.default ];

  # 시크릿 → sops-nix가 렌더하는 env 파일
  sops.secrets."jamye-plz/jwt_secret"          = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/kakao_client_id"     = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/kakao_client_secret" = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/google_client_id"    = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/google_client_secret"= { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/minio_root_user"     = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/minio_root_password" = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/minio_access_key"    = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/minio_secret_key"    = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/vapid_private_key"   = { sopsFile = ../secrets/jamye-plz.yaml; };
  sops.secrets."jamye-plz/vapid_public_key"    = { sopsFile = ../secrets/jamye-plz.yaml; };

  # 앱 env — 백엔드가 읽는다.
  sops.templates."jamye-plz.env" = {
    owner = "jamye";                              # 모듈의 services.jamye-plz.user 기본값
    restartUnits = [ "jamye-plz-backend.service" ];
    content = ''
      JWT_SECRET=${config.sops.placeholder."jamye-plz/jwt_secret"}
      KAKAO_CLIENT_ID=${config.sops.placeholder."jamye-plz/kakao_client_id"}
      KAKAO_CLIENT_SECRET=${config.sops.placeholder."jamye-plz/kakao_client_secret"}
      GOOGLE_CLIENT_ID=${config.sops.placeholder."jamye-plz/google_client_id"}
      GOOGLE_CLIENT_SECRET=${config.sops.placeholder."jamye-plz/google_client_secret"}
      KAKAO_REDIRECT_URI=https://jamye-plz.ridewithmin.com/api/auth/kakao/callback
      GOOGLE_REDIRECT_URI=https://jamye-plz.ridewithmin.com/api/auth/google/callback
      FRONTEND_ORIGIN=https://jamye-plz.ridewithmin.com
      MINIO_ACCESS_KEY=${config.sops.placeholder."jamye-plz/minio_access_key"}
      MINIO_SECRET_KEY=${config.sops.placeholder."jamye-plz/minio_secret_key"}
      VAPID_PRIVATE_KEY=${config.sops.placeholder."jamye-plz/vapid_private_key"}
      VAPID_PUBLIC_KEY=${config.sops.placeholder."jamye-plz/vapid_public_key"}
      VAPID_CLAIM_EMAIL=you@example.com   # 순수 이메일 — mailto: 는 백엔드가 붙인다
    '';
  };

  # MinIO 루트 자격증명 — 앱 env와 **별개 파일**이다. minio.service와
  # jamye-plz-minio-bucket.service만 읽으며, 백엔드에는 주지 않는다.
  sops.templates."jamye-plz-minio-root.env" = {
    restartUnits = [ "minio.service" ];
    content = ''
      MINIO_ROOT_USER=${config.sops.placeholder."jamye-plz/minio_root_user"}
      MINIO_ROOT_PASSWORD=${config.sops.placeholder."jamye-plz/minio_root_password"}
    '';
  };

  services.jamye-plz = {
    enable = true;
    listenPort = 8080;
    environmentFile = config.sops.templates."jamye-plz.env".path;

    storage = {
      # createLocally = true 가 기본 — services.minio + 버킷 생성 유닛을 함께 선언한다.
      rootCredentialsFile = config.sops.templates."jamye-plz-minio-root.env".path;
      # presigned URL에 그대로 박히므로 **브라우저가 닿는 https 주소**여야 한다.
      # 모듈이 localhost/non-https를 assertion으로 거부한다.
      publicUrl = "https://minio.ridewithmin.com";
    };
  };
}
```

`MINIO_ENDPOINT`/`MINIO_BUCKET`은 모듈이 `storage.publicUrl`/`storage.bucket`에서
직접 export 하므로 env 템플릿에 넣지 않습니다. 시크릿(access/secret key)만
`environmentFile`로 갑니다 — Nix store에 남지 않도록.

**`hosts/alfheim/default.nix`** — import 한 줄만 추가:

```nix
imports = [
  ./hardware-configuration.nix
  ./disko.nix
  ../../services/jamye-plz.nix      # ← 추가
];
```

### `services/ingress.nix` (yggdrasil) — virtualHost 1개

```nix
virtualHosts."jamye-plz.ridewithmin.com".extraConfig = ''
  reverse_proxy http://alfheim.tail6fc192.ts.net:8080
'';

# 미디어(MinIO S3) — presigned URL의 호스트가 이 주소다.
virtualHosts."minio.ridewithmin.com".extraConfig = ''
  reverse_proxy http://alfheim.tail6fc192.ts.net:9000
'';
```

> **왜 alfheim의 로컬 Caddy(:8080)를 재사용하지 않는가**: presigned URL은 SigV4가
> **호스트와 경로를 함께 서명**하므로, 앱과 같은 호스트에 경로로 얹으면(`/media/*`)
> 서명이 깨진다. MinIO는 자기 호스트 루트에 그대로 노출돼야 한다 → 별도 서브도메인.
>
> 버킷은 **프라이빗**이라 이 서브도메인이 열려도 서명 없는 요청은 403이다("도달성 ≠ 읽기 권한").
> MinIO 콘솔(:9001)은 loopback 바인딩이라 이 경로로 노출되지 않는다.

### `services/cloudflared.nix` (yggdrasil) — ingress 엔트리 1개

```nix
ingress."jamye-plz.ridewithmin.com" = {
  service = "https://localhost:443";
  originRequest = {
    httpHostHeader = "jamye-plz.ridewithmin.com";
    originServerName = "jamye-plz.ridewithmin.com";
  };
};

ingress."minio.ridewithmin.com" = {
  service = "https://localhost:443";
  originRequest = {
    httpHostHeader = "minio.ridewithmin.com";
    originServerName = "minio.ridewithmin.com";
  };
};
```

### Cloudflare DNS

`jamye-plz.ridewithmin.com`과 `minio.ridewithmin.com` **둘 다** Tunnel CNAME를
추가합니다(다른 public 서비스와 동일).

> Cloudflare 무료 플랜의 업로드 상한(100MB)이 미디어 업로드 경로에 걸립니다.
> 현재 이미지 cap이 10MiB라 여유가 있지만, M3에서 비디오를 열 때 재확인할 것.

---

## 배포

```bash
# homelab 리포에서
nix flake check --no-build           # eval 게이트
just test alfheim                    # 임시 활성화 (재부팅 시 사라짐)
# 확인 후:
just switch alfheim                  # 영구 적용

# switch 후, tailnet 클라이언트에서:
curl -fsS https://jamye-plz.ridewithmin.com/        # SPA
curl -fsS https://jamye-plz.ridewithmin.com/api/docs
```

alfheim에서:

```bash
systemctl status jamye-plz-migrate jamye-plz-backend caddy postgresql \
                 minio jamye-plz-minio-bucket
journalctl -u jamye-plz-backend -f
curl -fsS http://127.0.0.1:8000/api/docs            # 백엔드 직접
curl -fsS http://127.0.0.1:8080/                    # 로컬 caddy
curl -fsS http://127.0.0.1:9000/minio/health/ready  # MinIO 준비 상태
```

**버킷 유닛이 실패했다면** — 진짜 원인이 로그에 남습니다(크리덴셜은 절대 찍지 않음):

```bash
journalctl -u jamye-plz-minio-bucket --no-pager
```

이 유닛은 `health → mc alias → mc mb → mc stat`를 **한 묶음으로** 최대 120초간
재시도하고, 끝내 실패하면 마지막 curl/mc 오류를 그대로 출력합니다. 백엔드가 이
유닛을 `Requires`하므로 실패 시 앱도 뜨지 않습니다(조용히 무버킷 상태로 가는 것 방지).

롤백(호스트에서): `sudo nixos-rebuild switch --rollback`.

---

## 프로덕션 체크리스트 (앱 특화)

- [ ] OAuth 콘솔: redirect URI 등록
      `https://jamye-plz.ridewithmin.com/api/auth/{kakao,google}/callback`.
- [ ] `FRONTEND_ORIGIN=https://jamye-plz.ridewithmin.com` (동일 출처 ⇒ CORS 부담 없음).
- [ ] 프로덕션에서 JWT 쿠키 `Secure` — 백엔드는 프록시 뒤에서 평문 HTTP를 보지만
      브라우저↔Cloudflare 구간은 HTTPS입니다. `APP_ENV=production`이
      `core/config.py`/auth에서 secure 쿠키를 켜는지 확인하세요.
- [ ] `https://jamye-plz.ridewithmin.com/api/docs`에 대한 Uptime Kuma 체크 추가.
- [ ] **MinIO**: `storage.publicUrl`이 https이고 브라우저에서 닿는지 확인. 서명 없는
      `https://minio.ridewithmin.com/jamye/<key>` 요청이 **403**이어야 정상(프라이빗 버킷).
      `APP_ENV=production`에서 MinIO 키가 비었거나 endpoint가 localhost/non-https면
      백엔드가 **기동을 거부**합니다(무서명 URL이 조용히 켜지는 것 방지).
- [ ] **Web Push**: `GET /api/push/vapid-public-key`가 빈 문자열이 아닌지 확인.
      비어 있으면 VAPID 시크릿이 주입되지 않은 것이고, 프론트 알림 토글이 숨겨집니다.
- [ ] **서비스워커**: 배포 후 DevTools → Application → Service workers에 등록이
      **1건** 보이는지 확인. 0건이면 SW 스크립트 평가가 실패한 것(푸시 구독 자체가 불가) —
      Console에 workbox 예외가 찍힙니다.

## 참고 및 한계

- WebSocket `/api/ws`는 두 Caddy 계층을 모두 투명하게 통과합니다(별도 설정 불필요 —
  Caddy가 Upgrade를 자동 프록시).
- DB는 peer 인증을 쓰므로 `DATABASE_URL`에 비밀번호가 없고 시크릿이 아닙니다.
- 단일 호스트 배포입니다. 헬스체크 기반 자동 롤백이 필요하면 추후 `deploy-rs`를
  도입할 수 있지만, 호스트 1대에는 `nixos-rebuild --rollback`으로 충분합니다.
```
