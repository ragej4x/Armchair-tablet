import tkinter as tk
from tkinter import colorchooser, filedialog, simpledialog
from tkinter.ttk import Button, Frame
from PIL import Image, ImageDraw, ImageTk
import socket
import threading
import json


class PaintApp:
    def __init__(self, root):
        self.root = root
       

        self.brush_color = "black"
        self.eraser_color = "white"
        self.brush_size = 5
        self.tool = "brush"
        self.start_x = None
        self.start_y = None
        self.image = Image.new("RGB", (1024, 600), "white")
        self.draw = ImageDraw.Draw(self.image)


        

        # sserver setup
        self.clients = []
        self.clients_lock = threading.Lock()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = socket.gethostname()

        self.server_socket.bind((str(socket.gethostbyname(socket.gethostname())), 9999))
        self.server_socket.listen(5)
        threading.Thread(target=self.accept_clients, daemon=True).start()

        self.layout = Frame(self.root)
        self.layout.pack(fill=tk.BOTH, expand=True)

        self.root.title(f"Armchair Monitor (IPv4: {socket.gethostbyname(socket.gethostname())})")


        self.create_toolbar()

        self.canvas = tk.Canvas(self.layout, bg="white", width=1280, height=720, cursor="cross")
        self.canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<ButtonRelease-1>", self.end_draw)

    def accept_clients(self):
        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Client connected: {addr}")
            with self.clients_lock:
                self.clients.append(client_socket)
            threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()

    def handle_client(self, client_socket):
        data_buffer = ""
        while True:
            try:
                #increas lng ung buffer pag nag ddiscon
                chunk = client_socket.recv(4096).decode()
                if not chunk:
                    break
                data_buffer += chunk
                while "\n" in data_buffer:
                    message, data_buffer = data_buffer.split("\n", 1)
                    action = json.loads(message)
                    print(f"Received action: {action}")
            except (ConnectionResetError, BrokenPipeError, json.JSONDecodeError):
                break
        with self.clients_lock:
            self.clients.remove(client_socket)
        print("Client disconnected.")

    def broadcast(self, message):
        with self.clients_lock:
            to_remove = []
            for client in self.clients:
                try:
                    client.sendall((message + "\n").encode())
                except (ConnectionResetError, BrokenPipeError):
                    to_remove.append(client)
            for client in to_remove:
                self.clients.remove(client)
                print("Removed unresponsive client.")

    def create_toolbar(self):
        toolbar = Frame(self.layout)
        toolbar.pack(side=tk.LEFT, fill=tk.Y)

        Button(toolbar, text="Brush", command=lambda: self.select_tool("brush")).pack(padx=2, pady=2)
        Button(toolbar, text="Eraser", command=lambda: self.select_tool("eraser")).pack(padx=2, pady=2)
        Button(toolbar, text="Line", command=lambda: self.select_tool("line")).pack(padx=2, pady=2)
        Button(toolbar, text="Rectangle", command=lambda: self.select_tool("rectangle")).pack(padx=2, pady=2)
        Button(toolbar, text="Oval", command=lambda: self.select_tool("oval")).pack(padx=2, pady=2)
        Button(toolbar, text="Text", command=lambda: self.select_tool("text")).pack(padx=2, pady=2)
        Button(toolbar, text="Color", command=self.choose_color).pack(padx=2, pady=2)
        tk.Scale(toolbar, from_=1, to=100, orient=tk.HORIZONTAL, label="   Brush Size", command=self.change_brush_size).pack(padx=2, pady=2)
        Button(toolbar, text="Save", command=self.save_image).pack(padx=2, pady=2)
        Button(toolbar, text="Clear", command=self.clear_canvas).pack(padx=2, pady=2)
        #Button(toolbar, text="Shutdown", command=self.shutdown_server).pack(padx=2, pady=2)

    def select_tool(self, tool):
        self.tool = tool

    def choose_color(self):
        color = colorchooser.askcolor(color=self.brush_color)[1]
        if color:
            self.brush_color = color

    def change_brush_size(self, value):
        self.brush_size = int(value)

    def start_draw(self, event):
        self.start_x, self.start_y = event.x, event.y

    def paint(self, event):
        x, y = event.x, event.y
        if self.tool == "brush":
            self.draw_action("line", self.start_x, self.start_y, x, y)
            self.start_x, self.start_y = x, y
        elif self.tool == "eraser":
            self.draw_action("line", self.start_x, self.start_y, x, y, color=self.eraser_color)
            self.start_x, self.start_y = x, y

    def end_draw(self, event):
        if self.tool in ["line", "rectangle", "oval"]:
            self.draw_action(self.tool, self.start_x, self.start_y, event.x, event.y)
        elif self.tool == "text":
            self.add_text(event)

    def draw_action(self, action, x1, y1, x2, y2, color=None):
        if not (0 <= x1 <= 1024 and 0 <= y1 <= 600 and 0 <= x2 <= 1024 and 0 <= y2 <= 600):
            print(f"Invalid coordinates: {x1}, {y1}, {x2}, {y2}")
            return  #invalid coords

        if action == "line":
            color = color or self.brush_color
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=self.brush_size, capstyle=tk.ROUND, smooth=True)
            self.draw.line([x1, y1, x2, y2], fill=color, width=self.brush_size)
        elif action == "rectangle":
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=self.brush_color, width=self.brush_size)
            self.draw.rectangle([x1, y1, x2, y2], outline=self.brush_color, width=self.brush_size)
        elif action == "oval":
            self.canvas.create_oval(x1, y1, x2, y2, outline=self.brush_color, width=self.brush_size)
            self.draw.ellipse([x1, y1, x2, y2], outline=self.brush_color, width=self.brush_size)

        self.broadcast(json.dumps({
            "action": action,
            "x1": x1, "y1": y1,
            "x2": x2, "y2": y2,
            "color": color or self.brush_color,
            "width": self.brush_size
        }))

    def add_text(self, event):
        text = simpledialog.askstring("Text Input", "Enter text:")
        if text:
            x, y = event.x, event.y
            self.canvas.create_text(x, y, text=text, fill=self.brush_color, font=("Arial", self.brush_size * 2))
            self.draw.text((x, y), text, fill=self.brush_color)

            self.broadcast(json.dumps({
                "action": "text",
                "x": x,
                "y": y,
                "text": text,
                "color": self.brush_color,
                "size": self.brush_size * 2
            }))

    def clear_canvas(self):
        self.canvas.delete("all")
        self.image = Image.new("RGB", (1024, 600), "white")
        self.draw = ImageDraw.Draw(self.image)

        self.broadcast(json.dumps({"action": "clear"}))

    def save_image(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if file_path:
            self.image.save(file_path)

    def shutdown_server(self):
        with self.clients_lock:
            for client in self.clients:
                client.close()
            self.clients = []
        self.server_socket.close()
        print("Server shutdown.")
        self.root.quit()


root = tk.Tk()
app = PaintApp(root)
root.mainloop()
