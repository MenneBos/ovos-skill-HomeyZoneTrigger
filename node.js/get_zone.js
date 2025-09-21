import { HomeyAPI } from 'homey-api';
import fs from 'fs';
import os from 'os';
import path from 'path';

// Load configuration from user config directory
const configPath = path.join(os.homedir(), '.config', 'ovos_skill_homeyzonetrigger', 'config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const searchString = process.argv[2] || "";
console.log("Directory to config file:", configPath);

async function getFilteredZones() {
  try {
    // Connect to the Homey API
    const homeyApi = await HomeyAPI.createLocalAPI({
      address: config.homey.address, // Load address from config
      token: config.homey.token      // Load token from config
    });

    // Get all zones from Homey
    const Zones = await homeyApi.flow.getZones();

    // Filter zones based on the search string
    //const filteredZones = Object.values(Zones).filter(zone =>
    //  zone.name.toLowerCase().includes(searchString.toLowerCase())
    //);

    // Format the filtered zones in the zone_mappings.json structure
    const zoneMappings = {};
    Zones.forEach(zone => {
      zoneMappings[zone.name] = {
        id: zone.id,
        name: zone.name,
        sentences: [] // Empty sentences array, as this will be populated later
      };
    });

    // Return the zones to the Python script
    console.log(JSON.stringify(zoneMappings));
    //console.log("Zones zijn verzonden");
  } catch (error) {
    console.error("Een fout in het verkrijgen van de zones", error.message);
    process.exit(1); // Exit with an error code
  }
}

// Execute the function
getFilteredFlows();