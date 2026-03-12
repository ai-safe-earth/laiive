# Guide: Quality Filtering for Evaluation Datasets

Not all production logs are good evaluation examples. This guide shows you how to automatically evaluate and filter logs for quality before adding them to your datasets.

## The Problem

Raw production logs contain:
- ❌ Spam and gibberish
- ❌ Incomplete/malformed queries
- ❌ Queries that caused errors
- ❌ Queries with no results (might be bad examples)
- ❌ Test queries from developers
- ✅ Real, successful user interactions (what we want!)

**Solution**: Automatic quality filtering using heuristics + LLM evaluation.

## Quick Start

### 1. Basic Quality Filtering (Fast, No LLM)

```python
from evals.utils.smart_extraction import SmartLogExtractor

# Extract with automatic quality filtering
extractor = SmartLogExtractor(
    use_llm_evaluation=False,  # Fast heuristic-only mode
    min_score=0.5              # Minimum quality score (0.0-1.0)
)

# Extract, filter, and create datasets in one go
datasets = extractor.extract_filter_and_create_datasets(
    "logs/production.jsonl",
    log_format="jsonl",
    sample_size=50
)

# Result: Only high-quality queries in your datasets
```

### 2. LLM-Powered Quality Filtering (Slower, More Accurate)

```python
# Use LLM to evaluate conversation quality
extractor = SmartLogExtractor(
    use_llm_evaluation=True,   # Enable LLM evaluation
    min_score=0.6              # Higher threshold
)

datasets = extractor.extract_filter_and_create_datasets(
    "logs/production.jsonl",
    sample_size=30
)
```

### 3. Smart Selection (Best Quality)

```python
from evals.utils.smart_extraction import extract_with_llm_selection

# LLM selects the BEST examples
selected_queries = extract_with_llm_selection(
    "logs/production.jsonl",
    target_count=50  # Get top 50 examples
)
```

## How Quality Filtering Works

### Quality Signals (Heuristic)

The system automatically checks:

1. **Content Quality**
   - ✓ Has actual text content
   - ✓ Reasonable length (5-100 words)
   - ✗ Too short or too long

2. **Processing Success**
   - ✓ System successfully processed (QUERY_DB, NEEDS_INFO)
   - ✗ Errors or failures
   - ✓ Reasonable latency (<5 seconds)

3. **Results Quality** (for QUERY_DB)
   - ✓ Returned 1-50 results (good)
   - ⚠ Returned >50 results (too broad)
   - ✗ Returned 0 results (might be bad query)

4. **Conversation Flow** (multi-turn)
   - ✓ Multiple turns with progression
   - ✓ Context-dependent follow-ups
   - ✓ Low error rate
   - ✗ Repetitive or stuck

**Score**: 0.0 (terrible) to 1.0 (excellent)

### LLM Evaluation (Optional)

For higher accuracy, the LLM analyzes:

1. **User Satisfaction**
   - Detected thanks/positive feedback?
   - Frustration indicators?
   - Successful task completion?

2. **Conversation Success**
   - Did assistant help the user?
   - Appropriate responses?
   - Good interaction flow?

3. **User Engagement**
   - Follow-up questions?
   - Query refinement?
   - Natural progression?

4. **Example Quality**
   - Would this be useful for training/eval?
   - Clear intent?
   - Demonstrates system capabilities?

## Usage Examples

### Example 1: Filter Existing Logs

```python
from evals.utils.quality_filter import ConversationQualityEvaluator

evaluator = ConversationQualityEvaluator(use_llm=False)

# Evaluate a single query
query_data = {
    "user_query": "Find jazz concerts in Berlin",
    "action": "QUERY_DB",
    "result_count": 5,
    "latency_ms": 450
}

score = evaluator.evaluate_single_query(query_data)

print(f"Score: {score.overall_score:.2f}")
print(f"Good example: {score.is_good_example}")
print(f"Reasoning: {score.reasoning}")
# Output:
# Score: 0.80
# Good example: True
# Reasoning: Successfully processed as QUERY_DB; Returned 5 results
```

### Example 2: Batch Filter

```python
from evals.utils.log_to_dataset import LogToDatasetConverter
from evals.utils.quality_filter import ConversationQualityEvaluator

# Extract queries
converter = LogToDatasetConverter()
all_queries = converter.extract_from_api_logs("logs/week.jsonl")

# Filter for quality
evaluator = ConversationQualityEvaluator(use_llm=False)
filtered, scores = evaluator.batch_evaluate(
    all_queries,
    min_score=0.5,  # Only queries scoring 0.5+
    min_confidence=0.6
)

print(f"Filtered: {len(filtered)}/{len(all_queries)} queries")
# Output: Filtered: 127/342 queries (37% pass rate)

# Create dataset with filtered queries
converter.create_query_generation_dataset(filtered)
```

### Example 3: Quality Tiers

```python
from evals.utils.smart_extraction import extract_with_quality_tiers

# Separate queries by quality level
tiers = extract_with_quality_tiers("logs/production.jsonl")

# Use different tiers for different purposes
print(f"Excellent: {len(tiers['excellent'])} queries")  # Use for main eval set
print(f"Good: {len(tiers['good'])} queries")          # Use for regression tests
print(f"Fair: {len(tiers['fair'])} queries")          # Review manually
print(f"Poor: {len(tiers['poor'])} queries")          # Skip or negative examples

# Create datasets from excellent tier only
converter = LogToDatasetConverter()
converter.create_query_generation_dataset(tiers['excellent'])
```

### Example 4: LLM-Powered Selection

```python
from evals.utils.smart_extraction import extract_with_llm_selection

# Let LLM select the best 30 examples
best_queries = extract_with_llm_selection(
    "logs/production.jsonl",
    target_count=30
)

# These are your golden examples - manually review and add to core eval set
```

### Example 5: Conversation Quality

```python
evaluator = ConversationQualityEvaluator(use_llm=True)

# Multi-turn conversation
conversation = [
    {
        "user_query": "Find concerts in Berlin",
        "action": "QUERY_DB",
        "result_count": 15
    },
    {
        "user_query": "What about jazz specifically?",
        "action": "QUERY_DB",
        "result_count": 5
    },
    {
        "user_query": "Thanks!",
        "action": "BYE_MESSAGE"
    }
]

score = evaluator.evaluate_conversation(conversation)

print(f"Conversation Score: {score.overall_score:.2f}")
print(f"Good example: {score.is_good_example}")
print(f"Signals: {score.signals}")
# Output:
# Conversation Score: 0.85
# Good example: True
# Signals: {'num_turns': 3, 'has_successful_query': True,
#           'context_dependent_turns': 1, 'user_satisfaction': 9/10, ...}
```

### Example 6: Quality Report

```python
from evals.utils.quality_filter import ConversationQualityEvaluator

evaluator = ConversationQualityEvaluator()

# Evaluate all queries
all_queries = [...]  # Your extracted queries
scores = [evaluator.evaluate_single_query(q) for q in all_queries]

# Generate detailed report
report = evaluator.generate_quality_report(
    all_queries,
    scores,
    output_file="evals/reports/quality_report.json"
)

# Output:
# ============================================================
# QUALITY ASSESSMENT SUMMARY
# ============================================================
# Overall Stats:
#   Total queries: 342
#   Good examples: 127 (37.1%)
#   Average score: 0.58
#   Average confidence: 0.75
#
# Score Distribution:
#   excellent (0.8-1.0): 45 (13.2%)
#   good (0.6-0.8): 82 (24.0%)
#   fair (0.4-0.6): 115 (33.6%)
#   poor (0.0-0.4): 100 (29.2%)
#
# Common Issues:
#   no_results: 67
#   failed_processing: 23
#   has_errors: 18
```

## CLI Usage

The smart extraction script supports quality filtering:

```bash
# Fast mode (heuristics only)
python evals/utils/smart_extraction.py \
    logs/production.jsonl \
    --format jsonl \
    --mode fast \
    --sample 50

# Balanced mode (selective LLM for borderline cases)
python evals/utils/smart_extraction.py \
    logs/production.jsonl \
    --mode balanced \
    --sample 30

# LLM mode (full LLM evaluation - slower but best quality)
python evals/utils/smart_extraction.py \
    logs/production.jsonl \
    --mode llm \
    --sample 20
```

## Quality Filtering Strategies

### Strategy 1: Fast Filtering (No Cost)

**When**: Initial filtering of large log files
**Method**: Heuristic signals only

```python
extractor = SmartLogExtractor(use_llm_evaluation=False, min_score=0.5)
```

**Pros**: Fast, free, processes thousands of queries
**Cons**: Less accurate, might miss subtle quality issues

### Strategy 2: Balanced Filtering (Low Cost)

**When**: Regular dataset updates
**Method**: Heuristics + LLM for borderline cases

```python
extractor = SmartLogExtractor(use_llm_evaluation=True, min_score=0.6)
```

**Pros**: Good accuracy, reasonable cost
**Cons**: Slower than pure heuristics

### Strategy 3: LLM Selection (Best Quality)

**When**: Building core evaluation set
**Method**: LLM evaluates all candidates

```python
queries = extract_with_llm_selection(log_file, target_count=30)
```

**Pros**: Highest quality, detects user satisfaction
**Cons**: Slower, API costs (use for final selection only)

### Strategy 4: Tiered Approach (Recommended)

**Combine multiple strategies:**

```python
# 1. Fast filter: 10,000 → 1,000 queries
extractor_fast = SmartLogExtractor(use_llm_evaluation=False, min_score=0.4)
candidates = extractor_fast.extract_and_filter("logs.jsonl")["filtered_queries"]

# 2. Sample diverse: 1,000 → 200 queries
converter = LogToDatasetConverter()
sampled = converter.sample_queries(candidates, n=200, strategy="diverse")

# 3. LLM selection: 200 → 50 best queries
evaluator = ConversationQualityEvaluator(use_llm=True)
scored = [(q, evaluator.evaluate_single_query(q)) for q in sampled]
best = sorted(scored, key=lambda x: x[1].overall_score, reverse=True)[:50]
final_queries = [q for q, s in best]

# 4. Create dataset
converter.create_query_generation_dataset(final_queries)
```

## Customizing Quality Signals

You can customize what makes a "good" example:

```python
from evals.utils.quality_filter import ConversationQualityEvaluator, QualityScore

class CustomQualityEvaluator(ConversationQualityEvaluator):
    def evaluate_single_query(self, query_data):
        # Your custom logic
        score = super().evaluate_single_query(query_data)

        # Add custom signals
        if "premium_user" in query_data.get("metadata", {}):
            score.overall_score *= 1.2  # Boost premium user queries

        if query_data.get("user_feedback") == "helpful":
            score.overall_score = max(score.overall_score, 0.8)

        return score

evaluator = CustomQualityEvaluator(use_llm=True)
```

## Best Practices

### ✅ Do

1. **Start with fast filtering** - Process large logs quickly
2. **Use LLM for final selection** - Select best 20-50 examples
3. **Review quality reports** - Understand what's being filtered
4. **Keep "fair" tier** - Might contain valuable edge cases
5. **Track filter rates** - If <20% pass, adjust thresholds

### ❌ Don't

1. **Don't skip filtering** - Raw logs are noisy
2. **Don't only use LLM** - Too slow/expensive for large datasets
3. **Don't set threshold too high** - You'll filter out good examples
4. **Don't ignore poor examples** - They show failure modes
5. **Don't forget to sample** - Quality + diversity matters

## Quality Signals Reference

### Single Query Signals

| Signal | Good Value | Weight | Description |
|--------|------------|--------|-------------|
| `has_content` | True | High | Query has text |
| `is_reasonable_length` | True | Medium | 5-100 words |
| `successful_action` | True | High | Processed successfully |
| `returned_results` | 1-50 | High | Good result count |
| `reasonable_latency` | <5000ms | Low | Fast response |
| `has_error` | False | High | No errors |

### Conversation Signals

| Signal | Good Value | Weight | Description |
|--------|------------|--------|-------------|
| `is_multi_turn` | True | Medium | Multiple turns |
| `has_successful_query` | True | High | Executed query |
| `context_dependent_turns` | >0 | Medium | Shows engagement |
| `error_rate` | <0.3 | High | <30% errors |
| `has_progression` | True | Medium | Not repetitive |

### LLM Signals (Optional)

| Signal | Range | Description |
|--------|-------|-------------|
| `user_satisfaction` | 0-10 | Detected satisfaction |
| `conversation_success` | 0-10 | Task completion |
| `user_engagement` | 0-10 | Active participation |
| `example_quality` | 0-10 | Training value |

## Troubleshooting

### "Too few queries pass the filter"

**Problem**: Filter rate <20%
**Solutions**:
- Lower `min_score` threshold (try 0.4 instead of 0.6)
- Check quality report for common issues
- Your logs might have quality problems - investigate

### "Filter is too slow"

**Problem**: Processing thousands of queries takes too long
**Solutions**:
- Use `use_llm_evaluation=False` for initial filtering
- Sample before evaluating: Extract → Sample 500 → Filter
- Use tiered approach (fast filter → sample → LLM selection)

### "LLM evaluation is expensive"

**Problem**: API costs adding up
**Solutions**:
- Only use LLM for final selection (20-50 examples)
- Use `gpt-4o-mini` instead of `gpt-4o` (configured by default)
- Pre-filter with heuristics first
- Cache LLM results (implementation TODO)

### "Quality scores don't match my judgment"

**Problem**: System rates examples differently than you
**Solutions**:
- Customize quality signals (see "Customizing" section)
- Review quality reports to understand scoring
- Use manual annotation for final quality check
- Adjust thresholds based on your use case

## Integration with Workflow

### Weekly Update Routine

```bash
#!/bin/bash
# Weekly dataset update with quality filtering

# 1. Extract and filter last week's logs
python -c "
from evals.utils.smart_extraction import SmartLogExtractor
extractor = SmartLogExtractor(use_llm_evaluation=False, min_score=0.5)
result = extractor.extract_and_filter('logs/week.jsonl')
print(f'Filtered: {len(result[\"filtered_queries\"])} queries')
" > /tmp/filter_stats.txt

# 2. Sample diverse examples
python -c "
from evals.utils.log_to_dataset import LogToDatasetConverter
converter = LogToDatasetConverter()
queries = [...] # Load from step 1
sampled = converter.sample_queries(queries, n=30, strategy='diverse')
converter.create_query_generation_dataset(sampled, 'query_generation/week.json')
"

# 3. Manual review
python evals/utils/manual_annotation.py evals/datasets/query_generation/week.json

# 4. Merge into main dataset
python scripts/merge_datasets.py

# 5. Run regression
python evals/run_evals.py --component all
```

## Next Steps

1. **Try it**: Run smart extraction on your logs
2. **Review report**: Understand what's being filtered
3. **Adjust thresholds**: Tune for your use case
4. **Iterate**: Improve custom signals over time

## Resources

- `evals/utils/quality_filter.py` - Quality evaluation module
- `evals/utils/smart_extraction.py` - Integrated extraction with filtering
- `evals/DATASET_GUIDE.md` - General dataset creation guide
