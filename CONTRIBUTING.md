# Contributing

Thank you for your interest in contributing to the FlowWhisper!

## Development Setup

1. **Fork the repository**
2. **Clone your fork**
   ```bash
   git clone https://github.com/your-username/FlowWhisper.git
   cd FlowWhisper
   ```

3. **Set up development environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

## Running Tests

Before submitting a pull request, please run the tests:

```bash
# Run all tests
python tests/test_gui.py
python tests/test_ai_format.py

# Test specific functionality
python -m pytest tests/
```

## Code Style

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions small and focused

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Add tests for new functionality
   - Update documentation if needed
   - Follow the existing code style

3. **Test your changes**
   ```bash
   # Run tests
   python tests/test_gui.py
   python tests/test_ai_format.py
   
   # Test the GUI
   python all_in_one_gui.py
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add your feature description"
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request**
   - Provide a clear description of your changes
   - Link any related issues
   - Include screenshots if UI changes

## Feature Requests

- Check existing issues before creating new ones
- Provide clear descriptions of requested features
- Explain the use case and benefits

## Bug Reports

- Use the GitHub issue template
- Provide steps to reproduce
- Include error messages and screenshots
- Specify your environment (OS, Python version, etc.)

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.