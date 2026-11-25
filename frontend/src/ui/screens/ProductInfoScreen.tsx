import { useState } from 'react';
import {
  Button,
  ChoiceChips,
  FilePicker,
  FlowHeader,
  MobileScreen,
  PendingBadge,
  ScreenTitle,
  TextField,
} from '../components';
import { PRODUCT_CATEGORIES } from './flowData';

export interface ProductInfo {
  name: string;
  intro: string;
  category: string | null;
  photo: File | null;
}

export interface ProductInfoScreenProps {
  initialValue?: Partial<ProductInfo>;
  onBack?: () => void;
  onNext?: (value: ProductInfo) => void;
}

/** 안1-2 제품 정보 (1/8) */
export function ProductInfoScreen({ initialValue, onBack, onNext }: ProductInfoScreenProps) {
  const [name, setName] = useState(initialValue?.name ?? '');
  const [intro, setIntro] = useState(initialValue?.intro ?? '');
  const [category, setCategory] = useState<string | null>(initialValue?.category ?? null);
  const [photo, setPhoto] = useState<File | null>(initialValue?.photo ?? null);

  return (
    <MobileScreen
      header={<FlowHeader title="제품 정보" step={1} onBack={onBack} />}
      footer={
        <Button
          label="다음"
          isBlock
          isDisabled={!name.trim()}
          onClick={() => onNext?.({ name, intro, category, photo })}
        />
      }
    >
      <ScreenTitle title="뭘 팔아 볼까요?">
        <PendingBadge>입력 항목 미정 · FR-001</PendingBadge>
      </ScreenTitle>

      <TextField label="제품 이름" placeholder="예: 접이식 실리콘 도마" value={name} onChange={setName} isRequired />
      <TextField
        label="한 줄 소개"
        placeholder="한 줄로 자랑해 주세요"
        value={intro}
        onChange={setIntro}
        isMultiline
        isOptional
      />
      <ChoiceChips label="카테고리" options={PRODUCT_CATEGORIES} value={category} onChange={setCategory} />
      <FilePicker
        label="제품 사진"
        isOptional
        variant="compact"
        accept="image/*"
        value={photo}
        onChange={setPhoto}
        placeholder="사진 고르기"
        description="있으면 시안이 더 찰떡이에요"
      />
    </MobileScreen>
  );
}
