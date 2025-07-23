import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

class LanguageSelectionDialog:
    def __init__(self, root):
        self.root = root
        self.root.title("Select Language / Выберите язык")
        self.root.geometry("400x200")
        self.root.resizable(False, False)
        
        # Center the window
        self.root.eval('tk::PlaceWindow . center')
        
        self.selected_language = None
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(
            main_frame, 
            text="Select your language / Выберите ваш язык", 
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Create frame for buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, expand=True)
        
        # Load flag images
        try:
            ru_img = Image.open("ru_flag.png").resize((64, 48))
            self.ru_photo = ImageTk.PhotoImage(ru_img)
            
            en_img = Image.open("uk_flag.png").resize((64, 48))
            self.en_photo = ImageTk.PhotoImage(en_img)
        except Exception as e:
            print(f"Error loading flag images: {e}")
            # Create placeholder images if files don't exist
            ru_img = Image.new('RGB', (64, 48), color='red')
            self.ru_photo = ImageTk.PhotoImage(ru_img)
            
            en_img = Image.new('RGB', (64, 48), color='blue')
            self.en_photo = ImageTk.PhotoImage(en_img)
        
        # Create language buttons
        self.ru_button = ttk.Button(
            button_frame,
            image=self.ru_photo,
            text="Русский",
            compound=tk.TOP,
            command=lambda: self.select_language("ru")
        )
        self.ru_button.pack(side=tk.LEFT, padx=20)
        
        self.en_button = ttk.Button(
            button_frame,
            image=self.en_photo,
            text="English",
            compound=tk.TOP,
            command=lambda: self.select_language("en")
        )
        self.en_button.pack(side=tk.RIGHT, padx=20)
        
    def select_language(self, lang_code):
        self.selected_language = lang_code
        self.root.destroy()

def get_language():
    """Show language selection dialog and return selected language code."""
    root = tk.Tk()
    app = LanguageSelectionDialog(root)
    root.mainloop()
    return app.selected_language

