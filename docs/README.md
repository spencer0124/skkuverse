---
title: Docs Index & Conventions
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-07-24
audience: internal
---

# Docs Index & Conventions

> skkuverse(시스템 문서 허브)의 인덱스이자 작성 규칙. 이 레포는 **레포 경계를 넘는(cross-cutting) 지식 전용** — 레포 국소 지식은 각 레포의 `docs/`에 둔다.

## 이 레포가 담는 것 / 담지 않는 것

| 담는다 (cross-repo) | 담지 않는다 (레포 국소) |
| --- | --- |
| 시스템 경계·아키텍처 다이어그램 | 특정 레포의 빌드/배포 런북 |
| 레포를 가로지르는 데이터 흐름 (공지 파이프라인) | 한 컬렉션의 상세 스키마 (→ 소유 레포) |
| 데이터 소유권 맵 (누가 무엇을 쓰나) | 프레임워크별 구현 디테일 |
| 레포 경계를 넘는 ADR | 한 레포 안에서 끝나는 ADR |

**원칙: 스키마/수치를 여기 복사하지 않는다.** 이 레포는 *인덱스이자 지도*다 — 상세는 소유 레포의 문서를 링크한다. ([데이터 토폴로지](architecture/data-topology.md)가 그 지도.)

## 폴더 구조 (Diátaxis)

skkuverse-app의 컨벤션을 워크스페이스 표준으로 채택. **분류 기준은 주제가 아니라 독자의 니즈.**

| 폴더 | 니즈 | 내용 |
| --- | --- | --- |
| `architecture/` | 이해하기 | 시스템 경계·컨테이너 뷰·데이터 토폴로지 (C4) |
| `flows/` | 이해하기 | 레포를 가로지르는 end-to-end 흐름 |
| `decisions/` | — | cross-repo ADR (`NNNN-kebab-title.md`) |

## 문서 인덱스

### architecture

| 문서 | 요약 |
| --- | --- |
| [system-context.md](architecture/system-context.md) | C4 L1 — 시스템 경계와 외부 접점 |
| [container-view.md](architecture/container-view.md) | C4 L2 — 6개 레포 + MongoDB + FCM의 맞물림 |
| [data-topology.md](architecture/data-topology.md) | DB/컬렉션별 소유 레포 + 스키마 문서 링크 |

### flows

| 문서 | 요약 |
| --- | --- |
| [notice-pipeline.md](flows/notice-pipeline.md) | AI 공지 end-to-end (크롤 → AI → 서빙 → 푸시 → 렌더) |

### decisions

| 문서 | 상태 |
| --- | --- |
| [0001-notice-data-ownership.md](decisions/0001-notice-data-ownership.md) | accepted |

### contracts (기계 판독 가능)

`docs/` 바깥에 있는 유일한 예외. 산문이 아니라 도구가 읽는 계약 레지스트리다 — 위의 "스키마·수치를
복사하지 않는다" 원칙은 그대로 지킨다. manifest는 포인터(레포·경로·생성기)만 담고, 해시와 값은
각 소비자 레포의 `.contracts.lock.json`에 산다. 그래서 manifest는 계약 **집합**이 바뀔 때만 바뀐다.

| 문서 | 요약 |
| --- | --- |
| [contracts/README.md](../contracts/README.md) | 크로스 레포 설정 계약 — 세 엣지, 해시 기반 lock, 일상 작업 |
| [contracts/manifest.json](../contracts/manifest.json) | 계약 토폴로지 (생산자 · 소비자 · 생성기) |

## 문서 작성 규칙

### 1. Frontmatter (필수)

```yaml
---
title: <Title Case 제목>
type: reference | explanation | adr
status: draft | accepted | superseded | deprecated
owner: zoyoong124@gmail.com
last-updated: YYYY-MM-DD
audience: internal | public
---
```

포트폴리오로 공개되는 문서는 `audience: public`. 개인 준비 자료(인터뷰 노트 등)는 `audience: internal`.

### 2. 골격

frontmatter → `# H1`(정확히 하나) → `> 한 줄 요약` → `##` 섹션(레벨 건너뛰기 금지). 새 문서는 [`_template.md`](_template.md) 복사.

### 3. 값을 복사하지 말고 출처를 가리켜라

버전·수치·개수·스키마 필드를 이 레포에 하드코딩하지 않는다. 다른 레포의 코드가 바뀌면 이곳이 조용히 거짓말을 시작한다.

- ❌ `크롤 소스는 149개다`
- ✅ `크롤 소스 목록의 SSOT는 skkuverse-crawler의 sources.json` (개수는 "작성 시점 기준 ~149" 정도로만)

### 4. 다이어그램

- **Mermaid**를 기본으로 쓴다 (GitHub 네이티브 렌더, 빌드 불필요). 코드펜스 `mermaid`.
- 다이어그램이 Mermaid로 감당 안 될 때만 `diagrams/`에 PlantUML/C4 소스를 둔다.

### 5. 파일명·서식

- kebab-case 소문자 `.md`. ADR은 `NNNN-kebab-title.md`.
- 코드펜스 언어 태그 필수. 구조화된 사실은 표로. 본문 한국어, 기술 용어 영어.

## 관련

- [워크스페이스 랜딩](../README.md)
- [skkuverse-app 문서 컨벤션(원본 표준)](https://github.com/spencer0124/skkuverse-app/tree/main/docs)
