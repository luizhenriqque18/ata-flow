import json
import os
import logging

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao ler arquivo de configuracao: {e}")
        return {}

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo de configuracao: {e}")
        return False

def get_gemini_key():
    config = load_config()
    return config.get("gemini_api_key", None)

def set_gemini_key(api_key):
    config = load_config()
    config["gemini_api_key"] = api_key
    return save_config(config)
