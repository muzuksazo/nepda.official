# 빌드: 저장소 루트에서  docker build -f backend/Dockerfile -t napda-backend .
# 키는 이미지에 넣지 않는다. 실행할 때 환경변수로 준다 (backend/.env.example 참고).

# 1) A·B 시나리오 작업자 (TypeScript) 패키지 설치
FROM node:22-bookworm-slim AS workers
WORKDIR /w
COPY backend/bridge-dev/a/package.json backend/bridge-dev/a/package-lock.json a/
COPY backend/bridge-dev/b/package.json backend/bridge-dev/b/package-lock.json b/
RUN cd a && npm ci --no-audit --no-fund && cd ../b && npm ci --no-audit --no-fund
COPY backend/bridge-dev/a/src a/src
COPY backend/bridge-dev/a/tsconfig.json a/
COPY backend/bridge-dev/b/src b/src
COPY backend/bridge-dev/b/tsconfig.json b/

# 2) 서버
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    SCRIPTS_DIR=/app/scripts \
    HOOK_WORKERS_DIR=/app/bridge-dev \
    HOOK_ASSETS_DIR=/app/data/hook_assets \
    SHORTFORM_FONT_BOLD=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc \
    SHORTFORM_FONT_REGULAR=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc

# ffmpeg(자막 굽기 libass 포함), 한글 글꼴
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node 22 (A·B 작업자 실행용). 같은 Debian bookworm 이라 실행 파일만 옮겨도 된다
COPY --from=workers /usr/local/bin/node /usr/local/bin/node

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY libraries/media-tools /app/scripts
COPY backend/app /app/app
COPY backend/hookpipe /app/hookpipe
COPY backend/bridge-dev/WORKER_CONTRACT.md /app/bridge-dev/
COPY --from=workers /w/a /app/bridge-dev/a
COPY --from=workers /w/b /app/bridge-dev/b
COPY backend/bridge-dev/c/src /app/bridge-dev/c/src
COPY scripts/hookpipe_smoke.py /app/scripts/hookpipe_smoke.py

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
