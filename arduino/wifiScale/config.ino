//#define DEBUG                          1      // Enable verbose serial logging

#include <EEPROM.h>
#include "common.h"

#define MAX_LINE_SIZE  CONNECTION_STRING_LEN

systemConfig *g_config;               // Scale settings saved/retrieved from EEPROM

#ifdef DEBUG
void dumpConfig(void)
{
  uint8_t *ptr = EEPROM.getDataPtr();
#if 0
  Serial.println("config raw data:");
  for(int i=0; i < sizeof(systemConfig); i++) {
    Serial.printf("%02x ", ptr[i]);
    if (i%16 == 15)
      Serial.println();
  }
  Serial.println();
#endif
  Serial.printf("ssid: [%s] (offset %d)\r\n", g_config->ssid, (((uint8_t *)&(g_config->ssid))-ptr));
  Serial.printf("pass: [%s] (offset %d)\r\n", g_config->pass, (((uint8_t *)&(g_config->pass))-ptr));
  Serial.printf("connection: [%s] (offset %d)\r\n", g_config->connection, (((uint8_t *)&(g_config->connection))-ptr));
  Serial.printf("deviceid: [%s] (offset %d)\r\n", g_config->deviceid, (((uint8_t *)&(g_config->deviceid))-ptr));
  for(int adc_offset = 0; adc_offset < NUM_ADC; adc_offset++)
  {
    for(int chan = 0; chan < NUM_CHAN_PER_ADC; chan++)
    {
      int scalenum = adc_offset * NUM_CHAN_PER_ADC + chan;
      Serial.printf("  scale-%d enabled: %d (offset %d)\r\n",
                    scalenum, g_config->scaledata[scalenum].enabled,
                    (((uint8_t *)&(g_config->scaledata[scalenum].enabled))-ptr));
      Serial.printf("  scale-%d slope: %.2f (offset %d)\r\n",
                    scalenum, g_config->scaledata[scalenum].slope,
                    (((uint8_t *)&(g_config->scaledata[scalenum].slope))-ptr));
      Serial.printf("  scale-%d offset: %d (offset %d)\r\n",
                    scalenum, g_config->scaledata[scalenum].offset,
                    (((uint8_t *)&(g_config->scaledata[scalenum].offset))-ptr));
      Serial.printf("  scale-%d last_weight: %d (offset %d)\r\n",
                    scalenum, g_config->scaledata[scalenum].last_weight,
                    (((uint8_t *)&(g_config->scaledata[scalenum].last_weight))-ptr));
      Serial.printf("  scale-%d updates: %d (offset %d)\r\n",
                    scalenum, g_config->scaledata[scalenum].updates,
                    (((uint8_t *)&(g_config->scaledata[scalenum].updates))-ptr));
    }
  }
}
#endif

void initConfig()
{
  EEPROM.begin(sizeof(systemConfig));

  g_config = (systemConfig *)EEPROM.getDataPtr();

#ifdef DEBUG
  Serial.printf("Loaded %d bytes of data from EEPROM\r\n", sizeof(systemConfig));
  dumpConfig();
#endif

  if ((g_config->ssid[0] == '\0') ||
      (g_config->pass[0] == '\0') ||
      (g_config->connection[0] == '\0') ||
      (g_config->deviceid[0] == '\0'))
  {
#ifdef DEBUG
  Serial.println("Forcing RECONFIG based on missing data");
#endif
    reconfig();
  }
}

void reconfig()
{
  int i;
  char buff[MAX_LINE_SIZE];
  int adc_offset, chan;

  snprintf(buff, MAX_LINE_SIZE, "SSID [%s]: ", g_config->ssid);
  readFromSerial(buff, buff, SSID_LEN, 0, false);
  if (strlen(buff))
  {
    strcpy(g_config->ssid, buff);
  }

  snprintf(buff, MAX_LINE_SIZE, "Password [%s] :", g_config->ssid);
  strcpy(buff, "Password [");
  for (i = 0; i < strlen(g_config->pass); i++)
  {
    strcat(buff, "*");
  }
  strcat(buff, "]: ");
  readFromSerial(buff, buff, PASS_LEN, 0, true);
  if (strlen(buff)) {
    strcpy(g_config->pass, buff);
  }

  Serial.println("Azure IOT device connection string can be obtained from Azure portal at:");
  Serial.println("  IOT Hub-> IOT Devices -> [Device ID] -> Primary Connection String");
  Serial.println("or with az CLI command: ");
  Serial.println("  az iot hub device-identity show-connection-string --hub-name [IOT Hub Name] --device [Device Node Name] --query \"connectionString\"");
  snprintf(buff, MAX_LINE_SIZE, "Connection String [%s]: ", g_config->connection);
  readFromSerial(buff, buff, CONNECTION_STRING_LEN, 0, false);
  if (strlen(buff))
  {
    strcpy(g_config->connection, buff);
  }

  /* Need to extract DeviceId from connection string.  Format should be:
   *  HostName=SomeIotHubName.azure-devices.net;DeviceId=IotDeviceName;SharedAccessKey=SuperSecretAccessKeyWouldGoHere==
   */
  bool parsed_deviceid = false;
  char *ptr = strstr(g_config->connection, "DeviceId=");
  if (ptr) {
    int before_len, match_len = 0;
    ptr += strlen("DeviceId=");
    before_len = ptr - g_config->connection;
    while ((ptr[match_len] != '/0') && (ptr[match_len] != ';') &&
           ((before_len + match_len) < CONNECTION_STRING_LEN)) { match_len++; }
    if (match_len < DEVICEID_MAX_LEN)
    {
      strncpy(g_config->deviceid, ptr, match_len);
      g_config->deviceid[match_len] = '\0';
      parsed_deviceid = true;
#ifdef DEBUG
      Serial.printf("Parsed DeviceID: %s\r\n", g_config->deviceid);
#endif
    }
  }

  if (!parsed_deviceid) {
    hang("Error parsing deviceid from connection string");
  }

  for(adc_offset = 0; adc_offset < NUM_ADC; adc_offset++)
  {
    for(chan = 0; chan < NUM_CHAN_PER_ADC; chan++)
    {
      char result;
      int scalenum = adc_offset * NUM_CHAN_PER_ADC + chan;

      if (g_config->scaledata[scalenum].enabled)
      {
        sprintf(buff, "Enable Scale #%d [ADC-%d / Channel %d]? [Y/n] ",
                scalenum, adc_offset, chan);
      } else {
        sprintf(buff, "Enable Scale #%d [ADC-%d / Channel %d]? [y/N] ",
                scalenum, adc_offset, chan);
      }
      readFromSerial(buff, &result, 1, 0, false);
      if (!g_config->scaledata[scalenum].enabled && result == '\0') {
          result = 'n';
      }
      if (result == 'N' || result == 'n')
      {
        g_config->scaledata[scalenum].enabled = false;
      } else {
        g_config->scaledata[scalenum].enabled = true;
        if (g_config->scaledata[scalenum].slope == 0.0)
        {
            Serial.printf("Calibration required on scale #%d\r\n", scalenum);
        } else {
          sprintf(buff, "Recalibrate Scale #%d [ADC-%d / Channel %d]? [y/N] ",
                  scalenum, adc_offset, chan);
          readFromSerial(buff, &result, 1, 0, false);
          if (result == 'Y' || result == 'y')
          {
            /* setting slope to 0.0 (invalid) forces recal when instantiated */
            g_config->scaledata[scalenum].slope = 0.0;
          }
        }
      }
    }
  }
}

void saveSettings()
{
#ifdef DEBUG
  Serial.printf("Saving %d bytes of data to EEPROM:\r\n", sizeof(systemConfig));
  dumpConfig();
#endif
  EEPROM.commit();
}
