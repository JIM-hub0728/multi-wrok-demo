"""
Multi-Agent Collaboration Demo - Streamlit 前端
UI 结构改造版：纯布局重构，保留全部功能
"""
import streamlit as st
import os
import json
import time
from datetime import datetime

from config.settings import Settings
from core.agent_factory import AgentFactory
from core.private_chat import PrivateChatManager
from core.group_chat import GroupChatSession
from utils.chat_logger import ChatLogger

st.set_page_config(page_title="Multi-Agent Demo", page_icon="🤖", layout="wide")

# =============================================================================
# CSS：布局结构 + 中性默认样式
# =============================================================================
st.markdown("""
<style>
/* ─── 基础重置 ─── */
* { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important; }
footer { visibility: hidden !important; }

/* ─── 整体布局 ─── */
[data-testid="stAppViewContainer"] { background: #ffffff !important; }

/* 侧边栏 */
[data-testid="stSidebar"] {
    width: 280px !important; min-width: 280px !important; max-width: 280px !important;
    background: #F8FAFC !important; border-right: 1px solid #E2E8F0 !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 20px 16px !important; }

/* 主内容区顶部清理 */
[data-testid="stAppViewContainer"] .main > div { padding: 0 !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }

/* ─── Sidebar 品牌区 ─── */
.sidebar-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.sidebar-brand { font-size: 18px; font-weight: 700; color: #0F172A; letter-spacing: -0.5px; }
.sidebar-subtitle { font-size: 12px; color: #64748B; margin-bottom: 24px; font-weight: 400; }

/* 折叠按钮 */
.collapse-btn { width: 32px !important; height: 32px !important; border-radius: 8px !important; padding: 0 !important; font-size: 14px !important; }

/* ─── 分组标题 ─── */
.group-title { font-size: 11px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.8px; margin: 24px 0 10px 0; font-weight: 600; }

/* ─── Sidebar 按钮（模式卡片） ─── */
[data-testid="stSidebar"] .stButton > button {
    width: 100% !important; height: 44px !important; margin-bottom: 8px !important;
    border-radius: 8px !important; border: none !important; font-size: 14px !important;
    text-align: left !important; justify-content: flex-start !important;
    padding-left: 16px !important; transition: all 0.2s ease !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #2563EB !important; color: white !important;
    box-shadow: 0 2px 4px rgba(37,99,235,0.15) !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background: transparent !important; color: #334155 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    background: #F1F5F9 !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
}

/* ─── 下拉框 ─── */
.stSelectbox > div > div {
    background: #ffffff !important; border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important; font-size: 14px !important;
}
.stSelectbox > div > div:hover { border-color: #2563EB !important; }
.stSelectbox > div > div > div { padding: 8px 12px !important; }

/* ─── 多选框 ─── */
.stMultiSelect > div > div {
    background: #ffffff !important; border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
}
.stMultiSelect > div > div:hover { border-color: #2563EB !important; }

/* ─── 聊天区域 ─── */
.chat-wrapper {
    max-width: 900px; margin: 0 auto;
    padding: 20px 24px 140px 24px; min-height: calc(100vh - 80px);
}

/* ─── 消息气泡 ─── */
.msg-row { display: flex; margin-bottom: 16px; animation: fadeIn 0.25s ease; }
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
.msg-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0; margin: 0 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.msg-avatar.user { background: #2563EB; color: white; order: 2; }
.msg-avatar.ai { background: #7C3AED; color: white; order: 0; }

.msg-bubble {
    padding: 12px 16px; border-radius: 16px; font-size: 14px;
    line-height: 1.65; word-wrap: break-word; max-width: 70%;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.msg-bubble.user {
    background: #2563EB; color: white;
    border-bottom-right-radius: 4px; order: 1; margin-left: auto;
}
.msg-bubble.ai {
    background: #F1F5F9; color: #1E293B;
    border-bottom-left-radius: 4px; order: 1;
}
.msg-name { font-size: 12px; color: #94A3B8; margin-bottom: 4px; font-weight: 500; }

/* ─── 输入框区域 ─── */
.input-wrapper {
    position: fixed; bottom: 0; left: 280px; right: 0;
    background: #ffffff; border-top: 1px solid #E2E8F0;
    padding: 12px 24px 20px 24px; z-index: 100;
}
.input-inner { max-width: 900px; margin: 0 auto; }

/* chat_input 样式 */
[data-testid="stChatInput"] {
    background: #F1F5F9 !important; border: none !important;
    border-radius: 24px !important; padding: 10px 18px !important;
}
[data-testid="stChatInput"] > div { background: transparent !important; border: none !important; box-shadow: none !important; }
[data-testid="stChatInput"] input { font-size: 14px !important; color: #1E293B !important; }
[data-testid="stChatInput"] input::placeholder { color: #94A3B8 !important; }
[data-testid="stChatInput"] button {
    background: #2563EB !important; color: white !important;
    border-radius: 50% !important; width: 32px !important; height: 32px !important;
    padding: 0 !important; display: flex; align-items: center; justify-content: center;
    transition: all 0.2s ease !important;
}
[data-testid="stChatInput"] button:hover { background: #1D4ED8 !important; }
[data-testid="stChatInput"] button svg { fill: white !important; }

/* ─── 滚动条 ─── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

/* ─── 加载状态 ─── */
.loading-pulse {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    background: #2563EB; animation: pulse 1.4s infinite ease-in-out both;
    margin: 0 2px;
}
.loading-pulse:nth-child(1) { animation-delay: -0.32s; }
.loading-pulse:nth-child(2) { animation-delay: -0.16s; }
@keyframes pulse {
    0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
    40% { transform: scale(1); opacity: 1; }
}

/* ─── 响应式 ─── */
@media (max-width: 768px) {
    [data-testid="stSidebar"] { width: 240px !important; min-width: 240px !important; max-width: 240px !important; }
    .input-wrapper { left: 240px; }
    .msg-bubble { max-width: 85%; }
}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 初始化
# =============================================================================
@st.cache_resource
def init_backend():
    settings = Settings()
    llm_config = settings.get_llm_config()
    factory = AgentFactory(llm_config)
    # 工作 Agent
    work_agents = factory.create_all()
    # 故事角色
    story_agents = factory.create_all_story_roles()
    # 合并
    all_agents = {**work_agents, **story_agents}
    private_chat = PrivateChatManager(work_agents, llm_config=llm_config)
    group_chat = GroupChatSession(work_agents, llm_config, max_round=20)
    logger = ChatLogger()
    return all_agents, work_agents, story_agents, private_chat, group_chat, logger

agents, work_agents, story_agents, private_chat, group_chat, logger = init_backend()
AGENT_NAMES = list(agents.keys())
AGENT_AVATARS = {
    "Manager": "🧠", "Searcher": "🔍", "Engineer": "⚙️", "User": "👤",
    "林远": "🎭", "苏晓": "🎭",
}

# =============================================================================
# 会话管理
# =============================================================================
SESSIONS_DIR = os.path.join("memory", "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

def _session_filepath(session_id):
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")

def load_all_sessions():
    sessions = {}
    if not os.path.exists(SESSIONS_DIR): return sessions
    for fname in os.listdir(SESSIONS_DIR):
        if fname.endswith(".json"):
            sid = fname[:-5]
            try:
                with open(os.path.join(SESSIONS_DIR, fname), "r", encoding="utf-8") as f:
                    sessions[sid] = json.load(f)
            except: continue
    return sessions

def save_session(session_id, title, messages):
    data = {"session_id": session_id, "title": title, "updated_at": datetime.now().isoformat(), "messages": messages}
    with open(_session_filepath(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def delete_session(session_id):
    fpath = _session_filepath(session_id)
    if os.path.exists(fpath): os.remove(fpath)

def generate_session_title(first_message):
    text = first_message.strip().replace("\n", " ")
    return text[:30] + "..." if len(text) > 30 else text

# =============================================================================
# Session State
# =============================================================================
def init_session_state():
    defaults = {
        "view": "private", "active_agent": "Manager", "group_members": [],
        "messages": {}, "sessions": {}, "current_session_id": None,
        "error": None, "last_group_result": None,
        "sidebar_collapsed": False, "profile_agent": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
    if not st.session_state.sessions:
        st.session_state.sessions = load_all_sessions()
init_session_state()

# =============================================================================
# 辅助函数
# =============================================================================
def get_convo_id():
    v = st.session_state.view
    if v == "private": return f"private_{st.session_state.active_agent}"
    elif v == "group":
        sid = st.session_state.get("current_group_session_id")
        if sid: return sid
        return f"group_{'_'.join(sorted(st.session_state.group_members))}"
    elif v == "auto": return "auto_coordination"
    return "review"

def get_messages(convo_id): return st.session_state.messages.get(convo_id, [])

def add_message(convo_id, role, content, avatar=None, files=None):
    if convo_id not in st.session_state.messages: st.session_state.messages[convo_id] = []
    msg = {"role": role, "content": content, "avatar": avatar or AGENT_AVATARS.get(role, "🤖")}
    if files:
        msg["files"] = files
    st.session_state.messages[convo_id].append(msg)
    sid = st.session_state.current_session_id
    if sid and sid == convo_id and st.session_state.view not in ("review",):
        title = st.session_state.sessions.get(sid, {}).get("title", "新会话")
        save_session(sid, title, st.session_state.messages[convo_id])

def create_new_session(convo_id, first_message=""):
    title = generate_session_title(first_message) if first_message else "新会话"
    st.session_state.sessions[convo_id] = {"session_id": convo_id, "title": title, "messages": [], "updated_at": datetime.now().isoformat()}
    save_session(convo_id, title, [])
    st.session_state.current_session_id = convo_id
    return convo_id

def switch_session(session_id):
    st.session_state.current_session_id = session_id
    st.session_state.messages[session_id] = st.session_state.sessions.get(session_id, {}).get("messages", [])

def get_or_create_session(convo_id, first_message=""):
    if convo_id in st.session_state.sessions:
        switch_session(convo_id); return convo_id
    return create_new_session(convo_id, first_message)

def render_message(role, content, avatar, is_user=False):
    safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    if is_user or role == "User":
        st.markdown(
            f'<div class="msg-row" style="justify-content: flex-end;">'
            f'<div class="msg-bubble user">{safe}</div>'
            f'<div class="msg-avatar user">👤</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="msg-row" style="justify-content: flex-start;">'
            f'<div class="msg-avatar ai">{avatar}</div>'
            f'<div>'
            f'<div class="msg-name">{role}</div>'
            f'<div class="msg-bubble ai">{safe}</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

def _scroll_to_bottom():
    """注入 JS 滚动到聊天区底部。"""
    st.html("""
    <script>
    (function() {
        var sc = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
        if (sc) sc.scrollTop = sc.scrollHeight;
    })();
    </script>
    """)


def render_chat_messages(convo_id):
    messages = get_messages(convo_id)
    for idx, msg in enumerate(messages):
        render_message(msg["role"], msg["content"], msg.get("avatar", "🤖"), is_user=(msg["role"] == "User"))
    _scroll_to_bottom()

# =============================================================================
# Sidebar
# =============================================================================
collapsed = st.session_state.sidebar_collapsed

with st.sidebar:
    # ── 品牌区 + 折叠按钮 ──
    header_cols = st.columns([4, 1])
    with header_cols[0]:
        st.markdown('<div class="sidebar-brand">Multi-Agent</div>', unsafe_allow_html=True)
    with header_cols[1]:
        toggle_icon = "▶" if collapsed else "◀"
        if st.button(toggle_icon, key="toggle_sidebar", help="折叠/展开侧边栏"):
            st.session_state.sidebar_collapsed = not collapsed

    if not collapsed:
        st.markdown('<div class="sidebar-subtitle">Alice 工程方法论实践</div>', unsafe_allow_html=True)

        # ── 新建对话 ──
        if st.button("➕ 新建对话", use_container_width=True):
            # 新会话始终从 private_Manager 起步，convo_id 固定
            convo_id = "private_Manager"
            if convo_id in st.session_state.sessions:
                delete_session(convo_id)
                del st.session_state.sessions[convo_id]
            create_new_session(convo_id)
            st.session_state.messages.pop(convo_id, None)
            st.session_state.view = "private"
            st.session_state.active_agent = "Manager"
            st.rerun()

        # ── 历史会话 ──
        sessions = st.session_state.sessions
        if sessions:
            for sid, sdata in sorted(sessions.items(), key=lambda x: x[1].get("updated_at", ""), reverse=True)[:10]:
                title = sdata.get("title", "未命名")
                is_active = sid == st.session_state.current_session_id
                c1, c2 = st.columns([4, 1])
                with c1:
                    label = f"{'▸ ' if is_active else ''}{title}"
                    if st.button(label, key=f"sess_{sid}", use_container_width=True):
                        if sid.startswith("private_"):
                            st.session_state.view = "private"
                            st.session_state.active_agent = sid.replace("private_", "")
                        elif sid.startswith("group_"):
                            st.session_state.view = "group"
                            st.session_state.current_group_session_id = sid
                        elif sid == "auto_coordination":
                            st.session_state.view = "auto"
                        else:
                            st.session_state.view = "private"
                            st.session_state.active_agent = "Manager"
                        switch_session(sid)
                        st.rerun()
                with c2:
                    if st.button("🗑️", key=f"del_{sid}"):
                        delete_session(sid)
                        if sid in st.session_state.sessions:
                            del st.session_state.sessions[sid]
                        if st.session_state.current_session_id == sid:
                            st.session_state.current_session_id = None
                            st.session_state.messages = {}
                        st.rerun()
        else:
            st.caption("暂无历史会话")

        # ── 对话模式（卡片式按钮） ──
        st.markdown('<div class="group-title">对话模式</div>', unsafe_allow_html=True)
        mode_items = [
            ("private", "💬 私聊"),
            ("group", "👥 手动群聊"),
            ("auto", "🤖 自动协调"),
            ("review", "📦 交付物"),
        ]
        for mode_key, mode_label in mode_items:
            is_active = st.session_state.view == mode_key
            btn_type = "primary" if is_active else "secondary"
            if st.button(mode_label, key=f"mode_{mode_key}", use_container_width=True, type=btn_type):
                st.session_state.view = mode_key

        # ── 选择助手 ──
        st.markdown('<div class="group-title">选择助手</div>', unsafe_allow_html=True)
        if st.session_state.view == "private":
            st.session_state.active_agent = st.selectbox(
                "选择 Agent", AGENT_NAMES,
                index=AGENT_NAMES.index(st.session_state.active_agent) if st.session_state.active_agent in AGENT_NAMES else 0,
                label_visibility="collapsed",
            )
        elif st.session_state.view in ["group", "auto"]:
            default = st.session_state.group_members if st.session_state.group_members else AGENT_NAMES
            st.session_state.group_members = st.multiselect(
                "选择进群的 Agent", AGENT_NAMES, default=default, label_visibility="collapsed"
            )
        elif st.session_state.view == "review":
            st.info("📁 交付物")

        # ── 画像按钮 ──
        if st.session_state.view == "private":
            agent_name = st.session_state.active_agent
            is_profile_open = st.session_state.profile_agent == agent_name
            btn_label = f"{'✕ ' if is_profile_open else ''}{AGENT_AVATARS[agent_name]} {agent_name} 画像"
            btn_type = "primary" if is_profile_open else "secondary"
            if st.button(btn_label, key=f"profile_{agent_name}", use_container_width=True, type=btn_type):
                if is_profile_open:
                    st.session_state.profile_agent = None
                else:
                    st.session_state.profile_agent = agent_name
                    st.session_state._scroll_to_profile = True
    else:
        # ── 折叠状态：只显示图标 ──
        st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
        mode_emojis = [("private", "💬"), ("group", "👥"), ("auto", "🤖"), ("review", "📦")]
        for mode_key, emoji in mode_emojis:
            is_active = st.session_state.view == mode_key
            btn_type = "primary" if is_active else "secondary"
            if st.button(emoji, key=f"collapsed_{mode_key}", use_container_width=True, type=btn_type):
                st.session_state.view = mode_key

    if st.session_state.error:
        st.error(f"⚠️ {st.session_state.error}")
        st.session_state.error = None

# =============================================================================
# 主区域：聊天区 + 底部输入框
# =============================================================================
def render_private_chat():
    agent_name = st.session_state.active_agent
    convo_id = get_convo_id()
    if st.session_state.current_session_id != convo_id: get_or_create_session(convo_id)

    # 聊天消息区（画像编辑器作为顶部卡片嵌入）
    st.markdown('<div class="chat-wrapper" id="chat-top">', unsafe_allow_html=True)
    profile_agent = st.session_state.get("profile_agent")
    if profile_agent and profile_agent == agent_name:
        render_profile_editor(profile_agent)
        st.divider()
    render_chat_messages(convo_id)
    st.markdown('</div>', unsafe_allow_html=True)

    # 底部输入框
    st.markdown('<div class="input-wrapper"><div class="input-inner">', unsafe_allow_html=True)
    placeholder = f"给 {agent_name} 发消息..."
    user_msg = st.chat_input(placeholder)
    st.markdown('</div></div>', unsafe_allow_html=True)

    if user_msg:
        if not get_messages(convo_id): st.session_state.sessions[convo_id]["title"] = generate_session_title(user_msg)
        add_message(convo_id, "User", user_msg); render_message("User", user_msg, "👤", is_user=True)
        with st.spinner(f"{agent_name} 正在思考..."):
            try:
                resp = private_chat.chat_with(agent_name, user_msg)
                content = resp.get("content", "") if isinstance(resp, dict) else str(resp)
                files = resp.get("files", []) if isinstance(resp, dict) else []
                add_message(convo_id, agent_name, content, AGENT_AVATARS[agent_name], files=files)
                render_message(agent_name, content, AGENT_AVATARS[agent_name])
            except Exception as e: st.session_state.error = f"{agent_name} 回复失败: {str(e)}"; st.rerun()

def render_group_chat():
    members = st.session_state.group_members
    if not members:
        st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
        st.warning("👈 请先在侧边栏选择至少一个 Agent 进群")
        st.markdown('</div>', unsafe_allow_html=True)
        st.session_state.current_group_session_id = None
        return

    # 固定当前群聊会话 ID，避免成员微调时反复创建新会话
    if st.session_state.get("current_group_session_id"):
        convo_id = st.session_state.current_group_session_id
    else:
        convo_id = f"group_{'_'.join(sorted(members))}"
        st.session_state.current_group_session_id = convo_id

    if st.session_state.current_session_id != convo_id:
        get_or_create_session(convo_id)

    # 聊天消息区
    st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
    render_chat_messages(convo_id)
    st.markdown('</div>', unsafe_allow_html=True)

    # 底部输入框
    st.markdown('<div class="input-wrapper"><div class="input-inner">', unsafe_allow_html=True)
    task = st.chat_input("输入群聊任务，按 Enter 开始...")
    st.markdown('</div></div>', unsafe_allow_html=True)

    if task:
        if not get_messages(convo_id): st.session_state.sessions[convo_id]["title"] = generate_session_title(task)
        st.session_state.messages[convo_id] = []; st.session_state.last_group_result = None; transcript = []
        chat_placeholder = st.empty()

        # 判断模式：选中故事角色 → story 模式，否则 work 模式
        story_names = set(story_agents.keys())
        is_story_mode = bool(set(members) & story_names)
        mode = "story" if is_story_mode else "work"
        active_agents = story_agents if is_story_mode else work_agents
        session = GroupChatSession(active_agents, active_agents[list(active_agents.keys())[0]].agent.llm_config, max_round=20, mode=mode)

        try:
            for msg in session.start_streaming(task, selected_names=members):
                speaker = msg.get("speaker", "Unknown"); content = msg.get("content", "")
                files = msg.get("files", [])
                transcript.append(msg); add_message(convo_id, speaker, content, AGENT_AVATARS.get(speaker, "🤖"), files=files)
                with chat_placeholder.container():
                    st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
                    render_chat_messages(convo_id)
                    st.markdown('</div>', unsafe_allow_html=True)
                time.sleep(0.1)
            logger.log_group(transcript)
            st.success("✅ 群聊完成")
            st.session_state.last_group_result = {"task": task, "transcript": transcript, "member_count": len(members)}
            # story 模式不复盘
            if not is_story_mode and len(transcript) >= 3:
                try:
                    from main import generate_group_review, save_review, update_agent_profiles_from_review
                    manager = agents.get("Manager")
                    review = generate_group_review(manager, transcript); filepath = save_review(review, task)
                    update_agent_profiles_from_review(review, agents)
                    st.session_state.last_group_result["review_path"] = filepath; st.toast("📊 复盘报告已生成")
                except Exception as e: st.warning(f"⚠️ 复盘生成失败: {e}")
        except Exception as e: st.error(f"❌ 群聊出错: {str(e)}"); st.session_state.error = f"群聊出错: {str(e)}"

def render_auto_coordination():
    convo_id = get_convo_id()
    if st.session_state.current_session_id != convo_id: get_or_create_session(convo_id)

    # 聊天消息区
    st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
    render_chat_messages(convo_id)
    st.markdown('</div>', unsafe_allow_html=True)

    # 底部输入框
    st.markdown('<div class="input-wrapper"><div class="input-inner">', unsafe_allow_html=True)
    task = st.chat_input("描述你的任务，Manager 会自动协调...")
    st.markdown('</div></div>', unsafe_allow_html=True)

    if task:
        if not get_messages(convo_id): st.session_state.sessions[convo_id]["title"] = generate_session_title(task)
        st.session_state.messages[convo_id] = []; st.session_state.last_group_result = None; transcript = []
        chat_placeholder = st.empty()

        # 先加用户消息，保证渲染顺序正确
        add_message(convo_id, "User", task, AGENT_AVATARS["User"])
        with chat_placeholder.container():
            st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
            render_chat_messages(convo_id)
            st.markdown('</div>', unsafe_allow_html=True)

        try:
            manager = agents.get("Manager")
            status_text = st.empty()
            status_text.info("🧠 Manager 正在分析任务...")
            prompt = (f"用户提出了以下任务：{task}\n\n请分析这个任务需要哪些 Agent 参与。可用的 Agent 有：\n"
                      "- Searcher（调研员）：擅长信息调研、资料搜集、事实核查\n"
                      "- Engineer（开发者）：擅长代码编写、技术实现、调试排错\n\n"
                      "请判断：\n1. 这个任务需要 Searcher 参与吗？为什么？\n"
                      "2. 这个任务需要 Engineer 参与吗？为什么？\n"
                      "3. 如果都需要，请简要说明分工建议。\n\n"
                      "用简洁的语言回答，最后一行必须写「@Searcher 请开始调研」来启动群聊协作。")
            analysis = manager.agent.generate_reply(messages=[{"role": "user", "content": prompt}])
            if isinstance(analysis, dict): analysis = analysis.get("content", str(analysis))
            status_text.empty()
            # 把 Manager 的分析也加入消息
            add_message(convo_id, "Manager", f"📋 **任务分析**\n\n{analysis}", AGENT_AVATARS["Manager"])
            with chat_placeholder.container():
                st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
                render_chat_messages(convo_id)
                st.markdown('</div>', unsafe_allow_html=True)

            agents_needed = ["Manager"]
            for name in ["Searcher", "Engineer"]:
                if name in analysis: agents_needed.append(name)
            agents_needed = list(dict.fromkeys(agents_needed))

            add_message(convo_id, "Manager", f"🚀 将拉 {', '.join(agents_needed)} 进群协作...", AGENT_AVATARS["Manager"])
            with chat_placeholder.container():
                st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
                render_chat_messages(convo_id)
                st.markdown('</div>', unsafe_allow_html=True)

            # 把 Manager 的分析作为群聊初始上下文，末尾 @ 确保第一个发言人选中
            enriched_task = (
                f"【Manager 的任务分析】\n{analysis}\n\n"
                f"【原始任务】\n{task}\n\n"
                f"请按照 Manager 的分工开始协作。@Searcher"
            )
            for msg in group_chat.start_streaming(enriched_task, selected_names=agents_needed):
                speaker = msg.get("speaker", "Unknown"); content = msg.get("content", "")
                files = msg.get("files", [])
                transcript.append(msg); add_message(convo_id, speaker, content, AGENT_AVATARS.get(speaker, "🤖"), files=files)
                with chat_placeholder.container():
                    st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)
                    render_chat_messages(convo_id)
                    st.markdown('</div>', unsafe_allow_html=True)
                time.sleep(0.1)
            logger.log_group(transcript)
            st.success("✅ 群聊完成")
            st.session_state.last_group_result = {"task": task, "transcript": transcript, "member_count": len(agents_needed)}
            if len(transcript) >= 3:
                try:
                    from main import generate_group_review, save_review, update_agent_profiles_from_review
                    review = generate_group_review(manager, transcript); filepath = save_review(review, task)
                    update_agent_profiles_from_review(review, agents)
                    st.session_state.last_group_result["review_path"] = filepath; st.toast("📊 复盘报告已生成")
                except Exception as e: st.warning(f"⚠️ 复盘生成失败: {e}")
        except Exception as e: st.error(f"❌ 自动协调出错: {str(e)}"); st.session_state.error = f"自动协调出错: {str(e)}"

def render_review():
    st.markdown('<div style="max-width:900px;margin:0 auto;padding:20px 24px;">', unsafe_allow_html=True)
    st.markdown("### 📦 交付物")

    # Tab 切换三类交付物
    tab_labels = ["📄 调研报告", "💻 代码文件", "📊 复盘报告"]
    tabs = st.tabs(tab_labels)

    # Tab 1: 调研报告
    with tabs[0]:
        research_dir = os.path.join("deliverables", "research")
        _render_file_list(research_dir, ".md", "暂无调研报告")

    # Tab 2: 代码文件
    with tabs[1]:
        code_dir = os.path.join("deliverables", "code")
        _render_file_list(code_dir, ".py", "暂无代码文件")

    # Tab 3: 复盘报告
    with tabs[2]:
        projects_dir = os.path.join("memory", "projects")
        _render_file_list(projects_dir, "_review.md", "暂无复盘报告")

    st.markdown('</div>', unsafe_allow_html=True)


def _render_file_list(directory: str, suffix: str, empty_msg: str):
    """通用的文件列表渲染组件。"""
    if not os.path.exists(directory):
        st.info(empty_msg)
        return
    files = sorted(
        [f for f in os.listdir(directory) if f.endswith(suffix)],
        reverse=True,
    )
    if not files:
        st.info(empty_msg)
        return
    selected = st.selectbox("选择文件", files, key=f"filelist_{suffix}", label_visibility="collapsed")
    if selected:
        filepath = os.path.join(directory, selected)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if suffix == ".py":
                st.code(content, language="python")
            else:
                st.markdown(content)
        except Exception as e:
            st.error(f"读取文件失败: {e}")

def render_profile_editor(agent_name: str):
    """渲染 Agent 画像编辑器，可查看和编辑各项属性。"""
    profile_key = f"profile_data_{agent_name}"
    # 首次打开时从磁盘加载，之后使用 session_state 中的副本
    if profile_key not in st.session_state:
        profile_path = os.path.join("memory", "agents", f"{agent_name}_profile.json")
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                st.session_state[profile_key] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            st.session_state[profile_key] = {
                "name": agent_name, "role": "", "capabilities": [], "communication_style": "",
                "collaboration_experience": {}, "self_reflections": [], "updated_at": ""}
    profile = st.session_state[profile_key]
    profile_path = os.path.join("memory", "agents", f"{agent_name}_profile.json")

    # 滚动到画像区域顶部
    if st.session_state.pop("_scroll_to_profile", False):
        st.html("""
        <script>
        var el = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
        if (el) el.scrollTop = 0;
        </script>
        """)

    st.markdown(f"### {AGENT_AVATARS[agent_name]} {agent_name} 画像")

    col1, col2 = st.columns(2)
    with col1:
        profile["name"] = st.text_input("名称", value=profile.get("name", ""), key=f"prof_name_{agent_name}")
        profile["role"] = st.text_input("角色", value=profile.get("role", ""), key=f"prof_role_{agent_name}")
    with col2:
        profile["communication_style"] = st.text_area(
            "沟通风格", value=profile.get("communication_style", ""),
            key=f"prof_comm_{agent_name}", height=68)

    caps_text = "\n".join(profile.get("capabilities", []))
    new_caps = st.text_area("能力列表（每行一个）", value=caps_text, key=f"prof_caps_{agent_name}", height=80)
    profile["capabilities"] = [c.strip() for c in new_caps.split("\n") if c.strip()]

    # 协作经验（垂直布局，避免中文标签挤压）
    with st.expander("🔗 协作经验 (collaboration_experience)", expanded=False):
        exp = profile.get("collaboration_experience", {})
        if exp:
            st.caption("已记录的经验（修改后自动保存到缓存，需点底部「保存」持久化）")
            for k in list(exp.keys()):
                c_left, c_right = st.columns([5, 1])
                with c_left:
                    new_k = st.text_input("Agent 名", value=k, key=f"exp_k_{agent_name}_{k}", label_visibility="collapsed")
                    new_v = st.text_input("经验描述", value=exp[k], key=f"exp_v_{agent_name}_{k}", label_visibility="collapsed")
                with c_right:
                    st.write("")  # 占位对齐
                    if st.button("🗑️ 删除", key=f"exp_del_{agent_name}_{k}"):
                        del exp[k]
                        st.rerun()
                if new_k != k:
                    exp[new_k] = new_v
                    del exp[k]
                    st.rerun()
                else:
                    exp[k] = new_v
                st.divider()
        else:
            st.caption("暂无协作经验记录")

        st.markdown("**新增协作经验**")
        new_exp_key = st.text_input("Agent 名", value="", key=f"new_exp_k_{agent_name}", placeholder="例如: Searcher")
        new_exp_val = st.text_input("经验描述", value="", key=f"new_exp_v_{agent_name}", placeholder="例如: 调研报告质量高，建议附带关键数据来源")
        if st.button("➕ 添加", key=f"add_exp_{agent_name}") and new_exp_key.strip() and new_exp_val.strip():
            exp[new_exp_key.strip()] = new_exp_val.strip()
            st.rerun()

    # 自我反思（垂直布局，避免中文标签挤压）
    with st.expander("🪞 自我反思 (self_reflections)", expanded=False):
        refls = profile.get("self_reflections", [])
        del_indices = []
        for i, r in enumerate(refls):
            st.caption(f"#{i+1}")
            c_left, c_right = st.columns([6, 1])
            with c_left:
                r["date"] = st.text_input("日期", value=r.get("date", ""), key=f"refl_date_{agent_name}_{i}")
                r["improvement"] = st.text_input(
                    "改进建议", value=r.get("improvement", ""), key=f"refl_imp_{agent_name}_{i}")
            with c_right:
                st.write("")
                st.write("")
                if st.button("🗑️ 删除", key=f"refl_del_{agent_name}_{i}"):
                    del_indices.append(i)
            st.divider()
        if del_indices:
            for i in sorted(del_indices, reverse=True):
                refls.pop(i)
            st.rerun()

    profile["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 底部操作栏：padding-bottom 防止被固定输入框遮挡
    st.markdown('<div style="padding-bottom: 20px;">', unsafe_allow_html=True)
    c_save, c_close, c_space = st.columns([1, 1, 4])
    with c_save:
        if st.button("💾 保存", key=f"save_profile_{agent_name}", use_container_width=True, type="primary"):
            os.makedirs(os.path.dirname(profile_path), exist_ok=True)
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            agent = agents.get(agent_name)
            if agent:
                agent.profile = profile
                agent.agent.update_system_message(agent._build_system_message(agent.raw_system_message))
            st.session_state.pop(profile_key, None)
            st.toast(f"✅ {agent_name} 画像已保存")
            st.rerun()
    with c_close:
        if st.button("❌ 关闭", key=f"close_profile_{agent_name}", use_container_width=True):
            st.session_state.pop(profile_key, None)
            st.session_state.profile_agent = None
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# =============================================================================
# 路由
# =============================================================================
v = st.session_state.view

if v == "private": render_private_chat()
elif v == "group": render_group_chat()
elif v == "auto": render_auto_coordination()
elif v == "review": render_review()
