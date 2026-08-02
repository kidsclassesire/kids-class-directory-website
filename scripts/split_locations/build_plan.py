import json, re, sys

DATA_PATH = '/Users/davidmacmahon/kids-class-directory-website/south_dublin_kids_activities.json'
data = json.load(open(DATA_PATH))
by_id = {d['id']: d for d in data}

def split_concatenated(addr):
    parts = re.split(r'(?<=Ireland)\s+', addr.strip())
    return [p.strip() for p in parts if p.strip()]

# rows with >=2 "Ireland" occurrences -> concatenated multi-address
concatenated_ids = [d['id'] for d in data if d.get('address') and len(re.findall(r'ireland', d['address'].lower())) >= 2]

# manual fix for hidden double-address chunks (no "Ireland" delimiter between them)
HIDDEN_BOUNDARY_FIX = {
    182: ("Ballymun Road, Glasnevin, Dublin, Dublin, D09 H5F6 Howth Road, Dublin 3, Ireland",
          ["Ballymun Road, Glasnevin, Dublin, Dublin, D09 H5F6", "Howth Road, Dublin 3, Ireland"]),
    789: ("Jessop St, Maryborough, Portlaoise, Co. Laois, R32 KV20 Townparks, Athy, County Kildare, R14 XD30, Ireland",
          ["Jessop St, Maryborough, Portlaoise, Co. Laois, R32 KV20", "Townparks, Athy, County Kildare, R14 XD30, Ireland"]),
}

# manually curated area-name splits (from "and"-joined descriptions + 1 "Serving" description + researched businesses)
MANUAL_SPLITS = {
    473: ["Knocklyon, Dublin", "Tallaght, Dublin"],  # Curtain's Up Drama School
    476: ["Tallaght, Dublin", "Rialto, Dublin"],  # Dance Sport
    491: ["Ballinteer, Dublin", "Dublin 15"],  # GymStars
    445: ["Rathmines, Dublin", "Dun Laoghaire, Dublin", "Castleknock, Dublin", "Dundrum, Dublin"],  # B.A.N.T.S
    482: ["Blackrock, Dublin", "Killiney, Dublin", "Castleknock, Dublin"],  # Dublin Stage School
    489: ["Temple Bar, Dublin", "Sandyford, Dublin", "Malahide Castle and Gardens, Malahide"],  # Gaiety School of Acting
    492: ["Blackrock, Dublin", "Cherrywood, Dublin", "Kilmainham, Dublin", "Loughlinstown, Dublin", "Sandymount, Dublin"],  # Happy Cubs
    419: ["Knocklyon, Dublin", "Rathfarnham, Dublin", "Firhouse, Dublin", "Tallaght, Dublin", "Templeogue, Dublin"],  # The Brickx Club
    # researched
    83: [  # Archaeology Camps
        "Harold's Cross National School, Harold's Cross, Dublin 6W",
        "Malahide Community School, Malahide, Co. Dublin",
        "Rosemont School, Sandyford, Dublin 18",
        "Clonturk Community College, Whitehall, Dublin 9",
        "Dalkey GAA, Dalkey, Co. Dublin",
        "St Joseph's Parish Church, Terenure, Dublin 6",
        "Rivertown Hall, Maynooth University, Maynooth, Co. Kildare",
        "Monaghan County Museum, Monaghan",
        "Clonmel, Co. Tipperary",
    ],
    513: ["Dun Laoghaire, Co. Dublin", "Sandyford, Dublin 18", "Dundrum, Dublin 14", "Castleknock, Dublin 15"],  # Me & You Music
    514: [  # Mel Ryan School
        "Mount Merrion Community Centre, Mount Merrion, Co. Dublin",
        "Mount Merrion Scout Hall, Mount Merrion, Co. Dublin",
        "Mounttown Community Facility, Monkstown, Co. Dublin",
        "Samuel Beckett Civic Centre, Carrickmines, Dublin 18",
    ],
    524: ["Docklands, Dublin", "Sandymount, Dublin 4"],  # NPAS
    533: ["Inchicore, Dublin 8", "Terenure, Dublin 6", "Sandymount, Dublin 4", "Dun Laoghaire, Co. Dublin"],  # PlayAct Drama School
    562: [  # Westwood Club
        "West Wood Club, Clontarf Rd, Dublin 3, D03 T6T3",
        "West Wood Club, Leopardstown Race Course, Foxrock, Dublin 18, D18 C9V6",
        "West Wood Club, Westmanstown, Clonsilla, Dublin 15, D15 T447",
    ],
}

DELETE_DUPLICATE_STUB_IDS = [464, 465, 511, 529, 561]

plan = {}  # id -> list of addresses
for rid in concatenated_ids:
    addr = by_id[rid]['address']
    parts = split_concatenated(addr)
    if rid in HIDDEN_BOUNDARY_FIX:
        old_chunk, replacement = HIDDEN_BOUNDARY_FIX[rid]
        parts = [c for p in parts for c in (replacement if p == old_chunk else [p])]
    plan[rid] = parts

for rid, addrs in MANUAL_SPLITS.items():
    plan[rid] = addrs

total_new_rows = sum(len(v) for v in plan.values())
total_orig_rows = len(plan)
print(f'Rows being split: {total_orig_rows}')
print(f'Total resulting addresses: {total_new_rows}')
print(f'Net new rows: {total_new_rows - total_orig_rows}')
print(f'Rows being deleted (pure duplicates): {len(DELETE_DUPLICATE_STUB_IDS)}')
print()
# sanity: any row with 1 address after split? shouldn't split those
single = [rid for rid, addrs in plan.items() if len(addrs) < 2]
print('rows with <2 resulting addresses (bug check):', single)

json.dump({str(k): v for k, v in plan.items()}, open('/Users/davidmacmahon/kids-class-directory-website/scripts/split_locations/plan.json', 'w'), indent=2)
print('Wrote plan.json')
