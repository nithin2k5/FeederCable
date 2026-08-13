import tkinter as tk
from tkinter import ttk

# Import our screen modules
import test_console
import model_settings
import data_console
import comport_settings

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Feeder Cable App")
        self.root.geometry("1350x860")
        self.root.configure(bg="black")
        
        # Apply standard theme
        style = ttk.Style()
        style.theme_use("clam")
        
        self.build_header()
        self.build_body()
        
        # Start on the default page
        self.load_page('test_console')

    def build_header(self):
        # Universal header
        self.header = tk.Frame(self.root, bg="black", height=45)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)

        logo_box = tk.Frame(self.header, bg="white", padx=6, pady=3)
        logo_box.pack(side="left", padx=10, pady=6)
        tk.Label(logo_box, text="INFAC", fg="#c00000", bg="white", font=('Arial', 16, 'bold')).pack(side="left")
        tk.Label(logo_box, text=" 주식회사인팩", fg="black", bg="white", font=('Malgun Gothic', 9)).pack(side="left")

        # Dynamic title label
        self.lbl_title = tk.Label(self.header, text="", fg="#e8a000", bg="black", font=('Arial', 15, 'bold'))
        self.lbl_title.pack(side="left", padx=25)
        
        # Datetime
        tk.Label(self.header, text="15/07/2025  15:05:07", fg="white", bg="black", font=('Arial', 10)).pack(side="right", padx=15)

    def build_body(self):
        self.body = tk.Frame(self.root, bg="black")
        self.body.pack(fill="both", expand=True)
        
        # --- Sidebar ---
        sidebar_w = 90
        sidebar = tk.Frame(self.body, bg="black", width=sidebar_w)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        sidebar_buttons = [
            ("👤", "Admin", "test_console"),
            ("⚙", "Settings", "model_settings"),
            ("⚖", "Comparator", ""),
            ("📋", "Test Data", "data_console"),
            ("🔧", "COM Setting", "comport_settings"),
        ]
        
        for icon, text, page in sidebar_buttons:
            # We use a hand2 cursor only if the page exists
            has_page = bool(page)
            cursor_type = "hand2" if has_page else "arrow"
            
            f = tk.Frame(sidebar, bg="#111", bd=1, relief="solid", highlightbackground="#444", highlightthickness=1, cursor=cursor_type)
            f.pack(fill="x", padx=4, pady=3)
            
            lbl_icon = tk.Label(f, text=icon, bg="#111", fg="white", font=('Arial', 18), cursor=cursor_type)
            lbl_icon.pack(pady=(6, 0))
            
            lbl_text = tk.Label(f, text=text, bg="#111", fg="white", font=('Arial', 8), cursor=cursor_type)
            lbl_text.pack(pady=(0, 6))
            
            # Bind click event
            if has_page:
                f.bind("<Button-1>", lambda e, p=page: self.load_page(p))
                lbl_icon.bind("<Button-1>", lambda e, p=page: self.load_page(p))
                lbl_text.bind("<Button-1>", lambda e, p=page: self.load_page(p))

        # --- Content Container ---
        # This empty frame will hold our different pages.
        self.content_area = tk.Frame(self.body, bg="black")
        self.content_area.pack(side="left", fill="both", expand=True)
        
    def load_page(self, page_name):
        # 1. Clear the current content area
        for widget in self.content_area.winfo_children():
            widget.destroy()
            
        # 2. Render the new page and update the title
        if page_name == "test_console":
            self.lbl_title.config(text="Feeder Cable", fg="#e8a000")
            test_console.render(self.content_area)
            
        elif page_name == "model_settings":
            self.lbl_title.config(text="Model Settings", fg="#e8a000")
            model_settings.render(self.content_area)
            
        elif page_name == "comport_settings":
            self.lbl_title.config(text="COM Settings", fg="#e8a000")
            comport_settings.render(self.content_area)
            
        elif page_name == "data_console":
            # data_console has its own specific title header built-in, so hide the universal one
            self.lbl_title.config(text="") 
            data_console.render(self.content_area)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
