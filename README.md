# SKKUverse — System Documentation

> SKKUverse는 성균관대 캠퍼스 앱입니다. 이 저장소는 **6개 레포에 흩어진 시스템을 하나로 잇는 문서 허브**입니다 — 개별 레포의 코드가 아니라, 레포 사이의 경계·데이터 흐름·설계 근거를 다룹니다.

한 줄 요약: **"하나의 MongoDB Atlas를 버스(bus)로 공유하는 두 개의 백엔드 평면 — Python 수집 평면(크롤러 + AI)과 NestJS 서빙 평면 — 위에 동기 HTTP 시임 2개만 얹은 시스템. 전부 Oracle Cloud ARM 무료 VM 1대, 월 $0."**

## 이 문서부터 읽으세요

| 문서 | 무엇 |
| --- | --- |
| [시스템 컨텍스트](docs/architecture/system-context.md) | 시스템 경계 — 외부 세계(SKKU 사이트, FCM)와 SKKUverse의 접점 (C4 Level 1) |
| [컨테이너 뷰](docs/architecture/container-view.md) | 6개 레포 + MongoDB + FCM이 어떻게 맞물리나 (C4 Level 2) |
| [**공지 파이프라인**](docs/flows/notice-pipeline.md) | ⭐ AI 공지 기능의 end-to-end 흐름 (크롤 → AI 요약 → 서빙 → 푸시 → 렌더) |
| [데이터 토폴로지](docs/architecture/data-topology.md) | 어느 컬렉션을 어느 레포가 소유하고 어디에 스키마가 문서화돼 있나 |
| [설계 결정 (ADR)](docs/decisions/) | 레포 경계를 넘는 결정들 |

## 서비스 토폴로지

| 서비스 | 스택 | 역할 | 평면 | 레포 |
| --- | --- | --- | --- | --- |
| server | NestJS 11 · TS(strict) · MongoDB | 읽기 API · 버스 정보 · 푸시 디스패치 오케스트레이션 | 읽기/서빙 | [skkuverse-server](https://github.com/spencer0124/skkuverse-server) |
| crawler | Python 3.12 · httpx · BeautifulSoup · motor · APScheduler | 학과 공지 + 학사일정(+ 예정: 식당) 크롤링/전처리 | 쓰기/수집 | [skkuverse-crawler](https://github.com/spencer0124/skkuverse-crawler) |
| ai | Python 3.12 · FastAPI · litellm | 공지 구조화 추출(요약·분류·일시/장소) — stateless | 쓰기/수집 | [skkuverse-ai](https://github.com/spencer0124/skkuverse-ai) |
| app | Expo 54 · RN 0.81 · React 19 (Yarn 모노레포) | 모바일 앱 — 실시간 셔틀·공지 피드·건물 검색 (iOS/Android) | 클라이언트 | [skkuverse-app](https://github.com/spencer0124/skkuverse-app) |
| web | Next.js | 마케팅/랜딩 웹 (`skkuverse.com`) | 클라이언트 | [skkuverse.com](https://github.com/spencer0124/skkuverse.com) |
| codepush | self-hosted `expo-open-ota` (Docker · `ota.skkuverse.com`) | 코드사이닝 OTA 업데이트 서버 (앱 JS 번들 무선 배포) | 인프라 | [skkuverse-codepush](https://github.com/spencer0124/skkuverse-codepush) |

## 각 레포의 문서

시스템 전체 지식은 여기에, **레포 국소 지식은 각 레포의 `docs/`에** 둡니다 (소유 = 그것을 쓰는/마이그레이션하는 레포).

- [server docs](https://github.com/spencer0124/skkuverse-server/tree/main/docs) — 읽기 API 계약, 읽기 인덱스, FCM 디스패치
- [crawler docs](https://github.com/spencer0124/skkuverse-crawler/tree/main/docs) — 크롤 전략, 소스, **`skku_notices` 스키마(SSOT)**, 예정: MCP
- [ai docs](https://github.com/spencer0124/skkuverse-ai/tree/main/docs) — LLM 라우팅, 공지 요약/분류 설계
- [app docs](https://github.com/spencer0124/skkuverse-app/tree/main/docs) — 클라이언트 렌더링, FCM 전달, ADR
- [web](https://github.com/spencer0124/skkuverse.com) — 마케팅/랜딩 (문서 예정)
- [codepush](https://github.com/spencer0124/skkuverse-codepush) — self-hosted OTA 인프라

## 이 저장소의 규칙

문서 작성 규칙과 인덱스는 [docs/README.md](docs/README.md)를 따릅니다 (Diátaxis + frontmatter + "값을 복사하지 말고 출처를 가리켜라"). 이 규칙은 [skkuverse-app의 문서 컨벤션](https://github.com/spencer0124/skkuverse-app/tree/main/docs)을 워크스페이스 표준으로 채택한 것입니다.
