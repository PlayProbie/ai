"""Task 2: 전체 플로우 통합 테스트 (LLM 호출 포함)"""

import asyncio
from datetime import datetime, timezone

from app.services.bedrock_service import BedrockService


async def test_full_flow():
    """전체 플로우 테스트: LLM 연결 → 분류 → 프로빙 판단"""
    
    print("=" * 70)
    print("🧪 전체 플로우 통합 테스트")
    print("=" * 70)
    
    service = BedrockService()
    print("✅ 1. BedrockService 초기화 성공")
    
    # -------------------------------------------------------
    # 테스트 케이스 정의
    # -------------------------------------------------------
    test_cases = [
        {
            "name": "EMPTY 응답 (짧은 답변)",
            "question": "게임이 재미있었나요?",
            "answer": "좋았어요",
            "expected_quality": "EMPTY",
        },
        {
            "name": "GROUNDED 응답 (상황만)",
            "question": "어려웠던 부분이 있었나요?",
            "answer": "2스테이지 보스전에서 회피할 때 10번 넘게 죽었어요",
            "expected_quality": "GROUNDED",
        },
        {
            "name": "FLOATING 응답 (해석만)",
            "question": "게임이 재미있었나요?",
            "answer": "전투가 긴장감 있고 전략적이라서 몰입됐어요. 다크소울 같은 느낌이었어요",
            "expected_quality": "FLOATING",
        },
        {
            "name": "FULL 응답 (상황 + 해석)",
            "question": "게임이 재미있었나요?",
            "answer": "2스테이지 보스가 3페이즈로 바뀔 때 패턴이 완전히 달라져서 처음엔 당황했는데, 다크소울 느낌이었어요",
            "expected_quality": "FULL",
        },
        {
            "name": "REFUSAL 응답 (거부)",
            "question": "게임이 재미있었나요?",
            "answer": "모르겠어요",
            "expected_validity": "REFUSAL",
        },
    ]
    
    # -------------------------------------------------------
    # 2. 응답 분류 테스트
    # -------------------------------------------------------
    print("\n" + "-" * 70)
    print("📋 2. 응답 분류 테스트 (classify_answer_async)")
    print("-" * 70)
    
    for i, tc in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {tc['name']}")
        print(f"   질문: {tc['question']}")
        print(f"   답변: {tc['answer'][:50]}...")
        
        try:
            result = await service.classify_answer_async(
                current_question=tc["question"],
                user_answer=tc["answer"],
            )
            
            validity = result.validity.value
            quality = result.quality.value if result.quality else None
            
            # 기대값 확인
            if "expected_validity" in tc:
                expected = tc["expected_validity"]
                status = "✅" if validity == expected else "⚠️"
                print(f"   {status} validity: {validity} (기대: {expected})")
            else:
                expected = tc["expected_quality"]
                status = "✅" if quality == expected else "⚠️"
                print(f"   {status} quality: {quality} (기대: {expected})")
                print(f"      thickness: {result.thickness}, richness: {result.richness}")
            
        except Exception as e:
            print(f"   ❌ 에러: {e}")
    
    # -------------------------------------------------------
    # 3. 피로도-커버리지 판단 테스트
    # -------------------------------------------------------
    print("\n" + "-" * 70)
    print("📋 3. 피로도-커버리지 판단 테스트 (decide_probe_action_async)")
    print("-" * 70)
    
    probe_test_cases = [
        {
            "name": "피로↓ + 커버↓ → 프로빙 지속",
            "question": "게임이 재미있었나요?",
            "quality": "EMPTY",
            "probe_count": 0,
            "history": [{"question": "게임이 재미있었나요?", "answer": "좋았어요"}],
            "expected_action": "CONTINUE_PROBE",
        },
        {
            "name": "피로↓ + 커버↑ → 다음 질문",
            "question": "게임이 재미있었나요?",
            "quality": "FULL",
            "probe_count": 1,
            "history": [
                {"question": "게임이 재미있었나요?", "answer": "2스테이지 보스전이 정말 재미있었어요"},
                {"question": "어떤 부분이 재미있었나요?", "answer": "패턴을 익히는 과정이 다크소울 느낌이었어요"},
            ],
            "expected_action": "NEXT_QUESTION",
        },
    ]
    
    for i, tc in enumerate(probe_test_cases, 1):
        print(f"\n[{i}/{len(probe_test_cases)}] {tc['name']}")
        
        try:
            result = await service.decide_probe_action_async(
                current_question=tc["question"],
                answer_quality=tc["quality"],
                probe_count=tc["probe_count"],
                conversation_history=tc["history"],
            )
            
            action = result.action.value
            expected = tc["expected_action"]
            status = "✅" if action == expected else "⚠️"
            
            print(f"   {status} action: {action} (기대: {expected})")
            print(f"      fatigue: {result.fatigue.value}, coverage: {result.coverage.value}")
            print(f"      reason: {result.reason[:50]}...")
            
        except Exception as e:
            print(f"   ❌ 에러: {e}")
    
    # -------------------------------------------------------
    # 4. 프로빙 질문 생성 테스트
    # -------------------------------------------------------
    print("\n" + "-" * 70)
    print("📋 4. 프로빙 질문 생성 테스트 (generate_probe_question_async)")
    print("-" * 70)
    
    try:
        probe_question = await service.generate_probe_question_async(
            current_question="게임이 재미있었나요?",
            user_answer="좋았어요",
            answer_quality="EMPTY",
        )
        
        print(f"   ✅ 프로빙 질문 생성됨:")
        print(f"      \"{probe_question}\"")
        
    except Exception as e:
        print(f"   ❌ 에러: {e}")
    
    # -------------------------------------------------------
    # 완료
    # -------------------------------------------------------
    print("\n" + "=" * 70)
    print("🎉 전체 플로우 테스트 완료!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_full_flow())
