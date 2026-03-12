# Guide: Building Evaluation Datasets from Production Logs

This guide shows you how to expand your evaluation datasets with real user queries from production logs.

## Overview

Good evaluation datasets should include:
1. **Real user queries** - From production logs
2. **Edge cases** - Queries that break the system
3. **Diverse examples** - Different query types, complexity levels
4. **Ground truth** - Expected outputs for comparison

## Step-by-Step Process

### Step 1: Extract Queries from Logs

First, identify where your user queries are logged. Common sources:

- **API request logs** (FastAPI, Flask, etc.)
- **Application logs** (loguru, Python logging)
- **Database query logs**
- **Analytics events**

#### Option A: Use the automated converter

```python
from evals.utils.log_to_dataset import LogToDatasetConverter

converter = LogToDatasetConverter()

# Extract from JSON/JSONL logs
queries = converter.extract_from_api_logs(
    "logs/api_requests.jsonl",
    log_format="jsonl"
)

# Create evaluation datasets
converter.create_query_generation_dataset(queries)
converter.create_intent_classification_dataset(queries)
```

#### Option B: Manual extraction

If your logs are in a custom format, write a simple extraction script:

```python
import json

def extract_queries_from_custom_logs(log_file):
    queries = []

    with open(log_file) as f:
        for line in f:
            # Parse your log format
            log_entry = parse_log_line(line)

            # Extract query info
            if log_entry.get("endpoint") == "/chat":
                queries.append({
                    "user_query": log_entry["request"]["message"],
                    "timestamp": log_entry["timestamp"],
                    "response_time_ms": log_entry["latency"],
                })

    return queries

queries = extract_queries_from_custom_logs("production.log")
```

### Step 2: Sample and Filter

Don't use all queries - sample intelligently:

```python
from evals.utils.log_to_dataset import LogToDatasetConverter

converter = LogToDatasetConverter()

# Extract all queries
all_queries = converter.extract_from_api_logs("logs/requests.jsonl")

# Sample diverse examples
sampled = converter.sample_queries(
    all_queries,
    n=50,              # Number of queries
    strategy="diverse"  # Options: "random", "diverse", "recent"
)

# Create dataset from samples
converter.create_query_generation_dataset(sampled)
```

**Sampling strategies:**
- `"diverse"` - Get examples from each category (recommended)
- `"recent"` - Most recent queries (good for finding new patterns)
- `"random"` - Random selection

### Step 3: Add Ground Truth / Expected Outputs

Auto-generated datasets need manual review to add expected outputs.

#### Automatic Ground Truth (if available)

If your logs include the actual system response, use it:

```python
queries_with_results = [
    {
        "user_query": "Jazz concerts in Berlin",
        "cypher": "MATCH (e:Event)...",  # Actual query generated
        "action": "QUERY_DB",             # Actual action taken
        "result_count": 5,
    }
]

# These get added automatically as ground truth
converter.create_query_generation_dataset(queries_with_results)
```

The generated test case will include:
```json
{
  "id": "qg_user_001",
  "user_query": "Jazz concerts in Berlin",
  "actual_cypher_generated": "MATCH (e:Event)...",
  "metadata": {
    "has_ground_truth": true,
    "actual_action": "QUERY_DB"
  }
}
```

#### Manual Annotation

For queries without ground truth, use the annotation tool:

```bash
# Annotate query generation dataset
python evals/utils/manual_annotation.py \
    evals/datasets/query_generation/user_queries.json \
    --type query_generation

# Annotate intent classification dataset
python evals/utils/manual_annotation.py \
    evals/datasets/intent_classification/user_queries.json \
    --type intent_classification
```

**The annotation tool lets you:**
- Review auto-categorized queries
- Add expected patterns
- Set difficulty levels
- Correct inferred actions
- Delete irrelevant cases

### Step 4: Validate Your Dataset

Before using your new dataset, validate it:

```python
import json

def validate_query_generation_dataset(dataset_file):
    """Check that dataset is well-formed."""
    with open(dataset_file) as f:
        dataset = json.load(f)

    issues = []
    test_cases = dataset.get("test_cases", [])

    for tc in test_cases:
        # Check required fields
        if not tc.get("user_query"):
            issues.append(f"{tc['id']}: Missing user_query")

        if not tc.get("expected_patterns"):
            issues.append(f"{tc['id']}: No expected patterns")

        # Check for ground truth
        if not tc.get("metadata", {}).get("manually_reviewed"):
            issues.append(f"{tc['id']}: Not manually reviewed")

    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"✓ Dataset valid ({len(test_cases)} cases)")

    return len(issues) == 0

validate_query_generation_dataset(
    "evals/datasets/query_generation/user_queries.json"
)
```

### Step 5: Run Evaluations

Use your new dataset:

```bash
# Test with your new dataset
python evals/run_evals.py --component query_builder
```

Or create a custom eval config:

```python
from evals.config import EvalConfig, ModelConfig

custom_eval = EvalConfig(
    eval_name="production_queries_eval",
    component="query_builder",
    dataset_path="evals/datasets/query_generation/user_queries.json",
    models=[ModelConfig(name="gpt-4o", provider="openai")],
    prompt_versions=["v1.1"],
    metrics=["accuracy", "latency"],
    output_path="evals/reports/production_eval.json",
)

from evals.runners.component_eval import run_component_eval
run_component_eval(custom_eval)
```

## Real-World Examples

### Example 1: Extract from FastAPI JSON logs

```python
from evals.utils.log_to_dataset import LogToDatasetConverter

converter = LogToDatasetConverter()

# Your FastAPI logs with structure:
# {"timestamp": "...", "endpoint": "/chat", "request": {...}, "response": {...}}

queries = converter.extract_from_api_logs(
    "logs/fastapi_requests.jsonl",
    log_format="jsonl"
)

# Filter only successful requests
successful = [q for q in queries if q.get("success", True)]

# Sample 100 diverse examples
sampled = converter.sample_queries(successful, n=100, strategy="diverse")

# Create datasets
converter.create_query_generation_dataset(sampled)
converter.create_intent_classification_dataset(sampled)
```

### Example 2: Extract from application logs

```python
import re
from datetime import datetime

def extract_from_app_logs(log_file):
    """Extract from custom log format."""
    queries = []

    # Pattern: 2026-01-22 10:30:00 | USER_QUERY | Find jazz concerts
    pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| USER_QUERY \| (.+)"

    with open(log_file) as f:
        for line in f:
            match = re.match(pattern, line)
            if match:
                timestamp, query = match.groups()
                queries.append({
                    "user_query": query.strip(),
                    "timestamp": timestamp,
                })

    return queries

# Extract and convert
queries = extract_from_app_logs("application.log")

converter = LogToDatasetConverter()
converter.create_query_generation_dataset(queries)
```

### Example 3: Add edge cases manually

```bash
# Add a new challenging test case
python evals/utils/manual_annotation.py \
    evals/datasets/query_generation/test_cases.json \
    --type query_generation \
    --add

# Then enter:
# User query: events by radiohead or coldplay under 50 euros in berlin or amsterdam this month
# Category: complex_multi_constraint
# Expected patterns: MATCH.*Artist, price_amount.*<, City, datetime
# Difficulty: hard
```

### Example 4: Extract conversation flows

```python
def extract_conversations_from_session_logs(log_file):
    """Group queries by session for multi-turn conversations."""
    from collections import defaultdict

    sessions = defaultdict(list)

    with open(log_file) as f:
        for line in f:
            log = json.loads(line)
            session_id = log.get("session_id")

            if session_id:
                sessions[session_id].append({
                    "user_message": log["message"],
                    "action": log.get("action"),
                    "generated_query": log.get("cypher"),
                    "returned_results": log.get("result_count", 0) > 0,
                })

    # Convert to conversation format
    conversations = []
    for session_id, turns in sessions.items():
        if len(turns) >= 2:  # Only multi-turn conversations
            conversations.append({
                "session_id": session_id,
                "name": f"session_{session_id}",
                "turns": turns
            })

    return conversations

# Extract conversations
conversations = extract_conversations_from_session_logs("sessions.jsonl")

# Create end-to-end dataset
converter = LogToDatasetConverter()
converter.create_end_to_end_dataset(conversations)
```

## Best Practices

### 1. Dataset Size Guidelines

- **Component evals**: 50-200 test cases per component
  - Start with 20-30 diverse examples
  - Add 5-10 new cases weekly from production
  - Remove duplicates and low-quality cases

- **System evals**: 10-50 conversations
  - Focus on quality over quantity
  - Include both successful and failure scenarios

### 2. Diversity Matters

Ensure your dataset covers:
- ✅ Different query types (artist, venue, date, genre, etc.)
- ✅ Varying complexity (simple → complex)
- ✅ Edge cases and corner cases
- ✅ Different phrasings of similar queries
- ✅ Common failure modes

### 3. Regular Updates

```bash
# Weekly routine:
# 1. Extract new queries from logs
python scripts/extract_weekly_queries.py

# 2. Sample and add to dataset
python evals/utils/log_to_dataset.py --source logs/weekly.jsonl

# 3. Manual review
python evals/utils/manual_annotation.py evals/datasets/.../new_cases.json

# 4. Merge into main dataset
python scripts/merge_datasets.py

# 5. Run regression tests
python evals/run_evals.py --component all
```

### 4. Track Dataset Metrics

Keep a changelog for your datasets:

```json
{
  "version": "1.2",
  "created_at": "2026-01-22",
  "description": "Added 30 user queries from production",
  "changes": [
    "Added 15 complex multi-constraint queries",
    "Added 10 edge cases from failed requests",
    "Added 5 semantic search examples",
    "Removed 3 duplicate cases"
  ],
  "test_cases": [...]
}
```

### 5. Quality Over Quantity

Better to have:
- 50 high-quality, diverse, manually-reviewed cases
- Than 500 auto-generated, low-quality cases

Focus on:
- **Representativeness**: Covers real user behavior
- **Clarity**: Clear expected outputs
- **Difficulty balance**: Mix of easy, medium, hard
- **Actionability**: Failed cases point to specific improvements

## Common Pitfalls

### ❌ Don't

1. **Use all production queries** - Too noisy, includes spam/errors
2. **Skip manual review** - Auto-categorization is imperfect
3. **Ignore failed cases** - These are often the most valuable
4. **Make datasets too large** - Slows down iteration, harder to maintain
5. **Forget to version** - Track changes over time

### ✅ Do

1. **Sample intelligently** - Diverse, representative examples
2. **Review and annotate** - Ensure quality ground truth
3. **Include edge cases** - Explicitly add challenging examples
4. **Keep datasets lean** - Remove duplicates and low-value cases
5. **Update regularly** - Add new patterns as they emerge

## Troubleshooting

### "My logs don't match the expected format"

Customize the extraction logic:

```python
class CustomLogExtractor(LogToDatasetConverter):
    def _extract_query_from_log_entry(self, log_entry: Dict):
        # Your custom extraction logic
        return {
            "user_query": log_entry["custom_field"],
            "timestamp": log_entry["time"],
            # ... map your fields
        }

extractor = CustomLogExtractor()
```

### "I don't have ground truth in logs"

That's fine! Use auto-categorization + manual review:

```python
# Auto-categorize provides starting point
converter.create_query_generation_dataset(
    queries,
    auto_categorize=True  # Suggests patterns automatically
)

# Then manually review and correct
# python evals/utils/manual_annotation.py dataset.json
```

### "Too many cases need manual review"

Sample more aggressively:

```python
# Start with just 20-30 high-quality examples
sampled = converter.sample_queries(queries, n=30, strategy="diverse")

# Or focus on specific categories
jazz_queries = [q for q in queries if "jazz" in q["user_query"].lower()]
```

## Next Steps

1. **Extract your first batch**: Use `log_to_dataset.py` on your logs
2. **Manual review**: Annotate 20-30 cases with `manual_annotation.py`
3. **Run evals**: Test with your new dataset
4. **Iterate**: Add more cases based on failures
5. **Automate**: Set up weekly extraction and review process

## Resources

- `evals/utils/log_to_dataset.py` - Automated extraction tool
- `evals/utils/manual_annotation.py` - Interactive annotation
- `evals/example_usage.py` - Code examples
- `evals/README.md` - Full evaluation framework docs
