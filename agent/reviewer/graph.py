"""Reviewer Agent Graph - Following Original Code Patterns"""

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from typing import List, TypedDict, Optional
import os
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agent.reviewer.state import CodeReviewerState
from agent.tools.search import search_tools  # ORIGINAL tools
from agent.tools.codemap import codemap_tools  # ORIGINAL tools
from agent.tools.write import get_files_structure
from helpers.prompts import markdown_to_prompt_template

# Load prompts - following original pattern
review_research_prompt = markdown_to_prompt_template("agent/reviewer/prompts/review_research.md")
generate_review_prompt = markdown_to_prompt_template("agent/reviewer/prompts/generate_review.md")

# Create runnables
review_research_runnable = review_research_prompt | ChatAnthropic(model="claude-sonnet-4-20250514", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")).bind_tools(search_tools + codemap_tools)
generate_review_runnable = generate_review_prompt | ChatAnthropic(model="claude-sonnet-4-20250514", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))

# Tool node - using ORIGINAL tools
tool_node = ToolNode(search_tools + codemap_tools, messages_key="review_scratchpad")

def research_for_review(state: CodeReviewerState):
    """Research code to understand quality - following original pattern"""
    response = review_research_runnable.invoke({
        "files_to_review": state.files_to_review,
        "review_scratchpad": state.review_scratchpad,
        "codebase_structure": get_files_structure.invoke({"directory": "./workspace_repo"})
    })
    
    return {"review_scratchpad": [response]}

def generate_review(state: CodeReviewerState):
    """Generate review based on research"""
    response = generate_review_runnable.invoke({
        "review_scratchpad": state.review_scratchpad
    })
    
    return {
        "review_summary": response.content,
        "review_scratchpad": [AIMessage(content=response.content)]
    }

def should_call_tool(state: CodeReviewerState):
    """Router - following original pattern"""
    if state.review_scratchpad:
        last_message = state.review_scratchpad[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "call_tools"
    
    return "generate_review"

# Define workflow
workflow = StateGraph(CodeReviewerState)

# Add nodes
workflow.add_node("research_for_review", research_for_review)
workflow.add_node("generate_review", generate_review)
workflow.add_node("tools", tool_node)

# Add edges
workflow.add_edge(START, "research_for_review")
workflow.add_conditional_edges(
    "research_for_review",
    should_call_tool,
    {
        "call_tools": "tools",
        "generate_review": "generate_review"
    }
)
workflow.add_edge("tools", "research_for_review")
workflow.add_edge("generate_review", END)

# Compile
swe_reviewer = workflow.compile()
