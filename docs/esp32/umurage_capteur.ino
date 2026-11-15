/*
  UMURAGE — capteur de niveau d'eau pour un forage (ESP32)

  Matériel : ESP32 + capteur ultrasonique étanche JSN-SR04T (ou capteur de pression),
  alimentation solaire 5 V. Le boîtier mesure la distance jusqu'à la surface de l'eau
  et envoie le niveau à l'API UMURAGE toutes les 15 minutes.

  En zone sans Wi-Fi : remplacer l'envoi HTTP par un module LoRa (SX1276) vers une
  passerelle LoRaWAN, qui transmet ensuite à /api/iot/ingestion/ par lot.
*/
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID     = "NomDuReseau";
const char* WIFI_PASSWORD = "MotDePasse";
const char* API_URL       = "https://umurage.example.org/api/iot/ingestion/";
const char* API_KEY       = "remplacer-par-IOT_API_KEY";
const char* CODE_CAPTEUR  = "FOR-MUY-NIV";   // code du capteur créé dans UMURAGE

const int PIN_TRIG = 5;
const int PIN_ECHO = 18;
const float PROFONDEUR_PUITS_M = 8.0;        // distance du capteur au fond du puits
const unsigned long INTERVALLE_MS = 15UL * 60UL * 1000UL;

float mesurerNiveau() {
  float total = 0;
  int valides = 0;
  for (int i = 0; i < 5; i++) {              // moyenne de 5 mesures
    digitalWrite(PIN_TRIG, LOW);  delayMicroseconds(2);
    digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(10);
    digitalWrite(PIN_TRIG, LOW);
    long duree = pulseIn(PIN_ECHO, HIGH, 60000);
    if (duree > 0) { total += duree * 0.000343 / 2.0; valides++; }
    delay(100);
  }
  if (valides == 0) return -1;
  return PROFONDEUR_PUITS_M - total / valides; // hauteur d'eau en mètres
}

void envoyer(float niveau) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  String corps = String("{\"capteur\":\"") + CODE_CAPTEUR + "\",\"valeur\":" + String(niveau, 2) + "}";
  int code = http.POST(corps);
  Serial.printf("Envoi %.2f m -> HTTP %d\n", niveau, code);
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(500);
}

void loop() {
  float niveau = mesurerNiveau();
  if (niveau >= 0) envoyer(niveau);
  // Économie d'énergie : sommeil profond jusqu'à la prochaine mesure
  esp_sleep_enable_timer_wakeup((uint64_t)INTERVALLE_MS * 1000ULL);
  esp_deep_sleep_start();
}
