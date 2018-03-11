#!/usr/bin/python3
import sys
import time
import json
import statistics
import datetime
import os.path
import RPi.GPIO as GPIO
from hx711 import HX711  # https://github.com/tatobari/hx711py
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

from scaleconfig import scaleConfigs
from scaleconfig import THING
from scaleconfig import GROUP
from scaleconfig import ENDPOINT

LOGFILE = "/var/log/scale.log"

## Debug mode (verbose)
#FAST_SAMPLE_PERIOD = 1
#SLOW_SAMPLE_PERIOD = 5 

# Regular mode
FAST_SAMPLE_PERIOD = 10
SLOW_SAMPLE_PERIOD = 180

UPDATES_PER_READ = 5 # scale readings per mqtt result

def cleanAndExit():
    GPIO.cleanup()
    myMQTTClient.unsubscribe("device/+/tare")
    myMQTTClient.disconnect()
    print ("%s: Bye!" % datetime.datetime.now())
    sys.exit()

def tareScale(scaleConfig):
    scaleConfig['tare_offset'] = hx.tare()
    print ("%s: Tare Value: %.2f" % (datetime.datetime.now(), scaleConfig['tare_offset']))

def getScaleConfig(name):
    global scaleConfigs
    for config in scaleConfigs:
        if (config['name'] == name):
            return config

def handleIncoming(client, userdata, message):
    path = message.topic.split("/")
    if (len(path) == 3):
        if (path[2] == "tare"):
            config = getScaleConfig(path[2])
            if config is not None:
                tareScale(config)
            else:
                print("Invalid Scale: %s" % path[2])
        else:
            print("Received unkown message topic: ")
            print(message.topic)
    else:
        print("Received invalid topic name: ")
        print(message.topic)
    

data = [[], []]
mqtt = [[], []]
updates = 0
scaleDevices = []

certdir = "aws_certs"
if (len(sys.argv) > 1):
    certdir = sys.argv[1];

if ((not os.path.isfile(certdir + "/VeriSign-Class 3-Public-Primary-Certification-Authority-G5.pem")) or
    (not os.path.isfile(certdir + "/affd2b97c0-private.pem.key")) or
    (not os.path.isfile(certdir + "/affd2b97c0-certificate.pem.crt")) ):
    print("Error: Could not find aws certificates in: " + certdir);
    print("Usage: " + sys.argv[0] + " [aws certs dir]");
    sys.exit(-1)

sys.stdout = sys.stderr = open(LOGFILE, 'a')

# Initialize Scales
for config in scaleConfigs:
    print("%s: Initializing %s (%d,%d) [%d/%d]" %
          (datetime.datetime.now(), config['name'],
           config['clk_gpio'], config['data_gpio'],
           config['ref_unit'], config['tare_offset']))
    hx = HX711(config['data_gpio'], config['clk_gpio'])
    hx.set_reading_format("LSB", "MSB")
    hx.set_reference_unit(config['ref_unit'])
    hx.reset()
    hx.set_tare(config['tare_offset'])
    scaleDevices.append(hx)

# Initialize MQTT session
myMQTTClient = AWSIoTMQTTClient(THING)
myMQTTClient.configureEndpoint(ENDPOINT, 8883)
myMQTTClient.configureCredentials(certdir + "/VeriSign-Class 3-Public-Primary-Certification-Authority-G5.pem",
                                  certdir + "/affd2b97c0-private.pem.key",
                                  certdir + "/affd2b97c0-certificate.pem.crt")
myMQTTClient.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
myMQTTClient.configureDrainingFrequency(2)  # Draining: 2 Hz
myMQTTClient.configureConnectDisconnectTimeout(10)  # 10 sec
myMQTTClient.configureMQTTOperationTimeout(5)  # 5 sec
print ("%s: Connect to MQTT endpiont: %s  thing: %s" %
       (datetime.datetime.now(), ENDPOINT, THING))
myMQTTClient.connect()
myMQTTClient.subscribe("device/+/tare", 1, handleIncoming)

sleep_time = FAST_SAMPLE_PERIOD
while True:
    try:
        updates += 1
        # Read each scale
        i = 0
        while i < len(scaleDevices):
            val = scaleDevices[i].get_weight(5)
            data[i].append(val)

            while len(data[i]) > UPDATES_PER_READ:
                data[i].pop(0)

            print ("%s: %s:  %.1f kg    [Val: %.2f  Size: %d/%d  period: %d]" %
                    (datetime.datetime.now(), scaleConfigs[i]['name'], statistics.median(data[i]) / 1000.0,
                     val, len(data[i]), UPDATES_PER_READ, sleep_time))
            scaleDevices[i].power_down()
            scaleDevices[i].power_up()
            i += 1

        if (updates % UPDATES_PER_READ) == 0:
            # Send a single MQTT message with all of the scale readings
            sleep_time = SLOW_SAMPLE_PERIOD
            message = {}
            j = 0
            while j < len(scaleDevices):
                scalename = scaleConfigs[j]['name']
                timestamp = int(time.time())
                weight = round(statistics.median(data[j])[0], 1)
                message[scalename] = dict()
                message[scalename]['thing'] = THING
                message[scalename]['group'] = GROUP
                message[scalename]['timestamp'] = timestamp
                message[scalename]['weight'] = weight
                messageJson = json.dumps(message)

                # Save last 5 reports to check std deviation.  If there is
                # a big change on any scale, then increase sampling rate.
                mqtt[j].append(weight)
                while len(mqtt[j]) > 5:
                    mqtt[j].pop(0)
                if (len(mqtt[j]) > 1):
                    stdev = statistics.stdev(mqtt[j])
                    if (stdev > 10):
                        sleep_time = FAST_SAMPLE_PERIOD
                    print ("stdev: %.2f  sample rate: %d" % (stdev, sleep_time));
                j += 1
            myMQTTClient.publish("device/" + THING + "/data", messageJson, 1)
            print ("%s: MQTT send to device/%s/data: %s" % (datetime.datetime.now(), THING, messageJson))

        sys.stdout.flush()
        sys.stderr.flush()
        os.fsync(sys.stdout.fileno())
        os.fsync(sys.stderr.fileno())
        time.sleep(sleep_time)
    except (KeyboardInterrupt, SystemExit):
        cleanAndExit()
