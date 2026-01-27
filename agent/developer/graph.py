from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import json
import os
import re  # Regular expression module
from typing import List
from diff_match_patch import diff_match_patch
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from helpers.prompts import markdown_to_prompt_template
from agent.developer.state import SoftwareDeveloperState, Diffs
from langgraph.prebuilt import ToolNode
from agent.tools.search import search_tools
from agent.tools.codemap import codemap_tools
from agent.tools.agents_md import agents_md_tools
from agent.tools.sandbox import sandbox_tools
from agent.tools.multi_language_sandbox import multi_language_sandbox_tools
from agent.tools.multi_language_builder import multi_language_build_tools
from agent.tools.write import get_files_structure

# Load the extract diff prompt
extract_diffs_tasks_prompt = markdown_to_prompt_template("agent/developer/prompts/create_diff_prompt.md")
implement_diffs_prompt = markdown_to_prompt_template("agent/developer/prompts/implement_diff.md")
implement_new_file_prompt = markdown_to_prompt_template("agent/developer/prompts/implement_new_file.md")

# ENHANCEMENT: Increased token limits for complete file generation
# Create the runnable with the prompt and model - UPDATED MODEL AND TOKENS
extract_diff_runnable = extract_diffs_tasks_prompt | ChatAnthropic(
    model="claude-sonnet-4-20250514",  # Updated model
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=8192  # Increased tokens
) | StrOutputParser()

edit_according_to_diff_runnable = implement_diffs_prompt | ChatAnthropic(
    model="claude-sonnet-4-20250514",  # Updated model
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=8192  # Increased tokens
) | StrOutputParser()

create_new_file_runnable = implement_new_file_prompt | ChatAnthropic(
    model="claude-sonnet-4-20250514",  # Updated model
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=8192  # Increased tokens
) | StrOutputParser()

# Load the get clear implementation plan prompt
get_clear_implementation_plan_prompt = markdown_to_prompt_template("agent/developer/prompts/get_clear_implementation_plan.md")

# Create the runnable with the prompt and model - UPDATED MODEL AND TOKENS
get_clear_implementation_plan_runnable = get_clear_implementation_plan_prompt | ChatAnthropic(
    model="claude-sonnet-4-20250514",  # Updated model
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=8192  # Increased tokens
).bind_tools(search_tools+codemap_tools)

dmp = diff_match_patch()

def start_implementing(state: SoftwareDeveloperState):
    """Initialize the implementation process"""
    # Check if we already have an implementation plan
    if state.implementation_plan is None:
        # If no plan exists, we need to create one from the architect
        # This happens when developer is invoked directly
        from agent.architect.graph_enhanced import swe_architect
        
        print("No implementation plan found, invoking architect first...")
        
        # Get task description from state or messages
        task_description = getattr(state, 'task_description', None)
        if not task_description and hasattr(state, 'messages') and state.messages:
            # Try to extract from messages
            for msg in state.messages:
                if hasattr(msg, 'content'):
                    task_description = msg.content
                    break
        
        if not task_description:
            raise ValueError("No task description provided and no implementation plan exists")
        
        # Invoke architect to get the plan
        architect_result = swe_architect.invoke({
            "task_description": task_description,
            "workspace_dir": getattr(state, 'workspace_dir', './workspace_repo')
        })
        
        # Extract the implementation plan
        implementation_plan = architect_result.get("implementation_plan")
        
        if not implementation_plan:
            raise ValueError("Architect failed to create implementation plan")
        
        # Update state with the plan
        return {
            "implementation_plan": implementation_plan,
            "current_task_idx": 0,
            "current_atomic_task_idx": 0
        }
    
    # If plan exists, just initialize indices
    return {
        "current_task_idx": 0,
        "current_atomic_task_idx": 0
    }


def proceed_to_next_atomic_task(state: SoftwareDeveloperState):
    # Get current indices
    current_task_idx = state.current_task_idx
    current_atomic_task_idx = state.current_atomic_task_idx
    
    # Get the implementation plan
    plan = state.implementation_plan
    
    # Get current task
    current_task = plan.tasks[current_task_idx]
    atomic_tasks = current_task.atomic_tasks
    
    # If we've completed all atomic tasks in current task
    if current_atomic_task_idx >= len(atomic_tasks) - 1:
        # Move to next main task and reset atomic task index
        return {
            "current_task_idx": current_task_idx + 1,
            "current_atomic_task_idx": 0
        }
    # Otherwise, move to next atomic task
    return {
        "current_task_idx": current_task_idx,
        "current_atomic_task_idx": current_atomic_task_idx + 1
    }


def get_clear_implementation_plan_for_atomic_task(state: SoftwareDeveloperState):
    current_task = state.implementation_plan.tasks[state.current_task_idx]
    current_atomic_task = current_task.atomic_tasks[state.current_atomic_task_idx]
    result = get_clear_implementation_plan_runnable.invoke({
        "development_task": current_atomic_task.atomic_task,
        "file_content": state.current_file_content,
        "target_file": current_task.file_path,
        "codebase_structure": state.codebase_structure,
        "additional_context": current_atomic_task.additional_context,
        "atomic_implementation_research": state.atomic_implementation_research
    })
    
    # Ensure scratchpad entries are message objects
    if not hasattr(result, "type"):  # likely a string
        result = AIMessage(content=str(result))
    
    return {"atomic_implementation_research": [result]}

def should_continue_implementation_research(state: SoftwareDeveloperState):
    """Router function to determine if tools should be called"""
    # Handle empty/None scratchpad defensively
    if not state.atomic_implementation_research:
        return "implement_plan"
        
    last_research_step = state.atomic_implementation_research[-1]
    
    # Continue if we either requested a tool OR just received a tool result
    if getattr(last_research_step, "tool_calls", None) or getattr(last_research_step, "type", None) == "tool":
        return "should_continue_research"
    
    return "implement_plan"


def prepare_for_implementation(state: SoftwareDeveloperState):
    """Read the code file content (if not new) and reset the research"""
    current_task = state.implementation_plan.tasks[state.current_task_idx]
    
    # Add validation for file_path
    import os
    file_path = current_task.file_path
    
    # Check if the path is valid and not just a directory
    if not file_path or file_path.endswith('/') or file_path.endswith('\\'):
        # If no file specified, create a default main.py
        file_path = os.path.join(file_path or "./workspace_repo", "main.py")
        current_task.file_path = file_path
        print(f"Warning: Invalid file_path, defaulting to: {file_path}")
    
    # Check if it's a directory without a filename
    if os.path.exists(file_path) and os.path.isdir(file_path):
        # If it's a directory, append main.py
        file_path = os.path.join(file_path, "main.py")
        current_task.file_path = file_path
        print(f"Warning: file_path was a directory, changed to: {file_path}")
    
    try:
        # Only try to read if it's an existing file
        if os.path.exists(file_path) and os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                file_content = file.read()
        else:
            # New file or doesn't exist yet
            file_content = "This is a new file"
    except FileNotFoundError:
        file_content = "This is a new file"
    except PermissionError as e:
        print(f"PermissionError reading {file_path}: {e}")
        file_content = "This is a new file"

    return {"current_file_content": file_content,
            "codebase_structure": get_files_structure.invoke({"directory": "./workspace_repo"}),
            "atomic_implementation_research": None}


def is_implementation_complete(state: SoftwareDeveloperState):
    """
    Check if we've completed all implementation tasks.
    """
    current_task_idx = state.current_task_idx
    plan = state.implementation_plan
    return END if current_task_idx >= len(plan.tasks) else "continue"

def convert_tools_messages_to_ai_and_human(implementation_research_scratchpad: List[AnyMessage]):
    messages = []
    if not implementation_research_scratchpad:
        return messages
        
    for message in implementation_research_scratchpad:
        if hasattr(message, 'type'):
            if message.type == "ai":
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    tool_name = message.tool_calls[0]["name"]
                    tool_args = json.dumps(message.tool_calls[0]["args"])
                    messages.append(AIMessage(content=f"I want to call the tool {tool_name} with the following arguments: {tool_args}"))
                else:
                    messages.append(message)
            elif message.type == "tool":
                messages.append(HumanMessage(content=f"Tool {message.name} returned: {message.content}"))
            else:
                messages.append(message)
        else:
            # Handle string messages
            messages.append(AIMessage(content=str(message)))
    return messages

# ENHANCEMENT: Helper function to detect if file will be large
def should_split_file_generation(task: str, file_path: str) -> bool:
    """Simple check to see if we should split file generation"""
    large_indicators = [
        "large", "complex", "full", "complete", "comprehensive",
        "entire", "whole", "all features", "production-ready",
        "multiple components", "full application"
    ]
    return any(indicator in task.lower() for indicator in large_indicators)

# ENHANCEMENT: Clean generated content helper
def clean_file_content(content: str) -> str:
    """Clean the generated content from any wrapping or artifacts"""
    if not content:
        return ""
    
    # Remove tool call wrapping if present
    if content.startswith("I want to call the tool"):
        try:
            json_start = content.find('{"')
            if json_start != -1:
                json_str = content[json_start:]
                json_str = json_str.rstrip('"')
                if not json_str.endswith('}'):
                    json_str += '}'
                args = json.loads(json_str)
                content = args.get("file_content", content)
        except:
            match = re.search(r'"file_content":\s*"([^"]*)"', content)
            if match:
                content = match.group(1)
                # FIXED: Assign backslash sequences to variables first
                newline = '\n'
                quote = '"'
                backslash = '\\'
                content = content.replace('\\n', newline).replace('\\"', quote).replace('\\\\', backslash)
    
    # Remove markdown code blocks if present
    if "```" in content:
        content = re.sub(r'^```[a-zA-Z]*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'\n```$', '', content, flags=re.MULTILINE)
    
    # Remove explanation patterns
    explanation_patterns = [
        r"^Here's the complete.*?:\n+",
        r"^I'll generate.*?:\n+",
        r"^Creating.*?:\n+",
        r"^The following is.*?:\n+",
    ]
    
    for pattern in explanation_patterns:
        content = re.sub(pattern, "", content, flags=re.MULTILINE | re.IGNORECASE)
    
    return content.strip()

def creating_diffs_for_task(state: SoftwareDeveloperState):
    import re  # Ensure re module is available
    # Get current task information
    current_task = state.implementation_plan.tasks[state.current_task_idx]
    current_atomic_task = current_task.atomic_tasks[state.current_atomic_task_idx]
    file_path = current_task.file_path

    # check if file is new
    if not os.path.exists(file_path):
        # Ensure the directory exists before creating the file
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # ENHANCEMENT: Check if we should split the generation
        if should_split_file_generation(current_atomic_task.atomic_task, file_path):
            print(f" Generating large file {file_path} in sections...")
            
            # Define sections based on file type
            sections = []
            if file_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                sections = [
                    "imports and type definitions",
                    "state management and configuration", 
                    "helper functions and utilities",
                    "main component or class implementation",
                    "sub-components and exports"
                ]
            elif file_path.endswith('.py'):
                sections = [
                    "imports and configuration",
                    "class definitions and models",
                    "core functions",
                    "helper functions",
                    "main execution block if applicable"
                ]
            else:
                sections = ["first half", "second half"]
            
            # Generate each section and accumulate
            complete_content = ""
            for i, section in enumerate(sections):
                # FIXED: Use format() instead of f-string with backslash
                prev_content_text = "Previous content generated:\n" + complete_content[-1000:] if complete_content else "This is the first section."
                section_prompt = """
                Generate ONLY the {} for {}.
                This is part {} of {}.
                
                Original task: {}
                
                {}
                
                Continue from where the previous section ended. Do NOT repeat content.
                """.format(section, file_path, i+1, len(sections), current_atomic_task.atomic_task, prev_content_text)
                
                section_content = create_new_file_runnable.invoke({
                    "task": section_prompt,
                    "additional_context": current_atomic_task.additional_context,
                    "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research or []),
                    "file_path": file_path
                })
                
                section_content = clean_file_content(section_content)
                
                if complete_content and not complete_content.endswith('\n'):
                    complete_content += '\n\n'
                complete_content += section_content
                
                print(f" Section {i+1}/{len(sections)} generated ({len(section_content)} chars)")
            
            new_file_content = complete_content
            
        else:
            # Generate file in one go for smaller files
            new_file_content = create_new_file_runnable.invoke({
                "task": current_atomic_task.atomic_task,
                "additional_context": current_atomic_task.additional_context,
                "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research or []),
                "file_path": file_path
            })
            
            new_file_content = clean_file_content(new_file_content)
        
        # Write the file
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(new_file_content)
            file.flush()
            
        print(f"Created new file: {file_path} ({len(new_file_content)} chars)")
            
    else:
        # Get the diffs - ORIGINAL CODE PRESERVED
        with open(file_path, "r", encoding="utf-8") as file:
            file_content = file.read()
        # add line numbers
        lines = []
        for i, line in enumerate(file_content.splitlines(), start=1):
            lines.append(f"{i}| {line}")
        file_content = "\n".join(lines)

        diffs_tasks = extract_diff_runnable.invoke({
            "task": current_atomic_task.atomic_task,
            "additional_context": current_atomic_task.additional_context,
            "research": convert_tools_messages_to_ai_and_human(state.atomic_implementation_research or []),
            "file_path": file_path,
            "file_content": file_content,
            "output_format": JsonOutputParser(pydantic_object=Diffs).get_format_instructions()
        })
        # Find all content between <code_change_request> and </code_change_request>
        blocks = re.findall(
            r"<code_change_request>(.*?)</code_change_request>", diffs_tasks, re.DOTALL
        )

        for block in blocks:
            # Use regex to extract the original code snippet and the task description.
            # The re.DOTALL flag allows the dot (.) to match newline characters.
            match = re.search(
                r"original_code_snippet:\s*(.*?)\s*edit_code_snippet:\s*(.*)",
                block,
                re.DOTALL,
            )
            if match:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                original_code = match.group(1).strip()
                edited_code = match.group(2).strip()
                orig_lines = original_code.splitlines()
                
                # Check if we have valid lines to work with
                if not orig_lines:
                    print(f"Warning: Empty original code snippet for file {file_path}")
                    continue
                    
                # Extract line numbers safely
                try:
                    first_line = int(orig_lines[0].split("|")[0].strip())
                    last_line = int(orig_lines[-1].split("|")[0].strip())
                except (IndexError, ValueError) as e:
                    print(f"Warning: Could not parse line numbers from diff: {str(e)}")
                    continue
                    
                new_content = file_content.splitlines()
                new_content = (
                    new_content[: first_line - 1]
                    + edited_code.splitlines()
                    + new_content[last_line:]
                )
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(new_content))
                    f.flush()

# Create tool node with expanded tool set
research_tool_node = ToolNode(
    search_tools + codemap_tools + agents_md_tools + sandbox_tools + multi_language_sandbox_tools + multi_language_build_tools,
    messages_key="atomic_implementation_research"
)

# Create the workflow graph
workflow = StateGraph(SoftwareDeveloperState)

# Add nodes
workflow.add_node("start_implementing", start_implementing)
workflow.add_node("prepare_for_implementation", prepare_for_implementation)
workflow.add_node("proceed_to_next_atomic_task", proceed_to_next_atomic_task)
workflow.add_node("get_clear_implementation_plan_for_atomic_task", get_clear_implementation_plan_for_atomic_task)
workflow.add_node("research_tool_node", research_tool_node )
workflow.add_node("creating_diffs_for_task", creating_diffs_for_task)

# Add edges
# Reset the system and load the file from the context of atomic task (if not new file)
workflow.add_edge(START, "start_implementing")
# Read file content and reset previous implementation research
workflow.add_edge("start_implementing", "prepare_for_implementation")
# Go to research about how to implement the atomic task
workflow.add_edge("prepare_for_implementation", "get_clear_implementation_plan_for_atomic_task")
# Check if research is done or we should continue research
workflow.add_conditional_edges(
    "get_clear_implementation_plan_for_atomic_task",
    should_continue_implementation_research,
    {
        "should_continue_research": "research_tool_node",
        "implement_plan": "creating_diffs_for_task"
    }
)
# Go back from executing a research tool to research about implementation
workflow.add_edge("research_tool_node", "get_clear_implementation_plan_for_atomic_task")
# After the research lets apply the diffs
workflow.add_edge("creating_diffs_for_task", "proceed_to_next_atomic_task")
# If next atomic task exists rest and go back to research if not end as everything was implemented
workflow.add_conditional_edges(
    "proceed_to_next_atomic_task",
    is_implementation_complete,
    {
        "continue": "prepare_for_implementation",
        END: END
    }
)

# Compile the workflow
swe_developer = workflow.compile().with_config({"tags": ["developer-agent-v3"]})