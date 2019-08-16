#include "common.h"

/* set I2C mux position (negative: disable all) */
void setmux(int position)
{
  uint8_t val;

  if (NUM_ADC == 1)
    return;

  if (position < 0) {
    val = 0;
  } else if (position < NUM_ADC) {
    val = (1 << position);
  } else {
    Serial.print(F("Invalid mux position: "));
    Serial.println(position);
    return;
  }
  
#ifndef SIMULATED
  Wire.beginTransmission(I2C_MUX_ADDR);
  Wire.write(byte(val));
  Wire.endTransmission();
#endif
}

void hang(const char *message)
{
  Serial.println(message);
  while (1)
  {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(1000);
    digitalWrite(LED_BUILTIN, LOW);
    delay(1000);
  }
}

/* Promt the user, then read a string back.  Reading ends when max limit
 * reached, timeout occurs or CR encountered.  Newline is printed at the end
 *
 *    prompt   - message to present to user
 *    buf      - location to store user input
 *    maxLen   - buf length
 *    timeout  - timeout waiting for user input (returns data entered so far)
 *    hide     - 1: show '*'; 0: show user input
 */
bool readFromSerial(char * prompt, char * buf, int maxLen, int timeout, bool hide)
{
    unsigned long begintime = millis();
    bool timedout = false;
    int loc=0;
    char newchar;

    if(maxLen <= 0)
    {
        // nothing can be read
        return false;
    }

    /* consume all the pending serial data first */
    while (0xFF != (newchar = Serial.read())) {
      delay(5);
    };

    Serial.print(prompt);
    do {
        while (0xFF == (newchar = Serial.read())) {
            delay(10);
            if ((timeout > 0) && ((millis() - begintime) >= timeout)) {
              break;
            }
        }
        buf[loc++] = newchar;
        if (hide)
            Serial.print('*');
        else
            Serial.print((char)buf[loc-1]);

        if (timeout > 0)
            timedout = ((millis() - begintime) >= timeout);
      
      /* stop at max length, CR or timeout */
    } while ((loc < maxLen) && (buf[loc-1] != '\r') && !timedout);

    /* If carriage return was cause of the break, then erase it */
    if ((loc > 0) && (buf[loc-1] == '\r')) {
        loc--;
    }

    /* NULL terminate if there's room, but sometimes 1 single char is passed */
    if (loc < maxLen)
        buf[loc] = '\0';

    Serial.println("");
    return true;
}
