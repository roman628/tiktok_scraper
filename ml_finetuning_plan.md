# TikTok Content Optimization Model - Fine-Tuning Plan

## Executive Summary

This document outlines a comprehensive plan for fine-tuning a 7B parameter language model to:
1. **Score Reddit posts** based on predicted TikTok performance
2. **Rewrite/optimize content** for the TikTok algorithm

The model will learn from ~9,133 categorized TikTok videos with transcripts, engagement metrics, and 1,861 content categories, discovering algorithmic patterns rather than using hard-coded rules.

---

## 1. Database Assets & Preparation

### 1.1 Available Data
- **Database Size**: 52 MB total (very manageable for cloud transfer)
- **2,558 transcripts** with average length ~3,500 characters
- **1,861 content categories** with confidence scores
- **Engagement metrics**: views, likes, comments, shares, reposts, saves
- **Temporal data**: upload timestamps, processing dates
- **Content features**: transcripts, hashtags, titles, descriptions
- **Medallion architecture** with Bronze/Silver/Gold layers for ML-ready features

### 1.1.1 Actual Data Sizes
- **Full database**: 52 MB
- **Transcriptions table**: 6.4 MB
- **Videos table**: 6.3 MB
- **ML features table**: 1.3 MB
- **Expected training data export**: ~15-20 MB (CSV) or ~5-10 MB (compressed)

### 1.2 Data Enhancement Requirements

#### 1.2.1 Temporal Metrics Collection
```sql
-- Create table for tracking metric evolution
CREATE TABLE IF NOT EXISTS metric_snapshots (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id),
    snapshot_hour INTEGER, -- 1, 6, 12, 24, 48, 168 hours
    view_count BIGINT,
    like_count BIGINT,
    comment_count BIGINT,
    share_count BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient queries
CREATE INDEX idx_snapshots_video_hour ON metric_snapshots(video_id, snapshot_hour);
```

#### 1.2.2 Performance Distribution Calculation
```sql
-- Create materialized view for performance percentiles
CREATE MATERIALIZED VIEW performance_distributions AS
WITH metric_percentiles AS (
    SELECT 
        video_id,
        -- Global percentiles
        PERCENT_RANK() OVER (ORDER BY view_count) as view_percentile,
        PERCENT_RANK() OVER (ORDER BY engagement_rate) as engagement_percentile,
        PERCENT_RANK() OVER (ORDER BY virality_score) as virality_percentile,
        
        -- Category-specific percentiles
        PERCENT_RANK() OVER (
            PARTITION BY category_id 
            ORDER BY view_count
        ) as category_view_percentile
    FROM gold.ml_features f
    JOIN video_categories vc ON vc.video_id = f.video_id
)
SELECT * FROM metric_percentiles;
```

---

## 2. Model Architecture Design

### 2.1 Base Model Selection
- **Primary Choice**: Llama 2 7B or Mistral 7B
- **Fallback**: Smaller models (3B) if compute limited
- **Fine-tuning Method**: QLoRA for efficient training

### 2.2 Multi-Head Architecture

```python
class TikTokOptimizationModel(nn.Module):
    """
    Multi-task model for content scoring and optimization
    """
    def __init__(self, base_model_name="meta-llama/Llama-2-7b"):
        super().__init__()
        
        # Base LLM
        self.base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            load_in_4bit=True,  # QLoRA optimization
            device_map="auto"
        )
        
        # Task-specific heads
        self.scoring_head = ScoringHead(hidden_dim=4096)
        self.category_head = CategoryHead(num_categories=1861)
        self.metric_predictor = MetricPredictor(num_metrics=6)
        self.rewrite_head = RewriteHead(hidden_dim=4096)
        
        # Learnable components
        self.metric_importance_matrix = nn.Parameter(torch.ones(1861, 6))
        self.category_embeddings = nn.Embedding(1861, 768)
        self.temporal_dynamics = TemporalDynamicsModule()
```

### 2.3 Key Components

#### 2.3.1 Algorithm Discovery Module
```python
class AlgorithmDiscoveryModule(nn.Module):
    """
    Learns TikTok's algorithmic patterns from data
    """
    def __init__(self):
        super().__init__()
        # Attention mechanism to discover metric relationships
        self.metric_attention = nn.MultiheadAttention(768, num_heads=8)
        
        # Learns causal relationships between metrics
        self.causal_discovery = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(768, nhead=8),
            num_layers=4
        )
        
        # Category-specific algorithm behavior
        self.category_algorithm_patterns = nn.ModuleDict()
```

#### 2.3.2 Performance Distribution Learner
```python
class DistributionAwareScoring(nn.Module):
    """
    Learns performance distributions rather than fixed thresholds
    """
    def __init__(self):
        super().__init__()
        self.distribution_parameters = nn.ParameterDict({
            'mean': nn.Parameter(torch.tensor(0.0)),
            'std': nn.Parameter(torch.tensor(1.0)),
            'skewness': nn.Parameter(torch.tensor(0.0))
        })
        
    def score_to_percentile(self, raw_score):
        # Map raw scores to distribution percentiles
        z_score = (raw_score - self.distribution_parameters['mean']) / self.distribution_parameters['std']
        percentile = torch.sigmoid(z_score)
        return percentile
```

---

## 3. Training Data Pipeline

### 3.1 Dataset Creation

#### 3.1.1 Scoring Dataset
```python
def create_scoring_dataset():
    """
    Create dataset for learning to score content
    """
    query = """
    WITH scored_content AS (
        SELECT 
            t.whisper_transcription as text,
            v.video_id,
            c.name as category,
            
            -- Continuous performance score (0-1)
            (PERCENT_RANK() OVER (ORDER BY f.view_count) * 0.3 +
             PERCENT_RANK() OVER (ORDER BY f.engagement_rate) * 0.3 +
             PERCENT_RANK() OVER (ORDER BY f.comment_rate) * 0.2 +
             PERCENT_RANK() OVER (ORDER BY f.share_rate) * 0.2) as performance_score,
            
            -- Category-relative performance
            PERCENT_RANK() OVER (
                PARTITION BY c.name 
                ORDER BY f.virality_score
            ) as category_percentile,
            
            -- Individual metrics for multi-task learning
            f.view_count,
            f.like_count,
            f.comment_count,
            f.share_count,
            
            -- Failure indicators
            CASE 
                WHEN f.view_count < 1000 THEN true
                ELSE false
            END as is_failure
            
        FROM transcriptions t
        JOIN videos v ON v.id = t.video_id
        JOIN gold.ml_features f ON f.video_id = v.video_id
        JOIN video_categories vc ON vc.video_id = v.id
        JOIN categories c ON c.id = vc.category_id
        WHERE t.whisper_transcription IS NOT NULL
    )
    SELECT * FROM scored_content
    """
    
    return format_for_training(execute_query(query))
```

#### 3.1.2 Rewrite Dataset
```python
def create_rewrite_dataset():
    """
    Create paired examples for content rewriting
    """
    query = """
    -- Pair low and high performers within same category
    WITH content_pairs AS (
        SELECT 
            low_perf.transcription as source_text,
            high_perf.transcription as target_text,
            low_perf.category,
            high_perf.virality_score - low_perf.virality_score as improvement,
            
            -- Extract patterns
            high_perf.opening_hook,
            high_perf.key_phrases,
            low_perf.weak_points
            
        FROM (
            SELECT * FROM videos WHERE performance_tier = 'low'
        ) low_perf
        JOIN (
            SELECT * FROM videos WHERE performance_tier = 'viral'
        ) high_perf ON low_perf.category_id = high_perf.category_id
        WHERE 
            -- Similar content length for fair comparison
            ABS(LENGTH(low_perf.transcription) - LENGTH(high_perf.transcription)) < 500
    )
    SELECT * FROM content_pairs
    """
    
    return create_instruction_pairs(execute_query(query))
```

### 3.2 Training Data Format

#### 3.2.1 Instruction Format for Scoring
```json
{
    "instruction": "Score this content for TikTok performance in the {category} category",
    "input": "transcript text here...",
    "context": {
        "category": "storytime",
        "expected_metrics": ["comments", "likes"],
        "category_baseline": {
            "median_views": 50000,
            "median_comments": 500
        }
    },
    "output": {
        "performance_score": 0.72,
        "percentile": 0.65,
        "predicted_metrics": {
            "views": 75000,
            "comments": 850,
            "likes": 6000
        },
        "success_factors": ["strong_hook", "emotional_content"],
        "failure_factors": ["slow_middle", "weak_ending"]
    }
}
```

#### 3.2.2 Instruction Format for Rewriting
```json
{
    "instruction": "Rewrite this Reddit post for TikTok virality",
    "input": "long reddit post text...",
    "context": {
        "target_category": "reddit_stories",
        "optimization_goals": ["increase_comments", "improve_retention"],
        "category_patterns": {
            "typical_opening": "POV: You just discovered...",
            "engagement_triggers": ["plot_twist", "cliffhanger"]
        }
    },
    "output": "Optimized TikTok script with hook, pacing, and CTA..."
}
```

### 3.3 Data Balancing Strategy

```python
def balance_training_data(dataset):
    """
    Ensure balanced representation across performance spectrum
    """
    distribution = {
        'viral': [],       # Top 5% (percentile > 0.95)
        'successful': [],  # Top 10-25% (0.75-0.95)
        'moderate': [],    # Middle 50% (0.25-0.75)
        'poor': [],        # Bottom 25% (0.10-0.25)
        'failure': []      # Bottom 10% (< 0.10)
    }
    
    # Critical: Include equal amounts from each tier
    # Traditional: 80% positive, 20% negative
    # Our approach: 20% each tier for better discrimination
    
    max_per_tier = len(dataset) // 5
    
    for tier in distribution:
        distribution[tier] = sample_tier(dataset, tier, max_per_tier)
    
    return flatten(distribution.values())
```

---

## 4. Training Strategy

### 4.1 Multi-Task Learning Objectives

```python
class MultiTaskLoss(nn.Module):
    def __init__(self):
        super().__init__()
        self.task_weights = {
            'scoring': 0.3,
            'metric_prediction': 0.2,
            'category_classification': 0.1,
            'rewriting': 0.3,
            'algorithm_discovery': 0.1
        }
    
    def forward(self, predictions, targets, task_mask):
        total_loss = 0
        
        # Scoring loss with distribution awareness
        if task_mask['scoring']:
            scoring_loss = self.distribution_aware_mse(
                predictions['score'], 
                targets['score']
            )
            total_loss += self.task_weights['scoring'] * scoring_loss
        
        # Metric prediction with category weighting
        if task_mask['metrics']:
            metric_loss = self.category_weighted_loss(
                predictions['metrics'],
                targets['metrics'],
                targets['category']
            )
            total_loss += self.task_weights['metric_prediction'] * metric_loss
        
        # Rewriting loss with BLEU/ROUGE scores
        if task_mask['rewriting']:
            rewrite_loss = self.sequence_loss(
                predictions['rewrite'],
                targets['rewrite']
            )
            total_loss += self.task_weights['rewriting'] * rewrite_loss
        
        return total_loss
```

### 4.2 Training Phases

#### Phase 1: Algorithm Discovery (Weeks 1-2)
- Train model to understand metric relationships
- Learn category-specific patterns
- Discover temporal dynamics

#### Phase 2: Performance Scoring (Weeks 2-3)
- Train on performance prediction
- Learn distribution-based scoring
- Understand success/failure patterns

#### Phase 3: Content Rewriting (Weeks 3-4)
- Train on content optimization
- Learn style transfer
- Incorporate scoring feedback

#### Phase 4: Fine-Tuning & Validation (Week 5)
- Combined training on all tasks
- Hyperparameter optimization
- Validation on held-out data

### 4.3 Training Configuration

```yaml
training_config:
  base_model: "meta-llama/Llama-2-7b"
  method: "qlora"
  
  lora_config:
    r: 64
    lora_alpha: 16
    lora_dropout: 0.1
    target_modules: ["q_proj", "v_proj", "k_proj", "o_proj"]
  
  training_params:
    learning_rate: 2e-4
    batch_size: 8
    gradient_accumulation_steps: 4
    num_epochs: 5
    warmup_steps: 500
    max_grad_norm: 0.3
    
  optimization:
    optimizer: "adamw"
    scheduler: "cosine"
    mixed_precision: "fp16"
```

---

## 5. Evaluation Framework

### 5.1 Scoring Evaluation

```python
def evaluate_scoring_accuracy(model, test_set):
    metrics = {
        'spearman_correlation': None,  # Rank correlation
        'percentile_mae': None,        # Percentile accuracy
        'distribution_match': None,     # KS test for distribution
        'failure_detection_f1': None,   # Identifying bad content
        'top_10_precision': None        # Finding viral content
    }
    
    predictions = model.score_batch(test_set['texts'])
    actual = test_set['scores']
    
    # Correlation with actual performance
    metrics['spearman_correlation'] = spearmanr(predictions, actual)[0]
    
    # Distribution matching
    metrics['distribution_match'] = ks_2samp(predictions, actual).statistic
    
    # Failure detection (bottom 10%)
    failure_threshold = np.percentile(actual, 10)
    predicted_failures = predictions < np.percentile(predictions, 10)
    actual_failures = actual < failure_threshold
    metrics['failure_detection_f1'] = f1_score(actual_failures, predicted_failures)
    
    return metrics
```

### 5.2 Rewriting Evaluation

```python
def evaluate_rewriting_quality(model, test_pairs):
    metrics = {
        'performance_improvement': None,  # Score increase
        'style_transfer_success': None,   # TikTok style adoption
        'content_preservation': None,     # Semantic similarity
        'engagement_prediction': None     # Predicted metric improvement
    }
    
    for source, target in test_pairs:
        rewritten = model.rewrite(source)
        
        # Score improvement
        original_score = model.score(source)
        rewritten_score = model.score(rewritten)
        metrics['performance_improvement'].append(rewritten_score - original_score)
        
        # Style metrics
        tiktok_style_score = evaluate_tiktok_style(rewritten)
        metrics['style_transfer_success'].append(tiktok_style_score)
        
        # Content preservation
        semantic_sim = cosine_similarity(embed(source), embed(rewritten))
        metrics['content_preservation'].append(semantic_sim)
    
    return aggregate_metrics(metrics)
```

### 5.3 A/B Testing Framework

```python
def ab_test_predictions():
    """
    Test model predictions against actual TikTok performance
    """
    test_cases = {
        'hook_variations': [
            "So basically what happened was...",  # Weak
            "You'll NEVER believe what just happened...",  # Strong
        ],
        'pacing_variations': [
            "Long introduction with context and background...",  # Slow
            "BOOM! Right into the action...",  # Fast
        ],
        'category_specific': {
            'storytime': "Storytime: The day everything changed...",
            'tutorial': "Step 1: Here's exactly how to...",
            'comedy': "POV: When your mom finds out..."
        }
    }
    
    results = {}
    for variation_type, variations in test_cases.items():
        scores = model.score_batch(variations)
        results[variation_type] = {
            'scores': scores,
            'ranking': np.argsort(scores)[::-1],
            'spread': np.std(scores)
        }
    
    return results
```

---

## 6. Implementation Timeline

### Week 1: Data Preparation
- [ ] Export training data from PostgreSQL
- [ ] Create temporal metrics collection system
- [ ] Generate performance distributions
- [ ] Create balanced datasets

### Week 2: Model Setup
- [ ] Set up QLoRA training environment
- [ ] Implement multi-task architecture
- [ ] Create data loaders
- [ ] Initialize evaluation metrics

### Week 3: Initial Training
- [ ] Train algorithm discovery module
- [ ] Train scoring head
- [ ] Validate on held-out data
- [ ] Analyze learned patterns

### Week 4: Advanced Training
- [ ] Train rewriting module
- [ ] Implement category-specific learning
- [ ] Fine-tune all components together
- [ ] Cross-validation

### Week 5: Evaluation & Optimization
- [ ] Comprehensive evaluation
- [ ] Hyperparameter tuning
- [ ] A/B testing
- [ ] Documentation

### Week 6: Deployment Preparation
- [ ] Model optimization (quantization)
- [ ] API development
- [ ] Integration testing
- [ ] Production deployment

---

## 7. Success Metrics

### 7.1 Primary Metrics
- **Scoring Accuracy**: Spearman correlation > 0.7 with actual performance
- **Failure Detection**: F1 score > 0.8 for identifying poor content
- **Rewrite Performance**: 50%+ improvement in predicted scores

### 7.2 Secondary Metrics
- **Category Understanding**: 85%+ accuracy in category-specific predictions
- **Distribution Matching**: KS statistic < 0.1 for score distributions
- **Inference Speed**: < 500ms per scoring request

---

## 8. Risk Mitigation

### 8.1 Data Risks
- **Temporal Drift**: Regular retraining on new data
- **Category Imbalance**: Weighted sampling and augmentation
- **Missing Metrics**: Imputation strategies for incomplete data

### 8.2 Model Risks
- **Overfitting**: Dropout, early stopping, validation monitoring
- **Catastrophic Forgetting**: Gradual unfreezing, replay buffers
- **Hallucination**: Constrained generation, fact checking

### 8.3 Deployment Risks
- **Scalability**: Model quantization, caching strategies
- **Monitoring**: Real-time performance tracking
- **Fallback**: Ensemble with simpler models

---

## 9. Future Enhancements

### 9.1 Short Term (1-3 months)
- Incorporate visual features (thumbnails, first frames)
- Add audio analysis (music, voice patterns)
- Real-time trend adaptation

### 9.2 Medium Term (3-6 months)
- Multi-platform optimization (YouTube Shorts, Instagram Reels)
- Personalized scoring based on creator history
- Automated A/B testing system

### 9.3 Long Term (6-12 months)
- Full video generation from text
- Cross-platform content adaptation
- Trend prediction and early detection

---

## 10. Code Repository Structure

```
ml_finetuning/
├── data/
│   ├── extractors/           # SQL to training data
│   ├── processors/           # Data cleaning and balancing
│   └── loaders/             # PyTorch data loaders
├── models/
│   ├── architecture/        # Model definitions
│   ├── heads/              # Task-specific heads
│   └── losses/             # Custom loss functions
├── training/
│   ├── trainers/           # Training loops
│   ├── schedulers/         # Learning rate schedules
│   └── callbacks/          # Training callbacks
├── evaluation/
│   ├── metrics/            # Evaluation metrics
│   ├── validators/         # Validation logic
│   └── visualizers/        # Result visualization
├── deployment/
│   ├── api/               # Serving API
│   ├── optimization/      # Model optimization
│   └── monitoring/        # Production monitoring
└── notebooks/
    ├── exploration/       # Data exploration
    ├── experiments/       # Training experiments
    └── analysis/         # Result analysis
```

---

## Appendix A: SQL Queries for Data Extraction

```sql
-- Complete training data extraction
WITH training_data AS (
    SELECT 
        v.video_id,
        t.whisper_transcription,
        c.name as category,
        vc.confidence_score as category_confidence,
        f.*,  -- All ML features
        
        -- Performance calculations
        PERCENT_RANK() OVER (ORDER BY f.view_count) as global_percentile,
        PERCENT_RANK() OVER (PARTITION BY c.id ORDER BY f.view_count) as category_percentile,
        
        -- Temporal features if available
        EXTRACT(hour FROM v.upload_date) as upload_hour,
        EXTRACT(dow FROM v.upload_date) as upload_dow,
        
        -- Text features
        LENGTH(t.whisper_transcription) as text_length,
        array_length(string_to_array(t.whisper_transcription, ' '), 1) as word_count
        
    FROM videos v
    JOIN transcriptions t ON t.video_id = v.id
    JOIN video_categories vc ON vc.video_id = v.id
    JOIN categories c ON c.id = vc.category_id
    JOIN gold.ml_features f ON f.video_id = v.video_id
    WHERE 
        t.whisper_transcription IS NOT NULL
        AND LENGTH(t.whisper_transcription) > 10
        AND vc.confidence_score > 0.5
)
SELECT * FROM training_data;
```

---

## Appendix B: Training Script Example

```python
import torch
from transformers import AutoModelForCausalLM, TrainingArguments
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
import wandb

def main():
    # Initialize wandb for tracking
    wandb.init(project="tiktok-optimization", name="7b-finetuning")
    
    # Load base model with QLoRA
    model = AutoModelForCausalLM.from_pretrained(
        "meta-llama/Llama-2-7b",
        load_in_4bit=True,
        torch_dtype=torch.float16,
        device_map="auto"
    )
    
    # Configure LoRA
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=64,
        lora_alpha=16,
        lora_dropout=0.1,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]
    )
    
    model = get_peft_model(model, peft_config)
    
    # Load datasets
    train_dataset = load_training_data()
    eval_dataset = load_eval_data()
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir="./models/tiktok-7b",
        num_train_epochs=5,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_steps=500,
        logging_steps=10,
        save_strategy="epoch",
        evaluation_strategy="epoch",
        fp16=True,
        optim="adamw_torch",
        learning_rate=2e-4,
        report_to="wandb"
    )
    
    # Initialize trainer
    trainer = TikTokTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        compute_metrics=compute_metrics
    )
    
    # Train
    trainer.train()
    
    # Save model
    trainer.save_model("./models/tiktok-7b-final")

if __name__ == "__main__":
    main()
```

---

## Appendix C: Google Cloud Deployment with Docker

### C.1 Data Export Script (Run Locally)

```bash
#!/bin/bash
# export_training_data.sh - Run on local machine

# Export training data as CSV
psql -U ethan -d tiktok_scraper << EOF
\COPY (
    SELECT 
        t.video_id,
        t.whisper_transcription as text,
        v.title,
        v.description,
        v.view_count,
        v.like_count,
        v.comment_count,
        v.share_count,
        v.engagement_rate,
        v.virality_score,
        c.name as category,
        vc.confidence_score as category_confidence,
        PERCENT_RANK() OVER (ORDER BY v.view_count) as global_percentile,
        PERCENT_RANK() OVER (PARTITION BY c.id ORDER BY v.view_count) as category_percentile
    FROM transcriptions t
    JOIN videos v ON v.id = t.video_id
    LEFT JOIN gold.ml_features f ON f.video_id = v.video_id
    LEFT JOIN video_categories vc ON vc.video_id = v.id
    LEFT JOIN categories c ON c.id = vc.category_id
    WHERE t.whisper_transcription IS NOT NULL
) TO '/tmp/training_data.csv' WITH CSV HEADER;
EOF

# Compress the data (reduces ~20MB to ~5MB)
gzip -9 /tmp/training_data.csv

# Also export categories for reference
psql -U ethan -d tiktok_scraper -c "\COPY categories TO '/tmp/categories.csv' WITH CSV HEADER"

echo "Training data exported: /tmp/training_data.csv.gz"
echo "Categories exported: /tmp/categories.csv"
```

### C.2 Complete Dockerfile for Training

```dockerfile
# Dockerfile for Google Cloud training
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TORCH_CUDA_ARCH_LIST="6.0 6.1 7.0 7.5 8.0 8.6 8.9 9.0"
ENV WANDB_MODE=offline

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --upgrade pip

# Install PyTorch with CUDA support
RUN pip3 install torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cu118

# Install training dependencies
RUN pip3 install \
    transformers==4.36.0 \
    datasets==2.14.0 \
    accelerate==0.25.0 \
    peft==0.7.0 \
    bitsandbytes==0.41.0 \
    wandb \
    scikit-learn \
    pandas \
    numpy \
    tqdm \
    sentencepiece \
    protobuf

# Create working directory
WORKDIR /workspace

# Copy training data (small, only ~20MB)
COPY training_data.csv.gz /workspace/data/
COPY categories.csv /workspace/data/

# Copy training scripts
COPY train.py /workspace/
COPY config.yaml /workspace/
COPY utils/ /workspace/utils/

# Decompress training data
RUN gunzip /workspace/data/training_data.csv.gz

# Create model cache directory
RUN mkdir -p /workspace/models

# Default command
CMD ["python3", "train.py", "--config", "config.yaml"]
```

### C.3 Training Script (train.py)

```python
#!/usr/bin/env python3
"""
train.py - Fine-tune 7B model for TikTok content optimization
"""

import os
import torch
import pandas as pd
import json
from datetime import datetime
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset, DatasetDict
from sklearn.model_selection import train_test_split
import wandb

class TikTokDataProcessor:
    def __init__(self, data_path="data/training_data.csv"):
        """Load and process training data"""
        self.df = pd.read_csv(data_path)
        print(f"Loaded {len(self.df)} training examples")
        
    def create_instruction_dataset(self):
        """Convert to instruction-following format"""
        instructions = []
        
        for _, row in self.df.iterrows():
            # Scoring instruction
            score_instruction = {
                "instruction": f"Score this TikTok transcript for virality in the {row['category']} category:",
                "input": row['text'][:2000],  # Truncate long texts
                "output": json.dumps({
                    "score": float(row['global_percentile']),
                    "category_score": float(row['category_percentile']),
                    "predicted_views": int(row['view_count']),
                    "engagement_rate": float(row['engagement_rate']) if pd.notna(row['engagement_rate']) else 0.0
                })
            }
            instructions.append(score_instruction)
            
        return instructions
    
    def prepare_datasets(self, test_size=0.1):
        """Split into train/validation sets"""
        instructions = self.create_instruction_dataset()
        
        train_data, val_data = train_test_split(
            instructions,
            test_size=test_size,
            random_state=42
        )
        
        train_dataset = Dataset.from_list(train_data)
        val_dataset = Dataset.from_list(val_data)
        
        return DatasetDict({
            'train': train_dataset,
            'validation': val_dataset
        })

class TikTokTrainer:
    def __init__(self, model_name="meta-llama/Llama-2-7b-hf", use_quantization=True):
        """Initialize model and tokenizer"""
        self.model_name = model_name
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Load model with quantization for memory efficiency
        if use_quantization:
            from transformers import BitsAndBytesConfig
            
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.bfloat16
            )
            
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="auto",
                torch_dtype=torch.float16
            )
        
        # Configure LoRA
        peft_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=64,
            lora_alpha=16,
            lora_dropout=0.1,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            bias="none"
        )
        
        self.model = get_peft_model(self.model, peft_config)
        self.model.print_trainable_parameters()
    
    def preprocess_function(self, examples):
        """Tokenize the examples"""
        # Format as instruction-following
        texts = []
        for i in range(len(examples['instruction'])):
            text = f"### Instruction:\n{examples['instruction'][i]}\n\n"
            text += f"### Input:\n{examples['input'][i]}\n\n"
            text += f"### Response:\n{examples['output'][i]}"
            texts.append(text)
        
        model_inputs = self.tokenizer(
            texts,
            max_length=2048,
            truncation=True,
            padding=True
        )
        
        return model_inputs
    
    def train(self, train_dataset, val_dataset, output_dir="./models/tiktok-7b"):
        """Run training"""
        
        # Tokenize datasets
        train_dataset = train_dataset.map(self.preprocess_function, batched=True)
        val_dataset = val_dataset.map(self.preprocess_function, batched=True)
        
        # Training arguments optimized for Google Cloud
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=3,
            per_device_train_batch_size=4,
            per_device_eval_batch_size=4,
            gradient_accumulation_steps=4,
            warmup_steps=100,
            learning_rate=2e-4,
            fp16=True,
            logging_steps=10,
            evaluation_strategy="steps",
            eval_steps=50,
            save_strategy="steps",
            save_steps=100,
            save_total_limit=2,
            load_best_model_at_end=True,
            report_to="wandb" if os.getenv("WANDB_API_KEY") else "none",
            optim="adamw_torch",
            gradient_checkpointing=True,
            ddp_find_unused_parameters=False
        )
        
        # Initialize trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            tokenizer=self.tokenizer,
            data_collator=DataCollatorForLanguageModeling(self.tokenizer, mlm=False)
        )
        
        # Train
        print("Starting training...")
        trainer.train()
        
        # Save final model
        print(f"Saving model to {output_dir}")
        trainer.save_model(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        return trainer

def main():
    # Initialize wandb if API key exists
    if os.getenv("WANDB_API_KEY"):
        wandb.init(
            project="tiktok-finetuning",
            name=f"training-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
    
    # Load and process data
    print("Loading training data...")
    processor = TikTokDataProcessor()
    datasets = processor.prepare_datasets()
    
    print(f"Train size: {len(datasets['train'])}")
    print(f"Validation size: {len(datasets['validation'])}")
    
    # Initialize trainer
    print("Initializing model...")
    trainer = TikTokTrainer(use_quantization=True)
    
    # Train
    trainer.train(
        datasets['train'],
        datasets['validation']
    )
    
    print("Training complete!")

if __name__ == "__main__":
    main()
```

### C.4 Google Cloud Setup Instructions

```bash
# 1. Create GCP instance with GPU
gcloud compute instances create tiktok-training \
    --zone=us-central1-a \
    --machine-type=n1-standard-8 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --maintenance-policy=TERMINATE \
    --image-family=deep-learning-vm \
    --image-project=deeplearning-platform-release \
    --boot-disk-size=100GB \
    --preemptible  # 70% cheaper

# 2. Upload files to instance
gcloud compute scp training_data.csv.gz tiktok-training:~/
gcloud compute scp categories.csv tiktok-training:~/
gcloud compute scp Dockerfile tiktok-training:~/
gcloud compute scp train.py tiktok-training:~/

# 3. SSH into instance
gcloud compute ssh tiktok-training

# 4. Build Docker image (on instance)
docker build -t tiktok-trainer .

# 5. Run training in Docker
docker run --gpus all \
    -v $(pwd)/output:/workspace/models \
    -e WANDB_API_KEY=your_key_here \
    tiktok-trainer

# 6. Monitor GPU usage
nvidia-smi -l 1

# 7. After training, download model
gcloud compute scp --recurse tiktok-training:~/output/tiktok-7b ./
```

### C.5 Cost Optimization Tips

1. **Use Preemptible Instances**: 70% cheaper, good for training jobs
2. **Use T4 GPU**: $0.35/hour vs A100 at $2.50/hour
3. **Enable Gradient Checkpointing**: Reduces memory usage by 40%
4. **Use Mixed Precision (fp16)**: 2x faster training
5. **Stop Instance When Done**: Set up auto-shutdown script

### C.6 Estimated Costs with $300 Credits

| GPU Type | Cost/Hour | Training Time | Total Cost | Credits Remaining |
|----------|-----------|---------------|------------|-------------------|
| T4 (preemptible) | $0.11 | 20 hours | $2.20 | $297.80 |
| T4 (regular) | $0.35 | 20 hours | $7.00 | $293.00 |
| V100 (preemptible) | $0.74 | 10 hours | $7.40 | $292.60 |
| A100 40GB (preemptible) | $1.00 | 5 hours | $5.00 | $295.00 |

**Recommendation**: Use T4 preemptible for maximum value - you can run 2,700 hours of training!

### C.7 Alternative: Using Google Colab Pro+

For $50/month, Colab Pro+ provides:
- A100 40GB GPU access
- 24-hour runtime
- Background execution
- Perfect for experimentation before cloud deployment

```python
# Colab setup cell
!pip install transformers peft datasets accelerate bitsandbytes

# Mount Google Drive for data
from google.colab import drive
drive.mount('/content/drive')

# Upload your CSV to Drive and train directly
```

---

This comprehensive plan provides a complete roadmap for fine-tuning a 7B model to understand and optimize content for TikTok, learning patterns directly from your data rather than relying on hard-coded rules.