"""Reviewer State - Following Original Pattern with Code Issue Models"""

from typing import Annotated, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages

class CodeIssue(BaseModel):
    """Represents a code issue found during review"""
    severity: str  # e.g., LOW|MEDIUM|HIGH
    category: str  # e.g., security|quality|style
    file_path: str
    line_number: int | None = None
    description: str
    suggestion: str | None = None

class CodeReviewerState(BaseModel):
    """State for reviewer - following original simple pattern"""
    files_to_review: List[str] = Field(default_factory=list, description="List of files to review")
    review_summary: Optional[str] = Field(None, description="Review summary created by Claude")
    review_scratchpad: Annotated[list[AnyMessage], add_messages] = Field(default_factory=list, description="Review research messages")
    issues_found: List[CodeIssue] = Field(default_factory=list)
    approved: Optional[bool] = None