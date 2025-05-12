# Desktop Assistant

A modern, interactive desktop assistant with long-term memory, chat history, and conversation summarization, powered by LLMs via OpenRouter.

## Features
- Animated desktop assistant with GUI (Tkinter)
- Chat with LLM (Google Gemini, etc. via OpenRouter)
- Long-term memory: all conversations are saved and can be reloaded
- Conversation history browser (threaded)
- Conversation summarization (auto-generated JSON summary for each thread)
- Multi-threaded chat: start new conversations, revisit old ones

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/nortable/desktop_assistant.git
   cd desktop_assistant
   ```

2. **Install requirements**
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
