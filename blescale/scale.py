#!/usr/bin/python

import sys
import time
import json
import glob
#import statistics
import datetime
import argparse
import os.path
import threading    # for timer
from struct import unpack

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from bluepy.btle import Scanner, DefaultDelegate, Peripheral, ADDR_TYPE_RANDOM, BTLEException

# Constants
COMPLETE_LOCAL_NAME=0x09
WEIGHT_SCALE_SERVICE='0000181d-0000-1000-8000-00805f9b34fb'
WEIGHT_MEASUREMENT_CHAR='00002a9d-0000-1000-8000-00805f9b34fb'
BASE_HANDLE=0x2b
HANDLES_PER_MEAS_CHAR=3

LOGFILE = "/var/log/scale.log"

class ReadCharacteristicDelegate(DefaultDelegate):
    def __init__(self, sensornames):
        DefaultDelegate.__init__(self)
        self.sensornames = sensornames
        self.thread = threading.Timer(1,SendMQTT)

    def handleNotification(self, cHandle, data):
        # byte 0 is config (ignored because we assume we know it)
        # byte 1-2 is little endian u16 in '5 gram' units
        if (handleToIndex(cHandle) < len(self.sensornames)):
            datapoint = dict()
            datapoint['timestamp'] = int(time.time())
            datapoint['weight'] = unpack('<h', (data[1:]))[0] * 5
            datapoint['thing'] = settings['thing']
            datapoint['group'] = settings['group']
            datapoint['tap'] = self.sensornames[handleToIndex(cHandle)]
            lock.acquire();
            data_queue.append(datapoint);
            lock.release();
            print(datapoint); 
        else:
            print("INVALID reading: #%d : unconfigured tap name" % (handleToIndex(cHandle)))

        # reschedule data upload for 1 second from now
        self.thread.cancel()
        self.thread = threading.Timer(1,SendMQTT)
        self.thread.start()

def SendMQTT():
    # Send a single MQTT message with all of the scale readings like this:
    #  {
    #    "reported": {
    #      "taps": [
    #        {
    #          "weight": 4613.4,
    #          "thing": "RightFridge",
    #          "timestamp": 1524607481,
    #          "tap": "RightFridgeLeftTap",
    #          "group": "FultonKitchen"
    #        },
    #        {
    #          "weight": 1034.9,
    #          "thing": "RightFridge",
    #          "timestamp": 1524607482,
    #          "tap": "RightFridgeRightTap",
    #          "group": "FultonKitchen"
    #        }
    #      ]
    #    }
    #  }

    update = {}
    update['state'] = {}
    update['state']['reported'] = {}
    lock.acquire();
    update['state']['reported']['taps'] = data_queue;

    messageJson = json.dumps(update)
    myMQTTClient.publish("$aws/things/" + settings['thing'] + "/shadow/update", messageJson, 1)
    del data_queue[:]
    lock.release();
    print ("%s: MQTT send to %s: %s" % (datetime.datetime.now(),
           "$aws/things/" + settings['thing'] + "/shadow/update", messageJson))

def waitForNotifications(peripheral):
    print ("Waiting for async events from: %s" % (peripheral.addr))
    while True:
        try:
            peripheral.waitForNotifications(10)
        except BTLEException:
            found = 0
            for dev in devices:
                if (dev['mac'] == peripheral.addr):
                    print ("Handling disconnect from %s [%s]" % (dev['blename'], dev['mac']))
                    dev['connected'] = 0
                    dev['mac'] == ''
                    found = 1
            if (found == 0):
                print ("Disconnect from unkonw device: [%s]" % peripheral.addr)
            return

def handleToIndex(handle):
    return ((int(handle) - BASE_HANDLE) / HANDLES_PER_MEAS_CHAR)

def cleanAndExit():
    myMQTTClient.disconnect()
    print ("%s: Bye!" % datetime.datetime.now())
    sys.exit()

# Globals Variables
devices = [];
data_queue = [];
parser = argparse.ArgumentParser(description='Read BLE scale data and report to AWS IOT')
parser.add_argument('-c', '--config', default='scaleconfig.json', help='configuration file')
args = parser.parse_args()
lock = threading.Lock()

#Load config file for AWS and BLE settings
try:
    print("Loading settings from: " + args.config)
    settings = json.load(open(args.config))
    if (('thing' not in settings) or
        ('endpoint' not in settings) or
        ('group' not in settings) or
        ('scales' not in settings) or
        ('certdir' not in settings)):
        print("Error: Invalid config file")
        raise ImportError
except:
    print("Error: Could not load JSON configuratin file: " + args.config)
    sys.exit(-1)

for reader in settings['scales']:
    device = dict()
    device['blename'] = reader['blename']
    device['sensors'] = reader['sensors']
    device['mac'] = ''
    device['connected'] = 0
    devices.append(device);

print("Setup devices:")
print(devices)

#Check AWS certificate files
matches = glob.glob(settings['certdir'] + "/*.pem")
if matches:
    ca_cert = matches[0]
else:
    print("Error: Could not find certificate authority file in " + settings['certdir'] + "/")
    sys.exit(-1)
matches = glob.glob(settings['certdir'] + "/*private.pem.key")
if matches:
    priv_key = matches[0]
else:
    print("Error: Could not find private key file in " + settings['certdir'] + "/")
    sys.exit(-1)
matches = glob.glob(settings['certdir'] + "/*certificate.pem.crt")
if matches:
    cert = matches[0]
else:
    print("Error: Could not find certificate file in " + settings['certdir'] + "/")
    sys.exit(-1)

##Redirect the rest to logfile
#sys.stdout = sys.stderr = open(LOGFILE, 'a')

# Initialize MQTT session
myMQTTClient = AWSIoTMQTTClient(settings['thing'])
myMQTTClient.configureEndpoint(settings['endpoint'], 8883)
myMQTTClient.configureCredentials(ca_cert, priv_key, cert)
myMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
print ("%s: Connect to MQTT endpiont: %s  thing: %s" %
       (datetime.datetime.now(), settings['endpoint'], settings['thing']))
myMQTTClient.connect()

while True:
    scanner = Scanner()
    for btdev in scanner.scan(5.0):
        for dev in devices:
            if ((dev['connected'] != 1) and
                (btdev.getValueText(COMPLETE_LOCAL_NAME) == dev['blename'])):

                print ("Found '%s - %s'" % (dev['blename'], btdev.addr))

                periph = Peripheral(btdev.addr, addrType=ADDR_TYPE_RANDOM)
                periph.setDelegate(ReadCharacteristicDelegate(dev['sensors']))

                for char in periph.getServiceByUUID(WEIGHT_SCALE_SERVICE).getCharacteristics():
                    if char.uuid == WEIGHT_MEASUREMENT_CHAR:
                        # Enable indications on Weight Measurement Characteristics
                        periph.writeCharacteristic(char.getHandle() + 1, b"\x02\x00", withResponse=True)
                        print ("Enabled indications on %s - %d" % (dev['blename'], handleToIndex(char.getHandle())))

                dev['connected'] = 1
                dev['mac'] = periph.addr
                threading.Thread(target=waitForNotifications, args=[periph]).start()

                print ("")
    time.sleep(10)
