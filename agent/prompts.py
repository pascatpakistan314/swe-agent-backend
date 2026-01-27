
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Robust import for tool_descriptions (works whether the package exports it or not)
try:
    from agent.tools import tool_descriptions  # prefer package export
except Exception:
    from agent.tools.search import search_tools
    from agent.tools.codemap import codemap_tools
    from agent.tools.agents_md import agents_md_tools
    from agent.tools.sandbox import sandbox_tools
    from agent.tools.multi_language_sandbox import multi_language_sandbox_tools
    from agent.tools.multi_language_builder import multi_language_build_tools
    from agent.tools.terminal import terminal_tools

    def _tools_to_str(tools: list) -> str:
        return "\n---\n".join(
            f"Tool Name: {t.name}\nTool Description: {getattr(t, 'description', '')}" for t in tools
        )

    tool_descriptions = _tools_to_str(
        search_tools
        + codemap_tools
        + agents_md_tools
        + sandbox_tools
        + multi_language_sandbox_tools
        + multi_language_build_tools
        + terminal_tools
    )

# THINK — advisory only; no tool calls
SYSTEM_PROMPT_THINK = (
    "You are an AI Software Architecture Consultant advising a human Software Engineer.\n"
    "You see a list of tools the engineer can use to complete the task, but you will not call tools yourself.\n"
    "Think step by step and recommend the single best next action the engineer should take and why.\n"
    "Write exactly one paragraph of 3–6 sentences. Do not ask questions or seek permission.\n"
    "Use self-reflective language (e.g., “I would…”, “I think…”, “I must…”). "
    "Assume no prior knowledge of the codebase beyond what is provided.\n"
    "\nAvailable tools:\n"
    f"{tool_descriptions}\n"
)
# (No-CoT variant if needed later: “Write a concise 2–4 sentence plan. Do not reveal your internal chain-of-thought.”)

SYSTEM_PROMPT_ACT = (
    "You are a Software Engineering Agent. You will receive the architect’s analysis (THINK) as context.\n"
    "Follow that analysis exactly and use the available tools to complete the task. "
    "Do not add your own independent reasoning beyond executing the plan. "
    "When a tool is required, call it; otherwise, make a concise status update or finish.\n"
)

# Choose ONE of these patterns for THINK:

# A) If you pass `input=...` AND also pass a history list under `messages`:
PROMPT_THINK = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT_THINK),
    MessagesPlaceholder("messages"),   # prior turns, if any
    ("human", "{input}"),              # the new user task
])

# B) If you already append the human message into `messages`, use this instead:
# PROMPT_THINK = ChatPromptTemplate.from_messages([
#     ("system", SYSTEM_PROMPT_THINK),
#     MessagesPlaceholder("messages"),
# ])

# ACT — gets the full running thread (including THINK output)
PROMPT_ACT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT_ACT),
    MessagesPlaceholder("messages"),   # should include the THINK assistant message before ACT runs
])
