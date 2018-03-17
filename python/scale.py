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

# Paramaters for MQTT reporting rate control
# Samples are taken and stored locally.  A median of those samples
# is taken and reported via MQTT.  If the range of sample data has
# a lot of variance (weight change detected), then the mqtt reporting
# rate moves to the higher rate.  If the MQTT data reported has low
# variance (weight has stabalized for some time), then the mqtt reporting
# rate moves to the lower rate.
SAMPLE_PERIOD = 5           # seconds between reading scale data
MAX_SAMPLES_PER_MQTT = 180  # Max samples between MQTT updates (happens with stable weight)
MEDIAN_FILTER_SIZE = 5
MQTT_ALLOWED_VARIANCE = 5   # Variance (in grams) which triggers a new MQTT update

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
    

# Neet to allocate these dynamicaly based on number of scales
data = [[], []]
last_mqtt_report = [0,0];
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

while True:
    try:
        weight_change = False;
        updates += 1
        # Read each scale
        i = 0
        while i < len(scaleDevices):
            val = scaleDevices[i].get_weight(5)[0]
            data[i].append(val)

            while len(data[i]) > MEDIAN_FILTER_SIZE:
                data[i].pop(0)

            print ("%s: %s:  %.1f kg    [Val: %.2f  Size: %d/%d   update: %d/%.1f]" %
                    (datetime.datetime.now(), scaleConfigs[i]['name'], statistics.median(data[i]) / 1000.0,
                     val, len(data[i]), MEDIAN_FILTER_SIZE, updates % MAX_SAMPLES_PER_MQTT, MAX_SAMPLES_PER_MQTT))
            scaleDevices[i].power_down()
            scaleDevices[i].power_up()

            if (abs(statistics.median(data[i]) - last_mqtt_report[i]) > MQTT_ALLOWED_VARIANCE):
                print ("  Detected weight change on %s: delta: %.1f" % (scaleConfigs[i]['name'], statistics.median(data[i]) - last_mqtt_report[i]));
                weight_change = True;
            i += 1

        if ((weight_change == True) or ((updates % MAX_SAMPLES_PER_MQTT) == 0)):
            # Send a single MQTT message with all of the scale readings
            update = {}
            update['state'] = {}
            update['state']['reported'] = {}
            update['state']['reported']['taps'] = []
            j = 0
            while j < len(scaleDevices):
                weight = round(statistics.median(data[j]), 1)
                datapoint = dict()
                datapoint['tap'] = scaleConfigs[j]['name']
                datapoint['thing'] = THING
                datapoint['group'] = GROUP
                datapoint['timestamp'] = int(time.time())
                datapoint['weight'] = weight

                update['state']['reported']['taps'].append(datapoint)

                last_mqtt_report[j] = weight;

                j += 1
            messageJson = json.dumps(update)
            myMQTTClient.publish("$aws/things/" + THING + "/shadow/update", messageJson, 1)
            print ("%s: MQTT send to %s: %s" % (datetime.datetime.now(),
                   "$aws/things/" + THING + "/shadow/update", messageJson))
            updates = 0;


        sys.stdout.flush()
        sys.stderr.flush()
        os.fsync(sys.stdout.fileno())
        os.fsync(sys.stderr.fileno())
        time.sleep(SAMPLE_PERIOD)
    except (KeyboardInterrupt, SystemExit):
        cleanAndExit()
