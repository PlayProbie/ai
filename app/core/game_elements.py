"""
게임 요소 정의 및 유틸리티 함수

이 모듈은 게임 핵심 요소 추출에 필요한:
- ELEMENT_DEFINITIONS: 요소별 정의
- GENRE_ELEMENT_MAPPING: 장르별 요소 매핑
- GENERIC_PHRASES: 필터링할 일반 문구
- build_extraction_prompt(): 추출 프롬프트 생성 함수
를 포함합니다.
"""

from app.core.prompts import GAME_ELEMENT_EXTRACTION_PROMPT

# =============================================================================
# 요소 정의 (Element Definitions)
# =============================================================================

ELEMENT_DEFINITIONS = {
    # === 공통 필수 ===
    "core_mechanic": {
        "name": "핵심 메카닉",
        "description": "플레이어가 반복적으로 수행하는 핵심 행동",
        "examples": ["타워 배치", "카드 조합", "점프/회피", "자원 수집", "대화 선택"],
    },
    "player_goal": {
        "name": "플레이어 목표",
        "description": "플레이어가 달성하려는 주요 목표",
        "examples": ["스테이지 클리어", "생존", "퍼즐 해결", "영토 확장", "엔딩 도달"],
    },
    # === 액션 ===
    "combat_system": {
        "name": "전투 시스템",
        "description": "전투/액션 방식",
        "examples": ["콤보 공격", "회피와 패링", "실시간 전투", "턴제 전투"],
    },
    "control_scheme": {
        "name": "조작 방식",
        "description": "플레이어 입력 방식",
        "examples": ["가상패드", "스와이프", "키보드+마우스", "터치"],
    },
    # === 어드벤처/내러티브 ===
    "narrative": {
        "name": "스토리/세계관",
        "description": "배경 설정과 이야기",
        "examples": ["포스트 아포칼립스", "판타지 왕국", "근미래 디스토피아", "일상 로맨스"],
    },
    "main_character": {
        "name": "주인공/캐릭터",
        "description": "플레이어가 조작하거나 감정이입하는 대상",
        "examples": ["기억 잃은 기사", "고양이 탐정", "평범한 고등학생", "로봇"],
    },
    "exploration_element": {
        "name": "탐험 요소",
        "description": "탐험하는 대상이나 방식",
        "examples": ["오픈월드", "던전 탐사", "숨겨진 방", "미지의 행성"],
    },
    # === 시뮬레이션 ===
    "simulation_target": {
        "name": "시뮬레이션 대상",
        "description": "무엇을 시뮬레이션하는지",
        "examples": ["농장 경영", "도시 건설", "병원 운영", "연애", "요리"],
    },
    "management_element": {
        "name": "관리 요소",
        "description": "관리해야 하는 것",
        "examples": ["재정", "직원", "시간", "관계", "자원"],
    },
    # === 퍼즐 ===
    "puzzle_mechanic": {
        "name": "퍼즐 방식",
        "description": "퍼즐의 핵심 메카닉",
        "examples": ["3매치", "물리 퍼즐", "논리 추론", "숨은그림찾기", "탈출"],
    },
    # === 전략 ===
    "decision_type": {
        "name": "의사결정 요소",
        "description": "전략적으로 고민하는 것",
        "examples": ["유닛 배치", "자원 분배", "타이밍 선택", "기술 연구 순서"],
    },
    "resource_system": {
        "name": "자원 시스템",
        "description": "관리하는 자원 종류",
        "examples": ["골드", "마나", "식량", "인구", "에너지"],
    },
    # === RPG ===
    "progression_system": {
        "name": "성장 시스템",
        "description": "캐릭터/플레이어 성장 방식",
        "examples": ["레벨업", "스킬트리", "장비 강화", "직업 전직", "스탯 분배"],
    },
    # === 아케이드 ===
    "score_system": {
        "name": "스코어 시스템",
        "description": "점수 획득 방식",
        "examples": ["콤보 보너스", "시간 보너스", "퍼펙트 클리어", "멀티플라이어"],
    },
    "difficulty_curve": {
        "name": "난이도 곡선",
        "description": "난이도 상승 방식",
        "examples": ["스테이지별 상승", "무한 모드", "적응형 난이도"],
    },
    # === 호러 ===
    "horror_element": {
        "name": "공포 연출 방식",
        "description": "공포를 주는 방식",
        "examples": ["점프스케어", "심리적 공포", "추격전", "고어", "언캐니"],
    },
    "atmosphere": {
        "name": "분위기",
        "description": "게임의 무드/톤",
        "examples": ["어둡고 습한", "긴장감", "고립감", "불안함"],
    },
    # === 슈팅 ===
    "shooting_mechanic": {
        "name": "슈팅 방식",
        "description": "슈팅 시점과 방식",
        "examples": ["FPS", "TPS", "탑다운 슈터", "탄막 슈팅", "레일 슈터"],
    },
    "weapon_variety": {
        "name": "무기 종류",
        "description": "사용 가능한 무기들",
        "examples": ["총기류", "마법", "근접무기", "폭발물", "탈것 무기"],
    },
    # === 비주얼 노벨 ===
    "choice_system": {
        "name": "선택지 시스템",
        "description": "스토리 분기 방식",
        "examples": ["대화 선택지", "행동 선택", "멀티 엔딩", "호감도 시스템"],
    },
    # === 로그라이크 ===
    "run_structure": {
        "name": "런 구조",
        "description": "한 판의 진행 방식",
        "examples": ["층별 진행", "스테이지 선택", "시간 제한", "방 클리어"],
    },
    "permanent_progression": {
        "name": "영구 성장 요소",
        "description": "죽어도 유지되는 것",
        "examples": ["메타 화폐", "영구 업그레이드", "해금 캐릭터", "도감"],
    },
    "randomness_element": {
        "name": "랜덤 요소",
        "description": "매 런마다 바뀌는 것",
        "examples": ["맵 구조", "아이템 드랍", "이벤트", "적 배치"],
    },
    # === 스포츠 ===
    "sport_type": {
        "name": "종목",
        "description": "스포츠 종류",
        "examples": ["축구", "농구", "야구", "골프", "테니스", "레이싱"],
    },
    "play_mode": {
        "name": "플레이 모드",
        "description": "게임 모드",
        "examples": ["시즌 모드", "커리어", "멀티플레이", "토너먼트", "연습"],
    },
    # === 리듬 ===
    "rhythm_system": {
        "name": "리듬 시스템",
        "description": "노트/판정 방식",
        "examples": ["떨어지는 노트", "원형 노트", "롱노트", "슬라이드", "플릭"],
    },
    "music_genre": {
        "name": "음악 장르",
        "description": "수록곡 장르",
        "examples": ["K-POP", "EDM", "클래식", "애니송", "오리지널"],
    },
    "input_method": {
        "name": "입력 방식",
        "description": "플레이어 입력 방법",
        "examples": ["터치", "키보드", "컨트롤러", "모션"],
    },
    # === 대전 ===
    "fighting_system": {
        "name": "대전 시스템",
        "description": "대전 방식",
        "examples": ["1:1 격투", "팀 대전", "카드 배틀", "자동 배틀"],
    },
    "character_roster": {
        "name": "캐릭터 로스터",
        "description": "선택 가능 캐릭터 구성",
        "examples": ["20명의 파이터", "속성별 캐릭터", "클래스별 영웅"],
    },
    # === 캐주얼 ===
    "session_length": {
        "name": "한 판 길이",
        "description": "평균 플레이 시간",
        "examples": ["1분", "3분", "5분", "무제한"],
    },
}


# =============================================================================
# 장르별 요소 매핑 (Genre-Element Mapping)
# =============================================================================

GENRE_ELEMENT_MAPPING = {
    "_common": {"required": ["core_mechanic", "player_goal"], "optional": []},
    "액션": {"required": ["combat_system"], "optional": ["control_scheme"]},
    "어드벤처": {
        "required": ["narrative"],
        "optional": ["main_character", "exploration_element"],
    },
    "시뮬레이션": {"required": ["simulation_target"], "optional": ["management_element"]},
    "퍼즐": {"required": ["puzzle_mechanic"], "optional": []},
    "전략": {"required": ["decision_type"], "optional": ["resource_system"]},
    "RPG": {"required": ["progression_system"], "optional": ["narrative", "main_character"]},
    "아케이드": {"required": ["score_system"], "optional": ["difficulty_curve"]},
    "호러": {"required": ["horror_element"], "optional": ["atmosphere", "narrative"]},
    "슈팅": {"required": ["shooting_mechanic"], "optional": ["weapon_variety"]},
    "비주얼 노벨": {
        "required": ["narrative", "main_character"],
        "optional": ["choice_system"],
    },
    "로그라이크": {
        "required": ["run_structure", "permanent_progression"],
        "optional": ["randomness_element"],
    },
    "스포츠": {"required": ["sport_type", "play_mode"], "optional": []},
    "리듬": {"required": ["rhythm_system"], "optional": ["music_genre", "input_method"]},
    "대전": {"required": ["fighting_system"], "optional": ["character_roster"]},
    "캐주얼": {"required": [], "optional": ["session_length"]},
}


# =============================================================================
# 무의미한 추출 필터링용 일반 문구
# =============================================================================

GENERIC_PHRASES = [
    "게임 플레이",
    "재미있는 경험",
    "다양한 콘텐츠",
    "게임을 즐기세요",
    "플레이어",
    "게임",
    "재미",
]


# =============================================================================
# 유틸리티 함수
# =============================================================================


def build_extraction_prompt(
    game_name: str,
    genres: list[str],
    game_description: str,
    required_fields: list[str],
    optional_fields: list[str],
) -> str:
    """추출 프롬프트 생성

    Args:
        game_name: 게임 이름
        genres: 장르 목록
        game_description: 게임 설명
        required_fields: 필수 추출 필드
        optional_fields: 선택 추출 필드

    Returns:
        포맷팅된 추출 프롬프트
    """
    required_info = "\n".join(
        [
            f"- {ELEMENT_DEFINITIONS[f]['name']} ({f}): {ELEMENT_DEFINITIONS[f]['description']}. 예시: {', '.join(ELEMENT_DEFINITIONS[f]['examples'])}"
            for f in required_fields
            if f in ELEMENT_DEFINITIONS
        ]
    )

    optional_info = (
        "\n".join(
            [
                f"- {ELEMENT_DEFINITIONS[f]['name']} ({f}): {ELEMENT_DEFINITIONS[f]['description']}. 예시: {', '.join(ELEMENT_DEFINITIONS[f]['examples'])}"
                for f in optional_fields
                if f in ELEMENT_DEFINITIONS
            ]
        )
        if optional_fields
        else "없음"
    )

    return GAME_ELEMENT_EXTRACTION_PROMPT.format(
        game_name=game_name,
        genres=", ".join(genres),
        game_description=game_description,
        required_info=required_info,
        optional_info=optional_info,
    )
