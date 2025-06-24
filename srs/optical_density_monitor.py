import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import queue
import time
import re
import configparser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import os
import json
from datetime import datetime

class OpticalDensityMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("OptiNanoDense Controller")
        self.root.geometry("1000x800")
        
        self.ser = None
        self.data_queue = queue.Queue()
        self.running = False
        self.config = configparser.ConfigParser()
        self.measurements = []
        self.calibration = {'a1': 1.0, 'a2': 0.0, 'cuvet_length': 1.0}
        self.load_config()
        
        self.create_widgets()
        self.auto_connect()
    
    def load_config(self):
        """Загружает конфигурацию из файла"""
        self.config.read('config.ini')
        
        # Настройки по умолчанию
        defaults = {
            'Serial': {'baudrate': '9600', 'timeout': '1'},
            'Calibration': {'a1': '1.0', 'a2': '0.0', 'cuvet_length': '1.0'},
            'UI': {'theme': 'light', 'max_measurements': '50'},
            'Paths': {'save_dir': './data'}
        }
        
        # Создаем секции с дефолтными значениями, если их нет
        for section, options in defaults.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, value)
        
        # Сохраняем конфиг, если файла не было
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)
        
        # Создаем папку для данных, если не существует
        save_dir = self.config.get('Paths', 'save_dir')
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        # Загружаем калибровку
        self.calibration['a1'] = self.config.getfloat('Calibration', 'a1')
        self.calibration['a2'] = self.config.getfloat('Calibration', 'a2')
        self.calibration['cuvet_length'] = self.config.getfloat('Calibration', 'cuvet_length')
    
    def save_config(self):
        """Сохраняет текущие настройки в конфиг"""
        self.config.set('Calibration', 'a1', str(self.calibration['a1']))
        self.config.set('Calibration', 'a2', str(self.calibration['a2']))
        self.config.set('Calibration', 'cuvet_length', str(self.calibration['cuvet_length']))
        
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)
    
    def create_widgets(self):
        # Настройка стилей
        self.set_theme(self.config.get('UI', 'theme'))
        
        # Основные фреймы
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Левая панель (управление)
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Правая панель (данные и график)
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Панель управления подключением
        connection_frame = ttk.LabelFrame(left_panel, text="Управление подключением")
        connection_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(connection_frame, text="Порт:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.port_combo = ttk.Combobox(connection_frame, width=20)
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(connection_frame, text="Скорость:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.baud_combo = ttk.Combobox(connection_frame, width=10, values=["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.set(self.config.get('Serial', 'baudrate'))
        self.baud_combo.grid(row=1, column=1, padx=5, pady=5)
        
        self.connect_btn = ttk.Button(connection_frame, text="Подключиться", command=self.toggle_connection)
        self.connect_btn.grid(row=2, column=0, padx=5, pady=5)
        
        self.refresh_btn = ttk.Button(connection_frame, text="Обновить порты", command=self.refresh_ports)
        self.refresh_btn.grid(row=2, column=1, padx=5, pady=5)
        
        # Панель калибровки
        calibration_frame = ttk.LabelFrame(left_panel, text="Калибровочные параметры")
        calibration_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(calibration_frame, text="a1:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.a1_entry = ttk.Entry(calibration_frame, width=10)
        self.a1_entry.insert(0, str(self.calibration['a1']))
        self.a1_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(calibration_frame, text="a2:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.a2_entry = ttk.Entry(calibration_frame, width=10)
        self.a2_entry.insert(0, str(self.calibration['a2']))
        self.a2_entry.grid(row=1, column=1, padx=5, pady=2)
        
        ttk.Label(calibration_frame, text="Длина кюветы:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.length_entry = ttk.Entry(calibration_frame, width=10)
        self.length_entry.insert(0, str(self.calibration['cuvet_length']))
        self.length_entry.grid(row=2, column=1, padx=5, pady=2)
        
        self.save_calib_btn = ttk.Button(calibration_frame, text="Сохранить", command=self.save_calibration)
        self.save_calib_btn.grid(row=3, column=0, columnspan=2, pady=5)
        
        # Панель команд
        command_frame = ttk.LabelFrame(left_panel, text="Управление устройством")
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
            btn.grid(row=i//2, column=i%2, padx=5, pady=5, sticky="we")
        
        # Ручной ввод команд
        ttk.Label(command_frame, text="Ручная команда:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.cmd_entry = ttk.Entry(command_frame)
        self.cmd_entry.grid(row=3, column=1, padx=5, pady=5, sticky="we")
        
        self.send_cmd_btn = ttk.Button(command_frame, text="Отправить", 
                                      command=lambda: self.send_command(self.cmd_entry.get()))
        self.send_cmd_btn.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="we")
        
        # Панель управления данными
        data_control_frame = ttk.LabelFrame(left_panel, text="Управление данными")
        data_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.save_btn = ttk.Button(data_control_frame, text="Сохранить логи", command=self.save_logs)
        self.save_btn.pack(pady=5, fill=tk.X)
        
        self.save_data_btn = ttk.Button(data_control_frame, text="Сохранить данные", command=self.save_measurements)
        self.save_data_btn.pack(pady=5, fill=tk.X)
        
        self.clear_btn = ttk.Button(data_control_frame, text="Очистить график", command=self.clear_plot)
        self.clear_btn.pack(pady=5, fill=tk.X)
        
        # Панель данных
        data_frame = ttk.LabelFrame(right_panel, text="Данные с устройства")
        data_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.data_text = scrolledtext.ScrolledText(data_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.data_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.data_text.config(state=tk.DISABLED)
        
        # Панель графика
        graph_frame = ttk.LabelFrame(right_panel, text="График измерений")
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Настройка графика
        self.ax.set_title('Оптическая плотность и концентрация')
        self.ax.set_xlabel('Измерение')
        self.ax.set_ylabel('Значение')
        self.ax.grid(True)
        
        # Панель статуса
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.status_var = tk.StringVar(value="Статус: Ожидание подключения")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        self.density_var = tk.StringVar(value="Оптическая плотность: --")
        ttk.Label(status_frame, textvariable=self.density_var).pack(side=tk.RIGHT, padx=10)
        
        self.concentration_var = tk.StringVar(value="Концентрация: --")
        ttk.Label(status_frame, textvariable=self.concentration_var).pack(side=tk.RIGHT, padx=10)
    
    def set_theme(self, theme):
        """Устанавливает цветовую тему интерфейса"""
        if theme == 'dark':
            bg_color = "#2d2d2d"
            fg_color = "#ffffff"
            self.root.tk_setPalette(background=bg_color, foreground=fg_color)
        else:  # light
            bg_color = "#f0f0f0"
            fg_color = "#000000"
            self.root.tk_setPalette(background=bg_color, foreground=fg_color)
    
    def auto_connect(self):
        """Пытается автоматически подключиться к устройству"""
        self.refresh_ports()
        ports = [p.device for p in serial.tools.list_ports.comports() 
                if 'CH340' in p.description or 'USB Serial' in p.description]
        
        if ports:
            self.port_combo.set(ports[0])
            self.toggle_connection()
    
    def refresh_ports(self):
        """Обновляет список доступных портов"""
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_combo.get():
            self.port_combo.set(ports[0])
    
    def toggle_connection(self):
        """Подключает или отключает устройство"""
        if self.ser and self.ser.is_open:
            self.stop_serial()
            self.connect_btn.config(text="Подключиться")
            self.status_var.set("Статус: Отключено")
        else:
            port = self.port_combo.get()
            baud = int(self.baud_combo.get())
            if port:
                self.start_serial(port, baud)
                self.connect_btn.config(text="Отключиться")
                self.status_var.set(f"Статус: Подключено к {port}@{baud} бод")
    
    def start_serial(self, port, baudrate):
        """Устанавливает соединение с последовательным портом"""
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=float(self.config.get('Serial', 'timeout')))
            self.running = True
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
            
            self.process_thread = threading.Thread(target=self.process_data)
            self.process_thread.daemon = True
            self.process_thread.start()
            
            # Обновляем конфиг
            self.config.set('Serial', 'baudrate', str(baudrate))
            self.save_config()
        except Exception as e:
            self.status_var.set(f"Ошибка: {str(e)}")
    
    def stop_serial(self):
        """Закрывает соединение с последовательным портом"""
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
    
    def read_serial(self):
        """Читает данные из последовательного порта"""
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
        """Обрабатывает полученные данные и обновляет интерфейс"""
        while self.running:
            try:
                data = self.data_queue.get(timeout=0.1)
                self.update_display(data)
                
                # Автоматическое извлечение данных
                if "Оптическая плотность A:" in data:
                    match = re.search(r"[-+]?\d*\.\d+|\d+", data)
                    if match:
                        density = float(match.group())
                        self.density_var.set(f"Оптическая плотность: {density:.4f}")
                        
                        # Сохраняем измерение
                        measurement = {
                            'timestamp': datetime.now().isoformat(),
                            'density': density,
                            'concentration': None
                        }
                        
                        # Рассчитываем концентрацию, если есть калибровка
                        if self.calibration['a1'] != 0:
                            concentration = self.calibration['a1'] * density + self.calibration['a2']
                            measurement['concentration'] = concentration
                            self.concentration_var.set(f"Концентрация: {concentration:.4f}")
                        
                        self.measurements.append(measurement)
                        self.update_plot()
                
                elif "Концентрация:" in data:
                    match = re.search(r"[-+]?\d*\.\d+|\d+", data)
                    if match:
                        concentration = float(match.group())
                        self.concentration_var.set(f"Концентрация: {concentration:.4f}")
                        
                        # Обновляем последнее измерение
                        if self.measurements:
                            self.measurements[-1]['concentration'] = concentration
                            self.update_plot()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.status_var.set(f"Ошибка обработки: {str(e)}")
    
    def update_display(self, data):
        """Обновляет текстовое поле с данными"""
        self.data_text.config(state=tk.NORMAL)
        self.data_text.insert(tk.END, data + "\n")
        self.data_text.see(tk.END)
        self.data_text.config(state=tk.DISABLED)
    
    def update_plot(self):
        """Обновляет график с последними измерениями"""
        if not self.measurements:
            return
            
        max_measurements = self.config.getint('UI', 'max_measurements')
        measurements = self.measurements[-max_measurements:]
        
        # Подготавливаем данные для графика
        x = list(range(len(measurements)))
        densities = [m['density'] for m in measurements]
        concentrations = [m['concentration'] for m in measurements if m['concentration'] is not None]
        
        # Очищаем и перерисовываем график
        self.ax.clear()
        
        # Рисуем оптическую плотность
        self.ax.plot(x, densities, 'bo-', label='Оптическая плотность')
        
        # Рисуем концентрацию, если есть данные
        if concentrations and len(concentrations) == len(x[:len(concentrations)]):
            self.ax.plot(x[:len(concentrations)], concentrations, 'r^-', label='Концентрация')
            
            # Добавляем вторую ось Y для концентрации
            ax2 = self.ax.twinx()
            ax2.plot(x[:len(concentrations)], concentrations, 'r^-')
            ax2.set_ylabel('Концентрация', color='r')
            ax2.tick_params(axis='y', labelcolor='r')
        
        # Настраиваем график
        self.ax.set_title('Оптическая плотность и концентрация')
        self.ax.set_xlabel('Измерение')
        self.ax.set_ylabel('Оптическая плотность', color='b')
        self.ax.tick_params(axis='y', labelcolor='b')
        self.ax.grid(True)
        self.ax.legend(loc='upper left')
        
        self.canvas.draw()
    
    def send_command(self, command):
        """Отправляет команду на устройство"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write((command + "\n").encode())
                self.update_display(f">>> Отправлена команда: {command}")
            except Exception as e:
                self.status_var.set(f"Ошибка отправки: {str(e)}")
    
    def save_calibration(self):
        """Сохраняет калибровочные параметры"""
        try:
            self.calibration['a1'] = float(self.a1_entry.get())
            self.calibration['a2'] = float(self.a2_entry.get())
            self.calibration['cuvet_length'] = float(self.length_entry.get())
            self.save_config()
            self.status_var.set("Калибровочные параметры сохранены")
            
            # Отправляем новые параметры на устройство
            self.send_command(f"SET_CALIB {self.calibration['a1']} {self.calibration['a2']} {self.calibration['cuvet_length']}")
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректные значения параметров")
    
    def save_logs(self):
        """Сохраняет логи в файл"""
        save_dir = self.config.get('Paths', 'save_dir')
        filename = filedialog.asksaveasfilename(
            initialdir=save_dir,
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(self.data_text.get("1.0", tk.END))
                self.status_var.set(f"Логи сохранены в {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {str(e)}")
    
    def save_measurements(self):
        """Сохраняет измерения в формате JSON"""
        save_dir = self.config.get('Paths', 'save_dir')
        filename = filedialog.asksaveasfilename(
            initialdir=save_dir,
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump({
                        'calibration': self.calibration,
                        'measurements': self.measurements
                    }, f, indent=4, ensure_ascii=False)
                self.status_var.set(f"Данные сохранены в {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {str(e)}")
    
    def clear_plot(self):
        """Очищает график и историю измерений"""
        self.measurements = []
        self.update_plot()
        self.density_var.set("Оптическая плотность: --")
        self.concentration_var.set("Концентрация: --")
        self.status_var.set("График очищен")
    
    def on_closing(self):
        """Обработчик закрытия окна"""
        self.stop_serial()
        self.save_config()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = OpticalDensityMonitor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
