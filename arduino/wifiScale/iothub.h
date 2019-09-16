#ifndef IotHub_h
#define IotHub_h

#include <AzureIoTHub.h>
#include <AzureIoTProtocol_MQTT.h>

class IotHub
{
  public:
    IotHub();
    bool init(const char *connection_string, const char *device_name);
    void sendMessage(char *buffer);
    bool workPending();
    void doWork();

  private:
    IOTHUB_CLIENT_LL_HANDLE _iotHubClientHandle;
    uint32_t _refcount;
    bool _connected;
};

#endif
