#!/usr/bin/python3
import sys
import time
import json
import glob
import statistics
import datetime
import argparse
import os.path
#import RPi.GPIO as GPIO
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


def cleanAndExit():
    GPIO.cleanup()
    myMQTTClient.disconnect()
    print ("%s: Bye!" % datetime.datetime.now())
    sys.exit()

def getScaleRaw(scaleConfig):
    with open(scaleConfig['iio'], 'r') as iiof:
        return int(iiof.read());

def getScaleReading(scaleConfig):
    val = getScaleRaw(scaleConfig)
    val = val - float(scaleConfig['offset'])
    val = val / float(scaleConfig['gain'])
    return val

def doCalibration(scaleName, calWeight):
    CALIBRATION_SAMPLES = 8
    CALIBRATION_STDEV = 0.13  # 13% of mean
    CALIBRATION_SAMPLE_PERIOD = 1
    CALIBRATION_TEST_THRESHOLD = 0.03 # 3% error
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

    sys.stdout.write("Measuring");
    sys.stdout.flush()
    while ((len(data[i]) < CALIBRATION_SAMPLES) or (statistics.stdev(data[i]) > abs(CALIBRATION_STDEV * (statistics.mean(data[i]))))): 
        data[i].append(getScaleRaw(scaleConfig))
        if (len(data[i]) > CALIBRATION_SAMPLES):
            data[i].pop(0)
        if (len(data[i]) > CALIBRATION_SAMPLES-1):
            print ("  stddev: %.1f  mean: %.1f  threshold: %1.f   data: %s" % (statistics.stdev(data[i]), statistics.mean(data[i]), abs(CALIBRATION_STDEV * statistics.mean(data[i])), tuple(data[i])));
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    empty_meas = statistics.mean(data[i]);
    print("got empty_meas: %.1f" % empty_meas);

    print("");
    print("Place %d gram weight on scale" % calWeight);
    time.sleep(2);
    data[i].clear();
    sys.stdout.write("Measuring");
    sys.stdout.flush()
    while ((len(data[i]) < CALIBRATION_SAMPLES) or (statistics.stdev(data[i]) > 18000)):
        data[i].append(getScaleRaw(scaleConfig))
        if (len(data[i]) > CALIBRATION_SAMPLES):
            data[i].pop(0)
        if (len(data[i]) > CALIBRATION_SAMPLES-1):
            print ("  stddev: %.1f  mean: %.1f  threshold: %1.f   data: %s" % (statistics.stdev(data[i]), statistics.mean(data[i]), abs(CALIBRATION_STDEV * statistics.mean(data[i])), tuple(data[i])));
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    cal_meas = statistics.mean(data[i]);
    print("got cal_meas: %.1f" % cal_meas);
    print("");

    gain = (cal_meas - empty_meas) / calWeight
    print("empty: %.1f   cal: %.1f   gain: %.1f" % (empty_meas, cal_meas, gain));
    if (gain == 0):
        print("Invalid measurements empty=%d  calibrated=%d" % (empty_meas, cal_meas))
        sys.exit()
        
    scaleConfig['gain'] = gain
    print("DZ: set gain to %f" % gain);

    print("Remove weight from scale to tare");
    time.sleep(2);
    data[i].clear();
    sys.stdout.write("Waiting for stability")
    sys.stdout.flush()
    while ((len(data[i]) < CALIBRATION_SAMPLES) or (statistics.stdev(data[i]) > abs(CALIBRATION_STDEV * (statistics.mean(data[i]))))): 
        data[i].append(getScaleRaw(scaleConfig))
        if (len(data[i]) > CALIBRATION_SAMPLES):
            data[i].pop(0)
        if (len(data[i]) > CALIBRATION_SAMPLES-1):
            print ("  stddev: %.1f  mean: %.1f  threshold: %1.f   data: %s" % (statistics.stdev(data[i]), statistics.mean(data[i]), abs(CALIBRATION_STDEV * statistics.mean(data[i])), tuple(data[i])));
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    scaleConfig['offset'] = statistics.mean(data[i]);
    print("got offset: %.1f" % scaleConfig['offset']);
    print("");

    print("Place %d gram weight on scale to verify" % calWeight);
    time.sleep(2);
    data[i].clear();
    sys.stdout.write("Waiting for stability")
    sys.stdout.flush()
    while ((len(data[i]) < CALIBRATION_SAMPLES) or (statistics.stdev(data[i]) > abs(CALIBRATION_STDEV * (statistics.mean(data[i]))))): 
        data[i].append(getScaleReading(scaleConfig))
        if (len(data[i]) > CALIBRATION_SAMPLES):
            data[i].pop(0)
        if (len(data[i]) > CALIBRATION_SAMPLES-1):
            print ("  stddev: %.1f  mean: %.1f  threshold: %1.f   data: %s" % (statistics.stdev(data[i]), statistics.mean(data[i]), abs(CALIBRATION_STDEV * statistics.mean(data[i])), tuple(data[i])));
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(CALIBRATION_SAMPLE_PERIOD)
    check_weight = statistics.mean(data[i]);
    print("");

    print ("Cailibration weight: %.1f" % calWeight);
    print ("Measured weight: %.1f" % check_weight);
    if (((calWeight-check_weight)/calWeight) > CALIBRATION_TEST_THRESHOLD):
        print ("Failed calibration")
    else:
        print ("Passed calibration")
        # Write JSON config file back now
        with open(args.config, "w") as f:
            json.dump(settings, f);

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

# Globals Variables
updates = 0

# Create lists of lists to hold data for each scale
data = [[] for x in range(len(settings['hx711']))]
last_mqtt_report = [[] for x in range(len(settings['hx711']))]

# Validate scale configs
#for config in settings['hx711']:
#    print("%s: Validating %s" % (datetime.datetime.now(), config['name']))
#    hx = HX711(config['data_gpio'], config['clk_gpio'])
#    hx.set_reading_format("LSB", "MSB")
#    hx.set_reference_unit(config['gain'])
#    hx.reset()
#    hx.set_tare(config['offset'])
#    scaleDevices.append(hx)

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

while True:
    try:
        weight_change = False
        updates += 1
#         Read each scale
        i = 0
        for config in settings['hx711']:
            print("DZ going to get scale reading with:");
            print(config);
            val = getScaleReading(config)
            data[i].append(val)

            while len(data[i]) > MEDIAN_FILTER_SIZE:
                data[i].pop(0)

            print ("%s: %s:  %.1f kg    [Val: %.2f  Size: %d/%d   update: %d/%.1f]" %
                    (datetime.datetime.now(), settings['hx711'][i]['name'], statistics.median(data[i]) / 1000.0,
                     val, len(data[i]), MEDIAN_FILTER_SIZE, updates % MAX_SAMPLES_PER_MQTT, MAX_SAMPLES_PER_MQTT))

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
            while j < len(data):
                print("DZ: j=%d data: %s\n" % (j, data))
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
