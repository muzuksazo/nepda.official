import type { AGenreArchetype } from "./schema.js";

export interface ArchetypeDef {
  id: AGenreArchetype;
  labelKo: string;
  retentionPrinciple: string;
  defaultVisualStyle: string;
  antiClicheHint: string;
}

export const ARCHETYPE_CATALOG: ArchetypeDef[] = [
  {
    id: "extreme_physics_experiment",
    labelKo: "극한 3D 물리 실험 (Zack D. 스타일)",
    retentionPrinciple: "만약 극한 상황에 X를 넣으면? 예측 불가능한 물리 파괴·충돌 서스펜스",
    defaultVisualStyle: "blender_3d_physics",
    antiClicheHint: "직전 캠페인과 같은 실험 장치(예: 제트기/우산) 금지 — 매번 새로운 구조물·유체·압력 실험 발명",
  },
  {
    id: "courtroom_trial",
    labelKo: "클레이 법정 공방",
    retentionPrinciple: "일상 습관·추상 개념을 피고로 세운 과장 법정 스릴",
    defaultVisualStyle: "blender_clay_diorama",
    antiClicheHint: "제품명 대신 습관·물리 현상을 피고석에 세우고 판사 망치 순간 정적 인터럽트",
  },
  {
    id: "noir_interrogation",
    labelKo: "느와르 취조실",
    retentionPrinciple: "단 한 줄기 스포트라이트 아래 추궁당하는 미스터리 물체",
    defaultVisualStyle: "blender_clay_diorama",
    antiClicheHint: "속보 뉴스 클리셰 금지; 묵직한 취조 톤에서 0.25초 정적 후 반전",
  },
  {
    id: "romance_breakup",
    labelKo: "이별 멜로 드라마 패러디",
    retentionPrinciple: "진지한 멜로 대사와 황당한 물리 사건의 부조화 충돌",
    defaultVisualStyle: "flow_cinematic_parody",
    antiClicheHint: "사랑/이별 갈등 100% 몰입 직전 작은 물리 법칙이 갈등을 무력화",
  },
  {
    id: "historical_drama",
    labelKo: "사극 / 궁중 진상조사",
    retentionPrinciple: "고전 왕실 문체로 현대 물리 모순을 추적하는 부조화",
    defaultVisualStyle: "flow_cinematic_parody",
    antiClicheHint: "특정 웹소설/인물 IP 복제 금지, 순수 가상 궁정 설정만 사용",
  },
  {
    id: "sports_var",
    labelKo: "스포츠 VAR 심판 판독",
    retentionPrinciple: "0.1mm 슬로모션 판독으로 시선을 잠그는 긴장감",
    defaultVisualStyle: "blender_3d_physics",
    antiClicheHint: "호루라기 정적 + 슬로모션 확대 후 실제 제품 물성 컷으로 매치컷",
  },
  {
    id: "sci_fi_contact",
    labelKo: "외계 탐사선 조우",
    retentionPrinciple: "지구 밖 연구원이 미지 현상을 분석하다 깨닫는 스케일 반전",
    defaultVisualStyle: "blender_3d_cutaway",
    antiClicheHint: "외계어 UI 텍스트 생성 금지, 3D 계측 물리만 묘사",
  },
  {
    id: "audition_judge",
    labelKo: "오디션 심사위원 탈락 위기",
    retentionPrinciple: "차가운 3인 심사위원의 버저 직전 예측 불허 시연",
    defaultVisualStyle: "flow_cinematic_parody",
    antiClicheHint: "버저 정적 0.25s 직후 제품 실제 시연으로 연결",
  },
  {
    id: "horror_mystery",
    labelKo: "오컬트 미스터리 탐사",
    retentionPrinciple: "정체를 숨긴 미지 현상의 공포에서 허무할 만큼 평온한 착지",
    defaultVisualStyle: "blender_clay_diorama",
    antiClicheHint: "실제 제품 공간(욕실·현관 등) 배경 사용 금지, 순수 추상 공간만 사용",
  },
  {
    id: "mock_documentary",
    labelKo: "가짜 자연다큐멘터리",
    retentionPrinciple: "진지한 야생 다큐 내레이션과 기묘한 미니 모형의 괴리",
    defaultVisualStyle: "blender_clay_diorama",
    antiClicheHint: "뉴스 '속보입니다' 톤 금지, 차분한 BBC 다큐 관찰 톤 유지",
  },
  {
    id: "absurd_skit",
    labelKo: "무표정 엉뚱 상황극",
    retentionPrinciple: "일상 속 과장된 물리 사고가 1초 만에 엉뚱하게 해결",
    defaultVisualStyle: "blender_isometric_toy",
    antiClicheHint: "제품군 일상 소품 대신 전혀 다른 세계관 소품 사용",
  },
  {
    id: "brainrot_hypnosis",
    labelKo: "미완결 수렴 최면 루프",
    retentionPrinciple: "359도에서 딱 1mm 남기고 멈추려는 자이가르닉 수렴 긴장",
    defaultVisualStyle: "blender_isometric_toy",
    antiClicheHint: "트렌드 사물/노래 복제 금지 — 추상 기하 모노리스와 로열티프리 퍼커션만 사용",
  },
  {
    id: "deadpan_rhythmic_loop",
    labelKo: "무표정 리듬 반복",
    retentionPrinciple: "4박자 고정 비트에 맞춘 무표정 기하 캐릭터의 부조화 군무",
    defaultVisualStyle: "blender_clay_diorama",
    antiClicheHint: "기존 밈 곡명/댄스 복제 금지",
  },
  {
    id: "sensory_sync_loop",
    labelKo: "1프레임 촉각·음향 동기 루프",
    retentionPrinciple: "폴리머 클레이/유리 물리가 효과음과 1프레임 오차 없이 맞물리는 쾌감",
    defaultVisualStyle: "blender_isometric_toy",
    antiClicheHint: "돌연 0.25s 무음 정지 후 실물 컷 전환",
  },
];

const BY_ID = new Map<AGenreArchetype, ArchetypeDef>(ARCHETYPE_CATALOG.map((a) => [a.id, a]));

export function getArchetypeDef(id: AGenreArchetype): ArchetypeDef {
  return BY_ID.get(id) ?? ARCHETYPE_CATALOG[0];
}

/** previous_scenarios에 이미 쓰인 장르를 제외하고 count개의 비중복 A안 장르 원형을 고른다. */
export function pickUnusedArchetypes(previousScenarios: unknown[], count: number): ArchetypeDef[] {
  const used = new Set<string>();
  for (const prev of previousScenarios) {
    if (prev && typeof prev === "object") {
      const spec = (prev as Record<string, unknown>).ad_spec;
      if (spec && typeof spec === "object") {
        const g = (spec as Record<string, unknown>).a_genre_archetype;
        if (typeof g === "string") used.add(g);
      }
    }
  }
  const unused = ARCHETYPE_CATALOG.filter((a) => !used.has(a.id));
  const pool = unused.length >= count ? unused : [...unused, ...ARCHETYPE_CATALOG.filter((a) => used.has(a.id))];
  return pool.slice(0, count);
}
