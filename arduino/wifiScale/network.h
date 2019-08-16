#ifndef Network_h
#define Network_h

#include <ESP8266WiFi.h>

class Network
{
  public:
    Network();
    bool isConnected();
    bool connectWifi(const char *ssid, const char *passwd);
    time_t getTime();
  private:
    bool _init;
};

#endif
