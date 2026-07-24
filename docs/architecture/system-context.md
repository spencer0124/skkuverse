---
title: System Context
type: explanation
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-07-24
audience: public
---

# System Context

> SKKUverse의 시스템 경계 — 누가 이 시스템을 쓰고, 이 시스템은 어떤 외부 세계에 의존하는가 (C4 Level 1). 한 단계 안으로 들어가려면 [컨테이너 뷰](container-view.md).

## 맥락

SKKUverse는 성균관대 학생을 위한 캠퍼스 앱이다. 핵심 가치는 **흩어진 학과 공지를 한곳에 모아 AI로 구조화**해 보여주는 것. 그래서 시스템은 본질적으로 두 종류의 외부 세계와 맞닿는다 — **데이터를 긁어올 원천(SKKU 학과 사이트)** 과 **결과를 밀어줄 채널(FCM 푸시)**.

## 다이어그램

```mermaid
graph TB
    student["학생<br/>(모바일 앱 사용자)"]

    subgraph skkuverse["SKKUverse 시스템"]
        core["공지 수집·요약·서빙<br/>+ 푸시 오케스트레이션"]
    end

    skku["SKKU 학과 사이트<br/>(~149개 · 9개 크롤 전략)"]
    llm["LLM 프로바이더<br/>(OpenAI / Cerebras / Groq)"]
    fcm["Firebase<br/>(Cloud Function · FCM · Firestore)"]

    student -->|공지 조회 / 알림 수신| core
    skku -->|HTTP 크롤 (rate-limited)| core
    core -->|공지 원문 요약 요청| llm
    core -->|푸시 전송 위임| fcm
    fcm -->|푸시 알림| student
```

## 경계가 의미하는 것

| 외부 시스템 | 관계 | 왜 시스템 밖인가 |
| --- | --- | --- |
| SKKU 학과 사이트 | 크롤 대상 (읽기) | 통제 불가능한 원천. 사이트 구조가 제각각이라 [9개 크롤 전략](https://github.com/spencer0124/skkuverse-crawler/tree/main/docs/strategies)으로 흡수 |
| LLM 프로바이더 | 요약 위임 (동기 HTTP) | 비용·가용성 리스크. `litellm` Router로 3중 fallback → [공지 파이프라인 §AI](../flows/notice-pipeline.md) |
| Firebase | 푸시 전송 위임 | 토큰 관리·전송을 Cloud Function으로 오프로딩 (VM 부하·비용 격리) |

**핵심 설계 선택**: 유저 데이터는 Firebase(Firestore/Auth), 공공 데이터(공지·건물·버스)는 MongoDB. 두 저장소의 경계는 "누구 소유의 데이터인가"로 갈린다. 상세는 [데이터 토폴로지](data-topology.md).

## 관련 문서

- [컨테이너 뷰](container-view.md) — 시스템 안쪽 (레포·저장소 단위)
- [공지 파이프라인](../flows/notice-pipeline.md) — 외부 접점이 실제로 흐르는 경로
