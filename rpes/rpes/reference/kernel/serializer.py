"""RPES Canonical Serializer (EI-003)"""

def serialize_canonical(record: dict) -> str:
    sorted_keys = sorted(record.keys())
    canonical_pairs = []

    for key in sorted_keys:
        value = record[key]

        if value is None:
            processed_value = ""
        else:
            if isinstance(value, str):
                processed_value = value.strip()
            elif isinstance(value, bool):
                processed_value = "True" if value else "False"
            elif isinstance(value, (int, float)):
                str_val = str(float(value))
                processed_value = str_val.rstrip('0').rstrip('.') if '.' in str_val else str_val
            else:
                processed_value = str(value).strip()

        canonical_pairs.append(f"{key}={processed_value}")

    return "|".join(canonical_pairs)
