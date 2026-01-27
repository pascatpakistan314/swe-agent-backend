#!/usr/bin/env python
"""
Enhanced SWE-Agent CLI with Devin-like features
"""
import click
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
import asyncio
from typing import Optional

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

# Import orchestrated agent with fallback to basic
try:
    # Prefer orchestrated agent with enhanced architect
    from agent.orchestrated_agent import orchestrated_swe_agent_compatible as swe_agent
    agent_mode = "orchestrated"
except Exception:
    # Fallback to basic
    from agent.graph import swe_agent
    agent_mode = "basic"

from agent.tools.agents_md import AgentsMDReader
from agent.tools.sandbox import CodeSandbox
from agent.tools.terminal import TerminalSession

console = Console()

@click.group()
@click.version_option(version="2.0.0", prog_name="SWE-Agent")
def cli():
    """SWE-Agent - AI-powered Software Engineering Agent with Devin-like capabilities"""
    pass

@cli.command()
@click.argument('task', required=True)
@click.option('--mode', type=click.Choice(['full', 'dev', 'test', 'review', 'sandbox']), 
              default='full', help='Workflow mode')
@click.option('--workspace', default='./workspace_repo', help='Workspace directory')
@click.option('--sandbox/--no-sandbox', default=True, help='Use sandboxed execution')
@click.option('--agents-md', is_flag=True, help='Show AGENTS.md context')
@click.option('--verbose', is_flag=True, help='Verbose output')
def execute(task, mode, workspace, sandbox, agents_md, verbose):
    """Execute a development task with AI agent"""
    
    console.print(Panel.fit(
        f"[bold blue]SWE-Agent v2.0[/bold blue]\n"
        f"[yellow]Task:[/yellow] {task}\n"
        f"[yellow]Mode:[/yellow] {mode} ({agent_mode} agent)\n"
        f"[yellow]Sandbox:[/yellow] {'Enabled' if sandbox else 'Disabled'}",
        title=" Starting Agent"
    ))
    
    # Check for AGENTS.md context
    if agents_md:
        try:
            reader = AgentsMDReader(workspace)
            context = reader.get_context(task)
            
            if context["found"]:
                console.print("\n[bold green] AGENTS.md Context Found:[/bold green]")
                for section, content in context["relevant_sections"].items():
                    console.print(f"\n[yellow]{section}:[/yellow]")
                    console.print(content[:200] + "..." if len(content) > 200 else content)
        except Exception as e:
            console.print(f"[yellow] Could not read AGENTS.md: {e}[/yellow]")
    
    # Initialize sandbox if enabled
    sandbox_session = None
    if sandbox:
        console.print("\n[bold cyan] Initializing Sandbox Environment...[/bold cyan]")
        try:
            sandbox_session = CodeSandbox(workspace)
            if sandbox_session.setup_container():
                console.print("[green]✓[/green] Sandbox ready (Docker)")
            else:
                console.print("[yellow]⚠[/yellow]  Using subprocess fallback (less secure)")
        except Exception as e:
            console.print(f"[yellow] Sandbox setup failed: {e}[/yellow]")
    
    # Execute with progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        # Add task phases
        planning = progress.add_task("[cyan]Planning...", total=None)
        
        try:
            # Prepare input based on agent type
            if agent_mode == "orchestrated":
                # Use the orchestrated agent's expected input format
                result = swe_agent(task)
            else:
                # Use basic agent format
                result = swe_agent.invoke({
                    "task_description": task,
                    "implementation_research_scratchpad": []
                })
            
            progress.update(planning, completed=100)
            
            # Show results
            console.print("\n[bold green] Task Completed![/bold green]\n")
            
            # Handle different result formats
            if isinstance(result, dict):
                implementation_plan = result.get("implementation_plan")
                if implementation_plan:
                    table = Table(title="Implementation Plan")
                    table.add_column("File", style="cyan")
                    table.add_column("Tasks", style="yellow")
                    
                    # Handle different plan formats
                    tasks = []
                    if hasattr(implementation_plan, 'tasks'):
                        tasks = implementation_plan.tasks
                    elif isinstance(implementation_plan, dict) and 'tasks' in implementation_plan:
                        tasks = implementation_plan['tasks']
                    elif isinstance(implementation_plan, list):
                        tasks = implementation_plan
                    
                    for task_item in tasks[:5]:  # Show first 5 tasks
                        if hasattr(task_item, 'file_path'):
                            file_path = task_item.file_path
                            description = getattr(task_item, 'logical_task', 'Task')
                        elif isinstance(task_item, dict):
                            file_path = task_item.get('file_path', 'Unknown')
                            description = task_item.get('logical_task', task_item.get('description', 'Task'))
                        else:
                            file_path = str(task_item)
                            description = "Task"
                        
                        table.add_row(
                            file_path,
                            description[:50] + "..." if len(str(description)) > 50 else str(description)
                        )
                    
                    console.print(table)
                
                # Show trace URL if available
                if result.get("trace_url"):
                    console.print(f"\n[bold cyan]🔗 Trace URL:[/bold cyan] {result['trace_url']}")
                
                if verbose and result.get("implementation_research_scratchpad"):
                    console.print("\n[bold]Research Log:[/bold]")
                    scratchpad = result["implementation_research_scratchpad"]
                    messages_to_show = scratchpad[-3:] if isinstance(scratchpad, list) else []
                    for msg in messages_to_show:
                        content = getattr(msg, 'content', str(msg))
                        console.print(f"  • {str(content)[:100]}...")
            else:
                # Handle non-dict results
                console.print(f"Result: {str(result)[:200]}...")
            
        except Exception as e:
            progress.update(planning, completed=100)
            console.print(f"\n[bold red] Error: {e}[/bold red]")
            if verbose:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")
        
        finally:
            if sandbox_session:
                try:
                    sandbox_session.cleanup()
                    console.print("[dim]Sandbox cleaned up[/dim]")
                except Exception:
                    pass

@cli.command()
@click.option('--session', default='main', help='Terminal session ID')
def terminal(session):
    """Open an interactive terminal session (Devin-like)"""
    
    console.print(Panel.fit(
        "[bold cyan]Interactive Terminal Mode[/bold cyan]\n"
        "Type commands to execute. Use 'exit' to quit.",
        title=" Terminal"
    ))
    
    try:
        terminal_session = TerminalSession()
        terminal_session.create_session(session)
        
        try:
            while True:
                # Get command from user
                command = console.input(f"\n[bold green]{session}>[/bold green] ")
                
                if command.lower() in ['exit', 'quit']:
                    break
                
                # Execute command
                result = terminal_session.execute_command(command, session)
                
                # Display output
                if result.get("output"):
                    console.print(result["output"])
                
                if result.get("error"):
                    console.print(f"[red]Error: {result['error']}[/red]")
                    
        except KeyboardInterrupt:
            console.print("\n[yellow]Terminal session interrupted[/yellow]")
        
        finally:
            terminal_session.close_session(session)
            console.print("[dim]Session closed[/dim]")
            
    except Exception as e:
        console.print(f"[red]Terminal not available: {e}[/red]")
        console.print("You can still use regular system terminal")

@cli.command()
@click.argument('code_file', type=click.Path(exists=True))
@click.option('--language', default='python', help='Programming language')
def sandbox(code_file, language):
    """Execute code in a sandboxed environment"""
    
    console.print(Panel.fit(
        f"[bold yellow]Sandbox Execution[/bold yellow]\n"
        f"File: {code_file}\n"
        f"Language: {language}",
        title=" Sandbox"
    ))
    
    try:
        # Read code
        with open(code_file, 'r') as f:
            code = f.read()
        
        # Show code preview
        syntax = Syntax(code[:500], language, theme="monokai", line_numbers=True)
        console.print("\n[bold]Code Preview:[/bold]")
        console.print(syntax)
        
        # Execute in sandbox
        sandbox_session = CodeSandbox()
        
        with console.status("[bold cyan]Executing code in sandbox..."):
            if hasattr(sandbox_session, 'docker_available') and sandbox_session.docker_available:
                sandbox_session.setup_container()
            
            result = sandbox_session.execute_code(code, language)
        
        # Show results
        if result.get("success"):
            console.print("\n[bold green] Execution Successful[/bold green]")
            if result.get("output"):
                console.print("\n[bold]Output:[/bold]")
                console.print(Panel(result["output"], style="green"))
        else:
            console.print("\n[bold red] Execution Failed[/bold red]")
            if result.get("error"):
                console.print("\n[bold]Error:[/bold]")
                console.print(Panel(result["error"], style="red"))
        
        sandbox_session.cleanup()
        
    except Exception as e:
        console.print(f"[red]Sandbox execution failed: {e}[/red]")

@cli.command()
@click.option('--workspace', default='./workspace_repo', help='Workspace directory')
def init(workspace):
    """Initialize a new project with AGENTS.md template"""
    
    console.print(Panel.fit(
        "[bold blue]Project Initialization[/bold blue]\n"
        f"Creating AGENTS.md in {workspace}",
        title=" Init"
    ))
    
    # Create workspace if doesn't exist
    workspace_path = Path(workspace)
    workspace_path.mkdir(exist_ok=True)
    
    # Check if AGENTS.md exists
    agents_md_path = workspace_path / "AGENTS.md"
    
    if agents_md_path.exists():
        if not click.confirm("AGENTS.md already exists. Overwrite?"):
            console.print("[yellow]Initialization cancelled[/yellow]")
            return
    
    # Create AGENTS.md template
    template = """# AGENTS.md

## Project Overview
<!-- Brief description of your project -->

## Dev Environment Setup
<!-- Instructions for setting up the development environment -->
- Python version: 3.11+
- Install dependencies: `pip install -r requirements.txt`
- Environment variables: Copy `.env.example` to `.env`

## Testing Instructions
<!-- How to run tests -->
- Run all tests: `pytest`
- Run specific test: `pytest tests/test_file.py`
- Check coverage: `pytest --cov`

## Code Style Guidelines
<!-- Coding standards and conventions -->
- Follow PEP 8 for Python code
- Use type hints for function signatures
- Write docstrings for all public methods

## Build & Deploy
<!-- Build and deployment instructions -->
- Build: `python setup.py build`
- Deploy: `python deploy.py`

## PR Instructions
<!-- Pull request guidelines -->
- Create feature branch: `git checkout -b feature/name`
- Run tests before committing
- Update documentation

## Security Considerations
<!-- Security guidelines and considerations -->
- Never commit secrets or API keys
- Use environment variables for sensitive data
- Follow OWASP guidelines

## Additional Notes
<!-- Any other important information for AI agents -->
"""
    
    # Write template
    agents_md_path.write_text(template)
    console.print(f"\n[bold green] Created AGENTS.md at {agents_md_path}[/bold green]")
    
    # Create basic project structure
    dirs_to_create = ['src', 'tests', 'docs', '.github/workflows']
    
    for dir_name in dirs_to_create:
        dir_path = workspace_path / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created {dir_path}")
    
    console.print("\n[bold green]Project initialized successfully![/bold green]")
    console.print("\nNext steps:")
    console.print("  1. Edit AGENTS.md with your project details")
    console.print("  2. Run 'swe-agent execute \"your task\"' to start developing")

@cli.command()
@click.option('--detailed', is_flag=True, help='Show detailed status')
def status(detailed):
    """Check agent and environment status"""
    
    console.print(Panel.fit(
        "[bold cyan]System Status Check[/bold cyan]",
        title=" Status"
    ))
    
    status_table = Table(title="Environment Status")
    status_table.add_column("Component", style="cyan")
    status_table.add_column("Status", style="green")
    status_table.add_column("Details")
    
    # Check agent mode
    status_table.add_row("Agent Mode", " Active", f"{agent_mode.title()} agent loaded")
    
    # Check Docker
    try:
        import docker
        client = docker.from_env()
        docker_version = client.version()['Version']
        status_table.add_row("Docker", " Available", f"v{docker_version}")
    except:
        status_table.add_row("Docker", " Not Available", "Install Docker for sandboxing")
    
    # Check API keys
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        status_table.add_row("Anthropic API", " Configured", f"...{anthropic_key[-4:]}")
    else:
        status_table.add_row("Anthropic API", " Missing", "Set ANTHROPIC_API_KEY")
    
    # Check workspace
    workspace = Path("./workspace_repo")
    if workspace.exists():
        status_table.add_row("Workspace", " Exists", str(workspace.resolve()))
    else:
        status_table.add_row("Workspace", " Missing", "Run 'swe-agent init'")
    
    # Check AGENTS.md
    agents_md = workspace / "AGENTS.md" if workspace.exists() else None
    if agents_md and agents_md.exists():
        status_table.add_row("AGENTS.md", " Found", f"{agents_md.stat().st_size} bytes")
    else:
        status_table.add_row("AGENTS.md", " Not Found", "Create for better guidance")
    
    console.print(status_table)
    
    if detailed:
        # Show more details
        console.print("\n[bold]Additional Information:[/bold]")
        console.print(f"  Python Version: {sys.version.split()[0]}")
        console.print(f"  Platform: {sys.platform}")
        console.print(f"  Current Directory: {Path.cwd()}")
        
        # Show agent capabilities
        console.print(f"\n[bold]Agent Capabilities ({agent_mode}):[/bold]")
        if agent_mode == "orchestrated":
            console.print("   Enhanced Architecture Planning")
            console.print("   Multi-Agent Orchestration") 
            console.print("   GitHub Integration")
            console.print("   Advanced Error Handling")
        else:
            console.print("   Basic Architecture Planning")
            console.print("   Code Development")
            console.print("    Limited orchestration")

if __name__ == '__main__':
    cli()