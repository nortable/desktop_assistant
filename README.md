# Desktop Assistant

A modern, interactive desktop assistant with long-term memory, chat history, and conversation summarization, powered by LLMs via OpenRouter.

## Features
- **Animated Desktop Assistant**: Friendly, always-on-top assistant with customizable GIF appearance (right-click to change).
- **Conversational AI**: Chat with a powerful LLM (Google Gemini, etc. via OpenRouter) in a modern GUI.
- **Long-term Memory**: All conversations are saved as JSON summaries and can be reloaded at any time.
- **Threaded Conversation History**: Browse, revisit, and continue any previous conversation thread.
- **Multi-threaded Chat**: Start new conversations with "New Conversation" or continue existing ones.
- **User-friendly Interface**: Clean, resizable chat window with color-coded messages and history navigation.

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/nortable/desktop_assistant.git
   cd desktop_assistant
   ```

2. **Create and activate virtual environment**
   ```bash
   # On Windows
   python -m venv venv
   .\venv\Scripts\activate

   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install requirements**
   ```bash
   pip install -r requirements.txt
   ```

3. **Register and set your OpenRouter API key**
   - Go to [OpenRouter.ai](https://openrouter.ai/) and sign up for an account.
   - Get your API key from the OpenRouter dashboard.
   - Open `desktop_assistant/agent.py` and set your API key:
     ```python
     self.api_key = "sk-..."  # Replace with your actual OpenRouter API key
     ```
   - Or, for better security, you can set your API key as an environment variable:
     ```bash
     export OPENROUTER_API_KEY="sk-..."
     ```
     And in `agent.py`:
     ```python
     import os
     self.api_key = os.getenv("OPENROUTER_API_KEY", "sk-")
     ```

4. **Run the assistant**
   ```bash
   python desktop_assistant/desktop_assistant.py
   ```

## Usage
- Right-click the assistant to open the context menu.
- Start chatting, or open the chat window for a full conversation experience.
- Click "New Conversation" to start a new thread.
- All conversations are saved as JSON summaries in the `summaries` folder.
- You can revisit and continue any previous thread.

## Requirements
- Python 3.8+
- See `requirements.txt` for all dependencies (Tkinter, Pillow, langchain, openai, etc.)

## License
MIT 
