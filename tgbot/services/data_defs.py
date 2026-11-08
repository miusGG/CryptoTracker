import json
import logging


def get_data_dict(file):
    try:
        with open(file, "r") as file:
            data = json.load(file)
            return data
    except Exception as e:
        logging.getLogger(__name__).error("CONFIG_READ_FAILED error=%s", type(e).__name__)
        return None


def add_admin(file, new_id):
    data = get_data_dict(file)
    data["main"]["ADMINS"].append(new_id)
    with open(file, "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def edit_exchange(file, new_exchange):
    data = get_data_dict(file)
    data["main"]["exchange"] = new_exchange
    with open(file, "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def edit_currency(file, new_currency):
    data = get_data_dict(file)
    data["main"]["currency"] = new_currency
    with open(file, "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
