#!/usr/bin/env python
"""
Safe expression evaluator for user-provided filter expressions.
This module provides a restricted evaluator that only allows safe operations
on metadata dictionaries, preventing code injection attacks.
"""
import ast
import operator
import logging
from typing import Any, Dict, Optional

# Define allowed operators
ALLOWED_OPERATORS = {
    # Comparison operators
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda x, y: x in y,
    ast.NotIn: lambda x, y: x not in y,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    
    # Boolean operators
    ast.And: lambda x, y: x and y,
    ast.Or: lambda x, y: x or y,
    ast.Not: operator.not_,
    
    # Arithmetic operators (for numeric comparisons)
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}

# Define allowed built-in functions
ALLOWED_BUILTINS = {
    'len': len,
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
    'list': list,
    'dict': dict,
    'set': set,
    'tuple': tuple,
    'min': min,
    'max': max,
    'sum': sum,
    'any': any,
    'all': all,
    'sorted': sorted,
    'reversed': reversed,
}

# Define allowed string methods
ALLOWED_STRING_METHODS = {
    'lower', 'upper', 'strip', 'lstrip', 'rstrip',
    'startswith', 'endswith', 'replace', 'split',
    'join', 'find', 'count', 'isdigit', 'isalpha',
    'isalnum', 'islower', 'isupper'
}

# Define allowed list/dict methods
ALLOWED_CONTAINER_METHODS = {
    'get', 'keys', 'values', 'items', 'index', 'count'
}


class SafeEvaluator(ast.NodeVisitor):
    """
    A safe AST evaluator that only allows specific operations.
    Prevents arbitrary code execution while allowing useful filter expressions.
    """
    
    def __init__(self, variables: Dict[str, Any]):
        """
        Initialize the evaluator with available variables.
        
        Args:
            variables: Dictionary of variable names to their values
        """
        self.variables = variables
        self.stack = []
    
    def evaluate(self, expression: str) -> Any:
        """
        Safely evaluate a Python expression.
        
        Args:
            expression: The expression string to evaluate
            
        Returns:
            The result of the expression
            
        Raises:
            ValueError: If the expression contains unsafe operations
            SyntaxError: If the expression has invalid syntax
        """
        try:
            # Parse the expression into an AST
            tree = ast.parse(expression, mode='eval')
            
            # Evaluate the AST
            return self.visit(tree.body)
            
        except SyntaxError as e:
            raise SyntaxError(f"Invalid expression syntax: {e}")
        except Exception as e:
            raise ValueError(f"Error evaluating expression: {e}")
    
    def visit_Expression(self, node):
        """Visit an Expression node."""
        return self.visit(node.body)
    
    def visit_BoolOp(self, node):
        """Visit a boolean operation (and/or)."""
        op = ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")
        
        # Evaluate all values
        values = [self.visit(val) for val in node.values]
        
        # Apply the operator
        result = values[0]
        for val in values[1:]:
            result = op(result, val)
        return result
    
    def visit_UnaryOp(self, node):
        """Visit a unary operation (not, -, +)."""
        op = ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        
        operand = self.visit(node.operand)
        return op(operand)
    
    def visit_Compare(self, node):
        """Visit a comparison operation."""
        left = self.visit(node.left)
        
        for op, comparator in zip(node.ops, node.comparators):
            op_func = ALLOWED_OPERATORS.get(type(op))
            if op_func is None:
                raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
            
            right = self.visit(comparator)
            
            # Perform the comparison
            if not op_func(left, right):
                return False
            
            # For chained comparisons
            left = right
        
        return True
    
    def visit_BinOp(self, node):
        """Visit a binary operation."""
        op = ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
        
        left = self.visit(node.left)
        right = self.visit(node.right)
        
        return op(left, right)
    
    def visit_Call(self, node):
        """Visit a function call."""
        # Get the function name
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ALLOWED_BUILTINS:
                func = ALLOWED_BUILTINS[func_name]
                args = [self.visit(arg) for arg in node.args]
                return func(*args)
            else:
                raise ValueError(f"Function '{func_name}' is not allowed")
        
        # Handle method calls (e.g., string.lower())
        elif isinstance(node.func, ast.Attribute):
            obj = self.visit(node.func.value)
            method_name = node.func.attr
            
            # Check if the method is allowed based on the object type
            if isinstance(obj, str) and method_name in ALLOWED_STRING_METHODS:
                method = getattr(obj, method_name)
                args = [self.visit(arg) for arg in node.args]
                return method(*args)
            elif isinstance(obj, (dict, list)) and method_name in ALLOWED_CONTAINER_METHODS:
                method = getattr(obj, method_name)
                args = [self.visit(arg) for arg in node.args]
                return method(*args)
            else:
                raise ValueError(f"Method '{method_name}' is not allowed for {type(obj).__name__}")
        
        # Handle lambda functions specifically
        elif isinstance(node.func, ast.Lambda):
            raise ValueError("Unsupported operation: lambda functions are not allowed")
        
        else:
            raise ValueError("Complex function calls are not allowed")
    
    def visit_Attribute(self, node):
        """Visit an attribute access (e.g., obj.attr)."""
        obj = self.visit(node.value)
        
        # Block access to dangerous attributes that could lead to code execution
        dangerous_attrs = {
            '__class__', '__bases__', '__mro__', '__subclasses__',
            '__globals__', '__locals__', '__dict__', '__getattribute__',
            '__setattr__', '__delattr__', '__import__', '__builtins__',
            '__code__', '__func_globals__', '__func_closure__'
        }
        
        if node.attr in dangerous_attrs:
            raise ValueError(f"Access to attribute '{node.attr}' is not allowed for security reasons")
        
        # Only allow attribute access on dictionaries using dot notation
        # This is mainly for convenience, as dict.get() is preferred
        if hasattr(obj, node.attr):
            return getattr(obj, node.attr)
        else:
            raise AttributeError(f"Object has no attribute '{node.attr}'")
    
    def visit_Subscript(self, node):
        """Visit a subscript operation (e.g., obj[key])."""
        obj = self.visit(node.value)
        
        if isinstance(node.slice, ast.Index):
            # Python < 3.9 compatibility
            key = self.visit(node.slice.value)
        else:
            key = self.visit(node.slice)
        
        try:
            return obj[key]
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(f"Invalid subscript access: {e}")
    
    def visit_Name(self, node):
        """Visit a variable name."""
        if node.id in self.variables:
            return self.variables[node.id]
        else:
            raise NameError(f"Variable '{node.id}' is not defined")
    
    def visit_Constant(self, node):
        """Visit a constant value."""
        return node.value
    
    # For Python 3.7 compatibility
    def visit_Num(self, node):
        """Visit a number."""
        return node.n
    
    def visit_Str(self, node):
        """Visit a string."""
        return node.s
    
    def visit_NameConstant(self, node):
        """Visit a name constant (True, False, None)."""
        return node.value
    
    def visit_List(self, node):
        """Visit a list literal."""
        return [self.visit(elt) for elt in node.elts]
    
    def visit_Tuple(self, node):
        """Visit a tuple literal."""
        return tuple(self.visit(elt) for elt in node.elts)
    
    def visit_Dict(self, node):
        """Visit a dict literal."""
        keys = [self.visit(k) for k in node.keys]
        values = [self.visit(v) for v in node.values]
        return dict(zip(keys, values))
    
    def generic_visit(self, node):
        """Called for nodes that don't have a specific visit method."""
        raise ValueError(f"Unsupported operation: {type(node).__name__}")


def safe_eval(expression: str, variables: Dict[str, Any]) -> Any:
    """
    Safely evaluate a Python expression with restricted operations.
    
    This function allows only safe operations like comparisons, boolean logic,
    and basic string/list operations. It prevents arbitrary code execution.
    
    Args:
        expression: The expression string to evaluate
        variables: Dictionary of available variables
        
    Returns:
        The result of the expression
        
    Raises:
        ValueError: If the expression contains unsafe operations
        SyntaxError: If the expression has invalid syntax
    
    Examples:
        >>> meta = {"type": "task", "status": "done", "priority": "high"}
        >>> safe_eval("meta_item.get('type') == 'task'", {"meta_item": meta})
        True
        >>> safe_eval("meta_item.get('status') == 'done' and meta_item.get('priority') == 'high'", {"meta_item": meta})
        True
        >>> safe_eval("'task' in meta_item.get('type', '')", {"meta_item": meta})
        True
    """
    evaluator = SafeEvaluator(variables)
    return evaluator.evaluate(expression)


def validate_expression(expression: str) -> Optional[str]:
    """
    Validate an expression without evaluating it.
    
    Args:
        expression: The expression to validate
        
    Returns:
        None if valid, error message if invalid
    """
    try:
        # Try to parse the expression
        ast.parse(expression, mode='eval')
        
        # Try to evaluate with a dummy meta_item
        dummy_meta = {
            "type": "test",
            "status": "test",
            "content": "test content",
            "id": "test_id"
        }
        safe_eval(expression, {"meta_item": dummy_meta})
        
        return None
    except SyntaxError as e:
        return f"Syntax error: {e}"
    except Exception as e:
        return f"Invalid expression: {e}"


# Example usage and tests
if __name__ == "__main__":
    # Test data
    test_meta = {
        "type": "snippet",
        "language": "python",
        "content": "def hello(): print('world')",
        "tags": ["function", "greeting"],
        "metadata": {
            "author": "test",
            "created": "2024-01-01"
        }
    }
    
    # Test cases
    test_expressions = [
        # Safe expressions that should work
        "meta_item.get('type') == 'snippet'",
        "meta_item.get('language') == 'python' and 'greeting' in meta_item.get('tags', [])",
        "len(meta_item.get('content', '')) > 10",
        "'hello' in meta_item.get('content', '').lower()",
        "meta_item.get('metadata', {}).get('author') == 'test'",
        
        # Unsafe expressions that should fail
        "__import__('os').system('ls')",
        "exec('print(1)')",
        "eval('1+1')",
        "open('/etc/passwd').read()",
        "meta_item.__class__.__bases__[0].__subclasses__()",
    ]
    
    print("Testing safe expression evaluator...")
    for expr in test_expressions:
        print(f"\nExpression: {expr}")
        try:
            result = safe_eval(expr, {"meta_item": test_meta})
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error (expected for unsafe expressions): {e}")