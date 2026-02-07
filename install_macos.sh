#!/bin/bash

# ==============================================================================
# Narrify Phase 2 - macOS ARM Installation Script
# Fixes numpy dependency conflicts between TTS and librosa
# ==============================================================================

set -e  # Exit on error

echo "🚀 Narrify Phase 2 - macOS ARM Installation"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Check Python version
echo -e "${BLUE}Step 1/8: Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

if [[ $(echo "$python_version" | cut -d. -f1) -lt 3 ]] || [[ $(echo "$python_version" | cut -d. -f2) -lt 10 ]]; then
    echo -e "${RED}❌ Python 3.10+ required (you have $python_version)${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python version OK${NC}"
echo ""

# 2. Check if virtual environment is activated
echo -e "${BLUE}Step 2/8: Checking virtual environment...${NC}"
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
    echo "Creating and activating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${GREEN}✅ Virtual environment activated${NC}"
else
    echo -e "${GREEN}✅ Virtual environment already active${NC}"
fi
echo ""

# 3. Upgrade pip
echo -e "${BLUE}Step 3/8: Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel
echo -e "${GREEN}✅ pip upgraded${NC}"
echo ""

# 4. Install numpy FIRST (critical for avoiding conflicts)
echo -e "${BLUE}Step 4/8: Installing numpy (conflict resolver)...${NC}"
pip install "numpy>=1.23.0,<2.0.0"
echo -e "${GREEN}✅ numpy installed${NC}"
echo ""

# 5. Install PyTorch (Apple Silicon optimized)
echo -e "${BLUE}Step 5/8: Installing PyTorch (Apple Silicon)...${NC}"
pip install torch torchaudio
echo -e "${GREEN}✅ PyTorch installed${NC}"
echo ""

# 6. Install core dependencies (without TTS first)
echo -e "${BLUE}Step 6/8: Installing core dependencies (this may take 10-15 min)...${NC}"
cat > temp_requirements.txt << 'EOF'
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6
pydantic==2.5.3
pydantic-settings==2.1.0
transformers>=4.35.0,<4.40.0
spacy>=3.7.0,<3.8.0
sentencepiece>=0.1.99
nltk>=3.8.0
PyMuPDF>=1.23.0
pdfplumber>=0.10.0
num2words>=0.5.13
unidecode>=1.3.0
python-dotenv>=1.0.0
tenacity>=8.2.0
tqdm>=4.66.0
loguru>=0.7.0
pytest>=7.4.0
httpx>=0.26.0
black>=24.1.0
soundfile>=0.12.0
pydub>=0.25.0
noisereduce>=3.0.0
EOF

pip install -r temp_requirements.txt
rm temp_requirements.txt
echo -e "${GREEN}✅ Core dependencies installed${NC}"
echo ""

# 7. Install librosa and TTS (in specific order)
echo -e "${BLUE}Step 7/8: Installing audio processing libraries...${NC}"
echo "Installing librosa..."
pip install "librosa>=0.10.0,<0.11.0"
echo "Installing TTS (Coqui)..."
pip install "TTS>=0.20.0" --no-deps
pip install "TTS>=0.20.0"
echo -e "${GREEN}✅ Audio libraries installed${NC}"
echo ""

# 8. Download spaCy model
echo -e "${BLUE}Step 8/8: Downloading spaCy English model...${NC}"
python -m spacy download en_core_web_sm
echo -e "${GREEN}✅ spaCy model downloaded${NC}"
echo ""

# Verification
echo "=============================================="
echo -e "${BLUE}Running verification tests...${NC}"
echo "=============================================="

python << 'EOF'
import sys
print("\n" + "=" * 70)
print("INSTALLATION VERIFICATION")
print("=" * 70 + "\n")

errors = []

# Test imports
try:
    import numpy
    print(f"✅ numpy {numpy.__version__}")
except ImportError as e:
    print(f"❌ numpy: {e}")
    errors.append("numpy")

try:
    import torch
    print(f"✅ PyTorch {torch.__version__}")
    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        print("   → MPS (Apple Silicon) available!")
except ImportError as e:
    print(f"❌ PyTorch: {e}")
    errors.append("PyTorch")

try:
    from TTS.api import TTS
    print("✅ Coqui TTS installed")
except ImportError as e:
    print(f"❌ Coqui TTS: {e}")
    errors.append("TTS")

try:
    import librosa
    print(f"✅ librosa {librosa.__version__}")
except ImportError as e:
    print(f"❌ librosa: {e}")
    errors.append("librosa")

try:
    import transformers
    print(f"✅ transformers {transformers.__version__}")
except ImportError as e:
    print(f"❌ transformers: {e}")
    errors.append("transformers")

try:
    import spacy
    print(f"✅ spaCy {spacy.__version__}")
    nlp = spacy.load('en_core_web_sm')
    print("   → en_core_web_sm model loaded")
except Exception as e:
    print(f"❌ spaCy: {e}")
    errors.append("spaCy")

try:
    import fastapi
    print(f"✅ FastAPI {fastapi.__version__}")
except ImportError as e:
    print(f"❌ FastAPI: {e}")
    errors.append("FastAPI")

print("\n" + "=" * 70)
if errors:
    print(f"❌ Installation incomplete. Failed: {', '.join(errors)}")
    print("=" * 70)
    sys.exit(1)
else:
    print("🎉 ALL DEPENDENCIES INSTALLED SUCCESSFULLY!")
    print("=" * 70)
EOF

verification_result=$?

if [ $verification_result -eq 0 ]; then
    echo ""
    echo "=============================================="
    echo -e "${GREEN}✅ INSTALLATION COMPLETE!${NC}"
    echo "=============================================="
    echo ""
    echo "Next steps:"
    echo "  1. Create app/services/tts/__init__.py (see instructions)"
    echo "  2. Start server: uvicorn app.main:app --reload"
    echo "  3. Open: http://localhost:8000/docs"
    echo ""
else
    echo ""
    echo "=============================================="
    echo -e "${RED}❌ Installation had errors${NC}"
    echo "=============================================="
    echo "Please check the output above for details."
    echo ""
    exit 1
fi