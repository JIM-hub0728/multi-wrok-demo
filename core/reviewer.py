"""
审查循环（Alice 方法论 Ch.6 + Ch.13）：产出 → 审查 → 修正/通过。

原则：
- 每个 Agent 的产出在交给下一环节前，由接手方先审查
- Manager 做最终交付审查
- 退回修改最多 2 次，避免死循环
"""
import json
import logging

logger = logging.getLogger(__name__)

# 每个 Agent 已审查次数（同一任务内跟踪）
_review_counts: dict[str, int] = {}


def reset_review_counts():
    """每次新任务开始前调用，重置审查计数器。"""
    _review_counts.clear()


def should_inject_review(
    last_message: str,
    last_speaker_name: str,
    next_speaker_name: str,
) -> bool:
    """
    判断是否需要在 Agent 交接时注入审查。

    条件：
    1. 上一位不是 Manager（Manager 不需要别人审查）
    2. 上一位不是 User（用户不是 Agent，无需审查）
    3. 最后一条消息中包含 @mention（表示要交接了）
    4. 审查次数未超上限（每个 Agent 最多被审查/退回 2 次）

    注意：本函数会递增审查计数。
    """
    if last_speaker_name in ("Manager", "User"):
        return False
    if next_speaker_name == last_speaker_name:
        return False
    count = _review_counts.get(last_speaker_name, 0)
    if count >= 2:
        return False
    _review_counts[last_speaker_name] = count + 1
    return True


def build_review_message(
    last_speaker_name: str,
    reviewer_name: str,
    task_context: str = "",
) -> dict:
    """
    生成审查指令消息，注入到群聊中。
    """
    review_rules = {
        ("Searcher", "Engineer"): (
            f"作为 {reviewer_name}，在开始写代码之前，请先审查 Searcher 的调研结果：\n"
            "1. 信息是否完整？有没有遗漏关键数据？\n"
            "2. 结论是否有来源支撑？有没有编造？\n"
            "3. 有哪些地方需要补充或修正？\n\n"
            "如果你发现严重问题（如事实错误、关键信息缺失），请明确指出并要求 Searcher 修正。\n"
            "如果只是小问题或者调研报告合格，请说「审查通过」然后继续你的开发任务。"
        ),
        ("Engineer", "Manager"): (
            f"作为 {reviewer_name}，在交付用户之前，请审查 Engineer 的代码工作：\n"
            "1. 代码是否可运行？是否已通过 run_code 验证？\n"
            "2. 是否实现了用户需求？有没有遗漏？\n"
            "3. 代码风格和质量是否合理？\n\n"
            "如果代码有问题，请要求 Engineer 修复。如果合格，请说「审查通过」然后给用户做最终交付总结。"
        ),
        ("Searcher", "Manager"): (
            f"作为 {reviewer_name}，请审查 Searcher 的调研报告：\n"
            "1. 调研是否覆盖了用户的问题？\n"
            "2. 结论是否清晰、有依据？\n"
            "3. 是否已保存为交付物？\n\n"
            "如果没问题，请说「审查通过」然后做最终交付总结。"
        ),
        ("Engineer", "Searcher"): (
            f"作为 {reviewer_name}，请审查 Engineer 的代码：\n"
            "1. 代码是否正确实现了需求？\n"
            "2. 是否已通过 run_code 验证？\n"
            "3. 如果发现问题，请指出具体位置和修改建议。\n\n"
            "没问题就说「审查通过」。"
        ),
    }

    key = (last_speaker_name, reviewer_name)
    rule = review_rules.get(
        key,
        f"作为 {reviewer_name}，请先审查 {last_speaker_name} 的工作成果，确认无误后再继续。",
    )

    msg = {
        "role": "user",
        "name": "reviewer",
        "content": f"【审查提醒】\n{rule}",
    }

    logger.info(
        "review injected: %s → %s (review #%d)",
        last_speaker_name, reviewer_name, _review_counts.get(last_speaker_name, 0),
    )
    return msg


def is_review_approved(review_message: str) -> bool:
    """
    检测审查者是否批准了交付物。
    """
    approved_phrases = [
        "审查通过", "通过审查", "没问题", "可以继续",
        "approved", "looks good", "no issues",
    ]
    msg_lower = review_message.lower()
    return any(phrase in msg_lower for phrase in approved_phrases)


def is_review_rejected(review_message: str) -> bool:
    """
    检测审查者是否要求修改。
    """
    reject_phrases = [
        "需要修改", "有问题", "修正", "补充", "缺少",
        "不正确", "没有通过", "请重新", "请修复",
    ]
    msg_lower = review_message.lower()
    return any(phrase in msg_lower for phrase in reject_phrases)
