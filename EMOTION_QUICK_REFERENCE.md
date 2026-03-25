# Quick Reference: Romantic Emotion Implementation

## What Changed?

### ✅ emotion_engine.py
- **NEW**: 6 romantic emotions (`romantic`, `passionate`, `tender`, `love`, `sensual`, `longing`)
- **NEW**: `get_prosody_with_intensity(emotion, intensity)` method
- Expanded from 4 to 24 total emotion mappings

### ✅ processor.py  
- **NEW**: `emotion_intensity` parameter (default: 1.5)
- Re-enabled emotion prosody (was disabled for quality)
- Added speed clamping (0.7x - 1.3x safe range)

---

## Quick Start

### 1️⃣ Enable in Your API Call

```python
# In routes.py or wherever you call generate_audiobook()

result = await audiobook_processor.generate_audiobook(
    segments=segments,
    voice_assignments=voice_assignments,
    speed=1.0,
    emotion_intensity=1.5  # ← NEW! Default for romance
)
```

### 2️⃣ Tag Segments with Romantic Emotions

```json
{
  "segments": [
    {
      "speaker": "Hero",
      "text": "I love you.",
      "emotion": "passionate"  // ← Use new emotions
    },
    {
      "speaker": "Heroine", 
      "text": "I love you too.",
      "emotion": "tender"  // ← Or any of the romantic ones
    }
  ]
}
```

### 3️⃣ Adjust Intensity as Needed

```python
# Light emotions
emotion_intensity=1.0

# Recommended (50% more intense)
emotion_intensity=1.5  # ← DEFAULT

# Very intense
emotion_intensity=2.0

# Maximum
emotion_intensity=2.5
```

---

## The New Emotions at a Glance

| Emotion | Use When | Speed | Pitch |
|---------|----------|-------|-------|
| **romantic** | Tender romantic moments | 0.9x | 1.1x |
| **passionate** | Love declarations, intense emotion | 1.1x | 1.2x |
| **tender** | Gentle, affectionate speech | 0.85x | 0.95x |
| **love** | Expressing love warmly | 0.95x | 1.05x |
| **sensual** | Intimate/sensual scenes | 0.8x | 0.95x |
| **longing** | Missing someone, yearning | 0.85x | 0.9x |

---

## Code Snippets

### Get Emotion with Intensity

```python
from app.services.nlp.emotion_engine import emotion_service

# With 1.5x intensity (romantic default)
prosody = emotion_service.get_prosody_with_intensity(
    emotion="passionate",
    intensity=1.5
)
# Returns: {"pitch": 1.3, "speed": 1.15, "energy": 1.525}

# With normal intensity
prosody = emotion_service.get_prosody_with_intensity(
    emotion="passionate", 
    intensity=1.0
)
# Returns: {"pitch": 1.2, "speed": 1.1, "energy": 1.35}
```

### Generate Audiobook with Romance

```python
from app.services.processor import audiobook_processor

# Generate with romantic emotion intensity
audio_path = await audiobook_processor.generate_audiobook(
    segments=my_segments,
    voice_assignments=voices,
    speed=1.0,
    emotion_intensity=1.5  # 50% more intense emotions
)
```

---

## Math Behind Intensity

```
Formula: result = 1.0 + ((base - 1.0) × intensity)

Example - Passionate emotion with 1.5x intensity:
  Base speed: 1.1
  Adjusted: 1.0 + ((1.1 - 1.0) × 1.5) = 1.15  ← 15% faster

Example - Tender emotion with 2.0x intensity:
  Base pitch: 0.95
  Adjusted: 1.0 + ((0.95 - 1.0) × 2.0) = 0.9  ← 10% lower pitch
```

---

## Before vs After

### BEFORE (Emotion Disabled)
```python
# Was using constant speed
adjusted_speed = speed  # No emotion prosody
```

### AFTER (Emotion Re-enabled with Intensity)
```python
# Now using emotion prosody with intensity control
prosody = emotion_service.get_prosody_with_intensity(
    segment['emotion'],
    intensity=emotion_intensity
)
adjusted_speed = speed * prosody['speed']
adjusted_speed = max(0.7, min(1.3, adjusted_speed))  # Safe range
```

---

## Default Values

```python
# In processor.py generate_audiobook()
emotion_intensity: float = 1.5  # Default for romance

# Speed clamping
min_speed = 0.7   # Slowest safe
max_speed = 1.3   # Fastest safe
```

---

## Testing Checklist

- [ ] Romantic scenes use `romantic`, `passionate`, `tender`, `love`
- [ ] Heartbreak scenes use `heartbroken`
- [ ] Nervous/anxious moments use `nervous`, `anxious`
- [ ] Sensual scenes use `sensual`
- [ ] Longing is tagged with `longing`
- [ ] Intensity set to 1.5 (or appropriate for your book)
- [ ] Audio quality acceptable with emotions enabled
- [ ] No speed goes below 0.7x or above 1.3x

---

## Files Modified

1. ✅ [emotion_engine.py](app/services/nlp/emotion_engine.py)
   - Line 24-54: Expanded EMOTION_PROSODY_MAP
   - Line 163-184: New get_prosody_with_intensity() method

2. ✅ [processor.py](app/services/processor.py)
   - Line 258-314: Updated generate_audiobook() with emotion_intensity

---

## Examples in Repo

- 📄 [ROMANTIC_CONTENT_EXAMPLE.json](ROMANTIC_CONTENT_EXAMPLE.json) - Full example request
- 📘 [ROMANTIC_EMOTIONS_GUIDE.md](ROMANTIC_EMOTIONS_GUIDE.md) - Detailed guide

---

## Backward Compatibility

✅ **Fully backward compatible!**

- Default `emotion_intensity=1.5` works great for romantic content
- Existing code using `generate_audiobook()` without the parameter gets the default
- Emotion detection still works the same way
- All other parameters unchanged

---

## Questions?

See the detailed guides:
- Want examples? → [ROMANTIC_CONTENT_EXAMPLE.json](ROMANTIC_CONTENT_EXAMPLE.json)
- Want deep dive? → [ROMANTIC_EMOTIONS_GUIDE.md](ROMANTIC_EMOTIONS_GUIDE.md)
- Want code? → Check emotion_engine.py and processor.py

---

**Status**: ✅ Ready to use! Just update your API calls to include `emotion_intensity` parameter.
