import pytest
from ..scripts.tasks import parse_free_text_task


class TestFreeTextTaskParser:
    """Test the parse_free_text_task function for parsing free-text task input"""

    def test_empty_input(self):
        """Test parsing empty input."""
        result = parse_free_text_task("")
        assert result["title"] == "Untitled Task"
        assert result["status"] == "todo"
        assert result["progress"] == 0
        assert result["plan"] == []
        assert result["notes"] == []
        assert result["priority"] is None
        assert result["tags"] == []

    def test_title_only(self):
        """Test parsing input with only a title."""
        result = parse_free_text_task("My Task Title")
        assert result["title"] == "My Task Title"
        assert result["status"] == "todo"
        assert result["progress"] == 0
        assert result["plan"] == []
        assert result["notes"] == []
        assert result["priority"] is None
        assert result["tags"] == []

    def test_with_plan(self):
        """Test parsing input with title and plan."""
        result = parse_free_text_task("Build login page\nplan: Create form; Add validation; Style inputs")
        assert result["title"] == "Build login page"
        assert result["plan"] == ["Create form", "Add validation", "Style inputs"]
        assert result["status"] == "todo"

    def test_with_status(self):
        """Test parsing input with title and status."""
        result = parse_free_text_task("Refactor authentication\nstatus: in_progress")
        assert result["title"] == "Refactor authentication"
        assert result["status"] == "in_progress"
        
        # Test different status values
        result = parse_free_text_task("Task\nstatus: done")
        assert result["status"] == "done"
        
        result = parse_free_text_task("Task\nstatus: pending")
        assert result["status"] == "pending"
        
        # Test invalid status (should default to todo)
        result = parse_free_text_task("Task\nstatus: invalid_status")
        assert result["status"] == "todo"

    def test_with_priority(self):
        """Test parsing input with title and priority."""
        result = parse_free_text_task("Critical issue\npriority: high")
        assert result["title"] == "Critical issue"
        assert result["priority"] == "high"
        
        # Test different priority values
        result = parse_free_text_task("Task\npriority: medium")
        assert result["priority"] == "medium"
        
        result = parse_free_text_task("Task\npriority: low")
        assert result["priority"] == "low"
        
        # Test invalid priority (should be None)
        result = parse_free_text_task("Task\npriority: invalid_priority")
        assert result["priority"] is None

    def test_with_progress(self):
        """Test parsing input with title and progress."""
        result = parse_free_text_task("Task in progress\nprogress: 75")
        assert result["title"] == "Task in progress"
        assert result["progress"] == 75
        
        # Test with percentage sign
        result = parse_free_text_task("Task\nprogress: 30%")
        assert result["progress"] == 30
        
        # Test out of range values (should be clamped)
        result = parse_free_text_task("Task\nprogress: 120%")
        assert result["progress"] == 100
        
        result = parse_free_text_task("Task\nprogress: -10")
        assert result["progress"] == 0
        
        # Test invalid progress (should default to 0)
        result = parse_free_text_task("Task\nprogress: not_a_number")
        assert result["progress"] == 0

    def test_with_tags(self):
        """Test parsing input with title and tags."""
        result = parse_free_text_task("UI improvements\ntags: #frontend #ui")
        assert result["title"] == "UI improvements"
        assert "frontend" in result["tags"]
        assert "ui" in result["tags"]
        
        # Test comma-separated tags
        result = parse_free_text_task("Task\ntags: api, backend, database")
        assert "api" in result["tags"]
        assert "backend" in result["tags"]
        assert "database" in result["tags"]
        
        # Test mixed format
        result = parse_free_text_task("Task\ntags: #api backend, #database")
        assert "api" in result["tags"]
        assert "backend" in result["tags"]
        assert "database" in result["tags"]

    def test_with_notes(self):
        """Test parsing input with title and notes."""
        result = parse_free_text_task("Important task\nnotes: This is a note\nAnother line of the note")
        assert result["title"] == "Important task"
        assert len(result["notes"]) > 0
        assert "This is a note" in result["notes"]
        
        # Test multi-line notes
        result = parse_free_text_task("Task\nnotes: First line\nSecond line\nThird line")
        assert len(result["notes"]) == 3
        assert "First line" in result["notes"]
        assert "Second line" in result["notes"]
        assert "Third line" in result["notes"]

    def test_all_fields(self):
        """Test parsing input with all fields."""
        input_text = """Implement login form validation
plan: Create validation rules; Write functions; Add error messages
status: in_progress
progress: 35%
priority: high
tags: #frontend #auth
notes: Use client-side validation first
Then add server-side validation"""
        
        result = parse_free_text_task(input_text)
        assert result["title"] == "Implement login form validation"
        assert result["plan"] == ["Create validation rules", "Write functions", "Add error messages"]
        assert result["status"] == "in_progress"
        assert result["progress"] == 35
        assert result["priority"] == "high"
        assert "frontend" in result["tags"]
        assert "auth" in result["tags"]
        assert "Use client-side validation first" in result["notes"]
        assert "Then add server-side validation" in result["notes"]

    def test_mixed_order_fields(self):
        """Test parsing input with fields in mixed order."""
        input_text = """Refactor authentication module
priority: medium
plan: Identify dependencies; Extract common functions
status: todo
tags: #backend #refactoring"""
        
        result = parse_free_text_task(input_text)
        assert result["title"] == "Refactor authentication module"
        assert result["plan"] == ["Identify dependencies", "Extract common functions"]
        assert result["status"] == "todo"
        assert result["priority"] == "medium"
        assert "backend" in result["tags"]
        assert "refactoring" in result["tags"]

    def test_trailing_notes(self):
        """Test parsing input with notes at the end without notes: keyword."""
        input_text = """Todo App Feature
plan: Add dark mode; Implement notifications
status: todo

This is a note without notes: keyword
It should be captured as part of notes."""
        
        result = parse_free_text_task(input_text)
        assert result["title"] == "Todo App Feature"
        assert result["plan"] == ["Add dark mode", "Implement notifications"]
        assert result["status"] == "todo"
        assert len(result["notes"]) >= 2
        assert "This is a note without notes: keyword" in result["notes"]
        assert "It should be captured as part of notes." in result["notes"]

    def test_whitespace_handling(self):
        """Test handling of whitespace in parsing."""
        input_text = """  Task with whitespace  
  plan:  Step 1;   Step 2  
  status:  in_progress  
  tags:  #tag1   #tag2  """
        
        result = parse_free_text_task(input_text)
        assert result["title"] == "Task with whitespace"
        assert result["plan"] == ["Step 1", "Step 2"]
        assert result["status"] == "in_progress"
        assert "tag1" in result["tags"]
        assert "tag2" in result["tags"] 