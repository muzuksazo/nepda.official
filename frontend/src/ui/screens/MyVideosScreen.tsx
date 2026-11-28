import { useState } from 'react';
import { BottomNav, Button, ConfirmSheet, Mascot, MobileScreen, PageHeader, ProjectCard, Stack, Tabs, type NavTab } from '../components';
import { brand } from '../brand';
import type { CompletedProject, InProgressProject } from './HomeScreen';

export type MyVideosTab = 'inProgress' | 'completed';

export interface MyVideosScreenProps {
  inProgress: InProgressProject[];
  completed: CompletedProject[];
  /** 영상 보관 기간(일). 기본 7일 */
  retentionDays?: number;
  /** 홈에서 누른 화살표에 맞춰 처음 열 탭 */
  initialTab?: MyVideosTab;
  onBack?: () => void;
  onContinue?: (id: string) => void;
  onDownloadAgain?: (id: string) => void;
  /**
   * 고른 작업물 지우기. 넘기면 머리 오른쪽에 "선택"이 생긴다.
   * 확인 시트에서 "지우기"를 누른 뒤에만 불린다 — 되돌릴 수 없는 행동이다.
   */
  onDelete?: (ids: string[]) => void;
  /** 하단 내비게이션 이동. 넘기면 탭 최상위 화면으로 그린다(뒤로 버튼 없음 + 하단 바). */
  onNavigate?: (tab: NavTab) => void;
}

/**
 * 안3-2 내 영상 — '진행 중'과 '완료'를 탭 하나로 묶은 전체 목록.
 * "선택"을 누르면 카드를 여러 개 골라 한 번에 지울 수 있다(사진 앱의 선택 모드와 같은 흐름).
 */
export function MyVideosScreen({
  inProgress,
  completed,
  retentionDays = 7,
  initialTab = 'inProgress',
  onBack,
  onContinue,
  onDownloadAgain,
  onDelete,
  onNavigate,
}: MyVideosScreenProps) {
  const [tab, setTab] = useState<MyVideosTab>(initialTab);
  const [isSelecting, setIsSelecting] = useState(false);
  const [selected, setSelected] = useState<ReadonlySet<string>>(() => new Set());
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);

  const visible = tab === 'inProgress' ? inProgress : completed;
  const canSelect = Boolean(onDelete) && visible.length > 0;
  const selectedCount = selected.size;

  const stopSelecting = () => {
    setIsSelecting(false);
    setSelected(new Set());
  };
  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const changeTab = (next: MyVideosTab) => {
    // 탭을 바꾸면 고른 것을 비운다(보이지 않는 카드가 함께 지워지지 않게)
    setTab(next);
    setSelected(new Set());
  };

  const empty = (text: string) => (
    <Stack gap={12} align="center" style={{ padding: '64px 0', textAlign: 'center' }}>
      <Mascot src={brand.mascot.lying} size="md" />
      <p className="n-muted">{text}</p>
    </Stack>
  );

  const selectionProps = (id: string) => ({
    isSelecting,
    isSelected: selected.has(id),
    onToggleSelect: () => toggle(id),
  });

  return (
    <>
      <MobileScreen
        isInert={isConfirmOpen}
        header={
          <PageHeader
            title="내 영상"
            onBack={onBack}
            isTabRoot={Boolean(onNavigate)}
            endContent={
              isSelecting ? (
                <button type="button" className="n-header-text-btn" onClick={stopSelecting}>
                  완료
                </button>
              ) : canSelect ? (
                <button type="button" className="n-header-text-btn" onClick={() => setIsSelecting(true)}>
                  선택
                </button>
              ) : undefined
            }
          />
        }
        footer={
          isSelecting ? (
            <Button
              label={selectedCount > 0 ? `${selectedCount}개 지우기` : '지울 영상을 골라 주세요'}
              isBlock
              isDisabled={selectedCount === 0}
              onClick={() => setIsConfirmOpen(true)}
            />
          ) : undefined
        }
        bottomNav={onNavigate && !isSelecting ? <BottomNav active="myVideos" onNavigate={onNavigate} /> : undefined}
      >
        <div style={{ marginTop: -16 }}>
          <Tabs<MyVideosTab>
            label="내 영상 구분"
            value={tab}
            onChange={changeTab}
            items={[
              { value: 'inProgress', label: '진행 중', count: inProgress.length },
              { value: 'completed', label: '완료', count: completed.length },
            ]}
          >
            <div style={{ paddingTop: 20 }} className="n-stack">
              <p className="napda-visually-hidden" role="status">
                {isSelecting ? `${selectedCount}개 골랐어요` : ''}
              </p>
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
                        thumbnailUrl={p.thumbnailUrl}
                        actionLabel="이어하기"
                        onAction={() => onContinue?.(p.id)}
                        {...selectionProps(p.id)}
                      />
                    ))}
                  </Stack>
                )
              ) : completed.length === 0 ? (
                empty('아직 완료한 영상이 없어요.')
              ) : (
                <Stack gap={12}>
                  <p className="n-small n-muted">만든 날부터 {retentionDays}일 동안 보관돼요.</p>
                  {completed.map((p) => (
                    <ProjectCard
                      key={p.id}
                      productName={p.productName}
                      status={p.status}
                      thumbnailUrl={p.thumbnailUrl}
                      actionLabel="다시 받기"
                      onAction={() => onDownloadAgain?.(p.id)}
                      {...selectionProps(p.id)}
                    />
                  ))}
                </Stack>
              )}
            </div>
          </Tabs>
        </div>
      </MobileScreen>

      <ConfirmSheet
        isOpen={isConfirmOpen}
        isDestructive
        title={`영상 ${selectedCount}개를 지울까요?`}
        description={
          tab === 'completed'
            ? '지우면 되돌릴 수 없어요. 완성된 영상과 썸네일 파일도 함께 사라져요.'
            : '지우면 되돌릴 수 없어요. 지금까지 만든 내용도 함께 사라져요.'
        }
        confirmLabel="지우기"
        cancelLabel="그냥 둘게요"
        onConfirm={() => {
          onDelete?.([...selected]);
          setIsConfirmOpen(false);
          stopSelecting();
        }}
        onClose={() => setIsConfirmOpen(false)}
      />
    </>
  );
}
