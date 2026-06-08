"""
项目入口：初始化所有组件，启动交互式命令行界面。

运行方式：
    python main.py

交互流程：
    1. 加载配置
    2. 创建所有 Agent
    3. 进入主循环，让用户选择：
       - [1] 和某个 Agent 私聊
       - [2] 发起一次群聊任务
       - [3] 查看可聊天的 Agent
       - [q] 退出
"""

import time
import json
import os
import re

from config.settings import Settings
from core.agent_factory import AgentFactory
from core.private_chat import PrivateChatManager
from core.group_chat import GroupChatSession
from utils.chat_logger import ChatLogger


def generate_group_review(coordinator_agent, transcript):
    """
    让 Coordinator（Manager）生成群聊复盘报告。
    """
    if not transcript or len(transcript) < 3:
        return "群聊轮数不足，无需复盘。"

    transcript_text = "\n".join(
        [f"{m['speaker']}: {m['content']}" for m in transcript]
    )
    prompt = (
        "请对以下群聊进行复盘总结，控制在 300 字以内：\n\n"
        f"{transcript_text}\n\n"
        "请从以下几个方面写复盘报告：\n"
        "1. 任务目标是否明确\n"
        "2. 各 Agent 的分工是否合理\n"
        "3. 沟通效率如何\n"
        "4. 有什么可以改进的地方\n"
        "5. 对每个 Agent 的具体建议\n\n"
        "用简洁的 Markdown 格式输出。"
    )

    try:
        review = coordinator_agent.agent.generate_reply(
            messages=[{"role": "user", "content": prompt}]
        )
        if isinstance(review, dict):
            review = review.get("content", str(review))
        return review
    except Exception as e:
        return f"复盘生成失败: {e}"


def save_review(review, task_desc):
    """
    将复盘报告保存到 memory/projects/ 目录。
    """
    projects_dir = "memory/projects"
    os.makedirs(projects_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_task = "".join(c for c in task_desc if c.isalnum() or c in (" ", "-", "_")).rstrip()[:30]
    filename = f"{timestamp}_{safe_task}_review.md"
    filepath = os.path.join(projects_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# 复盘：{task_desc}\n\n")
        f.write(review)

    return filepath


def update_agent_profiles_from_review(review_text, agents_dict):
    """
    从复盘报告中提取各 Agent 的改进建议，更新画像文件。
    """
    manager = agents_dict.get("Manager")
    if not manager:
        return

    prompt = (
        "以下是一份群聊复盘报告。请从中提取对每个 Agent 的具体改进建议，\n"
        "输出为 JSON 格式（不要包含 markdown 代码块标记）：\n\n"
        f"{review_text}\n\n"
        "请严格按以下格式输出：\n"
        '{"Searcher": "具体建议...", "Engineer": "具体建议..."}\n'
        "如果某个 Agent 没有具体建议，值设为空字符串。"
    )

    try:
        reply = manager.agent.generate_reply(
            messages=[{"role": "user", "content": prompt}]
        )
        if isinstance(reply, dict):
            reply = reply.get("content", str(reply))

        # 尝试提取 JSON
        json_str = reply.strip()
        if json_str.startswith("```"):
            lines = json_str.splitlines()
            json_str = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        updates = json.loads(json_str)
        if not isinstance(updates, dict):
            return

        for name, suggestion in updates.items():
            agent = agents_dict.get(name)
            if agent and suggestion and str(suggestion).strip():
                if "self_reflections" not in agent.profile:
                    agent.profile["self_reflections"] = []
                agent.profile["self_reflections"].append({
                    "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "improvement": str(suggestion).strip(),
                })
                agent.save_profile()
                print(f"  {name} 的画像已更新")
    except Exception as e:
        print(f"  画像更新失败: {e}")


def update_user_profile(task_type, topic):
    """
    更新用户画像的交互历史。
    """
    profile_path = "memory/user/profile.json"
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        profile = {
            "name": "User",
            "task_preferences": [],
            "communication_style": "",
            "common_commands": [],
            "habits": {},
            "interaction_history": [],
            "updated_at": "",
        }

    profile["interaction_history"].append({
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "type": task_type,
        "topic": topic[:50],
    })
    profile["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def main():
    """
    应用主入口。
    """
    print("=== Multi-Agent Demo ===\n")

    # 第 1 步：加载配置
    settings = Settings()
    llm_config = settings.get_llm_config()

    # 第 2 步：创建所有 Agent（工作 + 故事角色）
    factory = AgentFactory(llm_config)
    work_agents = factory.create_all()
    story_agents = factory.create_all_story_roles()
    agents = {**work_agents, **story_agents}

    # 第 3 步：初始化管理器
    private_chat = PrivateChatManager(work_agents, llm_config=llm_config)
    group_chat = GroupChatSession(agents, llm_config, max_round=20)
    logger = ChatLogger()

    # 第 4 步：进入交互循环
    while True:
        print("\n请选择操作：")
        print("1. 和 Agent 私聊")
        print("2. 发起群聊任务（手动选 Agent）")
        print("3. 查看可聊天的 Agent")
        print("4. 让 Manager 自动协调任务")
        print("q. 退出")
        choice = input("\n输入选项: ").strip()

        if choice == "1":
            name = input("想和谁聊？（Manager/Searcher/Engineer）: ").strip()
            if name not in private_chat.list_agents():
                print("该 Agent 不存在")
                continue
            print(f"\n--- 开始和 {name} 私聊，输入 'q' 返回主菜单 ---")
            while True:
                msg = input("你说: ").strip()
                if msg.lower() == "q":
                    break
                if not msg:
                    continue
                try:
                    reply = private_chat.chat_with(name, msg)
                    print(f"\n{name}: {reply}\n")
                    logger.log_private(name, msg, reply)
                    update_user_profile("private_chat", f"与 {name} 私聊")
                except Exception as e:
                    print(f"出错了: {e}")

        elif choice == "2":
            print("可选择的 Agent:", ", ".join(private_chat.list_agents()))
            names_input = input("请输入要进群的 Agent（用逗号分隔，留空表示全部）: ").strip()
            task = input("请输入任务描述: ")
            try:
                print("\n--- 群聊开始 ---")
                selected = None
                if names_input:
                    selected = [n.strip() for n in names_input.split(",")]
                transcript = group_chat.start(task, selected_names=selected)
                logger.log_group(transcript)

                # 展示用摘要版，日志仍记录完整版
                display_transcript = group_chat.get_summary_transcript()
                print("\n--- 群聊记录 ---")
                for msg in display_transcript:
                    print(f"{msg['speaker']}: {msg['content']}")

                # 自动复盘（t4）：群聊轮数 >= 3 才触发
                if len(transcript) >= 3:
                    print("\n--- 正在生成复盘报告 ---")
                    try:
                        review = generate_group_review(agents.get("Manager"), transcript)
                        filepath = save_review(review, task)
                        print(f"复盘报告已保存: {filepath}")

                        # 从复盘报告中提取改进建议，更新各 Agent 画像
                        print("--- 正在更新 Agent 画像 ---")
                        update_agent_profiles_from_review(review, agents)
                    except Exception as e:
                        print(f"复盘生成失败: {e}")

                # 更新用户画像（t5）
                update_user_profile("group_chat", task)
            except Exception as e:
                print(f"出错了: {e}")

        elif choice == "4":
            task = input("请输入任务描述: ")
            try:
                print("\n--- Manager 正在分析任务 ---")
                manager = agents.get("Manager")
                prompt = (
                    f"用户提出了以下任务：{task}\n\n"
                    "请分析这个任务需要哪些 Agent 参与。可用的 Agent 有：\n"
                    "- Searcher（调研员）：擅长信息调研、资料搜集、事实核查\n"
                    "- Engineer（开发者）：擅长代码编写、技术实现、调试排错\n\n"
                    "请判断：\n"
                    "1. 这个任务需要 Searcher 参与吗？为什么？\n"
                    "2. 这个任务需要 Engineer 参与吗？为什么？\n"
                    "3. 如果都需要，请简要说明分工建议。\n\n"
                    "用简洁的语言回答，最后明确列出需要参与的 Agent 名字（格式：参与 Agent: Searcher, Engineer）。"
                )
                analysis = manager.agent.generate_reply(
                    messages=[{"role": "user", "content": prompt}]
                )
                if isinstance(analysis, dict):
                    analysis = analysis.get("content", str(analysis))
                print(f"\nManager 的任务分析:\n{analysis}\n")

                # 从回复中提取 Agent 名字，Manager 作为 Coordinator 自动进群
                agents_needed = ["Manager"]
                for name in ["Searcher", "Engineer"]:
                    if name in analysis:
                        agents_needed.append(name)

                # 去重
                agents_needed = list(dict.fromkeys(agents_needed))

                if len(agents_needed) <= 1:
                    print("Manager 判断不需要其他 Agent 参与，任务由她直接处理。")
                    continue

                print(f"Manager 将拉 {', '.join(agents_needed)} 进群...")
                print("\n--- 群聊开始 ---")
                transcript = group_chat.start(task, selected_names=agents_needed)
                logger.log_group(transcript)

                display_transcript = group_chat.get_summary_transcript()
                print("\n--- 群聊记录 ---")
                for msg in display_transcript:
                    print(f"{msg['speaker']}: {msg['content']}")

                if len(transcript) >= 3:
                    print("\n--- 正在生成复盘报告 ---")
                    try:
                        review = generate_group_review(manager, transcript)
                        filepath = save_review(review, task)
                        print(f"复盘报告已保存: {filepath}")

                        print("--- 正在更新 Agent 画像 ---")
                        update_agent_profiles_from_review(review, agents)
                    except Exception as e:
                        print(f"复盘生成失败: {e}")

                update_user_profile("group_chat", task)
            except Exception as e:
                print(f"出错了: {e}")

        elif choice == "3":
            print("可聊天的 Agent:", ", ".join(private_chat.list_agents()))
            input("\n按回车继续...")

        elif choice.lower() == "q":
            print("正在保存记忆...")
            for agent in agents.values():
                agent.save_history()
            print("再见！")
            break

        else:
            print("无效选项")


if __name__ == "__main__":
    main()
