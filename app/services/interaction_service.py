"""
설문/인터뷰 상호작용 서비스 (LangGraph 기반)
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from app.agents.survey_workflow import build_survey_workflow
from app.schemas.survey import (
    InterviewPhase,
    SurveyAction,
    SurveyInteractionRequest,
)

if TYPE_CHECKING:
    from app.services.bedrock_service import BedrockService

logger = logging.getLogger(__name__)


class InteractionService:
    """설문/인터뷰 상호작용 서비스 (LangGraph Wrapper)"""

    def __init__(self, bedrock_service: "BedrockService"):
        self.bedrock_service = bedrock_service
        self.workflow = build_survey_workflow(bedrock_service)

    async def stream_interaction(
        self, request: SurveyInteractionRequest
    ) -> AsyncGenerator[str, None]:
        """
        SSE 스트리밍으로 답변 분석 및 응답 생성 (실시간 astream_events 기반).
        """
        try:
            logger.info(f"🚀 stream_interaction 시작: session={request.session_id}")
            yield self._sse_event("start", {"status": "processing", "phase": "main"})

            input_state = self._build_input_state(request)
            logger.info(
                f"📋 입력 상태 구성 완료: question={request.current_question[:30]}..."
            )

            # 상태 누적용 변수
            final_state = {}
            message_buffer = []

            # 핵심: astream_events로 LLM 토큰 스트리밍 캡처
            logger.info("🔄 astream_events 시작...")
            event_count = 0
            async for event in self.workflow.astream_events(input_state, version="v2"):
                try:
                    event_count += 1
                    event_kind = event.get("event", "")
                    event_name = event.get("name", "")

                    # 디버그 로깅 (처음 몇 개 이벤트만)
                    if event_count <= 10:
                        logger.debug(
                            f"📨 Event #{event_count}: kind={event_kind}, name={event_name}"
                        )

                    # 커스텀 스트리밍 이벤트 (명시적으로 dispatch된 토큰만 스트리밍하여 중복 방지 및 제어권 확보)
                    if event_kind == "on_custom_event" and event_name == "probe_stream":
                        chunk_content = event.get("data", {}).get("content", "")
                        if chunk_content:
                            message_buffer.append(chunk_content)
                            yield self._sse_event(
                                "continue", {"content": chunk_content, "q_type": "TAIL"}
                            )

                    # 노드 완료 시 SSE 이벤트 전송
                    elif event_kind == "on_chain_end":
                        output = event.get("data", {}).get("output", {})

                        if isinstance(output, dict):
                            final_state.update(output)

                        # 노드별 이벤트 매핑
                        sse_event = self._map_node_to_sse_event(
                            event_name, output, final_state
                        )
                        if sse_event:
                            yield sse_event

                        # 메시지 생성 완료 이벤트 (generate_probe 또는 generate_retry 노드 완료 시)
                        if event_name in ["generate_probe", "generate_retry"]:
                            logger.info(
                                f"✅ 노드 완료: {event_name}, buffer_len={len(message_buffer)}"
                            )

                            # generate_retry는 LLM을 사용하지 않으므로 수동 스트리밍
                            if event_name == "generate_retry" and not message_buffer:
                                message = final_state.get("generated_message", "")
                                if message:
                                    for char in message:
                                        # Retry 생성은 RETRY 타입 명시
                                        yield self._sse_event(
                                            "continue",
                                            {"content": char, "q_type": "RETRY"},
                                        )

                            complete_event = self._emit_message_complete(
                                event_name, final_state, message_buffer
                            )
                            if complete_event:
                                yield complete_event
                            message_buffer = []

                except Exception as event_error:
                    logger.warning(f"⚠️ Event 처리 오류 (계속 진행): {event_error}")
                    continue

            # 최종 done 이벤트
            logger.info(f"🏁 스트리밍 완료, 총 이벤트 수: {event_count}")
            yield self._build_done_event(final_state)

        except GeneratorExit:
            logger.warning("⚠️ 클라이언트가 연결을 종료함")
        except Exception as e:
            logger.error(f"Streaming Error: {e}", exc_info=True)
            yield self._sse_event("error", {"message": str(e)})

    def _build_input_state(self, request: SurveyInteractionRequest) -> dict:
        """LangGraph 입력 상태 구성"""
        return {
            "session_id": request.session_id,
            "user_answer": request.user_answer,
            "current_question": request.current_question,
            "game_info": request.game_info,
            "conversation_history": request.conversation_history,
            "current_tail_count": request.current_tail_count
            or request.probe_count
            or 0,
            "max_tail_questions": request.max_tail_questions or 2,
            "retry_count": request.retry_count or 0,
            "current_question_order": request.current_question_order,
            "total_questions": request.total_questions,
        }

    def _map_node_to_sse_event(
        self, node_name: str, output: dict, final_state: dict
    ) -> str | None:
        """노드 완료 시 SSE 이벤트 매핑"""
        # [NEW] 병렬 실행 노드 처리 -> 기존 이벤트 2개 분리 전송
        if node_name == "evaluate_parallel":
            events = []

            # 1. Validity Result
            if output.get("validity"):
                events.append(
                    self._sse_event(
                        "validity_result",
                        {
                            "validity": output["validity"].value,
                            "confidence": output.get("validity_confidence", 0),
                            "reason": output.get("validity_reason", ""),
                            "source": output.get("validity_source", ""),
                        },
                    )
                )

            # 2. Quality Result
            if output.get("quality"):
                events.append(
                    self._sse_event(
                        "quality_result",
                        {
                            "quality": output["quality"].value,
                            "thickness": output.get("thickness"),
                            "thickness_evidence": output.get("thickness_evidence", []),
                            "richness": output.get("richness"),
                            "richness_evidence": output.get("richness_evidence", []),
                        },
                    )
                )

            return "".join(events) if events else None

        if node_name in ["pass_to_next", "generate_probe", "generate_retry"]:
            action = output.get("action", SurveyAction.PASS_TO_NEXT)
            action_value = action.value if hasattr(action, "value") else str(action)
            return self._sse_event(
                "analyze_answer",
                {
                    "action": action_value,
                    "analysis": output.get("analysis", ""),
                    "should_end": output.get("should_end", False),
                    "end_reason": output.get("end_reason").value
                    if output.get("end_reason")
                    else None,
                    "probe_type": output.get("probe_type"),
                },
            )

        if node_name == "generate_reaction" and output.get("reaction"):
            return self._sse_event("reaction", {"reaction_text": output["reaction"]})

        return None

    def _emit_message_complete(
        self, node_name: str, final_state: dict, message_buffer: list
    ) -> str:
        """메시지 생성 완료 이벤트 생성"""
        message = "".join(message_buffer).strip() or final_state.get(
            "generated_message", ""
        )

        if node_name == "generate_retry":
            return self._sse_event(
                "retry_request",
                {
                    "message": message,
                    "followup_type": final_state.get("followup_type", "clarify"),
                },
            )

        if node_name == "generate_probe":
            return self._sse_event(
                "generate_tail_complete",
                {
                    "message": message,
                    "tail_question_count": (
                        final_state.get("current_tail_count", 0) or 0
                    )
                    + 1,
                    "probe_type": final_state.get("probe_type"),
                },
            )

        return ""

    def _build_done_event(self, final_state: dict) -> str:
        """최종 done 이벤트 생성"""
        action = final_state.get("action", SurveyAction.PASS_TO_NEXT)
        action_value = action.value if hasattr(action, "value") else str(action)

        return self._sse_event(
            "done",
            {
                "status": "completed",
                "action": action_value,
                "phase": InterviewPhase.MAIN.value,
                "question_text": final_state.get("generated_message"),
                "should_end": final_state.get("should_end", False),
                "end_reason": final_state.get("end_reason").value
                if final_state.get("end_reason")
                else None,
                "validity": final_state["validity"].value
                if final_state.get("validity")
                else None,
                "quality": final_state["quality"].value
                if final_state.get("quality")
                else None,
            },
        )

    def _sse_event(self, event_type: str, data: dict) -> str:
        """SSE 이벤트 포맷 생성"""
        payload = {"event": event_type, "data": data}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
