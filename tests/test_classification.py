"""응답 분류 시스템 테스트 스크립트"""

import asyncio

from app.services.bedrock_service import BedrockService


async def test_classify_answer():
    """classify_answer_async 테스트"""
    service = BedrockService()

    # 테스트 케이스들
    test_cases = [
        # (질문, 답변, 예상 결과)
        ("게임이 재미있었나요?", "좋았어요", "VALID + EMPTY"),
        (
            "게임이 재미있었나요?",
            "2스테이지 보스전에서 회피할 때 10번 넘게 죽었어요",
            "VALID + GROUNDED",
        ),
        (
            "게임이 재미있었나요?",
            "다크소울 같은 느낌이었는데 거기보단 덜 답답했어요",
            "VALID + FLOATING",
        ),
        (
            "게임이 재미있었나요?",
            "2스테이지 보스가 3페이즈로 바뀔 때 패턴이 완전히 달라져서 처음엔 당황했는데, 다크소울 느낌이었어요",
            "VALID + FULL",
        ),
        ("게임이 재미있었나요?", "점심 뭐 먹지", "OFF_TOPIC"),
        ("게임이 재미있었나요?", "모르겠어요", "REFUSAL"),
        ("게임이 재미있었나요?", "ㅁㄴㅇㄹㅁㄴㅇㄹ", "UNINTELLIGIBLE"),
    ]

    print("=" * 60)
    print("응답 분류 시스템 테스트")
    print("=" * 60)

    for question, answer, expected in test_cases:
        print(f"\n질문: {question}")
        print(f"답변: {answer}")
        print(f"예상: {expected}")

        result = await service.classify_answer_async(
            current_question=question,
            user_answer=answer,
        )

        print(f"결과: validity={result.validity.value}", end="")
        if result.quality:
            print(f", quality={result.quality.value}")
            print(f"       thickness={result.thickness}, richness={result.richness}")
        else:
            print(f"\n       reason={result.validity_reason}")
        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(test_classify_answer())
