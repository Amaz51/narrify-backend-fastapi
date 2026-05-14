# 📄 Test PDF Content Guide

## 🎯 Available Test PDFs

I've created **5 test PDFs** for you with different scenarios:

---

## 1️⃣ **test_short.pdf** (QUICKEST TEST - 30 seconds)

**Best for:** Quick testing, debugging

**Content:**
- 6 sentences
- 2 speakers: Emma, Tom
- 1 narrator
- Simple dialogue

**Expected Output:**
```
Speakers: Narrator, Emma, Tom
Segments: ~6
Duration: ~15 seconds
```

**Dialogue Sample:**
```
Emma: "What is this?"
Tom: "Did you find something?"
Emma: "Yes, look at this old box."
Tom: "It looks ancient!"
```

---

## 2️⃣ **test_harry_potter.pdf** (RECOMMENDED - 1-2 min)

**Best for:** Multi-speaker testing, emotion detection

**Content:**
- ~300 words
- 3 speakers: Harry, Hermione, Ron
- Multiple emotions: neutral, excited, nervous, determined
- Good dialogue patterns

**Expected Output:**
```
Speakers: Narrator, Harry, Hermione, Ron
Segments: ~15-20
Duration: ~60-90 seconds
```

**Dialogue Samples:**
```
Hermione: "Harry, you won't believe what I found!"
Harry: "What is it?"
Hermione: "It's a letter from Dumbledore. He wants to see us immediately!"
Ron: "This is serious, isn't it?"
Harry: "I think so, but we'll face it together, like always."
```

---

## 3️⃣ **test_conversation.pdf** (REALISTIC - 2-3 min)

**Best for:** Natural conversation testing, real-world scenarios

**Content:**
- ~250 words
- 2 speakers: Sarah, Mike
- Coffee shop conversation
- Natural dialogue flow

**Expected Output:**
```
Speakers: Narrator, Sarah, Mike
Segments: ~12-15
Duration: ~50-70 seconds
```

**Dialogue Samples:**
```
Sarah: "Hey Mike! Sorry I'm late."
Mike: "No worries, I just got here myself."
Sarah: "Work has been crazy this month."
Mike: "I'm thinking about moving to New York."
```

---

## 4️⃣ **test_fairy_tale.pdf** (COMPLEX - 3-4 min)

**Best for:** Multiple speakers, emotion variety, storytelling

**Content:**
- ~400 words
- 4 speakers: Alice, Bob, Charlie, Dragon
- Emotions: brave, nervous, sad, happy
- Narrative + dialogue

**Expected Output:**
```
Speakers: Narrator, Alice, Bob, Charlie, Dragon
Segments: ~18-25
Duration: ~90-120 seconds
```

**Dialogue Samples:**
```
Alice: "We must do something."
Bob: "But we're just kids. How can we fight a dragon?"
Charlie: "Maybe we don't need to fight it. Maybe we can talk to it."
Dragon: "Why do you disturb my sleep?"
Alice: "We heard you were scaring the villagers."
Dragon: "I'm not trying to scare anyone. I'm just lonely."
```

---

## 5️⃣ **test_multilingual.pdf** (LANGUAGE TEST - 2 min)

**Best for:** Testing Urdu/English processing, RTL languages

**Content:**
- English section (customer service dialogue)
- Urdu section (ہیلپ لائن متن)
- Tests language detection

**Expected Output:**
```
Speakers: Narrator, Customer, Agent
Languages detected: English, Urdu
Segments: ~8-10
```

**English Sample:**
```
Customer: "I've been waiting for three hours. This is unacceptable!"
Agent: "I sincerely apologize for the inconvenience."
```

**Urdu Sample:**
```
ہماری ہیلپ لائن تمام حکومتی سہولیات فراہم کرنے کے لیے موجود ہے۔
```

---

## 🧪 **Testing Workflow**

### **Test 1: Basic Functionality**
```bash
1. Upload: test_short.pdf
2. Expected: 3 speakers (Narrator, Emma, Tom)
3. Time: ~30 seconds generation
```

### **Test 2: Multi-Speaker Quality**
```bash
1. Upload: test_harry_potter.pdf
2. Expected: 4 speakers with distinct voices
3. Check: Different male voices for Harry/Ron
4. Check: Female voice for Hermione
```

### **Test 3: Emotion Detection**
```bash
1. Upload: test_fairy_tale.pdf
2. Expected: Brave, nervous, sad, happy emotions
3. Check: Dragon sounds different when grumbling vs happy
```

### **Test 4: Urdu Language**
```bash
1. Upload: test_multilingual.pdf
2. Expected: Proper Urdu text (not romanized gibberish)
3. Check: Text reads: "ہماری ہیلپ لائن..." not "hmry hylp..."
```

---

## 📊 **Expected Processing Results**

### **test_short.pdf:**
```json
{
  "speakers_detected": ["Narrator", "Emma", "Tom"],
  "total_segments": 6,
  "genders": {
    "Narrator": "neutral",
    "Emma": "female",
    "Tom": "male"
  }
}
```

### **test_harry_potter.pdf:**
```json
{
  "speakers_detected": ["Narrator", "Harry", "Hermione", "Ron"],
  "total_segments": 18,
  "genders": {
    "Harry": "male",
    "Hermione": "female",
    "Ron": "male",
    "Narrator": "neutral"
  },
  "emotions": ["neutral", "excited", "nervous", "determined"]
}
```

### **test_fairy_tale.pdf:**
```json
{
  "speakers_detected": ["Narrator", "Alice", "Bob", "Charlie", "Dragon"],
  "total_segments": 22,
  "genders": {
    "Alice": "female",
    "Bob": "male",
    "Charlie": "male",
    "Dragon": "male",
    "Narrator": "neutral"
  }
}
```

---

## 🎯 **Quick Test Commands**

### **Upload & Process:**
```bash
# Upload
curl -X POST http://localhost:8001/api/upload \
  -F "file=@test_short.pdf"

# Response: {"file_id": "abc123", ...}

# Process
curl -X POST http://localhost:8001/api/process/v2 \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123", "detect_emotions": true}'
```

### **Expected Response:**
```json
{
  "file_id": "abc123",
  "speakers_detected": ["Narrator", "Emma", "Tom"],
  "total_segments": 6,
  "processing_time": 0.15
}
```

---

## ✅ **Quality Checklist**

After generating audiobook, verify:

- [ ] **Speaker Count:** Correct number detected
- [ ] **Gender Assignment:** Males have male voices, females have female voices
- [ ] **Dialogue Detection:** Quoted text is marked as dialogue
- [ ] **Narration:** Non-dialogue is marked as narration
- [ ] **Audio Quality:** Clear, no distortion
- [ ] **Speaker Distinction:** Can clearly tell speakers apart
- [ ] **Urdu Text:** Displays properly (not romanized)
- [ ] **Duration:** Matches expected (1 word = ~0.3 seconds)

---

## 🎤 **Voice Assignment Examples**

### **Default (Auto-assigned by gender):**
```
Harry → Male Voice 1
Ron → Male Voice 1 (same as Harry - limitation)
Hermione → Female Voice 1
Narrator → Neutral Voice
```

### **Custom (User-specified):**
```json
{
  "voice_assignments": [
    {"speaker_name": "Harry", "voice_id": "male_british_01"},
    {"speaker_name": "Ron", "voice_id": "male_british_02"},
    {"speaker_name": "Hermione", "voice_id": "female_british_01"},
    {"speaker_name": "Narrator", "voice_id": "narrator_deep"}
  ]
}
```

---

## 🌍 **Translation Test**

To test English → Urdu translation:

```json
{
  "file_id": "harry_potter_id",
  "source_language": "english",
  "target_language": "urdu",
  "detect_emotions": true
}
```

**Expected:** 
- English text translated to Urdu
- Audiobook generated in Urdu voices
- Speaker assignments preserved

---

## 💡 **Pro Tips**

1. **Start with test_short.pdf** for quick debugging
2. **Use test_harry_potter.pdf** for demos (most impressive)
3. **Use test_multilingual.pdf** to test Urdu support
4. **Generate same PDF multiple times** to test caching
5. **Try different voice assignments** to showcase flexibility

---

## 📁 **Files Created:**

1. `test_short.pdf` - 1 page, ~100 words
2. `test_harry_potter.pdf` - 1 page, ~300 words
3. `test_conversation.pdf` - 1 page, ~250 words
4. `test_fairy_tale.pdf` - 1 page, ~400 words
5. `test_multilingual.pdf` - 1 page, English + Urdu

**All PDFs are ready to upload and test!** 🎉
