PORT := "/dev/ttyUSB0"
BOARD := esp8266:esp8266:huzzah

SRC = $(wildcard *.ino)
SRC += $(wildcard *.cpp)
DEP = $(wildcard *.h)

DIRNAME:=$(shell basename $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST)))))
TARGET=$(DIRNAME).$(subst :,.,$(BOARD))


all: $(TARGET).elf

$(TARGET).elf: $(TARGET).bin

$(TARGET).bin: $(SRC) $(DEP)
	arduino-cli compile --fqbn $(BOARD)

.PHONY: upload
upload: $(TARGET).elf
	test -e $(PORT) || { echo "Port not found!"; exit 1; }
	arduino-cli upload  --fqbn $(BOARD) -p $(PORT)

.PHONY: clean
clean:
	rm -f $(TARGET).elf $(TARGET).bin
