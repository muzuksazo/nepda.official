# FLUX 3 Image Klein (공식 레포) Modal 배포 가이드

Black Forest Labs 공식 `black-forest-labs/flux-3-image-klein` 추론 코드와 가중치(`flux-3-image-klein` + Prompt Upsampler `flux-3-image-klein-pup`)를 Modal 서버리스 GPU에 배포하는 스크립트입니다.

## 왜 이 구성을 쓰나요?
- **공식 레포 + PUP 포함**: 공식 README 권장대로 9B VLM 프롬프트 업샘플러(`flux-3-image-klein-pup`)를 함께 로드해 텍스트→이미지, 최대 10장 레퍼런스 편집, 바운딩박스 레이아웃 제어를 최대 퀄리티로 냅니다.
- **L4(24GB) 대신 H100 기본값인 이유**: 공식 메모리 표 기준 `distilled --no-pup`만으로도 `FP8 = 26GB`, `BF16 = 31GB` VRAM이 필요하며, `PUP`(기본 35% 점유)까지 함께 띄우려면 `H100 (80GB)` 이상이 필요합니다.
  - **비용 절감 옵션**: Gemini 등 외부 VLM으로 캡션을 확장해 넘길 때는 `L40S (48GB)` + `--fp8` + `MODAL_FLUX3_ENABLE_PUP=false` 조합이 가능합니다.
- **라이선스 준수 기본값**: `FLUX Kommunity License v1.0` Section 2.e에 맞춰 API 요청 기본값이 `safety=True`이며, 반환 이미지에 AI 생성 EXIF 태그가 포함됩니다. (연 매출 `$5M` 미만 기업·개인은 상업 이용 무료 허용)

---

## 1. 사전 준비 (1회)

1. Hugging Face에서 공식 모델 페이지 방문 후 **Agree** 클릭(auto-gated 라이선스 동의):
   - https://huggingface.co/black-forest-labs/flux-3-image-klein
   - https://huggingface.co/black-forest-labs/flux-3-image-klein-pup
2. Hugging Face Read 토큰(`HF_TOKEN`) 발급: https://huggingface.co/settings/tokens
3. 로컬 Modal CLI 설치 및 로그인:
   ```bash
   pip install modal
   modal setup
   ```
4. Modal Secret 등록 (또는 아래 배포 스크립트 실행 시 환경변수로 전달):
   ```bash
   modal secret create flux3-klein-secrets \
     HF_TOKEN="hf_..." \
     MODAL_API_TOKEN="$(openssl rand -hex 24)"
   ```

---

## 2. 배포 실행

```bash
chmod +x infra/modal-flux3/deploy.sh
./infra/modal-flux3/deploy.sh
```

가중치가 이미 Modal Volume(`flux3-klein-weights`)에 올라가 있다면 다운로드 단계를 건너뛸 수 있습니다:
```bash
./infra/modal-flux3/deploy.sh --skip-download
```

### GPU / 양자화 조합 옵션 (환경변수로 전환)

| 목적 | 환경변수 조합 | 비고 |
| --- | --- | --- |
| **기본 권장 (최고 퀄리티 + PUP)** | `MODAL_FLUX3_GPU=H100 MODAL_FLUX3_QUANT=fp8 MODAL_FLUX3_ENABLE_PUP=true` | 16-step, 1장 ~3~5초 |
| **무손실 BF16 + PUP** | `MODAL_FLUX3_GPU=H100 MODAL_FLUX3_QUANT="" MODAL_FLUX3_ENABLE_PUP=true` | BF16 DiT (`11.1GB`) |
| **최고속 Blackwell NVFP4** | `MODAL_FLUX3_GPU=B200 MODAL_FLUX3_QUANT=nvfp4 MODAL_FLUX3_ENABLE_PUP=true` | flashinfer cu130 빌드 |
| **가성비 L40S (외부 VLM 프롬프트)** | `MODAL_FLUX3_GPU=L40S MODAL_FLUX3_QUANT=fp8 MODAL_FLUX3_ENABLE_PUP=false` | 요청 시 `use_pup: false` 또는 `src/flux3/pup_prompts_external_vlm.json` 스타일 캡션 전달 |

---

## 3. 호출 테스트

### 헬스체크
```bash
python infra/modal-flux3/client_example.py --url https://<your-modal-url> --health
```

### 텍스트 → 이미지
```bash
MODAL_API_TOKEN="..." python infra/modal-flux3/client_example.py \
  --url https://<your-modal-url> \
  --prompt "1000원대 고흡수 스펀지 블록 제품 스튜디오 컷, 세면대 물기를 한 번에 흡수하는 장면" \
  --width 1080 --height 1350 \
  --out sponge_card.png
```

### 레퍼런스 이미지 편집 (최대 10장)
```bash
MODAL_API_TOKEN="..." python infra/modal-flux3/client_example.py \
  --url https://<your-modal-url> \
  --prompt "Place the sponge from the first image cleanly beside a modern ceramic sink" \
  --image ./product_ref.png \
  --out edited.png
```

---

## 4. Vertex AI (Modal OIDC WIF)와 함께 쓰기

- `L40S` 비용 절감 조합(`MODAL_FLUX3_ENABLE_PUP=false`)에서 외부 VLM으로 프롬프트 업샘플링을 하거나, Modal 워커(`napda-backend`)에서 Gemini Vertex AI 추론을 함께 호출할 때는 정적 JSON 키 대신 **Modal OIDC (`MODAL_IDENTITY_TOKEN_FILE` / `MODAL_IDENTITY_TOKEN`) ↔ GCP Workload Identity**를 사용합니다.
- 전체 GCP 공급업체 등록, Modal Secret(`napda-backend`) 설정, Python WIF 추론 코드 예시는 [`backend/GCP_WIF_SETUP.md`](../../backend/GCP_WIF_SETUP.md)의 **7단계 · 8단계**를 참고하세요.
