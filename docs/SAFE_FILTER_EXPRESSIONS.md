# Safe Filter Expressions Guide

## Overview

The Memex search functionality includes an advanced filtering feature that allows you to write custom filter expressions. For security reasons, these expressions use a restricted subset of Python that only allows safe operations.

## Allowed Operations

### 1. Comparisons
- `==` (equal)
- `!=` (not equal)
- `<` (less than)
- `<=` (less than or equal)
- `>` (greater than)
- `>=` (greater than or equal)
- `in` (membership test)
- `not in` (negative membership test)
- `is` (identity test)
- `is not` (negative identity test)

### 2. Boolean Logic
- `and`
- `or`
- `not`

### 3. Data Access
- Dictionary access: `meta_item.get('key', default)`
- List/string indexing: `meta_item['key']`
- Nested access: `meta_item.get('metadata', {}).get('author')`

### 4. String Methods
- `lower()` - Convert to lowercase
- `upper()` - Convert to uppercase
- `strip()`, `lstrip()`, `rstrip()` - Remove whitespace
- `startswith()`, `endswith()` - Check string prefix/suffix
- `replace()` - Replace substring
- `split()` - Split string into list
- `find()` - Find substring position
- `count()` - Count occurrences

### 5. Safe Built-in Functions
- `len()` - Get length
- `str()`, `int()`, `float()`, `bool()` - Type conversions
- `min()`, `max()` - Find minimum/maximum
- `sum()` - Sum numbers
- `any()`, `all()` - Boolean aggregation

## Examples

### Basic Filtering

```python
# Filter by type
meta_item.get('type') == 'task'

# Filter by status
meta_item.get('status') == 'in_progress'

# Multiple conditions
meta_item.get('type') == 'task' and meta_item.get('status') == 'done'
```

### String Operations

```python
# Case-insensitive search
'python' in meta_item.get('content', '').lower()

# Check if title starts with specific text
meta_item.get('title', '').startswith('Fix')

# Check language (case-insensitive)
meta_item.get('language', '').lower() == 'python'
```

### Numeric Comparisons

```python
# Progress greater than 50%
meta_item.get('progress', 0) > 50

# Check list length
len(meta_item.get('tags', [])) > 2
```

### Complex Filters

```python
# Find high-priority tasks that are in progress
meta_item.get('type') == 'task' and 
meta_item.get('priority') == 'high' and 
meta_item.get('status') == 'in_progress'

# Find Python snippets containing 'api'
meta_item.get('type') == 'snippet' and 
meta_item.get('language') == 'python' and 
'api' in meta_item.get('content', '').lower()

# Find notes created by specific author
meta_item.get('type') == 'note' and 
meta_item.get('metadata', {}).get('author') == 'john_doe'
```

## Blocked Operations

For security reasons, the following operations are NOT allowed:

### ❌ Imports
```python
__import__('os')  # BLOCKED
import subprocess  # BLOCKED
```

### ❌ Function Definitions
```python
lambda x: x * 2  # BLOCKED
def func(): pass  # BLOCKED
```

### ❌ Dangerous Built-ins
```python
eval('code')  # BLOCKED
exec('code')  # BLOCKED
open('file')  # BLOCKED
compile()     # BLOCKED
```

### ❌ Attribute Manipulation
```python
meta_item.__class__  # BLOCKED
meta_item.__dict__   # BLOCKED
setattr()            # BLOCKED
delattr()            # BLOCKED
```

## Validation

Before using a filter expression, you can validate it using the "Validate Expression" button in the UI. This will check if your expression is syntactically correct and uses only allowed operations.

## Tips

1. **Use `.get()` with defaults**: Always use `.get('key', default)` instead of direct access to avoid KeyError
2. **Handle None values**: Check for None before string operations
3. **Case sensitivity**: Use `.lower()` for case-insensitive comparisons
4. **Type safety**: Ensure the data type before operations (e.g., check if it's a string before using string methods)

## Common Patterns

### Check if a field contains text (case-insensitive)
```python
'search_term' in meta_item.get('field', '').lower()
```

### Check if a tag exists
```python
'important' in meta_item.get('tags', [])
```

### Check multiple possible values
```python
meta_item.get('status') in ['done', 'completed', 'finished']
```

### Combine conditions with parentheses
```python
(meta_item.get('type') == 'task' or meta_item.get('type') == 'note') and 
'urgent' in meta_item.get('content', '').lower()
```