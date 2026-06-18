# jamye-plz를 alfheim에 배포하기 (NixOS 홈랩)

[smg1024/homelab](https://github.com/smg1024/homelab) NixOS flake의 **alfheim**
호스트에 백엔드·프론트엔드·DB를 배포하고, 외부 공개는 **yggdrasil** 인그레스
노드에 위임하는 방법입니다.

## 아키텍처

```
인터넷 → Cloudflare Edge → Cloudflare Tunnel → cloudflared (yggdrasil)
                                                    │  https://localhost:443
                                            caddy (yggdrasil)  ← 여기서 TLS 종단
                                            (cloudflare DNS-ACME 인증서)
                                                    │  reverse_proxy
                                                    │  http://alfheim.<tailnet>:8080
                                        ─── tailnet (WireGuard) ───
                                                    │
                         ┌────────────────────── alfheim ───────────────────────┐
                         │  caddy :8080  (auto_https off, 앱 내부 라우팅)         │
                         │    ├ /api/*  → 127.0.0.1:8000  (uvicorn, WS 포함)      │
                         │    └ /*      → 정적 SPA (Nix store), try_files          │
                         │  jamye-backend.service (uvicorn)                       │
                         │  jamye-migrate.service (alembic upgrade head, oneshot) │
                         │  postgresql (로컬, Unix-socket peer 인증)              │
                         └────────────────────────────────────────────────────────┘
```

- **유일한 외부 노출점**: Cloudflare Tunnel. 어떤 호스트도 public 포트를 열지 않습니다.
- **yggdrasil → alfheim** 홉은 tailnet을 탑니다. 이 홈랩에서는 `tailscale0`가
  trusted 방화벽 인터페이스라 **alfheim 방화벽은 손댈 필요가 없습니다** — public
  방화벽은 닫힌 채 유지됩니다.
- **시크릿**은 homelab의 기존 sops-nix가 소유합니다. 이 리포의 모듈은 `environmentFile`
  경로만 받습니다.
- **데이터베이스**는 비밀번호 없는 Unix-socket peer 인증을 사용 — 암호화할 게 없습니다.

이 리포가 제공하는 것: `packages.{backend,frontend,backendSrc}` 와
`nixosModules.jamye`. 아래의 배선(wiring)은 **homelab** 리포에 들어갑니다.

---

## 이 리포가 노출하는 출력 (`flake.nix`)

| 출력 | 용도 |
| --- | --- |
| `packages.<sys>.backend` | uv2nix virtualenv (`bin/uvicorn`, `bin/alembic`) |
| `packages.<sys>.backendSrc` | 마이그레이션용 `alembic.ini` + `alembic/` |
| `packages.<sys>.frontend` | 정적 SvelteKit SPA 빌드 |
| `nixosModules.jamye` | systemd + Caddy + PostgreSQL 배선 |

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
ssh-keyscan -t ed25519 alfheim.<tailnet>.ts.net | ssh-to-age
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
sops secrets/jamye.yaml
```

```yaml
jamye:
  jwt_secret: "<openssl rand -hex 32>"
  kakao_client_id: "..."
  kakao_client_secret: ""        # Kakao 콘솔에서 "Client Secret"을 켰을 때만
  google_client_id: "..."
  google_client_secret: "..."
  # M1: minio_access_key / minio_secret_key / vapid_* 는 추후 추가
```

---

## homelab flake에 배선하기

### `flake.nix` (homelab) — 입력 추가

```nix
inputs.jamye-plz.url = "github:jamye-plz/jamye-plz";   # 또는 본인 fork/branch
# inputs.jamye-plz.inputs.nixpkgs.follows = "nixpkgs"; # 선택: uv2nix는 자체 nixpkgs를 pin
```

`inputs`를 호스트 모듈로 전달하세요(이 flake는 이미 호스트에 `specialArgs`/
`extraSpecialArgs`를 쓰므로 그대로 재사용해 `hosts/alfheim/default.nix` 안에서
`inputs.jamye-plz`가 보이게 합니다).

### `hosts/alfheim/default.nix` — 모듈 import + 시크릿 렌더

```nix
{ config, inputs, ... }:
{
  imports = [
    ./hardware-configuration.nix
    ./disko.nix
    inputs.jamye-plz.nixosModules.jamye
  ];

  # 시크릿 → sops-nix가 렌더하는 env 파일
  sops.secrets."jamye/jwt_secret"        = { sopsFile = ../../secrets/jamye.yaml; };
  sops.secrets."jamye/kakao_client_id"   = { sopsFile = ../../secrets/jamye.yaml; };
  sops.secrets."jamye/kakao_client_secret" = { sopsFile = ../../secrets/jamye.yaml; };
  sops.secrets."jamye/google_client_id"  = { sopsFile = ../../secrets/jamye.yaml; };
  sops.secrets."jamye/google_client_secret" = { sopsFile = ../../secrets/jamye.yaml; };

  sops.templates."jamye.env" = {
    owner = "jamye";
    restartUnits = [ "jamye-backend.service" ];
    content = ''
      JWT_SECRET=${config.sops.placeholder."jamye/jwt_secret"}
      KAKAO_CLIENT_ID=${config.sops.placeholder."jamye/kakao_client_id"}
      KAKAO_CLIENT_SECRET=${config.sops.placeholder."jamye/kakao_client_secret"}
      GOOGLE_CLIENT_ID=${config.sops.placeholder."jamye/google_client_id"}
      GOOGLE_CLIENT_SECRET=${config.sops.placeholder."jamye/google_client_secret"}
      KAKAO_REDIRECT_URI=https://jamye-plz.ridewithmin.com/api/auth/kakao/callback
      GOOGLE_REDIRECT_URI=https://jamye-plz.ridewithmin.com/api/auth/google/callback
      FRONTEND_ORIGIN=https://jamye-plz.ridewithmin.com
    '';
  };

  services.jamye = {
    enable = true;
    listenPort = 8080;
    environmentFile = config.sops.templates."jamye.env".path;
  };
}
```

### `services/ingress.nix` (yggdrasil) — virtualHost 1개

```nix
virtualHosts."jamye-plz.ridewithmin.com".extraConfig = ''
  reverse_proxy http://alfheim.<tailnet>.ts.net:8080
'';
```

### `services/cloudflared.nix` (yggdrasil) — ingress 엔트리 1개

```nix
ingress."jamye-plz.ridewithmin.com" = {
  service = "https://localhost:443";
  originRequest = {
    httpHostHeader = "jamye-plz.ridewithmin.com";
    originServerName = "jamye-plz.ridewithmin.com";
  };
};
```

### Cloudflare DNS

`jamye-plz.ridewithmin.com`에 대한 Tunnel CNAME를 추가합니다(다른 public
서비스와 동일).

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
systemctl status jamye-migrate jamye-backend caddy postgresql
journalctl -u jamye-backend -f
curl -fsS http://127.0.0.1:8000/api/docs            # 백엔드 직접
curl -fsS http://127.0.0.1:8080/                    # 로컬 caddy
```

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
- [ ] M1: 사진 업로드가 들어오면 MinIO + VAPID 활성화(시크릿 + 모듈 옵션 추가).

## 참고 및 한계

- WebSocket `/api/ws`는 두 Caddy 계층을 모두 투명하게 통과합니다(별도 설정 불필요 —
  Caddy가 Upgrade를 자동 프록시).
- DB는 peer 인증을 쓰므로 `DATABASE_URL`에 비밀번호가 없고 시크릿이 아닙니다.
- 단일 호스트 배포입니다. 헬스체크 기반 자동 롤백이 필요하면 추후 `deploy-rs`를
  도입할 수 있지만, 호스트 1대에는 `nixos-rebuild --rollback`으로 충분합니다.
```
