# TeaAgent Onboarding Guide for ML Researchers

This guide helps ML researchers leverage TeaAgent's parallel experiment capabilities and AI-native workflow for machine learning research and experimentation.

## Overview

TeaAgent is designed for AI-assisted research, with features specifically built for iterative experimentation, hyperparameter optimization, and reproducible workflows. Unlike traditional coding assistants, TeaAgent understands the research cycle: hypothesis → experiment → analysis → iteration.

## Core Research Features

### 1. Parallel Experiment Stack

TeaAgent's parallel experiment capabilities are ideal for ML research:

- **Isolated Branches**: Each experiment runs in its own Git branch
- **Concurrent Execution**: Run multiple experiments simultaneously
- **Quality Matrix**: Automatic evaluation of compilation, tests, and performance
- **Smart Selection**: Choose the best result based on configurable metrics

**Basic Usage:**
```bash
# Test multiple optimization strategies in parallel
teaagent agent run --parallel "adam,sgd,rmsprop" \
  --task "Optimize the neural network training loop"

# Test different hyperparameter configurations
teaagent agent run --parallel "lr-0.001,lr-0.01,lr-0.1" \
  --task "Experiment with learning rates"
```

### 2. Context Management

Research projects accumulate context over time. TeaAgent provides:

- **Context Compaction**: Automatically compress old observations when context fills
- **Semantic Summarization**: Preserves key insights while reducing token usage
- **Memory Integration**: Recall previous experiments and findings

**REPL Commands:**
```bash
teaagent agent chat
# In chat:
/compact  # Show compression metrics
/cost     # Show session cost
```

### 3. Modular Rules

Organize research-specific rules in `.teaagent/rules/`:

- **Path-Aware Injection**: Only load rules relevant to current work
- **Reduced Context**: Lower token costs by avoiding irrelevant rules
- **Domain-Specific Guidelines**: Separate rules for data, models, experiments

**Example Structure:**
```
.teaagent/
  rules/
    data.md        # Data preprocessing rules
    models.md      # Model architecture rules
    experiments.md # Experiment design rules
    papers.md      # Paper writing rules
```

## Research Workflow

### Phase 1: Experiment Design

**Define your hypothesis:**
```bash
teaagent agent chat
> Design an experiment to compare transformer architectures for time series forecasting
```

**Create experiment branches:**
```bash
teaagent agent run --parallel "vanilla,attention-only,hybrid" \
  --task "Implement three transformer variants for time series"
```

### Phase 2: Parallel Execution

**Run experiments concurrently:**
```bash
# Each branch runs independently
teaagent agent run --parallel "variant-a,variant-b,variant-c" \
  --task "Train models with different architectures"
```

**Monitor progress:**
```bash
# Check experiment status
teaagent agent status --show-branches

# View quality matrix
teaagent agent compare --branches "variant-a,variant-b,variant-c"
```

### Phase 3: Analysis

**Select best result:**
```bash
teaagent agent select variant-b --metric "test_accuracy"
```

**Generate analysis report:**
```bash
teaagent agent analyze --branch variant-b --output analysis.md
```

### Phase 4: Iteration

**Refine based on results:**
```bash
teaagent agent run --task "Improve variant-b based on analysis"
```

**Document findings:**
```bash
teaagent agent chat
> Summarize the experiment results and write a methods section
```

## ML-Specific Features

### 1. Data Management

**Data preprocessing rules** (`.teaagent/rules/data.md`):
```markdown
# Data Preprocessing Guidelines

- Always validate data distributions before training
- Use train/validation/test splits with proper randomization
- Document data sources and preprocessing steps
- Check for data leakage between splits
- Handle missing values appropriately for the task
```

**Automated data validation:**
```bash
teaagent agent run --task "Validate the dataset and report statistics"
```

### 2. Model Development

**Model architecture rules** (`.teaagent/rules/models.md`):
```markdown
# Model Architecture Guidelines

- Start with simple baselines before complex models
- Use established architectures when possible
- Document model hyperparameters and configuration
- Implement proper weight initialization
- Add gradient clipping for training stability
```

**Model comparison:**
```bash
teaagent agent run --parallel "baseline,improved,experimental" \
  --task "Compare model architectures on the benchmark"
```

### 3. Experiment Tracking

**Automatic experiment logging:**
```bash
teaagent agent run --task "Train model and log metrics" \
  --log-experiment experiment-001
```

**Reproducibility checks:**
```bash
teaagent audit verify --audit-log experiment-001-audit.jsonl
```

## Best Practices for ML Research

### 1. Reproducibility

**Use version control for everything:**
```bash
# Track code, data, and configurations
git add models/ data/ configs/
git commit -m "Experiment 001: baseline model"

# Create TSB for reproducible skill distribution
teaagent skill build-tsb --skill-path experiment-001-skill
```

**Document hyperparameters:**
```bash
teaagent agent chat
> Document all hyperparameters used in experiment-001 in a config file
```

### 2. Systematic Experimentation

**Use parallel experiments for hyperparameter search:**
```bash
# Grid search over learning rates and batch sizes
teaagent agent run --parallel \
  "lr-0.001-bs-32,lr-0.001-bs-64,lr-0.01-bs-32,lr-0.01-bs-64" \
  --task "Run hyperparameter grid search"
```

**Track experiment lineage:**
```bash
teaagent agent lineage --experiment experiment-001
```

### 3. Collaboration

**Share skills with reproducibility guarantees:**
```bash
# Build and sign skill for sharing
teaagent skill build-tsb --skill-path my-experiment-skill
teaagent skill publish-tsb --tsb-path my-experiment-skill.tsb

# Colleague verifies and installs
teaagent skill verify-tsb my-experiment-skill.tsb --identity "researcher@lab.edu"
teaagent skill install my-experiment-skill.tsb
```

### 4. Documentation

**Automated paper writing:**
```bash
teaagent agent chat
> Write the methods section based on experiment-001 results
> Generate figures from the training logs
> Create a results table comparing all variants
```

**Modular rules for paper writing** (`.teaagent/rules/papers.md`):
```markdown
# Paper Writing Guidelines

- Use LaTeX for mathematical notation
- Include confidence intervals for all results
- Report both mean and standard deviation
- Document statistical significance tests
- Include reproducibility information
```

## Common Research Scenarios

### Scenario 1: Hyperparameter Optimization

**Goal:** Find optimal learning rate and batch size

```bash
# Define search space
teaagent agent run --parallel \
  "lr-0.0001,lr-0.001,lr-0.01,lr-0.1" \
  --task "Test different learning rates"

# Analyze results
teaagent agent compare --metric "validation_loss"

# Refine around best result
teaagent agent run --parallel \
  "lr-0.005,lr-0.0075,lr-0.01" \
  --task "Fine-tune learning rate around best result"
```

### Scenario 2: Architecture Search

**Goal:** Compare different model architectures

```bash
# Implement variants in parallel
teaagent agent run --parallel \
  "transformer,lstm,gru,hybrid" \
  --task "Implement four sequence model architectures"

# Train and evaluate
teaagent agent run --task "Train all variants on the dataset"

# Select best based on multiple metrics
teaagent agent select hybrid --metrics "accuracy,efficiency,memory"
```

### Scenario 3: Ablation Studies

**Goal:** Understand contribution of each component

```bash
# Create ablation variants
teaagent agent run --parallel \
  "full,no-attention,no-positional-encoding,no-layer-norm" \
  --task "Create ablation study variants"

# Compare performance
teaagent agent compare --all-branches --output ablation-results.csv
```

### Scenario 4: Reproducing Published Results

**Goal:** Reproduce a paper's results

```bash
# Install the author's skill
teaagent skill verify-tsb paper-skill.tsb --identity "authors@university.edu"
teaagent skill install paper-skill.tsb

# Run the experiment
teaagent agent run --task "Run the paper's experiment"

# Compare results
teaagent agent compare --baseline paper-results --output reproduction-report.md
```

## Integration with ML Tools

### Jupyter Notebooks

**Convert notebook to TeaAgent skill:**
```bash
teaagent skill convert --notebook experiment.ipynb --output skill-path/
```

**Run skill from notebook:**
```python
from teaagent import SkillRunner

runner = SkillRunner()
result = runner.run("my-experiment-skill")
```

### Weights & Biases

**Log experiments to W&B:**
```bash
teaagent agent run --task "Train model" \
  --wandb-project my-research \
  --wandb-entity my-lab
```

### MLflow

**Track experiments with MLflow:**
```bash
teaagent agent run --task "Train model" \
  --mlflow-tracking-uri mlflow-server \
  --mlflow-experiment my-experiment
```

## Performance Tips

### 1. Context Optimization

**Use modular rules to reduce context:**
```bash
# Only load data rules when working with data
teaagent agent run --task "Preprocess dataset" --rules data.md
```

**Compact context regularly:**
```bash
teaagent agent chat
/compact  # Shows compression metrics
```

### 2. Parallel Execution

**Maximize parallelism for independent experiments:**
```bash
# Run many variants concurrently
teaagent agent run --parallel "variant-1,variant-2,...,variant-10" \
  --task "Run hyperparameter sweep"
```

### 3. Caching

**Cache intermediate results:**
```bash
teaagent agent run --task "Preprocess data" --cache preprocessed-data
teaagent agent run --task "Train model" --use-cache preprocessed-data
```

## Resources

- **Parallel Experiments**: [docs/parallel-experiments.md](parallel-experiments.md)
- **Context Management**: [docs/context-management.md](context-management.md)
- **Modular Rules**: [docs/modular-rules.md](modular-rules.md)
- **Research Examples**: [examples/research/](../examples/research/)

## Support

For research-specific questions:
- GitHub Discussions: [github.com/TeaEntityLab/teaAgent/discussions](https://github.com/TeaEntityLab/teaAgent/discussions)
- Research Email: research@teaagent.dev
- Documentation: [docs.teaagent.dev/research](https://docs.teaagent.dev/research)
