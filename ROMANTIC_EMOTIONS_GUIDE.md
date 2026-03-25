# 💕 Romantic Content Enhancement Guide

## Overview

Your audiobook processor now has **enhanced emotion support** specifically designed for romantic novels, with **emotion intensity control** to make romantic scenes more emotionally impactful.

---

## 🎭 New Romantic Emotions

### Newly Added Emotions:

| Emotion | Speed | Pitch | Best For |
|---------|-------|-------|----------|
| **romantic** | 0.9x | 1.1x | Tender romantic moments, intimate scenes |
| **passionate** | 1.1x | 1.2x | Love declarations, intense emotions |
| **tender** | 0.85x | 0.95x | Gentle, affectionate dialogue |
| **love** | 0.95x | 1.05x | Expressions of love, warm moments |
| **sensual** | 0.8x | 0.95x | Sensual/intimate scenes |
| **longing** | 0.85x | 0.9x | Missing someone, yearning |

### Enhanced Negative Emotions (for dramatic scenes):

| Emotion | Speed | Pitch | Best For |
|---------|-------|-------|----------|
| **heartbroken** | 0.7x | 0.75x | Character heartbreak, separation scenes |
| **disappointed** | 0.85x | 0.85x | Mild disappointment |

### Tension Emotions:

| Emotion | Speed | Pitch | Best For |
|---------|-------|-------|----------|
| **nervous** | 1.15x | 1.1x | Confession scenes, first meetings |
| **anxious** | 1.2x | 1.15x | Anticipation, worry |

---

## 📊 Emotion Intensity Control

### What is Emotion Intensity?

Emotion intensity is a **multiplier** that amplifies emotional prosody effects:

- **1.0** = Normal emotion (base settings)
- **1.5** = 50% more intense (RECOMMENDED for romance)
- **2.0** = Double intensity (for very dramatic scenes)
- **2.5** = Maximum intensity (use sparingly)

### How It Works

```python
# Example: Passionate emotion with 1.5x intensity
base_prosody = {
    "speed": 1.1,      # 10% faster
    "pitch": 1.2,      # 20% higher pitch
    "energy": 1.35
}

# With 1.5x intensity multiplier:
adjusted_prosody = {
    "speed": 1.0 + ((1.1 - 1.0) * 1.5) = 1.15  # 15% faster
    "pitch": 1.0 + ((1.2 - 1.0) * 1.5) = 1.3   # 30% higher pitch
    "energy": 1.0 + ((1.35 - 1.0) * 1.5) = 1.525
}
```

---

## 🚀 Implementation Details

### Files Modified

1. **`app/services/nlp/emotion_engine.py`**
   - Expanded `EMOTION_PROSODY_MAP` with romantic emotions
   - Added `get_prosody_with_intensity()` method

2. **`app/services/processor.py`**
   - Updated `generate_audiobook()` with `emotion_intensity` parameter
   - Re-enabled emotion prosody with safety clamping (0.7x - 1.3x speed)

### Method: `get_prosody_with_intensity()`

```python
def get_prosody_with_intensity(
    self, 
    emotion: str, 
    intensity: float = 1.0
) -> Dict[str, float]:
    """
    Get prosody settings with intensity multiplier
    
    Args:
        emotion: Emotion label (e.g., "passionate", "tender")
        intensity: Multiplier (1.0 = normal, 1.5 = 50% more intense)
    
    Returns:
        Dict with adjusted pitch, speed, energy
    """
```

---

## 📝 Usage Examples

### Example 1: Simple Romantic Scene

```json
{
  "file_id": "romance_001",
  "base_speed": 1.0,
  "emotion_intensity": 1.5,
  "chapters": [{
    "segments": [
      {
        "speaker": "Narrator",
        "gender": "female",
        "text": "He stepped closer, his eyes searching hers.",
        "emotion": "romantic"
      },
      {
        "speaker": "Hero",
        "gender": "male",
        "text": "I love you. I have since the beginning.",
        "emotion": "passionate"
      },
      {
        "speaker": "Heroine",
        "gender": "female",
        "text": "I love you too.",
        "emotion": "tender"
      }
    ]
  }]
}
```

### Example 2: Emotional Roller Coaster

```json
{
  "file_id": "romance_drama",
  "base_speed": 1.0,
  "emotion_intensity": 2.0,  // More intense
  "chapters": [{
    "segments": [
      {
        "speaker": "Heroine",
        "gender": "female",
        "text": "Where have you been? I've been waiting for you.",
        "emotion": "longing"  // Yearning
      },
      {
        "speaker": "Hero",
        "gender": "male",
        "text": "I can't do this anymore. I'm leaving.",
        "emotion": "angry"  // Conflict
      },
      {
        "speaker": "Heroine",
        "gender": "female",
        "text": "No, please don't go. I can't lose you.",
        "emotion": "heartbroken"  // Maximum sadness
      },
      {
        "speaker": "Narrator",
        "gender": "female",
        "text": "But he came back. He always came back to her.",
        "emotion": "romantic"  // Resolution
      }
    ]
  }]
}
```

---

## 🎯 Recommended Intensity Levels by Genre

### Light Romance
- **Intensity**: 1.0
- **Characteristics**: Subtle emotions, gentle storytelling
- **Example**: Pride and Prejudice-style slow burns

### Moderate Romance (RECOMMENDED)
- **Intensity**: 1.5 (DEFAULT)
- **Characteristics**: Clear emotions without being over-the-top
- **Example**: Contemporary romance, new adult fiction

### Intense Romance
- **Intensity**: 2.0
- **Characteristics**: Strong emotional delivery, dramatic scenes
- **Example**: Paranormal romance, second-chance romance

### Very Intense Romance
- **Intensity**: 2.5
- **Characteristics**: Maximum emotional impact, sparse use
- **Example**: Used for critical emotional moments only

---

## 🎤 Voice + Emotion Combinations

### For Maximum Impact:

```json
{
  "segments": [
    {
      "speaker": "Hero",
      "gender": "male",
      "text": "I've loved you since the moment I saw you.",
      "emotion": "passionate",
      "voice": "male_voice_deep"  // Pair deep voice with passion
    },
    {
      "speaker": "Heroine", 
      "gender": "female",
      "text": "I... I love you too.",
      "emotion": "tender",
      "voice": "female_voice_soft"  // Pair soft voice with tenderness
    }
  ]
}
```

---

## ⚙️ Technical Details

### Safety Clamping

All generated speeds are clamped to safe range:
```python
adjusted_speed = max(0.7, min(1.3, adjusted_speed))
```

- **Minimum**: 0.7x (slowest safe speed)
- **Maximum**: 1.3x (fastest safe speed)

### Default Emotion Intensity

- **Default value**: 1.5
- **Modifiable**: Via `emotion_intensity` parameter
- **Backward compatible**: Works with existing code

---

## 📋 Scene Type → Emotion Mapping

### First Meeting
- **Narrator**: `neutral` or `calm`
- **Characters**: `nervous`, `happy`

### Building Tension
- **Narrator**: `serious`
- **Characters**: `nervous`, `anxious`

### Love Declaration
- **Character**: `passionate`, `nervous`
- **Response**: `tender`, `love`

### Intimate/Sensual Scene
- **All**: `sensual`, `romantic`, `love`

### Heartbreak/Separation
- **Narrator**: `serious`
- **Character**: `heartbroken`, `sad`, `angry`

### Reunion/Happy Ending
- **All**: `excited`, `passionate`, `romantic`

---

## 🧪 Testing Your Romantic Content

### Step 1: Generate with Default Intensity (1.5x)
```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "test_romance",
    "chapters": [...],
    "emotion_intensity": 1.5
  }'
```

### Step 2: Listen and Evaluate
- Do romantic scenes feel emotionally impactful?
- Do tender moments sound soft enough?
- Do passionate declarations have enough energy?

### Step 3: Adjust Intensity if Needed
```bash
# Less intense (more subtle)
"emotion_intensity": 1.0

# More intense (very dramatic)
"emotion_intensity": 2.0
```

---

## 🚫 Troubleshooting

### Problem: Emotions Sound Unnatural
**Solution**: Reduce intensity (use 1.0 instead of 1.5)

### Problem: Romantic Scenes Sound Flat
**Solution**: Increase intensity (use 2.0) OR check emotion mapping

### Problem: Speed Varies Too Much
**Solution**: All speeds are clamped (0.7-1.3x) - adjust base speed instead

### Problem: High Pitch is Unpleasant
**Solution**: Reduce intensity or use different voice

---

## 📚 Complete Emotion List

### Available Emotions:
- `neutral` - No emotion
- `calm` - Peaceful, relaxed
- `serious` - Formal, important
- `happy` - Content, pleased
- `excited` - Very happy, energetic
- `joyful` - Full of joy
- **`romantic`** - Tender, romantic ⭐
- **`passionate`** - Intense, energetic ⭐
- **`tender`** - Soft, affectionate ⭐
- **`love`** - Expression of love ⭐
- **`sensual`** - Intimate, sensual ⭐
- **`longing`** - Yearning, missing ⭐
- `sad` - Unhappy
- **`heartbroken`** - Deeply sad ⭐
- `disappointed` - Let down
- `nervous` - Anxious, worried
- `anxious` - Very worried
- `angry` - Furious
- `fear` - Afraid

⭐ = Specifically useful for romantic content

---

## 🎓 Next Steps

1. **Try the example**: Use `ROMANTIC_CONTENT_EXAMPLE.json` to test
2. **Adjust intensity**: Find the sweet spot for your book style
3. **Mix emotions**: Combine different emotions for dynamic narration
4. **Monitor logs**: Check logs for emotion/prosody details

---

## 📞 Questions?

For more details, see:
- `emotion_engine.py` - Emotion mapping and prosody
- `processor.py` - Audiobook generation logic
- `ROMANTIC_CONTENT_EXAMPLE.json` - Full example request

Happy creating! 💕🎤
