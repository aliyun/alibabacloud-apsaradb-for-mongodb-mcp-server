import os
import re
import logging
import ipaddress
from urllib.parse import urlparse
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from alibabacloud_dds20151201.client import Client as Dds20151201Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_vpc20160428.client import Client as Vpc20160428Client


mcp = FastMCP("apsaradb_mongodb_mcp_server", host="127.0.0.1")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("apsaradb_mongodb_mcp_server")

load_dotenv()
global_config = None


def get_mongodb_connection_configuration():
    # Check if configuration is already cached
    global global_config
    if global_config:
        return global_config

    # Use connection string from environment variable
    connection_string = os.getenv("MONGODB_CONNECTION_STRING")
    if connection_string:
        logger.info("Database configuration loaded successfully: connection_string=%s", mask_connection_string(connection_string))
        global_config = connection_string
        return global_config

    # Use individual configuration parameters
    config = {
        "host": os.getenv("MONGODB_HOST"),
        "port": os.getenv("MONGODB_PORT"),
        "user": os.getenv("MONGODB_USER"),
        "password": os.getenv("MONGODB_PASSWORD"),
        "database": os.getenv("MONGODB_DATABASE"),
    }

    # Check if all required parameters are present
    missing_params = [
        key for key in ["host", "port", "user", "password", "database"] if not config.get(key)
    ]
    if missing_params:
        logger.error(
            "Missing required database configuration. Please check the following parameters: %s",
            ", ".join(missing_params),
        )
        raise ValueError(
            "Unable to obtain database connection configuration information from environment variables. "
            "Please provide database connection configuration information."
        )

    logger.info(
        "Database configuration loaded successfully: host=%s, port=%d, user=%s, database=%s",
        config["host"],
        config["port"],
        config["user"],
        config["database"],
    )
    global_config = config

    return global_config


def get_dds_client() -> Dds20151201Client:
    try:
        config = open_api_models.Config(
            access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        )
        config.endpoint = f'mongodb.aliyuncs.com'
        return Dds20151201Client(config)
    except Exception as e:
        logger.error("Failed to create OpenAPI client: %s", str(e))
        raise


def get_vpc_client(region_id: str) -> Vpc20160428Client:
    try:
        config = open_api_models.Config(
            access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        )
        if region_id:
            config.endpoint = f'vpc.{region_id}.aliyuncs.com'
        return Vpc20160428Client(config)
    except Exception as e:
        logger.error("Failed to create VPC client: %s", str(e))
        raise


def mask_connection_string(connection_string: str) -> str:
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', connection_string)


_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

ALLOWED_HOST_SUFFIXES = [
    ".mongodb.rds.aliyuncs.com",
    ".mongodb.aliyuncs.com",
]


def _is_private_ip(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def validate_connection_string(connection_string: str) -> None:
    allowed_suffixes = os.getenv("MONGODB_ALLOWED_HOST_SUFFIXES", "").split(",")
    allowed_suffixes = [s.strip() for s in allowed_suffixes if s.strip()]
    allowed_suffixes.extend(ALLOWED_HOST_SUFFIXES)

    parsed = urlparse(connection_string)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid connection string: no hostname found.")

    if _is_private_ip(hostname):
        raise ValueError(
            f"Connection to private/internal address '{hostname}' is not allowed."
        )

    if not any(hostname.endswith(suffix) for suffix in allowed_suffixes):
        env_conn = os.getenv("MONGODB_CONNECTION_STRING", "")
        if env_conn:
            env_parsed = urlparse(env_conn)
            if env_parsed.hostname == hostname:
                return
        env_host = os.getenv("MONGODB_HOST", "")
        if env_host == hostname:
            return
        raise ValueError(
            f"Connection to host '{hostname}' is not allowed. "
            f"Only Alibaba Cloud MongoDB endpoints or pre-configured hosts are permitted."
        )
