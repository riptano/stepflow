# Production Model Serving with StepFlow

This example demonstrates how StepFlow enables production-ready AI model serving with resource optimization, independent scaling, and robust deployment patterns.

## Architecture Overview

This demo showcases two deployment modes that illustrate StepFlow's production benefits:

### Development Mode (Local)
- **Two approaches**: Direct `run` for fast iteration, `serve`/`submit` for production testing
- **Subprocess-based model servers** with process isolation for debugging
- **Resource sharing** on a single development machine
- **Fast iteration** with immediate code changes

### Production Mode (Containerized Serve/Submit)
- **Containerized StepFlow server** orchestrating distributed model servers
- **Production-ready deployment** with Docker Compose
- **Independent scaling** of runtime and model servers
- **Resource optimization** (CPU for text, GPU for vision, lightweight runtime)
- **High availability** with health checks and service dependencies

## Key Production Benefits

### 1. Resource Optimization
```yaml
# Text models run on CPU-optimized instances
text_models_cluster:
  type: stepflow
  transport: http
  url: "http://text-models:8080"

# Vision models run on GPU-enabled instances
vision_models_cluster:
  type: stepflow
  transport: http
  url: "http://vision-models:8081"
```

**Why this matters in production:**
- **Cost efficiency**: Only pay for GPU resources when processing vision workloads
- **Performance optimization**: Text models get fast CPU instances, vision gets GPU acceleration
- **Resource isolation**: Heavy vision processing doesn't impact text model responsiveness

### 2. Independent Scaling
Each model server can scale based on its specific workload patterns:

```bash
# Scale text processing for high throughput
kubectl scale deployment text-models --replicas=10

# Scale vision processing for GPU-intensive periods
kubectl scale deployment vision-models --replicas=3
```

**Production scenarios:**
- **Text processing**: Linear scaling for high-volume document processing
- **Vision processing**: Burst scaling for image analysis workflows
- **Mixed workloads**: Different scaling policies for different model types

### 3. Deployment Flexibility
```dockerfile
# Text models: CPU-optimized container
FROM python:3.11-slim
# Lightweight, fast startup, cost-effective

# Vision models: GPU-enabled container
FROM nvidia/cuda:11.8-devel-ubuntu20.04
# GPU support, larger memory allocation, specialized hardware
```

**Benefits:**
- **Rolling deployments**: Update text models without affecting vision processing
- **Blue-green deployments**: Switch model versions with zero downtime
- **Canary releases**: Test new models on subset of traffic

### 4. Fault Tolerance and Reliability
- **Process isolation**: Vision model crash doesn't affect text processing
- **Health checks**: Automatic detection and recovery of failed services
- **Circuit breakers**: Prevent cascading failures across model types
- **Graceful degradation**: Continue processing with available models

## Serve/Submit Architecture Benefits

This demo uses StepFlow's `serve` and `submit` commands to demonstrate production-ready deployment patterns:

### Why Serve/Submit vs Direct Run?

**Development Benefits:**
```bash
# Traditional approach - rebuilds and restarts everything
cargo run -- run --flow=workflow.yaml --input=input.json

# Serve/Submit approach - persistent server, fast iteration
stepflow serve --config=config.yml &           # Start once
stepflow submit --flow=workflow.yaml --input=input1.json  # Submit many
stepflow submit --flow=workflow.yaml --input=input2.json
stepflow submit --flow=workflow.yaml --input=input3.json
```

**Production Benefits:**
- **Service separation**: Runtime orchestration separated from workflow execution
- **Persistent resources**: Model servers stay warm between requests
- **Concurrent execution**: Multiple workflows can execute simultaneously  
- **Better monitoring**: Centralized logging and metrics collection
- **Realistic deployment**: Mirrors production container/service architecture

### Architecture Comparison

| Aspect | Direct Run | Serve/Submit |
|--------|------------|--------------|
| **Startup Time** | Full restart per workflow | Fast submission to warm server |
| **Resource Usage** | Cold start overhead | Persistent, warm resources |
| **Debugging** | Mixed logs, harder to isolate | Clean separation of concerns |
| **Production Similarity** | Development-only pattern | Production-ready architecture |
| **Scalability** | Single workflow at a time | Concurrent workflow execution |
| **Monitoring** | Per-execution logging | Centralized server monitoring |

## File Structure

```
examples/production-model-serving/
├── README.md                      # This documentation
├── ai_pipeline_workflow.yaml      # Demo workflow showcasing model routing
├── requirements.txt               # Python dependencies
├── sample_input_*.json            # Example inputs for testing
│
├── text_models_server.py          # Hugging Face text models server
├── vision_models_server.py        # Computer vision models server
│
├── stepflow-config-dev.yml        # Development config (subprocess)
├── stepflow-config-prod.yml       # Production config (HTTP)
│
├── docker-compose.yml             # Container orchestration
├── Dockerfile.stepflow            # StepFlow runtime container
├── Dockerfile.text-models         # Text models container
├── Dockerfile.vision-models       # Vision models container
│
└── scripts/
    ├── run-dev-direct.sh          # Development setup (direct run)
    ├── run-dev.sh                 # Development setup (serve/submit)
    ├── run-prod.sh                # Production setup
    └── test-workflow.sh           # Test all approaches
```

## Quick Start

### Development Mode (Local)

1. **Install dependencies:**
   ```bash
   # Install Python dependencies for the demo
   pip install msgspec

   # Optionally install full ML dependencies (may take longer)
   # pip install -r requirements.txt
   ```

   **Note**: The demo includes mock implementations that work without ML libraries installed. For full functionality with real models, install the complete requirements.

2. **Choose your development approach:**

   **Option A: Direct `run` (Fast Iteration)**
   ```bash
   # Use the direct run script (recommended)
   cd examples/production-model-serving
   ./scripts/run-dev-direct.sh
   
   # Or manually:
   cd stepflow-rs
   cargo run -- run \
     --flow=../examples/production-model-serving/ai_pipeline_workflow.yaml \
     --input=../examples/production-model-serving/sample_input_text.json \
     --config=../examples/production-model-serving/stepflow-config-dev.yml
   ```
   
   **Option B: `serve`/`submit` (Production Testing)**
   ```bash
   # Best for: Testing server behavior, multiple submissions, debugging
   cd examples/production-model-serving
   ./scripts/run-dev.sh
   
   # Or manually:
   # 1. Build and start StepFlow server
   cd stepflow-rs
   cargo build --release
   ./target/release/stepflow serve --port=7837 --config=../examples/production-model-serving/stepflow-config-dev.yml &
   
   # 2. Submit workflow (can repeat multiple times)
   ./target/release/stepflow submit \
     --url=http://localhost:7837/api/v1 \
     --flow=../examples/production-model-serving/ai_pipeline_workflow.yaml \
     --input=../examples/production-model-serving/sample_input_text.json
   ```

   **When to use each approach:**
   - **Use `run`**: Workflow development, quick iterations, testing changes
   - **Use `serve`/`submit`**: Testing production patterns, multiple executions, server debugging

### Production Mode (Containerized Serve/Submit)

This demonstrates a complete production-like deployment with containerized services:
- **StepFlow Runtime Server**: Central workflow orchestration
- **Text Models Server**: CPU-optimized text processing microservice  
- **Vision Models Server**: GPU-enabled computer vision microservice
- **Monitoring**: Prometheus metrics collection and Redis caching

1. **Start all production services:**
   ```bash
   # Use the production script (recommended)
   cd examples/production-model-serving
   ./scripts/run-prod.sh
   
   # Or manually:
   docker-compose up -d --build
   ```

2. **Services will start in dependency order:**
   ```
   1. Redis Cache & Prometheus (monitoring)
   2. Text Models Server (CPU-optimized)
   3. Vision Models Server (GPU-enabled) 
   4. StepFlow Runtime Server (orchestration)
   ```

3. **Submit workflows to the production server:**
   ```bash
   # After services are healthy, submit workflows
   cd stepflow-rs
   ./target/release/stepflow submit \
     --url=http://localhost:7837/api/v1 \
     --flow=../examples/production-model-serving/ai_pipeline_workflow.yaml \
     --input=../examples/production-model-serving/sample_input_multimodal.json
   ```

**Production advantages:**
- **Service isolation**: Each component runs in its own container
- **Independent deployment**: Update model servers without affecting runtime
- **Resource allocation**: Dedicated resources per service type
- **Health monitoring**: Automatic health checks and dependency management
- **Scalability**: Each service can be scaled independently


## Model Servers

### Text Models Server (`text_models_server.py`)
Provides text processing capabilities optimized for CPU workloads:

- **Text Generation**: GPT-2 based text completion
- **Sentiment Analysis**: DistilBERT sentiment classification
- **Batch Processing**: Efficient multi-text processing
- **Health Monitoring**: Resource usage and model status

**Components:**
- `models/text/generate_text` - Generate text from prompts
- `models/text/analyze_sentiment` - Analyze text sentiment
- `models/text/batch_process_text` - Process multiple texts efficiently
- `models/text/model_health_check` - Server health and metrics

### Vision Models Server (`vision_models_server.py`)
Provides computer vision capabilities optimized for GPU workloads:

- **Image Classification**: ResNet, Vision Transformer models
- **Batch Image Processing**: Efficient multi-image processing
- **Image Analysis**: Metadata extraction and model recommendations
- **GPU Monitoring**: Memory usage and performance metrics

**Components:**
- `models/vision/classify_image` - Classify images with various models
- `models/vision/batch_classify_images` - Process multiple images
- `models/vision/analyze_image_metrics` - Image property analysis
- `models/vision/vision_health_check` - GPU status and model health

## Workflow Capabilities

The `ai_pipeline_workflow.yaml` demonstrates:

1. **Health Checks**: Verify model server availability before processing
2. **Content Analysis**: Determine optimal processing strategy based on input
3. **Model Selection**: Choose appropriate models based on resource preferences
4. **Multi-modal Processing**: Handle both text and image inputs
5. **Batch Processing**: Demonstrate efficient multi-input processing
6. **Performance Monitoring**: Track processing times and resource usage
7. **Production Insights**: Generate recommendations for optimization

## Sample Inputs

### Text-only Processing (`sample_input_text.json`)
```json
{
  "user_text": "I'm excited about our new AI features!",
  "processing_mode": "accurate",
  "prefer_gpu": false
}
```

### Multi-modal Processing (`sample_input_multimodal.json`)
```json
{
  "user_text": "What do you think about this image?",
  "user_image": "data:image/jpeg;base64,...",
  "processing_mode": "accurate",
  "prefer_gpu": true
}
```

### Batch Processing (`sample_input_batch.json`)
```json
{
  "user_text": "Multiple\\nlines\\nof\\ntext",
  "processing_mode": "batch",
  "batch_size": 8
}
```

## Production Deployment Patterns

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: text-models
spec:
  replicas: 5
  selector:
    matchLabels:
      app: text-models
  template:
    spec:
      containers:
      - name: text-models
        image: company/text-models:v1.0
        resources:
          requests:
            cpu: "1"
            memory: "2Gi"
          limits:
            cpu: "2"
            memory: "4Gi"
```

### AWS ECS/Fargate
```json
{
  "family": "text-models",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [{
    "name": "text-models",
    "image": "company/text-models:v1.0",
    "essential": true,
    "portMappings": [{"containerPort": 8080}]
  }]
}
```

### Google Cloud Run
```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: text-models
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containers:
      - image: gcr.io/company/text-models:v1.0
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
```

## Monitoring and Observability

### Health Check Endpoints
- `GET /health` - Basic service health
- `GET /metrics` - Prometheus metrics
- `GET /models` - Available models status

### Key Metrics to Monitor
- **Request latency**: p50, p95, p99 response times
- **Throughput**: Requests per second by model type
- **Error rates**: 4xx/5xx errors and model failures
- **Resource usage**: CPU, memory, GPU utilization
- **Model performance**: Inference time, queue depth

### Logging Best Practices
```python
logger.info("Processing request", extra={
    "model": model_name,
    "request_id": request_id,
    "user_id": user_id,
    "processing_time_ms": processing_time
})
```

## Security Considerations

### Network Security
- **Service mesh**: Istio/Linkerd for encrypted service-to-service communication
- **Network policies**: Kubernetes NetworkPolicies for traffic isolation
- **API Gateway**: Rate limiting, authentication, and request validation

### Data Security
- **Input sanitization**: Validate and sanitize all user inputs
- **Model security**: Regular security scans of model dependencies
- **Secrets management**: Use Kubernetes secrets or cloud secret managers

## Cost Optimization

### Resource Management
1. **Right-sizing**: Match instance types to workload requirements
2. **Auto-scaling**: Scale down during low-traffic periods
3. **Spot instances**: Use preemptible instances for batch processing
4. **Model caching**: Share downloaded models across instances

### Workload Optimization
1. **Batch processing**: Group similar requests for efficiency
2. **Model selection**: Use smaller models for simple tasks
3. **Caching**: Cache frequently requested results
4. **Request routing**: Route to least-loaded instances

## Next Steps

To adapt this demo for production:

1. **Replace mock implementations** with real model deployments
2. **Implement authentication** and authorization
3. **Add comprehensive monitoring** and alerting
4. **Set up CI/CD pipelines** for model deployments
5. **Configure auto-scaling** policies
6. **Implement circuit breakers** and retry logic
7. **Add integration tests** for all model endpoints
8. **Set up log aggregation** and distributed tracing

This example demonstrates how StepFlow's component architecture enables production-ready AI workflows with enterprise-grade reliability, scalability, and operational excellence.