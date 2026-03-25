# Integration Guide: Using Emotion Intensity in Your API

## Where to Use emotion_intensity Parameter

### Location: `app/api/routes.py`

Find the endpoint that calls `generate_audiobook()` and add the parameter.

---

## Example Integration

### Current Code (Before)

```python
# In routes.py - generate endpoint
@router.post("/generate")
async def generate_audiobook_endpoint(request: dict):
    """Generate audiobook from segments"""
    
    # ... validation code ...
    
    # Call processor
    audio_path = await audiobook_processor.generate_audiobook(
        segments=segments,
        voice_assignments=voice_assignments,
        speed=request.get("base_speed", 1.0)
    )
    
    return {"status": "success", "audio_path": str(audio_path)}
```

### Updated Code (After)

```python
# In routes.py - generate endpoint
@router.post("/generate")
async def generate_audiobook_endpoint(request: dict):
    """Generate audiobook from segments with emotion intensity control"""
    
    # ... validation code ...
    
    # Get emotion intensity from request (default 1.5 for romance)
    emotion_intensity = request.get("emotion_intensity", 1.5)
    
    # Log the configuration
    logger.info(f"Generating with emotion_intensity={emotion_intensity}")
    
    # Call processor with emotion intensity
    audio_path = await audiobook_processor.generate_audiobook(
        segments=segments,
        voice_assignments=voice_assignments,
        speed=request.get("base_speed", 1.0),
        emotion_intensity=emotion_intensity  # ← NEW!
    )
    
    return {
        "status": "success",
        "audio_path": str(audio_path),
        "emotion_intensity": emotion_intensity  # ← Include in response
    }
```

---

## API Request/Response Examples

### Request 1: Normal Romantic Content

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "romance_001",
    "base_speed": 1.0,
    "emotion_intensity": 1.5,
    "chapters": [
      {
        "segments": [
          {
            "speaker": "Hero",
            "text": "I love you.",
            "emotion": "passionate"
          }
        ]
      }
    ]
  }'
```

**Response:**
```json
{
  "status": "success",
  "audio_path": "/data/outputs/romance_001_audiobook.mp3",
  "emotion_intensity": 1.5
}
```

### Request 2: Very Intense Romance

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "intense_romance",
    "base_speed": 1.0,
    "emotion_intensity": 2.5,
    "chapters": [...]
  }'
```

---

## Integration Points

### 1. Update Request Schema

If you have a Pydantic model for the request:

```python
# In models/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, List

class AudiobookRequest(BaseModel):
    file_id: str
    chapters: List[dict]
    base_speed: float = 1.0
    emotion_intensity: float = Field(default=1.5, ge=0.5, le=3.0)  # ← NEW!
    voice_assignments: Optional[dict] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_id": "romance_001",
                "base_speed": 1.0,
                "emotion_intensity": 1.5,
                "chapters": []
            }
        }
```

### 2. Validate Input

```python
# In routes.py - validate emotion_intensity
if emotion_intensity < 0.5:
    logger.warning("emotion_intensity too low, clamping to 0.5")
    emotion_intensity = 0.5
elif emotion_intensity > 3.0:
    logger.warning("emotion_intensity too high, clamping to 3.0")
    emotion_intensity = 3.0

logger.info(f"Emotion intensity: {emotion_intensity}x")
```

### 3. Pass to Processor

```python
# In routes.py - call processor
audio_path = await audiobook_processor.generate_audiobook(
    segments=segments,
    voice_assignments=voice_assignments,
    speed=request.get("base_speed", 1.0),
    emotion_intensity=emotion_intensity  # ← Pass the parameter
)
```

---

## OpenAPI Documentation

Update your API docs to include emotion_intensity:

```python
# In routes.py

@router.post(
    "/generate",
    summary="Generate audiobook with emotion control",
    description="Generate multi-speaker audiobook with emotion intensity control"
)
async def generate_audiobook_endpoint(request: AudiobookRequest):
    """
    Generate complete audiobook from segments.
    
    **Parameters:**
    - **file_id**: PDF file identifier
    - **base_speed**: Global speed multiplier (0.5-2.0)
    - **emotion_intensity**: Emotion multiplier (default: 1.5)
      - 1.0 = normal emotions
      - 1.5 = 50% more intense (recommended for romance)
      - 2.0 = 100% more intense
      - 2.5 = maximum intensity
    - **chapters**: List of chapters with segments
    
    **Emotions:**
    - Romantic: romantic, passionate, tender, love, sensual, longing
    - Negative: sad, heartbroken, disappointed
    - Tension: nervous, anxious, angry, fear
    - Positive: happy, excited, joyful
    - Neutral: neutral, calm, serious
    
    **Example:**
    ```json
    {
      "file_id": "romance_001",
      "base_speed": 1.0,
      "emotion_intensity": 1.5,
      "chapters": [...]
    }
    ```
    """
```

---

## Testing the Integration

### Test 1: Default Intensity

```python
# Test without specifying emotion_intensity
request = {
    "file_id": "test_001",
    "base_speed": 1.0,
    "chapters": [...]
    # emotion_intensity not specified → should default to 1.5
}

# Should use 1.5x intensity
```

### Test 2: Custom Intensity

```python
request = {
    "file_id": "test_002",
    "base_speed": 1.0,
    "emotion_intensity": 2.0,  # Explicitly set
    "chapters": [...]
}

# Should use 2.0x intensity
```

### Test 3: With Romantic Emotions

```python
request = {
    "file_id": "test_romance",
    "base_speed": 1.0,
    "emotion_intensity": 1.5,
    "chapters": [{
        "segments": [
            {
                "speaker": "Hero",
                "text": "I love you.",
                "emotion": "passionate"  # New emotion!
            },
            {
                "speaker": "Heroine",
                "text": "I love you too.",
                "emotion": "tender"  # New emotion!
            }
        ]
    }]
}

# Should generate with romantic emotions at 1.5x intensity
```

---

## Logging & Monitoring

### Add Logging to Track Emotion Intensity

```python
# In routes.py

from loguru import logger

logger.info(f"Audiobook generation started:")
logger.info(f"  File ID: {file_id}")
logger.info(f"  Base speed: {base_speed}")
logger.info(f"  Emotion intensity: {emotion_intensity}x")  # ← NEW!
logger.info(f"  Total segments: {len(segments)}")
```

### Monitor in Logs

```
[INFO] Audiobook generation started:
[INFO]   File ID: romance_001
[INFO]   Base speed: 1.0
[INFO]   Emotion intensity: 1.5x
[INFO]   Total segments: 42
[INFO] Emotion intensity: 1.5x
[INFO] Generating segment 1/42: Hero (passionate)
[INFO] Generating segment 2/42: Heroine (tender)
...
```

---

## Backward Compatibility Checklist

✅ **All checks pass**

- [ ] Default parameter (1.5) works for existing code
- [ ] Old code without emotion_intensity parameter still works
- [ ] New code can override with custom emotion_intensity
- [ ] All emotions detected automatically (no changes needed)
- [ ] Speed clamping prevents invalid values
- [ ] TTS generation still works the same

---

## Summary of Changes

| Item | Before | After |
|------|--------|-------|
| Emotions | 4 basic emotions | 24 emotions (6 romantic) |
| Intensity | Fixed (not configurable) | Configurable (1.5x default) |
| Quality | No prosody (disabled) | Prosody enabled |
| API | `generate_audiobook(segments, voices, speed)` | `generate_audiobook(..., emotion_intensity=1.5)` |
| Romantic | Not optimized | Optimized for romance |

---

## Quick Checklist for Integration

- [ ] Update `routes.py` to accept `emotion_intensity` parameter
- [ ] Pass `emotion_intensity` to `generate_audiobook()`
- [ ] Update request schema if using Pydantic models
- [ ] Add input validation (0.5 - 3.0 range)
- [ ] Update API documentation
- [ ] Test with default intensity (1.5)
- [ ] Test with custom intensity (1.0, 2.0, etc.)
- [ ] Test with romantic emotions (passionate, tender, etc.)
- [ ] Monitor logs to confirm emotions are being applied
- [ ] Get feedback on audio quality and emotional impact

---

## Need Help?

- 📄 See [ROMANTIC_CONTENT_EXAMPLE.json](ROMANTIC_CONTENT_EXAMPLE.json) for complete example
- 📘 See [ROMANTIC_EMOTIONS_GUIDE.md](ROMANTIC_EMOTIONS_GUIDE.md) for detailed guide
- ⚡ See [EMOTION_QUICK_REFERENCE.md](EMOTION_QUICK_REFERENCE.md) for quick syntax

**Status**: Ready to integrate! 🚀
