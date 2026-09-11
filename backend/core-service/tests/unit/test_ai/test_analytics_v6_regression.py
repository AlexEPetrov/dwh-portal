from domains.ai.models.conversation_state_v6 import ConversationSlotsV6, ConversationStateV6
from domains.ai.models.turn_delta_v6 import TurnDeltaV6, TurnSlotUpdatesV6
from domains.ai.registry.metrics import AnalyticsRegistry
from domains.ai.rendering.clarification_renderer_v6 import ClarificationRendererV6
from domains.ai.routing.rules.short_slot_answer_rule import ShortSlotAnswerRule
from domains.ai.routing.rules.slot_options_rule import SlotOptionsRule
from domains.ai.routing.turn_context import TurnContext
from domains.ai.sql.sql_draft_store import SqlDraftStore
from domains.ai.sql.sql_safety_validator import SqlSafetyValidator
from domains.ai.state.response_policy_v6 import ResponsePolicyV6
from domains.ai.workflows.analytics_v6 import AiAnalyticsWorkflowV6


def test_meta_turn_does_not_drop_accumulated_slots() -> None:
    workflow = AiAnalyticsWorkflowV6()
    state = ConversationStateV6(
        active_branch="analytics",
        slots=ConversationSlotsV6(metric_key="revenue_sales_rub", valuation_year=2026),
        unresolved_slots=[],
        is_ready_for_sql=True,
    )
    delta = TurnDeltaV6(turn_kind="meta", confidence=0.9)

    next_state = workflow._reduce_state(state, delta)

    assert next_state.active_branch == "meta"
    assert next_state.slots.metric_key == "revenue_sales_rub"
    assert next_state.slots.valuation_year == 2026


def test_short_slot_reply_recovers_from_unrelated_turn() -> None:
    workflow = AiAnalyticsWorkflowV6()
    state = ConversationStateV6(
        active_branch="analytics",
        slots=ConversationSlotsV6(metric_key=None, valuation_year=2026),
        unresolved_slots=["metric_key"],
        is_ready_for_sql=False,
    )
    parsed = TurnDeltaV6(turn_kind="unrelated", confidence=0.7)

    recovered = workflow._recover_slot_answer_turn("выручку", state, parsed)

    assert recovered is not None
    assert recovered.turn_kind == "analytics_update"
    assert recovered.slot_updates.metric_key == "revenue_sales_rub"


def test_meta_recheck_accepts_paraphrased_capability_prompt() -> None:
    workflow = AiAnalyticsWorkflowV6()

    def _fake_ollama_chat(_messages: list[dict[str, str]], timeout_sec: int = 12) -> str:
        _ = timeout_sec
        return '{"is_meta": true, "confidence": 0.88}'

    workflow._ollama_chat = _fake_ollama_chat  # type: ignore[method-assign]

    assert workflow._llm_meta_recheck("объясни, что вообще можно у тебя спросить по этим данным")


def test_sql_draft_store_rejects_wrong_draft_id() -> None:
    store = SqlDraftStore()

    stored = store.create("SELECT 1")

    assert store.resolve("wrong-id", stored.sql) is None
    assert store.resolve(stored.draft_id, stored.sql) is not None


def test_sql_safety_validator_rejects_mutating_sql() -> None:
    validator = SqlSafetyValidator()

    violations = validator.validate("SELECT 1; DELETE FROM simulation_data")

    assert violations


def test_predict_year_creates_metric_pending_clarification() -> None:
    workflow = AiAnalyticsWorkflowV6()

    state = workflow._reduce_state(
        ConversationStateV6(),
        TurnDeltaV6(
            turn_kind="analytics_update",
            slot_updates=TurnSlotUpdatesV6(valuation_year=2026),
            confidence=0.8,
        ),
    )

    assert state.slots.valuation_year == 2026
    assert state.slots.metric_key is None
    assert state.last_clarification_slot == "metric_key"
    assert state.pending_clarification is not None
    assert state.pending_clarification.slot == "metric_key"


def test_slot_options_rule_keeps_context_for_metric_question() -> None:
    ctx = TurnContext(
        message="а какие есть?",
        normalized_message="а какие есть",
        history=[],
        state=ConversationStateV6(
            slots=ConversationSlotsV6(valuation_year=2026),
            unresolved_slots=["metric_key"],
            last_clarification_slot="metric_key",
        ),
        registry=AnalyticsRegistry(),
    )

    delta = SlotOptionsRule().match(ctx)

    assert delta is not None
    assert delta.turn_kind == "meta"
    assert delta.meta_request is not None
    assert delta.meta_request.related_slot == "metric_key"


def test_short_slot_answer_rule_preserves_year_context() -> None:
    ctx = TurnContext(
        message="выручку",
        normalized_message="выручку",
        history=[],
        state=ConversationStateV6(
            slots=ConversationSlotsV6(valuation_year=2026),
            unresolved_slots=["metric_key"],
            last_clarification_slot="metric_key",
        ),
        registry=AnalyticsRegistry(),
    )

    delta = ShortSlotAnswerRule().match(ctx)

    assert delta is not None
    assert delta.turn_kind == "analytics_update"
    assert delta.slot_updates.metric_key == "revenue_sales_rub"


def test_response_policy_prefers_meta_answer_for_slot_options() -> None:
    state = ConversationStateV6(
        active_branch="meta",
        slots=ConversationSlotsV6(valuation_year=2026),
        unresolved_slots=["metric_key"],
        is_ready_for_sql=False,
    )
    delta = TurnDeltaV6(turn_kind="meta", confidence=0.9)

    decision = ResponsePolicyV6().decide(state, delta)

    assert decision.output_mode == "meta_answer"


def test_response_policy_requires_pending_confirmation_for_execution() -> None:
    state = ConversationStateV6(active_branch="analytics")
    delta = TurnDeltaV6(turn_kind="confirmation", confidence=0.9)

    decision = ResponsePolicyV6().decide(state, delta)

    assert decision.output_mode == "clarification"


def test_clarification_renderer_provides_metric_options() -> None:
    renderer = ClarificationRendererV6()
    state = ConversationStateV6(unresolved_slots=["metric_key"])

    pending = renderer.build(state)

    assert pending.slot == "metric_key"
    assert pending.options
    assert "метрику" in pending.question.lower()


def test_confirmation_decision_executes_only_with_pending_confirmation() -> None:
    state = ConversationStateV6.model_validate(
        {
            "pending_confirmation": {
                "kind": "execute_sql",
                "draft_id": "draft-1",
                "text": "Подтвердите выполнение SQL черновика",
            }
        }
    )
    delta = TurnDeltaV6(turn_kind="confirmation", confidence=0.95)

    decision = ResponsePolicyV6().decide(state, delta)

    assert decision.output_mode == "execute_pending_sql"
