# 게임 핵심 요소 추출 기능 구현 명세서

## 개요

게임 등록 시 자유 텍스트(게임 설명)에서 LLM을 활용해 핵심 요소를 추출하고, 사용자가 확인/수정할 수 있게 하는 기능.

추출된 요소는 이후 **질문 템플릿에 동적으로 채워넣어** 게임 맞춤형 설문 질문을 생성하는 데 활용됨.

## 구현 위치

**FastAPI (AI 서버)**

## 전체 흐름

```
1. Spring → FastAPI: 게임 정보 전달 (이름, 장르 1~3개, 설명 2000자 이내)
2. FastAPI: 장르 기반으로 필수/선택 요소 목록 결정
3. FastAPI: LLM으로 게임 설명에서 요소 추출
4. FastAPI → Spring: 추출 결과 + 실패한 필수 항목 리스트 반환
5. 프론트: 사용자 확인/수정 UI 표시
6. 사용자 확인 후 최종 저장
```

## UI 예시

```
[AI가 분석한 게임 핵심 요소]

📌 필수
• 핵심 메카닉: 카드 조합과 덱 빌딩
• 플레이어 목표: 던전 최하층 도달
• 영구 성장 요소: ⚠️ 감지 실패 [직접 입력 ________]

💡 선택 (더 정확한 질문 생성에 도움)
• 런 구조: 층별 전투 → 보상 선택 → 다음 층
• 랜덤 요소: (비어있음) [+ 추가]

[확인] ← 필수 다 채워져야 활성화
```

---

## 데이터 구조

### 공통 필수 요소 (모든 장르)

| 요소 | 영문 키 | 설명 |
|------|---------|------|
| 핵심 메카닉 | `core_mechanic` | 플레이어가 반복적으로 수행하는 핵심 행동 |
| 플레이어 목표 | `player_goal` | 플레이어가 달성하려는 주요 목표 |

### 장르별 필수/선택 요소 매핑

| 장르 | 필수 | 선택 |
|------|------|------|
| **액션** | `combat_system` | `control_scheme` |
| **어드벤처** | `narrative` | `main_character`, `exploration_element` |
| **시뮬레이션** | `simulation_target` | `management_element` |
| **퍼즐** | `puzzle_mechanic` | - |
| **전략** | `decision_type` | `resource_system` |
| **RPG** | `progression_system` | `narrative`, `main_character` |
| **아케이드** | `score_system` | `difficulty_curve` |
| **호러** | `horror_element` | `atmosphere`, `narrative` |
| **슈팅** | `shooting_mechanic` | `weapon_variety` |
| **비주얼 노벨** | `narrative`, `main_character` | `choice_system` |
| **로그라이크** | `run_structure`, `permanent_progression` | `randomness_element` |
| **스포츠** | `sport_type`, `play_mode` | - |
| **리듬** | `rhythm_system` | `music_genre`, `input_method` |
| **대전** | `fighting_system` | `character_roster` |
| **캐주얼** | - | `session_length` |

### 요소 상세 정의 (프롬프트 및 검증용)

```python
ELEMENT_DEFINITIONS = {
    # === 공통 필수 ===
    "core_mechanic": {
        "name_ko": "핵심 메카닉",
        "description": "플레이어가 반복적으로 수행하는 핵심 행동",
        "examples": ["타워 배치", "카드 조합", "점프/회피", "자원 수집", "대화 선택"]
    },
    "player_goal": {
        "name_ko": "플레이어 목표",
        "description": "플레이어가 달성하려는 주요 목표",
        "examples": ["스테이지 클리어", "생존", "퍼즐 해결", "영토 확장", "엔딩 도달"]
    },
    
    # === 액션 ===
    "combat_system": {
        "name_ko": "전투 시스템",
        "description": "전투/액션 방식",
        "examples": ["콤보 공격", "회피와 패링", "실시간 전투", "턴제 전투"]
    },
    "control_scheme": {
        "name_ko": "조작 방식",
        "description": "플레이어 입력 방식",
        "examples": ["가상패드", "스와이프", "키보드+마우스", "터치"]
    },
    
    # === 어드벤처/내러티브 ===
    "narrative": {
        "name_ko": "스토리/세계관",
        "description": "배경 설정과 이야기",
        "examples": ["포스트 아포칼립스", "판타지 왕국", "근미래 디스토피아", "일상 로맨스"]
    },
    "main_character": {
        "name_ko": "주인공/캐릭터",
        "description": "플레이어가 조작하거나 감정이입하는 대상",
        "examples": ["기억 잃은 기사", "고양이 탐정", "평범한 고등학생", "로봇"]
    },
    "exploration_element": {
        "name_ko": "탐험 요소",
        "description": "탐험하는 대상이나 방식",
        "examples": ["오픈월드", "던전 탐사", "숨겨진 방", "미지의 행성"]
    },
    
    # === 시뮬레이션 ===
    "simulation_target": {
        "name_ko": "시뮬레이션 대상",
        "description": "무엇을 시뮬레이션하는지",
        "examples": ["농장 경영", "도시 건설", "병원 운영", "연애", "요리"]
    },
    "management_element": {
        "name_ko": "관리 요소",
        "description": "관리해야 하는 것",
        "examples": ["재정", "직원", "시간", "관계", "자원"]
    },
    
    # === 퍼즐 ===
    "puzzle_mechanic": {
        "name_ko": "퍼즐 방식",
        "description": "퍼즐의 핵심 메카닉",
        "examples": ["3매치", "물리 퍼즐", "논리 추론", "숨은그림찾기", "탈출"]
    },
    
    # === 전략 ===
    "decision_type": {
        "name_ko": "의사결정 요소",
        "description": "전략적으로 고민하는 것",
        "examples": ["유닛 배치", "자원 분배", "타이밍 선택", "기술 연구 순서"]
    },
    "resource_system": {
        "name_ko": "자원 시스템",
        "description": "관리하는 자원 종류",
        "examples": ["골드", "마나", "식량", "인구", "에너지"]
    },
    
    # === RPG ===
    "progression_system": {
        "name_ko": "성장 시스템",
        "description": "캐릭터/플레이어 성장 방식",
        "examples": ["레벨업", "스킬트리", "장비 강화", "직업 전직", "스탯 분배"]
    },
    
    # === 아케이드 ===
    "score_system": {
        "name_ko": "스코어 시스템",
        "description": "점수 획득 방식",
        "examples": ["콤보 보너스", "시간 보너스", "퍼펙트 클리어", "멀티플라이어"]
    },
    "difficulty_curve": {
        "name_ko": "난이도 곡선",
        "description": "난이도 상승 방식",
        "examples": ["스테이지별 상승", "무한 모드", "적응형 난이도"]
    },
    
    # === 호러 ===
    "horror_element": {
        "name_ko": "공포 연출 방식",
        "description": "공포를 주는 방식",
        "examples": ["점프스케어", "심리적 공포", "추격전", "고어", "언캐니"]
    },
    "atmosphere": {
        "name_ko": "분위기",
        "description": "게임의 무드/톤",
        "examples": ["어둡고 습한", "긴장감", "고립감", "불안함"]
    },
    
    # === 슈팅 ===
    "shooting_mechanic": {
        "name_ko": "슈팅 방식",
        "description": "슈팅 시점과 방식",
        "examples": ["FPS", "TPS", "탑다운 슈터", "탄막 슈팅", "레일 슈터"]
    },
    "weapon_variety": {
        "name_ko": "무기 종류",
        "description": "사용 가능한 무기들",
        "examples": ["총기류", "마법", "근접무기", "폭발물", "탈것 무기"]
    },
    
    # === 비주얼 노벨 ===
    "choice_system": {
        "name_ko": "선택지 시스템",
        "description": "스토리 분기 방식",
        "examples": ["대화 선택지", "행동 선택", "멀티 엔딩", "호감도 시스템"]
    },
    
    # === 로그라이크 ===
    "run_structure": {
        "name_ko": "런 구조",
        "description": "한 판의 진행 방식",
        "examples": ["층별 진행", "스테이지 선택", "시간 제한", "방 클리어"]
    },
    "permanent_progression": {
        "name_ko": "영구 성장 요소",
        "description": "죽어도 유지되는 것",
        "examples": ["메타 화폐", "영구 업그레이드", "해금 캐릭터", "도감"]
    },
    "randomness_element": {
        "name_ko": "랜덤 요소",
        "description": "매 런마다 바뀌는 것",
        "examples": ["맵 구조", "아이템 드랍", "이벤트", "적 배치"]
    },
    
    # === 스포츠 ===
    "sport_type": {
        "name_ko": "종목",
        "description": "스포츠 종류",
        "examples": ["축구", "농구", "야구", "골프", "테니스", "레이싱"]
    },
    "play_mode": {
        "name_ko": "플레이 모드",
        "description": "게임 모드",
        "examples": ["시즌 모드", "커리어", "멀티플레이", "토너먼트", "연습"]
    },
    
    # === 리듬 ===
    "rhythm_system": {
        "name_ko": "리듬 시스템",
        "description": "노트/판정 방식",
        "examples": ["떨어지는 노트", "원형 노트", "롱노트", "슬라이드", "플릭"]
    },
    "music_genre": {
        "name_ko": "음악 장르",
        "description": "수록곡 장르",
        "examples": ["K-POP", "EDM", "클래식", "애니송", "오리지널"]
    },
    "input_method": {
        "name_ko": "입력 방식",
        "description": "플레이어 입력 방법",
        "examples": ["터치", "키보드", "컨트롤러", "모션"]
    },
    
    # === 대전 ===
    "fighting_system": {
        "name_ko": "대전 시스템",
        "description": "대전 방식",
        "examples": ["1:1 격투", "팀 대전", "카드 배틀", "자동 배틀"]
    },
    "character_roster": {
        "name_ko": "캐릭터 로스터",
        "description": "선택 가능 캐릭터 구성",
        "examples": ["20명의 파이터", "속성별 캐릭터", "클래스별 영웅"]
    },
    
    # === 캐주얼 ===
    "session_length": {
        "name_ko": "한 판 길이",
        "description": "평균 플레이 시간",
        "examples": ["1분", "3분", "5분", "무제한"]
    }
}
```

### 장르별 요소 매핑 (코드용)

```python
GENRE_ELEMENT_MAPPING = {
    "_common": {
        "required": ["core_mechanic", "player_goal"],
        "optional": []
    },
    "액션": {
        "required": ["combat_system"],
        "optional": ["control_scheme"]
    },
    "어드벤처": {
        "required": ["narrative"],
        "optional": ["main_character", "exploration_element"]
    },
    "시뮬레이션": {
        "required": ["simulation_target"],
        "optional": ["management_element"]
    },
    "퍼즐": {
        "required": ["puzzle_mechanic"],
        "optional": []
    },
    "전략": {
        "required": ["decision_type"],
        "optional": ["resource_system"]
    },
    "RPG": {
        "required": ["progression_system"],
        "optional": ["narrative", "main_character"]
    },
    "아케이드": {
        "required": ["score_system"],
        "optional": ["difficulty_curve"]
    },
    "호러": {
        "required": ["horror_element"],
        "optional": ["atmosphere", "narrative"]
    },
    "슈팅": {
        "required": ["shooting_mechanic"],
        "optional": ["weapon_variety"]
    },
    "비주얼 노벨": {
        "required": ["narrative", "main_character"],
        "optional": ["choice_system"]
    },
    "로그라이크": {
        "required": ["run_structure", "permanent_progression"],
        "optional": ["randomness_element"]
    },
    "스포츠": {
        "required": ["sport_type", "play_mode"],
        "optional": []
    },
    "리듬": {
        "required": ["rhythm_system"],
        "optional": ["music_genre", "input_method"]
    },
    "대전": {
        "required": ["fighting_system"],
        "optional": ["character_roster"]
    },
    "캐주얼": {
        "required": [],
        "optional": ["session_length"]
    }
}
```

---

## API 명세

### Request

```
POST /api/game/extract-elements
```

```json
{
    "game_name": "다크 슬레이어",
    "genres": ["액션", "로그라이크"],
    "game_description": "어둠의 던전에서 살아남아야 하는 핵앤슬래시 로그라이크. 매 층마다 무작위 적과 보상이 등장하며, 죽으면 처음부터 다시 시작하지만 획득한 소울로 영구 강화가 가능합니다. 다양한 무기와 스킬 조합으로 나만의 빌드를 완성하세요."
}
```

### Response

```json
{
    "elements": {
        "core_mechanic": "핵앤슬래시 전투와 스킬 조합",
        "player_goal": "던전 최하층 도달 및 생존",
        "combat_system": "다양한 무기와 스킬 조합 전투",
        "run_structure": "층별 진행, 무작위 적과 보상",
        "permanent_progression": "소울을 통한 영구 강화",
        "control_scheme": null,
        "randomness_element": "무작위 적과 보상 등장"
    },
    "required_fields": ["core_mechanic", "player_goal", "combat_system", "run_structure", "permanent_progression"],
    "optional_fields": ["control_scheme", "randomness_element"],
    "missing_required": []
}
```

### 필수 항목 추출 실패 시

```json
{
    "elements": {
        "core_mechanic": "힐링 게임플레이",
        "player_goal": null,
        "...": "..."
    },
    "required_fields": ["core_mechanic", "player_goal"],
    "optional_fields": ["..."],
    "missing_required": ["player_goal"]
}
```

→ 프론트에서 `missing_required`에 있는 항목은 직접 입력 강제

---

## 검증 로직

### 무의미한 추출 필터링

```python
GENERIC_PHRASES = [
    "게임 플레이", "재미있는 경험", "다양한 콘텐츠", 
    "게임을 즐기세요", "플레이어", "게임", "재미"
]

def validate_element(value: str) -> bool:
    if not value:
        return False
    if len(value) < 2:
        return False
    if value in GENERIC_PHRASES:
        return False
    return True
```

### 필수 항목 체크

```python
def check_missing_required(elements: dict, required_fields: list) -> list:
    missing = []
    for field in required_fields:
        if not validate_element(elements.get(field)):
            missing.append(field)
    return missing
```

---

## LLM 프롬프트 템플릿

```python
def build_extraction_prompt(game_name: str, genres: list, game_description: str, 
                            required_fields: list, optional_fields: list) -> str:
    
    required_info = "\n".join([
        f"- {ELEMENT_DEFINITIONS[f]['name_ko']} ({f}): {ELEMENT_DEFINITIONS[f]['description']}. 예시: {', '.join(ELEMENT_DEFINITIONS[f]['examples'])}"
        for f in required_fields
    ])
    
    optional_info = "\n".join([
        f"- {ELEMENT_DEFINITIONS[f]['name_ko']} ({f}): {ELEMENT_DEFINITIONS[f]['description']}. 예시: {', '.join(ELEMENT_DEFINITIONS[f]['examples'])}"
        for f in optional_fields
    ]) if optional_fields else "없음"
    
    return f"""다음 게임 정보를 분석하여 핵심 요소를 추출해주세요.

[게임 정보]
- 게임명: {game_name}
- 장르: {', '.join(genres)}
- 설명: {game_description}

[필수 추출 항목]
반드시 추출해야 합니다. 명시적으로 언급되지 않았다면 설명에서 합리적으로 추론하세요.
{required_info}

[선택 추출 항목]
명시적으로 언급된 경우에만 추출하세요. 없으면 null로 표시하세요.
{optional_info}

[규칙]
1. 추측이나 일반적인 표현(예: "재미있는 게임플레이")은 금지
2. 게임 설명에 실제로 근거가 있는 내용만 작성
3. 각 항목은 한국어로 간결하게 (20자 이내 권장)
4. JSON 형식으로만 응답

[응답 형식]
{{
    "core_mechanic": "...",
    "player_goal": "...",
    ...
}}
"""
```

---

## 참고: 추출 결과 활용 (이후 단계)

추출된 요소는 질문 템플릿에 채워넣어 사용:

```python
QUESTION_TEMPLATES = [
    "[core_mechanic]이 직관적으로 느껴졌나요?",
    "[player_goal]를 달성하는 과정이 재미있었나요?",
    "[combat_system]의 타격감이 만족스러웠나요?",
    "[progression_system]이 플레이 동기를 부여했나요?",
    # ...
]

# 예시 출력
# "핵앤슬래시 전투와 스킬 조합이 직관적으로 느껴졌나요?"
# "던전 최하층 도달을 달성하는 과정이 재미있었나요?"
```
