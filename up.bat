REM This script is used to start the Docker containers defined in the Docker Compose file.

docker compose -f .\viron\compose.yml up -d --build
REM The -d flag runs the containers in detached mode, allowing them to run in the background.
REM The --build flag forces a rebuild of the images before starting the containers.
