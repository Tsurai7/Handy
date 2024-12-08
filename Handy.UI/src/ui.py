import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import helpers

icons = {
    "Info": "warning.png",
    "Error": "error.png"
}


def show_toast(message, message_type="Info", duration=3000):
    toast = tk.Toplevel()
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)

    screen_width = toast.winfo_screenwidth()
    screen_height = toast.winfo_screenheight()
    window_width = 300
    window_height = 60
    x = screen_width - window_width - 20
    y = screen_height - window_height - 60
    toast.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Create a frame to hold the icon and message
    frame = tk.Frame(toast, bg="black")
    frame.pack(fill=tk.BOTH, expand=True)

    # Load the icon based on message type
    icon_path = icons.get(message_type, "info.png")
    icon = helpers.load_icon(icon_path)

    # Display the icon (if loaded) and the message
    if icon:
        icon_label = tk.Label(frame, image=icon, bg="black")
        icon_label.image = icon  # Keep a reference to avoid garbage collection
        icon_label.pack(side=tk.LEFT, padx=10, pady=10)

    label = tk.Label(frame, text=message, bg="black", fg="white", font=("Arial", 12), anchor="w")
    label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    toast.after(duration, toast.destroy)