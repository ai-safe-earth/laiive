# Quick Start: Adding Real User Queries to Your Eval Datasets

## TL;DR - 5 Minute Setup

```bash
cd services/retriever

# 1. Extract queries from your logs
python -c "
from evals.utils.log_to_dataset import LogToDatasetConverter
converter = LogToDatasetConverter()
queries = converter.extract_from_api_logs('path/to/your/logs.jsonl', 'jsonl')
converter.create_query_generation_dataset(queries)
"

# 2. Manually review the generated dataset
python evals/utils/manual_annotation.py \
    evals/datasets/query_generation/user_queries.json \
    --type query_generation

# 3. Run evals with your new dataset
python evals/run_evals.py --component query_builder
```

## Step-by-Step

### 1️⃣ Extract Queries from Logs

**If you have JSON/JSONL logs:**

```python
from evals.utils.log_to_dataset import LogToDatasetConverter

converter = LogToDatasetConverter()

# Extract from logs
queries = converter.extract_from_api_logs(
    "logs/api_requests.jsonl",  # Your log file
    log_format="jsonl"           # Options: "json", "jsonl", "text"
)

# Create datasets
converter.create_query_generation_dataset(queries)
converter.create_intent_classification_dataset(queries)
```

**If you have custom log format:**

```python
import json

# Write a simple extraction function
def extract_from_my_logs(log_file):
    queries = []
    with open(log_file) as f:
        for line in f:
            log = json.loads(line)
            queries.append({
                "user_query": log["message"],  # Adjust field names
                "timestamp": log["time"],
            })
    return queries

queries = extract_from_my_logs("production.log")

# Convert to dataset
from evals.utils.log_to_dataset import LogToDatasetConverter
converter = LogToDatasetConverter()
converter.create_query_generation_dataset(queries)
```

### 2️⃣ Review and Annotate

The auto-generated dataset needs manual review:

```bash
python evals/utils/manual_annotation.py \
    evals/datasets/query_generation/user_queries.json \
    --type query_generation
```

**What you'll do:**
- Review auto-categorized queries
- Add expected patterns (regex for Cypher validation)
- Set difficulty level (easy/medium/hard)
- Delete irrelevant or duplicate cases

**Interactive menu:**
```
--- Case 1/50: qg_user_001 ---
Query: Find jazz concerts in Berlin this weekend

Options:
  1. Keep as is
  2. Update expected patterns
  3. Update category
  4. Add difficulty level
  5. Skip this case
  6. Delete this case
  s. Save and exit
```

### 3️⃣ Run Evaluations

Test your system with the new dataset:

```bash
# Run with your new dataset
python evals/run_evals.py --component query_builder

# Or create custom eval config
python -c "
from evals.config import EvalConfig, ModelConfig
from evals.runners.component_eval import run_component_eval

eval = EvalConfig(
    eval_name='production_queries',
    component='query_builder',
    dataset_path='evals/datasets/query_generation/user_queries.json',
    models=[ModelConfig(name='gpt-4o', provider='openai')],
    prompt_versions=['v1.1'],
    metrics=['accuracy', 'latency'],
    output_path='evals/reports/production_eval.json',
)

run_component_eval(eval)
"
```

## Common Log Formats

### FastAPI JSON Logs

```python
# Log structure:
# {"timestamp": "...", "message": "Find concerts", "action": "QUERY_DB"}

queries = converter.extract_from_api_logs("logs/fastapi.jsonl", "jsonl")
```

### Plain Text Logs (one query per line)

```python
queries = converter.extract_from_api_logs("logs/queries.txt", "text")
```

### Custom Format

Adapt the `_extract_query_from_log_entry` method:

```python
class MyConverter(LogToDatasetConverter):
    def _extract_query_from_log_entry(self, log_entry):
        return {
            "user_query": log_entry["your_field"],
            "timestamp": log_entry["your_timestamp"],
            "action": log_entry.get("your_action"),
        }

converter = MyConverter()
queries = converter.extract_from_api_logs("logs/custom.jsonl")
```

## Sampling Strategies

Don't add all queries - sample intelligently:

```python
# Get diverse examples (recommended)
sampled = converter.sample_queries(all_queries, n=50, strategy="diverse")

# Get most recent
sampled = converter.sample_queries(all_queries, n=50, strategy="recent")

# Get random sample
sampled = converter.sample_queries(all_queries, n=50, strategy="random")

converter.create_query_generation_dataset(sampled)
```

## Adding Individual Test Cases

Add a single challenging case:

```bash
python evals/utils/manual_annotation.py \
    evals/datasets/query_generation/test_cases.json \
    --type query_generation \
    --add
```

Then input:
```
User query: events by radiohead or coldplay in berlin this weekend under 50 euros
Category: complex_multi_constraint
Expected patterns:
  Pattern: MATCH.*Artist
  Pattern: price_amount.*<.*50
  Pattern: City.*Berlin
  Pattern: datetime
  Pattern: (empty line to finish)
Difficulty: hard
```

## Dataset Types

### 1. Query Generation Dataset

Tests Cypher query generation from natural language.

**Structure:**
```json
{
  "id": "qg_user_001",
  "category": "artist_query",
  "user_query": "Find concerts by Radiohead",
  "expected_patterns": ["MATCH.*Artist.*Radiohead", "PERFORMS_AT"],
  "should_not_contain": ["DELETE", "CREATE"],
  "metadata": {"difficulty": "easy"}
}
```

### 2. Intent Classification Dataset

Tests action decision (QUERY_DB, NEEDS_INFO, etc.).

**Structure:**
```json
{
  "id": "ic_user_001",
  "user_message": "Find jazz concerts in Berlin",
  "expected_action": "QUERY_DB",
  "conversation_history": [],
  "reasoning": "Has specific constraints"
}
```

### 3. End-to-End Conversations

Tests multi-turn conversations.

**Structure:**
```json
{
  "id": "e2e_user_001",
  "name": "user_conversation_1",
  "turns": [
    {
      "user": "Find concerts in Berlin",
      "expected_action": "QUERY_DB",
      "success_criteria": {"generates_query": true}
    }
  ]
}
```

## Tips

### ✅ Do

- **Start small**: 20-30 high-quality cases beats 200 low-quality ones
- **Sample diverse**: Cover different query types
- **Review manually**: Auto-categorization needs validation
- **Include failures**: Add queries that broke the system
- **Update regularly**: Weekly or bi-weekly additions from production

### ❌ Don't

- **Use all logs**: Filter for quality
- **Skip annotation**: Ground truth is essential
- **Ignore context**: Some queries need conversation history
- **Forget to test**: Run evals after adding cases

## Workflow Example

**Weekly dataset update routine:**

```bash
# Monday: Extract last week's queries
python scripts/extract_weekly_queries.py

# Tuesday: Sample and convert
python -c "
from evals.utils.log_to_dataset import LogToDatasetConverter
converter = LogToDatasetConverter()
queries = converter.extract_from_api_logs('logs/weekly.jsonl')
sampled = converter.sample_queries(queries, n=20, strategy='diverse')
converter.create_query_generation_dataset(sampled, 'query_generation/weekly_batch.json')
"

# Wednesday: Manual review
python evals/utils/manual_annotation.py \
    evals/datasets/query_generation/weekly_batch.json

# Thursday: Merge and test
python scripts/merge_datasets.py  # Combine with main dataset
python evals/run_evals.py --component all

# Friday: Review results, update prompts if needed
```

## Next Steps

1. **Read full guide**: `evals/DATASET_GUIDE.md` - Detailed instructions
2. **See examples**: `evals/example_usage.py` - Code patterns
3. **Understand framework**: `evals/README.md` - Full documentation

## Need Help?

Check these files:
- `evals/utils/log_to_dataset.py` - Extraction tool source
- `evals/utils/manual_annotation.py` - Annotation tool source
- `evals/datasets/*/test_cases.json` - Example datasets
