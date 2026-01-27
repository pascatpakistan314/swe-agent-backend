# Enhanced architect graph with AGENTS.md and sandbox support + TOKEN MANAGEMENT

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import json
import os
from typing import List, TypedDict, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.constants import END, START
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph

from agent.architect.state import SoftwareArchitectState
from agent.tools.search import search_tools
from agent.tools.codemap import codemap_tools
from agent.tools.write import get_files_structure
from agent.tools.agents_md import agents_md_tools  # NEW
from agent.tools.sandbox import sandbox_tools  # NEW
from agent.tools.multi_language_sandbox import multi_language_sandbox_tools  # MULTI-LANGUAGE
from agent.tools.multi_language_builder import multi_language_build_tools  # BUILD TOOLS
from agent.tools.terminal import terminal_tools  # TERMINAL
from helpers.prompts import markdown_to_prompt_template
from agent.common.entities import ImplementationPlan, ImplementationTask, AtomicTask
from langchain_core.output_parsers.openai_tools import PydanticToolsParser


class ResearchStep(BaseModel):
    reasoning: str = Field(description="The reasoning behind the research step, why research is needed how it going to help the implementation of the task")
    hypothesis: str = Field(description="The hypothesis that need to be researched")


class ResearchEvaluation(BaseModel):
    reasoning: str = Field(description="The reason why the research step is valid or not 1-3 sentences")
    is_valid: bool = Field(description="Whether the research step is valid")


# NEW: Add validation and critique models
class PreValidationDecision(BaseModel):
    verdict: str = Field(description="READY or MORE_RESEARCH")
    gaps: List[str] = Field(default=[], description="Identified gaps in research")
    suggested_next_step: Optional[str] = Field(default=None, description="Next research step if needed")


class PlanCritique(BaseModel):
    has_issues: bool = Field(description="Whether plan has issues")
    issues: List[str] = Field(default=[], description="List of specific issues")
    fix_hint: Optional[str] = Field(default=None, description="Hint for fixing issues")


# Constants
CLAUDE_CONTEXT_LIMIT = 200_000  # Claude Sonnet 4's context window
MIN_OUTPUT_TOKENS = 8000  # Minimum tokens to reserve for output
MAX_RESEARCH_TOKENS = 10000  # Maximum tokens for research findings
MAX_OUTPUT_LIMIT = 64000  # Sonnet 4 supports up to ~64k tokens of output

# Token counting utility
def approx_token_count(content) -> int:
    """
    Estimate token count by dividing character length by ~4.
    This is a rough approximation - 1 token ≈ 4 characters in English.
    """
    if isinstance(content, list):
        # Handle list of messages
        text = ""
        for m in content:
            if isinstance(m, (AIMessage, HumanMessage)):
                text += str(m.content)
            else:
                text += str(m)
    elif isinstance(content, str):
        text = content
    else:
        text = str(content)
    
    # Ensure at least 1 token
    return max(1, len(text) // 4)

def calculate_max_output_tokens(input_content, min_tokens=MIN_OUTPUT_TOKENS) -> int:
    """
    Calculate maximum output tokens based on input size and Claude's context limit.
    Ensures we never request more tokens than available.
    Now also respects Claude 4 Sonnet's 64k output limit.
    """
    input_tokens = approx_token_count(input_content)
    
    # Calculate available tokens, ensuring non-negative
    available_tokens = max(0, CLAUDE_CONTEXT_LIMIT - input_tokens)
    
    # If we don't have enough space for minimum tokens, use what's available
    if available_tokens < min_tokens:
        print(f"Warning: Only {available_tokens} tokens available, less than minimum {min_tokens}")
        return max(100, available_tokens - 100)  # Leave small buffer, ensure at least 100 tokens
    
    # Standard calculation: use available space minus buffer, but cap at half context
    max_output = min(available_tokens - 1000, CLAUDE_CONTEXT_LIMIT // 2)
    
    # Clamp to the model's supported maximum output limit (64k for Claude 4 Sonnet)
    max_output = min(max_output, MAX_OUTPUT_LIMIT)
    
    # Ensure we don't exceed available tokens
    max_output = min(max_output, available_tokens - 100)  # Small safety buffer
    
    return max(min_tokens, max_output)

def convert_tools_messages_to_ai_and_human(implementation_research_scratchpad: List[AnyMessage]):
    """Convert tool messages to AI and Human messages for better processing"""
    messages = []
    for message in implementation_research_scratchpad:
        if getattr(message, "type", None) == "ai":
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                tool_name = message.tool_calls[0]["name"]
                tool_args = json.dumps(message.tool_calls[0]["args"])
                messages.append(AIMessage(content=f"I want to call the tool {tool_name} with the following arguments: {tool_args}"))
            else:
                messages.append(message)
        elif message.type == "tool":
            messages.append(HumanMessage(content=f"When executing Tool {message.name} \n The result was {message.content} was called"))
        else:
            messages.append(message)
    return messages

def truncate_research_findings(research_findings: List[AnyMessage], max_tokens: int = MAX_RESEARCH_TOKENS, aggressive: bool = False) -> List[AnyMessage]:
    """
    Truncate research findings to fit within token limit while preserving most recent context.
    
    Args:
        research_findings: List of messages to truncate
        max_tokens: Maximum token limit
        aggressive: If True, applies more aggressive truncation
    """
    current_tokens = approx_token_count(research_findings)
    
    # Apply aggressive truncation if requested
    target_tokens = max_tokens // 2 if aggressive else max_tokens
    
    if current_tokens <= target_tokens:
        return research_findings
    
    print(f"Research findings too long ({current_tokens} tokens), truncating to {target_tokens} tokens...")
    
    # Strategy 1: Keep only the most recent messages
    truncated = []
    total_tokens = 0
    
    # Start from the end and work backwards (keep most recent)
    for message in reversed(research_findings):
        msg_tokens = approx_token_count(message)
        if total_tokens + msg_tokens <= target_tokens:
            truncated.insert(0, message)
            total_tokens += msg_tokens
        else:
            # Try to include a truncated version of this message if we have room
            remaining_tokens = target_tokens - total_tokens
            if remaining_tokens > 100:  # Only if we have meaningful space left
                content = str(message.content) if hasattr(message, 'content') else str(message)
                # Keep approximately remaining_tokens worth of characters
                max_chars = remaining_tokens * 4
                truncated_content = content[:max_chars] + "... [truncated]"
                
                if isinstance(message, AIMessage):
                    truncated.insert(0, AIMessage(content=truncated_content))
                elif isinstance(message, HumanMessage):
                    truncated.insert(0, HumanMessage(content=truncated_content))
                else:
                    # For other message types, skip if can't truncate
                    pass
            break
    
    # If we couldn't fit any complete messages, take at least the last one
    if not truncated and research_findings:
        last_msg = research_findings[-1]
        # Truncate the content of the last message if needed
        if isinstance(last_msg, (AIMessage, HumanMessage)):
            content = str(last_msg.content)
            # Keep approximately target_tokens worth of characters
            max_chars = target_tokens * 4
            if len(content) > max_chars:
                truncated_content = content[:max_chars] + "... [truncated]"
                if isinstance(last_msg, AIMessage):
                    truncated = [AIMessage(content=truncated_content)]
                else:
                    truncated = [HumanMessage(content=truncated_content)]
            else:
                truncated = [last_msg]
        else:
            truncated = [last_msg]
    
    print(f"Kept {len(truncated)} out of {len(research_findings)} messages ({approx_token_count(truncated)} tokens)")
    return truncated

def chunk_by_size(messages: List[AnyMessage], chunk_size: int) -> List[List[AnyMessage]]:
    """
    Split messages into chunks of length `chunk_size`.
    """
    return [messages[i:i + chunk_size] for i in range(0, len(messages), chunk_size)]

def chunk_by_tokens(messages: List[AnyMessage], max_tokens: int) -> List[List[AnyMessage]]:
    """
    Split messages into chunks such that the total token count per chunk does not
    exceed `max_tokens`.
    """
    chunks: List[List[AnyMessage]] = []
    current_chunk: List[AnyMessage] = []
    current_tokens = 0
    
    for msg in messages:
        msg_tokens = approx_token_count([msg])
        # If adding this message would exceed the limit, start a new chunk
        if current_tokens + msg_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [msg]
            current_tokens = msg_tokens
        else:
            current_chunk.append(msg)
            current_tokens += msg_tokens
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

# Load prompts
plan_next_step_prompt = markdown_to_prompt_template("agent/architect/prompts/plan_next_step_prompt.md")
check_research_prompt = markdown_to_prompt_template("agent/architect/prompts/check_research_already_explored.md")
conduct_research_prompt = markdown_to_prompt_template("agent/architect/prompts/conduct_research_plan_prompt.md")
extract_implementation_prompt = markdown_to_prompt_template("agent/architect/prompts/extract_implementation_plan.md")

# Create runnables with enhanced tools - ALL LANGUAGES
enhanced_tools = (
    search_tools + 
    codemap_tools + 
    agents_md_tools + 
    sandbox_tools +
    multi_language_sandbox_tools +
    multi_language_build_tools +
    terminal_tools
)

# Use Claude 4 Sonnet (IMPORTANT FIX!)
plan_next_step_runnable = plan_next_step_prompt | ChatAnthropic(
    model="claude-sonnet-4-20250514",  # Claude 4!
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
).with_structured_output(ResearchStep)

check_research_runnable = check_research_prompt | ChatAnthropic(
    model="claude-sonnet-4-20250514",  # Claude 4!
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
).with_structured_output(ResearchEvaluation)

conduct_research_runnable = conduct_research_prompt | ChatAnthropic(
    model="claude-sonnet-4-20250514",  # Claude 4!
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
).bind_tools(enhanced_tools)

# Enhanced tool node with all tools
tool_node = ToolNode(enhanced_tools, messages_key="implementation_research_scratchpad")

class ComeUpWithResearchNextStepOutput(TypedDict):
    research_next_step: str
    implementation_research_scratchpad: List[AnyMessage]

def come_up_with_research_next_step(state: SoftwareArchitectState) -> ComeUpWithResearchNextStepOutput:
    """Generate the next research step based on the current state - now reads AGENTS.md first"""
    
    # First, check for AGENTS.md context
    from agent.tools.agents_md import get_task_context
    agents_context = get_task_context.invoke({
        "task": state.task_description,
        "directory": "./workspace_repo"
    })
    
    response = plan_next_step_runnable.invoke({
        "task_description": state.task_description,
        "implementation_research_scratchpad": state.implementation_research_scratchpad,
        "codebase_structure": get_files_structure.invoke({
            "directory": "./workspace_repo"
        }),
        "agents_context": agents_context  # Add AGENTS.md context
    })
    
    return {"research_next_step": response.hypothesis,
            "implementation_research_scratchpad": [
                AIMessage(content=f"My next thing i need to check is {response.hypothesis}"
                          f"This is why I think it is useful: {response.reasoning}")]}

class CheckResearchStepOutput(TypedDict):
    is_valid_research_step: bool
    implementation_research_scratchpad: List[AnyMessage]

def check_research_step(state: SoftwareArchitectState)-> CheckResearchStepOutput:
    """Check if the proposed research step has already been explored"""
    response = check_research_runnable.invoke({
         "task_description": state.task_description,   
        "implementation_research_scratchpad": state.implementation_research_scratchpad
    })
    if not response.is_valid:
        return {
            "is_valid_research_step": False,
            "implementation_research_scratchpad": [
                HumanMessage(content=f"The research path is not valid, here is why: {response.reasoning}")
            ]
        }
    return {
        "is_valid_research_step": True,
        "implementation_research_scratchpad": [
            HumanMessage(content=f"The research path is valid, start conducting the research")
        ]
    }

def should_conduct_research(state: SoftwareArchitectState) -> str:
    """Router to determine if research should be done"""
    if state.is_valid_research_step:
        return "plan_is_valid"
    else:
        return "plan_is_not_valid"

def conduct_research(state: SoftwareArchitectState):
    """Conduct research using the available tools - enhanced with sandbox"""
    response = conduct_research_runnable.invoke({
        "task_description": state.task_description,
        "implementation_research_scratchpad": state.implementation_research_scratchpad,
        "research_next_step": state.research_next_step,
        "codebase_structure": get_files_structure.invoke({
            "directory": "./workspace_repo"
        })
    })
    return {"implementation_research_scratchpad": [response]}


# NEW: Add pre-validation function
def pre_validate_research_findings(state: SoftwareArchitectState):
    """
    Reason about the research and decide if we can extract the plan now.
    Returns structured verdict with proper state management.
    """
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Convert research to readable format (last 10 messages for efficiency)
    research_summary = convert_tools_messages_to_ai_and_human(
        state.implementation_research_scratchpad[-10:] if len(state.implementation_research_scratchpad) > 10 
        else state.implementation_research_scratchpad
    )
    
    prompt = f"""
You have just completed research for: {state.task_description}

Research findings (latest first):
{research_summary}

Codebase structure:
{get_files_structure.invoke({"directory": "./workspace_repo"})}

Before creating an implementation plan, think critically:
- If we tried to implement/run now, what would break first?
- What assumptions are unverified?
- What dependencies/configs may be missing?
- What additional research would de-risk the next step?

Respond as strict JSON with keys:
{{
  "verdict": "READY" | "MORE_RESEARCH",
  "gaps": string[],
  "suggested_next_step": string | null
}}
"""
    
    decision = llm.with_structured_output(PreValidationDecision).invoke(prompt)
    
    # Return ONLY new messages - let state reducer handle appending
    msgs = [AIMessage(content=f"PRE_VALIDATION → verdict={decision.verdict}; gaps={decision.gaps}")]
    
    result = {"implementation_research_scratchpad": msgs}
    
    # Add research_next_step only if needed
    if decision.verdict == "MORE_RESEARCH" and decision.suggested_next_step:
        result["research_next_step"] = decision.suggested_next_step
        
    return result


# NEW: Add post-plan critique function
def post_plan_llm_critique(llm, plan: ImplementationPlan) -> PlanCritique:
    """
    Critique an implementation plan for concrete execution risks.
    """
    plan_json_str = plan.model_dump_json(indent=2)
    
    critique_prompt = f"""
Validate this plan for concrete failure risks ONLY:
1) Missing entry/config files assumed by tasks
2) Edits to non-existent files without prior create
3) Imports likely to fail (missing targets)
4) Wrong task ordering (dependent before dependency)
5) Missing external deps (npm/py)

Return strict JSON:
{{"has_issues": bool, "issues": string[], "fix_hint": string|null}}

Plan (JSON):
{plan_json_str}
"""
    
    return llm.with_structured_output(PlanCritique).invoke(critique_prompt)


def should_call_tool(state: SoftwareArchitectState):
    """Router to determine if tools should be called"""
    if not state.implementation_research_scratchpad:
        return "implement_plan"
    last_message = state.implementation_research_scratchpad[-1]

    # Keep looping if we either asked to call a tool OR just received a tool result
    if getattr(last_message, "tool_calls", None) or getattr(last_message, "type", None) == "tool":
        return "should_call_tool"
    return "implement_plan"


# NEW: Add routing function for validation
def should_extract_or_research(state: SoftwareArchitectState) -> str:
    """
    Route based on pre-validation verdict using structured check.
    """
    if not state.implementation_research_scratchpad:
        return "extract_plan"
    
    last = state.implementation_research_scratchpad[-1]
    content = str(getattr(last, "content", "")).upper()
    
    # Check for structured verdict in message
    if "VERDICT=MORE_RESEARCH" in content:
        return "continue_research"
    
    return "extract_plan"


def validate_and_fix_file_paths(plan: ImplementationPlan) -> ImplementationPlan:
    """
    Validate and fix file paths in implementation plan to ensure they point to files, not directories.
    """
    import os
    
    for task in plan.tasks:
        file_path = task.file_path
        
        # Check if file_path is empty, None, or just a directory
        if not file_path or file_path == "./workspace_repo" or file_path == "workspace_repo":
            task.file_path = "./workspace_repo/main.py"
            print(f"Fixed invalid file_path: '{file_path}' -> '{task.file_path}'")
            continue
            
        # Check if it ends with a directory separator
        if file_path.endswith('/') or file_path.endswith('\\'):
            task.file_path = os.path.join(file_path, "main.py")
            print(f"Fixed directory path: '{file_path}' -> '{task.file_path}'")
            continue
            
        # Check if it's a directory path without extension
        if '.' not in os.path.basename(file_path):
            # Likely a directory, append main.py
            task.file_path = os.path.join(file_path, "main.py")
            print(f"Fixed probable directory: '{file_path}' -> '{task.file_path}'")
            
    return plan

def extract_implementation_plan(state: SoftwareArchitectState):
    """
    Extract implementation plan from research findings with chunking support and AGENTS.md context.
    Enhanced with post-plan critique for both single-batch and chunked paths.
    """
    
    # Get the LLM instance - using Claude 4 Sonnet
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",  # Claude 4!
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        verbose=True,
        max_tokens=8192
    )
    
    # Generate the output format from the Pydantic model
    output_format_hint = (
        "IMPORTANT: You MUST use ONLY a tool call. Do NOT output any text or explanation. "
        "Call the ImplementationPlan tool with tasks list directly."
    )
    
    # Get AGENTS.md guidelines for implementation
    from agent.tools.agents_md import get_agents_md_section
    coding_guidelines = get_agents_md_section.invoke({
        "section_name": "Code Style Guidelines",
        "directory": "./workspace_repo"
    })
    
    # Prepare research findings
    research_findings = convert_tools_messages_to_ai_and_human(state.implementation_research_scratchpad)
    
    # Get codebase structure
    codebase_structure = get_files_structure.invoke({"directory": "./workspace_repo"}) or "(empty repo)"
    
    # Truncate codebase structure if too long
    codebase_tokens = approx_token_count(codebase_structure)
    if codebase_tokens > 5000:
        print(f"Codebase structure too long ({codebase_tokens} tokens), truncating...")
        max_chars = 5000 * 4
        codebase_structure = codebase_structure[:max_chars] + "\n... [truncated]"
    
    # Check if we need to chunk the research findings
    research_tokens = approx_token_count(research_findings)
    
    if research_tokens > MAX_RESEARCH_TOKENS:
        print(f"Research findings too large ({research_tokens} tokens), processing in chunks...")
        
        # Process in chunks and accumulate tasks
        all_tasks: List[ImplementationTask] = []
        
        # Chunk by tokens to ensure each chunk fits
        chunks = chunk_by_tokens(research_findings, MAX_RESEARCH_TOKENS // 2)
        
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i + 1}/{len(chunks)}...")
            
            chunk_inputs = {
                "task_description": state.task_description,
                "research_findings": chunk,
                "codebase_structure": codebase_structure if i == 0 else "(see previous chunk)",
                "coding_guidelines": coding_guidelines if i == 0 else "(see previous chunk)",
                "output_format": output_format_hint
            }
            
            # Calculate appropriate max_tokens for this chunk
            total_input = [
                HumanMessage(content=state.task_description),
                *chunk,
                HumanMessage(content=chunk_inputs["codebase_structure"]),
                HumanMessage(content=chunk_inputs["coding_guidelines"]),
                HumanMessage(content=output_format_hint)
            ]
            
            max_output_tokens = calculate_max_output_tokens(total_input)
            print(f"Chunk {i + 1} - Input tokens: ~{approx_token_count(total_input)}, Max output tokens: {max_output_tokens}")
            
            # Configure LLM with calculated token limit and bind tools
            llm_for_extract = llm.bind(max_tokens=max_output_tokens).bind_tools([ImplementationPlan])
            parser = PydanticToolsParser(first_tool_only=True, tools=[ImplementationPlan])
            
            # Build the runnable chain
            extract_implementation_runnable = extract_implementation_prompt | llm_for_extract | parser
            
            try:
                # Try to extract plan for this chunk
                plan = extract_implementation_runnable.invoke(chunk_inputs, config={"tags": ["agent-v1"]})
                
                if plan and getattr(plan, "tasks", None):
                    print(f"Extracted {len(plan.tasks)} tasks from chunk {i + 1}")
                    all_tasks.extend(plan.tasks)
            except Exception as e:
                print(f"Failed to extract from chunk {i + 1}: {e}")
                continue
        
        # NEW: Critique the merged plan from chunks
        if all_tasks:
            print(f"Successfully extracted total of {len(all_tasks)} tasks from {len(chunks)} chunks")
            
            merged_plan = ImplementationPlan(tasks=all_tasks)
            # Validate and fix file paths
            merged_plan = validate_and_fix_file_paths(merged_plan)
            try:
                critique = post_plan_llm_critique(llm, merged_plan)
                
                if critique.has_issues:
                    print(f"Chunked plan critique found issues: {critique.issues}")
                    
                    # Re-extract with critique feedback
                    critique_context = HumanMessage(
                        content=f"IMPORTANT: Address these issues:\n"
                                f"Issues: {', '.join(critique.issues)}\n"
                                f"Fix hint: {critique.fix_hint}"
                    )
                    
                    # Use the last chunk's context plus critique
                    enhanced_chunk = chunks[-1] + [critique_context]
                    
                    chunk_inputs = {
                        "task_description": state.task_description,
                        "research_findings": enhanced_chunk,
                        "codebase_structure": codebase_structure,
                        "coding_guidelines": coding_guidelines,
                        "output_format": output_format_hint
                    }
                    
                    # Recalculate tokens
                    total_input = [
                        HumanMessage(content=state.task_description),
                        *enhanced_chunk,
                        HumanMessage(content=codebase_structure),
                        HumanMessage(content=coding_guidelines),
                        HumanMessage(content=output_format_hint)
                    ]
                    
                    max_output_tokens = calculate_max_output_tokens(total_input)
                    
                    llm_for_extract = llm.bind(max_tokens=max_output_tokens).bind_tools([ImplementationPlan])
                    parser = PydanticToolsParser(first_tool_only=True, tools=[ImplementationPlan])
                    extract_implementation_runnable = extract_implementation_prompt | llm_for_extract | parser
                    
                    fix_plan = extract_implementation_runnable.invoke(
                        chunk_inputs,
                        config={"tags": ["agent-v1", "chunk-fix"]}
                    )
                    
                    if fix_plan and getattr(fix_plan, "tasks", None):
                        # Merge the fix with other tasks
                        all_tasks.extend(fix_plan.tasks)
                        merged_plan = ImplementationPlan(tasks=all_tasks)
                        
            except Exception as e:
                print(f"Chunked critique failed: {e}, using original merged plan")
            
            return {"implementation_plan": merged_plan}
        else:
            print("Failed to extract any tasks from chunks")
    
    else:
        # Original single-batch processing
        research_findings = truncate_research_findings(research_findings, MAX_RESEARCH_TOKENS)
        
        inputs = {
            "task_description": state.task_description,
            "research_findings": research_findings,
            "codebase_structure": codebase_structure,
            "coding_guidelines": coding_guidelines,
            "output_format": output_format_hint
        }
        
        # Calculate appropriate max_tokens based on actual input size
        total_input = [
            HumanMessage(content=state.task_description),
            *research_findings,
            HumanMessage(content=codebase_structure),
            HumanMessage(content=coding_guidelines),
            HumanMessage(content=output_format_hint)
        ]
        
        max_output_tokens = calculate_max_output_tokens(total_input)
        input_tokens = approx_token_count(total_input)
        print(f"Input tokens: ~{input_tokens}, Max output tokens: {max_output_tokens}")
        
        # Configure LLM with calculated token limit and bind tools
        llm_for_extract = llm.bind(max_tokens=max_output_tokens).bind_tools([ImplementationPlan])
        parser = PydanticToolsParser(first_tool_only=True, tools=[ImplementationPlan])
        
        # Build the runnable chain
        extract_implementation_runnable = extract_implementation_prompt | llm_for_extract | parser
        
        # Retry logic to handle edge cases
        plan = None
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                print(f"Attempt {attempt + 1}: Extracting implementation plan...")
                
                plan = extract_implementation_runnable.invoke(inputs, config={"tags": ["agent-v1"]})
                
                if plan and getattr(plan, "tasks", None):
                    print(f"Successfully extracted plan with {len(plan.tasks)} tasks")
                    
                    # NEW: Add critique pass for single-batch
                    try:
                        critique = post_plan_llm_critique(llm, plan)
                        
                        if critique.has_issues:
                            print(f"Plan critique found issues: {critique.issues}")
                            
                            critique_context = HumanMessage(
                                content=f"IMPORTANT: Address these issues:\n"
                                        f"Issues: {', '.join(critique.issues)}\n"
                                        f"Fix hint: {critique.fix_hint}"
                            )
                            
                            # Re-run with critique
                            inputs["research_findings"] = research_findings + [critique_context]
                            
                            # Recalculate tokens
                            total_input = [
                                HumanMessage(content=state.task_description),
                                *inputs["research_findings"],
                                HumanMessage(content=codebase_structure),
                                HumanMessage(content=coding_guidelines),
                                HumanMessage(content=output_format_hint)
                            ]
                            
                            max_output_tokens = calculate_max_output_tokens(total_input)
                            
                            llm_for_extract = llm.bind(max_tokens=max_output_tokens).bind_tools([ImplementationPlan])
                            parser = PydanticToolsParser(first_tool_only=True, tools=[ImplementationPlan])
                            extract_implementation_runnable = extract_implementation_prompt | llm_for_extract | parser
                            
                            improved_plan = extract_implementation_runnable.invoke(
                                inputs,
                                config={"tags": ["agent-v1", "autofix-1"]}
                            )
                            
                            if improved_plan and getattr(improved_plan, "tasks", None):
                                print(f"Improved plan generated with {len(improved_plan.tasks)} tasks")
                                # Validate and fix file paths before returning
                                improved_plan = validate_and_fix_file_paths(improved_plan)
                                return {"implementation_plan": improved_plan}
                                
                    except Exception as e:
                        print(f"Critique pass failed: {e}, using original plan")
                    
                    # Validate generated code snippets if any
                    if plan.tasks:
                        for task in plan.tasks:
                            if hasattr(task, 'code_snippet') and task.code_snippet:
                                from agent.tools.sandbox import validate_code_safety
                                safety_check = validate_code_safety.invoke({"code": task.code_snippet})
                                print(f"Safety check for task {task.logical_task}: {safety_check}")
                    
                    # Validate and fix file paths before returning
                    plan = validate_and_fix_file_paths(plan)
                    return {"implementation_plan": plan}
                else:
                    print(f"Attempt {attempt + 1}: Got plan but no tasks")
                    
            except Exception as e:
                print(f"Attempt {attempt + 1} failed with error: {e}")
                
                if attempt < max_attempts - 1:
                    print(f"Retrying with more aggressive truncation (attempt {attempt + 2})...")
                    
                    reduction_factor = 2 ** (attempt + 1)
                    target_tokens = max(1000, MAX_RESEARCH_TOKENS // reduction_factor)
                    
                    research_findings = truncate_research_findings(
                        research_findings, 
                        target_tokens, 
                        aggressive=True
                    )
                    
                    max_codebase_chars = max(500, 5000 // reduction_factor) * 4
                    if len(codebase_structure) > max_codebase_chars:
                        codebase_structure = codebase_structure[:max_codebase_chars] + "\n... [truncated]"
                    
                    inputs["research_findings"] = research_findings
                    inputs["codebase_structure"] = codebase_structure
                    
                    total_input = [
                        HumanMessage(content=state.task_description),
                        *research_findings,
                        HumanMessage(content=codebase_structure),
                        HumanMessage(content=coding_guidelines),
                        HumanMessage(content=output_format_hint)
                    ]
                    max_output_tokens = calculate_max_output_tokens(total_input)
                    print(f"Retry {attempt + 2} - Input tokens: ~{approx_token_count(total_input)}, Max output tokens: {max_output_tokens}")
                    
                    llm_for_extract = llm.bind(max_tokens=max_output_tokens).bind_tools([ImplementationPlan])
                    extract_implementation_runnable = extract_implementation_prompt | llm_for_extract | parser
    
    # Create a minimal valid implementation plan as fallback
    print("Failed to extract complete implementation plan, using fallback")
    fallback_plan = ImplementationPlan(
        tasks=[
            ImplementationTask(
                file_path="./workspace_repo/main.py",
                logical_task="Implement the requested functionality",
                atomic_tasks=[
                    AtomicTask(
                        atomic_task="Implement the main logic based on the research",
                        additional_context="Use the research findings and AGENTS.md guidelines to guide the implementation"
                    )
                ]
            )
        ]
    )
    
    # Ensure fallback plan has valid file paths
    fallback_plan = validate_and_fix_file_paths(fallback_plan)
    return {"implementation_plan": fallback_plan}

# Input/Output types
class SoftwareArchitectInput(TypedDict):
    task_description: str
    implementation_research_scratchpad: List[AnyMessage]

class SoftwareArchitectOutput(TypedDict):
    implementation_plan: Optional[ImplementationPlan]

# Create enhanced architect graph
workflow = StateGraph(SoftwareArchitectState,
                      input=SoftwareArchitectInput,
                      output=SoftwareArchitectOutput)

# Define all workflow nodes
workflow.add_node("come_up_with_research_next_step", come_up_with_research_next_step)
workflow.add_node("check_research_step", check_research_step)
workflow.add_node("conduct_research", conduct_research)
workflow.add_node("pre_validate", pre_validate_research_findings)  # NEW node
workflow.add_node("extract_implementation_plan", extract_implementation_plan)
workflow.add_node("tools", tool_node)

# Set up workflow structure - conditional edges for decision points
workflow.add_edge(START, "come_up_with_research_next_step")
workflow.add_edge("come_up_with_research_next_step", "check_research_step")

# After checking research step, either continue with research or go back to planning
workflow.add_conditional_edges(
    "check_research_step",
    should_conduct_research,
    {
        "plan_is_valid": "conduct_research",
        "plan_is_not_valid": "come_up_with_research_next_step"
    }
)

# MODIFIED: After conducting research, go through pre-validation
workflow.add_conditional_edges(
    "conduct_research",
    should_call_tool,
    {
        "should_call_tool": "tools",
        "implement_plan": "pre_validate"  # Changed from "extract_implementation_plan"
    }
)

# NEW: Add routing from pre_validate
workflow.add_conditional_edges(
    "pre_validate",
    should_extract_or_research,
    {
        "continue_research": "conduct_research",
        "extract_plan": "extract_implementation_plan"
    }
)

# Tools always go back to conduct_research
workflow.add_edge("tools", "conduct_research")

# Extract implementation plan is the final step
workflow.add_edge("extract_implementation_plan", END)

# Compile and export the enhanced architect
swe_architect = workflow.compile()
