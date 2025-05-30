#!/usr/bin/env python
"""
Tests for the safe expression evaluator.
"""
import pytest

from ..scripts.safe_eval import safe_eval, validate_expression, SafeEvaluator


class TestSafeEval:
    """Test cases for the safe expression evaluator."""
    
    def test_basic_comparisons(self):
        """Test basic comparison operations."""
        meta = {"type": "task", "status": "done", "priority": "high"}
        
        # Equal
        assert safe_eval("meta_item.get('type') == 'task'", {"meta_item": meta}) is True
        assert safe_eval("meta_item.get('type') == 'snippet'", {"meta_item": meta}) is False
        
        # Not equal
        assert safe_eval("meta_item.get('type') != 'snippet'", {"meta_item": meta}) is True
        
        # In operator
        assert safe_eval("'task' in meta_item.get('type', '')", {"meta_item": meta}) is True
        assert safe_eval("'snippet' in meta_item.get('type', '')", {"meta_item": meta}) is False
    
    def test_boolean_operations(self):
        """Test boolean AND/OR operations."""
        meta = {"type": "task", "status": "done", "priority": "high"}
        
        # AND
        assert safe_eval(
            "meta_item.get('type') == 'task' and meta_item.get('status') == 'done'",
            {"meta_item": meta}
        ) is True
        
        assert safe_eval(
            "meta_item.get('type') == 'task' and meta_item.get('status') == 'todo'",
            {"meta_item": meta}
        ) is False
        
        # OR
        assert safe_eval(
            "meta_item.get('type') == 'snippet' or meta_item.get('status') == 'done'",
            {"meta_item": meta}
        ) is True
        
        # NOT
        assert safe_eval(
            "not (meta_item.get('type') == 'snippet')",
            {"meta_item": meta}
        ) is True
    
    def test_string_methods(self):
        """Test allowed string methods."""
        meta = {"content": "Hello World", "type": "TASK"}
        
        # lower()
        assert safe_eval(
            "meta_item.get('type', '').lower() == 'task'",
            {"meta_item": meta}
        ) is True
        
        # upper()
        assert safe_eval(
            "meta_item.get('content', '').upper() == 'HELLO WORLD'",
            {"meta_item": meta}
        ) is True
        
        # startswith()
        assert safe_eval(
            "meta_item.get('content', '').startswith('Hello')",
            {"meta_item": meta}
        ) is True
        
        # in with lower()
        assert safe_eval(
            "'world' in meta_item.get('content', '').lower()",
            {"meta_item": meta}
        ) is True
    
    def test_numeric_operations(self):
        """Test numeric comparisons and operations."""
        meta = {"progress": 75, "items": [1, 2, 3, 4, 5]}
        
        # Greater than
        assert safe_eval(
            "meta_item.get('progress', 0) > 50",
            {"meta_item": meta}
        ) is True
        
        # Less than or equal
        assert safe_eval(
            "meta_item.get('progress', 0) <= 100",
            {"meta_item": meta}
        ) is True
        
        # Length function
        assert safe_eval(
            "len(meta_item.get('items', [])) == 5",
            {"meta_item": meta}
        ) is True
    
    def test_nested_data(self):
        """Test accessing nested data structures."""
        meta = {
            "metadata": {
                "author": "test_user",
                "tags": ["python", "testing"]
            }
        }
        
        # Nested dict access
        assert safe_eval(
            "meta_item.get('metadata', {}).get('author') == 'test_user'",
            {"meta_item": meta}
        ) is True
        
        # List membership in nested structure
        assert safe_eval(
            "'python' in meta_item.get('metadata', {}).get('tags', [])",
            {"meta_item": meta}
        ) is True
    
    def test_safe_builtins(self):
        """Test allowed built-in functions."""
        meta = {"numbers": [3, 1, 4, 1, 5]}
        
        # min/max
        assert safe_eval(
            "min(meta_item.get('numbers', [])) == 1",
            {"meta_item": meta}
        ) is True
        
        assert safe_eval(
            "max(meta_item.get('numbers', [])) == 5",
            {"meta_item": meta}
        ) is True
        
        # sum
        assert safe_eval(
            "sum(meta_item.get('numbers', [])) == 14",
            {"meta_item": meta}
        ) is True
    
    def test_dangerous_operations_blocked(self):
        """Test that dangerous operations are properly blocked."""
        meta = {"type": "test"}
        
        # Import statements
        with pytest.raises(ValueError, match="Function '__import__' is not allowed"):
            safe_eval("__import__('os')", {"meta_item": meta})
        
        # exec/eval
        with pytest.raises(ValueError, match="Function 'exec' is not allowed"):
            safe_eval("exec('print(1)')", {"meta_item": meta})
        
        with pytest.raises(ValueError, match="Function 'eval' is not allowed"):
            safe_eval("eval('1+1')", {"meta_item": meta})
        
        # File operations
        with pytest.raises(ValueError, match="Function 'open' is not allowed"):
            safe_eval("open('/etc/passwd')", {"meta_item": meta})
        
        # Attribute access to special attributes
        with pytest.raises(ValueError):
            safe_eval("meta_item.__class__.__bases__", {"meta_item": meta})
        
        # Lambda functions
        with pytest.raises(ValueError, match="Unsupported operation"):
            safe_eval("(lambda x: x*2)(5)", {"meta_item": meta})
    
    def test_complex_expressions(self):
        """Test more complex but safe expressions."""
        meta = {
            "type": "snippet",
            "language": "python",
            "content": "def calculate_sum(a, b):\n    return a + b",
            "tags": ["function", "math", "utility"],
            "lines": 2
        }
        
        # Complex boolean expression
        assert safe_eval(
            "(meta_item.get('type') == 'snippet' and "
            "meta_item.get('language') == 'python' and "
            "('function' in meta_item.get('tags', []) or 'class' in meta_item.get('tags', [])))",
            {"meta_item": meta}
        ) is True
        
        # String operations combined with boolean logic
        assert safe_eval(
            "'calculate' in meta_item.get('content', '').lower() and "
            "meta_item.get('lines', 0) < 10",
            {"meta_item": meta}
        ) is True
    
    def test_validation_function(self):
        """Test the expression validation function."""
        # Valid expressions
        assert validate_expression("meta_item.get('type') == 'task'") is None
        assert validate_expression("'test' in meta_item.get('content', '')") is None
        
        # Invalid syntax
        error = validate_expression("meta_item.get('type' ==")
        assert error is not None
        assert "Syntax error" in error
        
        # Dangerous operations
        error = validate_expression("__import__('os').system('ls')")
        assert error is not None
        assert "Invalid expression" in error
    
    def test_edge_cases(self):
        """Test edge cases and error handling."""
        meta = {"type": None, "empty": "", "list": []}
        
        # None values
        assert safe_eval(
            "meta_item.get('type') is None",
            {"meta_item": meta}
        ) is True
        
        # Empty strings
        assert safe_eval(
            "meta_item.get('empty', 'default') == ''",
            {"meta_item": meta}
        ) is True
        
        # Empty lists
        assert safe_eval(
            "len(meta_item.get('list', [])) == 0",
            {"meta_item": meta}
        ) is True
        
        # Missing keys with defaults
        assert safe_eval(
            "meta_item.get('missing', 'default') == 'default'",
            {"meta_item": meta}
        ) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])