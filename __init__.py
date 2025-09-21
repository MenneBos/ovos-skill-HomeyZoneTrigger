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
        # Im not using the Homey API package as the API has no one command to alter all lights
        #self.nodejs_start_zone = os.path.expanduser(self.config.get("nodejs", {}).get("start_zone", ""))
        #self.nodejs_get_zone = os.path.expanduser(self.config.get("nodejs", {}).get("get_zone", ""))


        # Device/topic info (safe extraction)
        #self.device_name = self.config.get("device", {}).get("name", "")
        #self.secret = self.config.get("device", {}).get("secret", "")
        #self.naam_geclaimd = self.config.get("device", {}).get("naam_geclaimd", False)
        #self.topics = self.config.get("topics", {})

 
        ###### to be solved to run in english mode, standard Dutch ######
        self.language = "nl-nl"
        #self.log.info(f"✅ Detected language: {self.language}")
        if self.language.lower() == "nl-nl":
            self.vocab_dir = os.path.join(self.root_dir, "locale", "nl-nl", "vocab")
        elif self.language.lower() == "en-us":
            self.vocab_dir = os.path.join(self.root_dir, "locale", "en-us", "vocab")
        else:
            self.log.error("❌ No valid langauge (nl-nl or en-us detected in mycroft.conf).")

        # Ensure configuration is loaded before setting up MQTT
        #f not self.broker_url:
        #    self.log.error("❌ broker_url is missing in config.json. MQTT setup skipped.")
        #    return
        # Set up MQTT after configuration is loaded
        #self._setup_mqtt()

        # Other initialization tasks
        self.zone_mapping_path = os.path.expanduser("~/.config/ovos_skill_homeyzonetrigger/zone_mappings.json")

        # Remove all existing .voc files
        self.clear_voc_files()

        # Recreate .voc files based on zone_mappings.json
        self.create_zone_voc_files()

        # Register all .voc files so the Python script can use the vocab
        # !!!! dont think it is needs with intentbuilder 
        # self.register_all_vocabs()

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

    def clear_voc_files(self):
        """Remove all existing .voc files in the vocab directory."""
        try:
            if os.path.exists(self.vocab_dir):
                for voc_file in os.listdir(self.vocab_dir):
                    if voc_file == "zone.voc":
                        voc_file_path = os.path.join(self.vocab_dir, voc_file)
                        os.remove(voc_file_path)
                        self.log.info(f"✅ Verwijderd zone.voc-bestand")
            else:
                self.log.warning(f"⚠️ Intent directory '{self.intent_dir}' bestaat niet.")
        except Exception as e:
            self.log.error(f"❌ Fout bij het verwijderen van .intent-bestanden: {e}")

    def create_zone_voc_files(self):
        """Create .voc files directly from http response."""

        url = f"{self.homey_address}/api/manager/zones/zone"
        headers = {
            "Authorization": f"Bearer {self.homey_token}",
            "Content-Type": "application/json"
        }

        try:
            # GET request to Homey API  
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            # Parse JSON response
            zones = response.json()

            # Load the zone_mappings.json file
            if os.path.exists(self.zone_mapping_path):
                with open(self.zone_mapping_path, "w", encoding="utf-8") as f:
                  json.dump(zones, f, indent=4, ensure_ascii=False)

                self.log.info("✅ Zones saved to zone_mapping.json")
                zone_names = [z["name"] for z in zones.values()]

                # Zet alle namen in lowercase
                zone_names = [z["name"].lower() for z in zones.values()]

                # Ensure directory exists
                os.makedirs(os.path.dirname(self.vocab_dir), exist_ok=True)
                
                # Build full file path inside the directory
                voc_file = os.path.join(self.vocab_dir, "zones.voc")

                with open(voc_file, "w", encoding="utf-8") as f:
                    for name in zone_names:
                        f.write(name + "\n")

                self.log.info(f"✅ Saved {len(zone_names)} zones to {voc_file}")

            else:
                self.log.warning(f"⚠️ Zone mappings file '{self.zone_mapping_path}' bestaat niet.")

        except Exception as e:
            self.log.error(f"❌ Unexpected error fetching zones: {e}")

    """
    def register_all_intents(self):
        #Register all .voc files so the Python script can use the intent.
        try:
            if not os.path.exists(self.vocab_dir):
                self.log.warning(f"⚠️ Vocabulary directory '{self.vocab_dir}' does not exist.")
                return

            for voc_file in os.listdir(self.vocab_dir):
                if voc_file.endswith(".voc"):
                    voc_name = os.path.splitext(voc_file)[0]  # Remove the .voc extension
                    self.register_intent(voc_file, self.handle_start_zone)
                    self.log.info(f"✅ Intent '{voc_name}' registered.")
        except Exception as e:
            self.log.error(f"❌ Error registering intents: {e}")

    def restart_ovos_service(self):
        #Restart the OVOS service to re-train Padatious.
        try:
            subprocess.run(["systemctl", "--user", "restart", "ovos.service"], check=True)
            self.log.info("✅ OVOS service succesvol herstart.")
        except subprocess.CalledProcessError as e:
            self.log.error(f"❌ Fout bij het herstarten van de OVOS-service: {e}")
        except Exception as e:
            self.log.error(f"❌ Onverwachte fout bij het herstarten van de OVOS-service: {e}")

            """


    @intent_handler(IntentBuilder("homeyZone.intent").require("zones").require("licht"))
    def handle_start_zone(self, message):
        # Extract the utterance from the message
        utterance = message.data.get("utterance", "").strip().lower()

        # Fallback to the first item in 'utterances' if 'utterance' is empty
        if not utterance and "utterances" in message.data and message.data["utterances"]:
            utterance = message.data["utterances"][0].strip().lower()

        self.log.info(f"✅ Selected utterance: '{utterance}'")

        """
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
        """

        # Je JSON-body als Python dict
        data = {
            "model": "gemma3:4b",
            "messages": [
                {"role": "system", "content": "Je bent een smarthome-assistent. Geef JSON terug {zone, capability, value}."},
                {"role": "user", "content": utterance}
            ],
            "stream": False
        }

        # Headers, voeg hier Authorization toe als dat nodig is
        headers = {
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(self.n8n_address, headers=headers, json=data)

            response.raise_for_status()  # Raise an error for bad status codes
            result = response.json()
            self.log.info(f"✅ n8n response: {result}")

        except requests.exceptions.RequestException as e:
            self.log.error(f"❌ HTTP fout: {e}")

