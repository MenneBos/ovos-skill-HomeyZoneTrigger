import { HomeyAPI } from 'homey-api';
import fs from 'fs';
import os from 'os';
import path from 'path';

// Load configuration from user config directory
const configPath = path.join(os.homedir(), '.config', 'ovos_skill_homeyzonetrigger', 'config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const ZoneId = process.argv[2];

if (!ZoneId) {
    console.error("Geen zone-id meegegeven.");
    process.exit(1);
  }

  const homeyApi = await HomeyAPI.createLocalAPI({
    address: config.homey.address, // Load address from config
    token: config.homey.token      // Load token from config
});

//const flows = await homeyApi.flow.getFlows();

try {
    await homeyApi.zone.triggerZone({ uri: 'homey:manager:zone', id: ZoneId });
    console.log(`Success`);
  } catch (err) {
    console.error(`Error`);
    process.exit(1);
  }

process.exit();  // Ensures that the script exits properly