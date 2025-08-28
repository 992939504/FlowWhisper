# 🎙️ FlowWhisper

A comprehensive audio transcription tool based on whisper.cpp with intelligent audio cleaning and multi-AI format support.

## ✨ Features

### Core Functionality
- **Single File Transcription**: Transcribe individual audio files with multiple output formats
- **Batch Transcription**: Process entire directories of audio files
- **Voice-to-Text Service**: Real-time transcription using Caps Lock key
- **Intelligent Audio Cleaning**: AI-powered audio quality improvement

### Advanced Features
- **Multi-AI Format Support**: OpenAI, Ollama, and Gemini API compatibility
- **Secondary Transcription**: Enhanced accuracy through dual-pass transcription
- **HRT Subtitle Generation**: Optimized subtitle files with proper timing
- **Smart URL Processing**: Automatic API endpoint formatting

### Supported Formats
- **Audio**: WAV, MP3, OGG, FLAC, M4A
- **Output**: TXT, SRT, VTT, JSON, HRT
- **Languages**: Auto-detection, English, Chinese, Japanese, Korean, Spanish, French, German

## 🛠️ Installation

### Prerequisites
- Python 3.7+
- Windows 10/11
- At least 4GB RAM
- Microphone (for voice-to-text service)

### Quick Setup
1. **Clone or download this repository**
2. **Install dependencies**:
   ```bash
   # Run the automated installer
   install_dependencies.bat
   ```
   OR
   ```bash
   # Manual installation
   pip install -r requirements.txt
   ```

3. **Download whisper.cpp components**:
   - Download whisper-cli.exe and required DLL files
   - Download Whisper model files (.bin)
   - Place them in the project directory

### File Requirements

#### Required Files
- **whisper-cli.exe**: Command line tool from whisper.cpp
- **Model files (.bin)**: Whisper models like `ggml-base.bin`
- **DLL files**: Dynamic link libraries required by whisper-cli.exe

#### Model File Placement
Place downloaded Whisper model files in one of these locations:
- `models/` directory
- `whisper/models/` directory
- Project root directory

#### Preparation Steps
1. Download whisper.cpp release package
2. Extract to project directory and rename to `whisper`
3. Download required model files and place in `models/` directory
4. Ensure `whisper-cli.exe` is in project root or `whisper/` directory

#### Model Downloads
Download model files from:
- [whisper.cpp releases](https://github.com/ggerganov/whisper.cpp/releases)
- [Hugging Face](https://huggingface.co/ggerganov/whisper)

#### Recommended Models
- `ggml-base.bin`: Base model, balanced performance and accuracy
- `ggml-small.bin`: Small model, faster speed
- `ggml-medium.bin`: Medium model, good accuracy
- `ggml-large-v3.bin`: Large model, best accuracy

### Directory Structure
```
FlowWhisper/
├── all_in_one_gui.py          # Main GUI application
├── requirements.txt           # Python dependencies
├── install_dependencies.bat   # Automated installer
├── audio_cleaner_config.json  # AI configuration template
├── models/                    # Whisper model files (empty - add your own)
├── tests/                     # Test scripts
├── docs/                      # Documentation
├── LICENSE                    # MIT License
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## 🎯 Usage

### Starting the Application
```bash
# Full-featured GUI (recommended)
python all_in_one_gui.py
```

### Intelligent Audio Cleaning

1. **Select Audio**: Choose your audio file
2. **Configure AI**: Select AI format and enter API credentials
3. **Process**: Click "Start Intelligent Cleaning"
4. **Generate Subtitles**: Enable secondary transcription for HRT subtitles

#### AI Format Support
- **OpenAI**: Standard OpenAI-compatible APIs (automatically adds /v1 suffix)
- **Ollama**: Local AI models (no API key required)
- **Gemini**: Google Gemini API

#### Quick Configuration
- 🌐 **OpenRouter**: Cloud AI services
- 🦙 **Ollama**: Local AI models
- 💎 **Gemini**: Google AI services

### Voice-to-Text Service
1. Click "Start Service"
2. Hold **Caps Lock** to record
3. Release to transcribe and copy to clipboard

## 📋 Configuration

### AI Configuration
Edit `audio_cleaner_config.json`:
```json
{
  "ai_format": "openai",
  "api_url": "https://openrouter.ai",
  "api_key": "YOUR_API_KEY_HERE",
  "model": "gpt-3.5-turbo"
}
```

### Supported AI Services
- **OpenAI API**
- **OpenRouter API**
- **Any OpenAI-compatible API**
- **Ollama local models**
- **Google Gemini API**

## 🧪 Testing

Run the test scripts to verify functionality:

```bash
# Test GUI functionality
python tests/test_gui.py

# Test AI format features
python tests/test_ai_format.py
```

## 📚 API Reference

### OpenAI Format
- **URL Format**: Automatically appends `/v1` to base URL
- **Authentication**: API Key in header
- **Models**: gpt-3.5-turbo, gpt-4, claude series, etc.

### Ollama Format
- **URL Format**: Automatically appends `/api` to base URL
- **Authentication**: None required for local models
- **Models**: llama3.1, qwen2.5, mistral, etc.

### Gemini Format
- **URL Format**: Uses full API path as provided
- **Authentication**: API Key in header
- **Models**: gemini-1.5-flash, gemini-1.5-pro, etc.

## 🔧 Troubleshooting

### Common Issues

1. **Missing Dependencies**
   - Run `install_dependencies.bat`
   - Ensure Python 3.7+ is installed

2. **Whisper CLI Not Found**
   - Download whisper-cli.exe and place in project directory
   - Ensure all required DLL files are present

3. **Model Files Missing**
   - Download Whisper model files (.bin)
   - Place them in the `models/` directory

4. **API Connection Issues**
   - Verify API keys are correct
   - Check network connectivity
   - Test with "Test Connection" button

5. **Audio Processing Errors**
   - Ensure audio files are in supported formats
   - Check file permissions
   - Verify sufficient disk space

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) - Core whisper functionality
- [OpenAI](https://openai.com/) - AI API services
- [Ollama](https://ollama.com/) - Local AI models
- [Google Gemini](https://ai.google.dev/) - Google AI services

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Run the test scripts
3. Create an issue on GitHub

---

**Note**: This tool is designed for legitimate transcription purposes. Please ensure you have the right to transcribe any audio content you process.