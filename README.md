# hygieia teamcity collector

Provides connection between Hygiea API and teamcity

# pre-requirements:
- web-hook plugin installed on teamcity
- configure web-hook for build or build group(projects) in way like:
  - URL: url to connector
  - Enabled: true
  - Payload Format: Legacy Webhook (JSON)
  - Trigger on event:
    - Build Interrupted
  - On Completion:
    - Trigger when build is Succesfull
    - Trigger when build Fails

# environment variables:

- `HYGIEIA_API_URL`: ex. http://<host>:<port>/api
- `TEAMCITY_HOST`: ex. <IP address> or <teamcity.corp> etc...
- `TEAMCITY_USER`: ex. "admin"
- `TEAMCITY_PASSWORD`: ex. "securepassword"

# standalone container run command:
``
docker run \
  -e "TEAMCITY_HOST=192.168.100.101" \
  -e "TEAMCITY_USER=administrator" \
  -e "TEAMCITY_PASSWORD=securepassword" \
  -e "HYGIEIA_API_URL=http://hygieia-01.dub:8080/api" \
  -p 8080:80 \
  --name "hygieia-teamcity-collector" \
  alexeyanikanov/hygieia_teamcity_collector:latest
``
# docker-compose example:
``
hygieia-teamcity-collector:
  image: alexeyanikanov/hygieia_teamcity_collector:latest
  container_name: hygieia-teamcity
  links:
    - hygieia-api
  ports:
  - "8090:80"
  environment:
    - TEAMCITY_HOST=192.168.100.101
    - TEAMCITY_USER=administrator
    - TEAMCITY_PASSWORD=securepassword
    - HYGIEIA_API_URL=http://hygieia-api:8080/api
``

