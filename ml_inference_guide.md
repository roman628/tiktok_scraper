# Fine-Tuned Model Inference Guide

## Overview
This document explains how to run your fine-tuned 7B TikTok optimization model for scoring and rewriting content, specifically optimized for batch processing on a single GPU (3090).

---

## System Requirements

### Hardware
- **GPU**: NVIDIA RTX 3090 (24GB VRAM)
- **RAM**: 32GB system RAM recommended
- **Storage**: 30GB for model weights + cache

### VRAM Usage
- **Full Precision (FP16)**: ~14GB VRAM
- **4-bit Quantization**: ~7GB VRAM (recommended for batch processing)
- **8-bit Quantization**: ~10GB VRAM

---

## Batch Processing Setup

### Why Batch Processing?
- Frees GPU between runs for other tasks
- Efficient for scheduled jobs (every 12 hours)
- Processes 300 posts in ~10 minutes total
- No idle GPU memory consumption

### Basic Batch Script

```python
#!/usr/bin/env python3
"""
batch_score_posts.py - Score Reddit posts for TikTok performance
Run every 12 hours via cron or task scheduler
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datetime import datetime
import json
import gc

class TikTokScorer:
    def __init__(self, model_path="./models/tiktok-7b-finetuned"):
        """Initialize model with 4-bit quantization for memory efficiency"""
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load model with quantization
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            load_in_4bit=True,
            device_map="auto",
            torch_dtype=torch.float16
        )
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.tokenizer.pad_token = self.tokenizer.eos_token
        
    def score_batch(self, posts, batch_size=4):
        """
        Score multiple posts efficiently in batches
        
        Args:
            posts: List of reddit post texts
            batch_size: Number of posts to process simultaneously
        
        Returns:
            List of scoring results
        """
        results = []
        
        for i in range(0, len(posts), batch_size):
            batch = posts[i:i+batch_size]
            
            # Format inputs for the model
            formatted_inputs = [f"<score>{post}</score>" for post in batch]
            
            # Tokenize
            inputs = self.tokenizer(
                formatted_inputs,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048  # Adjust based on your needs
            ).to(self.device)
            
            # Generate predictions
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=150,
                    temperature=0.1,  # Low temperature for consistent scoring
                    do_sample=False,
                    pad_token_id=self.tokenizer.pad_token_id
                )
            
            # Decode outputs
            for output in outputs:
                decoded = self.tokenizer.decode(output, skip_special_tokens=True)
                # Extract just the generated part (after the input)
                result = decoded.split("</score>")[-1].strip()
                results.append(self.parse_score_output(result))
            
            # Clear batch from memory
            del inputs, outputs
            torch.cuda.empty_cache()
            
            print(f"Processed batch {i//batch_size + 1}/{(len(posts)-1)//batch_size + 1}")
        
        return results
    
    def parse_score_output(self, output):
        """Parse the model's structured output into a dictionary"""
        # Model outputs in format: "Score: 0.72, Percentile: 65%, Views: 45K, Issues: slow_hook"
        result = {
            "raw_output": output,
            "score": 0.0,
            "percentile": 0,
            "predicted_views": 0,
            "issues": [],
            "strengths": []
        }
        
        try:
            # Parse structured output (adjust based on your fine-tuning format)
            parts = output.split(",")
            for part in parts:
                if "Score:" in part:
                    result["score"] = float(part.split(":")[-1].strip())
                elif "Percentile:" in part:
                    result["percentile"] = int(part.split(":")[-1].strip().rstrip("%"))
                elif "Views:" in part:
                    views_str = part.split(":")[-1].strip()
                    if "K" in views_str:
                        result["predicted_views"] = int(float(views_str.rstrip("K")) * 1000)
                    elif "M" in views_str:
                        result["predicted_views"] = int(float(views_str.rstrip("M")) * 1000000)
                # Add more parsing as needed
        except Exception as e:
            print(f"Error parsing output: {e}")
        
        return result
    
    def cleanup(self):
        """Free GPU memory"""
        del self.model
        del self.tokenizer
        torch.cuda.empty_cache()
        gc.collect()

def main():
    """Main batch processing function"""
    
    # Load posts from database or file
    with open("reddit_posts_to_score.json", "r") as f:
        posts_data = json.load(f)
    
    posts = [p["text"] for p in posts_data]
    print(f"Loaded {len(posts)} posts to score")
    
    # Initialize scorer
    scorer = TikTokScorer()
    
    # Process in batches
    start_time = datetime.now()
    results = scorer.score_batch(posts, batch_size=4)
    end_time = datetime.now()
    
    print(f"Scoring completed in {(end_time - start_time).seconds} seconds")
    
    # Save results
    output_data = []
    for post, result in zip(posts_data, results):
        output_data.append({
            "post_id": post.get("id"),
            "original_text": post["text"],
            "score": result["score"],
            "percentile": result["percentile"],
            "predicted_views": result["predicted_views"],
            "issues": result["issues"],
            "timestamp": datetime.now().isoformat()
        })
    
    with open(f"scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
        json.dump(output_data, f, indent=2)
    
    # Cleanup GPU memory
    scorer.cleanup()
    print(f"GPU memory freed. Saved results to scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

if __name__ == "__main__":
    main()
```

---

## Scheduling the Batch Job

### Linux/Mac (Cron)
```bash
# Edit crontab
crontab -e

# Add line to run every 12 hours (noon and midnight)
0 0,12 * * * cd /path/to/project && python batch_score_posts.py >> logs/scoring.log 2>&1
```

### Windows (Task Scheduler)
```powershell
# Create scheduled task
schtasks /create /tn "TikTokScoring" /tr "python C:\path\to\batch_score_posts.py" /sc daily /st 00:00 /ri 720
```

### Python Scheduler (Alternative)
```python
import schedule
import time

def run_batch_scoring():
    import subprocess
    subprocess.run(["python", "batch_score_posts.py"])

# Schedule every 12 hours
schedule.every(12).hours.do(run_batch_scoring)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Performance Optimization

### Batch Size Selection
```python
def determine_optimal_batch_size(post_length_avg):
    """
    Dynamically determine batch size based on post length
    
    For 3090 with 24GB VRAM using 4-bit quantization:
    - Short posts (< 200 tokens): batch_size = 8
    - Medium posts (200-500 tokens): batch_size = 4
    - Long posts (> 500 tokens): batch_size = 2
    """
    if post_length_avg < 200:
        return 8
    elif post_length_avg < 500:
        return 4
    else:
        return 2
```

### Memory Management
```python
# Clear cache between batches
torch.cuda.empty_cache()

# Monitor VRAM usage
print(f"VRAM used: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
print(f"VRAM cached: {torch.cuda.memory_reserved() / 1024**3:.2f} GB")
```

---

## Processing Estimates

### Time Estimates (RTX 3090)
- **Model Loading**: 30-45 seconds
- **Per Post (single)**: 2-3 seconds
- **Per Batch (4 posts)**: 5-6 seconds
- **300 Posts Total**: ~10 minutes (including load time)

### Token Throughput
- **4-bit Quantization**: 40-50 tokens/second
- **8-bit Quantization**: 30-40 tokens/second
- **FP16**: 25-35 tokens/second

---

## Input/Output Specifications

### Input Format
```python
# Maximum input length: 2048 tokens (~1500 words)
# Typical Reddit post: 200-500 tokens (~150-400 words)

input_text = """
<score>
[Reddit post text here, can include multiple paragraphs,
maintains original formatting and structure]
</score>
"""
```

### Output Format
```python
# Model generates structured output (150 tokens max)
output = {
    "score": 0.72,  # 0-1 continuous scale
    "percentile": 65,  # Performance percentile
    "predicted_views": 45000,
    "predicted_engagement_rate": 0.08,
    "category": "storytime",
    "issues": ["slow_opening", "weak_hook", "no_cta"],
    "strengths": ["emotional_content", "relatable"],
    "rewrite_suggestions": "Start with the climax, add mystery"
}
```

---

## Alternative Deployment Options

### 1. FastAPI Server (On-Demand)
```python
from fastapi import FastAPI
import uvicorn

app = FastAPI()
scorer = None  # Load on first request

@app.post("/score")
async def score_post(text: str):
    global scorer
    if scorer is None:
        scorer = TikTokScorer()
    return scorer.score_batch([text], batch_size=1)[0]

# Run with: uvicorn api:app --host 0.0.0.0 --port 8000
```

### 2. Queue-Based Processing
```python
import redis
from rq import Queue

# Submit jobs to queue
q = Queue(connection=redis.Redis())
for post in posts:
    q.enqueue(score_single_post, post)
```

### 3. Cloud Deployment (Runpod/Modal)
```python
# modal.com example
import modal

stub = modal.Stub("tiktok-scorer")

@stub.function(gpu="A10", timeout=600)
def score_batch_cloud(posts):
    scorer = TikTokScorer()
    return scorer.score_batch(posts)

# Costs ~$0.001 per post, no idle costs
```

---

## Monitoring & Logging

### Basic Monitoring
```python
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    filename=f'scoring_{datetime.now().strftime("%Y%m%d")}.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Log performance metrics
logging.info(f"Scored {len(posts)} posts in {elapsed_time}s")
logging.info(f"Average time per post: {elapsed_time/len(posts):.2f}s")
logging.info(f"Peak VRAM usage: {peak_vram_gb:.2f}GB")
```

### Performance Tracking
```python
# Track scoring distribution
import numpy as np

scores = [r["score"] for r in results]
print(f"Score distribution:")
print(f"  Mean: {np.mean(scores):.3f}")
print(f"  Std: {np.std(scores):.3f}")
print(f"  Min: {np.min(scores):.3f}")
print(f"  Max: {np.max(scores):.3f}")
print(f"  Viral (>0.9): {sum(s > 0.9 for s in scores)} posts")
print(f"  Failed (<0.1): {sum(s < 0.1 for s in scores)} posts")
```

---

## Troubleshooting

### Common Issues

1. **Out of Memory (OOM)**
   - Reduce batch_size
   - Use more aggressive quantization (4-bit instead of 8-bit)
   - Clear cache more frequently

2. **Slow Processing**
   - Ensure using GPU: `torch.cuda.is_available()`
   - Check for CPU fallback in model loading
   - Reduce max_new_tokens if outputs are simple

3. **Inconsistent Outputs**
   - Set temperature=0 for deterministic results
   - Use do_sample=False
   - Set seed for reproducibility: `torch.manual_seed(42)`

---

## Cost Analysis

### Local GPU (RTX 3090)
- **Power**: ~300W during inference, ~100W idle
- **Processing 300 posts**: ~0.05 kWh
- **Cost**: ~$0.01 per batch (at $0.15/kWh)
- **Wear**: Minimal at 2x daily runs

### Cloud Options Comparison
- **Runpod**: ~$0.30 per batch (10 min @ $1.80/hr for A6000)
- **Modal**: ~$0.25 per batch (pay per second)
- **AWS**: ~$0.50 per batch (g4dn.xlarge)

**Conclusion**: Local processing is 25-50x cheaper for regular scheduled batches

---

## Next Steps

1. **Optimize batch sizes** based on your specific post lengths
2. **Add rewriting functionality** using same batch architecture
3. **Implement result caching** to avoid re-scoring identical posts
4. **Create dashboard** to visualize scoring trends over time
5. **Add A/B testing** to validate model predictions against actual TikTok performance