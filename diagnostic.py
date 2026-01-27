#!/usr/bin/env python3
"""
SWE Agent Diagnostic Script
This will identify the exact issue preventing your agent from running
"""

import os
import sys
import traceback
from pathlib import Path

# Add agent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_environment():
    """Test environment setup"""
    print("=" * 60)
    print("1. TESTING ENVIRONMENT")
    print("=" * 60)
    
    # Check Python version
    print(f"Python version: {sys.version}")
    
    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file found")
    else:
        print("❌ .env file not found")
    
    # Check API keys
    from dotenv import load_dotenv
    load_dotenv()
    
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        print(f"✅ Anthropic API key loaded (...{anthropic_key[-4:]})")
    else:
        print("❌ ANTHROPIC_API_KEY not found")
        return False
    
    # Check workspace
    workspace = Path("./workspace_repo")
    if workspace.exists():
        print(f"✅ Workspace exists: {workspace.absolute()}")
    else:
        print(f"⚠️ Creating workspace: {workspace.absolute()}")
        workspace.mkdir(exist_ok=True)
    
    return True

def test_imports():
    """Test if all components can be imported"""
    print("\n" + "=" * 60)
    print("2. TESTING IMPORTS")
    print("=" * 60)
    
    imports_ok = True
    
    # Test architect
    try:
        from agent.architect.graph_enhanced import swe_architect
        print("✅ Architect imported")
    except Exception as e:
        print(f"❌ Architect import failed: {e}")
        imports_ok = False
    
    # Test developer
    try:
        from agent.developer.graph import swe_developer
        print("✅ Developer imported")
    except Exception as e:
        print(f"❌ Developer import failed: {e}")
        imports_ok = False
    
    # Test orchestrated agent
    try:
        from agent.orchestrated_agent import orchestrated_swe_agent_compatible
        print("✅ Orchestrated agent imported")
    except Exception as e:
        print(f"❌ Orchestrated agent import failed: {e}")
        imports_ok = False
    
    # Test integrated graph
    try:
        from agent.integrated_graph import swe_agent
        print("✅ Integrated graph imported")
    except Exception as e:
        print(f"❌ Integrated graph import failed: {e}")
        imports_ok = False
    
    return imports_ok

def test_basic_execution():
    """Test basic agent execution"""
    print("\n" + "=" * 60)
    print("3. TESTING BASIC EXECUTION")
    print("=" * 60)
    
    try:
        # Test the simplest component first - developer
        from agent.developer.graph import swe_developer
        
        test_state = {
            "implementation_plan": {
                "tasks": [
                    {
                        "file_path": "test.py",
                        "atomic_tasks": [
                            {
                                "atomic_task": "Create a hello world function",
                                "additional_context": "Simple test"
                            }
                        ]
                    }
                ]
            },
            "current_task_idx": 0,
            "current_atomic_task_idx": 0,
            "atomic_implementation_research": [],
            "workspace_dir": "./workspace_repo"
        }
        
        print("Attempting to run developer with minimal state...")
        
        # Try to get the graph structure
        if hasattr(swe_developer, 'get_graph'):
            graph = swe_developer.get_graph()
            print(f"Graph nodes: {graph.nodes if hasattr(graph, 'nodes') else 'unknown'}")
        
        # Check if it's compiled
        if hasattr(swe_developer, '__class__'):
            print(f"Developer type: {type(swe_developer)}")
        
        # Try invoke
        if hasattr(swe_developer, 'invoke'):
            print("Developer has invoke method")
            # Don't actually run it yet, just check
        else:
            print("❌ Developer missing invoke method")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Basic execution test failed: {e}")
        traceback.print_exc()
        return False

def test_architect_execution():
    """Test architect component"""
    print("\n" + "=" * 60)
    print("4. TESTING ARCHITECT")
    print("=" * 60)
    
    try:
        from agent.architect.graph_enhanced import swe_architect
        
        test_state = {
            "task_description": "Create a simple hello world Python script",
            "messages": [],
            "implementation_research_scratchpad": []
        }
        
        print("Testing architect with simple task...")
        
        # Check structure
        print(f"Architect type: {type(swe_architect)}")
        
        if hasattr(swe_architect, 'invoke'):
            # Try to run it
            print("Attempting to invoke architect...")
            result = swe_architect.invoke(test_state)
            
            if result:
                print("✅ Architect executed successfully")
                if "implementation_plan" in result:
                    print("✅ Implementation plan generated")
                    return True
                else:
                    print("⚠️ No implementation plan in result")
                    print(f"Result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
            else:
                print("❌ Architect returned empty result")
        else:
            print("❌ Architect missing invoke method")
            
    except Exception as e:
        print(f"❌ Architect test failed: {e}")
        traceback.print_exc()
        
    return False

def test_orchestrated_agent():
    """Test the orchestrated agent wrapper"""
    print("\n" + "=" * 60)
    print("5. TESTING ORCHESTRATED AGENT")
    print("=" * 60)
    
    try:
        from agent.orchestrated_agent import orchestrated_swe_agent_compatible
        
        print(f"Orchestrated agent type: {type(orchestrated_swe_agent_compatible)}")
        
        if hasattr(orchestrated_swe_agent_compatible, 'invoke'):
            print("✅ Orchestrated agent has invoke method")
            
            # Test with minimal input
            test_input = {
                "task_description": "Create a test file"
            }
            
            print("Attempting to invoke orchestrated agent...")
            result = orchestrated_swe_agent_compatible.invoke(test_input)
            
            if result:
                print("✅ Orchestrated agent returned result")
                print(f"Result keys: {result.keys() if isinstance(result, dict) else type(result)}")
            else:
                print("⚠️ Orchestrated agent returned empty result")
                
        else:
            print("❌ Orchestrated agent missing invoke method")
            
    except Exception as e:
        print(f"❌ Orchestrated agent test failed: {e}")
        traceback.print_exc()
        return False
    
    return True

def test_file_writing():
    """Test if files can be written to workspace"""
    print("\n" + "=" * 60)
    print("6. TESTING FILE WRITING")
    print("=" * 60)
    
    workspace = Path("./workspace_repo")
    test_file = workspace / "diagnostic_test.txt"
    
    try:
        # Ensure workspace exists
        workspace.mkdir(exist_ok=True)
        
        # Try to write a file
        with open(test_file, 'w') as f:
            f.write("Test content from diagnostic")
        
        # Verify it was written
        if test_file.exists():
            print(f"✅ Successfully wrote test file: {test_file}")
            content = test_file.read_text()
            print(f"   Content: {content}")
            
            # Clean up
            test_file.unlink()
            print("   Cleaned up test file")
            return True
        else:
            print("❌ Test file was not created")
            return False
            
    except Exception as e:
        print(f"❌ File writing test failed: {e}")
        return False

def main():
    """Run all diagnostics"""
    print("\n" + "🔍 SWE AGENT DIAGNOSTIC TOOL 🔍")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Environment", test_environment()))
    results.append(("Imports", test_imports()))
    results.append(("Basic Execution", test_basic_execution()))
    results.append(("File Writing", test_file_writing()))
    
    # Only test components if basics work
    if results[1][1]:  # If imports succeeded
        results.append(("Architect", test_architect_execution()))
        results.append(("Orchestrated Agent", test_orchestrated_agent()))
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if not results[0][1]:  # Environment
        print("1. Fix your .env file and ensure ANTHROPIC_API_KEY is set")
    
    if not results[1][1]:  # Imports
        print("2. Fix import errors - likely missing dependencies or syntax errors")
    
    if results[1][1] and not results[2][1]:  # Basic execution
        print("3. The agent graphs are not properly compiled")
    
    if all(r[1] for r in results[:3]) and not results[4][1]:  # Architect
        print("4. The architect is failing - check prompts and model configuration")
    
    print("\nRun this diagnostic to identify the exact issue with your agent.")
    
if __name__ == "__main__":
    main()