# 🎙️ Audio Transcription & Cleaning Suite

A comprehensive audio processing platform powered by whisper.cpp, featuring single-file transcription, batch processing, real-time voice-to-text service, and AI-powered audio cleaning capabilities.

## ✨ Key Features

### 1. Single File Transcription
- Multiple audio format support (WAV, MP3, OGG, FLAC, M4A)
- Multiple output formats (TXT, SRT, VTT, JSON)
- Multi-language transcription support
- Real-time progress tracking

### 2. Batch Transcription
- Process entire directories of audio files
- Selective file type processing
- Unified output format settings
- Progress tracking and error handling

### 3. Voice-to-Text Service
- Press and hold Caps Lock to record
- Automatic transcription and clipboard copy
- Real-time status display
- Automatic temporary file cleanup

### 4. AI Audio Cleaning 🆕
- AI-powered audio content analysis
- Automatic detection and removal of low-quality segments
- Customizable cleaning rules
- Output cleaned audio files

### 5. Secondary Transcription & HRT Subtitle Generation 🎬
- Perform speech recognition on cleaned audio for higher accuracy
- Generate high-quality HRT format subtitle files
- Intelligent filtering of meaningless segments and noise
- Optimized subtitle display timing (2-5 second standard)
- Automatic punctuation cleanup
- Clear operational guidance and real-time status feedback

## 🛠️ Installation

### Method 1: Installation Script (Recommended)
1. Double-click `install_dependencies.bat`
2. Wait for all dependencies to install
3. Run `python all_in_one_gui.py` to start the program

### Method 2: Manual Installation
```bash
# Upgrade pip
pip install --upgrade pip

# Install core dependencies
pip install numpy>=1.21.0 scipy>=1.7.0 openai>=1.100.0

# Install audio processing libraries
pip install pydub>=0.25.1 sounddevice>=0.4.5

# Install system interaction libraries
pip install pyperclip>=1.8.0 pynput>=1.7.0
```

## 📋 System Requirements

- Python 3.7+
- Windows 10/11
- Minimum 4GB RAM
- Microphone (for voice-to-text service)

## 🎯 Usage Guide

### Starting the Program
```bash
# Full-featured version (recommended)
python all_in_one_gui.py

# Basic transcription version
python transcribe_gui.py
```

### Smart Audio Cleaning Configuration
1. In the "Smart Audio Cleaning" tab
2. Follow the workflow indicator: 📁 Select Audio → ⚙️ Configure API → 🧹 AI Cleaning → 🎬 Generate Subtitles
3. Choose AI format (OpenAI/Ollama/Gemini)
4. Use quick configuration buttons for common AI services:
   - 🌐 OpenRouter: Cloud AI service
   - 🦙 Ollama: Local AI model (no API key required)
   - 💎 Gemini: Google AI service
5. Click "📋 Paste" to paste your API Key (not required for Ollama)
6. Click "🧪 Test Connection" to verify configuration
7. Select audio file (output path automatically set)
8. Choose whether to enable secondary transcription and HRT subtitle generation
9. Click "🚀 Start Smart Cleaning" to process

### AI Format Support
- **OpenAI Format**: Standard OpenAI-compatible interface, automatically adds /v1 suffix
- **Ollama Format**: Local AI model service, no API key required, default address: http://localhost:11434
- **Gemini Format**: Google Gemini API, requires complete API path

### New Feature Highlights
- **Multi-AI Format Support**: Supports OpenAI, Ollama, and Gemini formats
- **Smart URL Processing**: OpenAI format automatically adds /v1 suffix, users only need to enter base URL
- **Secondary Transcription**: Perform speech recognition on cleaned audio for higher accuracy
- **HRT Subtitles**: Generate standard-compliant subtitle files with optimized timing and content
- **Real-time Status**: Detailed step progress display during processing
- **Smart Guidance**: Clear operational instructions and workflow indicators in the interface

### Supported AI Services
- OpenAI API
- OpenRouter API
- Other OpenAI-compatible API services

## 🎨 Interface Features

- 🎨 Modern UI design with Chinese language support
- 📊 Real-time status indicators and progress display
- 🎵 Intuitive audio file operation interface
- 🧪 One-click API connection testing
- 📋 Convenient paste functionality
- 🔄 Smart error handling and prompts

## Component Overview

### Core Libraries

- `whisper.dll` - Core functionality library
- `ggml.dll`, `ggml-cpu.dll`, `ggml-cuda.dll`, `ggml-base.dll` - Machine learning inference engines
- CUDA libraries - For GPU acceleration (`cublas64_12.dll`, `cublasLt64_12.dll`, `cudart64_12.dll`, `nvblas64_12.dll`, `nvrtc-builtins64_124.dll`, `nvrtc64_120_0.dll`)

### Command Line Tools

- `whisper-cli.exe` - Basic command-line transcription tool
- `whisper-stream.exe` - Real-time audio stream transcription tool
- `whisper-server.exe` - Transcription server providing API services
- `whisper-command.exe` - Command control tool
- `whisper-bench.exe` - Performance benchmarking tool
- `whisper-talk-llama.exe` - Conversation tool integrated with LLaMA models

### Auxiliary Tools

- `test-vad.exe`, `test-vad-full.exe` - Voice activity detection testing tools
- `vad-speech-segments.exe` - Speech segment extraction tool
- `quantize.exe` - Model quantization tool

### GUI Applications

- `all_in_one_gui.py` - Full-featured GUI application
- `start_all_in_one_gui.bat` - Batch script to launch the GUI
- `voice_to_text_service.py` - Voice-to-text background service
- `start_voice_service.bat` - Batch script to start the voice-to-text service

## Usage Examples

### Basic Transcription

```bash
whisper-cli.exe -m models/ggml-base.en.bin -f audio.wav -otxt
```

### Real-time Audio Stream Transcription

```bash
whisper-stream.exe -m models/ggml-base.en.bin
```

### Start Transcription Server

```bash
whisper-server.exe -m models/ggml-base.en.bin -p 8080
```

### Using the GUI Application

1. Double-click `start_all_in_one_gui.bat` to launch the full-featured GUI
2. Select the desired function tab:
   - Single File Transcription: Transcribe individual audio files
   - Batch Transcription: Transcribe all audio files in a specified directory
   - Voice-to-Text Service: Press and hold spacebar to record, release to auto-transcribe and copy to clipboard

### Using Voice-to-Text Service

1. In the GUI, switch to the "Voice-to-Text Service" tab
2. Click the "Start Service" button
3. Press and hold spacebar to start recording
4. Release spacebar to end recording, system will automatically transcribe and copy text to clipboard
5. Click "Stop Service" to stop the service

## Model Downloads

Before use, you need to download Whisper models. Models can be obtained from:

1. Official pre-trained models: [https://github.com/openai/whisper/](https://github.com/openai/whisper/)
2. ggml format models: [https://huggingface.co/ggerganov/whisper.cpp](https://huggingface.co/ggerganov/whisper.cpp)

After downloading, place the model files in the `models` directory.

## System Requirements

- Windows operating system
- For GPU acceleration: NVIDIA graphics card with CUDA support
- Sufficient RAM (minimum 4GB, depending on model size)
- Python 3.6+ (for GUI applications)
- Dependencies: tkinter, numpy, sounddevice, pynput, pyperclip, scipy (for voice-to-text service)

## Important Notes

- Transcription quality depends on model size and audio quality
- Larger models provide higher accuracy but require more computational resources
- GPU acceleration can significantly improve transcription speed

## References

- [whisper.cpp GitHub Repository](https://github.com/ggerganov/whisper.cpp)
- [OpenAI Whisper Project](https://github.com/openai/whisper)