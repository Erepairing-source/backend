"""
Single source of truth for India locations: 35 states/UTs and cities per state.
Use this everywhere (API, seed, country_admin). UP has 75+ cities.
"""
from typing import Dict, List

# All 35 states and union territories (28 states + 7 UTs)
INDIA_STATES = [
    {"name": "Andhra Pradesh", "code": "AP", "capital": "Amaravati"},
    {"name": "Arunachal Pradesh", "code": "AR", "capital": "Itanagar"},
    {"name": "Assam", "code": "AS", "capital": "Dispur"},
    {"name": "Bihar", "code": "BR", "capital": "Patna"},
    {"name": "Chhattisgarh", "code": "CG", "capital": "Raipur"},
    {"name": "Goa", "code": "GA", "capital": "Panaji"},
    {"name": "Gujarat", "code": "GJ", "capital": "Gandhinagar"},
    {"name": "Haryana", "code": "HR", "capital": "Chandigarh"},
    {"name": "Himachal Pradesh", "code": "HP", "capital": "Shimla"},
    {"name": "Jharkhand", "code": "JH", "capital": "Ranchi"},
    {"name": "Karnataka", "code": "KA", "capital": "Bengaluru"},
    {"name": "Kerala", "code": "KL", "capital": "Thiruvananthapuram"},
    {"name": "Madhya Pradesh", "code": "MP", "capital": "Bhopal"},
    {"name": "Maharashtra", "code": "MH", "capital": "Mumbai"},
    {"name": "Manipur", "code": "MN", "capital": "Imphal"},
    {"name": "Meghalaya", "code": "ML", "capital": "Shillong"},
    {"name": "Mizoram", "code": "MZ", "capital": "Aizawl"},
    {"name": "Nagaland", "code": "NL", "capital": "Kohima"},
    {"name": "Odisha", "code": "OD", "capital": "Bhubaneswar"},
    {"name": "Punjab", "code": "PB", "capital": "Chandigarh"},
    {"name": "Rajasthan", "code": "RJ", "capital": "Jaipur"},
    {"name": "Sikkim", "code": "SK", "capital": "Gangtok"},
    {"name": "Tamil Nadu", "code": "TN", "capital": "Chennai"},
    {"name": "Telangana", "code": "TS", "capital": "Hyderabad"},
    {"name": "Tripura", "code": "TR", "capital": "Agartala"},
    {"name": "Uttar Pradesh", "code": "UP", "capital": "Lucknow"},
    {"name": "Uttarakhand", "code": "UK", "capital": "Dehradun"},
    {"name": "West Bengal", "code": "WB", "capital": "Kolkata"},
    {"name": "Andaman and Nicobar Islands", "code": "AN", "capital": "Port Blair"},
    {"name": "Chandigarh", "code": "CH", "capital": "Chandigarh"},
    {"name": "Dadra and Nagar Haveli and Daman and Diu", "code": "DH", "capital": "Daman"},
    {"name": "Delhi", "code": "DL", "capital": "New Delhi"},
    {"name": "Jammu and Kashmir", "code": "JK", "capital": "Srinagar"},
    {"name": "Ladakh", "code": "LA", "capital": "Leh"},
    {"name": "Lakshadweep", "code": "LD", "capital": "Kavaratti"},
    {"name": "Puducherry", "code": "PY", "capital": "Puducherry"},
]

# Cities per state (unique names; UP has 75+). Same data from beginning everywhere.
_RAW_CITIES: Dict[str, List[str]] = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad", "Solapur", "Thane", "Kalyan", "Vasai-Virar", "Navi Mumbai", "Sangli", "Kolhapur", "Amravati", "Nanded", "Jalgaon", "Akola", "Latur", "Dhule", "Ahmednagar", "Chandrapur", "Parbhani", "Ichalkaranji", "Jalna", "Bhusawal", "Panvel", "Satara", "Beed", "Yavatmal", "Kamptee", "Gondia", "Barshi", "Achalpur", "Osmanabad", "Nandurbar", "Wardha", "Udgir", "Hinganghat"],
    "Karnataka": ["Bengaluru", "Mysuru", "Hubli-Dharwad", "Mangalore", "Belagavi", "Kalaburagi", "Davangere", "Ballari", "Tumakuru", "Shivamogga", "Raichur", "Bijapur", "Hassan", "Udupi", "Bhadravati", "Chitradurga", "Robertson Pet", "Kolar", "Mandya", "Chikmagalur", "Gangawati", "Bagalkot", "Ranebennuru", "Hospet", "Gokak", "Yadgir", "Karwar", "Koppal", "Haveri", "Gadag-Betigeri", "Sirsi", "Chamrajnagar", "Chintamani", "Anekal", "Srinivaspur"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli", "Erode", "Vellore", "Tuticorin", "Dindigul", "Thanjavur", "Hosur", "Nagercoil", "Kanchipuram", "Karaikudi", "Neyveli", "Cuddalore", "Kumbakonam", "Tiruvannamalai", "Pollachi", "Rajapalayam", "Gudiyatham", "Pudukkottai", "Vaniyambadi", "Ambur", "Nagapattinam", "Tirupathur", "Sivakasi", "Krishnagiri", "Dharmapuri", "Thiruvallur", "Tindivanam", "Villupuram", "Kallakurichi", "Ariyalur", "Perambalur", "Karur", "Namakkal", "Theni", "Tenkasi", "Ramanathapuram", "Sivaganga", "Virudhunagar", "Thoothukudi", "Kanyakumari"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Gandhinagar", "Junagadh", "Gandhidham", "Anand", "Navsari", "Morbi", "Nadiad", "Surendranagar", "Bharuch", "Mehsana", "Bhuj", "Porbandar", "Palanpur", "Valsad", "Vapi", "Gondal", "Veraval", "Godhra", "Patan", "Kalol", "Dahej", "Botad", "Amreli", "Modasa"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur", "Bhilwara", "Alwar", "Bharatpur", "Sri Ganganagar", "Sikar", "Tonk", "Pali", "Chittorgarh", "Hanumangarh", "Beawar", "Kishangarh", "Jhunjhunu", "Baran", "Churu", "Banswara", "Dausa", "Bundi", "Jhalawar", "Nagaur", "Pratapgarh", "Rajsamand", "Sawai Madhopur", "Sirohi", "Dholpur", "Karauli", "Jalore"],
    "Uttar Pradesh": [
        "Lucknow", "Kanpur", "Ghaziabad", "Agra", "Meerut", "Varanasi", "Allahabad", "Noida", "Bareilly", "Aligarh", "Moradabad", "Saharanpur", "Gorakhpur", "Faizabad", "Jhansi", "Muzaffarnagar", "Mathura", "Rampur", "Shahjahanpur", "Firozabad", "Etawah", "Sitapur", "Budaun", "Pilibhit", "Hapur", "Bulandshahr", "Amroha", "Hardoi", "Fatehpur", "Raebareli", "Orai", "Sultanpur", "Bahraich", "Deoria", "Banda", "Unnao", "Mainpuri", "Lalitpur", "Etah", "Bijnor", "Mirzapur", "Sambhal", "Shamli", "Azamgarh", "Kasganj", "Bhadohi", "Kaushambi", "Farrukhabad", "Kannauj", "Basti", "Gonda", "Siddharthnagar", "Maharajganj", "Ballia", "Jaunpur", "Mau", "Ghazipur", "Chandauli", "Sonbhadra", "Sant Kabir Nagar", "Kushinagar", "Mahoba", "Hamirpur", "Jalaun", "Auraiya", "Kheri", "Pratapgarh", "Ambedkar Nagar",
        "Ayodhya", "Amethi", "Shravasti", "Chitrakoot", "Barabanki", "Hathras", "Kasganj", "Kanpur Dehat", "Gautam Buddha Nagar",
    ],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri", "Bardhaman", "Malda", "Baharampur", "Habra", "Kharagpur", "Shantipur", "Dankuni", "Dhulian", "Ranaghat", "Haldia", "Raiganj", "Krishnanagar", "Nabadwip", "Medinipur", "Jalpaiguri", "Balurghat", "Bankura", "Darjeeling", "Alipurduar", "Purulia", "Jhargram", "Kalimpong"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Gwalior", "Jabalpur", "Ujjain", "Sagar", "Ratlam", "Satna", "Rewa", "Murwara", "Singrauli", "Burhanpur", "Khandwa", "Chhindwara", "Guna", "Shivpuri", "Vidisha", "Chhatarpur", "Damoh", "Mandsaur", "Khargone", "Neemuch", "Pithampur", "Itarsi", "Nagda", "Morena", "Bhind", "Datia", "Ashoknagar", "Tikamgarh", "Panna", "Katni", "Narsinghpur", "Seoni", "Mandla", "Dindori", "Anuppur", "Shahdol", "Umaria", "Sidhi", "Betul", "Harda", "Hoshangabad", "Raisen", "Rajgarh", "Shajapur", "Dewas", "Jhabua", "Alirajpur", "Barwani", "Dhar", "Agar Malwa", "Sehore"],
    "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Darbhanga", "Purnia", "Bihar Sharif", "Arrah", "Begusarai", "Katihar", "Munger", "Chhapra", "Saharsa", "Sasaram", "Hajipur", "Dehri", "Bettiah", "Motihari", "Siwan", "Nawada", "Jamalpur", "Buxar", "Kishanganj", "Sitamarhi", "Jehanabad", "Aurangabad", "Lakhisarai", "Nalanda", "Banka", "Gopalganj", "Vaishali", "Saran", "Samastipur", "Madhubani", "Supaul", "Araria", "Madhepura", "Khagaria", "Sheikhpura", "Bhojpur", "Kaimur", "Rohtas", "Jamui", "East Champaran", "West Champaran", "Sheohar"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Puri", "Baleshwar", "Bhadrak", "Baripada", "Balangir", "Jharsuguda", "Bargarh", "Rayagada", "Jeypore", "Bhawanipatna", "Dhenkanal", "Angul", "Talcher", "Barbil", "Kendujhar", "Paradip", "Jagatsinghapur", "Kendrapara", "Balasore", "Mayurbhanj", "Keonjhar", "Sundargarh", "Nuapada", "Kalahandi", "Koraput", "Nabarangpur", "Malkangiri", "Gajapati", "Ganjam", "Kandhamal", "Boudh", "Sonepur"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Rajahmundry", "Tirupati", "Kakinada", "Kadapa", "Anantapur", "Eluru", "Nandyal", "Ongole", "Chittoor", "Hindupur", "Machilipatnam", "Adoni", "Tenali", "Chilakaluripet", "Proddatur", "Bhimavaram", "Narasaraopet", "Palakollu", "Srikakulam", "Vizianagaram", "Parvathipuram Manyam", "Alluri Sitharama Raju", "NTR", "Palnadu", "Bapatla", "Prakasam", "Annamayya", "YSR Kadapa", "Sri Sathya Sai"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Ramagundam", "Khammam", "Mahbubnagar", "Nalgonda", "Adilabad", "Siddipet", "Suryapet", "Miryalaguda", "Jagtial", "Narayanpet", "Mancherial", "Kamareddy", "Sangareddy", "Medak", "Medchal-Malkajgiri", "Rangareddy"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam", "Alappuzha", "Palakkad", "Kannur", "Kottayam", "Malappuram", "Manjeri", "Thalassery", "Koyilandy", "Kanhangad", "Vatakara", "Neyyattinkara", "Kayamkulam", "Ponnani", "Chalakudy", "Kothamangalam", "Perinthalmanna", "Tirur", "Kodungallur", "Kunnamkulam", "Ottapalam", "Shoranur", "Thiruvalla", "Pathanamthitta", "Adoor", "Mavelikkara", "Chengannur", "Mannar", "Punalur", "Paravur", "Attingal", "Varkala", "Nedumangad", "Kattakada", "Balaramapuram", "Nemom", "Chirayinkeezhu", "Vamanapuram", "Kilimanoor", "Vellanad", "Perumkadavila", "Parassala"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Pathankot", "Hoshiarpur", "Batala", "Moga", "Abohar", "Malerkotla", "Khanna", "Phagwara", "Muktsar", "Barnala", "Firozpur", "Kapurthala", "Sangrur", "Faridkot", "Fazilka", "Gurdaspur", "Rupnagar", "Mohali", "Fatehgarh Sahib", "Tarn Taran", "Nawanshahr", "Mansa"],
    "Haryana": ["Faridabad", "Gurugram", "Panipat", "Ambala", "Yamunanagar", "Rohtak", "Hisar", "Karnal", "Sonipat", "Panchkula", "Sirsa", "Bhiwani", "Bahadurgarh", "Jind", "Thanesar", "Kaithal", "Rewari", "Palwal", "Fatehabad", "Narnaul", "Hansi", "Narwana", "Tohana", "Safidon", "Ellenabad", "Adampur", "Barwala", "Bawal", "Dabwali", "Gharaunda", "Gohana", "Jagadhri", "Jhajjar", "Kalanwali", "Kalka", "Ladwa", "Mandi Dabwali", "Mustafabad", "Pehowa", "Pinjore", "Rania", "Ratia", "Samalkha", "Shahbad", "Sohna", "Taraori"],
    "Himachal Pradesh": ["Shimla", "Dharamshala", "Mandi", "Solan", "Bilaspur", "Chamba", "Hamirpur", "Kangra", "Kinnaur", "Kullu", "Lahaul and Spiti", "Sirmaur", "Una", "Nahan", "Palampur", "Kasauli", "Manali", "Dalhousie", "McLeod Ganj"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Hazaribagh", "Deoghar", "Giridih", "Dumka", "Chaibasa", "Medininagar", "Ramgarh", "Sahibganj", "Pakur", "Godda", "Chatra", "Koderma", "Gumla", "Lohardaga", "Simdega", "Palamu", "Latehar", "Garhwa"],
    "Assam": ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tinsukia", "Tezpur", "Bongaigaon", "Dhubri", "Goalpara", "Barpeta", "Sivasagar", "Karimganj", "Hailakandi", "Cachar", "Dima Hasao", "Karbi Anglong", "Kokrajhar", "Baksa", "Udalguri", "Chirang", "Kamrup", "Kamrup Metropolitan", "Nalbari", "South Salmara-Mankachar", "West Karbi Anglong", "Dhemaji", "Lakhimpur", "Majuli", "Charaideo", "Hojai"],
    "Arunachal Pradesh": ["Itanagar", "Naharlagun", "Tawang", "Bomdila", "Ziro", "Pasighat", "Tezu", "Roing", "Daporijo", "Along", "Yingkiong", "Anini", "Khonsa", "Changlang", "Miao", "Namsai", "Hayuliang"],
    "Manipur": ["Imphal", "Thoubal", "Bishnupur", "Churachandpur", "Ukhrul", "Senapati", "Tamenglong", "Chandel", "Kangpokpi", "Jiribam", "Kakching", "Kamjong", "Noney", "Pherzawl", "Tengnoupal"],
    "Meghalaya": ["Shillong", "Tura", "Jowai", "Nongpoh", "Nongstoin", "Baghmara", "Williamnagar", "Resubelpara", "Ampati", "Mairang", "Mawkyrwat", "Mawphlang"],
    "Mizoram": ["Aizawl", "Lunglei", "Saiha", "Champhai", "Kolasib", "Serchhip", "Lawngtlai", "Mamit", "Saitual", "Khawzawl", "Hnahthial"],
    "Nagaland": ["Kohima", "Dimapur", "Mokokchung", "Tuensang", "Wokha", "Zunheboto", "Mon", "Phek", "Kiphire", "Longleng", "Peren", "Noklak"],
    "Sikkim": ["Gangtok", "Namchi", "Mangan", "Gyalshing", "Singtam", "Rangpo", "Jorethang", "Pakyong"],
    "Tripura": ["Agartala", "Udaipur", "Dharmanagar", "Kailasahar", "Belonia", "Khowai", "Teliamura", "Ambassa", "Sabroom", "Kamalpur"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda", "Bicholim", "Curchorem", "Canacona", "Sanguem", "Valpoi", "Quepem", "Pernem"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Rajnandgaon", "Raigarh", "Jagdalpur", "Ambikapur", "Dhamtari", "Mahasamund", "Kanker", "Kawardha", "Janjgir-Champa", "Mungeli", "Balod", "Bemetara", "Baloda Bazar", "Balrampur", "Bastar", "Bijapur", "Dantewada", "Gariaband", "Jashpur", "Kabirdham", "Kondagaon", "Koriya", "Narayanpur", "Sukma", "Surajpur", "Surguja"],
    "Jammu and Kashmir": ["Srinagar", "Jammu", "Anantnag", "Baramulla", "Sopore", "Kathua", "Udhampur", "Rajouri", "Poonch", "Doda", "Kishtwar", "Ramban", "Reasi", "Samba", "Ganderbal", "Bandipora", "Kulgam", "Pulwama", "Shopian", "Budgam", "Kupwara"],
    "Ladakh": ["Leh", "Kargil", "Nubra", "Zanskar", "Drass", "Diskit", "Hemis", "Alchi"],
    "Andaman and Nicobar Islands": ["Port Blair", "Diglipur", "Mayabunder", "Rangat", "Car Nicobar", "Kamorta", "Katchal", "Nancowry", "Little Andaman"],
    "Chandigarh": ["Chandigarh", "Sector 1", "Sector 17", "Sector 43", "Manimajra"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Daman", "Diu", "Silvassa", "Naroli", "Amli", "Khanvel"],
    "Delhi": ["New Delhi", "North Delhi", "South Delhi", "East Delhi", "West Delhi", "Central Delhi", "North East Delhi", "North West Delhi", "South West Delhi", "Shahdara", "Rohini", "Dwarka", "Pitampura", "Laxmi Nagar", "Karol Bagh", "Connaught Place", "Rajouri Garden", "Janakpuri", "Palam", "Najafgarh"],
    "Lakshadweep": ["Kavaratti", "Agatti", "Amini", "Andrott", "Bitra", "Chettat", "Kadmat", "Kalpeni", "Kilthan", "Minicoy"],
    "Puducherry": ["Puducherry", "Karaikal", "Mahe", "Yanam", "Ozhukarai", "Ariyankuppam", "Villianur"],
}


def _dedupe(lst: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in lst:
        k = x.lower().strip()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


# Deduplicated city list per state (same from beginning everywhere)
INDIA_CITIES_BY_STATE: Dict[str, List[str]] = {
    state: _dedupe(cities) for state, cities in _RAW_CITIES.items()
}

# UP must have 75+ cities
assert len(INDIA_CITIES_BY_STATE.get("Uttar Pradesh", [])) >= 75, "Uttar Pradesh must have at least 75 cities"

# For country_admin: list of {"name": state_name}
INDIA_STATES_FULL = [{"name": s["name"]} for s in INDIA_STATES]


def state_code_to_name(code: str) -> str | None:
    """2-letter state code -> state name."""
    if not code or len(code) > 4:
        return None
    c = code.strip().upper()
    for s in INDIA_STATES:
        if (s.get("code") or "").upper() == c:
            return s.get("name")
    return None


def get_cities_for_state(state_name: str) -> List[dict]:
    """Return list of {name, city} for API response. state_name must match exactly."""
    cities = INDIA_CITIES_BY_STATE.get(state_name)
    if not cities:
        return []
    return [{"name": c, "city": c} for c in cities]
