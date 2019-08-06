import random
import time
import sys
import iothub_client
from iothub_client import IoTHubClient, IoTHubClientError, IoTHubTransportProvider, IoTHubClientResult
from iothub_client import IoTHubMessage, IoTHubMessageDispositionResult, IoTHubError, DeviceMethodReturnValue

# !!!! UPDATE CONNECTION_STRING VALUE!!!!
# The device connection string to authenticate the device with your IoT hub.
# Printed by provish.sh script.  Can be manually fetched with:
#   az iot hub device-identity show-connection-string --hub-name {YourIoTHubName} --device-id {YourNodeName} --output table
CONNECTION_STRING = "HostName=SomeIotHubName.azure-devices.net;DeviceId=IotDeviceName;SharedAccessKey=SuperSecretAccessKeyWouldGoHere=="

PROTOCOL = IoTHubTransportProvider.MQTT
MESSAGE_TIMEOUT = 10000
FULL_KEG_WEIGHT = 20000
REPORT_PERIOD_S = 300

#Parse the device id
dbEnvVars = {}
for each in CONNECTION_STRING.split(';'):
        data=each.split('=', maxsplit=1)
        if (len(data) == 2):
                dbEnvVars[data[0]] = data[1]
DEVICE_ID=dbEnvVars['DeviceId']

# JSON message to send to IoT Hub.
MSG_TXT = "{\"timestamp\": %d, \"deviceid\": \"%s\", \"scale\": %d, \"temperature\": %.1f,\"weight\": %d}"

def send_confirmation_callback(message, result, user_context):
    print ( "IoT Hub responded to message with status: %s" % (result) )

def iothub_client_init():
    client = IoTHubClient(CONNECTION_STRING, PROTOCOL)
    return client

def iothub_client_telemetry_sample_run():
    # list of taps with starting keg weights
    taplist = [FULL_KEG_WEIGHT, FULL_KEG_WEIGHT, FULL_KEG_WEIGHT/2, FULL_KEG_WEIGHT/5];
    try:
        client = iothub_client_init()
        while True:
            for tap in range(len(taplist)):
                # 15% change of pouring a 200g-450g beer
                if (random.random() <= 0.15):
                    amount = random.randint(200, 450)
                    taplist[tap] -= amount
                if (taplist[tap] < 0):
                    taplist[tap] = FULL_KEG_WEIGHT; # keg magiclly refills when empty

                temperature = random.random() * 12  # 0-12 C
                msg_txt_formatted = MSG_TXT % \
                   (time.time(), DEVICE_ID, tap, temperature, taplist[tap])
                message = IoTHubMessage(msg_txt_formatted)

                prop_map = message.properties()
                if temperature > 10:
                  prop_map.add("temperatureAlert", "true")
                else:
                  prop_map.add("temperatureAlert", "false")

                # Send the message.
                print( "Sending message: %s" % message.get_string() )
                client.send_event_async(message, send_confirmation_callback, None)
            time.sleep(REPORT_PERIOD_S)

    except IoTHubError as iothub_error:
        print ( "Unexpected error %s from IoTHub" % iothub_error )
        return
    except KeyboardInterrupt:
        print ( "IoTHubClient sample stopped" )

if __name__ == '__main__':
    iothub_client_telemetry_sample_run()
