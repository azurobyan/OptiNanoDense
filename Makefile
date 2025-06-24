MCU = atmega328p
F_CPU = 16000000
PORT = /dev/cu.usbserial*
BAUD = 57600
PROGRAMMER = arduino
CFLAGS = -Os -DF_CPU=16000000UL -mmcu=atmega328p -std=gnu99

TARGET = main
SRC = $(TARGET).c

CC = avr-gcc
OBJCOPY = avr-objcopy

CFLAGS = -Os -DF_CPU=$(F_CPU) -mmcu=$(MCU)

all:
	$(CC) $(CFLAGS) -c $(SRC) -o $(TARGET).o
	$(CC) $(CFLAGS) $(TARGET).o -o $(TARGET).elf
	$(OBJCOPY) -O ihex -R .eeprom $(TARGET).elf $(TARGET).hex

upload:
	@PORT_ACTUAL=$$(ls $(PORT) 2>/dev/null | head -n1); \
	if [ -z "$$PORT_ACTUAL" ]; then echo "🔌 Port not found!"; exit 1; fi; \
	echo "📤 Uploading to $$PORT_ACTUAL..."; \
	avrdude -v -p $(MCU) -c $(PROGRAMMER) -P "$$PORT_ACTUAL" -b $(BAUD) -U flash:w:$(TARGET).hex:i

clean:
	rm -f *.o *.elf *.hex
