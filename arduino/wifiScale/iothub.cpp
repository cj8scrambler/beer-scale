#include <Arduino.h>
#include "common.h"
#include "iothub.h"

//#define DEBUG                          1      // Enable verbose serial logging

static void connectionCallback(IOTHUB_CLIENT_CONNECTION_STATUS result,
                               IOTHUB_CLIENT_CONNECTION_STATUS_REASON reason,
                               void* user_context);
static void sendCallback(IOTHUB_CLIENT_CONFIRMATION_RESULT result,
                         void *userContextCallback);

IotHub::IotHub()
{
    _refcount = 0;
    _connected = false;
    _iotHubClientHandle = NULL;
}

bool IotHub::workPending()
{
    IOTHUB_CLIENT_STATUS status;
    IoTHubClient_LL_GetSendStatus(_iotHubClientHandle, &status);
#ifdef DEBUG
    Serial.printf("status: %s  outstanding messages: %d\r\n",
                  (status == IOTHUB_CLIENT_SEND_STATUS_BUSY)?"busy":"idle",
                  _refcount);
#endif
    return (status == IOTHUB_CLIENT_SEND_STATUS_BUSY);
}

void IotHub::doWork()
{
#ifdef DEBUG
    Serial.printf("%d - %s()\r\n", millis(), __func__);
#endif
    IoTHubClient_LL_DoWork(_iotHubClientHandle);
}

/* returns true on success */
bool IotHub::init(const char *connection_string, const char *device_name)
{
    int rc;

    if (_iotHubClientHandle != NULL)
    {
        Serial.println("Error: iothub already initialized\r\n");
        return false;
    }
    _iotHubClientHandle = IoTHubClient_LL_CreateFromConnectionString(connection_string, MQTT_Protocol);

    if (_iotHubClientHandle == NULL)
    {
        Serial.println("Failed on IoTHubClient_LL_CreateFromConnectionString.");
        return false;
    }

    IoTHubClient_LL_SetOption(_iotHubClientHandle, "product_info", device_name);
    IoTHubClient_LL_SetConnectionStatusCallback(_iotHubClientHandle, connectionCallback, &_connected);
    return true;
}

void IotHub::sendMessage(char *buffer)
{
    IOTHUB_MESSAGE_HANDLE messageHandle = IoTHubMessage_CreateFromByteArray((const unsigned char *)buffer, strlen(buffer));
    if (messageHandle == NULL)
    {
        Serial.println("Unable to create a new IoTHubMessage.");
    }
    else
    {
#ifdef DEBUG
        Serial.printf("Sending message: %s.\r\n", buffer);
#endif
        if (IoTHubClient_LL_SendEventAsync(_iotHubClientHandle, messageHandle, sendCallback, &_refcount) != IOTHUB_CLIENT_OK)
        {
            Serial.println("Failed to hand over the message to IoTHubClient.");
        }
        else
        {
            _refcount++;
#ifdef DEBUG
            Serial.printf("Message queued for delivery. (%d outstanding)\r\n", _refcount);
#endif
        }
        IoTHubMessage_Destroy(messageHandle);
    }
}

static void sendCallback(IOTHUB_CLIENT_CONFIRMATION_RESULT result, void *userContextCallback)
{
    uint32_t *refcount = (uint32_t *)userContextCallback;

    if ((IOTHUB_CLIENT_CONFIRMATION_OK == result) && (refcount != NULL))
    {
        (*refcount)--;
#ifdef DEBUG
        Serial.printf("Message succesfully sent to Azure IoT Hub\r\n");
#endif
    }
    else
    {
        Serial.println("Failed to send message to Azure IoT Hub");
    }
}

static void connectionCallback(IOTHUB_CLIENT_CONNECTION_STATUS result, IOTHUB_CLIENT_CONNECTION_STATUS_REASON reason, void* user_context)
{
    bool *connected = (bool *)user_context;
    if (connected != NULL)
    {
        if (result == IOTHUB_CLIENT_CONNECTION_AUTHENTICATED)
        {
#ifdef DEBUG
            printf("CONNECTED STATE: %s -> connected (%d)\r\n", (*connected)?"connected":"disconnected", result);
#endif
            *connected = true;
        }
        else
        {
#ifdef DEBUG
            printf("CONNECTED STATE: %s -> disconnected (%d)\r\n", (*connected)?"connected":"disconnected", result);
#endif
            *connected = false;
        }
    }
}

