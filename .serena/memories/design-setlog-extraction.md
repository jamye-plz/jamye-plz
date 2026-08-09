# Setlog 레퍼런스 추출 및 잼얘좀 번역

## Retrieval
- 공식 도메인: https://setlog.kr
- 한국 App Store: https://apps.apple.com/kr/app/setlog/id6587576438
- App Store 공식 스크린샷 5장 확인.
- getdesign 0.6.24 manifest 75개에 setlog 매치 없음. Reference URL branch 사용.

## Extraction
- 따뜻한 미색 캔버스, 얇은 핑크 윤곽, 큰 유기적 라운드.
- 라벤더·베이비블루·버터옐로·민트 포인트와 검은 잉크 낙서.
- 중앙 집중형 카드 피드, 상단 pill 제목, 친구 이름·시간을 이미지 위에 직접 표시.
- 짧은 반응 pill과 낙서형 감정 표현으로 친밀감 형성.
- 마케팅 화면은 손그림 장식과 약간 기울어진 프레임을 사용.

## Translation
- 영상 로그 타일 → 날짜별 텍스트 주제 카드.
- 시간 라벨 → 날짜·작성 시각·새 메시지 상태.
- 영상 반응 → 빠른 반응 chip + 채팅 입장.
- 친구 스쿼드 → 폐쇄 그룹과 avatar group.
- 카메라/회전 제스처는 제외. 구조 아이콘은 Lucide 유지.
- 손그림은 빈 상태·온보딩·구획 장식으로 제한하고 본문/채팅에는 사용하지 않음.

## Synthesis constraints
- Pretendard 단일 패밀리, 16px 본문, WCAG 2.2 AA.
- 파스텔은 넓은 표면과 상태에 사용; CTA와 포커스는 더 짙은 접근성 색상.
- 과한 clay shadow, glass blur, continuous animation, card random rotation 금지.
- light/dark 두 테마를 함께 설계하고 daisyUI semantic tokens로 매핑.

## Alignment
- 사용자 확정: 한국어 전용, 친한 친구·지인, 장난스럽고 재치 있음, 부드러운 파스텔, Setlog 감각, WCAG 2.2 AA.
