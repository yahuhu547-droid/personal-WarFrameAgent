import asyncio
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from warframe_agent.chat import ChatAgent
from warframe_agent.goals import create_goal, format_goal_criteria_summary, parse_goal_description_criteria
from warframe_agent.memory import AgentMemory, FissureAlert
from warframe_agent.opportunity_lookup import OpportunityLookupStore
from warframe_agent.trading_memory import OpportunityOutcomeMemory, TradingMemoryDB


class MemoryCommandResolver:
    aliases = {"充沛": "arcane_energize"}
    generated_aliases = {}

    def resolve(self, name):
        if name == "充沛":
            class Result:
                item_id = "arcane_energize"
            return Result()
        raise LookupError(name)


class FakeOpportunityOutcomeDB:
    def __init__(self, records):
        self.records = records
        self.requested_limit = None

    def get_opportunity_outcomes(self, limit=100, **kwargs):
        self.requested_limit = limit
        return list(self.records)


class FakeGoalTracker:
    def __init__(self, goals=None):
        self.goals = list(goals or [])
        self.outcomes = []

    def add_goal(self, goal):
        self.goals.append(goal)
        return goal

    def get_active_goals(self):
        return [goal for goal in self.goals if goal.status == "active"]

    def update_goal_status(self, goal_id, status):
        for index, goal in enumerate(self.goals):
            if goal.goal_id == goal_id:
                self.goals[index] = replace(goal, status=status)
                return True
        return False

    def generate_review(self, goal_id):
        for goal in self.goals:
            if goal.goal_id == goal_id:
                return f"fake review: {goal.description} {goal.status}"
        return "目标不存在。"

    def format_goals_status(self):
        return "fake goal status"


def _sqlite_outcome(index: int = 0) -> OpportunityOutcomeMemory:
    return OpportunityOutcomeMemory(
        id=index,
        timestamp="2026-05-26T00:00:00",
        opportunity_id=f"OPSECRET{index}",
        item_name="arcane_energize",
        source="mod_flipper",
        strategy="arcane_rank0_to_max",
        status="completed",
        expected_profit=30,
        actual_profit=40,
        user_feedback="good",
        metadata={"safe_summary": {"roi_pct": 40}},
    )


def _reviewable_trade_plan():
    return {
        "source": "arcane_flip",
        "strategy": "arcane_r0_to_r5",
        "display_name": "Arcane Energize",
        "item_id": "arcane_energize",
        "required_quantity": 21,
        "total_cost": 179,
        "total_revenue": 210,
        "profit": 31,
        "roi_pct": 17.3,
        "risk_level": "medium",
        "profit_bucket": "small",
        "plan_signature": "sig-safe",
        "safe_summary": {
            "source": "arcane_flip",
            "strategy": "arcane_r0_to_r5",
            "item_id": "arcane_energize",
            "required_quantity": 21,
            "total_cost": 179,
            "total_revenue": 210,
            "profit": 31,
            "roi_pct": 17.3,
            "risk_level": "medium",
            "profit_bucket": "small",
            "plan_signature": "sig-safe",
        },
        "buy_steps": [
            {
                "player": "UnsafeSeller",
                "profile_url": "https://warframe.market/profile/UnsafeSeller",
                "whisper": "/w UnsafeSeller hi",
                "unit_price": 9,
                "quantity": 21,
            }
        ],
        "sell_steps": [],
    }


class ChatMemoryCommandTests(unittest.TestCase):
    def test_goal_set_parser_extracts_chinese_budget_profit_timeframe_risk_and_roi(self):
        criteria = parse_goal_description_criteria("一周赚500p，预算300p，低风险，最低ROI 20%")

        self.assertEqual(criteria["target_profit"], 500)
        self.assertEqual(criteria["target_amount"], 500)
        self.assertEqual(criteria["timeframe_days"], 7)
        self.assertEqual(criteria["budget"], 300)
        self.assertEqual(criteria["risk"], "low")
        self.assertEqual(criteria["min_roi"], 20)

        summary = format_goal_criteria_summary(criteria)
        self.assertIn("目标利润 500p", summary)
        self.assertIn("周期 7 天", summary)
        self.assertIn("预算 300p", summary)
        self.assertIn("低风险", summary)
        self.assertIn("最低 ROI 20%", summary)

    def test_goal_set_command_stores_parsed_criteria_without_real_goal_file(self):
        fake_tracker = FakeGoalTracker()
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                reply = agent.answer("/goal set 一周赚500p，预算300p，低风险，最低ROI 20%")

        self.assertEqual(len(fake_tracker.goals), 1)
        goal = fake_tracker.goals[0]
        self.assertEqual(goal.goal_type, "earn_platinum")
        self.assertEqual(goal.description, "一周赚500p，预算300p，低风险，最低ROI 20%")
        self.assertEqual(goal.criteria["target_profit"], 500)
        self.assertEqual(goal.criteria["target_amount"], 500)
        self.assertEqual(goal.criteria["timeframe_days"], 7)
        self.assertEqual(goal.criteria["budget"], 300)
        self.assertEqual(goal.criteria["risk"], "low")
        self.assertEqual(goal.criteria["min_roi"], 20)
        self.assertIn("已解析", reply)
        self.assertIn("目标利润 500p", reply)
        self.assertIn("预算 300p", reply)
        self.assertIn("低风险", reply)

    def test_goal_set_parser_keeps_existing_defaults_when_description_is_plain(self):
        criteria = parse_goal_description_criteria("找高利润倒卖机会")

        self.assertEqual(criteria, {"budget": 500, "min_roi": 10})

    def test_goal_set_command_keeps_legacy_type_for_plain_description(self):
        fake_tracker = FakeGoalTracker()
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                reply = agent.answer("/goal set 找高利润倒卖机会")

        self.assertEqual(len(fake_tracker.goals), 1)
        goal = fake_tracker.goals[0]
        self.assertEqual(goal.goal_type, "maximize_profit")
        self.assertEqual(goal.criteria, {"budget": 500, "min_roi": 10})
        self.assertIn("已创建目标", reply)

    def test_goal_confirmation_prompt_does_not_create_goal_until_user_confirms(self):
        fake_tracker = FakeGoalTracker()
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                reply = agent.answer("帮我制定一周赚500p的计划，预算300p，低风险，不要直接买")

        self.assertEqual(fake_tracker.goals, [])
        self.assertIn("是否创建", reply)
        self.assertIn("确认创建", reply)
        self.assertIn("目标利润 500p", reply)
        self.assertIn("/goal set", reply)

    def test_goal_confirmation_creates_parsed_goal_after_user_confirms(self):
        fake_tracker = FakeGoalTracker()
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "memory.json",
            )
            agent.answer("帮我制定一周赚500p的计划，预算300p，低风险，不要直接买")

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                reply = agent.answer("确认创建")

        self.assertEqual(len(fake_tracker.goals), 1)
        goal = fake_tracker.goals[0]
        self.assertEqual(goal.goal_type, "earn_platinum")
        self.assertEqual(goal.criteria["target_amount"], 500)
        self.assertEqual(goal.criteria["budget"], 300)
        self.assertEqual(goal.criteria["risk"], "low")
        self.assertIn("已创建目标", reply)
        self.assertIn("目标利润 500p", reply)

    def test_goal_confirmation_can_be_cancelled_before_creation(self):
        fake_tracker = FakeGoalTracker()
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "memory.json",
            )
            agent.answer("帮我制定一周赚500p的计划，预算300p，低风险，不要直接买")
            cancel_reply = agent.answer("取消")

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                confirm_reply = agent.answer("确认创建")

        self.assertIn("已取消", cancel_reply)
        self.assertEqual(fake_tracker.goals, [])
        self.assertIn("没有待确认", confirm_reply)

    def test_goal_status_confirmation_prompt_does_not_complete_until_confirmed(self):
        goal = create_goal("earn_platinum", "一周赚500p", criteria={"target_amount": 500})
        fake_tracker = FakeGoalTracker([goal])
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                reply = agent.answer("完成第1个目标")

        self.assertIn("确认完成", reply)
        self.assertIn(goal.goal_id[:6], reply)
        self.assertEqual(fake_tracker.goals[0].status, "active")

    def test_goal_status_confirmation_can_complete_after_user_confirms(self):
        goal = create_goal("earn_platinum", "一周赚500p", criteria={"target_amount": 500})
        fake_tracker = FakeGoalTracker([goal])
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                agent.answer("完成第1个目标")
                reply = agent.answer("确认完成")

        self.assertEqual(fake_tracker.goals[0].status, "achieved")
        self.assertIn("目标已标记为完成", reply)
        self.assertIn("fake review", reply)

    def test_goal_status_confirmation_can_be_cancelled_before_update(self):
        goal = create_goal("earn_platinum", "一周赚500p", criteria={"target_amount": 500})
        fake_tracker = FakeGoalTracker([goal])
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                agent.answer("完成第1个目标")
                reply = agent.answer("取消")

        self.assertEqual(fake_tracker.goals[0].status, "active")
        self.assertIn("已取消", reply)

    def test_goal_status_confirmation_can_abandon_after_user_confirms(self):
        goal = create_goal("earn_platinum", "一周赚500p", criteria={"target_amount": 500})
        fake_tracker = FakeGoalTracker([goal])
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                prompt = agent.answer("放弃第1个目标")
                reply = agent.answer("确认放弃")

        self.assertIn("确认放弃", prompt)
        self.assertEqual(fake_tracker.goals[0].status, "abandoned")
        self.assertIn("已放弃目标", reply)

    def test_goal_status_confirmation_stream_matches_regular_answer(self):
        async def consume(agent):
            chunks = []
            async for chunk in agent.answer_stream("完成第1个目标"):
                chunks.append(chunk)
            return "".join(chunks)

        goal = create_goal("earn_platinum", "一周赚500p", criteria={"target_amount": 500})
        fake_tracker = FakeGoalTracker([goal])
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                router_call=lambda prompt: (_ for _ in ()).throw(AssertionError("router should not be called")),
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                reply = asyncio.run(consume(agent))

        self.assertIn("确认完成", reply)
        self.assertIn(goal.goal_id[:6], reply)
        self.assertEqual(fake_tracker.goals[0].status, "active")

    def test_goal_status_question_does_not_create_pending_update(self):
        goal = create_goal("earn_platinum", "一周赚500p", criteria={"target_amount": 500})
        fake_tracker = FakeGoalTracker([goal])
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                question_reply = agent.answer("完成目标了吗")
                confirm_reply = agent.answer("确认完成")

        self.assertNotIn("确认完成”执行", question_reply)
        self.assertEqual(fake_tracker.goals[0].status, "active")
        self.assertNotIn("目标已标记为完成", confirm_reply)

    def test_goal_status_slash_command_still_updates_immediately(self):
        goal = create_goal("earn_platinum", "一周赚500p", criteria={"target_amount": 500})
        fake_tracker = FakeGoalTracker([goal])
        with tempfile.TemporaryDirectory() as tmp:
            agent = ChatAgent(
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
            )

            with patch("warframe_agent.goals.GoalTracker", return_value=fake_tracker):
                reply = agent.answer(f"/goal done {goal.goal_id[:6]}")

        self.assertEqual(fake_tracker.goals[0].status, "achieved")
        self.assertIn("目标已标记为完成", reply)

    def test_memory_command_can_add_favorite_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("/fav add 充沛")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加收藏", answer)
        self.assertIn("arcane_energize", saved.favorite_items)

    def test_natural_language_favorite_can_add_favorite_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("帮我关注充沛")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加收藏", answer)
        self.assertIn("arcane_energize", saved.favorite_items)

    def test_natural_language_favorite_can_remove_favorite_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )
            agent.answer("帮我关注充沛")

            answer = agent.answer("取消关注充沛")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已移除收藏", answer)
        self.assertNotIn("arcane_energize", saved.favorite_items)

    def test_natural_language_favorite_stream_matches_regular_answer(self):
        async def consume(agent):
            chunks = []
            async for chunk in agent.answer_stream("帮我收藏充沛"):
                chunks.append(chunk)
            return "".join(chunks)

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = asyncio.run(consume(agent))
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加收藏", answer)
        self.assertIn("arcane_energize", saved.favorite_items)

    def test_natural_language_favorite_guards_watchlist_and_question_phrases(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            watch_agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                watchlist={},
                memory_path=memory_path,
            )
            watch_reply = watch_agent.answer("关注列表")
            after_watch = AgentMemory.load(memory_path)

            question_agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )
            question_reply = question_agent.answer("充沛值得关注吗")
            after_question = AgentMemory.load(memory_path)

        self.assertNotIn("已添加收藏", watch_reply)
        self.assertNotIn("已添加收藏", question_reply)
        self.assertEqual(after_watch.favorite_items, [])
        self.assertEqual(after_question.favorite_items, [])

    def test_natural_language_favorite_can_remove_collection_phrase(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )
            agent.answer("帮我收藏充沛")

            answer = agent.answer("取消收藏充沛")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已移除收藏", answer)
        self.assertNotIn("arcane_energize", saved.favorite_items)

    def test_natural_language_favorite_guards_price_alert_and_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            alert_answer = agent.answer("充沛低于45p提醒我")
            after_alert = AgentMemory.load(memory_path)
            agent.answer("帮我关注充沛")
            agent.answer("帮我关注充沛")
            after_repeated = AgentMemory.load(memory_path)

        self.assertIn("已添加提醒", alert_answer)
        self.assertEqual(after_alert.favorite_items, [])
        self.assertEqual(after_repeated.favorite_items.count("arcane_energize"), 1)

    def test_memory_command_can_add_alert_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("/alert add 充沛 below 45")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加提醒", answer)
        self.assertEqual(saved.price_alerts[0].item_id, "arcane_energize")
        self.assertEqual(saved.price_alerts[0].price, 45)

    def test_natural_language_price_alert_can_add_below_alert_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("充沛低于45p提醒我")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加提醒", answer)
        self.assertIn("低于 45p", answer)
        self.assertEqual(saved.price_alerts[0].item_id, "arcane_energize")
        self.assertEqual(saved.price_alerts[0].direction, "below")
        self.assertEqual(saved.price_alerts[0].price, 45)

    def test_natural_language_price_alert_can_add_above_alert_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("充沛高于100p通知我")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加提醒", answer)
        self.assertIn("高于 100p", answer)
        self.assertEqual(saved.price_alerts[0].direction, "above")
        self.assertEqual(saved.price_alerts[0].price, 100)

    def test_natural_language_price_alert_can_remove_matching_alert_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )
            agent.answer("充沛低于45p提醒我")

            answer = agent.answer("取消充沛低于45p提醒")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已移除提醒", answer)
        self.assertEqual(saved.price_alerts, [])

    def test_natural_language_price_question_does_not_create_alert_without_reminder_verb(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("充沛低于45p了吗")
            saved = AgentMemory.load(memory_path)

        self.assertNotIn("已添加提醒", answer)
        self.assertEqual(saved.price_alerts, [])

    def test_natural_language_price_alert_stream_matches_regular_answer(self):
        async def consume(agent):
            chunks = []
            async for chunk in agent.answer_stream("充沛低于45p提醒我"):
                chunks.append(chunk)
            return "".join(chunks)

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = asyncio.run(consume(agent))
            saved = AgentMemory.load(memory_path)

        self.assertIn("已添加提醒", answer)
        self.assertEqual(saved.price_alerts[0].item_id, "arcane_energize")
        self.assertEqual(saved.price_alerts[0].direction, "below")
        self.assertEqual(saved.price_alerts[0].price, 45)

    def test_natural_language_vague_cancel_does_not_delete_existing_price_alert(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )
            agent.answer("充沛低于45p提醒我")

            answer = agent.answer("取消提醒")
            saved = AgentMemory.load(memory_path)

        self.assertNotIn("已移除提醒", answer)
        self.assertEqual(len(saved.price_alerts), 1)
        self.assertEqual(saved.price_alerts[0].price, 45)

    def test_regular_question_is_saved_into_common_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                model_call=lambda prompt: "测试回复",
                memory_path=memory_path,
            )

            agent.answer("充沛现在价格怎么样")
            saved = AgentMemory.load(memory_path)

        self.assertIn("充沛现在价格怎么样", saved.common_questions)

    def test_profile_command_shows_personal_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default().with_updated_preferences(
                risk_appetite="low",
                budget_min=20,
                budget_max=200,
                preferred_categories=["arcane"],
            )
            agent = ChatAgent(memory=memory, memory_path=memory_path)

            reply = agent.answer("/profile")

        self.assertIn("个人交易画像", reply)
        self.assertIn("风险偏好", reply)
        self.assertIn("20-200p", reply)

    def test_profile_pref_commands_update_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(memory=AgentMemory.default(), memory_path=memory_path)

            self.assertIn("已更新偏好", agent.answer("/pref risk low"))
            self.assertIn("已更新偏好", agent.answer("/pref budget 30-150"))
            self.assertIn("已更新偏好", agent.answer("/pref categories mod,arcane"))

            self.assertEqual(agent.memory.preferences.risk_appetite, "low")
            self.assertEqual(agent.memory.preferences.budget_min, 30)
            self.assertEqual(agent.memory.preferences.budget_max, 150)
            self.assertEqual(agent.memory.preferences.preferred_categories, ["mod", "arcane"])

    def test_natural_language_preference_updates_budget_risk_and_roi(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("我的预算300p，偏低风险，最低利润15%")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已更新偏好", answer)
        self.assertEqual(saved.preferences.budget_min, 0)
        self.assertEqual(saved.preferences.budget_max, 300)
        self.assertEqual(saved.preferences.risk_appetite, "low")
        self.assertEqual(saved.preferences.min_roi_pct, 15)

    def test_natural_language_preference_updates_categories_and_turnaround(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("我偏好mod和赋能，最长周转3天")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已更新偏好", answer)
        self.assertEqual(saved.preferences.preferred_categories, ["mod", "arcane"])
        self.assertEqual(saved.preferences.max_turnaround_days, 3)

    def test_natural_language_preference_updates_platform_crossplay_and_max_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = agent.answer("平台设为xbox，关闭跨平台，最多显示10个结果")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已更新偏好", answer)
        self.assertEqual(saved.preferences.platform, "xbox")
        self.assertFalse(saved.preferences.crossplay)
        self.assertEqual(saved.preferences.max_results, 10)

    def test_natural_language_preference_stream_matches_regular_answer(self):
        async def consume(agent):
            chunks = []
            async for chunk in agent.answer_stream("我预算30到150p，最低ROI25%"):
                chunks.append(chunk)
            return "".join(chunks)

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            answer = asyncio.run(consume(agent))
            saved = AgentMemory.load(memory_path)

        self.assertIn("已更新偏好", answer)
        self.assertEqual(saved.preferences.budget_min, 30)
        self.assertEqual(saved.preferences.budget_max, 150)
        self.assertEqual(saved.preferences.min_roi_pct, 25)

    def test_natural_language_preference_guards_questions_and_price_alerts(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                resolver=MemoryCommandResolver(),
                order_fetcher=lambda item_id: [],
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            question_reply = agent.answer("300p预算买什么好")
            after_question = AgentMemory.load(memory_path)
            alert_reply = agent.answer("充沛低于45p提醒我")
            after_alert = AgentMemory.load(memory_path)
            favorite_reply = agent.answer("帮我收藏充沛")
            after_favorite = AgentMemory.load(memory_path)
            opportunity_reply = agent.answer("交易机会只检测MOD")
            after_opportunity = AgentMemory.load(memory_path)

        self.assertNotIn("已更新偏好", question_reply)
        self.assertNotIn("已更新偏好", alert_reply)
        self.assertNotIn("已更新偏好", favorite_reply)
        self.assertNotIn("已更新偏好", opportunity_reply)
        self.assertEqual(after_question.preferences.budget_max, 0)
        self.assertEqual(after_alert.preferences.budget_max, 0)
        self.assertEqual(after_alert.price_alerts[0].item_id, "arcane_energize")
        self.assertEqual(after_favorite.preferences.preferred_categories, [])
        self.assertEqual(after_favorite.favorite_items, ["arcane_energize"])
        self.assertEqual(after_opportunity.preferences.preferred_categories, [])
        self.assertEqual(after_opportunity.preferences.opportunity_filter, "mod")

    def test_profile_pref_commands_reject_invalid_risk_and_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default().with_updated_preferences(
                risk_appetite="low",
                preferred_categories=["arcane"],
            )
            agent = ChatAgent(memory=memory, memory_path=memory_path)

            risk_reply = agent.answer("/pref risk banana")
            categories_reply = agent.answer("/pref categories banana")

            self.assertNotIn("/profile", risk_reply)
            self.assertNotIn("/profile", categories_reply)
            self.assertEqual(agent.memory.preferences.risk_appetite, "low")
            self.assertEqual(agent.memory.preferences.preferred_categories, ["arcane"])

    def test_scan_tools_pass_personal_profile_to_scanners(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory = AgentMemory.default().with_updated_preferences(
                risk_appetite="low",
                preferred_categories=["arcane"],
            )
            agent = ChatAgent(
                memory=memory,
                memory_path=memory_path,
                warframe_items=[{"url_name": "arcane_energize"}],
                order_fetcher=lambda item_id: [],
            )

            with patch("warframe_agent.mod_flipper.scan_all_mod_flips", return_value=[]) as mod_scan:
                agent._tool_mod_flipper({"limit": 1})
            with patch("warframe_agent.set_profit.scan_all_set_profits", return_value=[]) as set_scan:
                agent._tool_set_profit({"limit": 1})
            with patch("warframe_agent.investment.scan_prime_investments", return_value=[]) as investment_scan:
                agent._tool_investment_advisor({"limit": 1})

            for mocked_scan in (mod_scan, set_scan, investment_scan):
                profile = mocked_scan.call_args.kwargs["personal_profile"]
                self.assertEqual(profile.risk_appetite, "low")
                self.assertEqual(profile.preferred_categories, ["arcane"])

    def test_scan_tools_include_sqlite_outcomes_in_personal_profile_without_scanner_db_access(self):
        records = [_sqlite_outcome(index) for index in range(3)]
        fake_db = FakeOpportunityOutcomeDB(records)
        agent = ChatAgent(
            memory=AgentMemory.default(),
            warframe_items=[{"url_name": "arcane_energize"}],
            order_fetcher=lambda item_id: [],
            trading_memory_db=fake_db,
        )

        with patch("warframe_agent.mod_flipper.scan_all_mod_flips", return_value=[]) as mod_scan:
            agent._tool_mod_flipper({"limit": 1})

        profile = mod_scan.call_args.kwargs["personal_profile"]
        self.assertEqual(fake_db.requested_limit, 100)
        self.assertEqual(profile.completed_outcome_count, 3)
        self.assertEqual(profile.outcome_feedback[0].count, 3)
        self.assertEqual(profile.outcome_feedback[0].source, "mod_flipper")
        self.assertEqual(profile.outcome_feedback[0].strategy, "arcane_rank0_to_max")

    def test_investment_tool_uses_preference_defaults_when_args_omit_budget_and_roi(self):
        memory = AgentMemory.default().with_updated_preferences(
            budget_min=30,
            budget_max=150,
            min_roi_pct=25,
        )
        agent = ChatAgent(
            memory=memory,
            warframe_items=[{"url_name": "rhino_prime_set"}],
            order_fetcher=lambda item_id: [],
        )

        with patch("warframe_agent.investment.scan_prime_investments", return_value=[]) as investment_scan:
            agent._tool_investment_advisor({"limit": 1})

        self.assertEqual(investment_scan.call_args.kwargs["budget"], 150)
        self.assertEqual(investment_scan.call_args.kwargs["min_roi_pct"], 25.0)

    def test_investment_tool_treats_blank_args_as_missing_but_preserves_zero(self):
        memory = AgentMemory.default().with_updated_preferences(
            budget_min=30,
            budget_max=150,
            min_roi_pct=25,
        )
        agent = ChatAgent(
            memory=memory,
            warframe_items=[{"url_name": "rhino_prime_set"}],
            order_fetcher=lambda item_id: [],
        )

        with patch("warframe_agent.investment.scan_prime_investments", return_value=[]) as investment_scan:
            agent._tool_investment_advisor({"budget": "", "min_roi": "", "limit": 1})

        self.assertEqual(investment_scan.call_args.kwargs["budget"], 150)
        self.assertEqual(investment_scan.call_args.kwargs["min_roi_pct"], 25.0)

        with patch("warframe_agent.investment.scan_prime_investments", return_value=[]) as investment_scan:
            agent._tool_investment_advisor({"budget": 0, "min_roi": 0, "limit": 1})

        self.assertEqual(investment_scan.call_args.kwargs["budget"], 0)
        self.assertEqual(investment_scan.call_args.kwargs["min_roi_pct"], 0.0)

    def test_review_command_lists_safe_opportunity_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            db.record_opportunity_outcome(
                "OPABC123",
                "arcane_energize",
                "mod_flipper",
                "arcane_rank0_to_max",
                "completed",
                40,
                45,
                "good",
                {"safe_summary": {"roi_pct": 35, "risk_level": "low"}},
            )
            agent = ChatAgent(memory=AgentMemory.default(), memory_path=memory_path, trading_memory_db=db)

            try:
                reply = agent.answer("/review")
            finally:
                db.close()

        self.assertIn("机会复盘", reply)
        self.assertIn("OPABC123", reply)
        self.assertIn("arcane_energize", reply)
        self.assertNotIn("/w ", reply)
        self.assertNotIn("profile", reply.lower())

    def test_review_done_command_records_real_opportunity_outcome_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )

            try:
                reply = agent.answer(f"/review done {opportunity_id} 45 good")
                records = db.get_opportunity_outcomes(status="completed", item_name="arcane_energize", limit=10)
            finally:
                db.close()

        self.assertIn("已记录机会复盘", reply)
        self.assertIn(opportunity_id, reply)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.opportunity_id, opportunity_id)
        self.assertEqual(record.item_name, "arcane_energize")
        self.assertEqual(record.source, "arcane_flip")
        self.assertEqual(record.strategy, "arcane_r0_to_r5")
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.expected_profit, 31)
        self.assertEqual(record.actual_profit, 45)
        self.assertEqual(record.user_feedback, "good")
        serialized = str(record.metadata)
        self.assertIn("safe_summary", serialized)
        self.assertNotIn("UnsafeSeller", serialized)
        self.assertNotIn("profile", serialized.lower())
        self.assertNotIn("/w ", serialized)

    def test_review_done_natural_language_prompts_before_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )

            try:
                reply = agent.answer(f"{opportunity_id} 实际赚45p，结果不错，帮我复盘")
                records = db.get_opportunity_outcomes(status="completed", item_name="arcane_energize", limit=10)
            finally:
                db.close()

        self.assertIn("确认复盘", reply)
        self.assertIn(opportunity_id, reply)
        self.assertIn("45p", reply)
        self.assertEqual(records, [])

    def test_review_done_natural_language_records_after_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )

            try:
                agent.answer(f"{opportunity_id} 实际赚45p，结果不错，帮我复盘")
                reply = agent.answer("确认复盘")
                records = db.get_opportunity_outcomes(status="completed", item_name="arcane_energize", limit=10)
            finally:
                db.close()

        self.assertIn("已记录机会复盘", reply)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].opportunity_id, opportunity_id)
        self.assertEqual(records[0].actual_profit, 45)
        self.assertEqual(records[0].user_feedback, "good")

    def test_review_done_natural_language_can_cancel_before_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )

            try:
                agent.answer(f"{opportunity_id} 实际赚45p，结果不错，帮我复盘")
                reply = agent.answer("取消")
                records = db.get_opportunity_outcomes(limit=10)
            finally:
                db.close()

        self.assertIn("已取消", reply)
        self.assertEqual(records, [])

    def test_review_done_natural_language_stream_matches_regular_answer(self):
        async def consume(agent, message):
            chunks = []
            async for chunk in agent.answer_stream(message):
                chunks.append(chunk)
            return "".join(chunks)

        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )

            try:
                reply = asyncio.run(consume(agent, f"{opportunity_id} 实际亏5p，结果不好，帮我复盘"))
                records = db.get_opportunity_outcomes(limit=10)
            finally:
                db.close()

        self.assertIn("确认复盘", reply)
        self.assertIn("-5p", reply)
        self.assertIn("bad", reply)
        self.assertEqual(records, [])

    def test_review_done_natural_language_guards_missing_id_and_bad_profit(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )

            try:
                missing_id = agent.answer("实际赚45p，结果不错，帮我复盘")
                bad_profit = agent.answer(f"{opportunity_id} 实际赚很多，帮我复盘")
                market_chat = agent.answer("充沛今天能赚45p吗")
                confirm = agent.answer("确认复盘")
                records = db.get_opportunity_outcomes(limit=10)
            finally:
                db.close()

        self.assertNotIn("确认复盘", missing_id)
        self.assertNotIn("确认复盘", bad_profit)
        self.assertNotIn("确认复盘", market_chat)
        self.assertNotIn("已记录机会复盘", confirm)
        self.assertEqual(records, [])

    def test_review_done_command_rejects_missing_db_missing_lookup_and_bad_profit(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())

            no_db_agent = ChatAgent(
                memory=AgentMemory.default(),
                memory_path=Path(tmp) / "memory.json",
                opportunity_lookup_store=lookup,
            )
            self.assertIn("暂无机会复盘数据", no_db_agent.answer(f"/review done {opportunity_id} 45 good"))

            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )
            try:
                self.assertIn("实际利润必须是整数", agent.answer(f"/review done {opportunity_id} nope good"))
                self.assertIn("机会 ID 格式不正确", agent.answer("/review done abc 45 good"))
                self.assertIn("不存在或已过期", agent.answer("/review done OPZZZZZZ 45 good"))
                self.assertEqual(db.get_opportunity_outcomes(limit=10), [])
            finally:
                db.close()

    def test_review_done_command_supports_chinese_alias_without_breaking_status_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)
            lookup = OpportunityLookupStore(Path(tmp) / "lookup.db", now=lambda: now)
            opportunity_id = lookup.create("arcane_energize", "Arcane Energize", _reviewable_trade_plan())
            db = TradingMemoryDB(Path(tmp) / "trading_memory.db")
            agent = ChatAgent(
                memory=AgentMemory.default(),
                memory_path=Path(tmp) / "memory.json",
                trading_memory_db=db,
                opportunity_lookup_store=lookup,
            )

            try:
                reply = agent.answer(f"/复盘 完成 {opportunity_id} 12")
                completed_reply = agent.answer("/review completed")
            finally:
                db.close()

        self.assertIn("已记录机会复盘", reply)
        self.assertIn("反馈 good", reply)
        self.assertIn("机会复盘", completed_reply)
        self.assertIn(opportunity_id, completed_reply)


    def test_fissure_alert_natural_language_prompts_before_subscribing(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            reply = agent.answer("提醒我钢铁后纪歼灭裂缝")
            saved = AgentMemory.load(memory_path)

        self.assertIn("确认订阅", reply)
        self.assertIn("后纪", reply)
        self.assertIn("歼灭", reply)
        self.assertEqual(saved.fissure_alerts, [])

    def test_fissure_alert_natural_language_adds_after_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            agent.answer("提醒我钢铁后纪歼灭裂缝")
            reply = agent.answer("确认订阅")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已订阅裂缝通知", reply)
        self.assertEqual(len(saved.fissure_alerts), 1)
        alert = saved.fissure_alerts[0]
        self.assertEqual(alert.tier, "VoidT4")
        self.assertEqual(alert.mission_type, "MT_EXTERMINATION")
        self.assertTrue(alert.hard)

    def test_fissure_alert_natural_language_can_cancel_before_subscribing(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            agent.answer("提醒我钢铁后纪歼灭裂缝")
            reply = agent.answer("取消")
            saved = AgentMemory.load(memory_path)

        self.assertIn("已取消", reply)
        self.assertEqual(saved.fissure_alerts, [])

    def test_fissure_alert_natural_language_remove_after_confirmation(self):
        memory = AgentMemory.default().with_fissure_alert(
            FissureAlert(
                tier="VoidT4",
                mission_type="MT_EXTERMINATION",
                hard=True,
                note="等级=后纪、任务=歼灭、仅钢铁",
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            memory.save(memory_path)
            agent = ChatAgent(
                memory=memory,
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            prompt = agent.answer("取消第1个裂缝提醒")
            before = AgentMemory.load(memory_path)
            reply = agent.answer("确认取消")
            after = AgentMemory.load(memory_path)

        self.assertIn("确认取消", prompt)
        self.assertEqual(len(before.fissure_alerts), 1)
        self.assertIn("已取消订阅", reply)
        self.assertEqual(after.fissure_alerts, [])

    def test_fissure_alert_natural_language_stream_matches_regular_answer(self):
        async def consume(agent):
            chunks = []
            async for chunk in agent.answer_stream("提醒我普通虚空捕获裂缝"):
                chunks.append(chunk)
            return "".join(chunks)

        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            reply = asyncio.run(consume(agent))
            saved = AgentMemory.load(memory_path)

        self.assertIn("确认订阅", reply)
        self.assertIn("捕获", reply)
        self.assertEqual(saved.fissure_alerts, [])

    def test_fissure_alert_natural_language_guards_queries_and_slash_still_immediate(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = Path(tmp) / "memory.json"
            agent = ChatAgent(
                memory=AgentMemory.default(),
                model_call=lambda prompt: "unused",
                memory_path=memory_path,
            )

            query = agent.answer("现在有什么裂缝")
            after_query = AgentMemory.load(memory_path)
            add_reply = agent.answer("/fissure add 后纪 歼灭")
            after_add = AgentMemory.load(memory_path)
            remove_reply = agent.answer("/fissure remove 1")
            after_remove = AgentMemory.load(memory_path)

        self.assertNotIn("确认订阅", query)
        self.assertEqual(after_query.fissure_alerts, [])
        self.assertIn("已订阅裂缝通知", add_reply)
        self.assertEqual(len(after_add.fissure_alerts), 1)
        self.assertIn("已取消订阅", remove_reply)
        self.assertEqual(after_remove.fissure_alerts, [])


if __name__ == "__main__":
    unittest.main()
