#include "MCUFRIEND_kbv.h"
MCUFRIEND_kbv tft;
#include <TouchScreen.h>
#include <ArduinoJson.h>


const int XP=6,XM=A2,YP=A1,YM=7; //ID=0x9341
const int TS_LEFT=210,TS_RT=860,TS_TOP=160,TS_BOT=880;

TouchScreen ts = TouchScreen(XP, YP, XM, YM, 300);

#define MINPRESSURE 100
#define MAXPRESSURE 1000

int16_t BOXSIZE;
int16_t PENRADIUS = 1;
uint16_t ID, oldcolor, currentcolor;
uint8_t Orientation = 3;

#define BLACK   0x0000
#define BLUE    0x001F
#define RED     0xF800
#define GREEN   0x07E0
#define CYAN    0x07FF
#define MAGENTA 0xF81F
#define YELLOW  0xFFE0
#define WHITE   0xFFFF

const int btnCount = 4;
int selectedBtn = 0;
Adafruit_GFX_Button btns[btnCount];

int id = 2;

unsigned long time_clicked = 0;

char line[256];
int pos;
int prev_state;
uint16_t xpos, ypos;

void setup(void) {
  Serial.begin(115200);
  tft.reset();
  ID = tft.readID();
  tft.begin(ID);
  tft.setRotation(Orientation);
  tft.fillScreen(BLACK);
  Serial.println("{\"type\": \"reset\"}");
}

void loop() {
  while(Serial.available()) {
    line[pos] = Serial.read();
    if(line[pos] == '\n' || line[pos] == '\r') {
      line[pos] = '\0';
      StaticJsonDocument<256> doc;
      deserializeJson(doc, line);

      const char *widget = doc["widget"];
      if(strcmp(widget, "time") == 0) {
        tft.setTextSize(8);
        tft.setCursor(35, 50);
        tft.setTextColor(YELLOW, BLACK);
        tft.print((const char*) doc["state"]);
      } else if(strcmp(widget, "btn") == 0) {
        int num = doc["num"];
        btns[num].initButton(&tft,  doc["x"], doc["y"], doc["width"], 60, WHITE, doc["state"] ? YELLOW : CYAN, BLACK, doc["label"], 2);
        btns[num].drawButton(false);
      }

      Serial.println("{\"type\": \"ack\"}");
      pos = 0;
    } else {
      pos = (pos + 1) % sizeof(line);
    }
  }

  bool down = false;

  TSPoint tp;
  tp.x = tp.y = 0;
  int count = 6;
  int pressedCount = 0;
  for(int i = 0; i < count; i++) {
    TSPoint t = ts.getPoint();
    if(t.z >= MINPRESSURE) {
      pressedCount++;
      tp.x += t.x;
      tp.y += t.y;
    }
  }
  if(pressedCount) {
    tp.x /= pressedCount;
    tp.y /= pressedCount;
  }
  pinMode(XM, OUTPUT);
  pinMode(YP, OUTPUT);

  down = pressedCount > 0;

  switch (Orientation) {
    case 0:
      xpos = map(tp.x, TS_LEFT, TS_RT, 0, tft.width());
      ypos = map(tp.y, TS_TOP, TS_BOT, 0, tft.height());
      break;
    case 1:
      xpos = map(tp.y, TS_TOP, TS_BOT, 0, tft.width());
      ypos = map(tp.x, TS_RT, TS_LEFT, 0, tft.height());
      break;
    case 2:
      xpos = map(tp.x, TS_RT, TS_LEFT, 0, tft.width());
      ypos = map(tp.y, TS_BOT, TS_TOP, 0, tft.height());
      break;
    case 3:
      xpos = map(tp.y, TS_BOT, TS_TOP, 0, tft.width());
      ypos = map(tp.x, TS_LEFT, TS_RT, 0, tft.height());
      break;
  }

//  tft.drawRect(xpos, ypos, 2, 2, WHITE);

    if(prev_state != down) {
      if(down) {
        selectedBtn = -1;

        for(int i = 0; i < btnCount; i++) {
          if(btns[i].contains(xpos, ypos)) {
            selectedBtn = i;
            btns[i].drawButton(true);
            StaticJsonDocument<128> doc;
            doc["type"] = "btn_click";
            doc["num"] = i;
            serializeJson(doc, Serial);
            Serial.println();
            break;
          }
        }
      } else {
        if(selectedBtn >= 0) {
          btns[selectedBtn].drawButton();
        }
      }
    }

  prev_state = down;
}

