#!/usr/bin/env python3
"""
Enhanced SWE Agent CLI - Linear execution with parallel capabilities and terminal control
Addresses the terminal setup and project control issues
"""

import argparse
import sys
import os
from pathlib import Path

# Add the agent directory to Python path
current_dir = Path(__file__).parent
agent_dir = current_dir / "agent"
sys.path.insert(0, str(agent_dir))
sys.path.insert(0, str(current_dir))

from agent.integrated_graph import run_integrated_swe_agent, ExecutionMode

def main():
    parser = argparse.ArgumentParser(
        description="Enhanced SWE Agent - Linear execution with terminal control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python enhanced_cli.py "Create a web scraper for quotes"
  python enhanced_cli.py "Build a REST API" --parallel
  python enhanced_cli.py "Create a data analysis tool" --workspace /path/to/project
        """
    )
    
    parser.add_argument(
        "task",
        help="Description of the software engineering task to implement"
    )
    
    parser.add_argument(
        "--workspace",
        "-w",
        default="./workspace_repo",
        help="Workspace directory for the project (default: ./workspace_repo)"
    )
    
    parser.add_argument(
        "--parallel",
        "-p",
        action="store_true",
        help="Enable parallel execution mode (default: sequential)"
    )
    
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug mode with detailed logging"
    )
    
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only run environment setup and dependency installation"
    )
    
    args = parser.parse_args()
    
    # Print header
    print("🤖 Enhanced SWE Agent - Terminal Control Edition")
    print("=" * 60)
    print(f"📋 Task: {args.task}")
    print(f"📁 Workspace: {os.path.abspath(args.workspace)}")
    print(f"⚡ Mode: {'Parallel' if args.parallel else 'Sequential'}")
    print(f"🔧 Debug: {'Enabled' if args.debug else 'Disabled'}")
    print("=" * 60)
    
    # Determine execution mode
    execution_mode = ExecutionMode.PARALLEL if args.parallel else ExecutionMode.SEQUENTIAL
    
    # Ensure workspace directory exists
    workspace_path = Path(args.workspace).resolve()
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Run the integrated SWE agent
        result = run_integrated_swe_agent(
            task_description=args.task,
            workspace_dir=str(workspace_path),
            execution_mode=execution_mode
        )
        
        # Print results
        final_status = result.get('final_status', 'unknown')
        
        if final_status == 'completed':
            print("\n🎉 SUCCESS! Task completed successfully")
            
            if 'execution_summary' in result:
                summary = result['execution_summary']
                print("\n📊 Execution Summary:")
                print(f"   ✅ Phases completed: {summary.get('phases_executed', 0)}")
                print(f"   📋 Implementation tasks: {summary.get('implementation_plan_tasks', 0)}")
                print(f"   🖥️ Terminal sessions used: {summary.get('terminal_sessions', 0)}")
                
                if summary.get('project_structure'):
                    print(f"\n📁 Project structure:")
                    for line in summary['project_structure'].split('\n')[:10]:
                        if line.strip():
                            print(f"   {line.strip()}")
            
            print(f"\n📂 Check your results in: {workspace_path}")
            return 0
            
        elif final_status == 'error':
            print(f"\n❌ FAILED! Error occurred: {result.get('error', 'Unknown error')}")
            return 1
            
        else:
            print(f"\n⚠️ PARTIAL! Task status: {final_status}")
            return 2
            
    except KeyboardInterrupt:
        print("\n\n⏸️ Execution interrupted by user")
        return 130
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
