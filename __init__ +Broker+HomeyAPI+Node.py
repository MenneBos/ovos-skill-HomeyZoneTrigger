from ovos_workshop.decorators import intent_handler
from ovos_workshop.intents import IntentBuilder
from ovos_utils import classproperty
from ovos_utils.log import LOG
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.skills.ovos import OVOSSkill
import subprocess
import os
import json
import requests
import time
import re
from collections import deque
import paho.mqtt.client as mqtt
from difflib import get_close_matches

DEFAULT_SETTINGS = {
    "log_level": "INFO"
}

class HomeyZoneSkill(OVOSSkill):
    #def __init__(self, *args, **kwargs):
    #    super().__init__(*args, **kwargs)
    #    self.override = True
    
    def initialize(self):
        """Initialize the skill."""
        # Use settings in .config/mycroft/skills/ovos-skill-homeyzonetrigger/settings.json
        self.settings.merge(DEFAULT_SETTINGS, new_only=True)
        # set a callback to be called when settings are changed
        self.settings_change_callback = self.on_settings_changed

        # Load configuration from config.json
        #self.config_path = os.path.join(self.root_dir, "nodejs", "config.json")
        self.config_path = os.path.expanduser("~/.config/ovos_skill_homeyzonetrigger/config.json")
        self.config = self._load_config()

        # Extract values from the configuration (safe extraction)
        self.n8n_address = self.config.get("n8n", {}).get("address", "")
        self.homey_address = self.config.get("homey", {}).get("address", "")
        self.homey_token = self.config.get("homey", {}).get("token", "")
        self.broker_url = self.config.get("broker", {}).get("url", "")
        self.broker_login = self.config.get("broker", {}).get("login", "")
        self.broker_password = self.config.get("broker", {}).get("password", "")
        self.nodejs_start_zone = os.path.expanduser(self.config.get("nodejs", {}).get("start_zone", ""))
        self.nodejs_get_zone = os.path.expanduser(self.config.get("nodejs", {}).get("get_zone", ""))


        # Device/topic info (safe extraction)
        self.device_name = self.config.get("device", {}).get("name", "")
        self.secret = self.config.get("device", {}).get("secret", "")
        self.naam_geclaimd = self.config.get("device", {}).get("naam_geclaimd", False)
        self.topics = self.config.get("topics", {})

 
        ###### to be solved to run in english mode, standard Dutch ######
        self.language = "nl-nl"
        #self.log.info(f"✅ Detected language: {self.language}")
        if self.language.lower() == "nl-nl":
            self.intent_dir = os.path.join(self.root_dir, "locale", "nl-nl", "intents")
        elif self.language.lower() == "en-us":
            self.intent_dir = os.path.join(self.root_dir, "locale", "en-us", "intents")
        else:
            self.log.error("❌ No valid langauge (nl-nl or en-us detected in mycroft.conf).")

        # Ensure configuration is loaded before setting up MQTT
        if not self.broker_url:
            self.log.error("❌ broker_url is missing in config.json. MQTT setup skipped.")
            return
        # Set up MQTT after configuration is loaded
        self._setup_mqtt()

        # Other initialization tasks
        self.zone_mapping_path = os.path.expanduser("~/.config/ovos_skill_homeyzonetrigger/zone_mappings.json")

        # Remove all existing .intent files
        self.clear_intent_files()

        # Recreate .intent files based on zone_mappings.json
        self.recreate_intent_files()

        # Register all .intent files so the Python script can use the intent
        self.register_all_intents()

    def on_settings_changed(self):
        """This method is called when the skill settings are changed."""
        LOG.info("Settings changed!")

    @property
    def log_level(self):
        """Dynamically get the 'log_level' value from the skill settings file.
        If it doesn't exist, return the default value.
        This will reflect live changes to settings.json files (local or from backend)
        """
        return self.settings.get("log_level", "INFO")   

    def _load_config(self):
        """Load the configuration file."""
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                self.log.info(f"✅ Loaded config.json")
                return config
        except Exception as e:
            self.log.error(f"❌ Failed to load config.json: {e}")
            return {}

    def _save_config(self):
        """Save the current config to the config.json file."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
            self.log.info("✅ config.json updated and saved.")
        except Exception as e:
            self.log.error(f"❌ Failed to save config.json: {e}")

    def clear_intent_files(self):
        """Remove all existing .intent files in the intent directory."""
        try:
            if os.path.exists(self.intent_dir):
                for intent_file in os.listdir(self.intent_dir):
                    if intent_file.endswith(".intent"):
                        intent_file_path = os.path.join(self.intent_dir, intent_file)
                        os.remove(intent_file_path)
                        self.log.info(f"✅ Verwijderd .intent-bestand: {intent_file}")
            else:
                self.log.warning(f"⚠️ Intent directory '{self.intent_dir}' bestaat niet.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het verwijderen van .intent-bestanden: {e}")

    def recreate_intent_files(self):
        """Recreate .intent files based on the current zone_mappings.json."""
        try:
            # Load the zone_mappings.json file
            if os.path.exists(self.zone_mapping_path):
                with open(self.zone_mapping_path, "r") as f:
                    mappings = json.load(f)

                # Create .intent files for each zone
                for zon_name, zone_data in mappings.items():
                    self.create_intent_file(zon_name, zone_data.get("sentences", []))
            else:
                self.log.warning(f"⚠️ Zone mappings file '{self.zone_mapping_path}' bestaat niet.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het opnieuw aanmaken van .intent-bestanden: {e}")

    def register_all_intents(self):
        """Register all .intent files so the Python script can use the intent."""
        try:
            if not os.path.exists(self.intent_dir):
                self.log.warning(f"⚠️ Intent directory '{self.intent_dir}' does not exist.")
                return

            for intent_file in os.listdir(self.intent_dir):
                if intent_file.endswith(".intent"):
                    intent_name = os.path.splitext(intent_file)[0]  # Remove the .intent extension
                    self.register_intent(intent_file, self.handle_start_zone)
                    self.log.info(f"✅ Intent '{intent_name}' registered.")
        except Exception as e:
            self.log.error(f"❌ Error registering intents: {e}")

    def restart_ovos_service():
        try:
            subprocess.run(["systemctl", "restart", "ovos"], check=True)
            print("✅ OVOS service restarted successfully.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to restart OVOS service: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

    def _setup_mqtt(self):
        try:
            # MQTT broker details
            BROKER = self.broker_url
            self.log.info(f"✅ Show the BROKER URL {BROKER}")
            # Extract host and port from broker_url
            if "://" in BROKER:
                BROKER = BROKER.split("://")[1]
            if ":" in BROKER:
                host, port = BROKER.split(":")
                port = int(port)
            else:
                host = BROKER
                port = 8884  # default websocket secure port

            USERNAME = self.broker_login
            PASSWORD = self.broker_password

            # Callback when the client connects to the broker
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    self.log.info("✅ Connected to HiveMQ broker")
                    if not self.naam_geclaimd:
                        client.subscribe(f"nieuw/{self.device_name}")
                    else:
                        self._subscribe_device_topics()
                    client.subscribe("namenlijst/request")
                else:
                    self.log.error(f"❌ Failed to connect to broker, return code {rc}")

            # Create MQTT client
            self.client = mqtt.Client(transport="websockets")
            self.client.username_pw_set(USERNAME, PASSWORD)
            self.client.tls_set()  # Enable TLS

            # Assign callbacks
            self.client.on_connect = on_connect
            self.client.on_message = self._on_mqtt_message

            # Connect to the broker
            self.client.connect(host, port)

            # Start the MQTT loop
            self.client.loop_start()
            self.log.info("✅ MQTT client setup complete and connected to HiveMQ broker")
        except Exception as e:
            self.log.error(f"❌ Error setting up MQTT client: {e}")   

    # MQTT to subscribe to the topics of a device
    def _subscribe_device_topics(self):
        for topic in self.topics.values():
            self.client.subscribe(topic)

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode().strip()  # Decode the payload and strip whitespace
            self.log.info(f"✅ MQTT topic {topic} and payload {payload} en message {msg}")
            if payload:
                    try:
                        payload_json = json.loads(payload)
                    except Exception:
                        payload_json = payload
            else:
                payload_json = {}

            # Naam claimen
            if topic == f"nieuw/{self.device_name}" and not self.naam_geclaimd:
                try:
                    nieuwe_naam = payload_json.get("nieuwe_naam")
                    secret = payload_json.get("secret")
                except Exception:
                    self.client.publish(f"{self.device_name}/NaamError", "Ongeldig payload-formaat")
                    return

                if secret != self.secret:
                    self.client.publish(f"{self.device_name}/NaamError", "Secret ongeldig")
                    return

                # Naam claimen en topics updaten
                self.device_name = nieuwe_naam
                self.config["device"]["name"] = nieuwe_naam
                self.config["device"]["naam_geclaimd"] = True
                for key in self.topics:
                    self.topics[key] = f"{nieuwe_naam}/{key}"
                self.config["topics"] = self.topics
                self._save_config()
                self.naam_geclaimd = True
                self.client.unsubscribe(f"nieuw/{self.device_name}")
                self._subscribe_device_topics()
                self.client.publish(f"{nieuwe_naam}/NaamOk", "ok")
                return

            # Zone mapping topics
            for func, tpc in self.topics.items():
                if topic == tpc:
                    if func == "request_zone_mappings":
                        self._send_zone_mappings()
                    elif func == "save_zone_mappings":
                        self._save_zone_mappings(payload_json)
                    elif func == "request_zones":
                        self._request_zones(payload_json)
                    # Add more handlers as needed

        except Exception as e:
            self.log.error(f"❌ Fout bij verwerken MQTT-bericht: {e}") 
            self.speak("Er ging iets mis bij het verwerken van het MQTT-bericht.")

    def _send_zone_mappings(self):
        try:
            with open(self.zone_mapping_path, "r") as f:
                mappings = json.load(f)
            self.client.publish(self.topics.get("send_zone_mappings", "send_zone_mappings"), json.dumps(mappings))
            self.log.info("✅ Zone mappings verzonden.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het verzenden van zone mappings: {e}")

    def _save_zone_mappings(self, payload):
        try:
            # Sanitize zone names in the payload
            sanitized_payload = {}
            for zone_name, zone_data in payload.items():
                # Sanitize the zone name (remove spaces, convert to lowercase, replace special characters)
                sanitized_name = zone_name.replace(" ", "_").lower()
                sanitized_payload[sanitized_name] = zone_data

            # Overwrite the zone_mappings.json file with sanitized zone names
            with open(self.zone_mapping_path, "w") as f:
                json.dump(sanitized_payload, f, indent=2)

            # Update .intent files using sanitized zone names
            self.update_intent_files(sanitized_payload)

            # Restart OVOS service to retrain Padatious
            self.restart_ovos_service()

            self.client.publish(self.topics.get("saved_zone_mappings", "saved_zone_mappings"), json.dumps({"status": "success"}))
            self.log.info("✅ Zone mappings opgeslagen en intent-bestanden bijgewerkt.")
        except Exception as e:
            self.client.publish(self.topics.get("saved_zone_mappings", "saved_zone_mappings"), json.dumps({"status": "failure", "error": str(e)}))
            self.log.error(f"❌ Fout bij het opslaan van zone mappings: {e}")

    def _request_zone(self, payload):
        try:
            search_string = payload.get("name", "")
            args = ["node", self.nodejs_get_zone, search_string]
            script_dir = os.path.dirname(self.nodejs_get_zone)

            result = subprocess.run(args, cwd=script_dir, capture_output=True, text=True, check=True)
            #args = ["node", self.nodejs_get_zone, search_string]
            self.log.info("✅ Start the subprocess for Homey API.")
            #result = subprocess.run(args, capture_output=True, text=True, check=True)
            zones = json.loads(result.stdout.strip())

            # Check payload size
            payload_size = len(json.dumps(zones))
            self.log.info(f"Payload size: {payload_size} bytes")

            self.client.publish(self.topics.get("send_zone", "send_zone"), json.dumps(zones))
            self.log.info("✅ Zones verzonden.")
        except subprocess.CalledProcessError as e:
            self.log.error(f"❌ Fout bij ophalen van zones: {e.stderr}")
        except Exception as e:
            self.log.error(f"❌ Fout bij verwerken van zones: {e}")

    def update_intent_files(self, mappings):
        """Update .intent files based on the current zone mappings."""
        try:
            # Ensure the intent directory exists
            os.makedirs(self.intent_dir, exist_ok=True)

            # Get the current list of .intent files
            existing_intent_files = set(os.listdir(self.intent_dir))

            # Track the intent files that should exist
            required_intent_files = set()

            for zone_name, zone_data in mappings.items():
                intent_file_name = f"{zone_name}.intent"
                required_intent_files.add(intent_file_name)

                # Write or update the .intent file
                self.create_intent_file(zone_name, zone_data.get("sentences", []))

            # Delete .intent files that are no longer needed
            for intent_file in existing_intent_files - required_intent_files:
                zone_name = os.path.splitext(intent_file)[0]
                self.delete_intent_file(zone_name)

            self.log.info(f"✅ .intent-bestand aangeapst voor zone: {zone_name}")

        except Exception as e:
            self.log.error(f"❌ Fout bij het bijwerken van intent-bestanden: {e}")

    def create_intent_file(self, zone_name, sentences):
        """Create or update a .intent file for the given zone."""
        try:
            # Sanitize the zone_name to remove unwanted characters
            sanitized_zone_name = zone_name.replace("'", "").replace(" ", "_")

            # Ensure the intent directory exists
            os.makedirs(self.intent_dir, exist_ok=True)

            # Define the path for the .intent file
            intent_file_path = os.path.join(self.intent_dir, f"{sanitized_zone_name}.intent")

            # Write the sentences to the .intent file
            with open(intent_file_path, "w") as f:
                for sentence in sentences:
                    f.write(sentence + "\n")

            self.log.info(f"✅ .intent-bestand aangemaakt voor zone: {sanitized_zone_name}")
        except Exception as e:
            self.log.error(f"❌ Fout bij het aanmaken van .intent-bestand voor zone '{zone_name}': {e}")

    def delete_intent_file(self, zone_name):
        """Verwijder het .intent-bestand voor de gegeven zone."""
        try:
            intent_file_path = os.path.join(self.intent_dir, f"{zone_name}.intent")
            if os.path.exists(intent_file_path):
                os.remove(intent_file_path)
                self.log.info(f"✅ .intent-bestand verwijderd voor zone: {zone_name}")
            else:
                self.log.warning(f"⚠️ .intent-bestand voor zone '{zone_name}' niet gevonden.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het verwijderen van .intent-bestand voor zone '{zone_name}': {e}")

    def restart_ovos_service(self):
        """Restart the OVOS service to re-train Padatious."""
        try:
            subprocess.run(["systemctl", "--user", "restart", "ovos.service"], check=True)
            self.log.info("✅ OVOS service succesvol herstart.")
        except subprocess.CalledProcessError as e:
            self.log.error(f"❌ Fout bij het herstarten van de OVOS-service: {e}")
        except Exception as e:
            self.log.error(f"❌ Onverwachte fout bij het herstarten van de OVOS-service: {e}")

    #@intent_handler(IntentBuilder("homey.intent"))
    def handle_start_zone(self, message):
        # Extract the utterance from the message
        utterance = message.data.get("utterance", "").strip().lower()

        # Fallback to the first item in 'utterances' if 'utterance' is empty
        if not utterance and "utterances" in message.data and message.data["utterances"]:
            utterance = message.data["utterances"][0].strip().lower()

        self.log.info(f"✅ Selected utterance: '{utterance}'")

        try:
            # Load the zone_mappings.json file
            with open(self.zone_mapping_path, "r") as f:
                mappings = json.load(f)
        except Exception as e:
            self.log.error(f"❌ Kan zone_mappings.json niet laden: {e}")
            if self.language.lower() == "nl-nl":
                self.speak("Er ging iets mis bij het openen van de instellingen.")
            else:
                self.speak("Something went wrong while opening the settings.") 
            return

        # Flatten the sentences in zone_mappings.json for fuzzy matching
        sentence_to_zone = {}
        for zone_name, zone_data in mappings.items():
            for sentence in zone_data.get("sentences", []):
                sentence_to_zone[sentence.lower()] = zone_name

        """
        # Use fuzzy matching to find the closest sentence
        all_sentences = list(sentence_to_zone.keys())
        closest_matches = get_close_matches(utterance, all_sentences, n=1, cutoff=0.6)


        if not closest_matches:
            if self.language.lower() == "nl-nl":
                self.speak("Ik weet niet welke actie ik moet uitvoeren voor '{utterance}'.")
            else:
                self.speak("Not sure which flow to start for '{utterance}'.") 
            self.log.error(f"❌ Geen overeenkomende zin gevonden voor utterance: '{utterance}'")
            return
        """

        # Get the flow name from the closest matching sentence
        #closest_sentence = closest_matches[0]
        #flow_name = sentence_to_flow[closest_sentence]
        zone_info = mappings[zone_name]
        zone_id = zone_info.get("id")
        if not zone_id:
            if self.language.lower() == "nl-nl":
                self.speak(f"Ik weet niet welke actie ik moet uitvoeren voor '{zone_name}'.")
            else:
                self.speak(f"Not sure which zone to start for '{zone_name}'.")
            self.log.error(f"❌ Geen id gevonden voor zone: '{zone_name}'")
            return

        self.log.info(f"✅ Het pad naar start_zone.js is {self.nodejs_start_zone}")
        # Stel het pad in naar het Node.js-script en geef de zone-id door als argument
        args = ["node", self.nodejs_start_zone, zone_id]
        script_dir = os.path.dirname(self.nodejs_start_zone)  # Get the directory of the script


        # Je JSON-body als Python dict
        data = {
            "model": "gemma3:4b",
            "messages": [
                {"role": "system", "content": "Je bent een smarthome-assistent. Geef JSON terug {zone, capability, value}."},
                {"role": "user", "content": "kan je de lichten uit schakelen in de garage"}
            ],
            "stream": False
        }

        # Headers, voeg hier Authorization toe als dat nodig is
        headers = {
            "Content-Type": "application/json",
        }

        # POST request versturen
        response = requests.post(self.n8n_address, headers=headers, json=data)

        # Response afdrukken
        print(response.status_code)
        print(response.text)