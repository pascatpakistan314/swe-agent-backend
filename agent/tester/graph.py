"""Tester Agent Graph - Enhanced with full test pipeline"""

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

from agent.tester.state import SoftwareTesterState
from agent.tools.search import search_tools
from agent.tools.codemap import codemap_tools
from agent.tools.write import get_files_structure
from agent.tools.agents_md import agents_md_tools        # optional: align with architect/dev
from agent.tools.sandbox import sandbox_tools            # optional
from agent.tools.multi_language_sandbox import multi_language_sandbox_tools  # optional
from agent.tools.multi_language_builder import multi_language_build_tools    # optional
from helpers.prompts import markdown_to_prompt_template

# Load prompts
test_research_prompt = markdown_to_prompt_template("agent/tester/prompts/test_research.md")
plan_test_strategy_prompt = markdown_to_prompt_template("agent/tester/prompts/plan_test_strategy.md")
generate_test_cases_prompt = markdown_to_prompt_template("agent/tester/prompts/generate_test_cases.md")
execute_tests_prompt = markdown_to_prompt_template("agent/tester/prompts/execute_tests.md")
analyze_coverage_prompt = markdown_to_prompt_template("agent/tester/prompts/analyze_coverage.md")

# Create runnables (Claude)
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# (optional) give tester AGENTS.md + sandbox/build tools too
enhanced_tester_tools = search_tools + codemap_tools + agents_md_tools + sandbox_tools + multi_language_sandbox_tools + multi_language_build_tools

test_research_runnable = test_research_prompt | ChatAnthropic(model=MODEL, anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")).bind_tools(enhanced_tester_tools)
plan_test_strategy_runnable = plan_test_strategy_prompt | ChatAnthropic(model=MODEL, anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))
generate_test_cases_runnable = generate_test_cases_prompt | ChatAnthropic(model=MODEL, anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))
execute_tests_runnable = execute_tests_prompt | ChatAnthropic(model=MODEL, anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))
analyze_coverage_runnable = analyze_coverage_prompt | ChatAnthropic(model=MODEL, anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))

# Tool node
tool_node = ToolNode(enhanced_tester_tools, messages_key="testing_scratchpad")

def research_for_testing(state: SoftwareTesterState):
    """Research codebase to understand what needs testing"""
    response = test_research_runnable.invoke({
        "implementation_plan": state.implementation_plan,
        "testing_scratchpad": state.testing_scratchpad,
        "codebase_structure": get_files_structure.invoke({"directory": "./workspace_repo"})
    })
    
    return {"testing_scratchpad": [response]}

def plan_test_strategy(state: SoftwareTesterState):
    """Design a comprehensive test strategy"""
    response = plan_test_strategy_runnable.invoke({
        "implementation_plan": state.implementation_plan,
        "codebase_structure": get_files_structure.invoke({"directory": "./workspace_repo"})
    })
    return {
        "test_strategy": response.content,
        "test_plan": response.content,
        "testing_scratchpad": [AIMessage(content=response.content)]
    }

def generate_test_cases(state: SoftwareTesterState):
    """Generate concrete test cases from strategy"""
    response = generate_test_cases_runnable.invoke({
        "implementation_plan": state.implementation_plan,
        "test_strategy": state.test_strategy or state.test_plan,
        "testing_scratchpad": state.testing_scratchpad
    })
    return {
        "test_cases": response.content,
        "testing_scratchpad": [AIMessage(content=response.content)]
    }

def execute_tests(state: SoftwareTesterState):
    """Execute test cases (conceptually) and collect results"""
    response = execute_tests_runnable.invoke({
        "test_cases": state.test_cases,
        "testing_scratchpad": state.testing_scratchpad
    })
    return {
        "test_results": response.content,
        "testing_scratchpad": [AIMessage(content=response.content)]
    }

def analyze_coverage(state: SoftwareTesterState):
    """Analyze coverage and produce a coverage/quality report"""
    response = analyze_coverage_runnable.invoke({
        "test_results": state.test_results,
        "implementation_plan": state.implementation_plan,
        "testing_scratchpad": state.testing_scratchpad
    })
    return {
        "coverage_report": response.content,
        "testing_scratchpad": [AIMessage(content=response.content)]
    }

def should_call_tool(state: SoftwareTesterState):
    """Router"""
    if not state.testing_scratchpad:
        return "next"
    last_message = state.testing_scratchpad[-1]
    # Continue tool loop if we either requested a tool OR just received a tool result
    if getattr(last_message, "tool_calls", None) or getattr(last_message, "type", None) == "tool":
        return "call_tools"
    return "next"

# Define workflow
workflow = StateGraph(SoftwareTesterState)

# Add nodes
workflow.add_node("research_for_testing", research_for_testing)
workflow.add_node("plan_test_strategy", plan_test_strategy)
workflow.add_node("generate_test_cases", generate_test_cases)
workflow.add_node("execute_tests", execute_tests)
workflow.add_node("analyze_coverage", analyze_coverage)
workflow.add_node("tools", tool_node)

# Add edges
workflow.add_edge(START, "research_for_testing")
workflow.add_conditional_edges("research_for_testing", should_call_tool, {
    "call_tools": "tools",
    "next": "plan_test_strategy"
})
workflow.add_edge("tools", "research_for_testing")
workflow.add_edge("plan_test_strategy", "generate_test_cases")
workflow.add_edge("generate_test_cases", "execute_tests")
workflow.add_edge("execute_tests", "analyze_coverage")
workflow.add_edge("analyze_coverage", END)

# Compile the graph
swe_tester = workflow.compile()