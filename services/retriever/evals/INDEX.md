# Evaluation Framework Documentation Index

Complete evaluation system for the retriever agent with prompt versioning, multi-model testing, quality filtering, and automated dataset creation.

## 📚 Documentation

### Getting Started

1. **[QUICK_START.md](QUICK_START.md)** ⚡ *5 min read*
   - Immediate actionable steps
   - Basic extraction and evaluation
   - Copy-paste examples
   - **Start here if you want to get running quickly**

2. **[README.md](README.md)** 📖 *20 min read*
   - Complete evaluation framework overview
   - All features and capabilities
   - Running evaluations
   - Configuration options

### Dataset Creation

3. **[DATASET_GUIDE.md](DATASET_GUIDE.md)** 📊 *25 min read*
   - Step-by-step dataset creation process
   - Extracting from production logs
   - Manual annotation workflow
   - Real-world examples
   - **Essential for building quality datasets**

4. **[QUALITY_FILTERING_GUIDE.md](QUALITY_FILTERING_GUIDE.md)** 🎯 *20 min read*
   - Automatic quality evaluation
   - Filtering low-quality logs
   - LLM-powered selection
   - Quality signals and scoring
   - **Critical for ensuring dataset quality**

## 🚀 Quick Navigation

### I want to...

**...get started immediately**
→ Read [QUICK_START.md](QUICK_START.md)
→ Run `python evals/demo_extract_from_logs.py`

**...run evaluations**
→ `python evals/run_evals.py --component all`
→ See [README.md](README.md#quick-start)

**...add real user queries to my datasets**
→ Read [DATASET_GUIDE.md](DATASET_GUIDE.md)
→ Run `python evals/demo_extract_from_logs.py`

**...filter logs for quality**
→ Read [QUALITY_FILTERING_GUIDE.md](QUALITY_FILTERING_GUIDE.md)
→ Run `python evals/demo_quality_filtering.py`

**...test different prompts**
→ `python evals/run_evals.py --component query_builder --compare-prompts`
→ See [README.md](README.md#prompt-versioning)

**...test different models**
→ `python evals/run_evals.py --component query_builder --models gpt-4o gpt-4o-mini`
→ See [README.md](README.md#multi-model-testing)

**...see code examples**
→ Run `python evals/example_usage.py <1-8>`
→ Browse `evals/example_usage.py`

## 📁 File Structure

```
evals/
├── README.md                   # Main documentation
├── QUICK_START.md             # 5-minute quick start
├── DATASET_GUIDE.md           # Dataset creation guide
├── QUALITY_FILTERING_GUIDE.md # Quality filtering guide
├── INDEX.md                   # This file
│
├── config.py                  # Prompt versions, model configs
├── run_evals.py              # Main CLI runner
├── example_usage.py          # 8 detailed code examples
│
├── demo_extract_from_logs.py      # Demo: Basic extraction
├── demo_quality_filtering.py      # Demo: Quality filtering
│
├── datasets/                  # Test datasets
│   ├── query_generation/      # Query builder test cases
│   ├── intent_classification/ # Intent classifier test cases
│   ├── safety/               # Safety guard test cases
│   └── end_to_end/           # Full conversation scenarios
│
├── runners/                   # Evaluation runners
│   ├── component_eval.py     # Component evaluation logic
│   └── system_eval.py        # End-to-end evaluation logic
│
├── utils/                     # Utilities
│   ├── log_to_dataset.py     # Log extraction
│   ├── quality_filter.py     # Quality evaluation
│   ├── smart_extraction.py   # Integrated extraction + filtering
│   └── manual_annotation.py  # Interactive annotation tool
│
└── reports/                   # Generated reports (JSON)
```

## 🎯 Common Workflows

### Workflow 1: First-Time Setup

```bash
# 1. Read quick start
cat evals/QUICK_START.md

# 2. Run demos to understand
python evals/demo_extract_from_logs.py
python evals/demo_quality_filtering.py

# 3. Run first evaluation
python evals/run_evals.py --component query_builder
```

### Workflow 2: Adding Production Queries

```bash
# 1. Extract with quality filtering
python -c "
from evals.utils.smart_extraction import SmartLogExtractor
extractor = SmartLogExtractor(use_llm_evaluation=False, min_score=0.5)
extractor.extract_filter_and_create_datasets('logs/production.jsonl', sample_size=50)
"

# 2. Manual annotation
python evals/utils/manual_annotation.py \
    evals/datasets/query_generation/filtered_queries.json \
    --type query_generation

# 3. Run evals with new dataset
python evals/run_evals.py --component query_builder
```

### Workflow 3: Testing New Prompt Version

```bash
# 1. Add prompt version to evals/config.py

# 2. Compare prompts
python evals/run_evals.py --component query_builder --compare-prompts

# 3. Review report
cat evals/reports/query_builder_eval.json

# 4. Deploy if better
```

### Workflow 4: Weekly Dataset Update

```bash
# Monday: Extract last week
python evals/utils/smart_extraction.py logs/week.jsonl --mode fast --sample 30

# Tuesday: Annotate
python evals/utils/manual_annotation.py evals/datasets/query_generation/user_queries.json

# Wednesday: Run regression
python evals/run_evals.py --component all

# Thursday: Review and iterate
```

## 🔑 Key Concepts

### Prompt Versioning

Track and compare different prompt iterations:
- Baseline prompts (v1.0)
- Improved versions (v1.1, v2.0, etc.)
- A/B testing
- Historical tracking

### Quality Filtering

Automatic evaluation of log quality:
- **Heuristic signals**: Fast, free (query length, results, errors)
- **LLM evaluation**: Accurate, slower (user satisfaction, conversation success)
- **Quality tiers**: Excellent/Good/Fair/Poor
- **Filtering strategies**: Fast/Balanced/LLM

### Evaluation Types

- **Component evals**: Test individual parts (query builder, intent classifier, safety)
- **System evals**: Test complete conversation flows end-to-end
- **Regression evals**: Ensure changes don't break existing functionality

### Dataset Quality

Good datasets have:
- ✓ Real user queries from production
- ✓ Diverse examples (different types, complexity)
- ✓ Clear ground truth
- ✓ Quality filtering applied
- ✓ Manual review for accuracy

## 📊 Metrics

### Component Metrics

- **Accuracy**: % of tests passing all criteria
- **Score**: Normalized score (0-1) based on partial matches
- **Latency**: Response time in milliseconds
- **Precision/Recall**: For classification tasks

### System Metrics

- **Conversation Success Rate**: % of conversations completing successfully
- **Turn Success Rate**: % of individual turns meeting criteria
- **Avg Latency per Turn**: Performance metric
- **User Satisfaction**: Based on LLM evaluation

### Quality Metrics

- **Overall Score**: 0.0-1.0 quality assessment
- **Confidence**: How confident the system is
- **Filter Rate**: % of queries passing quality checks
- **Signal Distribution**: Breakdown of quality signals

## 🛠️ Tools Reference

### CLI Tools

```bash
# Run evaluations
python evals/run_evals.py --component <name>

# Extract logs with filtering
python evals/utils/smart_extraction.py <logfile> --mode <fast|balanced|llm>

# Manual annotation
python evals/utils/manual_annotation.py <dataset> --type <query_generation|intent_classification>

# Run examples
python evals/example_usage.py <1-8>

# Run demos
python evals/demo_extract_from_logs.py
python evals/demo_quality_filtering.py
```

### Python API

```python
# Run evaluation
from evals.config import COMPONENT_EVALS
from evals.runners.component_eval import run_component_eval
results = run_component_eval(COMPONENT_EVALS["query_builder"])

# Extract and filter
from evals.utils.smart_extraction import SmartLogExtractor
extractor = SmartLogExtractor(use_llm_evaluation=True)
extractor.extract_filter_and_create_datasets("logs.jsonl")

# Quality evaluation
from evals.utils.quality_filter import ConversationQualityEvaluator
evaluator = ConversationQualityEvaluator(use_llm=True)
score = evaluator.evaluate_single_query(query_data)
```

## 💡 Best Practices

### Dataset Creation

1. Start with 20-30 manually curated examples
2. Add 10-20 filtered production queries weekly
3. Always apply quality filtering
4. Review and annotate before adding
5. Remove duplicates and low-quality cases

### Quality Filtering

1. Use fast heuristics for initial filtering
2. Apply LLM evaluation for final selection
3. Set reasonable thresholds (0.5-0.6)
4. Review quality reports regularly
5. Track filter rates over time

### Evaluation Workflow

1. Run component evals first (faster)
2. Run system evals for critical changes
3. Compare prompt versions before deploying
4. Test on cheaper models first
5. Keep eval datasets lean and focused

## 📈 Success Metrics

Track these over time:

- **Dataset size**: 50-200 test cases per component
- **Filter rate**: 30-50% of logs passing quality checks
- **Eval accuracy**: 80%+ passing rate
- **Coverage**: All major query types represented
- **Update frequency**: Weekly or bi-weekly additions

## 🆘 Troubleshooting

### Common Issues

**"No queries extracted"**
→ Check log file path and format
→ Verify log structure matches expected format

**"Too few queries pass filter"**
→ Lower min_score threshold
→ Review quality report for issues
→ Check if logs have quality problems

**"Evaluations are too slow"**
→ Use smaller datasets (50-100 cases)
→ Run component evals instead of system evals
→ Disable LLM evaluation for speed

**"LLM costs adding up"**
→ Use LLM only for final selection
→ Pre-filter with heuristics
→ Use gpt-4o-mini instead of gpt-4o

## 📞 Support

- **Issues**: GitHub repository issues
- **Questions**: See documentation files
- **Examples**: Run demo scripts
- **Code**: Browse `evals/example_usage.py`

## 🗺️ Reading Order

**For complete understanding, read in this order:**

1. **QUICK_START.md** - Get running (5 min)
2. **README.md** - Understand framework (20 min)
3. **DATASET_GUIDE.md** - Learn dataset creation (25 min)
4. **QUALITY_FILTERING_GUIDE.md** - Master quality filtering (20 min)
5. **example_usage.py** - See code patterns (15 min)

**Total**: ~85 minutes to master the evaluation framework

---

**Ready to start?** → Begin with [QUICK_START.md](QUICK_START.md)
