# Retriever Agent Evaluation Framework

A comprehensive evaluation system for testing the retriever agent across different models, prompt versions, and system configurations.

## Overview

This framework supports:
- **Component-level evaluations**: Test individual parts (query builder, intent classifier, safety guard)
- **System-level evaluations**: Test complete conversation flows end-to-end
- **Prompt versioning**: Compare different prompt iterations
- **Multi-model testing**: Evaluate across different LLM models
- **Metrics tracking**: Accuracy, latency, safety scores, and more

## Structure

```
evals/
├── config.py              # Configuration, prompt versions, model configs
├── datasets/              # Test datasets
│   ├── query_generation/  # Query builder test cases
│   ├── intent_classification/  # Intent classification test cases
│   ├── safety/            # Safety guard test cases
│   └── end_to_end/        # Full conversation scenarios
├── runners/               # Evaluation runners
│   ├── component_eval.py  # Component evaluation logic
│   └── system_eval.py     # System evaluation logic
├── reports/               # Generated evaluation reports (JSON)
├── run_evals.py           # Main CLI runner
└── README.md              # This file
```

## Quick Start

### 1. Run all component evaluations

```bash
python evals/run_evals.py --component all
```

### 2. Run specific component

```bash
# Query builder
python evals/run_evals.py --component query_builder

# Intent classification
python evals/run_evals.py --component intent_classification

# Safety guard
python evals/run_evals.py --component safety_guard
```

### 3. Run system-level (end-to-end) evaluations

```bash
python evals/run_evals.py --system
```

### 4. Compare prompt versions

```bash
# List available prompt versions
python evals/run_evals.py --list-prompts

# Compare all prompt versions for query builder
python evals/run_evals.py --component query_builder --compare-prompts
```

### 5. Test with specific models

```bash
python evals/run_evals.py --component query_builder --models gpt-4o gpt-4o-mini
```

### 6. Test specific prompt versions

```bash
python evals/run_evals.py --component query_builder --prompts v1.0 v1.1
```

## Configuration

### Adding New Models

Edit `evals/config.py`:

```python
EVAL_MODELS = [
    ModelConfig(name="gpt-4o", provider="openai", temperature=0.0),
    ModelConfig(name="gpt-4o-mini", provider="openai", temperature=0.0),
    ModelConfig(name="claude-3-5-sonnet-20241022", provider="anthropic", temperature=0.0),
    # Add your model here
]
```

### Adding Prompt Versions

Edit `evals/config.py`:

```python
QUERY_BUILDER_PROMPTS = {
    "v1.0": PromptVersion(
        version="v1.0",
        name="baseline",
        created_at="2026-01-15",
        description="Original query builder prompt",
        prompt_text="...",
    ),
    "v2.0": PromptVersion(
        version="v2.0",
        name="improved_version",
        created_at="2026-01-22",
        description="Improved with better X",
        prompt_text="...",
    ),
}
```

### Creating Custom Evaluations

Create a new eval config:

```python
from evals.config import EvalConfig, ModelConfig

my_eval = EvalConfig(
    eval_name="my_custom_eval",
    component="query_builder",
    dataset_path="evals/datasets/my_dataset.json",
    models=[ModelConfig(name="gpt-4o", provider="openai", temperature=0.0)],
    prompt_versions=["v1.0", "v2.0"],
    metrics=["accuracy", "latency"],
    output_path="evals/reports/my_eval.json",
)

# Run it
from evals.runners.component_eval import run_component_eval
run_component_eval(my_eval)
```

## Dataset Format

### Query Generation Dataset

```json
{
  "version": "1.0",
  "test_cases": [
    {
      "id": "qg_001",
      "category": "simple_artist_query",
      "user_query": "Find concerts by Radiohead",
      "expected_patterns": ["MATCH.*Artist.*Radiohead"],
      "should_not_contain": ["DELETE", "CREATE"],
      "metadata": {
        "difficulty": "easy"
      }
    }
  ]
}
```

### Intent Classification Dataset

```json
{
  "version": "1.0",
  "test_cases": [
    {
      "id": "ic_001",
      "user_message": "Find jazz concerts in Berlin",
      "expected_action": "QUERY_DB",
      "conversation_history": [],
      "reasoning": "Has specific constraints"
    }
  ]
}
```

### End-to-End Conversation Dataset

```json
{
  "version": "1.0",
  "conversations": [
    {
      "id": "e2e_001",
      "name": "successful_event_search",
      "turns": [
        {
          "user": "I'm looking for concerts in Berlin",
          "expected_action": "QUERY_DB",
          "success_criteria": {
            "generates_query": true,
            "returns_results": true
          }
        }
      ]
    }
  ]
}
```

## Evaluation Reports

Reports are generated as JSON files in `evals/reports/` with the following structure:

```json
{
  "eval_name": "query_builder_comprehensive",
  "component": "query_builder",
  "timestamp": "2026-01-22T10:30:00",
  "summary": {
    "total_tests": 10,
    "passed": 8,
    "failed": 2,
    "accuracy": 0.8,
    "avg_score": 0.85,
    "avg_latency_ms": 450,
    "by_model": {
      "gpt-4o": {
        "accuracy": 0.9,
        "avg_score": 0.92
      }
    },
    "by_prompt_version": {
      "v1.0": {
        "accuracy": 0.7,
        "avg_score": 0.75
      },
      "v1.1": {
        "accuracy": 0.9,
        "avg_score": 0.95
      }
    }
  },
  "results": [...]
}
```

## Metrics

### Component Evaluations

- **Accuracy**: Percentage of tests that pass all criteria
- **Score**: Normalized score (0-1) based on partial criteria matching
- **Latency**: Response time in milliseconds
- **Cypher Validity**: For query builder - checks pattern matching and safety
- **Precision/Recall**: For safety guard and classification tasks

### System Evaluations

- **Conversation Success Rate**: Percentage of complete conversations that succeed
- **Turn Success Rate**: Percentage of individual turns that meet criteria
- **Avg Latency per Turn**: Average response time per conversation turn
- **User Satisfaction Score**: Based on success criteria and quality metrics

## Best Practices

### 1. Iterative Development

When improving prompts:
1. Add new prompt version to `config.py`
2. Run comparison: `python evals/run_evals.py --component X --compare-prompts`
3. Analyze report in `evals/reports/`
4. Iterate based on results

### 2. Multi-Model Testing

Test on cheaper/faster models first (gpt-4o-mini, gpt-3.5-turbo), then validate on production model (gpt-4o).

### 3. Dataset Maintenance

- Start with ~10-20 test cases per component
- Add edge cases as you find issues
- Include both positive and negative examples
- Document expected behavior in test case metadata

### 4. Regression Testing

Run evals regularly:
- Before deploying new prompt versions
- After model upgrades
- When changing system components
- As part of CI/CD pipeline

### 5. Analyzing Results

Focus on:
- Prompt version comparisons: Which version performs best?
- Model comparisons: Cost vs. quality tradeoffs
- Failure patterns: What types of queries fail consistently?
- Latency: Performance bottlenecks

## Extending the Framework

### Adding New Metrics

Create a new metric in `evals/metrics/`:

```python
# evals/metrics/custom_metric.py
def calculate_custom_metric(output, expected):
    # Your metric logic
    return score
```

Use it in evaluators:

```python
from evals.metrics.custom_metric import calculate_custom_metric

score = calculate_custom_metric(cypher, expected_cypher)
```

### Adding New Components

1. Create dataset in `evals/datasets/your_component/`
2. Add eval logic in `component_eval.py` or create new runner
3. Register in `evals/config.py`
4. Run: `python evals/run_evals.py --component your_component`

## Troubleshooting

### "No module named 'config'"

Make sure you're running from the retriever directory:
```bash
cd services/retriever
python evals/run_evals.py ...
```

### "Dataset not found"

Check that dataset paths in `evals/config.py` are correct and files exist.

### API Rate Limits

If hitting rate limits, add delays or run tests sequentially instead of in parallel.

## Future Enhancements

Planned features:
- [ ] Automated A/B testing framework
- [ ] Cost tracking per eval run
- [ ] Integration with W&B or MLflow for experiment tracking
- [ ] Automated report generation with charts
- [ ] CI/CD integration examples
- [ ] Benchmark datasets for common queries
- [ ] Human evaluation interface
- [ ] Continuous eval monitoring in production
