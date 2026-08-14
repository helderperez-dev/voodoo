import os
import yaml
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env variables first
load_dotenv()

class VoodooConfig(BaseModel):
    """Core configuration for the Voodoo framework."""
    env: str = Field(default_factory=lambda: os.getenv("VOODOO_ENV", "development"))
    db_path: str = Field(default_factory=lambda: os.getenv("VOODOO_DB_PATH", ".data/voodoo.db"))
    storage_dir: str = Field(default_factory=lambda: os.getenv("VOODOO_STORAGE_DIR", "storage"))
    port: int = Field(default_factory=lambda: int(os.getenv("VOODOO_PORT", "8000")))
    host: str = Field(default_factory=lambda: os.getenv("VOODOO_HOST", "0.0.0.0"))
    extra: Dict[str, Any] = Field(default_factory=dict)

def load_yaml_config(file_path: str = "voodoo.yaml") -> Dict[str, Any]:
    """Loads configuration from a YAML file if it exists."""
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                print(f"Error parsing {file_path}: {e}")
    return {}

def get_config() -> VoodooConfig:
    """Gets the merged configuration from env vars and YAML."""
    yaml_data = load_yaml_config()
    
    # We allow yaml to override or extend defaults
    # but environment variables usually take precedence in production.
    # For this simple implementation, we'll merge them.
    config_args = {}
    
    # Add mapped YAML fields if they match our known fields
    if "env" in yaml_data: config_args["env"] = yaml_data["env"]
    if "db_path" in yaml_data: config_args["db_path"] = yaml_data["db_path"]
    if "storage_dir" in yaml_data: config_args["storage_dir"] = yaml_data["storage_dir"]
    if "port" in yaml_data: config_args["port"] = yaml_data["port"]
    if "host" in yaml_data: config_args["host"] = yaml_data["host"]
    
    # Store any extra custom configuration
    config_args["extra"] = {k: v for k, v in yaml_data.items() if k not in config_args}
    
    return VoodooConfig(**config_args)

# Global config instance
config = get_config()
