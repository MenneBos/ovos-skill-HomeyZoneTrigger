1️⃣ Maak projectfolder op de host
cd /home/ovos
mkdir ovos-skill-homeyzonetrigger
cd ovos-skill-homeyzonetrigger


Dit wordt:
je build context bevat Dockerfile bevat repo code

2️⃣ Clone je GitHub repo in de projectfolder

Hierdoor kan je makkelijk code op de host aanpassen
De code in de container is dan ook aanpast.
Makkelijk debuggen.

git clone https://github.com/<you>/<your-skill-repo>.git .

Resultaat:
/home/ovos/ovos-skill-homeyzonetrigger/
├── Dockerfile
├── setup.py
├── nodejs/
├── locale/
├── requirements.txt
└── ...

3️⃣ Kies een config folder (host + container)

Host & container pad (zelfde pad):

/home/ovos/.config/ovos-skill-homeyzonetrigger

Dit is gelijk aan de __init__.py code 

mkdir -p /home/ovos/.config/ovos-skill-homeyzonetrigger
cd /home/ovos/.config/ovos-skill-homeyzonetrigger

Maak en copier inhoud van:
- nano config.json
- nano zone_mappings.json

(geen chown nodig als je als ovos draait)

4️⃣ Dockerfile (skill image)

Dockerfile (definitieve versie)

✔ Geen config in image
✔ Geen volumes in Dockerfile
✔ Clean separation code ↔ data

5️⃣ Eerste-run defaults veilig maken (cruciaal)

Copier config.json and zone_mapping.json naar 
/home/ovos/.config/ovos-skill-homeyzonetrigger

In runtime kan container dit aanpassen
maar data is persistent, bij een container update


6️⃣ docker-compose service (skill)

✔ Config zichtbaar op host
✔ Skill code blijft in image
✔ Update-safe

7️⃣ Build & start

cd /home/ovos/ovos-docker/compose
docker compose build homey_zone_trigger
docker compose up -d homey_zone_trigger

Na start:
ls ~/.config/ovos-skill-homeyzonetrigger

➡️ config.json bestaat 🎉

8️⃣ Update van de skill (zonder data verlies)
cd /home/ovos/ovos-skill-homeyzonetrigger
git pull

cd /home/ovos/ovos-docker/compose
docker compose build homey_zone_trigger
docker compose up -d homey_zone_trigger