import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
from agent import ThreadedAgent
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json
import datetime
import glob
import uuid

class GIFPlayer:
    def __init__(self, parent, gif_path):
        self.parent = parent
        self.frame = ttk.Frame(parent)
        self.frame.pack()
        
        self.label = ttk.Label(self.frame)
        self.label.pack()
        
        self.current_frame = 0
        self.frames = []
        self.duration = 100  # Default duration in ms
        
        try:
            self.load_gif(gif_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load GIF: {str(e)}")
    
    def load_gif(self, gif_path):
        with Image.open(gif_path) as gif:
            # Get duration from GIF metadata if available
            try:
                self.duration = gif.info.get('duration', 100)
            except:
                pass
                
            # Load frames
            self.frames = []
            for frame in range(gif.n_frames):
                gif.seek(frame)
                self.frames.append(ImageTk.PhotoImage(gif.copy()))
            
            # Start animation
            self.animate()
    
    def animate(self):
        if self.frames:
            self.label.configure(image=self.frames[self.current_frame])
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.parent.after(self.duration, self.animate)
    
    def stop(self):
        if hasattr(self, 'label'):
            self.label.destroy()
        if hasattr(self, 'frame'):
            self.frame.destroy()

class DesktopAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Desktop Assistant")
        self.root.attributes('-topmost', True)  
        
        # Initialize the agent and state
        self.agent = ThreadedAgent()
        self.current_thread_id = None
        self.unsaved_changes = False
        
        # Setup paths and directories
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.summaries_dir = os.path.join(script_dir, 'summaries')
        self.gif_path = os.path.join(script_dir, 'assets', 'role4', 'gif1.gif')
        os.makedirs(self.summaries_dir, exist_ok=True)
        
        # Initialize UI
        self.gif_player = GIFPlayer(self.root, self.gif_path)
        self.create_context_menu()
        self.root.bind('<Button-3>', self.show_context_menu)
        

        
    def create_context_menu(self):
        """Create the context menu"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Open Chat", command=self.open_chat)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Quit", command=self.quit_application)
        
    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)
        
    def _create_chat_window(self):
        """Create the main chat window"""
        chat_window = tk.Toplevel(self.root)
        chat_window.title("Chat with Assistant")
        chat_window.geometry("600x700")
        chat_window.protocol("WM_DELETE_WINDOW", lambda: self.on_chat_window_close(chat_window))
        return chat_window

    def _create_history_panel(self, parent):
        """Create the left panel for conversation history"""
        panel = ttk.Frame(parent, width=200)
        panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        ttk.Label(panel, text="Conversation History").pack(pady=(0, 5))
        
        self.history_listbox = tk.Listbox(panel, width=30, height=20)
        self.history_listbox.pack(fill=tk.BOTH, expand=True)
        self.history_listbox.bind('<<ListboxSelect>>', self.load_selected_conversation)
        
        ttk.Button(panel, text="New Conversation", command=self.start_new_conversation).pack(pady=5)
        return panel

    def _create_chat_panel(self, parent):
        """Create the right panel for chat interface"""
        panel = ttk.Frame(parent)
        panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Chat history display
        history_frame = ttk.Frame(panel)
        history_frame.pack(fill=tk.BOTH, expand=True)
        
        self.chat_history = tk.Text(history_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.chat_history.pack(fill=tk.BOTH, expand=True)
        
        # Configure text tags
        self._configure_chat_tags()
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(history_frame, command=self.chat_history.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_history.config(yscrollcommand=scrollbar.set)
        
        # Input area
        self._create_input_area(panel)
        return panel

    def _configure_chat_tags(self):
        """Configure text tags for chat messages"""
        tags = {
            "user": {"foreground": "blue", "justify": "right", "font": ("Arial", 12, "bold"), 
                    "lmargin1": 80, "lmargin2": 80, "rmargin": 10, "spacing3": 10},
            "assistant": {"foreground": "green", "justify": "left", "font": ("Arial", 12),
                         "lmargin1": 10, "lmargin2": 10, "rmargin": 80, "spacing3": 10},
            "system": {"foreground": "gray", "font": ("Arial", 11, "italic"), "spacing3": 10}
        }
        for tag, config in tags.items():
            self.chat_history.tag_configure(tag, **config)

    def _create_input_area(self, parent):
        """Create the input area with entry and send button"""
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=tk.X, pady=10)
        
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.message_entry.bind('<Return>', lambda event: self.send_message())
        
        ttk.Button(input_frame, text="Send", command=self.send_message).pack(side=tk.RIGHT, padx=5)

    def open_chat(self):
        """Open the chat window and initialize all components"""
        # Create main window and frame
        chat_window = self._create_chat_window()
        main_frame = ttk.Frame(chat_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create panels
        self._create_history_panel(main_frame)
        self._create_chat_panel(main_frame)
        
        # Initialize conversation
        self.load_conversation_list()
        self.start_new_conversation()
        
    def load_conversation_list(self):
        """Load conversation history into the listbox, using thread numbers only."""
        self.history_listbox.delete(0, tk.END)
        if not os.path.exists(self.summaries_dir):
            return

        summary_files = sorted(glob.glob(os.path.join(self.summaries_dir, 'thread_*.json')), reverse=True)
        self.summary_files = summary_files  
        for idx, file_path in enumerate(summary_files, 1):
            self.history_listbox.insert(tk.END, f"Thread {idx}")

    def load_selected_conversation(self, event):
        """Load the selected conversation from history"""
        # Save current conversation before switching
        if self.current_thread_id and self.unsaved_changes:
            self.save_current_conversation()

        selection = self.history_listbox.curselection()
        if not selection:
            return

        selected_file = self.summary_files[selection[0]]
        try:
            with open(selected_file, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)
            
            # Clear current chat
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.delete(1.0, tk.END)
            self.chat_history.config(state=tk.DISABLED)
            
            # Load messages
            for msg in summary_data.get('messages', []):
                if msg['role'] == 'user':
                    self.update_chat_history(msg['content'], sender="user")
                elif msg['role'] == 'assistant':
                    self.update_chat_history(msg['content'], sender="assistant")
            
            # Update current thread ID
            basename = os.path.basename(selected_file)
            if basename.startswith('thread_') and basename.endswith('.json'):
                self.current_thread_id = basename[len('thread_'):-len('.json')]
            else:
                self.current_thread_id = os.path.splitext(basename)[0]
            self.unsaved_changes = False

            # Restore messages to agent memory
            messages = []
            for msg in summary_data.get('messages', []):
                if msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    messages.append(AIMessage(content=msg['content']))
            self.agent.store.mset([(f"thread_{self.current_thread_id}", {"messages": messages})])
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load conversation: {str(e)}")

    def start_new_conversation(self):
        """Start a new conversation"""
        # Save current conversation before starting new one
        if self.current_thread_id and self.unsaved_changes:
            self.save_current_conversation()

        self.current_thread_id = str(uuid.uuid4())
        self.unsaved_changes = True
        
        # Clear chat history
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state=tk.DISABLED)
        
        # Show welcome message
        welcome_message = "Hello! How can I help you today?"
        self.update_chat_history(welcome_message, sender="assistant")

        self.load_conversation_list()

    def send_message(self):
        message = self.message_entry.get().strip()  # Get and strip whitespace
        if message:
            # Clear the input field immediately
            self.message_entry.delete(0, tk.END)
            
            # Add user message to chat history
            self.update_chat_history(message, sender="user")
            self.unsaved_changes = True
            
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
            
            # Save conversation after each message exchange
            self.save_current_conversation()
            
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
        
    def save_current_conversation(self):
        """Save the current conversation if there are unsaved changes"""
        if not (self.current_thread_id and self.unsaved_changes):
            return
            
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Save conversation
            conversation = loop.run_until_complete(self.agent.save_conversation(self.current_thread_id))
            
            # Save to file
            filename = f"thread_{self.current_thread_id}.json"
            filepath = os.path.join(self.summaries_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(conversation, f, ensure_ascii=False, indent=2)
                
            self.unsaved_changes = False
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save conversation: {str(e)}")
        finally:
            loop.close()
            
        # Refresh conversation list
        self.load_conversation_list()

    def on_chat_window_close(self, chat_window):
        """Handle chat window close event"""
        self.save_current_conversation()
        chat_window.destroy()

    def quit_application(self):
        # Save if there is any message in the current thread
        self.save_current_conversation()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = DesktopAssistant(root)
    root.mainloop() 