#!/usr/bin/env python
"""
Quick test to verify the PermissionError fix is working
"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, r'C:\Users\LENOVO\OneDrive\Documents\swe-agent212\swe-agent212\swe-agent21\swe-agent')

from agent.common.entities import ImplementationPlan, ImplementationTask, AtomicTask
from agent.developer.graph import prepare_for_implementation
from agent.developer.state import SoftwareDeveloperState

print("Testing PermissionError fix...")

# Create a state with a directory path (this used to cause PermissionError)
state = SoftwareDeveloperState(
    task_description="Test task",
    workspace_dir="./workspace_repo",
    implementation_plan=ImplementationPlan(
        tasks=[
            ImplementationTask(
                file_path="./workspace_repo",  # Directory path - used to fail!
                logical_task="Test task",
                atomic_tasks=[
                    AtomicTask(
                        atomic_task="Test atomic task",
                        additional_context="Test context"
                    )
                ]
            )
        ]
    ),
    current_task_idx=0,
    current_atomic_task_idx=0,
    atomic_implementation_research=[]
)

try:
    # This should now work without PermissionError
    result = prepare_for_implementation(state)
    print("SUCCESS: No PermissionError! The fix is working.")
    print(f"File content type: {type(result['current_file_content'])}")
except PermissionError as e:
    print(f"FAILED: Still getting PermissionError: {e}")
except Exception as e:
    print(f"ERROR: Got different error: {type(e).__name__}: {e}")
