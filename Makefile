MCU = atmega328p
F_CPU = 16000000
PORT = /dev/cu.usb*
BAUD = 57600
PROGRAMMER = arduino

TARGET = main
SRC = ./srs/$(TARGET).c

CC = avr-gcc
OBJCOPY = avr-objcopy

CFLAGS = -Os -DF_CPU=$(F_CPU) -mmcu=$(MCU) -std=gnu99
LDFLAGS = -mmcu=$(MCU) -lm

all:
	$(CC) $(CFLAGS) -c $(SRC) -o $(TARGET).o
	$(CC) $(LDFLAGS) $(TARGET).o -o $(TARGET).elf
	$(OBJCOPY) -O ihex -R .eeprom $(TARGET).elf $(TARGET).hex

upload:
	@PORT_ACTUAL=$$(ls $(PORT) 2>/dev/null | head -n1); \
	if [ -z "$$PORT_ACTUAL" ]; then echo "🔌 Port not found!"; exit 1; fi; \
	echo "📤 Uploading to $$PORT_ACTUAL..."; \
	avrdude -v -p $(MCU) -c $(PROGRAMMER) -P "$$PORT_ACTUAL" -b $(BAUD) -U flash:w:$(TARGET).hex:i

clean:
	rm -f *.o *.elf *.hex
