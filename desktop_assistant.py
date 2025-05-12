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

class DesktopAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Desktop Assistant")
        self.root.attributes('-topmost', True)  
        
        # Initialize the agent
        self.agent = ThreadedAgent()
        self.current_thread_id = None
        
        # Create summaries directory if it doesn't exist
        self.summaries_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'summaries')
        os.makedirs(self.summaries_dir, exist_ok=True)

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
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Quit", command=self.quit_application)
        
    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)
        
    def change_state(self):
        self.current_state = 'chat' if self.current_state == 'normal' else 'normal'
        self.load_gif(self.gifs[self.current_state])
        
    def open_chat(self):
        # Create chat window
        chat_window = tk.Toplevel(self.root)
        chat_window.title("Chat with Assistant")
        chat_window.geometry("600x700")
        
        # Create main frame
        main_frame = ttk.Frame(chat_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create left panel for history list
        left_panel = ttk.Frame(main_frame, width=200)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Add history list label
        ttk.Label(left_panel, text="Conversation History").pack(pady=(0, 5))
        
        # Create listbox for history
        self.history_listbox = tk.Listbox(left_panel, width=30, height=20)
        self.history_listbox.pack(fill=tk.BOTH, expand=True)
        self.history_listbox.bind('<<ListboxSelect>>', self.load_selected_conversation)
        
        # Create right panel for chat
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create chat history display
        history_frame = ttk.Frame(right_panel)
        history_frame.pack(fill=tk.BOTH, expand=True)
        
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
        input_frame = ttk.Frame(right_panel)
        input_frame.pack(fill=tk.X, pady=10)
        
        # Create text entry
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Bind Enter key to send message
        self.message_entry.bind('<Return>', lambda event: self.send_message())
        
        # Create send button
        send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        send_button.pack(side=tk.RIGHT, padx=5)
        
        # Create new conversation button
        new_conv_button = ttk.Button(left_panel, text="New Conversation", command=self.start_new_conversation)
        new_conv_button.pack(pady=5)
        
        # Initialize thread if not exists
        if not self.current_thread_id:
            self.current_thread_id = str(hash("initial"))
        
        # Load conversation history into listbox
        self.load_conversation_list()
        
        # Insert default welcome message from assistant (English)
        welcome_message = "Hello! I am your desktop assistant. How can I help you today?"
        self.update_chat_history(welcome_message, sender="assistant")
        
    def load_conversation_list(self):
        """Load conversation history into the listbox"""
        self.history_listbox.delete(0, tk.END)
        summaries_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'summaries')
        if not os.path.exists(summaries_dir):
            return

        summary_files = glob.glob(os.path.join(summaries_dir, 'conversation_summary_*.json'))
        for file_path in sorted(summary_files, reverse=True):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                
                # Get timestamp from filename
                timestamp = os.path.basename(file_path).replace('conversation_summary_', '').replace('.json', '')
                date_str = f"{timestamp[:8]} {timestamp[9:11]}:{timestamp[11:13]}"
                
                # Get first user message as preview
                preview = "New Conversation"
                for msg in summary_data.get('messages', []):
                    if msg['role'] == 'user':
                        preview = msg['content'][:30] + "..." if len(msg['content']) > 30 else msg['content']
                        break
                
                self.history_listbox.insert(tk.END, f"{date_str} - {preview}")
                
            except Exception as e:
                print(f"Error loading conversation preview from {file_path}: {str(e)}")

    def load_selected_conversation(self, event):
        """Load the selected conversation from history"""
        selection = self.history_listbox.curselection()
        if not selection:
            return
            
        # Get the selected file
        summaries_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'summaries')
        summary_files = sorted(glob.glob(os.path.join(summaries_dir, 'conversation_summary_*.json')), reverse=True)
        selected_file = summary_files[selection[0]]
        
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
            self.current_thread_id = os.path.splitext(os.path.basename(selected_file))[0]
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load conversation: {str(e)}")

    def start_new_conversation(self):
        """Start a new conversation"""
        self.current_thread_id = str(hash(str(datetime.datetime.now())))
        
        # Clear chat history
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state=tk.DISABLED)
        
        # Show welcome message
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

    def quit_application(self):
        if self.current_thread_id:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Generate summary
                summary = loop.run_until_complete(self.agent.generate_summary(self.current_thread_id))
                
                # Save summary to file
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"conversation_summary_{timestamp}.json"
                filepath = os.path.join(self.summaries_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
                
                messagebox.showinfo("Summary Saved", f"Conversation summary has been saved to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to generate summary: {str(e)}")
            finally:
                loop.close()
        
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = DesktopAssistant(root)
    root.mainloop() 