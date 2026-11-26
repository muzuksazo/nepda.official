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
  bg-weak: oklch(0.976 0.003 106.4)               # #F7F7F5 배경 weak, 페이지 바닥(살짝 웜 그레이)
  surface-weak: oklch(0.955 0 0)                  # #F0F0F0 표면 weak, 자리표시 이미지
  surface-base: oklch(0.922 0 0)                  # #E5E5E5 표면 base (= brand-gray), 진행 막대 트랙
  surface-strong: oklch(0.870 0 0)                # #D4D4D4 표면 strong, 스켈레톤
  ## Background / Surface (다크)
  dark-bg-base: oklch(0.145 0 0)                  # #0A0A0A 배경 base
  dark-bg-weak: oklch(0 0 0)                      # #000000 배경 weak (= brand-black), 영상 플레이어 바탕
  dark-surface-weak: oklch(0.205 0 0)             # #171717 표면 weak, 카드
  dark-surface-base: oklch(0.256 0 0)             # #232323 표면 base, 입력창·secondary 버튼
  dark-surface-strong: oklch(0.321 0 0)           # #333333 표면 strong, 스켈레톤
  ## Text (라이트)
  text-primary: oklch(0.145 0 0)                  # #0A0A0A 텍스트 primary (19.8:1)
  text-secondary: oklch(0.321 0 0)                # #333333 텍스트 secondary (12.6:1)
  text-tertiary: oklch(0.475 0 0)                 # #5C5C5C 텍스트 tertiary, 보조 설명 (6.7:1)
  text-weak: oklch(0.566 0 0)                     # #767676 텍스트 weak, placeholder (흰 배경 4.5:1)
  ## Text (다크)
  dark-text-primary: oklch(1 0 0)                 # #FFFFFF 텍스트 primary
  dark-text-secondary: oklch(0.922 0 0)           # #E5E5E5 텍스트 secondary
  dark-text-tertiary: oklch(0.725 0 0)            # #A6A6A6 텍스트 tertiary (dark-surface-base 위 6.5:1)
  dark-text-weak: oklch(0.617 0 0)                # #858585 텍스트 weak, placeholder (dark-bg-base 위 5.4:1)
  ## Border
  border-weak: oklch(0.922 0 0)                   # #E5E5E5 라이트 보더 weak, 구분선
  border-base: oklch(0.855 0 0)                   # #CFCFCF 라이트 보더 base, 입력창
  border-strong: oklch(0.145 0 0)                 # #0A0A0A 라이트 보더 strong, 선택 카드·스티커 테두리
  dark-border-weak: oklch(0.269 0 0)              # #262626 다크 보더 weak
  dark-border-base: oklch(0.360 0 0)              # #3D3D3D 다크 보더 base
  ## Function — 오류 하나뿐. 주황·파랑·초록 같은 상태색은 쓰지 않는다 (주의·정보·완료는 회색 + 아이콘 + 문구)
  danger: oklch(0.560 0.203 28.2)                 # #D12A24 입력 오류 표시 전용 (흰 배경 5.2:1)
  dark-danger: oklch(0.710 0.183 26.6)            # #FF6B61 다크 오류 글자 (7.1:1)
  white: oklch(1 0 0)                             # #FFFFFF 반전 텍스트 고정 흰색
fonts:
  font-display: "\"NapdaChe\", \"Black Han Sans\", \"Pretendard Variable\", Pretendard, \"Apple SD Gothic Neo\", sans-serif"
  font-sans: "\"Pretendard Variable\", Pretendard, -apple-system, BlinkMacSystemFont, \"Apple SD Gothic Neo\", \"Malgun Gothic\", sans-serif"
typography:
  display-40:
    fontFamily: "{fonts.font-display}"
    fontSize: 40px
    fontWeight: 400
    lineHeight: 44px
    letterSpacing: -0.5px
  display-28:
    fontFamily: "{fonts.font-display}"
    fontSize: 28px
    fontWeight: 400
    lineHeight: 34px
    letterSpacing: -0.3px
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

브랜드 보드의 서체는 **"냅다체"** — "커스텀 폰트 느낌의 손글씨 타입"으로 소개된, 굵고 오른쪽으로 기운 붓글씨풍 한글과 둥근 대문자 라틴(ABC…, 0–9, 기호)이다 [src:1]. 아직 웹폰트 파일이 없으므로 `font-display`는 `NapdaChe`를 맨 앞에 두고, 폰트가 준비되기 전까지는 Google Fonts의 **Black Han Sans**(한글·라틴 지원, 굵은 디스플레이체)로 폴백한다. 이 대체 서체는 손글씨 질감이 없으므로 **로고와 키 비주얼의 "냅다" 글자는 항상 이미지(워드마크)로 쓰고, 폰트로 흉내 내지 않는다.**

본문과 UI는 **Pretendard**다. 한글 UI에서 가장 널리 쓰이고 굵기 단계가 넓어 손글씨 디스플레이와 섞여도 정보가 흐트러지지 않는다. 디스플레이 서체는 화면 제목 한 줄, 온보딩 헤드라인, 완성 축하 문구처럼 **화면당 한 곳**에만 쓴다. 버튼, 입력, 목록, 안내 문구는 모두 Pretendard다.

스케일은 display(28·40px, 냅다체), title(17·20·24px, Pretendard 700~800), body(14·16px, 400), label(12·14·16px, 600~700) 네 그룹이다. 본문 최소 크기는 14px, 입력 글자는 16px(모바일 확대 방지)이다. 한글 줄바꿈은 `word-break: keep-all`로 어절 단위를 지킨다.

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

UI 아이콘은 **Stratis UI Icons**(Figma Community, "Line Icons" 페이지, 840여 개) 한 세트만 쓴다 — https://www.figma.com/design/8FMHemIvaENHFsHNLrvKrZ . 다른 아이콘 세트(Lucide 등)를 섞지 않는다. Stratis에 없는 모양만 같은 규격으로 직접 그린다(아래 예외).

- 원본 규격: 24×24 그리드, 2px 선, 둥근 끝. 코드에서는 `frontend/src/ui/icons`의 컴포넌트로 쓰고 색은 `currentColor`를 따른다.
- 새 아이콘이 필요하면 같은 Figma 파일에서 이름으로 찾아 SVG를 내보내고, `icons/index.tsx`의 `ICONS`에 Stratis 이름·노드 ID 주석과 함께 추가한다.
- 쓰는 크기: 본문·버튼 18~20px, 헤더·내비게이션 24~26px, 배지 안 11~12px. Stratis 체크(`check-01`)는 그림이 24px 칸 가운데 10px 정도라, 원 안에 넣을 때 다른 아이콘보다 크게(18~24px) 잡는다.
- 꽉 찬 모양이 필요한 곳(재생, 크레딧 번개)은 선 아이콘에 `fill="currentColor"`를 더해 채운다.
- 지금 쓰는 매핑: 이전·전체 보기 `chevron-left/right`, 이어하기 `arrow-right`, 내려받기 `download-02`, 올리기 `upload-03`, 만들기 `plus-02`, 지우기 `x-02`, 선택 `check-01`, 안내 `information-circle-contained`, 미정 `clock-01`, 제품 `package-01`, 이미지 `image-01`, 재생 `play-03`, 일시정지 `pause-03`, 크레딧 `lightning-filled`.
- **예외 — Stratis에 없는 모양만 직접 그린다.** 같은 규격(24px 그리드, 2px 선, 둥근 끝·이음, 모서리 반경 2)으로 그리고 `icons/index.tsx`에 "자체 제작"이라고 적는다. 지금은 **슬레이트(`Slate`)** 하나 — 하단 내비게이션 "내 영상". 촬영·영상 제작을 바로 떠올리게 해서 필름 띠(`media-strip-01`)보다 "내 영상"으로 읽힌다.

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

- **프로필(`profile-avatar`)**: 32px 원, `{colors.surface-weak}` 면 + 1px `{colors.border-weak}` 안쪽 선. 사진이 있으면 원을 꽉 채우고, 없으면 닉네임 첫 글자(14px Bold, `{colors.text-secondary}`), 닉네임도 없으면 사람 아이콘을 보여 준다. 스크린 리더에는 "냅다사장 프로필"로 읽힌다.

### safe-area

화면 위아래의 기기 안전 영역을 지킨다. `viewport-fit=cover`로 화면을 끝까지 쓰고, 상단 헤더는 `env(safe-area-inset-top)`만큼, 하단 고정 영역(행동 버튼, 하단 내비게이션)은 `--safe-bottom`(= `env(safe-area-inset-bottom)`)만큼 띄운다. Storybook 기기 틀(390×844, 아이폰 14)은 `--safe-bottom: 34px`과 홈 인디케이터 막대를 그려 실제 하단 여백을 미리 보여 준다.

### bottom-nav

앱의 주요 이동 막대. 탭 최상위 화면(홈, 내 영상, 커뮤니티, 프로필)의 맨 아래에 고정한다. 만들기 흐름 1~8단계와 온보딩에는 두지 않는다 — 그 화면들은 하단을 "다음" 같은 행동 버튼에 쓰고, 뒤로 가기로 빠져나간다.

- 네 칸을 똑같이 나눈 그리드: **홈**(집) · **내 영상**(슬레이트) · **커뮤니티**(사람들) · **프로필**(사람). **아이콘만** 보인다(Stratis 24px, 선 굵기 2 — 홈 `home-03`(지붕만 있는 단순한 집), 내 영상 `slate`(슬레이트, 자체 제작), 커뮤니티 `users-profiles-01`, 프로필 `user-profile-01`). 이름은 화면에 쓰지 않고 각 버튼의 스크린 리더 이름(`aria-label`)으로만 둔다 — 네 개뿐이고 모두 흔한 모양이라 아이콘만으로 알아본다.
- 크기 기준: iOS 탭 바(막대 49pt + 홈 인디케이터 34pt = 83pt), Material 내비게이션 바(누르는 영역 48dp 이상). 냅다는 **위 4px + 아이콘 줄 56px + 아래 안전 영역**(`--safe-bottom`, 아이폰 34px, 안전 영역이 없는 기기도 최소 12px). 한 칸 누르는 영역은 약 93×56px.
- 위 1px `{colors.border-weak}` 선, 면 `{colors.bg-base}`.
- 현재 탭: 배경 표시 없이 **아이콘을 글자색으로 꽉 채운다**(라이트 검정 `{colors.text-primary}`, 다크 흰색). 라임은 쓰지 않는다 — 내비게이션은 매 화면에 늘 보이는 요소라 라임을 두면 화면마다 시선을 빼앗는다. 나머지 탭은 `{colors.text-tertiary}` 선만, 누르면 `{colors.text-primary}`로 진해진다. 채워도 사라지면 안 되는 안쪽 선(슬레이트 줄무늬)은 배경색으로 그어 면을 가른다. 위치는 '꽉 찬 모양 대 빈 선'으로 구분되고, 스크린 리더에는 `aria-current="page"`로 알린다.
- 하단 행동 버튼(예: 빈 홈의 "영상 만들기")이 있는 화면에서는 버튼을 내비게이션 바로 위에 한 덩어리로 붙여 고정한다(구분선은 내비게이션 위 한 줄만).
- 하단 내비게이션으로 들어온 "내 영상"은 탭 최상위라서 뒤로 버튼 없이 제목만 둔다(제목 왼쪽 여백 20px).
- 커뮤니티·프로필 화면은 아직 없다.

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

밑줄 탭. 칸을 반씩 나눈 48px 탭 두 개, 아래 1px `{colors.border-weak}` 선. 고른 탭은 검정 굵은 글자 + 아래 4px `{colors.brand-lime}` 막대(작은 신호), 아닌 탭은 `{colors.text-tertiary}` 글자다. 탭 이름 옆에 개수를 회색으로 붙인다. 좌우 화살표 키로 탭을 옮긴다(tablist/tab/tabpanel).

### 내 영상 (진행 중 · 완성)

진행 중·완성 프로젝트 전체 목록을 한 화면에 모은다. `page-header`("내 영상") 아래 `tabs`("진행 중 N" | "완성 N"), 그 아래 고른 탭의 `project-card`를 세로로 쌓는다. 완성 탭 맨 위에는 보관 기간 미정 배지를 둔다. 비어 있으면 누운 냅다곰과 한 줄 안내를 보여 준다.

### section-title + 전체 보기

홈 섹션 제목 줄. 제목·개수 오른쪽 끝에 44px 화살표(›) 버튼을 두고, 누르면 "내 영상"으로 간다. 진행 중 화살표는 "진행 중" 탭, 완성 화살표는 "완성" 탭이 열린 채로 들어간다. 버튼 이름은 "진행 중 전체 보기"처럼 읽힌다.

### carousel

홈의 진행 중·완성 프로젝트 카드 묶음. 카드 폭은 86%로 두어 다음 카드가 오른쪽에 걸쳐 보이게 하고(넘길 수 있다는 신호), 화면 좌우 여백까지 넓혀 가장자리로 흘러가 보이게 한다. 한 장씩 맞물려 멈추고(scroll-snap), 아래 점으로 위치를 보여 준다 — 현재 점은 18px 라임 알약, 나머지는 6px 회색 점. 가로 스크롤은 캐러셀 안에서만 일어나고 화면 자체는 옆으로 밀리지 않는다. 카드가 하나면 전체 폭을 쓰고 점을 숨긴다. 움직임 줄이기 설정에서는 부드러운 스크롤을 끈다.

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

홈·내 영상의 진행 중·완성 프로젝트. 흰 면, 1px `{colors.border-weak}`, radius 20px, `{elevation.shadow-card}`, 안쪽 16px. 위에 제품 썸네일(52px)·제품명·상태, 진행 중이면 가운데에 점선 게이지 + "5/8"을 둔다.

맨 아래는 **행동 타일**(`card-action`)이다. 카드 폭 전체를 쓰는 56px 높이의 `{colors.surface-weak}` 타일(radius 14px) 왼쪽에 무엇을 할지, 오른쪽에 원형 아이콘 버튼(`round-btn`)을 둔다. 버튼은 보이는 원 32px(흰 면 + 1px `{colors.border-weak}` 테두리 + 아주 옅은 그림자, 검정 아이콘 18px), 누르는 영역은 44px이다. 검정 원은 쓰지 않는다 — 위의 "영상 만들기"와 시선을 다투고 타일을 무겁게 만든다. 버튼에는 글자 없이 아이콘만 둔다.
- 진행 중: 왼쪽 "다음 단계 / 찍은 영상 올리기", 버튼 → (화살표)
- 완성: 왼쪽 "영상 + 썸네일", 버튼 ⤓ (내려받기)

아이콘 버튼의 접근 가능한 이름은 "실리콘 접이식 도마 이어하기", "원목 데스크 정리함 다시 받기"처럼 제품명 + 행동이다. hover는 `{colors.bg-weak}`, 누르면 `scale(0.92)`. 완성 카드에는 "완성" 배지를 따로 달지 않는다(섹션·탭 이름이 이미 알려 준다).

### badge-neutral · badge-brand · badge-pending

24px 알약, `{typography.label-12}`.
- neutral: `{colors.surface-base}` 면(장면 번호, 완성 표시)
- brand: 라임 면 + 검정 글자 + 1px 외곽선(선택된 훅 유형). 화면당 한두 개까지.
- pending: 투명 면 + 1px 회색 점선 + 시계 아이콘. 기획 미정(OQ·FR) 표시로, 와이어프레임의 점선 주석을 잇는다. 출시 전에 모두 사라진다.

### note

회색 안내 상자. `{colors.surface-weak}` 면, radius 14px, 정보 아이콘 + 제목 + 보조 내용. 경고·정보 배너를 색으로 나누지 않고 이 하나로 쓴다.

### video-frame

9:16 세로 영상 프레임. 순검정 면, radius 20px. 재생 버튼은 64px 흰 원 + 검정 재생 아이콘. 썸네일 미리보기 글자는 흰 디스플레이체 + 검은 띠.

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

- **냅다체 웹폰트 없음.** 브랜드 보드는 "커스텀 폰트 느낌의 손글씨 타입"이라고만 적고 [src:1] 폰트 파일은 없다. 지금은 Black Han Sans로 폴백한다.
- **로고 벡터 원본 없음.** 헤더 워드마크는 `asset/logo/logo.png`(투명 배경 국문 "냅다" + 영문 "NAPDA" 조합형, 1536×1024)에서 여백을 잘라 검정본·흰색본을 만든 PNG다. 화면에서는 충분히 선명하지만, 더 큰 크기나 인쇄용으로는 SVG 원본이 필요하다.
- **로고 최소 크기와 보호 영역 미정.**
- **공식 색은 4가지뿐.** 중립 단계, 반전 면, 오류색은 이 문서가 산출한 값이라 브랜드 담당자 확인이 필요하다.
- **냅다곰 원본이 시트 한 장.** 화면의 냅다곰은 캐릭터 시트(1536×1024)에서 잘라 배경을 지운 이미지라 가로 160~230px 정도다. 더 크게 쓰려면 포즈별 투명 원본이 필요하다. 클래퍼보드 포즈의 검정 효과선은 다크 바탕에서 거의 보이지 않는다.
- **다크 테마는 이 문서가 정의한 것.** 브랜드 보드에는 다크 UI 규정이 없다.

## References

1. `asset/BrandConcept/brand.png` — 냅다 브랜드 보드. 로고(라임 버스트 + 손글씨 워드마크 + NAPDA + 클래퍼보드), 슬로건 "B급 감성 광고영상, 냅다 만들어보세요!", "아이디어만 있다면, 이제는 냅다.", 앱 아이콘, 로고 변형(흰 바탕·검정 바탕), Brand Color 4색(#D6FF3F, #000000, #E5E5E5, #FFFFFF), Typography "냅다체", 마스코트 냅다곰 다섯 포즈, Key Visual, Brand Application(영상 오버레이, 검정 타일, 슬로건 카드), Brand Pattern & Graphic Elements.
2. `asset/logo/logo.png` — 국문 "냅다" + 영문 "NAPDA" 조합 워드마크(검정, 투명 배경). 헤더 워드마크의 원본. 같은 폴더의 `logoeng.png`(기울어진 영문)과 `logoeng2.png`(정자형 영문)는 지금 화면에서 쓰지 않는다.
3. `asset/CharacterSheet/mascot.png` — 냅다곰 캐릭터 시트. 이름·종·성격(엉뚱함, 장난기, 과감함), 컬러 팔레트(#D6FF3F, #000000, #E5B887, #F7F7F7), 4방향 모습, 표정 6개, 포즈 5개, 디테일(얼굴·발바닥·클래퍼보드).
