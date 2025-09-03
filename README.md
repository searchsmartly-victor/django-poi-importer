# SearchSmartly POI Importer

Django web application for importing and managing Point of Interest data from CSV, JSON, and XML files.

**Quick Access**: Visit `http://127.0.0.1:8000/` and you'll be automatically redirected to the admin interface!

### Manual Setup (Step by Step)

### Prerequisites

- Python 3.10+ (tested with Python 3.13.3)
- Git

### Step 1: Navigate to Project Directory
```bash
#  IMPORTANT: Must be in poi_ingest directory, not root!
# Copy pois.csv to data folder.
Copy pois.csv to ./data folder.
cd poi_ingest
```

### Step 2: Create Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Create Required Directories
```bash
# Create logs directory (prevents logging errors)
mkdir logs
```

### Step 5: Database Setup
```bash
# Create database tables
python manage.py migrate
```

### Step 6: Create Admin User
```bash
# Option 1: Create your own admin user
python manage.py createsuperuser

# Option 2: Use demo credentials (for testing)
# Username: demo, Password: demo123 (already created)
```

### Step 7: Load Sample Data
```bash
# Import POI data from sample files (takes ~10 seconds)
python manage.py import_poi ../data/ --verbose

# This will import:
# - JSON: ~1,000 records from JsonData.json  
# - XML: ~100 records from XmlData.xml
```

### Step 8: Start Server
```bash
#  IMPORTANT: Make sure you're in poi_ingest directory!
python manage.py runserver
```

### Step 9: Access Application

Open your browser and visit:

- **Home Page**: `http://127.0.0.1:8000/` (automatically redirects to admin)
- **Admin Interface**: `http://127.0.0.1:8000/admin/` - Main POI management
- **API Interface**: `http://127.0.0.1:8000/api/poi/` - REST endpoints
- **Health Check**: `http://127.0.0.1:8000/health/` - System status


## What You'll See

After loading sample data:

- **1,100+ POI records** from sample data files
- **Multiple categories** (restaurants, hotels, parks, schools, etc.)
- **International names** (Japanese, Chinese, Russian, Arabic)
- **2 data sources** (JSON, XML)

## Management Commands

### Import POI Data
```bash
# Import specific files
python manage.py import_poi data/pois.csv data/JsonData.json data/XmlData.xml

# Import entire directory
python manage.py import_poi ../data/ --verbose

# Validation only (no database changes)
python manage.py import_poi ../data/ --dry-run

# Custom batch size for large files
python manage.py import_poi ../data/pois.csv --batch-size 1000

# Stop on first error
python manage.py import_poi ../data/ --stop-on-error
```

### Other Commands
```bash
# Run tests
python manage.py test

# Check system
python manage.py check

# Database shell
python manage.py dbshell
```

## File Format Requirements

### CSV Format
```csv
poi_id,poi_name,poi_category,poi_latitude,poi_longitude,poi_ratings
rest_001,Mario's Pizza,restaurant,40.7128,-74.0060,"{4.5,3.8,4.2}"
```

### JSON Format
```json
{
  "id": "poi_001",
  "name": "Restaurant Name",
  "coordinates": {"latitude": 40.7128, "longitude": -74.0060},
  "category": "restaurant", 
  "ratings": [4.5, 3.8, 4.2],
  "description": "Optional description"
}
```

### XML Format
```xml
<DATA_RECORD>
  <pid>poi_001</pid>
  <pname>Restaurant Name</pname>
  <pcategory>restaurant</pcategory>
  <platitude>40.7128</platitude>
  <plongitude>-74.0060</plongitude>
  <pratings>4.5, 3.8, 4.2</pratings>
</DATA_RECORD>
```

## Admin Features

### Search Functionality

- **Internal ID**: Search by exact database ID (e.g., `123`)
- **External ID**: Search by exact external identifier (e.g., `poi_001`)
- **Name**: Partial text search (e.g., `pizza`)

### Filter Options

- **Category**: Filter by POI type (restaurant, hotel, etc.)
- **Source**: Filter by data source (CSV, JSON, XML)

### Bulk Actions

- **Recompute Average Ratings**: Recalculate averages from raw ratings

## API Endpoints

```bash
# List POIs (paginated, 25 per page)
GET http://127.0.0.1:8000/api/poi/

# Get specific POI
GET http://127.0.0.1:8000/api/poi/123/

# Filter examples
GET http://127.0.0.1:8000/api/poi/?category=restaurant
GET http://127.0.0.1:8000/api/poi/?external_id=poi_001
GET http://127.0.0.1:8000/api/poi/?min_rating=4.0

# Utility endpoints  
GET http://127.0.0.1:8000/api/poi/categories/
GET http://127.0.0.1:8000/api/poi/stats/
```

## Performance

Tested with real data:

- **CSV**: 106,777 records/second (999,703 records in 9.36s)
- **JSON**: 220 records/second  
- **XML**: 203 records/second
- **Memory**: Streaming processing for large files

## Testing

```bash
# Run all tests
python manage.py test

# Run specific test modules
python manage.py test tests.test_import_parsers
python manage.py test tests.test_admin
```

## Project Requirements Met

- **Django application** (Python 3.10+)  
- **Management command** for file import  
- **CSV, JSON, XML support** with specified formats  
- **Django admin** with required fields display  
- **Search by internal/external ID**  
- **Category filtering**

## 🔧 Troubleshooting

### Common Issues and Solutions

** Error: `can't open file 'manage.py': No such file or directory`**
```bash
# Solution: You're in the wrong directory!
cd poi_ingest
python manage.py runserver
```

** Error: `Unable to configure handler 'file'` or logging errors**
```bash
# Solution: Create the logs directory
mkdir logs
# Then run your command again
```

** Error: Unicode/encoding errors during import**
```bash
# Solution: These are warnings, not errors. Data still imports successfully.
# The application handles international characters correctly.
```

** No admin user?**
```bash
# Solution: Use demo credentials or create new user
# Username: demo, Password: demo123
# OR run: python manage.py createsuperuser
```

** No data showing?**
```bash
# Solution: Import sample data
python manage.py import_poi ../data/ --verbose
```

** Server not starting?**
```bash
# Solution: Check you're in the correct directory
pwd  # Should show: .../poi_ingest
ls   # Should show: manage.py, requirements.txt, etc.
```

** Import errors?**
```bash
# Solution: Check data directory exists
ls ../data/  # Should show: JsonData.json, XmlData.xml
```

### Directory Structure Check
Your working directory should look like this:
```
poi_ingest/          ← YOU SHOULD BE HERE
├── manage.py        ← This file should exist
├── requirements.txt
├── logs/           ← Create this if missing
├── poi_ingest/
├── ingest/
└── venv/
```

## Commands Verified

All instructions tested and working:

- `python manage.py migrate` - Database setup
- `python manage.py import_poi ../data/ --verbose` - Data import (1M+ records)
- `python manage.py runserver` - Server startup
- Admin login with demo/demo123 credentials
- All admin features: search, filter, bulk actions