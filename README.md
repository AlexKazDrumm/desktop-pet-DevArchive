# Dev Archive Manager — monorepo

Готовый старт для твоего приложения архива проектов с доступом к ФС, snap2txt, ссылками и Figma-пиксельным экспортом.

## Стек

- Desktop UI: **Next.js 14** + **Electron**
- API: **NestJS 10** + **Prisma** + **Postgres**
- Очереди/кеш: **Redis** (зарезервировано; worker можно добавить позже)
- Python: **FastAPI** сервисы
  - `snap2txt_service` — дерево/конкатенация проекта
  - `figma_parser` — дерево и pixel-perfect экспорт (SVG/PNG) по Figma API

## Быстрый старт

### 0) Зависимости
- Node 20+, pnpm 9+ (`npm i -g pnpm`)
- Python 3.10/3.11
- Docker + Docker Compose

### 1) Инфра
```bash
pnpm dev:infra            # поднимет postgres:5432 и redis:6379
```

### 2) Установка пакетов
```bash
pnpm install
```

### 3) Настройка окружения API
```bash
cd apps/api-gateway
cp .env.example .env
# при необходимости выставь:
# DATABASE_URL=postgresql://app:app@localhost:5432/appdb
# REDIS_URL=redis://localhost:6379
# PY_SNAP_URL=http://127.0.0.1:8801
# PY_FIGMA_URL=http://127.0.0.1:8802
cd ../../
```

### 4) Prisma (миграции)
```bash
cd apps/api-gateway
pnpm prisma:migrate         # введи имя миграции: init
pnpm prisma:generate
pnpm dev                    # API на http://127.0.0.1:7780
```

### 5) Python сервисы

#### snap2txt_service
```bash
cd workers/py/snap2txt_service
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py        # http://127.0.0.1:8801
```

#### figma_parser
```bash
cd ../figma_parser
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export FIGMA_TOKEN=...   # или set FIGMA_TOKEN=... в Windows
python app.py            # http://127.0.0.1:8802
```

### 6) Desktop UI
В новом терминале:
```bash
cd apps/desktop
pnpm dev         # Next dev server на 3000
# в отдельном окне:
pnpm electron    # Electron откроет http://127.0.0.1:3000
```

> UI ожидает API на `http://127.0.0.1:7780`. Можно переопределить переменной `NEXT_PUBLIC_API_URL`.

## Как пользоваться

1. В Desktop: **Создать проект** → укажи *Название* и *Тип*. (Опционально `localPath`, чтобы работал snap2txt).
2. На главной странице проекта нажми **Snap Tree** или **Concat** — API вызовет `snap2txt_service`.  
   Результаты сохраняются в системной папке приложения:
   - Windows: `%APPDATA%/DevArchiveManager/data/projects/<id>/artifacts/`
   - macOS: `~/Library/Application Support/DevArchiveManager/data/projects/<id>/artifacts/`
   - Linux: `~/.config/DevArchiveManager/data/projects/<id>/artifacts/`

## Структура
```
apps/
  api-gateway/       # NestJS API + Prisma
  desktop/           # Next.js + Electron
workers/
  py/
    snap2txt_service/
    figma_parser/
docker-compose.yml
```

## Дальше
- Добавить страницу "детали проекта" (артефакты/сканы/ссылки).
- Провести интеграцию Figma UI вызовов в Desktop.
- Подключить BullMQ воркера и прогресс-ивенты.
- Добавить генерацию отчетов (PDF/HTML).
