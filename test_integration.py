#!/usr/bin/env python
"""
Test script to verify all agent components are working
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv()

def test_imports():
    """Test all critical imports"""
    print("Testing imports...")
    
    results = []
    
    # Test basic agent
    try:
        from agent.graph import swe_agent
        results.append(("✅", "Basic agent (graph.py)"))
    except Exception as e:
        results.append(("❌", f"Basic agent: {e}"))
    
    # Test enhanced architect
    try:
        from agent.architect.graph_enhanced import swe_architect
        results.append(("✅", "Enhanced architect"))
    except Exception as e:
        results.append(("❌", f"Enhanced architect: {e}"))
    
    # Test orchestrated agent
    try:
        from agent.orchestrated_agent import orchestrated_swe_agent
        results.append(("✅", "Orchestrated agent"))
    except Exception as e:
        results.append(("❌", f"Orchestrated agent: {e}"))
    
    # Test multi-agent orchestrator
    try:
        from agent.orchestrator.multi_agent_orchestrator import MultiAgentOrchestrator
        results.append(("✅", "Multi-agent orchestrator"))
    except Exception as e:
        results.append(("❌", f"Multi-agent orchestrator: {e}"))
    
    # Test GitHub integration
    try:
        from agent.integrations.github_integration import GitHubPRHandler
        if os.getenv("GITHUB_TOKEN"):
            handler = GitHubPRHandler()
            results.append(("✅", "GitHub integration (with token)"))
        else:
            results.append(("⚠️", "GitHub integration (no token set)"))
    except ImportError:
        results.append(("⚠️", "GitHub integration (PyGithub not installed)"))
    except Exception as e:
        results.append(("❌", f"GitHub integration: {e}"))
    
    # Test multi-language tools
    try:
        from agent.tools.multi_language_sandbox import MultiLanguageSandbox
        results.append(("✅", "Multi-language sandbox"))
    except Exception as e:
        results.append(("❌", f"Multi-language sandbox: {e}"))
    
    # Test AGENTS.md tools
    try:
        from agent.tools.agents_md import AgentsMDReader
        results.append(("✅", "AGENTS.md reader"))
    except Exception as e:
        results.append(("❌", f"AGENTS.md reader: {e}"))
    
    # Test terminal tools
    try:
        from agent.tools.terminal import TerminalSession
        results.append(("✅", "Terminal tools"))
    except Exception as e:
        results.append(("❌", f"Terminal tools: {e}"))
    
    # Print results
    print("\n" + "="*50)
    print("IMPORT TEST RESULTS")
    print("="*50)
    for status, component in results:
        print(f"{status} {component}")
    print("="*50)
    
    # Check if all critical components work
    critical_ok = all(status != "❌" for status, _ in results[:4])
    return critical_ok

def test_basic_execution():
    """Test basic agent execution"""
    print("\nTesting basic execution...")
    
    try:
        from agent.orchestrated_agent import execute_task
        
        # Simple test task
        result = execute_task("Create a function that adds two numbers")
        
        if result and result.get("success"):
            print("✅ Basic execution test passed")
            print(f"   Workflow mode: {result.get('workflow_mode')}")
            print(f"   Agents used: {result.get('agents_used', [])}")
            return True
        else:
            print("❌ Basic execution test failed")
            print(f"   Result: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Execution test failed: {e}")
        return False

def test_api_compatibility():
    """Test API compatibility"""
    print("\nTesting API compatibility...")
    
    try:
        # Test that the orchestrated agent can be imported by simple_api
        from agent.orchestrated_agent import orchestrated_swe_agent_compatible as swe_agent
        
        # Test the interface
        test_input = {
            "task_description": "Test task",
            "implementation_research_scratchpad": []
        }
        
        # This should not crash
        result = swe_agent.invoke(test_input)
        
        print("✅ API compatibility test passed")
        return True
        
    except Exception as e:
        print(f"❌ API compatibility test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 SWE-Agent Integration Test Suite")
    print("="*50)
    
    # Check environment
    print("Environment Check:")
    print(f"  ANTHROPIC_API_KEY: {'✅ Set' if os.getenv('ANTHROPIC_API_KEY') else '❌ Not set'}")
    print(f"  GITHUB_TOKEN: {'✅ Set' if os.getenv('GITHUB_TOKEN') else '⚠️ Not set (optional)'}")
    print(f"  Working directory: {os.getcwd()}")
    
    # Run tests
    import_ok = test_imports()
    api_ok = test_api_compatibility()
    
    # Only test execution if API key is set
    execution_ok = False
    if os.getenv("ANTHROPIC_API_KEY"):
        execution_ok = test_basic_execution()
    else:
        print("\n⚠️ Skipping execution test (no API key)")
    
    # Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    if import_ok and api_ok:
        if os.getenv("ANTHROPIC_API_KEY"):
            if execution_ok:
                print("✅ All tests passed! Your SWE-Agent is ready to use.")
            else:
                print("⚠️ Imports work but execution failed. Check your API key and models.")
        else:
            print("✅ System is properly configured but needs ANTHROPIC_API_KEY to run.")
        
        print("\nTo start the API server:")
        print("  python simple_api.py")
        print("\nTo test with curl:")
        print('  curl -X POST "http://localhost:8000/agent/execute" \\')
        print('    -H "Content-Type: application/json" \\')
        print('    -H "Authorization: Bearer YOUR_TOKEN" \\')
        print('    -d \'{"task_description": "Your task here"}\'')
    else:
        print("❌ Some components are not working. Please fix the issues above.")

if __name__ == "__main__":
    main()
