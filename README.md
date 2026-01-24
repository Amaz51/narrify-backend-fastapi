# Narrify Backend

A powerful Python backend service for audio narration, text processing, and PDF conversion using advanced text-to-speech (TTS) technology.

## Features

- **Text-to-Speech (TTS)**: Convert text to natural-sounding audio using XTTS v2 multilingual model
- **Audio Processing**: Handle audio file uploads and processing
- **PDF Services**: Extract and process text from PDF documents
- **Multi-language Support**: Support for multiple languages via XTTS v2
- **Caching**: Efficient caching system for processed content
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Prerequisites

- Python 3.8+
- pip (Python package manager)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd narrify-backend-complete
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Project Structure

```
backend/
├── app/
│   ├── main.py           # Application entry point
│   ├── config.py         # Configuration settings
│   ├── api/
│   │   └── routes.py     # API endpoints
│   ├── services/
│   │   ├── audio_service.py    # Audio processing
│   │   ├── pdf_service.py      # PDF handling
│   │   ├── text_service.py     # Text processing
│   │   └── tts_service.py      # Text-to-speech
│   ├── models/
│   │   └── schemas.py    # Data schemas
│   └── utils/
│       ├── helpers.py    # Utility functions
│       └── logger.py     # Logging configuration
├── data/
│   ├── uploads/          # User uploaded files
│   ├── outputs/          # Generated output files
│   ├── cache/            # Cached data
│   └── voices/           # Voice samples
├── models/
│   └── tts/              # TTS model files (XTTS v2)
├── logs/                 # Application logs
├── requirements.txt      # Python dependencies
└── start.sh             # Startup script
```

## Running the Application

### Quick Start

```bash
cd backend
bash start.sh
```

### Manual Start

```bash
cd backend
python -m app.main
```

The application will be available at `http://localhost:5000` (or as configured in your `.env` file).

## API Endpoints

- **TTS Conversion**: Convert text to speech audio
- **Audio Processing**: Upload and process audio files
- **PDF Processing**: Extract text from PDFs and convert to speech
- **Text Processing**: Process and analyze text content

For detailed endpoint documentation, see the API routes in [app/api/routes.py](backend/app/api/routes.py).

## Configuration

Edit the `.env` file to configure:
- Server host and port
- TTS model settings
- API keys and credentials
- Logging level
- Cache settings
- Data directories

## Development

### Running Tests

```bash
pytest
```

### Code Style

Follow PEP 8 guidelines. Consider using:
```bash
pip install black flake8
black app/
flake8 app/
```

## Troubleshooting

- **TTS Model Issues**: Ensure the XTTS v2 model files are present in `models/tts/`
- **File Upload Errors**: Check write permissions on `data/uploads/` and `data/outputs/` directories
- **Memory Issues**: The TTS model is large; ensure sufficient RAM available

## Dependencies

Core dependencies (see `requirements.txt`):
- FastAPI/Flask - Web framework
- TTS - Text-to-speech engine
- PyPDF2/pdfplumber - PDF processing
- Pydantic - Data validation

## License

[Add your license information here]

## Support

For issues, questions, or contributions, please [add contact/contribution guidelines].
