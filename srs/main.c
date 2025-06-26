#include <avr/io.h>
#include <util/delay.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>  // Добавлено для логарифмической функции

// Константы
#define A0 0
#define LASER_PIN PD2
#define PHOTO_PIN A0
#define BAUDRATE 103 // 9600 bps для 16 МГц

// Прототипы функций
void uart_init();
void uart_putchar(char c);
void uart_print(const char *str);
void uart_println(const char *str);
void uart_print_float(float value);
char uart_read_char();
void uart_read_line(char *buffer, uint8_t size);
float uart_read_float();

void showMainMenu();
void handleUserInput();
void configureCoefficients();
void measurementProcedure();
float readOpticalDensity();
bool waitForUserConfirmation();
void showPostMeasurementMenu();

// Глобальные переменные
float a1 = 0.0;
float a2 = 0.0;
float A0_value = 0.0;
bool DefConcentration = false;
float cuvet_length = 1.0;  // Длина кюветы в см (значение по умолчанию)
float baseline = 0.0;      // Базовая линия (пустая кювета)

int main(void) {
    // Настройка UART
    uart_init();
    
    // Настройка пинов
    DDRD |= (1 << LASER_PIN);     // Лазер как выход
    PORTD &= ~(1 << LASER_PIN);   // Выключить лазер
    
    // Настройка АЦП
    ADMUX = (1 << REFS0);         // Референс = AVcc
    ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS1) | (1 << ADPS0); // Делитель 128
    
    // Настройка пинов UART
    DDRD &= ~(1 << PD0); // RX как вход (PD0)
    DDRD |= (1 << PD1);  // TX как выход (PD1)
    
    _delay_ms(100);
    uart_println("\nСистема инициализирована");
    showMainMenu();

    while(1) {
        handleUserInput();
        _delay_ms(100);
    }
    return 0;
}

//---------------------------------------------------------
// Реализация функций UART
//---------------------------------------------------------

void uart_init() {
    UBRR0H = (BAUDRATE >> 8);
    UBRR0L = BAUDRATE;
    UCSR0B = (1 << TXEN0) | (1 << RXEN0);
    UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
}

void uart_putchar(char c) {
    while (!(UCSR0A & (1 << UDRE0)));
    UDR0 = c;
}

void uart_print(const char *str) {
    while (*str) {
        uart_putchar(*str++);
    }
}

void uart_println(const char *str) {
    uart_print(str);
    uart_putchar('\r');
    uart_putchar('\n');
}

void uart_print_float(float value) {
    char buffer[10];
    dtostrf(value, 5, 3, buffer);
    uart_print(buffer);
}

char uart_read_char() {
    while (!(UCSR0A & (1 << RXC0)));
    return UDR0;
}

void uart_read_line(char *buffer, uint8_t size) {
    uint8_t idx = 0;
    char c;
    
    while (idx < size - 1) {
        c = uart_read_char();
        
        if (c == '\r' || c == '\n') {
            buffer[idx] = '\0';
            uart_print("\r\n");
            return;
        }
        else if (c == 8 || c == 127) { // Backspace
            if (idx > 0) {
                idx--;
                uart_print("\b \b");
            }
        }
        else if (c >= ' ' && c <= '~') {
            buffer[idx++] = c;
            uart_putchar(c);
        }
    }
    buffer[idx] = '\0';
}

float uart_read_float() {
    char buffer[16];
    uart_read_line(buffer, sizeof(buffer));
    return atof(buffer);
}

//---------------------------------------------------------
// Основная логика приложения
//---------------------------------------------------------

void showMainMenu() {
    uart_println("\nВыберите действие:");
    uart_println("1. Измерение оптической плотности");
    uart_println("2. Настройка коэффициентов и длины кюветы");
    uart_println("3. Определение концентрации");
    uart_print("> ");
}

void handleUserInput() {
    if (UCSR0A & (1 << RXC0)) {
        char input = UDR0;
        
        switch(input) {
            case '1':
                uart_println("\nИзмерение");
                measurementProcedure();
                break;
            case '2':
                uart_println("\nНастройка коэффициентов");
                configureCoefficients();
                break;
            case '3':
                if (DefConcentration) {
                    float concentration = a1 * A0_value + a2;
                    uart_print("Концентрация: ");
                    uart_print_float(concentration);
                    uart_println("");
                } else {
                    uart_println("Сначала настройте коэффициенты!");
                }
                showMainMenu();
                break;
            default:
                uart_putchar(input); // Эхо
                break;
        }
    }
}

void configureCoefficients() {
    // Настройка длины кюветы
    uart_print("Текущая длина кюветы: ");
    uart_print_float(cuvet_length);
    uart_println(" см");
    uart_print("Введите новую длину кюветы (см): ");
    cuvet_length = uart_read_float();
    
    // Настройка коэффициентов
    uart_print("Введите a1 (коэффициент a1*C + a2): ");
    a1 = uart_read_float();
    
    uart_print("Введите a2: ");
    a2 = uart_read_float();
    
    DefConcentration = true;
    uart_print("Коэффициенты установлены: a1=");
    uart_print_float(a1);
    uart_print(", a2=");
    uart_print_float(a2);
    uart_print(", длина кюветы=");
    uart_print_float(cuvet_length);
    uart_println(" см");
    
    showMainMenu();
}

void measurementProcedure() {
    // 1. Измерение базовой линии (пустая кювета)
    uart_println("Вставьте пустую кювету и нажмите 1");
    
    if (!waitForUserConfirmation()) {
        uart_println("Отмена измерения");
        showMainMenu();
        return;
    }

    _delay_ms(100); // Стабилизация
    
    // Измерение базовой линии
    baseline = readOpticalDensity();
    uart_print("Базовая линия A0: ");
    uart_print_float(baseline);
    uart_println("");
    
    // 2. Измерение с аналитом
    uart_println("Вставьте кювету с аналитом и нажмите 1");
    
    if (!waitForUserConfirmation()) {
        uart_println("Отмена измерения");
        showMainMenu();
        PORTD &= ~(1 << LASER_PIN); // Выключить лазер
        return;
    }
    
    // Измерение с аналитом
    float sample_value = readOpticalDensity();
    uart_print("Сигнал с аналитом: ");
    uart_print_float(sample_value);
    uart_println("");
    
    // Выключение лазера
    
    // 3. Расчет оптической плотности
    if (baseline <= 0 || sample_value <= 0) {
        uart_println("Ошибка: значения должны быть больше 0");
        A0_value = 0;
    } else {
        float ratio = sample_value / baseline;
        if (ratio <= 0) {
            uart_println("Ошибка: недопустимое отношение сигналов");
            A0_value = 0;
        } else {
            // Расчет оптической плотности по формуле: A = -ln(I/I0) / l
            A0_value = -log(ratio) / cuvet_length;
            uart_print("Оптическая плотность A: ");
            uart_print_float(A0_value);
            uart_println("");
        }
    }
    
    showPostMeasurementMenu();
}

float readOpticalDensity() {
    // Включение лазера
    PORTD |= (1 << LASER_PIN);
    uint32_t sum = 0;
    ADMUX = (1 << REFS0) | (PHOTO_PIN & 0x07);
    
    for (uint8_t i = 0; i < 100; i++) {
        ADCSRA |= (1 << ADSC);
        while (ADCSRA & (1 << ADSC));
        sum += ADC;
        _delay_ms(10);
    }
    PORTD &= ~(1 << LASER_PIN); // Выключить лазер
    return sum / 100.0;
}

bool waitForUserConfirmation() {
    uint32_t timeout = 30000; // 30 секунд таймаут
    uint32_t start_time = 0;
    
    while (start_time++ < timeout) {
        if (UCSR0A & (1 << RXC0)) {
            char c = UDR0;
            if (c == '1') {
                return true;
            }
        }
        _delay_ms(1);
    }
    uart_println("\nТаймаут! Операция отменена");
    return false;
}

void showPostMeasurementMenu() {
    uart_println("\nВыберите действие:");
    uart_println("1. Повторить измерение");
    uart_println("2. Вернуться в главное меню");
    uart_print("> ");
    
    uint32_t start_time = 0;
    while (start_time++ < 30000) { // 30 секунд таймаут
        if (UCSR0A & (1 << RXC0)) {
            char input = UDR0;
            if (input == '1') {
                measurementProcedure();
                return;
            } else if (input == '2') {
                showMainMenu();
                _delay_ms(100);
                return;
            }
        }
        _delay_ms(1);
    }
    uart_println("Таймаут! Возврат в главное меню");
}
