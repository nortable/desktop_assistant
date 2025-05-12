import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
from agent import ThreadedAgent
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

class DesktopAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Desktop Assistant")
        self.root.attributes('-topmost', True)  
        
        # Initialize the agent
        self.agent = ThreadedAgent()
        self.current_thread_id = None
        

        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.gifs = {
            'normal': os.path.join(script_dir, 'assets', 'role4', 'gif1.gif'),
            'chat': os.path.join(script_dir, 'assets', 'role4', 'gif2.gif')
        }
        self.current_state = 'normal'
        
        self.create_main_window()

        self.create_context_menu()
        
        self.root.bind('<Button-3>', self.show_context_menu)
        
    def create_main_window(self):
        # Create a frame for the GIF
        self.frame = ttk.Frame(self.root)
        self.frame.pack()
        
        # Load and display the initial GIF
        self.load_gif(self.gifs[self.current_state])
        
    def load_gif(self, gif_path):
        # Load the GIF
        self.gif = Image.open(gif_path)
        self.frames = []
        
        try:
            while True:
                self.frames.append(ImageTk.PhotoImage(self.gif.copy()))
                self.gif.seek(len(self.frames))
        except EOFError:
            pass
        
        # Create label for GIF
        if hasattr(self, 'gif_label'):
            self.gif_label.destroy()
        self.gif_label = ttk.Label(self.frame)
        self.gif_label.pack()
        
        # Start animation
        self.animate(0)
        
    def animate(self, frame_index):
        if frame_index < len(self.frames):
            self.gif_label.configure(image=self.frames[frame_index])
            self.root.after(100, lambda: self.animate((frame_index + 1) % len(self.frames)))
            
    def create_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Change State", command=self.change_state)
        self.context_menu.add_command(label="Open Chat", command=self.open_chat)
        
    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)
        
    def change_state(self):
        self.current_state = 'chat' if self.current_state == 'normal' else 'normal'
        self.load_gif(self.gifs[self.current_state])
        
    def open_chat(self):
        # Create chat window
        chat_window = tk.Toplevel(self.root)
        chat_window.title("Chat with Assistant")
        chat_window.geometry("400x500")
        
        # Create chat history display
        history_frame = ttk.Frame(chat_window)
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create text widget for chat history
        self.chat_history = tk.Text(history_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.chat_history.pack(fill=tk.BOTH, expand=True)
        
        # Tag config for user and assistant
        self.chat_history.tag_configure("user", foreground="blue", justify="right", font=("Arial", 12, "bold"), lmargin1=80, lmargin2=80, rmargin=10, spacing3=10)
        self.chat_history.tag_configure("assistant", foreground="green", justify="left", font=("Arial", 12), lmargin1=10, lmargin2=10, rmargin=80, spacing3=10)
        self.chat_history.tag_configure("system", foreground="gray", font=("Arial", 11, "italic"), spacing3=10)
        
        # Create scrollbar for chat history
        scrollbar = ttk.Scrollbar(history_frame, command=self.chat_history.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_history.config(yscrollcommand=scrollbar.set)
        
        # Create input frame
        input_frame = ttk.Frame(chat_window)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Create text entry
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Bind Enter key to send message
        self.message_entry.bind('<Return>', lambda event: self.send_message())
        
        # Create send button
        send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        send_button.pack(side=tk.RIGHT, padx=5)
        
        # Create history button
        history_button = ttk.Button(chat_window, text="Show History", command=self.show_history)
        history_button.pack(pady=5)
        
        # Initialize thread if not exists
        if not self.current_thread_id:
            self.current_thread_id = str(hash("initial"))
        
        # Insert default welcome message from assistant (English)
        welcome_message = "Hello! I am your desktop assistant. How can I help you today?"
        self.update_chat_history(welcome_message, sender="assistant")
        
    def send_message(self):
        message = self.message_entry.get().strip()  # Get and strip whitespace
        if message:
            # Clear the input field immediately
            self.message_entry.delete(0, tk.END)
            
            # Add user message to chat history
            self.update_chat_history(message, sender="user")
            
            # Disable input while processing
            self.message_entry.config(state='disabled')
            
            # Show typing indicator
            self.update_chat_history("Typing...", sender="assistant_typing")
            
            # Process message in background
            self.root.after(100, lambda: self.process_message(message))
            
    def process_message(self, message):
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the chat coroutine
            response = loop.run_until_complete(self.agent.chat(message, self.current_thread_id))
            
            # Remove typing indicator and show response
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.delete("end-2l", "end-1l")
            self.chat_history.config(state=tk.DISABLED)
            self.update_chat_history(response, sender="assistant")
            
            # Reset input
            self.message_entry.delete(0, tk.END)
            self.message_entry.config(state='normal')
            self.message_entry.focus_set()
            
        except Exception as e:
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.delete("end-2l", "end-1l")
            self.chat_history.config(state=tk.DISABLED)
            self.update_chat_history(f"Sorry, an error occurred: {str(e)}", sender="assistant")
            self.message_entry.config(state='normal')
            self.message_entry.focus_set()
        
    def update_chat_history(self, message, sender="user"):
        self.chat_history.config(state=tk.NORMAL)
        if sender == "user":
            self.chat_history.insert(tk.END, f"You: {message}\n", "user")
        elif sender == "assistant":
            self.chat_history.insert(tk.END, f"Assistant: {message}\n", "assistant")
        elif sender == "assistant_typing":
            self.chat_history.insert(tk.END, f"Assistant: {message}\n", "system")
        else:
            self.chat_history.insert(tk.END, message + "\n", "system")
        self.chat_history.see(tk.END)
        self.chat_history.config(state=tk.DISABLED)
        
    def show_history(self):
        if self.current_thread_id:
            history = self.agent.get_thread_history(self.current_thread_id)
            history_window = tk.Toplevel(self.root)
            history_window.title("Chat History")
            history_window.geometry("400x300")
            
            history_text = tk.Text(history_window, wrap=tk.WORD)
            history_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            for msg in history:
                if isinstance(msg, HumanMessage):
                    history_text.insert(tk.END, f"You: {msg.content}\n")
                elif isinstance(msg, AIMessage):
                    history_text.insert(tk.END, f"Assistant: {msg.content}\n")
                    
            history_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = DesktopAssistant(root)
    root.mainloop() 