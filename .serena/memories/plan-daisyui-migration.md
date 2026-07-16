# Plan: daisyUI 전면 마이그레이션 (session oma-00mr90qovpetqtnnlq)

- Tracker: `docs/planning/001-daisyui-migration.md` / JSON: `.agents/results/plan-oma-00mr90qovpetqtnnlq.json`
- Goal: frontend 전체를 daisyUI 5 + 빌트인 테마로 완전 이관. daisyUI 제공 값 > 기존 커스텀 값.
- 확정 결정: (1) 빌트인 `dark` 테마, (2) `light --default, dark --prefersdark` 시스템 추종 양 모드,
  (3) CTA `btn-primary` 통일, (4) 이모지→lucide, (5) elevation은 daisyUI 시맨틱 수용,
  (6) 카카오 #FEE500 유지, (7) DateDial 커스텀 유지(색만 토큰화)
- 6 Phases (0 설치 / 1 컬러 토큰 전면 이관 ~250회·13파일 / 2 프리미티브 / 3 구조+모달+아이콘 / 4 ChatRoom / 5 정리·PWA·QA)
- 실행 게이트: 사용자가 phase별 승인. 2026-07-16 Phase 0 승인 대기 상태.
- 주의: ChatRoom 스크롤 앵커·낙관 전송·IME 로직 불변, prose-invert 제거 필요(라이트 모드), PWA theme_color 듀얼 대응.
