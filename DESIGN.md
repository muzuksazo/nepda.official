---
name: 냅다
slug: napda
category: content
last_updated: 2026-11-25
created_at: 2026-11-25
lang: ko
logo: asset/logo/logo.png
colors:
  ## Brand (공식 4색 · 브랜드 보드 [src:1])
  brand-lime: oklch(0.939 0.208 121.4)            # #D6FF3F 공식 Lime. 작지만 꼭 필요한 기능 표시에만 쓴다 — 게이지(진행 막대·훅 길이), 단계 번호, 선택 체크, 브랜드 배지, 강조 단어. 버튼·카드 같은 넓은 면과 흰 배경 위 글자에는 쓰지 않는다(흰 배경 1.15:1)
  brand-black: oklch(0 0 0)                       # #000000 공식 Black. 워드마크, 라임 위 글자(18.2:1), 다크 캔버스
  brand-gray: oklch(0.922 0 0)                    # #E5E5E5 공식 Gray. 라이트 표면 base, 보더 weak
  brand-white: oklch(1 0 0)                       # #FFFFFF 공식 White. 라이트 배경, 다크 위 글자
  lime-edge: oklch(0.145 0 0)                     # #0A0A0A 라이트에서 라임 표시를 두르는 1.5px 외곽선. 라임은 흰·회색 바탕과 1.1:1이라 외곽선(17:1)이 경계를 만든다. 다크에서는 생략(라임 vs #232323 13.6:1)
  ## 선택된 카드 (라임 틴트 — 넓은 면에 허용되는 유일한 라임, 18%로 아주 옅게)
  selected-bg: oklch(0.986 0.046 116.4)           # #F8FFDC 라이트 선택 카드 면 (라임 18% + 흰색). 설명 글자 #5C5C5C 6.5:1
  selected-border: oklch(0.841 0.203 122.2)       # #B5DE0A 라이트 선택 카드 2px 테두리 (라임 한 단계 진하게)
  dark-selected-bg: oklch(0.242 0.034 118.7)      # #1E220F 다크 선택 카드 면 (라임 10% + #0A0A0A)
  ## 반전 면 (1차 버튼 — 넓은 면은 라임 대신 검정)
  inverse: oklch(0.145 0 0)                       # #0A0A0A 라이트 1차 버튼 면 (흰 글자 19.8:1)
  inverse-hover: oklch(0.284 0 0)                 # #2B2B2B 라이트 1차 버튼 hover
  dark-inverse: oklch(1 0 0)                      # #FFFFFF 다크 1차 버튼 면 (검정 글자)
  dark-inverse-hover: oklch(0.922 0 0)            # #E5E5E5 다크 1차 버튼 hover
  ## Background / Surface (라이트)
  bg-base: oklch(1 0 0)                           # #FFFFFF 배경 base
  bg-weak: "#FAF9F6"                       # 배경 weak, 온보딩 패널(종이 톤)
  surface-weak: "#F4F3EF"                  # 표면 weak — 행동 타일, 안내 상자, 미정 칩, 크레딧 알약, 콘티 스케치북. 차가운 순회색 대신 살짝 따뜻한 종이 톤
  surface-base: "#EAE9E3"                  # 표면 base, 진행 막대 빈 칸, 비활성 버튼
  surface-strong: "#DCDAD2"                # 표면 strong, 스켈레톤 반짝임, 스케치북 점
  ## Background / Surface (다크)
  dark-bg-base: "#0E0E0C"                  # 배경 base
  dark-bg-weak: oklch(0 0 0)                      # #000000 배경 weak (= brand-black), 영상 플레이어 바탕
  dark-surface-weak: "#1A1A17"             # 표면 weak, 카드
  dark-surface-base: "#24231F"             # 표면 base, 입력창·secondary 버튼
  dark-surface-strong: "#33322C"           # 표면 strong
  ## 미디어 자리 (작은 썸네일 — 회색 상자 대신)
  tint: "#F3FBD0"                                 # 제품·훅 썸네일 자리 면 (아주 옅은 라임)
  on-tint: "#4A5E00"                              # 그 위 아이콘 (6.8:1)
  dark-tint: "#1D2210"
  dark-on-tint: "#C9E86A"                         # (11.8:1)
  ## Text (라이트)
  text-primary: oklch(0.145 0 0)                  # #0A0A0A 텍스트 primary (19.8:1)
  text-secondary: "#2E2D2A"                # 텍스트 secondary (13.8:1)
  text-tertiary: "#5E5C55"                 # 텍스트 tertiary, 보조 설명 (흰 배경 6.7:1)
  text-weak: "#77756C"                     # placeholder (흰 배경 4.6:1)
  ## Text (다크)
  dark-text-primary: oklch(1 0 0)                 # #FFFFFF 텍스트 primary
  dark-text-secondary: "#E8E7E2"
  dark-text-tertiary: "#A8A69D"            # (7.9:1)
  dark-text-weak: "#8A887F"                # placeholder (5.4:1)
  ## Border
  border-weak: "#ECEBE5"                   # 구분선, 카드 테두리
  border-base: "#D6D4CC"                   # 입력창 테두리
  border-strong: oklch(0.145 0 0)                 # #0A0A0A 라이트 보더 strong, 선택 카드·스티커 테두리
  dark-border-weak: "#272622"
  dark-border-base: "#3D3C36"
  ## Function — 오류 하나뿐. 주황·파랑·초록 같은 상태색은 쓰지 않는다 (주의·정보·완료는 회색 + 아이콘 + 문구)
  danger: oklch(0.560 0.203 28.2)                 # #D12A24 입력 오류 표시 전용 (흰 배경 5.2:1)
  dark-danger: oklch(0.710 0.183 26.6)            # #FF6B61 다크 오류 글자 (7.1:1)
  white: oklch(1 0 0)                             # #FFFFFF 반전 텍스트 고정 흰색
fonts:
  font-display: "\"Paperlogy\", \"Pretendard Variable\", Pretendard, \"Apple SD Gothic Neo\", sans-serif"   # 페이퍼로지 7 Bold(700), 앱에 포함
  font-sans: "\"Pretendard Variable\", Pretendard, -apple-system, BlinkMacSystemFont, \"Apple SD Gothic Neo\", \"Malgun Gothic\", sans-serif"
typography:
  display-32:
    fontFamily: "{fonts.font-display}"
    fontSize: 32px
    fontWeight: 700
    lineHeight: 42px
    letterSpacing: -0.6px
  display-28:
    fontFamily: "{fonts.font-display}"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 36px
    letterSpacing: -0.6px
  title-24:
    fontSize: 24px
    fontWeight: 800
    lineHeight: 32px
    letterSpacing: -0.4px
  title-20:
    fontSize: 20px
    fontWeight: 700
    lineHeight: 28px
    letterSpacing: -0.3px
  title-17:
    fontSize: 17px
    fontWeight: 700
    lineHeight: 24px
    letterSpacing: -0.2px
  body-16:
    fontSize: 16px
    fontWeight: 400
    lineHeight: 24px
    letterSpacing: -0.2px
  body-14:
    fontSize: 14px
    fontWeight: 400
    lineHeight: 21px
    letterSpacing: -0.1px
  label-16:
    fontSize: 16px
    fontWeight: 700
    lineHeight: 20px
    letterSpacing: -0.2px
  label-14:
    fontSize: 14px
    fontWeight: 600
    lineHeight: 18px
    letterSpacing: -0.1px
  label-12:
    fontSize: 12px
    fontWeight: 700
    lineHeight: 16px
    letterSpacing: 0px
spacing:
  space-4: 4px
  space-8: 8px
  space-12: 12px
  space-16: 16px
  space-20: 20px
  space-24: 24px
  space-32: 32px
  space-40: 40px
  space-48: 48px
rounded:
  radius-sm: 6px
  radius-md: 10px
  radius-lg: 14px
  radius-xl: 20px
  radius-2xl: 28px
  radius-circular: 9999px
elevation:
  shadow-card: 0 1px 2px oklch(0 0 0 / 0.06), 0 4px 12px oklch(0 0 0 / 0.06)   # 라이트 카드. 다크는 그림자 대신 면 명도 차
  shadow-sheet: 0 -8px 24px oklch(0 0 0 / 0.06)   # 하단 고정 CTA 영역
components:
  app-header:
    backgroundColor: "{colors.bg-base}"
    height: 72px
  credit-badge:
    backgroundColor: "{colors.surface-weak}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.radius-circular}"
    height: 32px
  profile-avatar:
    backgroundColor: "{colors.surface-weak}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.radius-circular}"
    size: 32px
  profile-avatar-lg:
    backgroundColor: "{colors.surface-weak}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.radius-circular}"
    size: 56px
  list-row:
    backgroundColor: transparent
    textColor: "{colors.text-primary}"
    minHeight: 52px
  credit-balance-card:
    backgroundColor: "{colors.bg-base}"
    borderColor: "{colors.border-weak}"
    rounded: "{rounded.radius-xl}"
  stat-tile:
    backgroundColor: "{colors.surface-weak}"
    rounded: "{rounded.radius-lg}"
    minHeight: 76px
  confirm-sheet:
    backgroundColor: "{colors.bg-base}"
    rounded: 28px 28px 0 0
  flow-header:
    backgroundColor: "{colors.bg-base}"
    textColor: "{colors.text-primary}"
    typography: "{typography.title-17}"
    height: 94px
  progress-bar:
    backgroundColor: "{colors.surface-base}"
    fillColor: "{colors.brand-lime}"
    segments: 8
    gap: 4px
    height: 6px
  step-number:
    backgroundColor: "{colors.brand-lime}"
    textColor: "{colors.brand-black}"
    size: 32px
  button-primary:
    backgroundColor: "{colors.inverse}"
    textColor: "{colors.white}"
    typography: "{typography.label-16}"
    rounded: "{rounded.radius-lg}"
    height: 52px
  button-secondary:
    backgroundColor: "{colors.bg-base}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.border-strong}"
    typography: "{typography.label-16}"
    rounded: "{rounded.radius-lg}"
    height: 52px
  button-ghost:
    textColor: "{colors.text-primary}"
    typography: "{typography.label-14}"
    rounded: "{rounded.radius-md}"
    height: 44px
  text-input:
    backgroundColor: "{colors.bg-base}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.border-base}"
    typography: "{typography.body-16}"
    rounded: "{rounded.radius-md}"
    height: 48px
  choice-chip:
    backgroundColor: "{colors.bg-base}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.border-base}"
    typography: "{typography.label-14}"
    rounded: "{rounded.radius-md}"
    height: 48px
  choice-chip-selected:
    backgroundColor: "{colors.selected-bg}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.selected-border}"
    rounded: "{rounded.radius-md}"
    height: 48px
  hook-card:
    backgroundColor: "{colors.bg-base}"
    borderColor: "{colors.border-weak}"
    rounded: "{rounded.radius-xl}"
    padding: 12px
  hook-card-selected:
    backgroundColor: "{colors.selected-bg}"
    borderColor: "{colors.selected-border}"
    rounded: "{rounded.radius-xl}"
  check-mark-selected:
    backgroundColor: "{colors.brand-lime}"
    textColor: "{colors.brand-black}"
    size: 26px
  project-card:
    backgroundColor: "{colors.bg-base}"
    borderColor: "{colors.border-weak}"
    rounded: "{rounded.radius-xl}"
    padding: 16px
  badge-neutral:
    backgroundColor: "{colors.surface-base}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.label-12}"
    rounded: "{rounded.radius-circular}"
    height: 24px
  badge-brand:
    backgroundColor: "{colors.brand-lime}"
    textColor: "{colors.brand-black}"
    borderColor: "{colors.lime-edge}"
    typography: "{typography.label-12}"
    rounded: "{rounded.radius-circular}"
    height: 24px
  badge-pending:
    backgroundColor: transparent
    textColor: "{colors.text-tertiary}"
    borderColor: "{colors.text-weak}"
    typography: "{typography.label-12}"
    rounded: "{rounded.radius-circular}"
    height: 24px
  note:
    backgroundColor: "{colors.surface-weak}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.radius-lg}"
  video-frame:
    backgroundColor: "{colors.brand-black}"
    rounded: "{rounded.radius-xl}"
    aspectRatio: 9/16
  bottom-cta-bar:
    backgroundColor: "{colors.bg-base}"
    borderColor: "{colors.border-weak}"
    padding: 12px 20px 24px
---

# 냅다 — design.md

냅다(NAPDA)는 제품 영상 앞에 B급 감성 훅을 붙여 릴스 광고로 만들어 주는 서비스다. 제품 화면은 흑백으로 차분하게 두고, 형광 라임은 꼭 필요한 몇 곳에만 점처럼 찍는다 [src:1][src:2].

## Brand & Style

냅다는 "B급 감성 광고영상, 냅다 만들어보세요!"와 "아이디어만 있다면, 이제는 냅다."라는 두 문장으로 자신을 소개한다 [src:1]. 이름 그대로 망설이지 않고 바로 시작하는 태도가 브랜드의 중심이다. 시각적 인상은 세 가지다.

- **번쩍 버스트 위의 손글씨 워드마크.** 톱니 모양 라임 버스트 위에 굵고 기울어진 검정 손글씨 "냅다", 그 아래 둥근 대문자 "NAPDA"와 클래퍼보드 [src:1][src:2].
- **라임 × 블랙의 강한 대비.** 공식 색은 라임, 블랙, 그레이, 화이트 네 가지뿐이다 [src:1].
- **선글라스 곰 마스코트와 낙서풍 그래픽.** "냅다곰"과 효과선, "ㅋㅋ", 번개, 반짝이 같은 요소 [src:1].

UI의 원칙은 **"넓은 면은 흑백, 작은 신호는 라임"**이다. 라임은 형광색이라 면적이 조금만 넓어도 화면 전체가 시끄러워진다. 반대로 검정만 쓰면 화면이 무겁고 브랜드가 사라진다. 그래서 버튼·카드·영상 프레임 같은 넓은 면은 흑백이 맡고, 사용자가 "지금 어디까지 왔는지, 무엇을 골랐는지" 읽는 작은 신호에 라임을 쓴다.

1. 게이지 — 진행 막대 채움, 훅 길이 막대
2. 단계 번호 — 온보딩·촬영 가이드의 번호 원
3. 선택됨 — 선택된 선택지·카드의 체크
4. 브랜드 배지 — 라임 알약 안 검정 글자(예: "B 유형")
5. 강조 단어 — 화면당 한 단어의 하이라이트 마커

라이트에서는 브랜드 배지에 검정 외곽선(`{colors.lime-edge}`)을 두른다. 라임은 흰·회색 바탕과 명도 대비가 1.1:1이라 외곽선이 경계를 만든다. 검정 외곽선 스티커는 브랜드 보드의 그래픽 질감과도 같다 [src:1]. 게이지(진행 막대·훅 길이)는 외곽선 없이 칸을 끊은 점선으로 그린다. 칸 사이 틈이 경계를 대신하고, 진행 정도는 옆의 "5/8"·"N / 8" 숫자와 "훅/본편" 라벨이 함께 전한다.

로고(워드마크)는 홈·온보딩 상단 헤더에만, **한 화면에 하나**만 쓴다. 본문에 로고나 로고 이미지를 다시 넣지 않는다. 만들기 흐름(1~8단계) 화면에는 로고 대신 뒤로 가기와 단계 제목을 둔다.

기본 테마는 라이트다. 다크 테마는 같은 규칙을 검정 바탕 위로 뒤집은 것이다 — 1차 버튼이 흰 면이 되고, 라임 체크는 라임 원 안 검정 체크가 된다.

## Colors

공식 브랜드 색은 네 가지다 — Lime `{colors.brand-lime}`(#D6FF3F), Black `{colors.brand-black}`, Gray `{colors.brand-gray}`(#E5E5E5), White `{colors.brand-white}` [src:1]. 중립 단계와 반전 면, 오류색은 이 문서가 대비 계산으로 **산출한 값**이다.

**라임은 작은 기능 표시에만 쓴다.** 1차 버튼, 카드 배경, 배너, 영상 프레임 같은 넓은 면은 흑백이 맡고, 라임은 게이지·단계 번호·선택 표시·브랜드 배지처럼 작은 곳에만 쓴다. 라임 위 글자는 언제나 검정(18.2:1)이고, 흰 배경 위에 라임 글자를 쓰지 않는다(1.15:1). 라이트에서는 라임 표시에 1.5px `{colors.lime-edge}` 외곽선을 두른다.

**1차 행동은 검정이다.** 라이트에서 1차 버튼은 `{colors.inverse}` 면에 흰 글자(19.8:1), 다크에서는 `{colors.dark-inverse}` 면에 검정 글자다.

**회색이 와이어프레임처럼 보이지 않게 한다.** 와이어프레임 툴의 차가운 순회색(#F0F0F0·#E5E5E5)은 쓰지 않고, 회색 단계 전체를 아주 살짝 따뜻한 종이 톤(`#F4F3EF`·`#EAE9E3`)으로 둔다. 이미지가 아직 없는 자리도 "빈 회색 상자"로 두지 않는다 — 작은 썸네일(제품·훅)은 옅은 라임 틴트 `{colors.tint}` + 진한 라임 아이콘, 큰 그림 자리(그림 콘티)는 종이 톤 위 점 격자 스케치북으로 그린다. 기획 미정 배지도 점선 주석 대신 종이 톤 칩으로 쓴다. 회색 막대(스켈레톤)는 **불러오는 중**에만 반짝이며 보이고, 내용 자리를 채우는 용도로 쓰지 않는다.

**상태색을 늘리지 않는다.** 주황(경고), 파랑(정보), 초록(완료)은 라임·블랙 팔레트와 어울리지 않으므로 쓰지 않는다. 안내는 회색 `note` 상자에 정보 아이콘과 문구로, 완료는 회색 배지에 체크 아이콘으로, 미정 표시는 회색 점선 배지로 나타낸다. 색이 하나 더 필요한 곳은 입력 오류뿐이고, 그때만 `{colors.danger}`를 쓴다.

| 역할 | 라이트 | 다크 |
| --- | --- | --- |
| 배경 base | `{colors.bg-base}` | `{colors.dark-bg-base}` |
| 표면 (자리표시·안내 상자) | `{colors.surface-weak}` | `{colors.dark-surface-weak}` |
| 텍스트 primary | `{colors.text-primary}` | `{colors.dark-text-primary}` |
| 텍스트 tertiary | `{colors.text-tertiary}` | `{colors.dark-text-tertiary}` |
| 1차 버튼 면 | `{colors.inverse}` + 흰 글자 | `{colors.dark-inverse}` + 검정 글자 |
| 선택된 카드·선택지 | `{colors.selected-bg}` 면 + 2px `{colors.selected-border}` | `{colors.dark-selected-bg}` 면 + 2px `{colors.brand-lime}` |
| 게이지 (진행 막대·훅 길이) | `{colors.brand-lime}`, 외곽선 없음 + 숫자 병기 | `{colors.brand-lime}` |
| 단계 번호 원·선택 체크 | `{colors.brand-lime}` + 검정 숫자/체크, 외곽선 없음 | 같음 |
| 라임 표시 (브랜드 배지) | `{colors.brand-lime}` + 1.5px `{colors.lime-edge}` 외곽선, 위 글자 검정 | `{colors.brand-lime}`, 외곽선 없음 |
| 오류 | `{colors.danger}` | `{colors.dark-danger}` |

값은 frontmatter `colors:` 맵이 유일한 정본이다.

## Typography

포인트(디스플레이) 서체는 **페이퍼로지 Paperlogy 7 Bold**(굵기 700)다 — 화면 제목, 큰 숫자(예상 시간 "약 2~3분"), 썸네일 글자처럼 **눈에 먼저 들어와야 하는 곳에만** 쓰고, 나머지는 모두 Pretendard다. 둥글고 굵은 기하학적 한글(G마켓산스 계열)이라 B급 광고 톤의 큰 제목에 힘을 주면서도 본문 Pretendard와 잘 어울린다. 폰트 파일은 외부 CDN 없이 앱에 포함한다(`frontend/src/assets/fonts/Paperlogy-7Bold.woff2`, SIL OFL 1.1 — 같은 폴더 `OFL.txt`). 굵기는 700 하나만 싣는다(800은 화면에서 너무 무거워 낮췄다)(한글 전체 약 420KB). 브랜드 보드의 손글씨 "냅다체"는 아직 웹폰트가 없으므로 **로고와 키 비주얼의 "냅다" 글자는 항상 이미지(워드마크)로 쓰고, 폰트로 흉내 내지 않는다.**

본문과 UI는 **Pretendard**다. 한글 UI에서 가장 널리 쓰이고 굵기 단계가 넓어 손글씨 디스플레이와 섞여도 정보가 흐트러지지 않는다. 디스플레이 서체는 화면 제목 한 줄, 온보딩 헤드라인, 완성 축하 문구처럼 **화면당 한 곳**에만 쓴다. 버튼, 입력, 목록, 안내 문구는 모두 Pretendard다.

스케일은 display(24·28·32px, Paperlogy 700, 자간 -0.6px), title(17·20·24px, Pretendard 700~800), body(14·16px, 400), label(12·14·16px, 600~700) 네 그룹이다. 본문 최소 크기는 14px, 입력 글자는 16px(모바일 확대 방지)이다. 한글 줄바꿈은 `word-break: keep-all`로 어절 단위를 지킨다.

## Spacing

기준 단위는 4px이고, 실제로는 8px 배수를 주로 쓴다. 모바일 화면(기준 폭 390px)의 좌우 여백은 20px, 섹션 사이는 24px, 카드 안쪽은 16px, 하단 고정 CTA 영역은 위 12px · 아래 24px(홈 인디케이터 여백 포함)이다. 버튼이 둘 이상 쌓이면 사이를 8px로 둔다.

## Rounded

radius는 6, 10, 14, 20, 28px와 `circular` 여섯 단계다. 브랜드 앱 아이콘과 응용 타일이 크게 둥근 사각이라 [src:1] UI도 각진 모서리를 쓰지 않는다. 쓰임새는 이렇게 나눈다.

- 6px: 작은 태그
- 10px: 입력창, 고스트 버튼
- 14px: 버튼(52px 높이)
- 20px: 카드, 영상 프레임
- 알약(circular): 배지
- 10px(radius-md): 입력칸, 하나 고르기 선택지

## Elevation & Depth

깊이는 **면의 명도 차와 1px 구분선**으로 만든다. 라이트 카드는 `{elevation.shadow-card}` 한 단계만 쓰고, 다크에서는 그림자 없이 한 단계 밝은 면으로 띄운다. 하단 고정 CTA 영역은 위쪽으로 아주 옅게 퍼지는 `{elevation.shadow-sheet}`로 본문과 나눈다. 라임 글로우, 스티커형 오프셋 그림자는 제품 화면에 쓰지 않는다.

## Shapes

브랜드 그래픽 요소는 브랜드 보드의 "Brand Pattern & Graphic Elements"에 정리돼 있다 [src:1].

- **번쩍 버스트(starburst)**: 라임 톱니 모양. 로고 뒤, 축하 헤드라인 뒤, 강조 숫자 뒤에 깐다.
- **클래퍼보드**: 영상 제작의 상징. 로고 조합, 빈 화면, 촬영 단계 아이콘에 쓴다.
- **효과선(세 줄 빗금)**: 마스코트나 로고 모서리에서 튀어나오는 강조선이다.
- **낙서 요소**: "ㅋㅋ", 번개, 반짝이(4각 별), 꼬인 낙서선, 마우스 커서, 픽셀 선글라스, 찢어진 종이 띠. B급 유머를 더하는 장식이다.

규칙은 세 가지다. 장식 그래픽은 **화면당 1~2개**만 쓴다. 정보를 담지 않으므로 `aria-hidden`으로 숨긴다. 버튼, 입력, 목록 같은 조작 영역 위에는 겹치지 않는다. UI 아이콘은 그래픽 요소와 섞지 않고 선 굵기가 일정한 라인 아이콘으로 통일한다(아래 Iconography). 라임 버스트는 큰 라임 면이므로 제품 화면에는 쓰지 않고 마케팅 면에만 쓴다.

## Iconography

UI 아이콘은 **Stratis UI Icons**(Figma Community, "Line Icons" 페이지, 840여 개) 한 세트만 쓴다 — https://www.figma.com/design/8FMHemIvaENHFsHNLrvKrZ . 다른 아이콘 세트(Lucide 등)를 섞지 않고, 직접 그린 아이콘도 쓰지 않는다.

- 원본 규격: 24×24 그리드, 2px 선, 둥근 끝. 코드에서는 `frontend/src/ui/icons`의 컴포넌트로 쓰고 색은 `currentColor`를 따른다.
- 새 아이콘이 필요하면 같은 Figma 파일에서 이름으로 찾아 SVG를 내보내고, `icons/index.tsx`의 `ICONS`에 Stratis 이름·노드 ID 주석과 함께 추가한다.
- 쓰는 크기: 본문·버튼 18~20px, 헤더·내비게이션 24~26px, 배지 안 11~12px. Stratis 체크(`check-01`)는 그림이 24px 칸 가운데 10px 정도라, 원 안에 넣을 때 다른 아이콘보다 크게(18~24px) 잡는다.
- 꽉 찬 모양이 필요한 곳(재생, 크레딧 번개)은 선 아이콘에 `fill="currentColor"`를 더해 채운다.
- 지금 쓰는 매핑: 이전·전체 보기 `chevron-left/right`, 이어하기 `arrow-right`, 내려받기 `download-02`, 올리기 `upload-03`, 만들기 `plus-02`, 지우기 `x-02`, 선택 `check-01`, 안내 `information-circle-contained`, 미정 `clock-01`, 제품 `package-01`, 이미지 `image-01`, 재생 `play-03`, 일시정지 `pause-03`, 크레딧 `lightning-filled`, 알림 `bell-02`, 도움말·문의 `help-circle-contained`, 이용약관 `file-02`, 개인정보 `shield-check`, AI 라벨 `stars`, 로그아웃 `logout-02`, 좋아요 `heart`, 공유 `share`, 신고 `alert-triangle`(깃발 아이콘이 없어 경고 삼각형), 소리 켜짐 `volume-05`, 소리 꺼짐 `volume-02`.
- **직접 그린 아이콘은 쓰지 않는다.** Stratis에 딱 맞는 모양이 없으면 라이브러리에서 가장 가까운 아이콘을 고른다. 예: 하단 내비게이션 "내 영상"은 영상 모양 대신 **보관함**으로 읽히게 기본 폴더(`folder`)를 쓴다. 필름 띠(`media-strip-01`)·캠코더(`video-on`)는 "내가 만든 영상 모음"으로 읽히지 않았고, 종이가 꽂힌 폴더(`folder-open-03`)는 단순한 폴더보다 복잡해 보여 쓰지 않는다. 또 재생 버튼 화면(`youtube`)은 채우면 유튜브 로고와 같아 보여 쓰지 않는다.

## Mascot

**냅다곰**은 선글라스를 쓴 갈색 곰이다. 캐릭터 시트가 성격을 "엉뚱함, 장난기, 과감함"으로 정하고, 4방향 모습, 표정 6개(기본·신남·놀람·쿨함·슬픔·화남), 포즈 5개(서 있기·환호·달리기·클래퍼보드 들기·눕기)를 싣는다 [src:3]. 털색 #E5B887은 캐릭터 전용이라 UI 색으로 쓰지 않는다.

UI에서는 **감정이 있는 순간에만, 한 화면에 한 마리** 쓴다. 입력·선택처럼 집중해야 하는 화면에는 넣지 않는다.

| 순간 | 포즈 | 화면 |
| --- | --- | --- |
| 첫 만들기 권유 | 클래퍼보드 들기 | 빈 홈 |
| 생성 대기 | 눕기 + "냅다곰이 머리 굴리는 중…" | 시나리오 생성 중 |
| 결과 공개 | 놀람(!!) 표정(상반신) | 영상 확인 |
| 완성 | 신남 표정(상반신, 손 들기) | 썸네일·내려받기 |

제목 옆에 붙는 곰(영상 확인·썸네일)은 하반신이 잘린 표정 컷을 써서 제목 줄 높이에 맞추고, 본문 가운데에 서는 곰(빈 홈)이나 카드 안 곰(생성 대기)만 전신 포즈를 쓴다. 이미지는 캐릭터 시트에서 잘라 배경을 지운 투명 PNG다(`frontend/src/assets/brand/mascot-*.png`). 장식이므로 `alt=""`·`aria-hidden`으로 숨기고, 64px보다 작게 줄이지 않는다. 버튼·입력 위에 겹치지 않는다.

## Voice & Copy

말투는 "-해요"체의 짧은 문장이다. B급 감성은 말장난과 리듬으로 내되 정보를 가리지 않는다. 브랜드 문구 "냅다 만들어보세요", "이제는 냅다"처럼 **"냅다"를 동사 앞 부사로 쓰는 말장난**이 핵심 장치다(예: "냅다 올리기", "냅다 받기"). 단, 버튼 라벨은 행동이 분명해야 하므로 "다음", "영상 만들기", "내려받기"처럼 동사를 앞세우고, 말장난은 제목·축하 문구·빈 화면에 둔다. 강조할 한 단어는 화면당 하나만 라임 하이라이트 마커(글자 아래 1/3 높이의 `{colors.brand-lime}` 띠)로 감싼다 [src:1]. 다크에서는 띠 대신 글자를 라임으로 쓴다.

## Components

모바일 웹(기준 폭 390px) 기준이다. 구현은 `frontend/src/ui/`에 이 문서의 토큰으로 직접 만든 컴포넌트다(외부 디자인 시스템 없음).

### app-header

높이 72px(위 여백 12px), 왼쪽에 국문+영문 조합 워드마크(기울어진 손글씨 "냅다" + 아래 "NAPDA", 높이 40px, 가로 약 66px, 라이트=검정·다크=흰색). 오른쪽 크레딧 배지와 세로 중심을 맞춘다. 본문과는 16px 띄운다. 홈·온보딩에만 있고, 화면에 보이는 유일한 로고다.

홈에서는 오른쪽 끝에 **크레딧 배지**(`credit-badge`)를 로고와 같은 세로 중심에 둔다. 32px 회색 알약(`{colors.surface-weak}`, 다크 `#171717`) 안에 20px 라임 원 + 검정 번개 아이콘, 그 옆에 잔액 숫자(14px Bold, 천 단위 쉼표). 라임은 이 작은 원에만 쓴다. 누르는 영역은 44px이고, 누르면 크레딧 화면(충전·내역)으로 간다. 스크린 리더에는 "남은 크레딧 120, 크레딧 보기"로 읽힌다. 잔액을 아직 못 불러왔으면 "—"를 보여 준다. 온보딩은 가입 전이라 배지를 두지 않는다. 크레딧 단위·차감 기준은 아직 미정이다(OQ-003).

홈 헤더 오른쪽은 **크레딧 · 프로필** 한 묶음(`header-actions`)이다. 둘 다 누르는 영역은 44px, 보이는 크기는 크레딧 32px 알약, 프로필 32px 원이다. 프로필 원의 보이는 오른쪽 끝을 화면 여백 20px 선에 맞춘다. 라임은 크레딧 원에만 쓰고 프로필에는 쓰지 않는다. 메뉴(☰)는 두지 않는다 — 이동은 하단 내비게이션이 맡는다.

- **프로필(`profile-avatar`)**: 32px 원, `{colors.surface-weak}` 면 + 1px `{colors.border-weak}` 안쪽 선. 사진이 있으면 원을 꽉 채우고, 없으면 닉네임 첫 글자(14px Bold, `{colors.text-secondary}`), 닉네임도 없으면 사람 아이콘을 보여 준다. 누르면 내 정보 화면으로 간다. 스크린 리더에는 "냅다사장 프로필"로 읽힌다. 내 정보 화면의 계정 머리에서는 같은 원을 56px(`profile-avatar-lg`, 첫 글자 22px)로 쓴다.

### safe-area

화면 위아래의 기기 안전 영역을 지킨다. `viewport-fit=cover`로 화면을 끝까지 쓰고, 상단 헤더는 `env(safe-area-inset-top)`만큼, 하단 고정 영역(행동 버튼, 하단 내비게이션)은 `--safe-bottom`(= `env(safe-area-inset-bottom)`)만큼 띄운다. Storybook 기기 틀(390×844, 아이폰 14)은 `--safe-bottom: 34px`과 홈 인디케이터 막대를 그려 실제 하단 여백을 미리 보여 준다.

### bottom-nav

앱의 주요 이동 막대. 탭 최상위 화면(홈, 내 영상, 커뮤니티, 프로필)의 맨 아래에 고정한다. 만들기 흐름 1~8단계와 온보딩에는 두지 않는다 — 그 화면들은 하단을 "다음" 같은 행동 버튼에 쓰고, 뒤로 가기로 빠져나간다.

- 네 칸을 똑같이 나눈 그리드: **홈**(집) · **내 영상**(폴더) · **커뮤니티**(사람들) · **프로필**(사람). **아이콘만** 보인다(Stratis 24px, 선 굵기 2 — 홈 `home-03`(지붕만 있는 단순한 집), 내 영상 `folder`(폴더), 커뮤니티 `users-profiles-01`, 프로필 `user-profile-01`). 이름은 화면에 쓰지 않고 각 버튼의 스크린 리더 이름(`aria-label`)으로만 둔다 — 네 개뿐이고 모두 흔한 모양이라 아이콘만으로 알아본다.
- 크기 기준: iOS 탭 바(막대 49pt + 홈 인디케이터 34pt = 83pt), Material 내비게이션 바(누르는 영역 48dp 이상). 냅다는 **위 4px + 아이콘 줄 56px + 아래 안전 영역**(`--safe-bottom`, 아이폰 34px, 안전 영역이 없는 기기도 최소 12px). 한 칸 누르는 영역은 약 93×56px.
- 위 1px `{colors.border-weak}` 선, 면 `{colors.bg-base}`.
- 현재 탭: 배경 표시 없이 **아이콘을 글자색으로 꽉 채운다**(라이트 검정 `{colors.text-primary}`, 다크 흰색). 라임은 쓰지 않는다 — 내비게이션은 매 화면에 늘 보이는 요소라 라임을 두면 화면마다 시선을 빼앗는다. 나머지 탭은 `{colors.text-tertiary}` 선만, 누르면 `{colors.text-primary}`로 진해진다. 채워도 사라지면 안 되는 위치는 '꽉 찬 모양 대 빈 선'으로 구분되고, 스크린 리더에는 `aria-current="page"`로 알린다.
- 하단 행동 버튼(예: 빈 홈의 "영상 만들기")이 있는 화면에서는 버튼을 내비게이션 바로 위에 한 덩어리로 붙여 고정한다(구분선은 내비게이션 위 한 줄만).
- 하단 내비게이션으로 들어온 "내 영상"은 탭 최상위라서 뒤로 버튼 없이 제목만 둔다(제목 왼쪽 여백 20px).
- 커뮤니티 탭은 탐색 그리드(아래 "커뮤니티"), 프로필 탭은 내 정보 화면(아래 "내 정보")이다. 영상 보기 화면은 탭 최상위가 아니라서 하단 내비게이션 없이 뒤로 버튼으로 나온다.

### flow-header

만들기 흐름 상단. 위 여백 16px, 44px 뒤로 버튼·제목 `{typography.title-17}`·오른쪽 "**N** / 8"(현재 단계만 굵게) 한 줄, 12px 아래 6px `progress-bar`, 아래 여백 16px. 진행 막대와 화면 제목 사이는 32px이다.

### event-banner

홈 맨 위, "영상 만들기" 위에 있는 회전 배너. **최대 3장**까지만 보여 주고, 더 들어오면 앞의 3장만 쓴다. 화면 좌우 여백 안쪽 폭 전체를 쓰고 비율은 21:10으로 고정한다(390px 화면에서 **350 × 167px**, 최대 440 × 210px). radius 14px. 배너와 "영상 만들기" 사이는 16px.

- **배너 제작 사이즈:** 1050 × 500px(@3x), PNG 또는 WebP. 오른쪽 아래 120 × 72px(@3x)는 뱃지가 덮으므로 글자·로고를 두지 않는다.
- **회전:** 4초마다 다음 장, 마지막 다음은 처음으로. 손으로 밀어 넘길 수 있다(scroll-snap).
- **뱃지:** 오른쪽 아래 "1 / 3" + 일시정지 아이콘. 검정 60% 면 + 흰 글자, 24px 알약(터치 영역 44px). 누르면 자동 넘김이 멈추고 다시 누르면 재개한다(자동으로 움직이는 콘텐츠는 멈출 수 있어야 한다).
- 마우스를 올리거나 키보드 포커스가 들어오면 잠시 멈추고, 움직임 줄이기 설정에서는 자동으로 넘기지 않는다.
- 이미지가 없으면 회색 점선 자리표시에 "배너 N · 1050×500"을 보여 준다. 배너가 하나면 뱃지를 숨기고, 없으면 영역 자체를 숨긴다.

### page-header

목록 같은 일반 페이지 상단. 흐름 헤더와 같은 여백에 뒤로 버튼·제목만 두고 진행 막대는 없다. "내 영상" 화면에 쓴다.

### tabs

밑줄 탭. 칸을 똑같이 나눈 48px 탭(내 영상은 두 칸, 커뮤니티는 네 칸), 아래 1px `{colors.border-weak}` 선. 고른 탭은 검정 굵은 글자 + 아래 4px `{colors.brand-lime}` 막대(작은 신호), 아닌 탭은 `{colors.text-tertiary}` 글자다. 필요하면 탭 이름 옆에 개수를 회색으로 붙인다. 좌우 화살표 키로 탭을 옮긴다(tablist/tab/tabpanel). 목록이 길어 탭을 늘 보여야 하는 화면(커뮤니티)은 탭 줄만 화면 위 고정 영역에 두고 내용은 본문에 둔다.

### 내 영상 (진행 중 · 완료)

진행 중·완료 프로젝트 전체 목록을 한 화면에 모은다. `page-header`("내 영상") 아래 `tabs`("진행 중 N" | "완료 N"), 그 아래 고른 탭의 `project-card`를 세로로 쌓는다. 완료 탭 맨 위에는 보관 기간 미정 배지를 둔다. 비어 있으면 누운 냅다곰과 한 줄 안내를 보여 준다.

### section-title + 전체 보기

홈 섹션 제목 줄. 제목·개수 오른쪽 끝에 44px 화살표(›) 버튼을 두고, 누르면 "내 영상"으로 간다. 진행 중 화살표는 "진행 중" 탭, 완료 화살표는 "완료" 탭이 열린 채로 들어간다. 버튼 이름은 "진행 중 전체 보기"처럼 읽힌다.

### carousel

홈의 진행 중·완료 프로젝트 카드 묶음. 카드 폭은 86%로 두어 다음 카드가 오른쪽에 걸쳐 보이게 하고(넘길 수 있다는 신호), 화면 좌우 여백까지 넓혀 가장자리로 흘러가 보이게 한다. 한 장씩 맞물려 멈추고(scroll-snap), 아래 점으로 위치를 보여 준다 — 현재 점은 18px 라임 알약, 나머지는 6px 회색 점. 가로 스크롤은 캐러셀 안에서만 일어나고 화면 자체는 옆으로 밀리지 않는다. 카드가 하나면 전체 폭을 쓰고 점을 숨긴다. 움직임 줄이기 설정에서는 부드러운 스크롤을 끈다.

### progress-bar

**칸이 끊어진 점선 게이지**다. 전체 단계 수만큼(만들기 흐름은 8칸) 6px 높이 칸을 4px 간격으로 늘어놓고, 지나온 칸은 `{colors.brand-lime}`, 남은 칸은 `{colors.surface-base}`로 칠한다. 칸 경계가 보여서 몇 단계째인지 칸 수로 셀 수 있다(와이어프레임의 8칸 막대와 같은 구조).

### timeline (훅/본편 길이)

같은 점선 게이지를 15칸(한 칸 ≈ 2초)으로 쓴다. 훅 구간은 라임, 본편 구간은 회색이고, "훅/본편" 라벨은 각 구간의 첫 칸 아래에 맞춘다. 비율은 기획 미정(OQ-002)이라 지금은 훅 6칸 : 본편 9칸 임시값이다. 옆에 "5/8"이나 "N / 8" 숫자를 함께 둬서 색만으로 진행을 전하지 않는다. 채움은 0.25초 ease-out으로 늘어난다.

### step-number

32px 원, `{colors.brand-lime}` 면 + 검정 숫자(800), 외곽선 없음. 원의 경계는 흰 바탕과 대비가 낮지만 안의 검정 숫자(18.2:1)가 위치를 분명히 보여 준다. 원과 원 사이를 2px 회색 세로선으로 이어 순서를 보여 준다(온보딩·촬영 가이드 공통).

### button-primary

화면의 1차 행동 하나. `{colors.inverse}` 면 + 흰 글자, 높이 52px, radius 14px, `{typography.label-16}`. hover는 `{colors.inverse-hover}`, 누르면 `scale(0.98)`. 비활성은 `{colors.surface-base}` 면 + `{colors.text-weak}` 글자 + 금지 커서로 바꿔 활성처럼 보이지 않게 한다.

### button-secondary

1.5px `{colors.border-strong}` 테두리의 흰 버튼. 카드 안 "이어하기", "다시 받기"와 하단의 2차 행동("그림으로 보기", "썸네일 내려받기")에 쓴다.

### button-ghost

배경 없는 44px 텍스트 버튼("시안 없이 바로 만들기", "가이드 다시 보기"). hover는 `{colors.surface-weak}`.

### text-input

높이 48px, radius 10px, 1px `{colors.border-base}`, 글자 16px. 라벨은 입력 위에 항상 보이고 옆에 "필수/선택"을 회색으로 단다. 포커스는 테두리 `{colors.border-strong}` + 1px 링. 오류는 `{colors.danger}` 테두리와 입력 아래 문구.

### choice-chip

하나만 고르는 선택지(라디오 그룹). 가로 폭을 똑같이 나눈 타일 그리드(최소 84px, 간격 8px)라 입력칸 폭과 줄이 맞는다. 타일은 입력칸과 같은 48px 높이·radius 10px·1px `{colors.border-base}`. 선택되면 훅 유형 카드와 같은 언어를 쓴다: 면 `{colors.selected-bg}`, 2px `{colors.selected-border}` 테두리(다크는 `{colors.dark-selected-bg}` + 라임 테두리), 글자 굵게, 글자 앞에 18px 라임 원 + 검정 체크. 선택 여부는 체크 모양으로도 보여 색에만 기대지 않는다. 좌우 화살표 키로 선택이 옮겨 간다.

### hook-card

훅 유형 선택 카드(여러 개 선택, 카드 전체가 체크박스). 흰 면, 1px `{colors.border-weak}`, radius 20px. 왼쪽 9:16 검정 영상 썸네일, 가운데 제목·설명, 오른쪽 26px 체크 원. 선택되면 면이 `{colors.selected-bg}`(라임 18% 틴트), 테두리가 2px `{colors.selected-border}`(다크는 면 `{colors.dark-selected-bg}` + 라임 테두리), 체크 원이 **라임 원 + 검정 체크**(`check-mark-selected`, 외곽선 없음)가 된다. 선택 여부는 체크 원의 모양 변화(빈 회색 원 → 라임 원 + 체크)가 색과 함께 보여 준다. 왼쪽 예시 썸네일은 회색 자리표시(`{colors.surface-weak}`)라 세 카드가 나란히 있어도 검정이 몰리지 않는다.

### project-card

홈·내 영상의 진행 중·완료 프로젝트. 흰 면, 1px `{colors.border-weak}`, radius 20px, `{elevation.shadow-card}`, 안쪽 16px. 위에 제품 썸네일(52px)·제품명·상태, 진행 중이면 가운데에 점선 게이지 + "5/8"을 둔다.

맨 아래는 **행동 타일**(`card-action`)이다. 카드 폭 전체를 쓰는 56px 높이의 `{colors.surface-weak}` 타일(radius 14px) 왼쪽에 무엇을 할지, 오른쪽에 원형 아이콘 버튼(`round-btn`)을 둔다. 버튼은 보이는 원 32px(흰 면 + 1px `{colors.border-weak}` 테두리 + 아주 옅은 그림자, 검정 아이콘 18px), 누르는 영역은 44px이다. 검정 원은 쓰지 않는다 — 위의 "영상 만들기"와 시선을 다투고 타일을 무겁게 만든다. 버튼에는 글자 없이 아이콘만 둔다.
- 진행 중: 왼쪽 "다음 단계 / 찍은 영상 올리기", 버튼 → (화살표)
- 완료: 왼쪽 "영상 + 썸네일", 버튼 ⤓ (내려받기)

아이콘 버튼의 접근 가능한 이름은 "실리콘 접이식 도마 이어하기", "원목 데스크 정리함 다시 받기"처럼 제품명 + 행동이다. hover는 `{colors.bg-weak}`, 누르면 `scale(0.92)`. 완료 카드에는 "완료" 배지를 따로 달지 않는다(섹션·탭 이름이 이미 알려 준다).

### badge-neutral · badge-brand · badge-pending

24px 알약, `{typography.label-12}`.
- neutral: `{colors.surface-base}` 면(장면 번호, 완성 표시)
- brand: 라임 면 + 검정 글자 + 1px 외곽선(선택된 훅 유형). 화면당 한두 개까지.
- pending: 종이 톤 면(`{colors.surface-weak}`) + 1px `{colors.border-weak}` + 시계 아이콘. 기획 미정(OQ·FR) 표시. 점선은 와이어프레임처럼 보여 쓰지 않는다. 출시 전에 모두 사라진다.

### 내 정보 (프로필 탭)

계정·크레딧·설정을 한 화면에서 확인하는 곳. 영상 관리는 내 영상 탭이 맡으므로 여기서는 요약만 보여 준다. 탭 최상위 화면이라 `page-header`("내 정보")에 뒤로 버튼이 없고 하단 내비게이션이 붙는다. 위에서 아래로 여섯 묶음이다.

1. **계정 머리** — 56px 프로필 원 + 이름(20px Bold) + 이메일(14px tertiary, 길면 말줄임) + "구글 계정" 배지. 구글 계정에서 온 값이라 이 화면에서 고치지 않는다. 이름이 없으면 이메일 앞부분을 쓴다.
2. **크레딧**(`credit-balance-card`) — 아래 credit-balance-card. 영상은 하루 횟수 제한 없이 크레딧으로 만든다.
3. **내 영상** — `stat-tile` 두 칸("진행 중 N" · "완료 N"). 누르면 내 영상의 해당 탭으로 간다. 아래 한 줄 "만든 날부터 7일 동안 보관돼요."(보관 기간 값이 없으면 미정 배지).
4. **설정** — "화면 모드"는 `choice-chip` 세 칸(기기 설정 · 라이트 · 다크)이고 고르는 즉시 적용된다. "기기 설정"은 기기의 라이트/다크 설정을 따라가고 기기 설정이 바뀌면 바로 따라 바뀐다. "영상 완성 알림"은 방식이 미정이라 읽기만 하는 줄 + 미정 배지.
5. **도움말·약관** — `list-row` 네 줄: 도움말·문의, 이용약관, 개인정보 처리방침, AI 라벨 안내.
6. **계정** — "로그아웃" 줄(화살표 없음)과 맨 아래 가운데 조용한 글자 버튼 "탈퇴하기"(14px tertiary, 밑줄, 누르는 영역 44px). 둘 다 `confirm-sheet`를 한 번 거친다.

상태는 다섯 가지다. **불러오는 중**: 계정 머리와 크레딧 카드 자리에만 스켈레톤이 반짝이고(자리 크기를 미리 잡아 화면이 밀리지 않는다) 숫자 타일은 "–", 설정·약관 줄은 바로 보인다. **첫 영상 무료 남음**: 크레딧 카드 아래에 무료 1회 줄이 붙는다. **크레딧 없음**: 잔액 0 + "충전하면 바로 만들 수 있어요". **로그인 전**(세션 만료): 누운 냅다곰 + "로그인이 풀렸어요" + 하단 고정 로그인 버튼, 아래에는 도움말·약관만 남긴다. 로그인 버튼 자리에는 실제 앱에서 Google 공식 로그인 버튼을 넣는다(직접 그린 구글 로고 버튼을 쓰지 않는다). **확인 시트 열림**: 아래 confirm-sheet.

### credit-balance-card

크레딧 잔액을 보여 주고 충전으로 보내는 카드(흰 면, 1px `{colors.border-weak}`, radius 20px, `{elevation.shadow-card}`). **영상을 만드는 횟수에는 하루 제한이 없다** — 온보딩 때 주는 무료 제작 1회를 빼면, 크레딧을 충전한 만큼 계속 만든다.

- 위: "내 크레딧"(14px tertiary). 그 아래 왼쪽에 24px 라임 번개 원 + 잔액(Pretendard 28px ExtraBold, 천 단위 쉼표), 오른쪽에 1차 버튼 "충전하기"(44px). 잔액을 아직 못 불러왔으면 "—".
- 한 줄 안내: "횟수 제한 없이, 충전한 만큼 만들 수 있어요." 잔액이 0이고 무료 제작도 없으면 "크레딧이 없어요. 충전하면 바로 만들 수 있어요."
- **무료 제작 줄**: 온보딩 무료 1회가 남아 있을 때만 1px 구분선 아래에 `[무료]` 브랜드 배지 + "첫 영상 한 편은 무료예요" + 오른쪽 "1회 남음". 쓰고 나면 줄을 숨긴다.
- 영상 한 편에 드는 크레딧(단가)은 아직 정해지지 않아(OQ-003) 이 카드에는 "약 N편 만들 수 있어요" 같은 환산을 넣지 않는다. 충전 화면의 묶음 카드는 단가를 받으면 "영상 약 N편"을 함께 보여 준다.

### stat-tile

작은 이름 + 큰 숫자(Pretendard 24px Bold — 숫자는 포인트 서체 대신 본문 서체로 둔다) + 오른쪽 화살표로 된 누르는 타일. `{colors.surface-weak}` 면, radius 14px, 높이 76px 이상, 두 칸 그리드(간격 8px). 숫자를 아직 못 불러왔으면 "–". 스크린 리더에는 "완료 3개 보기"로 읽힌다.

### list-row

설정·메뉴 한 줄. 왼쪽 20px 아이콘(`{colors.text-secondary}`) · 이름(16px Medium) · (선택) 아래 설명 13px · 오른쪽 값이나 배지 · 다른 화면으로 가는 줄이면 20px 화살표(`{colors.text-weak}`). 높이 52px 이상, 누르는 면은 화면 좌우 끝까지 넓힌다. 카드나 구분선으로 감싸지 않고 화면에 바로 놓으며, 묶음은 13px tertiary 제목(`list-group`)과 24px 간격으로 나눈다. hover `{colors.bg-weak}`, 누르면 `{colors.surface-weak}`. 누를 수 없는 줄(미정 항목)은 화살표 없이 읽기만 하는 줄로 둔다. 로그아웃처럼 바로 실행되는 줄에도 화살표를 붙이지 않는다.

### confirm-sheet

로그아웃·탈퇴처럼 한 번 더 물어봐야 하는 행동에 쓰는, 아래에서 올라오는 확인 시트.

- 면 `{colors.bg-base}`(다크는 `{colors.dark-surface-weak}` + 위 1px 선), 위 모서리 radius 28px, 안쪽 28px 20px, 아래는 안전 영역 + 12px. 뒤에는 검정 50% 막. 250ms로 올라오고 움직임 줄이기 설정에서는 바로 나타난다.
- 내용: 제목(20px Bold, 질문형 "로그아웃할까요?") + 한 줄 설명(15px tertiary, 결과를 말한다) + 버튼 두 개를 세로로.
- 버튼 순서: 보통은 실행(1차 검정) → 취소(ghost). **되돌릴 수 없는 행동**(탈퇴)은 그만두는 쪽("계속 쓸게요")을 1차 버튼으로 올리고 실행("탈퇴하기")을 ghost로 내린다. 빨강은 쓰지 않는다(빨강은 입력 오류 전용).
- 접근성: `role="alertdialog"` + 제목·설명 연결. 열리면 포커스가 시트로 옮겨 가고 Tab은 시트 안에서만 돌며, Esc·바깥 누르기·취소로 닫힌다. 닫히면 시트를 연 버튼으로 포커스가 돌아간다. 떠 있는 동안 뒤 화면은 `inert`로 잠근다.

### 커뮤니티 (탐색 그리드)

다른 사람들이 냅다로 만든 영상을 둘러보는 화면. 인스타그램 탐색 탭처럼 썸네일 그리드에서 고르고, 누르면 영상 보기로 간다. 탭 최상위 화면이라 `page-header`("커뮤니티")에 뒤로 버튼이 없고 하단 내비게이션이 붙는다.

- **순서는 추천 알고리즘이 정한다.** 인기·최신 같은 정렬과 카테고리 거르기는 두지 않는다. 사용자가 고르는 것은 훅 유형 하나뿐이다.
- **유형 탭**(`tabs`): 제목 바로 아래 "전체 | A 유형 | B 유형 | C 유형" 네 칸 밑줄 탭. 내 영상의 탭과 같은 부품이고, 스크롤해도 제목과 함께 화면 위에 고정된다. 탭을 바꾸면 목록을 맨 위부터 다시 보여 준다.
- **탭 설명 한 줄**: 탭 바로 아래 14px tertiary 한 줄. 전체는 "좋아할 만한 영상을 골라 보여 드려요."(추천 기준이라는 안내), 유형 탭은 그 유형이 어떤 훅인지("살짝 흘려요. 눈치 빠르면 알아채요.") 알려 준다 — 만들기 2단계(유형 선택)와 같은 문구라, 구경하면서 유형을 익히게 된다. 그리드와 함께 스크롤된다.
- **그리드**: 9:16 썸네일(`video-tile`) 3칸, 간격 2px, 화면 좌우 끝까지. 영상이 모두 세로라 크기를 섞지 않는다. 썸네일은 8단계에서 만든 썸네일을 쓰고, 그리드에서는 영상을 자동 재생하지 않는다(데이터·배터리).
- **더 불러오기**: 맨 아래에 닿으면 다음 영상을 불러오고, 불러오는 동안 스켈레톤 타일 한 줄을 붙인다.
- **상태**: 불러오는 중(스켈레톤 타일 9칸) · 빈 상태(클래퍼보드 냅다곰 + "아직 올라온 영상이 없어요" + 하단 "영상 만들기") · 고른 유형에 영상 없음(누운 냅다곰 + "C 유형은 아직 없어요" + "전체 보기") · 불러오기 실패(놀란 냅다곰 + "다시 시도").

### video-tile

탐색 그리드의 영상 한 칸. 9:16, 모서리 각짐(그리드가 한 장의 판으로 보이게), 왼쪽 아래에 채운 하트 + 좋아요 수(12px Bold 흰색, 아래쪽 검정 그라데이션 위). 10,000 이상은 "1.2만"으로 줄인다. 썸네일 이미지가 없으면 검정 바탕에 썸네일 글자를 디스플레이체로 보여 준다. 스크린 리더에는 "실리콘 접이식 도마, 도마왕, 좋아요 1,284개. 영상 보기"로 읽힌다. 포커스 링은 어떤 썸네일 위에서도 보이게 검정 선 + 안쪽 흰 선 두 겹.

### 영상 보기 (커뮤니티)

탐색 그리드에서 고른 영상을 한 편씩 크게 보는 화면. 위아래로 넘기면 같은 목록의 다음 영상이 한 편씩 맞물려 멈춘다(scroll-snap). **영상 화면이라 앱의 라이트/다크 설정과 상관없이 늘 검정 바탕**을 쓴다.

- **위 줄**(56px): 뒤로 · "3 / 12" · 신고(경고 삼각형). 신고는 `confirm-sheet`("이 영상을 신고할까요?")를 거치고, 접수되면 위쪽에 "신고를 접수했어요" 알림이 잠깐 뜬다.
- **영상**: 9:16을 자르지 않고 radius 20px 카드로 보여 준다. 왼쪽 위에 **"AI 연출 포함" 라벨을 항상** 붙인다(검정 60% 알약 + 별 아이콘). 지금 보는 영상만 소리를 끈 채 자동 재생하고, 영상을 누르면 일시정지(가운데 64px 재생 원), 넘어가면 멈춘다.
- **오른쪽 아래 버튼**(44px 검정 55% 원): 좋아요(하트 + 수) · 공유 · 소리 켜기/끄기. **좋아요를 누르면 하트가 라임으로 찬다** — 빨강은 쓰지 않는다.
- **아래 정보**: 32px 프로필 원 + 닉네임(15px Bold) + 제품명(13px tertiary) + 훅 유형 브랜드 배지("B 유형"). 그 아래 화면 폭 1차 버튼 **"이 훅으로 만들기"** — 같은 훅 유형이 선택된 채로 만들기 흐름을 시작한다. 영상이나 시나리오를 복사하지 않는다(README의 "기존 인기 영상 재가공 제외").
- 접근성: 지금 보는 영상만 조작·읽기 대상이고 나머지는 `inert`. 키보드는 Page Up/Down·화살표로 넘긴다. 영상마다 "12개 중 3번째. 제품명, 닉네임"으로 읽힌다.

### switch

켜고 끄는 스위치 한 줄: 왼쪽에 이름(16px SemiBold)·설명(13px tertiary), 오른쪽에 52×32px 스위치(누르는 영역 44px). 꺼짐은 `{colors.surface-strong}` 면 + 흰 손잡이, 켜짐은 **라임 면 + 검정 손잡이**(선택 체크와 같은 짝, 라이트에서는 검정 외곽선). 색뿐 아니라 손잡이 위치로도 구분된다. `role="switch"`.

지금 쓰는 곳은 8단계(썸네일·내려받기)의 **"커뮤니티에도 올리기"**다. 기본은 꺼짐(비공개). 켤 때만 `confirm-sheet`("커뮤니티에 올릴까요?")로 한 번 동의를 받고, 끌 때는 바로 내린다. 켜지면 설명이 "지금 누구나 볼 수 있어요. 끄면 바로 내려가요."로 바뀐다.

### time-estimate

영상을 만들기 직전(6/8 "영상 올리기")에 **얼마나 기다려야 하는지** 미리 보여 주는 카드. 파일 카드 바로 아래에 둔다.

- 머리: 44px 라임 틴트 타일(`{colors.tint}`) 안에 시계 아이콘 + "얼마나 걸려요?"(14px, tertiary) + 총 시간 "약 2~3분"(디스플레이체 24px). 숫자 하나가 먼저 읽히게 크게 둔다.
- 아래: 1px 구분선 뒤 단계별 시간 목록 — 번호 원(20px 종이 톤) · 단계 이름 · 오른쪽 정렬 굵은 시간(tabular-nums). 지금 단계는 "훅 영상 뽑기 1~2분 / 본편에 이어 붙이기 30초 / 자막·마무리 30초"(예시).
- 맨 아래 한 줄: "만드는 동안 다른 화면 봐도 괜찮아요." + 미정 배지.
- 영상을 고르면 하단 버튼 바로 위 요약 줄에도 "약 2~3분이면 나와요"를 띄워, 누르는 순간 시간을 다시 확인하게 한다(가까이 둔 정보는 같은 결정으로 읽힌다).
- 시간 값은 서버가 알려 주는 값으로 바꿀 자리다(`estimate` prop). 실제 소요 시간과 완료 알림 방식은 아직 정해지지 않았다.

### note

회색 안내 상자. `{colors.surface-weak}` 면, radius 14px, 정보 아이콘 + 제목 + 보조 내용. 경고·정보 배너를 색으로 나누지 않고 이 하나로 쓴다.

### video-frame

9:16 세로 영상 프레임. 순검정 면, radius 20px. 재생 버튼은 64px 흰 원 + 검정 재생 아이콘.

### 썸네일·내려받기 (8단계)

**팀이 만든 썸네일 템플릿** 중 하나를 캐러셀에서 고르고, 글자를 넣어 내려받는 화면. 위에서 아래로 "시안 고르기 → 썸네일 글자 → 커뮤니티 올리기 스위치 → AI 라벨 안내" 순서이고, 하단에 "영상 내려받기"(1차)·"썸네일 내려받기"(2차)가 붙는다. 처음에는 첫 템플릿이 골라져 있어 아무것도 안 건드려도 내려받을 수 있다.

- **템플릿**: 앱이 그리지 않고 팀이 만든 이미지를 받은 순서대로 보여 준다(`ThumbnailTemplate` — id·이름·설명·미리보기 이미지). 개수는 정해 두지 않는다. 미리보기는 템플릿 이미지 그대로라 **입력한 글자가 미리보기에 반영되지 않는다** — 그래서 시안을 먼저 고르고 글자를 넣는 순서로 둔다.
- **썸네일 글자**: 한 줄 입력(`text-input`, 지우기 버튼), 한도 24자(임시값). 줄 나눔과 글자 배치는 템플릿이 정한다.

### thumbnail-picker

썸네일 시안 고르기. 9:16 미리보기를 **가로로 넘기는 캐러셀**에 놓고 하나만 고르는 라디오 그룹이다. 화면 좌우 끝까지 넓혀 시안 한 장이 콘텐츠 너비의 40%(390px 화면에서 약 140px), 간격 12px — 한 화면에 2장 반이 보여 세 번째 시안이 오른쪽에 걸쳐 보이는 것으로 넘길 수 있다는 걸 알린다. 넘기면 시안 단위로 딱 멈춘다(scroll-snap). 시안은 radius 14px, 아래에 이름(14px, 한 줄).

- **선택**: 사진 가장자리에 틈 없이 붙은 `{colors.selected-border}` 테두리 3px, 오른쪽 위 체크 원이 **라임 원 + 검정 체크**, 이름이 굵은 `{colors.text}`. 고르지 않은 시안의 체크 원은 흰 테두리의 빈 원이다. 테두리는 그림자로 그려 고를 때 레이아웃이 밀리지 않는다.
- **위치**: 오른쪽에 반쯤 걸친 시안을 누르면 다 보이게 끌어온다. 처음에 뒤쪽 시안이 골라져 있으면 그 시안이 보이게 가로로만 옮겨 둔다(화면 세로 위치는 그대로).
- **키보드·스크린 리더**: 좌우·위아래 화살표 키로 시안을 옮긴다. 이름 뒤에 설명("큼직, 굵은 글자를 가운데에 크게")을 읽는다.
- **이미지가 없을 때**: 옅은 라임 틴트 `{colors.tint}` + 이미지 아이콘의 빈 자리로 보인다(팀이 이미지를 넣기 전).

**템플릿 미리보기 이미지 규격 (디자이너 전달용)** — 비율 9:16 고정, 제작 사이즈 540 × 960px, WebP(권장) 또는 PNG. 화면에서는 약 140 × 249px로 작게 보이므로 글자는 크고 굵게 한다. 오른쪽 위 120 × 120px(제작 사이즈 기준)은 체크 원이 덮으니 중요한 요소를 두지 않는다. 모서리는 앱이 둥글게 자르므로 이미지는 각진 채로 넣는다. (`frontend/src/ui/components/thumbnailTemplates.ts`에도 같은 규격을 적어 두었다.)

### 크레딧 충전 흐름

들어오는 곳은 셋이다 — 상단 크레딧 배지, 내 정보의 "충전하기", **영상 올리기 단계에서 크레딧이 모자랄 때**. 충전이 끝나면 들어온 곳으로 돌아가고, 영상 올리기에서 왔으면 고른 영상을 그대로 둔 채 돌아가 "훅 붙여서 만들기"를 바로 누를 수 있다. 결제는 PG 결제창(모바일 웹)에 맡기고, 서버가 결제를 확인한 뒤에만 잔액을 올린다.

```
배지·내 정보 ───────────────────────┐
영상 올리기 "만들기" → 크레딧 부족 시트 ┤
                                    ▼
                          크레딧 충전 → PG 결제창 → 결제 확인 중 → 충전 완료 → 들어온 곳
                                    ▲          │ 실패: 충전 화면 + 안내 · 취소: 표시 없이 돌아옴
                                    └──────────┘
```

**영상 올리기 (버튼 위 한 줄)** — 영상을 고르면 무엇이 빠지는지 미리 보여 준다: "⚡ 12 크레딧 써요 · 보유 120". 온보딩 무료 1회가 남아 있으면 크레딧보다 먼저 쓰고 "[무료] 이번 영상은 무료예요"로 바꾼다. 단가를 모르면 "크레딧 미정" 배지를 둔다. 미리 막지 않고, 모자란 채로 "만들기"를 누르면 그때 시트를 띄운다.

**크레딧 부족 시트** — `confirm-sheet`에 숫자 세 칸(필요 · 보유 · **더 필요**)을 넣는다. 더 필요한 칸만 굵게 + 라임 번개. 버튼은 "충전하고 만들기"(1차) / "나중에". 닫으면 포커스가 "만들기" 버튼으로 돌아간다.

**크레딧 충전 화면** — `page-header`("크레딧 충전", 뒤로).
- 지금 잔액 카드(라임 번개 + Pretendard 28px). 모자라서 왔으면 "영상 만들려면 **7** 더 필요해요."
- **충전 묶음(`credit-package`)**: 세로로 쌓은 카드 중 하나만 고른다(라디오 그룹). 카드 높이 72px 이상, radius 20px. 왼쪽 체크 원, 가운데 "100 크레딧"(20px ExtraBold) + 아래 "영상 약 8편"(13px tertiary), 오른쪽 가격(17px Bold). 한 묶음에만 "많이 골라요" 브랜드 배지. 고르면 `select-card`처럼 라임 틴트 면 + 진한 라임 테두리 + 라임 체크. 라임 번개는 잔액·합계에만 쓰고 묶음 카드에는 넣지 않는다(라임이 화면에 몰리지 않게).
- 처음 골라 둘 묶음: 모자라서 왔으면 **모자란 만큼을 채우는 가장 작은 묶음**, 아니면 "많이 골라요" 묶음.
- 결제 전 안내 두 줄(크레딧은 영상 만들 때만 쓴다 · 실패하면 돌려준다) + "환불·유효기간 안내" 텍스트 버튼.
- 버튼 위 한 줄 "충전 후 ⚡ 220", 버튼은 고른 금액을 그대로 "12,900원 결제하기". 결제창을 여는 동안 "결제창 여는 중…"으로 잠가 두 번 결제되지 않게 한다.
- 결제 실패로 돌아오면 묶음 위에 안내 상자 "결제가 안 됐어요. 다른 수단으로 해 볼까요? · 돈은 빠져나가지 않았어요."(`role="alert"`). 사용자가 결제창을 닫은(취소) 경우는 실패가 아니므로 아무것도 띄우지 않는다.

**충전 결과** — 뒤로 버튼 없는 `page-header`. 결과가 바뀌는 걸 스크린 리더가 읽도록 `role="status"`.
- 결제 확인 중: 56px 라임 호가 도는 원 + "결제 확인 중이에요" + "잠깐이면 돼요. 창을 닫아도 충전은 그대로 돼요." 움직임 줄이기 설정이면 돌지 않고 천천히 깜빡인다.
- 충전 완료: 냅다곰 신남 컷 + "충전 완료!" + 잔액 변화 "~~5~~ → ⚡ **105**"(앞 숫자는 흐린 취소선, 뒤 숫자 32px ExtraBold). 버튼은 영상 올리기에서 왔으면 "영상 만들러 가기", 아니면 "확인".

**크레딧이 빠지는 규칙(제안)** — 글·콘티·가이드는 무료이고 영상을 만들 때만 쓴다. "만들기"를 누를 때 예상 크레딧만큼 묶어 두고, 완성되면 확정, 실패하면 자동으로 돌려준다.

### bottom-cta-bar

하단 고정 행동 영역. 위 1px 구분선, 안쪽 12px 20px, 아래는 max(24px, 안전 영역 + 8px)(아이폰에서 42px). 버튼은 최대 두 개를 세로로 쌓고, 결정 직전에 볼 정보("B 유형 1개 골랐어요", 크레딧 미정)는 버튼 바로 위 한 줄에 둔다.

## Do's and Don'ts

**Do** 1차 행동은 검정 버튼 하나로 둔다. 화면의 무게는 검정과 회색이 진다.

**Do** 라임은 게이지, 단계 번호, 선택 체크, 브랜드 배지, 화면당 강조 단어 하나처럼 작은 신호에 쓴다. 라이트에서 브랜드 배지는 검정 외곽선을 두르고(번호 원·선택 체크는 외곽선 없이)(게이지는 외곽선 없이 숫자를 함께 둔다), 위 글자는 검정이다.

**Do** 로고는 상단 헤더에 하나만 둔다.

**Do** 안내·완료·미정은 회색 면, 아이콘, 문구로 구분한다.

**Don't** 라임을 버튼 면, 카드 면, 배너, 영상 프레임처럼 넓게 칠하지 않는다. 흰 배경 위에 라임 글자를 쓰지 않는다(1.15:1). 외곽선 없는 라임 게이지는 반드시 숫자·라벨과 함께 둔다.

**Don't** 한 화면에 로고를 두 번 이상 보이게 하지 않는다. 본문에 로고 이미지·버스트 그래픽을 넣지 않는다.

**Don't** 주황, 파랑, 초록 같은 팔레트 밖 상태색을 쓰지 않는다. 오류의 빨강만 예외다.

**Don't** 로고를 재색칠하거나 기울기·비율을 바꾸지 않는다 [src:1].

## Responsive Behavior

모바일 웹이 기본이다. 기준 폭 390px에서 설계하고, 360px까지 줄어도 버튼 라벨과 카드 내용이 한 줄을 넘지 않게 한다. 콘텐츠 최대 폭은 480px이고, 그보다 넓은 화면에서는 가운데 정렬한 모바일 열 양옆에 `{colors.bg-weak}`를 채운다. 하단 고정 CTA는 `env(safe-area-inset-bottom)`만큼 아래 여백을 늘린다. 핀치 줌은 막지 않는다.

## Accessibility

- 대비 기준: 본문 4.5:1, 큰 글자·비텍스트 3:1. 이 문서의 모든 글자 조합은 계산값을 주석으로 달았다.
- 터치 영역 최소 44×44px. 아이콘 전용 버튼에는 접근 가능한 이름("이전", "재생")을 붙인다.
- 포커스 링을 지우지 않는다(`text-input`의 포커스 규칙을 모든 조작 요소에 쓴다).
- 색만으로 상태를 전하지 않는다. 선택된 카드는 테두리 굵기와 체크 아이콘을, 미정 배지는 시계 아이콘과 문구를 함께 쓴다.
- 모션은 `prefers-reduced-motion`을 존중한다. 버스트 회전, 마스코트 등장, 스티커 기울기 애니메이션은 이 설정에서 멈춘다.

## Known Gaps

- **냅다체 웹폰트 없음.** 브랜드 보드는 "커스텀 폰트 느낌의 손글씨 타입"이라고만 적고 [src:1] 폰트 파일은 없다. 포인트 서체는 페이퍼로지로 대신한다.
- **로고 벡터 원본 없음.** 헤더 워드마크는 `asset/logo/logo.png`(투명 배경 국문 "냅다" + 영문 "NAPDA" 조합형, 1536×1024)에서 여백을 잘라 검정본·흰색본을 만든 PNG다. 화면에서는 충분히 선명하지만, 더 큰 크기나 인쇄용으로는 SVG 원본이 필요하다.
- **로고 최소 크기와 보호 영역 미정.**
- **공식 색은 4가지뿐.** 중립 단계, 반전 면, 오류색은 이 문서가 산출한 값이라 브랜드 담당자 확인이 필요하다.
- **냅다곰 원본이 시트 한 장.** 화면의 냅다곰은 캐릭터 시트(1536×1024)에서 잘라 배경을 지운 이미지라 가로 160~230px 정도다. 더 크게 쓰려면 포즈별 투명 원본이 필요하다. 클래퍼보드 포즈의 검정 효과선은 다크 바탕에서 거의 보이지 않는다.
- **다크 테마는 이 문서가 정의한 것.** 브랜드 보드에는 다크 UI 규정이 없다.
- **내 정보 화면의 빈 자리.** 탈퇴 API가 없다(지금은 `GET /v1/auth/me`·`POST /v1/auth/logout`만 있다). 닉네임 수정도 없어 구글 이름을 그대로 쓴다. 영상 완성 알림 방식(푸시·이메일 등), 약관·개인정보 처리방침·AI 라벨 안내 문서 내용, 크레딧 잔액·충전 API는 아직 없다.
- **크레딧 충전은 화면만 있다.** 크레딧 단가·충전 묶음·가격(지금 화면의 30/100/300 크레딧 · 4,900/12,900/33,000원 · 영상 한 편 12크레딧은 예시 값), PG사, 환불(청약철회)·유효기간 정책(법무 확인 필요), 무료 1회를 온보딩에서만 쓸 수 있는지가 정해지지 않았다. 필요한 API — 잔액 조회, 묶음 목록, 결제 준비·확인(PG 웹훅), 크레딧 묶어 두기·확정·돌려주기, 내역 조회 — 도 없다. 크레딧 내역 화면은 아직 만들지 않았다.
- **과금 방식이 문서와 다르다.** 화면은 "하루 횟수 제한 없음 · 온보딩 무료 제작 1회 · 이후 크레딧 충전"을 기준으로 만든다. 그런데 API 명세(`contracts/api-spec.md` FR-006)와 백엔드는 아직 "결제 제외 무료 베타, 계정당 하루 영상 3회 제한(`DAILY_RENDER_LIMIT=3`)"이고, README도 결제를 제외 항목으로 적고 있다. 명세·백엔드를 새 방식에 맞춰야 한다.
- **커뮤니티는 화면만 있다.** 공개·내리기, 목록(이어 불러오기), 좋아요, 신고 API가 없다. 정해야 할 정책도 남아 있다 — 올린 영상의 보관 기간(지금은 7일 뒤 자동 삭제), 공개 닉네임(지금은 구글 이름뿐), 신고 처리 기준, 추천 알고리즘의 기준, 로그인 없이 볼 수 있는 범위. Storybook의 커뮤니티 영상은 예시용으로 만든 썸네일 12장과 4초짜리 예시 영상 1편(`frontend/src/assets/samples/community/`)이고 실제 사용자 영상이 아니다.
- **썸네일 템플릿은 화면 자리만 있다.** 템플릿은 팀이 만들어 넣기로 했지만, 템플릿 목록을 어디서 받을지(앱에 포함 · 서버 API)와 템플릿 파일 형식(글자가 들어갈 자리를 어떻게 정할지)이 정해지지 않았다. 내려받기 API(`GET /v1/projects/{id}/deliverables`)는 완성된 썸네일 한 장만 주므로, 고른 템플릿 id와 글자로 썸네일을 만드는 요청이 필요하다. 글자 수 한도 24자는 임시값이다. Storybook의 템플릿 4장(`frontend/src/assets/samples/thumbnail/`)은 자리를 확인하려고 만든 예시 이미지다.
- **보관 기간 표기가 화면마다 다르다.** API 명세는 7일 보관을 확정 정책으로 적어 내 정보에는 "7일 동안 보관돼요"로 쓰지만, 홈·내 영상에는 와이어프레임의 "보관 기간 미정 · OQ-012" 배지가 남아 있다. 하나로 맞춰야 한다.

## References

1. `asset/BrandConcept/brand.png` — 냅다 브랜드 보드. 로고(라임 버스트 + 손글씨 워드마크 + NAPDA + 클래퍼보드), 슬로건 "B급 감성 광고영상, 냅다 만들어보세요!", "아이디어만 있다면, 이제는 냅다.", 앱 아이콘, 로고 변형(흰 바탕·검정 바탕), Brand Color 4색(#D6FF3F, #000000, #E5E5E5, #FFFFFF), Typography "냅다체", 마스코트 냅다곰 다섯 포즈, Key Visual, Brand Application(영상 오버레이, 검정 타일, 슬로건 카드), Brand Pattern & Graphic Elements.
2. `asset/logo/logo.png` — 국문 "냅다" + 영문 "NAPDA" 조합 워드마크(검정, 투명 배경). 헤더 워드마크의 원본. 같은 폴더의 `logoeng.png`(기울어진 영문)과 `logoeng2.png`(정자형 영문)는 지금 화면에서 쓰지 않는다.
3. `asset/CharacterSheet/mascot.png` — 냅다곰 캐릭터 시트. 이름·종·성격(엉뚱함, 장난기, 과감함), 컬러 팔레트(#D6FF3F, #000000, #E5B887, #F7F7F7), 4방향 모습, 표정 6개, 포즈 5개, 디테일(얼굴·발바닥·클래퍼보드).
