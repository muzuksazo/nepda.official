import { useState } from 'react';
import { Mascot, MobileScreen, PageHeader, PendingBadge, ProjectCard, Stack, Tabs } from '../components';
import { brand } from '../brand';
import type { CompletedProject, InProgressProject } from './HomeScreen';

export type MyVideosTab = 'inProgress' | 'completed';

export interface MyVideosScreenProps {
  inProgress: InProgressProject[];
  completed: CompletedProject[];
  /** 홈에서 누른 화살표에 맞춰 처음 열 탭 */
  initialTab?: MyVideosTab;
  onBack?: () => void;
  onContinue?: (id: string) => void;
  onDownloadAgain?: (id: string) => void;
}

/** 안3-2 내 영상 — '진행 중'과 '완성'을 탭 하나로 묶은 전체 목록 */
export function MyVideosScreen({
  inProgress,
  completed,
  initialTab = 'inProgress',
  onBack,
  onContinue,
  onDownloadAgain,
}: MyVideosScreenProps) {
  const [tab, setTab] = useState<MyVideosTab>(initialTab);
  const empty = (text: string) => (
    <Stack gap={12} align="center" style={{ padding: '64px 0', textAlign: 'center' }}>
      <Mascot src={brand.mascot.lying} width={120} />
      <p className="n-muted">{text}</p>
    </Stack>
  );

  return (
    <MobileScreen header={<PageHeader title="내 영상" onBack={onBack} />}>
      <div style={{ marginTop: -16 }}>
        <Tabs<MyVideosTab>
          label="내 영상 구분"
          value={tab}
          onChange={setTab}
          items={[
            { value: 'inProgress', label: '진행 중', count: inProgress.length },
            { value: 'completed', label: '완성', count: completed.length },
          ]}
        >
          <div style={{ paddingTop: 20 }} className="n-stack">
            {tab === 'inProgress' ? (
              inProgress.length === 0 ? (
                empty('진행 중인 영상이 없어요.')
              ) : (
                <Stack gap={12}>
                  {inProgress.map((p) => (
                    <ProjectCard
                      key={p.id}
                      productName={p.productName}
                      status={p.status}
                      completedSteps={p.completedSteps}
                      nextStep={p.nextStep}
                      actionLabel="이어하기"
                      onAction={() => onContinue?.(p.id)}
                    />
                  ))}
                </Stack>
              )
            ) : completed.length === 0 ? (
              empty('아직 완성한 영상이 없어요.')
            ) : (
              <Stack gap={12}>
                <div>
                  <PendingBadge>보관 기간 미정 · OQ-012</PendingBadge>
                </div>
                {completed.map((p) => (
                  <ProjectCard
                    key={p.id}
                    productName={p.productName}
                    status={p.status}
                    actionLabel="다시 받기"
                    onAction={() => onDownloadAgain?.(p.id)}
                  />
                ))}
              </Stack>
            )}
          </div>
        </Tabs>
      </div>
    </MobileScreen>
  );
}
