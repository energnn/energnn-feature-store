# EnerGNN Feature Store

EnerGNN Feature Store is a centralized platform for managing problem instances, datasets, and training checkpoints
for EnerGNN-based projects. It includes a PostgreSQL database, an S3-compatible storage backend (MinIO for development),
a REST API, and a graphical user interface.

## Documentation

To get started, please refer to the documentation that best matches your needs:

- **If you want to set up, configure, and run the Feature Store services locally or in a server environment:**
  See [How to run the feature store](docs/how_to_run_the_feature_store.md)

- **If you are a developer or data scientist or ML engineer who wants to use the Feature Store in your Python code with EnerGNN:**
  See [Using FeatureStoreClient with EnerGNN](client/README.md)

## Project Structure

- `app/`: Source code for the Backend API.
- `docker/`: Dockerfiles and docker-compose configurations for running the services.
- `docs/`: Detailed documentation and guides.
- `client/`: Python client library for interacting with the Feature Store.
- `frontend/`: Source code for the graphical user interface.
- `launch_feature_store.sh`: Startup script for the Docker services.
