# Project Lessons Learned

### 2026-07-16: QA/Frontend — colored surface 안의 rich text는 상속 색상만 믿지 않는다

- **Problem**: daisyUI `chat-bubble-primary`는 올바른 `primary-content`를 제공했지만 Tailwind Typography `.prose`가 자식 Markdown을 `base-content`로 덮어 라이트 모드 대비가 2.13:1로 떨어졌다.
- **Root Cause**: theme smoke가 base surfaces 중심이었고 colored component 안 제목·목록·code의 computed style을 검증하지 않았다.
- **Fix Applied**: primary surface용 prose variable mapping과 semantic primary/neutral background mix를 적용해 Lighthouse contrast failure를 제거했다.
- **Prevention**: theme 변경 시 `surface token × content token × rich text element × light/dark` 매트릭스로 computed style과 WCAG 대비를 런타임 검증한다.
- **CD Impact**: oma-00mrnfuw0trni9gnb8 continuation에서 사용자 correct 2회, +50.

> `.agents/` is protected SSOT, so this project-local lesson is stored in Serena memory.
