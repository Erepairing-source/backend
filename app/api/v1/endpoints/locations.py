"""
Location endpoints (Countries, States, Cities)
Enhanced with comprehensive API integration
Special support for India with multiple API sources
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import httpx
import os

from app.core.database import get_db
from app.models.location import Country, State, City

router = APIRouter()

# API configurations
COUNTRY_STATE_CITY_API_KEY = os.getenv("COUNTRY_STATE_CITY_API_KEY", "")
COUNTRY_STATE_CITY_BASE_URL = "https://api.countrystatecity.in/v1"

# Indian-specific APIs (no API key required)
# Bharat API: https://github.com/AshokWebWorks/Bharat-States-Cities-API
BHARAT_API_BASE_URL = "https://bharat-api.vercel.app/api"
REST_INDIA_API_BASE_URL = "https://restcountries.com/api/v3.1/name/india"
# Alternative free API for Indian locations
INDIA_LOCATION_API = "https://api.countrystatecity.in/v1"


async def fetch_from_api(url: str, headers: dict = None, timeout: float = 10.0):
    """Fetch data from any API"""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            print(f"[API] Response: {url} - Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"[SUCCESS] API returned data: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
                return data
            elif response.status_code == 401:
                # API key issue - fallback to database
                print(f"[ERROR] API Authentication failed (401)")
                return None
            else:
                print(f"[ERROR] API returned status {response.status_code}: {response.text[:200]}")
                return None
    except Exception as e:
        print(f"[ERROR] API fetch error for {url}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def get_india_states_static():
    """Get comprehensive Indian states from static data"""
    return [
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
        {"name": "Puducherry", "code": "PY", "capital": "Puducherry"}
    ]


async def get_india_states_from_bharat_api():
    """Get comprehensive Indian states from Bharat API with multiple fallbacks"""
    try:
        # Try multiple possible endpoints for Bharat API
        urls_to_try = [
            f"{BHARAT_API_BASE_URL}/states",
            "https://bharat-api.vercel.app/states",
            "https://bharat-api.vercel.app/api/states",
            "https://api.countrystatecity.in/v1/countries/IN/states"  # Alternative API
        ]
        
        for url in urls_to_try:
            print(f"[BHARAT] Trying API: {url}")
            headers = {}
            # Add API key if available for countrystatecity API
            if "countrystatecity" in url and COUNTRY_STATE_CITY_API_KEY:
                headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
            
            data = await fetch_from_api(url, headers=headers if headers else None, timeout=15.0)
            if data and isinstance(data, list) and len(data) > 0:
                print(f"[SUCCESS] API returned {len(data)} states from {url}")
                # Normalize data format
                if isinstance(data[0], dict) and "name" in data[0]:
                    return data
                # If data is in different format, normalize it
                normalized = []
                for item in data:
                    if isinstance(item, dict):
                        normalized.append({
                            "name": item.get("name", item.get("state", "")),
                            "code": item.get("code", item.get("iso2", "")),
                            "capital": item.get("capital", ""),
                            "districts": item.get("districts", [])
                        })
                if normalized:
                    return normalized
            elif data:
                print(f"[WARNING] API returned data but not a list: {type(data)}")
        
        print(f"[FALLBACK] All API endpoints failed, using comprehensive static data")
        # Return comprehensive static data as fallback
        return get_india_states_static()
    except Exception as e:
        print(f"[ERROR] API error: {str(e)}, using static data")
        # Return static data on any error
        return get_india_states_static()


def get_india_cities_static(state_name: str):
    """Get comprehensive Indian cities from static data by state name"""
    # Comprehensive city data for all Indian states
    # Note: Some cities may appear multiple times in the list (they're in different districts)
    # We'll deduplicate them when returning
    cities_data = {
        "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad", "Solapur", "Thane", "Kalyan", "Vasai-Virar", "Navi Mumbai", "Sangli", "Kolhapur", "Amravati", "Nanded", "Jalgaon", "Akola", "Latur", "Dhule", "Ahmednagar", "Chandrapur", "Parbhani", "Ichalkaranji", "Jalna", "Bhusawal", "Panvel", "Satara", "Beed", "Yavatmal", "Kamptee", "Gondia", "Barshi", "Achalpur", "Osmanabad", "Nandurbar", "Wardha", "Udgir", "Hinganghat"],
        "Karnataka": ["Bengaluru", "Mysuru", "Hubli-Dharwad", "Mangalore", "Belagavi", "Kalaburagi", "Davangere", "Ballari", "Tumakuru", "Shivamogga", "Raichur", "Bijapur", "Hassan", "Udupi", "Bhadravati", "Chitradurga", "Robertson Pet", "Kolar", "Mandya", "Chikmagalur", "Gangawati", "Bagalkot", "Ranebennuru", "Hospet", "Gokak", "Yadgir", "Karwar", "Koppal", "Haveri", "Gadag-Betigeri", "Sirsi", "Chamrajnagar", "Chintamani", "Anekal", "Srinivaspur"],
        "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli", "Erode", "Vellore", "Tuticorin", "Dindigul", "Thanjavur", "Hosur", "Nagercoil", "Kanchipuram", "Karaikudi", "Neyveli", "Cuddalore", "Kumbakonam", "Tiruvannamalai", "Pollachi", "Rajapalayam", "Gudiyatham", "Pudukkottai", "Vaniyambadi", "Ambur", "Nagapattinam", "Tirupathur", "Sivakasi", "Krishnagiri", "Dharmapuri", "Thiruvallur", "Tindivanam", "Villupuram", "Kallakurichi", "Ariyalur", "Perambalur", "Karur", "Namakkal", "Theni", "Tenkasi", "Ramanathapuram", "Sivaganga", "Virudhunagar", "Thoothukudi", "Kanyakumari"],
        "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Gandhinagar", "Junagadh", "Gandhidham", "Anand", "Navsari", "Morbi", "Nadiad", "Surendranagar", "Bharuch", "Mehsana", "Bhuj", "Porbandar", "Palanpur", "Valsad", "Vapi", "Gondal", "Veraval", "Godhra", "Patan", "Kalol", "Dahej", "Botad", "Amreli", "Palanpur", "Modasa", "Palanpur"],
        "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur", "Bhilwara", "Alwar", "Bharatpur", "Sri Ganganagar", "Sikar", "Tonk", "Pali", "Chittorgarh", "Hanumangarh", "Beawar", "Kishangarh", "Jhunjhunu", "Baran", "Churu", "Banswara", "Dausa", "Bundi", "Jhalawar", "Nagaur", "Pratapgarh", "Rajsamand", "Sawai Madhopur", "Sirohi", "Dholpur", "Karauli", "Jalore", "Baran"],
        "Uttar Pradesh": ["Lucknow", "Kanpur", "Ghaziabad", "Agra", "Meerut", "Varanasi", "Allahabad", "Noida", "Bareilly", "Aligarh", "Moradabad", "Saharanpur", "Gorakhpur", "Faizabad", "Jhansi", "Muzaffarnagar", "Mathura", "Rampur", "Shahjahanpur", "Firozabad", "Etawah", "Sitapur", "Budaun", "Pilibhit", "Hapur", "Bulandshahr", "Amroha", "Hardoi", "Fatehpur", "Raebareli", "Orai", "Sultanpur", "Bahraich", "Deoria", "Banda", "Unnao", "Mainpuri", "Lalitpur", "Etah", "Bijnor", "Mirzapur", "Sambhal", "Shamli", "Azamgarh", "Kasganj", "Bhadohi", "Kaushambi", "Farrukhabad", "Kannauj", "Basti", "Gonda", "Siddharthnagar", "Maharajganj", "Ballia", "Jaunpur", "Mau", "Ghazipur", "Chandauli", "Sonbhadra", "Sant Kabir Nagar", "Kushinagar", "Mahoba", "Hamirpur", "Jalaun", "Auraiya", "Kheri", "Pratapgarh", "Ambedkar Nagar", "Kushinagar"],
        "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri", "Bardhaman", "Malda", "Baharampur", "Habra", "Kharagpur", "Shantipur", "Dankuni", "Dhulian", "Ranaghat", "Haldia", "Raiganj", "Krishnanagar", "Nabadwip", "Medinipur", "Jalpaiguri", "Balurghat", "Bankura", "Darjeeling", "Alipurduar", "Purulia", "Jhargram", "Kalimpong"],
        "Madhya Pradesh": ["Indore", "Bhopal", "Gwalior", "Jabalpur", "Ujjain", "Sagar", "Ratlam", "Satna", "Rewa", "Murwara", "Singrauli", "Burhanpur", "Khandwa", "Chhindwara", "Guna", "Shivpuri", "Vidisha", "Chhatarpur", "Damoh", "Mandsaur", "Khargone", "Neemuch", "Pithampur", "Itarsi", "Nagda", "Morena", "Bhind", "Guna", "Shivpuri", "Datia", "Ashoknagar", "Tikamgarh", "Chhatarpur", "Panna", "Sagar", "Damoh", "Katni", "Jabalpur", "Narsinghpur", "Seoni", "Mandla", "Dindori", "Anuppur", "Shahdol", "Umaria", "Rewa", "Satna", "Sidhi", "Singrauli", "Chhindwara", "Betul", "Harda", "Hoshangabad", "Raisen", "Vidisha", "Rajgarh", "Shajapur", "Dewas", "Ujjain", "Ratlam", "Mandsaur", "Neemuch", "Jhabua", "Alirajpur", "Barwani", "Burhanpur", "Khandwa", "Khargone", "Dhar", "Indore", "Dewas", "Shajapur", "Agar Malwa", "Rajgarh", "Bhopal", "Raisen", "Vidisha", "Sehore"],
        "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Darbhanga", "Purnia", "Bihar Sharif", "Arrah", "Begusarai", "Katihar", "Munger", "Chhapra", "Saharsa", "Sasaram", "Hajipur", "Dehri", "Bettiah", "Motihari", "Siwan", "Nawada", "Jamalpur", "Buxar", "Kishanganj", "Sitamarhi", "Jehanabad", "Aurangabad", "Lakhisarai", "Nalanda", "Banka", "Gopalganj", "Vaishali", "Saran", "Samastipur", "Madhubani", "Darbhanga", "Supaul", "Araria", "Kishanganj", "Purnia", "Katihar", "Madhepura", "Saharsa", "Khagaria", "Bhagalpur", "Munger", "Lakhisarai", "Sheikhpura", "Nalanda", "Patna", "Bhojpur", "Buxar", "Kaimur", "Rohtas", "Aurangabad", "Gaya", "Jehanabad", "Nawada", "Jamui", "Banka", "Munger", "Lakhisarai", "Sheikhpura", "Nalanda", "Patna", "Saran", "Siwan", "Gopalganj", "Vaishali", "Muzaffarpur", "East Champaran", "West Champaran", "Sheohar", "Sitamarhi", "Madhubani", "Supaul", "Araria", "Kishanganj", "Purnia", "Katihar", "Madhepura", "Saharsa", "Darbhanga", "Samastipur", "Begusarai", "Khagaria", "Bhagalpur", "Munger", "Lakhisarai", "Sheikhpura", "Nalanda", "Patna", "Bhojpur", "Buxar", "Kaimur", "Rohtas", "Aurangabad", "Gaya", "Jehanabad", "Nawada", "Jamui", "Banka"],
        "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Puri", "Baleshwar", "Bhadrak", "Baripada", "Balangir", "Jharsuguda", "Bargarh", "Rayagada", "Jeypore", "Bhawanipatna", "Dhenkanal", "Angul", "Talcher", "Barbil", "Kendujhar", "Paradip", "Jagatsinghapur", "Kendrapara", "Bhadrak", "Balasore", "Mayurbhanj", "Keonjhar", "Sundargarh", "Jharsuguda", "Sambalpur", "Bargarh", "Balangir", "Nuapada", "Kalahandi", "Rayagada", "Koraput", "Nabarangpur", "Malkangiri", "Gajapati", "Ganjam", "Gajapati", "Kandhamal", "Boudh", "Sonepur", "Balangir", "Nuapada", "Kalahandi", "Rayagada", "Koraput", "Nabarangpur", "Malkangiri"],
        "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Rajahmundry", "Tirupati", "Kakinada", "Kadapa", "Anantapur", "Eluru", "Nandyal", "Ongole", "Chittoor", "Hindupur", "Machilipatnam", "Adoni", "Tenali", "Chilakaluripet", "Proddatur", "Bhimavaram", "Nandyal", "Eluru", "Ongole", "Chittoor", "Hindupur", "Machilipatnam", "Adoni", "Tenali", "Chilakaluripet", "Proddatur", "Bhimavaram", "Narasaraopet", "Palakollu", "Srikakulam", "Vizianagaram", "Parvathipuram Manyam", "Alluri Sitharama Raju", "Eluru", "NTR", "Palnadu", "Bapatla", "Prakasam", "Nellore", "Tirupati", "Annamayya", "Chittoor", "YSR Kadapa", "Anantapur", "Sri Sathya Sai", "Kurnool", "Nandyal"],
        "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Ramagundam", "Khammam", "Mahbubnagar", "Nalgonda", "Adilabad", "Siddipet", "Suryapet", "Miryalaguda", "Jagtial", "Narayanpet", "Mancherial", "Kamareddy", "Sangareddy", "Medak", "Medchal-Malkajgiri", "Rangareddy", "Hyderabad", "Sangareddy", "Medak", "Medchal-Malkajgiri", "Rangareddy", "Hyderabad", "Sangareddy", "Medak", "Medchal-Malkajgiri", "Rangareddy"],
        "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam", "Alappuzha", "Palakkad", "Kannur", "Kottayam", "Malappuram", "Manjeri", "Thalassery", "Koyilandy", "Kanhangad", "Vatakara", "Neyyattinkara", "Kayamkulam", "Ponnani", "Chalakudy", "Kothamangalam", "Perinthalmanna", "Tirur", "Kodungallur", "Kunnamkulam", "Ottapalam", "Shoranur", "Thiruvalla", "Pathanamthitta", "Adoor", "Mavelikkara", "Chengannur", "Mannar", "Punalur", "Paravur", "Attingal", "Varkala", "Nedumangad", "Kattakada", "Neyyattinkara", "Balaramapuram", "Nemom", "Varkala", "Attingal", "Chirayinkeezhu", "Vamanapuram", "Kilimanoor", "Nedumangad", "Vellanad", "Perumkadavila", "Parassala", "Neyyattinkara", "Balaramapuram", "Nemom"],
        "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Pathankot", "Hoshiarpur", "Batala", "Moga", "Abohar", "Malerkotla", "Khanna", "Phagwara", "Muktsar", "Barnala", "Firozpur", "Kapurthala", "Sangrur", "Faridkot", "Fazilka", "Gurdaspur", "Rupnagar", "Mohali", "Fatehgarh Sahib", "Tarn Taran", "Nawanshahr", "Mansa"],
        "Haryana": ["Faridabad", "Gurugram", "Panipat", "Ambala", "Yamunanagar", "Rohtak", "Hisar", "Karnal", "Sonipat", "Panchkula", "Sirsa", "Bhiwani", "Bahadurgarh", "Jind", "Thanesar", "Kaithal", "Rewari", "Palwal", "Fatehabad", "Narnaul", "Hansi", "Narwana", "Tohana", "Safidon", "Ellenabad", "Adampur", "Barwala", "Bawal", "Dabwali", "Fatehabad", "Gharaunda", "Gohana", "Jagadhri", "Jhajjar", "Kalanwali", "Kalka", "Ladwa", "Mandi Dabwali", "Mustafabad", "Narwana", "Pehowa", "Pinjore", "Rania", "Ratia", "Safidon", "Samalkha", "Shahbad", "Sohna", "Taraori", "Tohana", "Yamunanagar"],
        "Himachal Pradesh": ["Shimla", "Dharamshala", "Mandi", "Solan", "Bilaspur", "Chamba", "Hamirpur", "Kangra", "Kinnaur", "Kullu", "Lahaul and Spiti", "Sirmaur", "Una", "Nahan", "Palampur", "Kasauli", "Manali", "Dalhousie", "McLeod Ganj"],
        "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Hazaribagh", "Deoghar", "Giridih", "Dumka", "Chaibasa", "Medininagar", "Ramgarh", "Sahibganj", "Pakur", "Godda", "Chatra", "Koderma", "Gumla", "Lohardaga", "Simdega", "Palamu", "Latehar", "Garhwa"],
        "Assam": ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tinsukia", "Tezpur", "Bongaigaon", "Dhubri", "Goalpara", "Barpeta", "Sivasagar", "Karimganj", "Hailakandi", "Cachar", "Dima Hasao", "Karbi Anglong", "Kokrajhar", "Baksa", "Udalguri", "Chirang", "Bongaigaon", "Kamrup", "Kamrup Metropolitan", "Nalbari", "Barpeta", "Bongaigaon", "Goalpara", "Dhubri", "South Salmara-Mankachar", "Kokrajhar", "Chirang", "Baksa", "Udalguri", "West Karbi Anglong", "Dima Hasao", "Karbi Anglong", "Dhemaji", "Lakhimpur", "Majuli", "Sivasagar", "Charaideo", "Hojai", "West Karbi Anglong", "Hailakandi", "Karimganj", "Cachar"],
        "Arunachal Pradesh": ["Itanagar", "Naharlagun", "Tawang", "Bomdila", "Ziro", "Pasighat", "Tezu", "Roing", "Daporijo", "Along", "Yingkiong", "Anini", "Khonsa", "Changlang", "Miao", "Namsai", "Roing", "Tezu", "Hayuliang"],
        "Manipur": ["Imphal", "Thoubal", "Bishnupur", "Churachandpur", "Ukhrul", "Senapati", "Tamenglong", "Chandel", "Kangpokpi", "Jiribam", "Kakching", "Kamjong", "Noney", "Pherzawl", "Tengnoupal"],
        "Meghalaya": ["Shillong", "Tura", "Jowai", "Nongpoh", "Nongstoin", "Baghmara", "Williamnagar", "Resubelpara", "Ampati", "Mairang", "Mawkyrwat", "Mawphlang"],
        "Mizoram": ["Aizawl", "Lunglei", "Saiha", "Champhai", "Kolasib", "Serchhip", "Lawngtlai", "Mamit", "Saitual", "Khawzawl", "Hnahthial"],
        "Nagaland": ["Kohima", "Dimapur", "Mokokchung", "Tuensang", "Wokha", "Zunheboto", "Mon", "Phek", "Kiphire", "Longleng", "Peren", "Noklak"],
        "Sikkim": ["Gangtok", "Namchi", "Mangan", "Gyalshing", "Singtam", "Rangpo", "Jorethang", "Pakyong"],
        "Tripura": ["Agartala", "Udaipur", "Dharmanagar", "Kailasahar", "Belonia", "Khowai", "Teliamura", "Ambassa", "Sabroom", "Kamalpur"],
        "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda", "Bicholim", "Curchorem", "Canacona", "Sanguem", "Valpoi", "Quepem", "Pernem"],
        "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Rajnandgaon", "Raigarh", "Jagdalpur", "Ambikapur", "Dhamtari", "Mahasamund", "Kanker", "Kawardha", "Janjgir-Champa", "Mungeli", "Balod", "Bemetara", "Baloda Bazar", "Balrampur", "Bastar", "Bijapur", "Dantewada", "Dhamtari", "Durg", "Gariaband", "Janjgir-Champa", "Jashpur", "Kabirdham", "Kanker", "Kondagaon", "Korba", "Koriya", "Mahasamund", "Mungeli", "Narayanpur", "Raigarh", "Raipur", "Rajnandgaon", "Sukma", "Surajpur", "Surguja"],
        "Jammu and Kashmir": ["Srinagar", "Jammu", "Anantnag", "Baramulla", "Sopore", "Kathua", "Udhampur", "Rajouri", "Poonch", "Doda", "Kishtwar", "Ramban", "Reasi", "Samba", "Ganderbal", "Bandipora", "Kulgam", "Pulwama", "Shopian", "Budgam", "Kupwara"],
        "Ladakh": ["Leh", "Kargil", "Nubra", "Zanskar", "Drass", "Diskit", "Hemis", "Alchi"],
        "Andaman and Nicobar Islands": ["Port Blair", "Diglipur", "Mayabunder", "Rangat", "Car Nicobar", "Kamorta", "Katchal", "Nancowry", "Little Andaman"],
        "Chandigarh": ["Chandigarh", "Sector 1", "Sector 17", "Sector 43", "Manimajra"],
        "Dadra and Nagar Haveli and Daman and Diu": ["Daman", "Diu", "Silvassa", "Naroli", "Amli", "Khanvel"],
        "Delhi": ["New Delhi", "North Delhi", "South Delhi", "East Delhi", "West Delhi", "Central Delhi", "North East Delhi", "North West Delhi", "South West Delhi", "Shahdara", "Rohini", "Dwarka", "Pitampura", "Laxmi Nagar", "Karol Bagh", "Connaught Place", "Rajouri Garden", "Janakpuri", "Palam", "Najafgarh"],
        "Lakshadweep": ["Kavaratti", "Agatti", "Amini", "Andrott", "Bitra", "Chettat", "Kadmat", "Kalpeni", "Kilthan", "Minicoy"],
        "Puducherry": ["Puducherry", "Karaikal", "Mahe", "Yanam", "Ozhukarai", "Ariyankuppam", "Villianur"]
    }
    
    # Normalize state name for lookup
    state_name_lower = state_name.lower().strip()
    for state_key, cities_list in cities_data.items():
        if state_key.lower() == state_name_lower:
            # Deduplicate cities while preserving order
            seen = set()
            unique_cities = []
            for city in cities_list:
                city_lower = city.lower().strip()
                if city_lower not in seen:
                    seen.add(city_lower)
                    unique_cities.append(city)
            return [{"name": city, "city": city} for city in unique_cities]
    
    # Return empty if state not found
    return []


async def get_india_cities_from_bharat_api(state_name: str):
    """Get comprehensive Indian cities from Bharat API by state name with multiple fallbacks"""
    try:
        # Get state code for alternative API
        state_code = None
        states_list = get_india_states_static()
        for state in states_list:
            if state.get("name", "").lower() == state_name.lower():
                state_code = state.get("code", "")
                break
        
        # Try multiple API endpoints
        urls_to_try = []
        if state_code:
            urls_to_try.append(f"https://api.countrystatecity.in/v1/countries/IN/states/{state_code}/cities")
        urls_to_try.extend([
            f"{BHARAT_API_BASE_URL}/cities/{state_name}",
            f"https://bharat-api.vercel.app/cities/{state_name}",
            f"https://bharat-api.vercel.app/api/cities/{state_name}"
        ])
        
        for url in urls_to_try:
            print(f"[BHARAT] Trying cities API: {url}")
            headers = {}
            # Add API key if available for countrystatecity API
            if "countrystatecity" in url and COUNTRY_STATE_CITY_API_KEY:
                headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
            
            data = await fetch_from_api(url, headers=headers if headers else None, timeout=10.0)
            if data and isinstance(data, list) and len(data) > 0:
                print(f"[SUCCESS] API returned {len(data)} cities for {state_name}")
                # Normalize data format
                normalized = []
                for item in data:
                    if isinstance(item, dict):
                        normalized.append({
                            "name": item.get("name", item.get("city", "")),
                            "city": item.get("name", item.get("city", "")),
                            "district": item.get("district", ""),
                            "latitude": item.get("latitude", ""),
                            "longitude": item.get("longitude", "")
                        })
                if normalized:
                    return normalized
                return data
        
        print(f"[FALLBACK] All APIs failed, using static data for {state_name}")
        # Use static data as fallback
        return get_india_cities_static(state_name)
    except Exception as e:
        print(f"[ERROR] API cities error: {str(e)}, using static data")
        # Return static data on any error
        return get_india_cities_static(state_name)


async def get_india_states_from_rest_india():
    """Get Indian states from REST India API"""
    try:
        # This is a GitHub-based API, might need different endpoint
        # For now, we'll use Bharat API as primary
        return None
    except Exception:
        return None


@router.get("/countries", response_model=List[dict])
async def list_countries(
    use_api: bool = Query(False, description="Use external API if available"),
    db: Session = Depends(get_db)
):
    """List all countries - uses comprehensive API if available, falls back to database"""
    
    # Try API first if requested and API key is available
    if use_api and COUNTRY_STATE_CITY_API_KEY:
        headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
        api_url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries"
        api_data = await fetch_from_api(api_url, headers)
        
        if api_data:
            # Return comprehensive API data
            return [
                {
                    "id": None,  # API doesn't provide IDs
                    "name": country.get("name", ""),
                    "code": country.get("iso2", ""),
                    "iso3": country.get("iso3", ""),
                    "phone_code": country.get("phonecode", ""),
                    "currency": country.get("currency", ""),
                    "currency_symbol": country.get("currency_symbol", ""),
                    "region": country.get("region", ""),
                    "subregion": country.get("subregion", ""),
                    "latitude": country.get("latitude", ""),
                    "longitude": country.get("longitude", ""),
                    "emoji": country.get("emoji", ""),
                    "from_api": True
                }
                for country in api_data
            ]
    
    # Fallback to database
    countries = db.query(Country).order_by(Country.name).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "code": c.code,
            "from_api": False
        }
        for c in countries
    ]


@router.get("/states", response_model=List[dict])
async def list_states(
    country_id: Optional[int] = Query(None, description="Country ID from database"),
    country_code: Optional[str] = Query(None, description="Country ISO2 code (e.g., 'IN', 'US')"),
    use_api: bool = Query(True, description="Use external API if available"),
    db: Session = Depends(get_db)
):
    """List states for a country - uses comprehensive API if available
    Special handling for India with Bharat API for comprehensive data
    """
    
    # Determine country code - prioritize code, but get from database if needed
    country_code_to_use = country_code
    country_name = None
    
    if not country_code_to_use and country_id:
        # Get country code from database
        country = db.query(Country).filter(Country.id == country_id).first()
        if country:
            country_code_to_use = country.code
            country_name = country.name
    
    # Special handling for India - use Bharat API for comprehensive data
    # ALWAYS check if it's India, regardless of use_api parameter
    is_india = False
    if country_code_to_use and country_code_to_use.upper() == "IN":
        is_india = True
        print(f"[INDIA] India detected by country_code: {country_code_to_use}")
    elif country_id:  # Check if country_id corresponds to India
        # Get country from database to check if it's India
        country = db.query(Country).filter(Country.id == country_id).first()
        if country:
            print(f"[CHECK] Checking country_id={country_id}: name={country.name}, code={country.code}")
            if (country.code and country.code.upper() == "IN") or country.name.lower() == "india":
                is_india = True
                country_code_to_use = "IN"
                print(f"[INDIA] India detected by country_id={country_id}")
            else:
                print(f"[SKIP] Not India: country_id={country_id}, code={country.code}, name={country.name}")
        else:
            print(f"[ERROR] Country not found for country_id={country_id}")
    
    # ALWAYS use Bharat API for India, regardless of use_api flag
    if is_india:
        print(f"[BHARAT] Using Bharat API for India (country_id={country_id}, code={country_code_to_use})")
        bharat_data = await get_india_states_from_bharat_api()
        if bharat_data:
            print(f"[SUCCESS] Returning {len(bharat_data)} states from Bharat API")
            # Bharat API returns comprehensive Indian states data
            return [
                {
                    "id": None,
                    "name": state.get("name", state.get("state", "")),
                    "code": state.get("code", state.get("state_code", "")),
                    "country_id": country_id,
                    "country_code": "IN",
                    "country_name": "India",
                    "capital": state.get("capital", ""),
                    "districts": state.get("districts", []),
                    "from_api": True,
                    "api_source": "bharat"
                }
                for state in bharat_data
            ]
        else:
            print(f"[WARNING] Bharat API returned no data, falling back to database")
    
    # Try CountryStateCity API for other countries
    if use_api and COUNTRY_STATE_CITY_API_KEY and country_code_to_use:
        headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
        api_url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries/{country_code_to_use}/states"
        api_data = await fetch_from_api(api_url, headers)
        
        if api_data:
            # Return comprehensive API data
            return [
                {
                    "id": None,
                    "name": state.get("name", ""),
                    "code": state.get("iso2", ""),
                    "country_id": country_id,
                    "country_code": country_code_to_use,
                    "latitude": state.get("latitude", ""),
                    "longitude": state.get("longitude", ""),
                    "type": state.get("type", ""),
                    "from_api": True,
                    "api_source": "countrystatecity"
                }
                for state in api_data
            ]
    
    # Fallback to database
    if not country_id:
        raise HTTPException(status_code=400, detail="Either country_id or country_code is required")
    
    states = db.query(State).filter(State.country_id == country_id).order_by(State.name).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "country_id": s.country_id,
            "from_api": False
        }
        for s in states
    ]


@router.get("/cities", response_model=List[dict])
async def list_cities(
    state_id: Optional[int] = Query(None, description="State ID from database"),
    country_code: Optional[str] = Query(None, description="Country ISO2 code"),
    state_code: Optional[str] = Query(None, description="State ISO2 code"),
    state_name: Optional[str] = Query(None, description="State name (for India Bharat API)"),
    use_api: bool = Query(False, description="Use external API if available"),
    db: Session = Depends(get_db)
):
    """List cities for a state - uses comprehensive API if available
    Special handling for India with Bharat API for comprehensive city data
    """
    
    # Special handling for India - use Bharat API for comprehensive cities
    if country_code and country_code.upper() == "IN" and state_name:
        bharat_data = await get_india_cities_from_bharat_api(state_name)
        if bharat_data:
            # Bharat API returns comprehensive Indian cities data
            return [
                {
                    "id": None,
                    "name": city.get("name", city.get("city", "")),
                    "state_id": state_id,
                    "country_code": "IN",
                    "state_code": state_code,
                    "state_name": state_name,
                    "district": city.get("district", ""),
                    "latitude": city.get("latitude", ""),
                    "longitude": city.get("longitude", ""),
                    "from_api": True,
                    "api_source": "bharat"
                }
                for city in bharat_data
            ]
    
    # Try CountryStateCity API for other countries
    if use_api and COUNTRY_STATE_CITY_API_KEY and country_code and state_code:
        headers = {"X-CSCAPI-KEY": COUNTRY_STATE_CITY_API_KEY}
        api_url = f"{COUNTRY_STATE_CITY_BASE_URL}/countries/{country_code}/states/{state_code}/cities"
        api_data = await fetch_from_api(api_url, headers)
        
        if api_data:
            # Return comprehensive API data
            return [
                {
                    "id": None,
                    "name": city.get("name", ""),
                    "state_id": state_id,
                    "country_code": country_code,
                    "state_code": state_code,
                    "latitude": city.get("latitude", ""),
                    "longitude": city.get("longitude", ""),
                    "from_api": True,
                    "api_source": "countrystatecity"
                }
                for city in api_data
            ]
    
    # Fallback to database
    if not state_id:
        raise HTTPException(status_code=400, detail="Either state_id or both country_code and state_code are required")
    
    cities = db.query(City).filter(City.state_id == state_id).order_by(City.name).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "state_id": c.state_id,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "from_api": False
        }
        for c in cities
    ]


@router.get("/countries/{country_code}/states", response_model=List[dict])
async def get_states_by_country_code(
    country_code: str,
    use_api: bool = Query(True, description="Use external API"),
    db: Session = Depends(get_db)
):
    """Get states by country ISO2 code - optimized for API usage"""
    return await list_states(country_code=country_code.upper(), use_api=use_api, db=db)


@router.get("/countries/{country_code}/states/{state_code}/cities", response_model=List[dict])
async def get_cities_by_state_code(
    country_code: str,
    state_code: str,
    state_name: Optional[str] = Query(None, description="State name (for India)"),
    use_api: bool = Query(True, description="Use external API"),
    db: Session = Depends(get_db)
):
    """Get cities by country and state ISO2 codes - optimized for API usage
    For India, can also use state_name for Bharat API
    """
    return await list_cities(
        country_code=country_code.upper(), 
        state_code=state_code.upper(),
        state_name=state_name,
        use_api=use_api, 
        db=db
    )


@router.get("/india/states", response_model=List[dict])
async def get_india_states(
    use_api: bool = Query(True, description="Use Bharat API"),
    db: Session = Depends(get_db)
):
    """Get all Indian states - uses Bharat API for comprehensive data"""
    if use_api:
        bharat_data = await get_india_states_from_bharat_api()
        if bharat_data:
            return [
                {
                    "id": None,
                    "name": state.get("name", state.get("state", "")),
                    "code": state.get("code", state.get("state_code", "")),
                    "country_code": "IN",
                    "capital": state.get("capital", ""),
                    "districts": state.get("districts", []),
                    "from_api": True,
                    "api_source": "bharat"
                }
                for state in bharat_data
            ]
    
    # Fallback to database
    india = db.query(Country).filter(Country.code == "IN").first()
    if india:
        states = db.query(State).filter(State.country_id == india.id).order_by(State.name).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "country_id": s.country_id,
                "from_api": False
            }
            for s in states
        ]
    return []


@router.get("/india/states/{state_name}/cities", response_model=List[dict])
async def get_india_cities_by_state(
    state_name: str,
    use_api: bool = Query(True, description="Use Bharat API"),
    db: Session = Depends(get_db)
):
    """Get all cities for an Indian state by state name - uses Bharat API"""
    if use_api:
        bharat_data = await get_india_cities_from_bharat_api(state_name)
        if bharat_data:
            return [
                {
                    "id": None,
                    "name": city.get("name", city.get("city", "")),
                    "state_name": state_name,
                    "district": city.get("district", ""),
                    "latitude": city.get("latitude", ""),
                    "longitude": city.get("longitude", ""),
                    "from_api": True,
                    "api_source": "bharat"
                }
                for city in bharat_data
            ]
    
    # Fallback to database
    india = db.query(Country).filter(Country.code == "IN").first()
    if india:
        state = db.query(State).filter(
            State.country_id == india.id,
            State.name.ilike(f"%{state_name}%")
        ).first()
        if state:
            cities = db.query(City).filter(City.state_id == state.id).order_by(City.name).all()
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "state_id": c.state_id,
                    "from_api": False
                }
                for c in cities
            ]
    return []
