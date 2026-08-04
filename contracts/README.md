---
title: 크로스 레포 설정 계약
type: reference
status: active
updated: 2026-08-04
---

# 크로스 레포 설정 계약

한 레포가 소유한 설정을 다른 레포가 사본으로 들고 있는 관계를 **계약(contract)** 이라 부른다.
[`manifest.json`](manifest.json)이 그 목록이고, [`../tools/skkuverse_sync.py`](../tools/skkuverse_sync.py)가
사본을 정직하게 유지하는 장치다.

한 번에 전체를 보려면:

```bash
python3 tools/skkuverse_sync.py status
```

## 왜 필요했나

원래는 크롤러의 `generate_artifacts.py`가 `copy_to_sibling()`으로 형제 레포에 **밀어 넣었다**.
대상 디렉터리가 없으면 조용히 건너뛰었다 — stdout 한 줄, exit 0, 반환값 없음.

```python
if dst.parent.exists():
    shutil.copy2(src, dst)
else:
    print(f"  -- Skipped {label} (directory not found)")
```

**실패 모드가 침묵인 동기화 장치는 성공과 구별되지 않는 드리프트를 만든다.** 게다가 push 방식이라
모든 레포가 나란히 체크아웃된 관리자 노트북에서만 돌았고, CI는 신선도를 검증할 수단이 없었다.

## 세 개의 엣지

**누가 그 실패를 고칠 수 있느냐**로 나뉜다.

| 엣지 | 비교 대상 | 네트워크 | 실행 위치 | 성격 |
| --- | --- | --- | --- | --- |
| **무결성** | 소비자 파일 ↔ 자기 lock | 불필요 | 각 소비자 `ci.yml` + `deploy.yml` | **하드 실패 (머지·배포 차단)** |
| **신선도** | 소비자 lock ↔ producer@main | 필요 | 각 소비자 일일 cron | 자기 자신에게 **동기화 PR을 연다** |
| **생산자 자체검사** | 재생성 ↔ 커밋된 아티팩트 | 불필요 | 크롤러 `ci.yml` | **하드 실패** |

차단하는 검사는 전부 **오프라인**이고 **PR과 같은 레포의 파일** 때문에 실패한다. 그래서 빨간 불은
항상 그 브랜치에서 고칠 수 있다. 크롤러에서 학과 하나 고쳤다고 무관한 서버 PR이 빨개지는 일은 없다.

> 저자가 현재 브랜치에서 고칠 수 없는 빨간 검사는 검사가 없는 것보다 나쁘다.
> 그런 상황이 관측되면 튜닝 문제가 아니라 설계 버그다 — 신선도 cron 쪽으로 옮겨야 한다.

## 왜 버전이 아니라 해시인가

lock 파일의 모든 값은 `pull`이 계산한 **콘텐츠 해시**이거나 소스에서 **추출한 상수**다.
사람이 적는 값이 하나도 없다. 사람이 만든 버전 문자열(`v3.5.1`)은 무엇이 바뀌었는지 말해주지 않고,
올리는 것을 잊으면 조용히 거짓말을 한다.

**manifest에는 해시도 값도 없다.** manifest는 *지도*(누가 무엇을 누구에게 주는가)이고,
해시는 *상태*라서 소비자 lock에 산다. 그래서 manifest는 계약 **집합**이 바뀔 때만 바뀐다 (드물다).
이건 [`docs/README.md`](../docs/README.md)의 "스키마/수치를 여기 복사하지 않는다" 원칙 그대로다.

## 비교 사슬 (SSOT를 직접 비교하면 왜 틀리나)

서버의 사본은 SSOT의 **변환 결과**지 복사본이 아니다 — `hasCategory`/`hasAuthor`는 `strategy`에서
`STRATEGY_FEATURES`로 유도된다. 그래서 비교 대상은 SSOT가 아니라 **생성된 아티팩트**이고,
그래서 크롤러의 `py/generated/`가 커밋돼야 한다.

```
crawler/sources.json                        SSOT, 커밋됨
    │  gen_sources_json()  [변환]
    ▼
crawler/py/generated/server-sources.json     커밋됨
    │  ├── sha256 ──► lock.producer.sha256 + lock.producer.commit
    │  mode: copy
    ▼
server/src/notices/sources.json              커밋됨
       └── sha256 ──► lock.sha256

엣지 1 (차단, 오프라인): sha256(서버 파일)      == lock.sha256
엣지 2 (cron, 네트워크): lock.producer.sha256  == sha256(crawler@main 아티팩트)
```

`mode: generate`는 두 해시가 구조적으로 다르다 (`sha256`은 산출된 소비자 파일, `producer.sha256`은
생성기 입력) — lock이 두 필드를 따로 들고 있는 이유다.

## 계약 종류

- **`kind: file` / `mode: copy`** — 바이트 사본.
- **`kind: file` / `mode: generate`** — 생성기가 producer 입력에서 소비자 파일을 만든다
  (`tools/generators/`). 생성기는 결정론적이어야 한다 — `pull`이 만들고 `status`가 재현해서 검증한다.
- **`kind: constant`** — 파일이 아니라 소스 안의 상수. 정규식으로 추출하되 **fail-closed**:
  매치가 정확히 1개가 아니면 예외다. "이 상수를 더 못 찾겠다"가 그 자체로 빌드 실패여야
  이름 변경이 검사를 조용히 무력화하지 못한다.

`relation`은 `eq`/`lte`/`gte`. 방향이 중요한 계약이 있다 — `notices.topic-cap`이 그렇다.
Cloud Function이 `MAX_TOPICS` 초과 payload를 400으로 거절하므로 서버 `TOPIC_CAP`은 그 **이하**여야 하고,
`lte`여야 ADR 0005가 강제하는 배포 순서(앱 먼저)의 중간 상태가 초록이다.

| 단계 | 앱 `MAX_TOPICS` | 서버 `TOPIC_CAP` | `eq` | `lte` | 실제로 안전? |
| --- | --- | --- | --- | --- | --- |
| 시작 | 10 | 10 | 초록 | 초록 | 예 |
| 앱 PR이 30으로 올림 | 30 | 10 | **빨강** | 초록 | 예 — 서버는 ≤10 전송, CF는 ≤30 수용 |
| 서버 PR이 30으로 올림 | 30 | 30 | 초록 | 초록 | 예 |
| *잘못된 순서*: 서버 먼저 | 10 | 30 | 빨강 | **빨강** | 아니오 — CF 400, 재시도 소진 후 영구 실패 |

`status`는 `active`(검사됨) / `planned`(표시만, 검사 생략) / `retired`를 구분한다.
아직 없는 계약을 `planned`로 올려두면 README가 아니라 매 실행 출력에 갭이 보인다.

## 일상 작업

```bash
# 전체 현황 (오프라인, 로컬 워킹 트리)
python3 tools/skkuverse_sync.py status

# origin/main 기준 (네트워크)
python3 tools/skkuverse_sync.py status --remote

# 업스트림 반영 + lock 갱신
python3 tools/skkuverse_sync.py pull --all

# 한 계약의 전체 사슬
python3 tools/skkuverse_sync.py explain notices.topic-cap

# CI가 도는 것 (오프라인, 소비자 레포에서)
python3 tools/skkuverse_sync.py check --repo server --root .
```

`pull`은 해시가 **실제로 바뀐 경우에만** lock을 다시 쓴다 (`syncedAt`은 비교 대상이 아니다).
깨끗한 상태에서 `pull --all`은 diff를 하나도 만들지 않는다 — 이 성질이 없으면 매번 네 레포가
더러워져서 아무도 이 도구를 믿지 않게 된다.

### 계약 추가

1. `manifest.json`에 항목 추가 (`status: "planned"`로 시작해도 된다)
2. `python3 tools/skkuverse_sync.py validate-manifest`
3. `pull --repo <consumer>` → 소비자 레포에 lock 커밋
4. `status: "active"`로 전환

`mode: generate`면 `tools/generators/`에 생성기를 추가하고 `_load_generators()`에 등록한다.
서버가 소비자이고 대상이 `src/` 아래 런타임 JSON이면 `"requires": ["server-build-asset"]`을 붙인다 —
`scripts/copy-build-assets.js`에 등록되지 않은 파일은 `dist/`에서 사라져 컨테이너가 부팅에 실패한다.

## 함정

- **lock 충돌은 손으로 풀지 않는다.** 긴 브랜치를 리베이스하면 `.contracts.lock.json`이 충돌할 수 있다.
  아무 쪽이나 take한 뒤 `pull`을 다시 돌린다.
- **`status --local`은 워킹 트리를 본다.** 푸시 안 된 브랜치와 "동기화됨"일 수 있다.
  커밋 안 된 사본은 `!` 노트로 따로 표시된다 — CI는 디스크가 아니라 git을 읽기 때문이다.
- **도구는 핀 고정 없이 `main`에서 클론된다.** umbrella에 나쁜 커밋이 들어가면 네 레포 CI가 동시에
  빨개진다. 의도된 트레이드오프다 — 핀을 두면 도구를 고칠 때마다 네 레포에서 버전을 올려야 하고,
  그게 바로 없애려던 수동 버전 관리다. umbrella 자체 CI(단위 테스트 + `validate-manifest`)가
  블라스트 반경을 막고, 복구는 문서 전용 레포에서 revert 한 번이다.

## 관련 문서

- [데이터 토폴로지](../docs/architecture/data-topology.md) — DB 컬렉션 소유권 맵 (이건 *설정* 소유권 맵)
- [컨테이너 뷰](../docs/architecture/container-view.md) — 동기 HTTP 이음매 2곳
- [ADR 0001](../docs/decisions/0001-notice-data-ownership.md) — 공지 데이터 필드 소유권
