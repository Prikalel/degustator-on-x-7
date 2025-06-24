import random
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os
from difficulty_multiplyer import get_difficulty

class ImageListDialog:
    image_data = []
    bouth_item = None

    def __init__(self, root, cached_mappings, round_num):
        self._cached_mappings = cached_mappings
        self.round_num = round_num
        self.root = root
        self.root.title("Покупка предмета!")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        self.selected_item = None
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create frame for the list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Load images
        self.load_images()
        
        # Create button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Create buttons
        self.buy_button = ttk.Button(button_frame, text="Купить и съесть!", command=self.buy_item, state=tk.DISABLED)
        cancel_button = ttk.Button(button_frame, text="Отказаться(", command=self.root.destroy)
        
        # Place buttons
        self.buy_button.pack(side=tk.RIGHT, padx=5)
        cancel_button.pack(side=tk.RIGHT, padx=5)
        
    def load_images(self):
        # Sample image paths - replace with your actual image paths
        # For this example, we'll create a list of dummy image data
        image_data = []
        for data in self._cached_mappings:
            image_data.append({"name": data["item"]["name"] + ' за ' + str(get_difficulty(self.round_num)*data["item"]["cost"]) + "$", "path": data["item"]["image"]})
        
        random.shuffle(image_data)
        # For demo purposes, create colored squares instead of loading actual images
        self.photo_references = []  # Keep references to prevent garbage collection
        
        # Create a single IntVar for all radio buttons
        self.selection_var = tk.IntVar(value=-1)

        for i, item in enumerate(image_data):
            # Create frame for each item
            item_frame = ttk.Frame(self.scrollable_frame)
            item_frame.pack(fill=tk.X, pady=5)
            
            # Create radio button for selection using the shared variable
            radio = ttk.Radiobutton(
                item_frame, 
                text=item["name"],
                variable=self.selection_var,
                value=i,
                command=self.on_selection_change
            )
            radio.pack(side=tk.LEFT, padx=(0, 10))
            
            # Create a colored square as a placeholder for the image
            # In a real app, you would load the image from item["path"]
            try:
                # Try to load the actual image if it exists
                img = Image.open(item["path"]).resize((100, 100))
                photo = ImageTk.PhotoImage(img)
            except (FileNotFoundError, OSError):
                # Create a colored placeholder if the image can't be loaded
                img = Image.new('RGB', (100, 100), color=(50*i % 200 + 55, 100, 150))
                photo = ImageTk.PhotoImage(img)
            
            self.photo_references.append(photo)
            
            # Display the image
            image_label = ttk.Label(item_frame, image=photo)
            image_label.pack(side=tk.LEFT)
        self.image_data = image_data
            
    def on_selection_change(self):
        self.selected_item = self.selection_var.get()
        # Enable the buy button when an item is selected
        self.buy_button.config(state=tk.NORMAL)
        
    def buy_item(self):
        if self.selected_item is not None and self.selected_item >= 0:
            print(f"Buying item {self.selected_item}")
            self.bouth_item = list(filter(lambda x: self.image_data[self.selected_item]["path"] == x["item"]["image"], self._cached_mappings ))[0]
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageListDialog(root)
    root.mainloop()
    print("done")