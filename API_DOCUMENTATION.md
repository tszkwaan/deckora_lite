# Presentation Agent API Documentation

## Base URL

After deployment, your service will be available at:
```
https://presentation-agent-XXXXX-uc.a.run.app
```

Replace `XXXXX` with your actual Cloud Run service URL.

---

## Endpoints

### 1. Health Check

**GET** `/health`

Check if the service is running and healthy.

**Response:**
```json
{
  "status": "healthy"
}
```

**Example:**
```bash
curl https://YOUR_SERVICE_URL/health
```

---

### 2. Generate Presentation

**POST** `/generate`

Generate a presentation from a research report.

**Request Body:**
```json
{
  "report_url": "https://arxiv.org/pdf/2511.08597",  // Optional if report_content provided
  "report_content": "...",                            // Optional if report_url provided
  "scenario": "academic_teaching",                    // Required
  "duration": "20 minutes",                          // Required
  "target_audience": "students",                     // Optional
  "custom_instruction": "keep slides clean"          // Optional
}
```

**Required Fields:**
- `scenario`: Presentation scenario
  - Options: `"academic_teaching"`, `"academic_student_presentation"`, `"business_pitch"`, `"technical_demo"`
- `duration`: Presentation duration
  - Format: `"10 minutes"`, `"20 minutes"`, `"1 hour"`, etc.

**Optional Fields:**
- `report_url`: URL to PDF report (e.g., arXiv paper)
- `report_content`: Direct text content of the report
- `target_audience`: Target audience (e.g., `"students"`, `"C-level"`, `"researchers"`)
- `custom_instruction`: Custom instructions for slide generation

**Response (Success):**
```json
{
  "status": "success",
  "outputs": {
    "report_knowledge": { ... },
    "presentation_outline": { ... },
    "slide_and_script": {
      "slide_deck": { ... },
      "presentation_script": { ... }
    },
    "slides_export_result": {
      "status": "success",
      "presentation_id": "...",
      "shareable_url": "https://docs.google.com/presentation/d/.../edit"
    },
    "layout_review": { ... }
  }
}
```

**Response (Error):**
```json
{
  "status": "error",
  "error": "Error message here"
}
```

**Example Request:**
```bash
curl -X POST https://YOUR_SERVICE_URL/generate \
  -H "Content-Type: application/json" \
  -d '{
    "report_url": "https://arxiv.org/pdf/2511.08597",
    "scenario": "academic_teaching",
    "duration": "20 minutes",
    "target_audience": "students",
    "custom_instruction": "keep slides clean, use point form only"
  }'
```

**Example with Python:**
```python
import requests

url = "https://YOUR_SERVICE_URL/generate"
payload = {
    "report_url": "https://arxiv.org/pdf/2511.08597",
    "scenario": "academic_teaching",
    "duration": "20 minutes",
    "target_audience": "students",
    "custom_instruction": "keep slides clean"
}

response = requests.post(url, json=payload)
result = response.json()

if result["status"] == "success":
    shareable_url = result["outputs"]["slides_export_result"]["shareable_url"]
    print(f"Presentation created: {shareable_url}")
else:
    print(f"Error: {result['error']}")
```

---

## Response Time

- **Typical**: 2-5 minutes (depends on report length and complexity)
- **Timeout**: 1 hour (Cloud Run configured with 3600s timeout)
- **Note**: Long-running requests are supported, but consider implementing async processing for production

---

## Error Handling

### Common Error Codes

- **400 Bad Request**: Missing required fields or invalid JSON
- **500 Internal Server Error**: Agent execution failed
- **503 Service Unavailable**: Agent not initialized

### Error Response Format
```json
{
  "status": "error",
  "error": "Detailed error message"
}
```

---

## Rate Limits

Cloud Run default limits:
- **Concurrent requests**: 10 instances max (configurable)
- **Request timeout**: 1 hour
- **Memory**: 2GB per instance
- **CPU**: 2 vCPU per instance

---

## Authentication

Currently, the API is **publicly accessible** (`--allow-unauthenticated`).

For production, consider:
1. Adding API key authentication
2. Using Cloud Run IAM authentication
3. Implementing rate limiting
4. Adding request validation

---

## Example Scenarios

### Academic Teaching Presentation
```json
{
  "report_url": "https://arxiv.org/pdf/2511.08597",
  "scenario": "academic_teaching",
  "duration": "20 minutes",
  "target_audience": "students",
  "custom_instruction": "keep slides clean, use point form only"
}
```

### Business Pitch
```json
{
  "report_url": "https://example.com/business-report.pdf",
  "scenario": "business_pitch",
  "duration": "10 minutes",
  "target_audience": "C-level",
  "custom_instruction": "focus on ROI and business value"
}
```

### Technical Demo
```json
{
  "report_content": "Full report text here...",
  "scenario": "technical_demo",
  "duration": "30 minutes",
  "target_audience": "engineers",
  "custom_instruction": "include implementation details"
}
```

---

## Testing Locally

Before deploying, test the server locally:

```bash
# Set environment variables
export GOOGLE_API_KEY="your-api-key"
export PORT=8080

# Run server
python server.py

# Test health endpoint
curl http://localhost:8080/health

# Test generate endpoint
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "report_url": "https://arxiv.org/pdf/2511.08597",
    "scenario": "academic_teaching",
    "duration": "1 minute"
  }'
```

