#!/usr/bin/python3
import sys
import time
import json
import glob
import statistics
import datetime
import argparse
import os.path
import RPi.GPIO as GPIO
from hx711 import HX711  # https://github.com/tatobari/hx711py
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

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

# Globals
# Neet to allocate these dynamicaly based on number of scales
data = [[], []]
last_mqtt_report = [0,0]
updates = 0
scaleDevices = []

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
    global settings
    for config in settings['hx711']:
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
    
def doCalibration(scaleName, calWeight):
    CALIBRATION_SAMPLES = 10
    CALIBRATION_STDEV = 0.0001
    CALIBRATION_SAMPLE_PERIOD = 1
    CALIBRATION_TEST_THRESHOLD = 0.02 #% error allowed (0-1)
    i=0
    scaleConfig=None;
    for config in settings['hx711']:
        if (config['name'] == scaleName):
           scaleConfig = config;
           break;
        i=i+1;
    if (scaleConfig is None):
        print("Error: Could not find config for scale '" + scaleName + "'");
        raise ImportError
    
    print("Running calibration for scale: " + scaleName);
    print("-----------------------------------------------------");
    print("Scale should be empty");

    # set reference to 1
    scaleDevices[i].set_reference_unit(1);

    sys.stdout.write("Measuring");
    while (len(data[i]) < CALIBRATION_SAMPLES):
        val = scaleDevices[i].get_weight(5)[0]
        data[i].append(val)
        sys.stdout.write('.')
        scaleDevices[i].power_down()
        scaleDevices[i].power_up()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    while (statistics.stdev(data[i]) > CALIBRATION_STDEV): 
        print ("  stddev: " + statistics.stdev(data[i]) + "  mean: " + statistics.mean(data[i]));
        val = scaleDevices[i].get_weight(5)[0]
        data[i].append(val)
        data[i].pop(0)
        sys.stdout.write('.')
        scaleDevices[i].power_down()
        scaleDevices[i].power_up()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    empty_meas = statistics.mean(data[i]);

    print("");
    print("Place " + calWeight + " gram weight on scale");
    while (statistics.stdev(data[i]) < 10 * CALIBRATION_STDEV):
        val = scaleDevices[i].get_weight(5)[0]
        data[i].append(val)
        data[i].pop(0)
        scaleDevices[i].power_down()
        scaleDevices[i].power_up()

    sys.stdout.write("Measuring");
    while (statistics.stdev(data[i]) > CALIBRATION_STDEV): 
        print ("  stddev: " + stdev(data[i]));
        val = scaleDevices[i].get_weight(5)[0]
        data[i].append(val)
        data[i].pop(0)
        sys.stdout.write('.')
        scaleDevices[i].power_down()
        scaleDevices[i].power_up()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    cal_meas = statistics.mean(data[i]);
    print("");

    ref_unit = (cal_meas - empty_meas) / calWeight
    printf("empty: " + empty_meas + "   cal: " + cal_meas + "   ref_unit: " + ref_unit);
    scaleDevices[i].set_reference_unit(ref_unit);

    print("Remove weight from scale to tare");
    while (statistics.stdev(data[i]) < 10 * CALIBRATION_STDEV):
        val = scaleDevices[i].get_weight(5)[0]
        data[i].append(val)
        data[i].pop(0)
        scaleDevices[i].power_down()
        scaleDevices[i].power_up()

    sys.stdout.write("Waiting for stability")
    while (statistics.stdev(data[i]) > CALIBRATION_STDEV): 
        print ("  stddev: " + stdev(data[i]));
        val = scaleDevices[i].get_weight(5)[0]
        data[i].append(val)
        data[i].pop(0)
        sys.stdout.write('.')
        scaleDevices[i].power_down()
        scaleDevices[i].power_up()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    scaleConfig['tare_offset'] = scaleDevices[i].tare();
    print("");

    print ("  tare: " + scaleConfig['tare_offset']);

    print("Place " + calWeight + " gram weight on scale to verify");
    while (statistics.stdev(data[i]) < 10 * CALIBRATION_STDEV):
        val = scaleDevices[i].get_weight(5)[0]
        data[i].append(val)
        data[i].pop(0)
        scaleDevices[i].power_down()
        scaleDevices[i].power_up()

    sys.stdout.write("Waiting for stability")
    while (statistics.stdev(data[i]) > CALIBRATION_STDEV): 
        print ("  stddev: " + stdev(data[i]));
        val = scaleDevices[i].get_weight(5)[0]
        data[i].append(val)
        data[i].pop(0)
        sys.stdout.write('.')
        scaleDevices[i].power_down()
        scaleDevices[i].power_up()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    check_weight = statistics.mean(data[i]);
    print("");

    print ("Cailibration weight: " + calWeight);
    print ("Measured weight: " + check_weight);
    if (((calWeight-check_weight)/calWeight) > CALIBRATION_TEST_THRESHOLD):
        print ("Failed calibration")
    else:
        print ("Passed calibration")
        # Write JSON config file back now

    return

parser = argparse.ArgumentParser(description='Read HX711 scale data and report to AWS IOT')
parser.add_argument('-a', '--awscerts', default='aws_certs', help='directory containing AWS certificates')
parser.add_argument('-c', '--config', default='scaleconfig.json', help='configuration file')
parser.add_argument('-w', '--weight', type=int, help='reference weight in grams for calibration mode (also need to specify scale name')
parser.add_argument('-s', '--scale', help='Name of scale to calibrate')
args = parser.parse_args()

#Load config file for AWS and HX711 interface settings
try:
    print("Loading settings from: " + args.config)
    settings = json.load(open(args.config))
    if (('hx711' not in settings) or
        ('endpoint' not in settings) or
        ('group' not in settings) or
        ('thing' not in settings)):
        print("Error: Invalid config file")
        raise ImportError
except:
    print("Error: Could not load JSON configuratin file: " + args.config)
    sys.exit(-1)

# Initialize Scales
for config in settings['hx711']:
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

if (args.weight is not None):
    if (args.scale is None):
        print("Error: Must specify scale name (--scale) to calibrate");
        raise ImportError
    if ((not isinstance(args.weight, int)) or (args.weight < 1000)):
        print("Error: Invalid calibration weight.  Must be >= 1000 (g) ")
        print(isinstance(args.weight, int));
        print("got: " + args.weight)
        raise ImportError
    doCalibration(args.scale, args.weight)
    sys.exit(0)

#Check AWS certificate files
matches = glob.glob(args.awscerts + "/*.pem")
if matches:
    ca_cert = matches[0]
else:
    print("Error: Could not find certificate authority file in " + args.awscerts + "/")
    sys.exit(-1)
matches = glob.glob(args.awscerts + "/*private.pem.key")
if matches:
    priv_key = matches[0]
else:
    print("Error: Could not find private key file in " + args.awscerts + "/")
    sys.exit(-1)
matches = glob.glob(args.awscerts + "/*certificate.pem.crt")
if matches:
    cert = matches[0]
else:
    print("Error: Could not find certificate file in " + args.awscerts + "/")
    sys.exit(-1)

#Redirect the rest to logfile
sys.stdout = sys.stderr = open(LOGFILE, 'a')

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
myMQTTClient.subscribe("device/+/tare", 1, handleIncoming)

while True:
    try:
        weight_change = False
        updates += 1
        # Read each scale
        i = 0
        while i < len(scaleDevices):
            val = scaleDevices[i].get_weight(5)[0]
            data[i].append(val)

            while len(data[i]) > MEDIAN_FILTER_SIZE:
                data[i].pop(0)

            print ("%s: %s:  %.1f kg    [Val: %.2f  Size: %d/%d   update: %d/%.1f]" %
                    (datetime.datetime.now(), settings['hx711'][i]['name'], statistics.median(data[i]) / 1000.0,
                     val, len(data[i]), MEDIAN_FILTER_SIZE, updates % MAX_SAMPLES_PER_MQTT, MAX_SAMPLES_PER_MQTT))
            scaleDevices[i].power_down()
            scaleDevices[i].power_up()

            if (abs(statistics.median(data[i]) - last_mqtt_report[i]) > MQTT_ALLOWED_VARIANCE):
                print ("  Detected weight change on %s: delta: %.1f" % (settings['hx711'][i]['name'], statistics.median(data[i]) - last_mqtt_report[i]))
                weight_change = True
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
                datapoint['tap'] = settings['hx711'][j]['name']
                datapoint['thing'] = settings['thing']
                datapoint['group'] = settings['group']
                datapoint['timestamp'] = int(time.time())
                datapoint['weight'] = weight

                update['state']['reported']['taps'].append(datapoint)

                last_mqtt_report[j] = weight

                j += 1
            messageJson = json.dumps(update)
            myMQTTClient.publish("$aws/things/" + settings['thing'] + "/shadow/update", messageJson, 1)
            print ("%s: MQTT send to %s: %s" % (datetime.datetime.now(),
                   "$aws/things/" + settings['thing'] + "/shadow/update", messageJson))
            updates = 0


        sys.stdout.flush()
        sys.stderr.flush()
        os.fsync(sys.stdout.fileno())
        os.fsync(sys.stderr.fileno())
        time.sleep(SAMPLE_PERIOD)
    except (KeyboardInterrupt, SystemExit):
        cleanAndExit()
