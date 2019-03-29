#include <Arduino.h>
#include <Q2HX711.h>
#include <RunningMedian.h>
#include <EEPROM.h>
#include <SPI.h>
#include <LowPower.h>
#include <avr/wdt.h>
#include <limits.h>

#include <Adafruit_BluefruitLE_SPI.h>

#define DEBUG                          1    // Enable verbose serial logging

#define MAX_SCALES                     4    // Number of HX711 scale devices connected
#define NUM_SAMPLES                    5    // Number of samples in normal reading's median
#define TARE_SAMPLES                   12   // Number of samples in median durring cal/tare operation

#define SCALE_CMD_TARE                 0x1
#define SCALE_CMD_CAL                  0x2
#define SCALE_CMD_DISABLE              0x3

#define MAX_NAME_LEN                   16   // Max len (including /0) for BLE or scale name
#define VALID_CONFIG                   0xFEEE // Barker marking config element as valid; anything but 0x00 will work
#define DEFAULT_BLE_NAME               "kegscale"
#define ALLOWED_VARIANCE               350  // variance which triggers an MQTT report
#define WEIGHT_CHANGE_REPORTS          8    // consectutive samples before going back to slow rate
#define MAX_SAMPLES_SKIPPED            80   // Max samples before MQTT report is forced

// BT SPI SETTINGS
#define VERBOSE_MODE                   false  // If set to 'true' enables debug output
#define BLUEFRUIT_SPI_CS               8
#define BLUEFRUIT_SPI_IRQ              7
#define BLUEFRUIT_SPI_RST              4

typedef struct scale_config {
  uint16_t valid;
  int32_t offset;
  float slope;
  char name[MAX_NAME_LEN];
} scaleConfig;

struct config {
  uint16_t valid;
  char name[MAX_NAME_LEN];
  scaleConfig scale[MAX_SCALES];
};

struct config g_config;    /* Scale settings saved/retrieved from EEPROM */

RunningMedian samples[MAX_SCALES] = RunningMedian(NUM_SAMPLES);
int32_t last_reported[MAX_SCALES] = {0};

Q2HX711 scales[MAX_SCALES] = {
  Q2HX711(13, 12),
  Q2HX711(11, 10),
  Q2HX711(9, 6),
  Q2HX711(A1, A0)  // GPIO 19/18
};

int32_t scaleCharId[MAX_SCALES];      /* scale weight characteristics ID */
int32_t scaleNameCharId[MAX_SCALES];  /* scale name characteristics ID */
int32_t cmdCharId;
int32_t bleNameCharId;

unsigned int updates = 0;
enum period_t sleep_period;
boolean weight_change = true;
boolean idle_update = false;
bool connected_state = false;
char buffer[256];

/* Notes
    AT+NVMWRITE/AT+NVMREAD   256 byte Non-voltatile storage; don't know how safe it is
    AT+HWMODELED=DISABLE     Save some power
    AT+BLEPOWERLEVEL=[-40, -20, -16, -12, -8, -4, 0, 4] Save power
*/

Adafruit_BluefruitLE_SPI ble(BLUEFRUIT_SPI_CS, BLUEFRUIT_SPI_IRQ, BLUEFRUIT_SPI_RST);

void error(const __FlashStringHelper*err) {
  Serial.println(err);
  while (1);
}

/* Handle incoming BLE GAT changes */
void BleGattRX(int32_t chars_id, uint8_t data[], uint16_t len) {
  uint16_t scale;
  bool need_reset = false;

  if (chars_id == cmdCharId) {
    /* handle incoming command */
    /* 32 bit command meanings:
       bit 18-19 : Command
                   00 - NO-OP
                   01 - tare scale (reset offset)
                   10 - calibrate (calculate slope)
                   11 - disable scale
       bit 16-17 : scale number (0-3)
       bit 0-15  : weight (grams) used in calibration
    */

    uint8_t cmd = (data[2] & 0x0C) >> 2;
    uint8_t scale = data[2] & 0x03;
    uint16_t tare_weight = data[0] + (data[1] << 8);

#if DEBUG
    Serial.print(F("Received command: 0x"));
    Serial.print(cmd, HEX);
    Serial.print(F(" scale="));
    Serial.print(scale);
    Serial.print(F(" weight="));
    Serial.println(tare_weight);
#endif
    if (scale < MAX_SCALES)
    {
      if (cmd == SCALE_CMD_DISABLE)
      {
        Serial.print(F("Disable scale # "));
        Serial.println(scale);
        g_config.scale[scale].valid = 0;
        need_reset = true;
      }
      else if (cmd == SCALE_CMD_CAL)
      {
        Serial.print(F("Got calibrate request on scale # "));
        Serial.print(scale );
        Serial.print(F(" at "));
        Serial.print(tare_weight / 1000.0);
        Serial.println(F("kg"));
        need_reset = calScale(scale, tare_weight);
      }
      else if (cmd == SCALE_CMD_TARE)
      {
        Serial.print(F("Got tare reqeust on scale # "));
        Serial.println(scale);
        calScale(scale, 0);
      }
    }
    else
    {
      Serial.print(F("Error: Invalid scale # "));
      Serial.println(scale);
    }

  /* handle BLE name change */
  } else if (chars_id == bleNameCharId) {
    strncpy(g_config.name, (char *)data, MAX_NAME_LEN-1);
    g_config.name[min(len,MAX_NAME_LEN-1)] = '\0';
    need_reset = true;

  /* handle scale name change */
  } else {
    bool handled = false;
    for (scale = 0; (scale < MAX_SCALES) && !handled; scale++) {
      if (scaleNameCharId[scale] == chars_id) {
        /* name change on a scale */
        strncpy(g_config.scale[scale].name, (char *)data, MAX_NAME_LEN-1);
        g_config.scale[scale].name[min(len,MAX_NAME_LEN-1)] = '\0';
        Serial.print(F("Update scale-"));
        Serial.print(scale);
        Serial.print(F(" name to "));
        Serial.println(g_config.scale[scale].name);
        handled = true;
      }
    }
    if (!handled) {
      Serial.print(F("Error: Unknown GATT characteristic id: "));
      Serial.println(chars_id);
    }
  }

  EEPROM.put(0, g_config);
  if (need_reset)
    reboot();

}

void reboot() {
  Serial.println(F("Rebooting..."));
  ble.println(F("AT+GAPDISCONNECT"));
  ble.end();
  wdt_disable();
  wdt_enable(WDTO_15MS);
  while (1) {}
}

void setup(void)
{
  int32_t scaleServiceId;
  int32_t scaleFeatureCharId;
  int i;

  delay(2000);

  boolean success;

  Serial.begin(115200);

  randomSeed(micros());

  /* Read in configuration */
  EEPROM.get(0, g_config);
  if (g_config.valid != VALID_CONFIG)
  {
    strcpy(g_config.name, DEFAULT_BLE_NAME);
    g_config.valid = VALID_CONFIG;
    for (i = 0; i < MAX_SCALES; i++) {
        sprintf(g_config.scale[0].name, "scale %d", i+1);
    }
    EEPROM.put(0, g_config);
  }
  Serial.print("BLE Name: ");
  Serial.println(g_config.name);
  Serial.println(F("----------------"));

  for (i = 0; i < MAX_SCALES; i++)
  {
    if (g_config.scale[i].valid == VALID_CONFIG)
    {
      Serial.println("");
      Serial.print(F(" Scale #"));
      Serial.print(i);
      Serial.print(F(": "));
      Serial.println(g_config.scale[i].name);
      Serial.println(F("--------------------"));
      Serial.print(F("  Slope: "));
      Serial.println(g_config.scale[i].slope);
      Serial.print(F("  Offset: "));
      Serial.print(g_config.scale[i].offset);
      Serial.print(F("  Valid: 0x"));
      Serial.println(g_config.scale[i].valid, HEX);
    }
  }

  /* Initialize the BT module */
  Serial.print(F("Initializing BLE module: "));
  if ( !ble.begin(VERBOSE_MODE) )
  {
    error(F("Error: couldn't find Bluefruit."));
  }
  Serial.println( F("OK!") );

  /* Perform a factory reset to make sure everything is in a known state */
  Serial.print(F("BLE factory reset: "));
  if (! ble.factoryReset() ) {
    error(F("Couldn't factory reset"));
  }
  Serial.println( F("OK!") );

  /* Disable command echo from Bluefruit */
  ble.echo(false);

  /* Change the device name to make it easier to find */
  Serial.print(F("Setting device name to "));
  Serial.println(g_config.name);
  ble.print( F("AT+GAPDEVNAME=") );
  ble.println( g_config.name );

  /* Add the WeightScale Service definition */
  /* Service ID should be 1 */
  Serial.println(F("Adding the Weight Scale Service definition #1 (UUID = 0x181D): "));
  success = ble.sendCommandWithIntReply( F("AT+GATTADDSERVICE=UUID=0x181D"), &scaleServiceId);
  if (! success) {
    error(F("Could not add Weight service"));
  }

  /* Add the Weight Scale Feature characteristics *

     PROPERTIES 0x02: Read-only
     VALUE 0x38: disable: timestamp, multiple user, BMI, height; resolution = 0.005 kg
  */
  success = ble.sendCommandWithIntReply( F("AT+GATTADDCHAR=UUID=0x2A9E, PROPERTIES=0x02, MIN_LEN=4, MAX_LEN=4, VALUE=38-00-00-00"), &scaleFeatureCharId);
  if (! success) {
    error(F("Could not add Scale Feature characteristic"));
  }

  for (i = 0; i < MAX_SCALES; i++)
  {
    if (g_config.scale[i].valid == VALID_CONFIG) {
      /* Add the Weight Measurement characteristic
         PROPERTIES 0x20: Indicate
         VALUE 0: 0x00: SI units; Disable timestamp, userID, BMI & height
         VALUE 1-2: weight in kg / 0.005 resolution
      */
      success = ble.sendCommandWithIntReply( F("AT+GATTADDCHAR=UUID=0x2A9D, PROPERTIES=0x20, MIN_LEN=3, MAX_LEN=3, VALUE=00-00-00"), &(scaleCharId[i]));
      if (! success) {
        error(F("Could not add Weight Measurement characteristic"));
      }

      /* Add a string characteristic to be used for setting scale name
         PROPERTIES 0x0A: Read/Write
         VALUE: utf-8 string of (MAX_NAME_LEN - 1) chars
      */
      sprintf(buffer, "AT+GATTADDCHAR=UUID=0x2A24, PROPERTIES=0x0A, MIN_LEN=1, MAX_LEN=%d, VALUE=%s, DESCRIPTION=Scale #%d Name", MAX_NAME_LEN-1, g_config.scale[i].name, i);
      success = ble.sendCommandWithIntReply(buffer, &(scaleNameCharId[i]));

      if (! success) {
        error(F("Could not add scale name characteristic"));
      }
    }
  }

  /* Add the custom characteristic for tare & calibration

     PROPERTIES 0x0A: Read/Write
     VALUE:
       bit 18-19 : Command
                   000 - NO-OP
                   001 - tare scale (reset offset)
                   010 - calibrate (calculate slope)
                   011 - disable scale
       bit 16-17 : scale number (0-3)
       bit 0-15  : weight (grams) used in calibration

  */
  success = ble.sendCommandWithIntReply( F("AT+GATTADDCHAR=UUID128=D8-D4-2A-BE-D2-F3-4A-E7-B1-69-21-E5-56-3F-1C-7B, PROPERTIES=0x0A, MIN_LEN=4, MAX_LEN=4, VALUE=0x00"), &cmdCharId);
  if (! success) {
    error(F("Could not add Tare characteristic"));
  }

  /* Add a string characteristic to be used for setting device BLE names
     PROPERTIES 0x0A: Read/Write
     VALUE: utf-8 string of (MAX_NAME_LEN - 1) chars
  */
  sprintf(buffer, "AT+GATTADDCHAR=UUID=0x2A24, PROPERTIES=0x0A, MIN_LEN=1, MAX_LEN=%d, VALUE=%s, DESCRIPTION=BLE Name", MAX_NAME_LEN-1, g_config.name);
  success = ble.sendCommandWithIntReply(buffer, &bleNameCharId);
  if (! success) {
    error(F("Could not add string characteristic"));
  }

  /* Reset the device for the new service setting changes to take effect */
  ble.reset();

  ble.setBleGattRxCallback(cmdCharId, BleGattRX);
  ble.setBleGattRxCallback(bleNameCharId, BleGattRX);
  for (i = 0; i < MAX_SCALES; i++)
  {
    ble.setBleGattRxCallback(scaleNameCharId[i], BleGattRX);
  }
}

void loop(void)
{
  int scale = 0;
  int32_t grams, median;
  uint16_t weight;

  /* Handle any incoming BLE requests */
  ble.handleDfuIrq();

  if (++updates >= MAX_SAMPLES_SKIPPED)
  {
    updates = 0;
    idle_update = true;
#ifdef DEBUG
    Serial.print(millis());
    Serial.print(F(" Scale # "));
    Serial.print(scale);
    Serial.println(F(" Idle too long generate 1 report"));
#endif
  }

  for (scale = 0; scale < MAX_SCALES; scale++)
  {
    if (g_config.scale[scale].valid == VALID_CONFIG)
    {
      int32_t datapoint = scales[scale].read();
      samples[scale].add(datapoint);
      median = samples[scale].getMedian();
#ifdef DEBUG
      Serial.print(millis());
      Serial.print(F(" Scale #"));
      Serial.print(scale);
      Serial.print(F(" Reading #"));
      Serial.print(updates);
      Serial.print(F(": "));
      Serial.print(datapoint);
      Serial.print(F(" Median: "));
      Serial.print(median);
      Serial.print(F(" LastReported: "));
      Serial.print(last_reported[scale]);
      Serial.print(F(" delta: "));
      Serial.print(abs(median - last_reported[scale]));
      Serial.print(F("/"));
      Serial.println(ALLOWED_VARIANCE);
#endif

      /* Check for a signifigant weight change */
      if (abs(median - last_reported[scale]) > ALLOWED_VARIANCE)
      {
#ifdef DEBUG
        Serial.print(millis());
        Serial.print(F(" Scale #"));
        Serial.print(scale);
        Serial.println(F(" Weight changed state"));
#endif
        updates = 0;
        weight_change = true;
        sleep_period = SLEEP_4S;
      }

      if (weight_change || idle_update)
      {
        last_reported[scale] = median;
        grams = (median - g_config.scale[scale].offset) / (float)g_config.scale[scale].slope;

        /* GATT weight measurement is repored as uint16 of weight in 5g units */
        if (grams <= 0)
          weight = 0;
        else
          weight = (uint16_t) (grams / 5.0);

#ifdef DEBUG
        Serial.print(millis());
        Serial.print(F(" Reporting: Scale #"));
        Serial.print(scale);
        Serial.print(F(" median: "));
        Serial.print(median);
        Serial.print(F(" grams: "));
        Serial.print(grams);
        Serial.print(F(" kg: "));
        Serial.print(grams / 1000.0);
        Serial.print(F(" weight counts: "));
        Serial.println(weight);
#endif

        /* AT+GATTCHAR=CharacteristicID,value */
        ble.print( F("AT+GATTCHAR=") );
        ble.print( scaleCharId[scale] );
        ble.print( F(",00-") );
        sprintf(buffer, "%02x", weight & 0xff);
        ble.print(buffer);
        ble.print( F("-") );
        sprintf(buffer, "%02x", weight >> 8);
        ble.println(buffer);

        /* Check if command executed OK */
        if ( !ble.waitForOK() )
        {
          Serial.println(F("Failed to get response!"));
        }
        delay(500); /* seems to need a delay between reports */
      }
    }
  }

  idle_update = false;
  if (updates >= WEIGHT_CHANGE_REPORTS)
  {
#ifdef DEBUG
    Serial.println(F(" Idle state"));
#endif
    weight_change = false;
    sleep_period = SLEEP_4S;
  }
#ifndef DEBUG
  Serial.print(F("."));
#endif

#ifdef DEBUG
  delay(200); /* flush serial prints before going to sleep */
#endif
  
  LowPower.idle(sleep_period, ADC_OFF, TIMER4_OFF, TIMER3_OFF, TIMER1_OFF,
                TIMER0_OFF, SPI_OFF, USART1_OFF, TWI_OFF, USB_OFF);
}

/* 0 passed as reference weight means tare the scale */
/* Return value:
    0 - no new scales provisioned
    1 - New scale provisioned; reset required
*/
int calScale(int scale, int reference)
{
  int i;
  RunningMedian tare_samples = RunningMedian(TARE_SAMPLES);
  bool need_reset = false;
  int32_t before, after;

  if (reference)
  {
    Serial.print(F("Calibrate Scale #"));
  } else {
    Serial.print(F("Tare Scale #"));
  }
  Serial.println(scale);

  /******** Get an empty baseline *************/
  Serial.print(F("Scale should be empty"));
  delay(1000);
  for (i = 0; i < 4 * TARE_SAMPLES; i++ )
  {
    tare_samples.add(scales[scale].read());
    delay(400);
    Serial.print(F("."));
  }
  before = tare_samples.getMedian();
  Serial.println(F(""));

  if (reference)
  {
    /******** Get a reference reading *************/
    Serial.print(F("  Add "));
    Serial.print(reference);
    Serial.println(F(" gram weight now."));
    delay(5000);
    Serial.print(F(" Reading"));
    for (i = 0; i < 4 * TARE_SAMPLES; i++ )
    {
      tare_samples.add(scales[scale].read());
      delay(400);
      Serial.print(F("."));
    }
    after = tare_samples.getMedian();
    Serial.println(F(""));

    /******** Save calculated slope ************/
    g_config.scale[scale].slope = (after - before) / (float) reference;

    if (g_config.scale[scale].valid != VALID_CONFIG)
      need_reset = true;
    g_config.scale[scale].valid = VALID_CONFIG;

#ifdef DEBUG
    Serial.print(F("  Before: "));
    Serial.println(before);
    Serial.print(F("  After: "));
    Serial.println(after);
#endif
    Serial.print(F("  Slope: "));
    Serial.println(g_config.scale[scale].slope);
  }
  g_config.scale[scale].offset = before;

  Serial.print(F("  Tare Offset: "));
  Serial.println(g_config.scale[scale].offset);
  
  return need_reset;
}
