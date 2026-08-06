import os
import re
import json
import pandas as pd
import numpy as np
from pathlib import Path
from urllib.parse import quote
from typing import List, Dict, Any

# ------------------------------
# Configuration
# ------------------------------
ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = ROOT / 'downloads'
DOWNLOAD_DIR.mkdir(exist_ok=True)

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://gnozodfteywsiwcnbwch.supabase.co')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', 'sb_publishable_eduvbMySPxHPT0iZjE_LqQ_w6nyjnjY')

TARGET_COLUMNS = [
    'company_name', 'category', 'description', 'class_types', 'minimum_age', 'maximum_age',
    'age_range_display', 'parental_requirement', 'address', 'eircode', 'latitude', 'longitude',
    'days_of_week', 'start_time', 'end_time', 'term_structure', 'price_amount', 'price_currency',
    'pricing_basis', 'pricing_details', 'website_url', 'booking_url', 'email_address', 'phone_number',
    'facilities', 'source_urls', 'date_verified', 'verification_status', 'image_url'
]

# ------------------------------
# Helpers
# ------------------------------

def normalize_text(v):
    if pd.isna(v):
        return None
    if isinstance(v, (list, tuple, set)):
        return ' | '.join(str(x).strip() for x in v if str(x).strip())
    s = str(v).strip()
    s = re.sub(r'\s+', ' ', s)
    return s or None


def normalize_name(v):
    s = normalize_text(v)
    if not s:
        return None
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def normalize_address(v):
    s = normalize_text(v)
    if not s:
        return None
    s = s.lower()
    s = s.replace('co. ', 'co ').replace('co.','co ')
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def normalize_bool(v):
    if pd.isna(v):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {'true', '1', 'yes', 'y'}:
        return True
    if s in {'false', '0', 'no', 'n'}:
        return False
    return None


def parse_number(v):
    if pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    s = s.replace(',', '')
    try:
        return float(s)
    except Exception:
        return None


def parse_list(v):
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        return [normalize_text(x) for x in v if normalize_text(x)]
    if isinstance(v, np.ndarray):
        return [normalize_text(x) for x in v.tolist() if normalize_text(x)]
    if pd.isna(v):
        return []
    if isinstance(v, str):
        if v.startswith('[') and v.endswith(']'):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [normalize_text(x) for x in parsed if normalize_text(x)]
            except Exception:
                pass
        parts = [p.strip() for p in re.split(r';|,|\|', v) if p.strip()]
        return parts
    return [normalize_text(v)]


def build_dedup_key(row: Dict[str, Any]) -> str:
    name = normalize_name(row.get('company_name')) or ''
    address = normalize_address(row.get('address')) or ''
    website = normalize_text(row.get('website_url')) or ''
    phone = normalize_text(row.get('phone_number')) or ''
    return '|'.join([name, address, website, phone])


def is_probably_duplicate(row: Dict[str, Any], existing_row: Dict[str, Any]) -> bool:
    name = normalize_name(row.get('company_name'))
    address = normalize_address(row.get('address'))
    website = normalize_text(row.get('website_url'))
    phone = normalize_text(row.get('phone_number'))
    description = normalize_text(row.get('description'))
    class_types = set(parse_list(row.get('class_types')))

    ex_name = normalize_name(existing_row.get('company_name'))
    ex_address = normalize_address(existing_row.get('address'))
    ex_website = normalize_text(existing_row.get('website_url'))
    ex_phone = normalize_text(existing_row.get('phone_number'))
    ex_description = normalize_text(existing_row.get('description'))
    ex_class_types = set(parse_list(existing_row.get('class_types')))

    if website and ex_website and website == ex_website:
        return True
    if phone and ex_phone and phone == ex_phone:
        return True

    if not name or not ex_name or name != ex_name:
        return False
    if not address or not ex_address or address != ex_address:
        return False

    if description and ex_description and description == ex_description:
        return True
    if class_types and ex_class_types and class_types == ex_class_types:
        return True

    return False


def sanitize_for_json(value):
    if value is None:
        return None
    if isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return None
        return value
    if isinstance(value, dict):
        return {k: sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return [sanitize_for_json(v) for v in value.tolist()]
    if pd.isna(value):
        return None
    return str(value)


# ------------------------------
# Supabase fetch
# ------------------------------

def fetch_existing_classes() -> pd.DataFrame:
    url = f'{SUPABASE_URL}/rest/v1/classes?select=*'
    import requests
    headers = {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
        'Accept': 'application/json'
    }
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)
    return df


# ------------------------------
# File loading
# ------------------------------

def load_source_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == '.csv':
        return pd.read_csv(path)
    if suffix == '.json':
        with path.open('r', encoding='utf-8') as f:
            obj = json.load(f)
        if isinstance(obj, list):
            return pd.DataFrame(obj)
        if isinstance(obj, dict):
            return pd.DataFrame([obj])
    if suffix in {'.xlsx', '.xls'}:
        return pd.read_excel(path)
    raise ValueError(f'Unsupported file type: {path}')


def discover_source_files(root: Path | None = None) -> List[Path]:
    base = root or ROOT
    download_dir = base / 'downloads'
    if not download_dir.exists():
        return []

    ignored_names = {
        'classes_in_database.json',
        'all_normalized_candidates.csv',
        'all_normalized_candidates.json',
        'deduped_candidates.csv',
        'deduped_candidates.json',
        'cleaned_new_candidates.json',
        'south_dublin_kids_activities.json',
    }

    candidates = []
    for path in sorted(download_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name in ignored_names:
            continue
        if path.suffix.lower() not in {'.csv', '.json', '.xlsx', '.xls'}:
            continue
        candidates.append(path)
    return candidates


# ------------------------------
# Mapping
# ------------------------------

def normalize_column_name(name: Any) -> str:
    if name is None:
        return ''
    if isinstance(name, str):
        text = name.strip().lower()
        return re.sub(r'[^a-z0-9]+', '_', text).strip('_')
    return str(name)


def map_row(row: Dict[str, Any], source_name: str) -> Dict[str, Any]:
    mapped = {}
    normalized_row = {normalize_column_name(k): v for k, v in row.items()}

    def pick(*candidates):
        for c in candidates:
            key = normalize_column_name(c)
            if key in normalized_row:
                value = normalized_row[key]
                if value is None:
                    continue
                if isinstance(value, (list, tuple, set)):
                    if len(value) > 0:
                        return value
                    continue
                if isinstance(value, np.ndarray):
                    if value.size > 0:
                        return value.tolist()
                    continue
                if pd.isna(value):
                    continue
                if isinstance(value, str) and value.strip() == '':
                    continue
                return value
        return None

    mapped['company_name'] = normalize_text(pick('company_name', 'name', 'provider', 'title', 'company'))
    mapped['category'] = normalize_text(pick('category', 'categories', 'category_name', 'type'))
    description_value = pick('description', 'description_text', 'summary', 'details', 'full_description')
    if not description_value:
        description_value = pick('title')
    mapped['description'] = normalize_text(description_value)
    mapped['class_types'] = parse_list(pick('class_types', 'classes', 'class_type', 'activities'))
    mapped['minimum_age'] = parse_number(pick('minimum_age', 'min_age', 'age_from'))
    mapped['maximum_age'] = parse_number(pick('maximum_age', 'max_age', 'age_to'))
    mapped['age_range_display'] = normalize_text(pick('age_range_display', 'ages_detail', 'age_range', 'ages'))
    mapped['parental_requirement'] = normalize_text(pick('parental_requirement', 'parental_requirement_display', 'supervision'))
    mapped['address'] = normalize_text(pick('address', 'street', 'location', 'venue', 'full_address'))
    mapped['eircode'] = normalize_text(pick('eircode', 'zip', 'postcode', 'postal_code'))
    mapped['latitude'] = parse_number(pick('latitude', 'lat', 'latitud'))
    mapped['longitude'] = parse_number(pick('longitude', 'lng', 'longitud'))
    mapped['days_of_week'] = parse_list(pick('days_of_week', 'days'))
    mapped['start_time'] = normalize_text(pick('start_time', 'time'))
    mapped['end_time'] = normalize_text(pick('end_time'))
    mapped['term_structure'] = normalize_text(pick('term_structure', 'schedule'))
    mapped['price_amount'] = parse_number(pick('price_amount', 'price', 'cost'))
    mapped['price_currency'] = normalize_text(pick('price_currency', 'currency')) or 'EUR'
    mapped['pricing_basis'] = normalize_text(pick('pricing_basis', 'pricing'))
    mapped['pricing_details'] = normalize_text(pick('pricing_details', 'pricing_text'))
    mapped['website_url'] = normalize_text(pick('website_url', 'website', 'link', 'url'))
    mapped['booking_url'] = normalize_text(pick('booking_url', 'book_now_url', 'booking_link'))
    mapped['email_address'] = normalize_text(pick('email_address', 'email'))
    mapped['phone_number'] = normalize_text(pick('phone_number', 'phone'))
    mapped['facilities'] = parse_list(pick('facilities', 'amenities'))

    source_urls = []
    for candidate in ['source_urls', 'source_links', 'website_url', 'website', 'url', 'link']:
        value = pick(candidate)
        if value is not None:
            source_urls.extend(parse_list(value))
    for candidate in ['booking_url', 'book_now_url', 'booking_link']:
        value = pick(candidate)
        if value is not None:
            source_urls.extend(parse_list(value))
    mapped['source_urls'] = [value for value in source_urls if value]

    mapped['date_verified'] = normalize_text(pick('date_verified', 'date_added', 'added_date'))
    mapped['verification_status'] = normalize_text(pick('verification_status', 'verified'))
    mapped['image_url'] = normalize_text(pick('image_url', 'featured_image', 'thumbnail', 'image'))

    # Keep source info in a metadata field if present
    mapped['source_file'] = source_name
    mapped['dedup_key'] = build_dedup_key(mapped)

    return mapped


# ------------------------------
# Canonicalization + dedup
# ------------------------------

def normalize_for_upload(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        mapped = map_row(row.to_dict(), 'import')
        rows.append(mapped)
    return pd.DataFrame(rows, columns=TARGET_COLUMNS + ['source_file', 'dedup_key'])


def dedup_against_existing(new_df: pd.DataFrame, existing_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    existing_df = existing_df.copy()
    new_df = new_df.copy()

    # Build keys for new rows
    new_df['dedup_key'] = new_df.apply(build_dedup_key, axis=1)

    existing_records = existing_df.to_dict(orient='records')
    kept_rows = []
    for _, row in new_df.iterrows():
        row_data = row.to_dict()
        if any(is_probably_duplicate(row_data, existing_row) for existing_row in existing_records):
            continue
        kept_rows.append(row_data)

    new_unique = pd.DataFrame(kept_rows, columns=new_df.columns)
    return new_unique, existing_df


# ------------------------------
# Upload to Supabase
# ------------------------------

def export_candidates(df: pd.DataFrame, prefix: str):
    if df.empty:
        print(f'No rows to export for {prefix}')
        return
    out_dir = ROOT / 'downloads'
    out_dir.mkdir(exist_ok=True)
    csv_path = out_dir / f'{prefix}.csv'
    json_path = out_dir / f'{prefix}.json'
    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient='records', indent=2)
    print(f'Exported {len(df)} rows to {csv_path} and {json_path}')


def upload_to_supabase(df: pd.DataFrame):
    if df.empty:
        print('No rows to upload')
        return
    import requests
    rows = df.to_dict(orient='records')
    # Remove helper columns before upload
    rows = [{k: sanitize_for_json(v) for k, v in r.items() if k not in {'source_file', 'dedup_key'}} for r in rows]
    headers = {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    resp = requests.post(f'{SUPABASE_URL}/rest/v1/classes', headers=headers, json=rows, timeout=120)
    print('Upload status', resp.status_code)
    print(resp.text[:500])
    resp.raise_for_status()


# ------------------------------
# Main
# ------------------------------

def main():
    print('Fetching existing classes table from Supabase...')
    existing = fetch_existing_classes()
    print('Existing rows:', len(existing))

    files = discover_source_files(ROOT)
    if not files:
        print('No candidate source files found in downloads/')
        return

    combined = []
    for path in files:
        print(f'Loading {path.name}...')
        df = load_source_file(path)
        print('Rows loaded:', len(df))
        normalized = normalize_for_upload(df)
        normalized['source_file'] = path.name
        combined.append(normalized)

    if not combined:
        print('No files found to process')
        return

    combined_df = pd.concat(combined, ignore_index=True)
    print('Rows normalized:', len(combined_df))

    all_candidates = combined_df.copy()
    export_candidates(all_candidates, 'all_normalized_candidates')

    deduped, _ = dedup_against_existing(combined_df, existing)
    print('Rows after dedup against existing table:', len(deduped))

    # Keep only columns that match the table schema
    upload_df = deduped[[c for c in TARGET_COLUMNS if c in deduped.columns]].copy()
    upload_df = upload_df.where(pd.notna(upload_df), None)

    # Fill any missing required values with nulls
    for col in TARGET_COLUMNS:
        if col not in upload_df.columns:
            upload_df[col] = None

    export_candidates(upload_df, 'deduped_candidates')
    try:
        upload_to_supabase(upload_df)
    except Exception as exc:
        print('Supabase upload blocked:', exc)
        print('The deduped candidate rows were still exported locally for review/import.')


if __name__ == '__main__':
    main()
