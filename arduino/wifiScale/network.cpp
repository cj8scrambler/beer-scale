#include "common.h"
#include <time.h>
#include "network.h"

//#define DEBUG                          1      // Enable verbose serial logging
#define WIFI_WAIT_SEC                   8
#define TIME_WAIT_SEC                   5
#define MIN_EPOCH     (49 * 365 * 24 * 3600)  // 1/1/2019

Network::Network()
{
    _init = false;
}

bool Network::isConnected()
{
    return (_init && (WiFi.status() == WL_CONNECTED));
}

bool Network::connectWifi(const char *ssid, const char *pass)
{
    int attempts = 0;
    time_t epochTime = 0;

    if (_init && WiFi.status() == WL_CONNECTED)
    {
        return true;
    }
#ifdef DEBUG
    Serial.print("Connecting to SSID:");
    Serial.println(ssid);
    //Serial.setDebugOutput(true);
#endif

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);
    _init = true;
    delay(500);
    while ((attempts++ < (WIFI_WAIT_SEC * 2)) && (WiFi.status() != WL_CONNECTED))
    {
#ifdef DEBUG
        Serial.print(".");
#endif
        delay(500);
    }
#ifdef DEBUG
    //Serial.setDebugOutput(false);
    Serial.println("");
#endif

    if (attempts >= (WIFI_WAIT_SEC * 2)) {
        Serial.printf("Unable to connect to wifi %s.\r\n", ssid);
        return false;
    }

#ifdef DEBUG
    Serial.println("Updating time");
#endif
    attempts = 0;
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
    while ((attempts++ < (TIME_WAIT_SEC * 2)) && (epochTime < MIN_EPOCH))
    {
#ifdef DEBUG
        Serial.println("");
#endif
        delay(500);
        epochTime = time(NULL);
    }

    if (attempts >= (TIME_WAIT_SEC * 2)) {
        Serial.printf("Unable to get time\r\n");
        return false;
    }

#ifdef DEBUG
    Serial.printf("Connected to: %s   Time: %d\r\n", ssid, epochTime);
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
#endif
    return true;
}

time_t Network::getTime(void)
{
    return (time(NULL));
}
