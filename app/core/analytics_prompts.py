"""Analytics 분석용 프롬프트"""

CLUSTER_ANALYSIS_SYSTEM_PROMPT = """당신은 게임 플레이테스트 피드백 분석 전문가입니다.
사용자 답변들을 분석하여 감정을 파악합니다."""

# 답변 목록 {answers}에는 MMR로 선정된 대표 답변이 최대 5개 포함됩니다.
SENTIMENT_ANALYSIS_PROMPT = """## 답변 목록
{answers}

## 작업
위 답변들의 공통된 감정과 의견을 분석하여, GEQ(Game Experience Questionnaire) 7가지 차원 각각에 대해 0~100 점수를 매기세요.

### GEQ 7가지 감정 차원
1. **성취감 (competence)**: 게임을 잘 다루고 있다, 컨트롤이 쉽다, 숙련됨
2. **몰입감 (immersion)**: 게임 세계에 빠져들었다, 스토리/비주얼에 흡입됨
3. **집중도 (flow)**: 시간 가는 줄 몰랐다, 완전히 집중했다, 다른 생각이 안 남
4. **긴장감 (tension)**: 손에 땀을 쥐었다, 스릴 있다, 긴박하다
5. **도전감 (challenge)**: 어렵지만 해볼 만하다, 노력이 필요하다, 정신적으로 자극됨
6. **즐거움 (positive_affect)**: 재미있다, 기분이 좋다, 만족스럽다
7. **불쾌함 (negative_affect)**: 짜증난다, 지루하다, 피곤하다, 불쾌하다

### 출력 형식 (JSON)
{{
  "summary": "이 답변들을 대표하는 한 줄 요약",
  "satisfaction": 0~100 (전반적 만족도),
  "emotion_detail": "구체적인 감정 맥락 1-2문장",
  "geq_scores": {{
    "competence": 0~100,
    "immersion": 0~100,
    "flow": 0~100,
    "tension": 0~100,
    "challenge": 0~100,
    "positive_affect": 0~100,
    "negative_affect": 0~100
  }}
}}

JSON만 출력하세요.
"""

# 이상치 목록 {answers}에는 MMR로 선정된 대표 이상치가 최대 10개 포함됩니다.
OUTLIER_ANALYSIS_PROMPT = """## 이상치 답변 목록
{answers}

## 작업
위 답변들은 주류 의견에 포함되지 않은 소수 의견입니다.
이들에서 발견되는 특이점이나 잠재적 문제점을 분석하세요.

### 출력 형식 (JSON)
{{
  "summary": "이 답변들에서 발견된 특이점 한 줄 요약"
}}

JSON만 출력하세요.
"""

# 클러스터 요약 {cluster_summaries}에는 최대 5개 클러스터의 요약이 포함됩니다.
META_SUMMARY_PROMPT = """## 클러스터별 요약
{cluster_summaries}

## 작업
위 클러스터 요약들을 종합하여, 전체 설문 응답에서 드러나는 핵심 인사이트를 한 문장으로 작성하세요.

### 출력 형식 (JSON)
{{
  "meta_summary": "전체 응답을 종합한 핵심 인사이트 한 문장"
}}

JSON만 출력하세요.
"""
