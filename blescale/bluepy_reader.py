# Install blupy with:
#    sudo apt-get install python-pip libglib2.0-dev
#    sudo pip install bluepy

COMPLETE_LOCAL_NAME = 0x09
WEIGHT_MEASUREMENT_CHAR = '00002a9d-0000-1000-8000-00805f9b34fb'

from bluepy.btle import Scanner, DefaultDelegate, Peripheral, ADDR_TYPE_RANDOM

def from_bytes (data, big_endian = True):
    if isinstance(data, str):
        data = bytearray(data)
    if big_endian:
        data = reversed(data)
    num = 0
    for offset, byte in enumerate(data):
        num += byte << (offset * 8)
    return num

class ScanDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if isNewDev:
            print "  Discovered device", dev.addr
        elif isNewData:
            print "  Update from", dev.addr

class ReadCharacteristicDelegate(DefaultDelegate):
    def __init__(self):
        DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        print "Scale #%d  %.1f Kg" % ((cHandle - 0x2b) / 3, (((from_bytes(data)&0xFFFF)*5)/1000.0))

print "Scanning devices..."
scanner = Scanner().withDelegate(ScanDelegate())
devices = scanner.scan(5.0)
print ""

for dev in devices:
    if dev.getValueText(COMPLETE_LOCAL_NAME) == 'kegscale':
        periph = Peripheral(dev.addr, addrType=ADDR_TYPE_RANDOM)
        periph.setDelegate(ReadCharacteristicDelegate())

        print "Found kegscale.  Services Available:"
        for service in periph.getServices():
            print "%s [%s]" % (service.uuid.getCommonName(), service.uuid)
            print "--------------------------------------------------------------------------------"
            for char in service.getCharacteristics():
                print "%45s : %s [0x%x]" % (char.uuid.getCommonName(), char.propertiesToString(), char.properties)
                if char.uuid == WEIGHT_MEASUREMENT_CHAR:
                    # Enable indications on Weight Measurement Characteristics
                    periph.writeCharacteristic(char.getHandle() + 1, b"\x02\x00", withResponse=True)
            print ""

        while True:
            if periph.waitForNotifications(60):
                continue
