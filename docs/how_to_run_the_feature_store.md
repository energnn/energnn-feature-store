# EnerGNN Feature Store

This project contains the code to run the feature store. The feature store is made up of:

- a **PostgreSQL database** running in a Docker container
- a **remote S3 storage** (a Docker container is used in the development environment)
- an **API** running in a Docker container to interact with data and metadata
- a **graphical user interface** running in a Docker container that queries the API to simplify usage.

To run the feature store, you must first clone the project onto your working machine. After that, a few adjustments and checks must be made.

## 1. Adjust Docker configurations

Depending on your working environment (Production or Development), some lines need to be commented out or removed in:

* the [API Dockerfile](../docker/Dockerfile.backend)
* the [docker-compose configuration file](../docker/docker-compose.yml)

In these files you'll find commented instructions indicating which lines or code blocks to comment or uncomment.

## 2. Environment files

To operate, the various services require several environment variables stored in files. You must therefore create these files if they are missing.

### 2.1. PostgreSQL database

The container hosting the PostgreSQL database requires a **file named `private.conf` at the project root** containing the authentication information. This file must follow the schema below:

```bash
POSTGRES_USER=        # Specify the username
POSTGRES_PASSWORD=    # Specify the password
POSTGRES_DB=          # Specify the database name
```

### 2.2. S3 Storage (DEV ONLY)

This part must be done only in the development environment. It is required for the MinIO container that will act as the S3 storage. Server-Side Encryption requires that communications between the S3 bucket and the API be performed over HTTPS. Therefore you must create a self-signed TLS certificate that will be added to the MinIO and API containers. From the project root, run the following Linux commands:

```bash
mkdir -p ./docker/minio/certs
cd ./docker/minio/certs

cat > san.cnf <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = minio

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = minio
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

openssl req -new -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout private.key \
  -out public.crt \
  -config san.cnf -extensions v3_req

cd ../../../
```

An environment file named **`minio.env`** must be created in the **`docker`** directory, following this schema :

```bash
  MINIO_ROOT_USER = # define S3 access id
  MINIO_ROOT_PASSWORD = # define S3 secret key
```

### 2.3. Backend API

The API requires environment variables and some configuration files, notably for communication with the S3 storage.

- **Environment file** (`app/.env`)

You must create an environment file named **`.env`** inside the **`app`** folder. It must follow the schema below:

```bash
DATABASE_URL=    # PostgreSQL URL, e.g. postgresql://username:password@hostname:port/database_name
S3_ENDPOINT=     # S3 storage endpoint (e.g. in DEV with MinIO: https://minio:9000)
S3_BUCKET=       # Bucket identifier
API_KEY=         # API key
SECRET_KEY_BIN=/run/secrets/s3_aes_key.bin # Do not modify
```

- **Binary AES Key** (`app/secrets/s3_aes_key.bin`)

To secure transfers between the S3 storage and the API using Server-Side Encryption, you must provide a binary file containing an AES-256 key. This file must be named **`s3_aes_key.bin`** and placed in the **`app/secrets/`** folder.

In the development environment (and for convenience), this file can be created by running the following commands from the project root:

```bash
mkdir -p ./app/secrets
openssl rand -out ./app/secrets/s3_aes_key.bin 32
chmod 600 ./app/secrets/s3_aes_key.bin
```

- **AWS configuration files** (`app/aws/`)

So that `boto3` can find the credentials needed to communicate with the S3 bucket, you must add a folder named `aws` inside the **`app`** folder. In this folder (`app/aws/`), add two files:

  * *`credentials`*
  ```bash
  [default]
  aws_access_key_id = # specify S3 access id
  aws_secret_access_key = # specify S3 secret key
  ```
  
  * *`config`*
  ```bash
  [default]
  region = # Specify the region (for example: eu-west-1)
  ```

### 2.4. Frontend

The container hosting the frontend also needs access to environment variables. These variables must be stored in a file named **`.env`** inside the **`frontend`** folder and contain:

```bash
VITE_API_BASE_URL=http://localhost:8000  # API URL
VITE_API_KEY= # API key (corresponding to the server API_KEY environment variable)
```

## 3. Launching the Feature Store

Then, to run the Feature Store, simply execute the startup script:

```bash
./launch_feature_store.sh
```

Once executed, you will be able to access the feature store web app at `http://localhost:5173`.