# 🎙️ FlowWhisper

基于 whisper.cpp 的智能音频转录工具，支持多种 AI 格式和智能音频清理功能。

## ✨ 功能特点

### 核心功能
- **单文件转录**: 支持多种输出格式的音频文件转录
- **批量转录**: 处理整个目录的音频文件
- **语音转文字服务**: 按住 Caps Lock 键实时录音转录
- **智能音频清理**: AI 驱动的音频质量提升

### 高级功能
- **多 AI 格式支持**: OpenAI、Ollama 和 Gemini API 兼容
- **二次转录**: 通过双重转录提高准确性
- **HRT 字幕生成**: 优化的字幕文件，时间精确
- **智能 URL 处理**: 自动 API 端点格式化

### 支持格式
- **音频**: WAV、MP3、OGG、FLAC、M4A
- **输出**: TXT、SRT、VTT、JSON、HRT
- **语言**: 自动检测、英语、中文、日语、韩语、西班牙语、法语、德语

## 🛠️ 安装说明

### 系统要求
- Python 3.7+
- Windows 10/11
- 至少 4GB 内存
- 麦克风（用于语音转文字服务）

### 快速设置
1. **下载或克隆此仓库**
2. **安装依赖**:
   ```bash
   # 运行自动安装脚本
   install_dependencies.bat
   ```
   或
   ```bash
   # 手动安装
   pip install -r requirements.txt
   ```

3. **下载 whisper.cpp 组件**:
   - 下载 whisper-cli.exe 和所需的 DLL 文件
   - 下载 Whisper 模型文件 (.bin)
   - 将它们放在项目目录中

### 目录结构
```
FlowWhisper/
├── all_in_one_gui.py          # 主 GUI 应用程序
├── requirements.txt           # Python 依赖
├── install_dependencies.bat   # 自动安装脚本
├── audio_cleaner_config.json  # AI 配置模板
├── models/                    # Whisper 模型文件（需要自行添加）
├── tests/                     # 测试脚本
├── docs/                      # 文档
├── LICENSE                    # MIT 许可证
├── .gitignore                 # Git 忽略规则
└── README.md                  # 说明文件
```

## 🎯 使用方法

### 启动应用程序
```bash
# 完整功能 GUI（推荐）
python all_in_one_gui.py
```

### 智能音频清理

1. **选择音频**: 选择您的音频文件
2. **配置 AI**: 选择 AI 格式并输入 API 凭据
3. **处理**: 点击"开始智能清理"
4. **生成字幕**: 启用二次转录以生成 HRT 字幕

#### AI 格式支持
- **OpenAI**: 标准 OpenAI 兼容 API（自动添加 /v1 后缀）
- **Ollama**: 本地 AI 模型（无需 API 密钥）
- **Gemini**: Google Gemini API

#### 快速配置
- 🌐 **OpenRouter**: 云端 AI 服务
- 🦙 **Ollama**: 本地 AI 模型
- 💎 **Gemini**: Google AI 服务

### 语音转文字服务
1. 点击"启动服务"
2. 按住 **Caps Lock** 录音
3. 松开以转录并复制到剪贴板

## 📋 配置说明

### AI 配置
编辑 `audio_cleaner_config.json`:
```json
{
  "ai_format": "openai",
  "api_url": "https://openrouter.ai",
  "api_key": "YOUR_API_KEY_HERE",
  "model": "gpt-3.5-turbo"
}
```

### 支持的 AI 服务
- **OpenAI API**
- **OpenRouter API**
- **任何 OpenAI 兼容的 API**
- **Ollama 本地模型**
- **Google Gemini API**

## 🧪 测试

运行测试脚本以验证功能：

```bash
# 测试 GUI 功能
python tests/test_gui.py

# 测试 AI 格式功能
python tests/test_ai_format.py
```

## 📚 API 参考

### OpenAI 格式
- **URL 格式**: 自动在基础 URL 后添加 `/v1`
- **身份验证**: 标头中的 API 密钥
- **模型**: gpt-3.5-turbo、gpt-4、claude 系列等

### Ollama 格式
- **URL 格式**: 自动在基础 URL 后添加 `/api`
- **身份验证**: 本地模型无需
- **模型**: llama3.1、qwen2.5、mistral 等

### Gemini 格式
- **URL 格式**: 使用提供的完整 API 路径
- **身份验证**: 标头中的 API 密钥
- **模型**: gemini-1.5-flash、gemini-1.5-pro 等

## 🔧 故障排除

### 常见问题

1. **缺少依赖**
   - 运行 `install_dependencies.bat`
   - 确保安装了 Python 3.7+

2. **未找到 Whisper CLI**
   - 下载 whisper-cli.exe 并放在项目目录中
   - 确保所有必需的 DLL 文件都存在

3. **缺少模型文件**
   - 下载 Whisper 模型文件 (.bin)
   - 将它们放在 `models/` 目录中

4. **API 连接问题**
   - 验证 API 密钥是否正确
   - 检查网络连接
   - 使用"测试连接"按钮进行测试

5. **音频处理错误**
   - 确保音频文件为支持的格式
   - 检查文件权限
   - 验证磁盘空间是否充足

## 🤝 贡献

1. Fork 仓库
2. 创建功能分支
3. 进行更改
4. 为新功能添加测试
5. 提交拉取请求

## 📝 许可证

本项目基于 MIT 许可证 - 详情请查看 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) - 核心 whisper 功能
- [OpenAI](https://openai.com/) - AI API 服务
- [Ollama](https://ollama.com/) - 本地 AI 模型
- [Google Gemini](https://ai.google.dev/) - Google AI 服务

## 📞 支持

如有问题和疑问：
1. 查看故障排除部分
2. 运行测试脚本
3. 在 GitHub 上创建问题

---

**注意**: 此工具专为合法转录目的而设计。请确保您有权处理任何转录的音频内容。

## 📦 文件说明

### 必需文件
- **whisper-cli.exe**: whisper.cpp 的命令行工具
- **模型文件 (.bin)**: Whisper 模型，如 `ggml-base.bin`
- **DLL 文件**: whisper-cli.exe 运行所需的动态链接库

### 模型文件
将下载的 Whisper 模型文件放在以下位置之一：
- `models/` 目录
- `whisper/models/` 目录
- 项目根目录

### 使用前准备
1. 下载 whisper.cpp 压缩包
2. 解压到项目目录，重命名为 `whisper`
3. 下载所需的模型文件并放在 `models/` 目录
4. 确保 `whisper-cli.exe` 在项目根目录或 `whisper/` 目录中

### 模型下载
可以从以下地址下载模型文件：
- [whisper.cpp releases](https://github.com/ggerganov/whisper.cpp/releases)
- [Hugging Face](https://huggingface.co/ggerganov/whisper)

### 推荐模型
- `ggml-base.bin`: 基础模型，平衡性能和准确性
- `ggml-small.bin`: 小型模型，较快速度
- `ggml-medium.bin`: 中型模型，较好准确性
- `ggml-large-v3.bin`: 大型模型，最佳准确性