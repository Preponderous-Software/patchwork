REM This script is used to stop the Docker containers defined in the Docker Compose file.

docker compose -f .\viron\compose.yml down --remove-orphans --volumes
REM The --remove-orphans flag removes containers for services not defined in the Compose file.
REM The --volumes flag removes the volumes associated with the containers, ensuring a clean shutdown.
REM This ensures that all resources are cleaned up when the containers are stopped.
