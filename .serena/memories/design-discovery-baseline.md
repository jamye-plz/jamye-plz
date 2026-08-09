# 잼얘좀 디자인 발견 베이스라인 (2026-08-06)

## 제품/플랫폼
- 폐쇄형 그룹 대화 PWA, 데스크톱 웹과 iOS/Android 모바일 브라우저 대상.
- 현재 UI 언어는 한국어(`app.html lang=ko`), 앱 이름은 잼얘좀.

## 현재 프런트엔드
- Svelte 5 + SvelteKit + Tailwind CSS 4 + daisyUI 5.6.x.
- Pretendard 16px/1.6, Lucide Svelte 아이콘.
- daisyUI `light --default`, `dark --prefersdark`; 의미 토큰을 전 화면에서 사용.
- AppHeader/navbar, chat/chat-bubble, card/list/modal/button/textarea/status/loading 등 daisyUI 구성요소가 이미 광범위하게 적용됨.
- PWA viewport-fit, dual theme-color, iOS standalone 메타, safe-area, pull-to-refresh, reduced-motion 지원 존재.

## 보존할 기존 결정
- 시스템 추종 라이트/다크, Lucide 아이콘, CTA btn-primary, daisyUI 의미 토큰과 elevation.
- iOS PWA 채팅 키보드 전환은 best-effort이며 정착 상태를 우선. 구조 변경 시 기존 스크롤 앵커, 낙관 전송, IME 로직을 보존.

## 발견된 디자인 과제
- 기능적 마이그레이션은 상당 부분 완료됐으나 별도 DESIGN.md와 .design-context.md가 없음.
- 모바일 중심 max-w-lg/max-w-2xl 단일 컬럼이 많아 데스크톱 적응형 정보 구조를 별도로 정의할 필요가 있음.
- 제품 고유의 브랜드 톤, 색/형태 언어, 밀도, 모션 규칙을 확정해야 함.

## 확정된 컨텍스트
- 서비스 언어: 한국어 전용.
- Pretendard와 한국어 문장 길이·줄바꿈을 기준으로 설계.
- 핵심 사용자: 친한 친구와 지인의 소규모 폐쇄 그룹.
- 공개 탐색보다 빠른 참여, 친밀감, 대화의 연속성을 우선.
- 브랜드 성격: 장난스럽고 재치 있게. 재미는 포인트 색상, 마이크로카피, 상태 표현에 집중하고 대화 가독성은 안정적으로 유지.
- 미적 방향: 부드러운 파스텔, 둥근 표면, 낮은 elevation. 파스텔은 표면과 상태에 쓰고 본문 대비는 유지. 다크 모드는 별도 저채도 톤으로 설계.
- 기준 레퍼런스: Setlog(setlog.kr, App Store). 미색 캔버스, 파스텔 윤곽선, 큰 라운드 카드, 손그림 리듬과 친구 반응 감각을 참고.
- 제품 번역: 영상 로그를 복제하지 않고 텍스트 주제 카드 → 친구 반응 → 실시간 채팅으로 변환. 구조 아이콘은 Lucide 유지.
- getdesign 0.6.24 최신 manifest 75개에는 Setlog 매치 없음. Reference URL 분석 경로 사용.
- 접근성 목표: WCAG 2.2 AA. 4.5:1 본문 대비, 44px 터치 대상, 키보드·스크린 리더, 비색상 상태 신호, reduced motion을 필수화.
