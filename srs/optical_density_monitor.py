import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import time
import re

class OpticalDensityMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("OptiNanoDense Controller")
        self.root.geometry("800x600")
        
        self.ser = None
        self.data_queue = queue.Queue()
        self.running = False
        
        self.create_widgets()
        self.auto_connect()
    
    def create_widgets(self):
        # Стили
        style = ttk.Style()
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TButton", padding=6, font=('Arial', 10))
        style.configure("TLabel", background="#f0f0f0", font=('Arial', 10))
        
        # Основные фреймы
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Панель управления
        control_frame = ttk.LabelFrame(main_frame, text="Управление подключением")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="Порт:").grid(row=0, column=0, padx=5, pady=5)
        self.port_combo = ttk.Combobox(control_frame, width=20)
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        
        self.connect_btn = ttk.Button(control_frame, text="Подключиться", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=2, padx=5, pady=5)
        
        self.refresh_btn = ttk.Button(control_frame, text="Обновить порты", command=self.refresh_ports)
        self.refresh_btn.grid(row=0, column=3, padx=5, pady=5)
        
        # Панель команд
        command_frame = ttk.LabelFrame(main_frame, text="Управление устройством")
        command_frame.pack(fill=tk.X, padx=5, pady=5)
        
        commands = [
            ("Измерить плотность", "1"),
            ("Настроить коэффициенты", "2"),
            ("Определить концентрацию", "3"),
            ("Повторить измерение", "1"),
            ("Главное меню", "m")
        ]
        
        for i, (text, cmd) in enumerate(commands):
            btn = ttk.Button(command_frame, text=text, 
                            command=lambda c=cmd: self.send_command(c))
            btn.grid(row=0, column=i, padx=5, pady=5)
        
        # Панель данных
        data_frame = ttk.LabelFrame(main_frame, text="Данные с устройства")
        data_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.data_text = scrolledtext.ScrolledText(data_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.data_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.data_text.config(state=tk.DISABLED)
        
        # Панель статуса
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_var = tk.StringVar(value="Статус: Ожидание подключения")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        self.density_var = tk.StringVar(value="Оптическая плотность: --")
        ttk.Label(status_frame, textvariable=self.density_var).pack(side=tk.RIGHT, padx=10)
        
        self.concentration_var = tk.StringVar(value="Концентрация: --")
        ttk.Label(status_frame, textvariable=self.concentration_var).pack(side=tk.RIGHT, padx=10)
    
    def auto_connect(self):
        self.refresh_ports()
        ports = [p.device for p in serial.tools.list_ports.comports() 
                if 'CH340' in p.description or 'USB Serial' in p.description]
        
        if ports:
            self.port_combo.set(ports[0])
            self.toggle_connection()
    
    def refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_combo.get():
            self.port_combo.set(ports[0])
    
    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.stop_serial()
            self.connect_btn.config(text="Подключиться")
            self.status_var.set("Статус: Отключено")
        else:
            port = self.port_combo.get()
            if port:
                self.start_serial(port)
                self.connect_btn.config(text="Отключиться")
                self.status_var.set(f"Статус: Подключено к {port}")
    
    def start_serial(self, port):
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=9600,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=1
            )
            self.running = True
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            self.process_thread = threading.Thread(target=self.process_data)
            self.process_thread.daemon = True
            self.process_thread.start()
        except Exception as e:
            self.status_var.set(f"Ошибка: {str(e)}")
    
    def stop_serial(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
    
    def read_serial(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.readline().decode('utf-8', errors='replace').strip()
                    if data:
                        self.data_queue.put(data)
            except Exception as e:
                self.status_var.set(f"Ошибка чтения: {str(e)}")
                time.sleep(1)
    
    def process_data(self):
        while self.running:
            try:
                data = self.data_queue.get(timeout=0.1)
                self.update_display(data)
                
                # Автоматическое извлечение данных
                if "Оптическая плотность A:" in data:
                    match = re.search(r"[-+]?\d*\.\d+|\d+", data)
                    if match:
                        self.density_var.set(f"Оптическая плотность: {match.group()}")
                
                if "Концентрация:" in data:
                    match = re.search(r"[-+]?\d*\.\d+|\d+", data)
                    if match:
                        self.concentration_var.set(f"Концентрация: {match.group()}")
                
            except queue.Empty:
                continue
            except Exception as e:
                self.status_var.set(f"Ошибка обработки: {str(e)}")
    
    def update_display(self, data):
        self.data_text.config(state=tk.NORMAL)
        self.data_text.insert(tk.END, data + "\n")
        self.data_text.see(tk.END)
        self.data_text.config(state=tk.DISABLED)
    
    def send_command(self, command):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((command + "\n").encode())
                self.update_display(f">>> Отправлена команда: {command}")
            except Exception as e:
                self.status_var.set(f"Ошибка отправки: {str(e)}")
    
    def on_closing(self):
        self.stop_serial()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = OpticalDensityMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
