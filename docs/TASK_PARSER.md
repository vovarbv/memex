# Free-Text Task Parser

The Memex task system supports creating tasks using natural free-text format. This document explains the capabilities of the free-text parser and provides examples of all supported formats.

## Basic Usage

The parser takes a free-text string and converts it into a structured task. The first line is always interpreted as the task title unless it starts with a recognized keyword.

**Example**:
```
Implement user authentication for the API
status: in_progress
priority: high
```

This creates a task with the title "Implement user authentication for the API", status set to "in_progress", and priority set to "high".

## Supported Keywords

The parser recognizes the following keywords:

| Keyword | Description | Default Value |
|---------|-------------|--------------|
| `status:` | Task status | `todo` |
| `priority:` | Task priority | `medium` |
| `progress:` | Completion percentage | `0` |
| `plan:` | List of steps to complete | `[]` (empty list) |
| `tags:` | Tags for categorization | `[]` (empty list) |
| `notes:` | Additional information | `""` (empty string) |

## Keyword Detection Features

### Case-Insensitive Keywords

All keywords are case-insensitive. These are all equivalent:
```
status: in_progress
Status: in_progress
STATUS: in_progress
```

### Flexible Whitespace

Whitespace around the colon is optional:
```
status: in_progress
status:in_progress
status : in_progress
```

## Status Values

### Status Options

- `todo` - Task hasn't been started
- `in_progress` - Task is being worked on
- `done` - Task is completed
- `blocked` - Task is blocked by external factors
- `deferred` - Task is postponed for later
- `pending` - Task is waiting for review or other action

### Status Synonyms

The parser recognizes various synonyms for each status:

**Todo synonyms**:
- `todo`
- `to-do`
- `backlog`
- `pending`
- `new`

**In Progress synonyms**:
- `in_progress`
- `in progress`
- `inprogress`
- `wip`
- `working`
- `started`
- `ongoing`
- `active`

**Done synonyms**:
- `done`
- `complete`
- `completed`
- `finished`
- `resolved`
- `closed`

## Priority Values

### Priority Options

- `high` - High priority task
- `medium` - Medium priority task
- `low` - Low priority task

### Priority Abbreviations and Synonyms

**High**:
- `h`
- `high`
- `important`
- `critical`
- `urgent`

**Medium**:
- `m`
- `med`
- `medium`
- `normal`
- `default`

**Low**:
- `l`
- `low`
- `minor`
- `trivial`

## Progress Values

The progress value can be specified as an integer or decimal with or without a percentage sign:

```
progress: 25
progress: 25%
progress: 33.5%
```

## Plan Formats

### Semicolon-Separated

```
plan: Step 1; Step 2; Step 3
```

### Numbered List

```
plan: 1. Design API 2. Implement endpoints 3. Write tests
```

### Newline-Separated

```
plan:
Step 1
Step 2
Step 3
```

## Tag Formats

### Space-Separated

```
tags: frontend api testing
```

### Comma-Separated

```
tags: frontend, api, testing
```

### Hashtag Prefixed

```
tags: #frontend #api #testing
```

### Multi-Word Tags with Quotes

```
tags: "user auth" api "error handling"
```

### Mixed Format Example

```
tags: #frontend, "api gateway", database
```

## Notes Handling

### Notes with Keyword

```
notes: This is a note
This is the second line of the note
```

### Implicit Notes (Without Keyword)

Any text without a recognized keyword is treated as notes:

```
Implement Login Feature
status: todo
priority: high
This line will be treated as a note.
And this one too.
```

## Complete Example

```
Implement User Authentication
status: in_progress
priority: high
progress: 35%
plan:
1. Design API endpoints
2. Implement JWT tokens
3. Add password hashing
tags: #backend, security, "user management"
notes: Need to follow OWASP guidelines
Also need to check for rate limiting requirements
```

This would create a task with:
- Title: "Implement User Authentication"
- Status: "in_progress"
- Priority: "high"
- Progress: 35%
- Plan: Three steps as listed
- Tags: "backend", "security", "user management"
- Notes: Two lines about OWASP and rate limiting

## Testing

You can run the tests for the free-text parser with:

```
python -m memex.scripts.test_free_text_parser
``` 